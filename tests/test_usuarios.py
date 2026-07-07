# tests/test_usuarios.py — Fundación identidad web: tabla `usuarios` (Fase 1)

"""
Cubre el PASO 1 de la plataforma web (mapeo email ↔ teléfono):

  - El modelo `Usuario` y su tabla se crean vía `metadata.create_all()` (lo que
    corre `inicializar_db()` en cada arranque), con los UNIQUE de email/telefono.
  - Helpers: crear/buscar por email y por teléfono, normalización de email
    (lower()+strip()), unicidad (UNIQUE de email) y upsert idempotente de
    `crear_o_vincular_usuario` (re-vincular actualiza sin duplicar ni pisar).
  - Siembra `sembrar_usuarios_desde_stripe()` con un cliente Stripe MOCKEADO:
    customers con email → filas `usuarios`; re-correr es idempotente; customers
    sin email se omiten. Nada de llamadas reales a Stripe.

Sigue el patrón de fixture de tests/test_suscripcion_stripe_models.py: SQLite en
tmp_path con `importlib.reload(agent.memory)` para aislar el engine por test.
"""

import importlib

import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """DB SQLite aislada por test, con la tabla `usuarios` creada vía create_all."""
    db_path = tmp_path / "usuarios.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    await agent.memory.inicializar_db()
    return agent.memory


# ── Modelo + creación de tabla ───────────────────────────────────────────────


class TestModeloUsuario:
    @pytest.mark.asyncio
    async def test_insert_y_select_basico(self, db):
        from sqlalchemy import select

        async with db.async_session() as session:
            session.add(db.Usuario(
                email="cel@dona.app",
                telefono="14076936023",
                stripe_customer_id="cus_001",
            ))
            await session.commit()

        async with db.async_session() as session:
            row = (await session.execute(
                select(db.Usuario).where(db.Usuario.email == "cel@dona.app")
            )).scalar_one()
            assert row.id is not None
            assert row.telefono == "14076936023"
            assert row.stripe_customer_id == "cus_001"
            # timestamps autopoblados
            assert row.creado is not None
            assert row.actualizado is not None

    @pytest.mark.asyncio
    async def test_telefono_y_stripe_son_nullable(self, db):
        """Un usuario puede existir con solo email (aún sin WhatsApp ni Stripe)."""
        from sqlalchemy import select

        async with db.async_session() as session:
            session.add(db.Usuario(email="solo-email@dona.app"))
            await session.commit()

        async with db.async_session() as session:
            row = (await session.execute(
                select(db.Usuario).where(db.Usuario.email == "solo-email@dona.app")
            )).scalar_one()
            assert row.telefono is None
            assert row.stripe_customer_id is None

    @pytest.mark.asyncio
    async def test_email_unico_previene_duplicados(self, db):
        """El UNIQUE de email es la barrera 'una cuenta por email'."""
        from sqlalchemy.exc import IntegrityError

        async with db.async_session() as session:
            session.add(db.Usuario(email="dup@dona.app", telefono="111"))
            await session.commit()

        with pytest.raises(IntegrityError):
            async with db.async_session() as session:
                session.add(db.Usuario(email="dup@dona.app", telefono="222"))
                await session.commit()

    @pytest.mark.asyncio
    async def test_telefono_unico_previene_duplicados(self, db):
        """El UNIQUE de telefono es la barrera 'un teléfono por cuenta'."""
        from sqlalchemy.exc import IntegrityError

        async with db.async_session() as session:
            session.add(db.Usuario(email="a@dona.app", telefono="14076936023"))
            await session.commit()

        with pytest.raises(IntegrityError):
            async with db.async_session() as session:
                session.add(db.Usuario(email="b@dona.app", telefono="14076936023"))
                await session.commit()


# ── Helpers de búsqueda + normalización ──────────────────────────────────────


class TestHelpers:
    @pytest.mark.asyncio
    async def test_crear_y_buscar_por_email(self, db):
        creado = await db.crear_o_vincular_usuario("nuevo@dona.app", telefono="555")
        assert creado.id is not None

        encontrado = await db.obtener_usuario_por_email("nuevo@dona.app")
        assert encontrado is not None
        assert encontrado.id == creado.id
        assert encontrado.telefono == "555"

    @pytest.mark.asyncio
    async def test_buscar_por_telefono(self, db):
        await db.crear_o_vincular_usuario("tel@dona.app", telefono="14076936023")
        encontrado = await db.obtener_usuario_por_telefono("14076936023")
        assert encontrado is not None
        assert encontrado.email == "tel@dona.app"

    @pytest.mark.asyncio
    async def test_email_se_normaliza_al_crear(self, db):
        """'  Cel@DONA.app ' y 'cel@dona.app' son la misma cuenta."""
        await db.crear_o_vincular_usuario("  Cel@DONA.app ")
        # Guardado en su forma canónica
        por_norm = await db.obtener_usuario_por_email("cel@dona.app")
        assert por_norm is not None
        # Buscar con la variante ruidosa también resuelve (búsqueda normaliza)
        por_ruidoso = await db.obtener_usuario_por_email("  CEL@dona.APP  ")
        assert por_ruidoso is not None
        assert por_ruidoso.id == por_norm.id

    @pytest.mark.asyncio
    async def test_busqueda_email_inexistente_retorna_none(self, db):
        assert await db.obtener_usuario_por_email("nadie@dona.app") is None
        assert await db.obtener_usuario_por_email("") is None
        assert await db.obtener_usuario_por_telefono("000") is None


# ── Upsert idempotente ───────────────────────────────────────────────────────


class TestUpsert:
    @pytest.mark.asyncio
    async def test_upsert_idempotente_no_duplica(self, db):
        """Dos llamadas con el mismo email → una sola fila, mismo id."""
        from sqlalchemy import func, select

        u1 = await db.crear_o_vincular_usuario("mismo@dona.app", telefono="555")
        u2 = await db.crear_o_vincular_usuario("mismo@dona.app", telefono="555")
        assert u1.id == u2.id

        async with db.async_session() as session:
            total = (await session.execute(
                select(func.count()).select_from(db.Usuario)
                .where(db.Usuario.email == "mismo@dona.app")
            )).scalar_one()
            assert total == 1

    @pytest.mark.asyncio
    async def test_upsert_email_existente_actualiza_telefono_y_customer(self, db):
        """Email ya presente: si llegan telefono/customer nuevos, se rellenan."""
        await db.crear_o_vincular_usuario("crece@dona.app")  # sin telefono ni customer
        actualizado = await db.crear_o_vincular_usuario(
            "crece@dona.app", telefono="999", stripe_customer_id="cus_999"
        )
        assert actualizado.telefono == "999"
        assert actualizado.stripe_customer_id == "cus_999"

    @pytest.mark.asyncio
    async def test_upsert_no_pisa_datos_existentes_con_none(self, db):
        """Re-vincular sin telefono NO borra el teléfono ya guardado."""
        await db.crear_o_vincular_usuario("mantiene@dona.app", telefono="777", stripe_customer_id="cus_777")
        despues = await db.crear_o_vincular_usuario("mantiene@dona.app")  # sin datos nuevos
        assert despues.telefono == "777"
        assert despues.stripe_customer_id == "cus_777"

    @pytest.mark.asyncio
    async def test_upsert_normaliza_email_en_actualizacion(self, db):
        """La variante ruidosa del email cae sobre la misma fila (no crea otra)."""
        u1 = await db.crear_o_vincular_usuario("Mix@Dona.app", telefono="111")
        u2 = await db.crear_o_vincular_usuario("  mix@dona.APP ", stripe_customer_id="cus_mix")
        assert u1.id == u2.id
        assert u2.telefono == "111"                 # conservado
        assert u2.stripe_customer_id == "cus_mix"   # agregado

    @pytest.mark.asyncio
    async def test_email_vacio_lanza(self, db):
        with pytest.raises(ValueError):
            await db.crear_o_vincular_usuario("   ")


# ── Siembra desde Stripe (cliente MOCKEADO) ──────────────────────────────────


class _FakeCustomer:
    """Imita el objeto Customer del SDK de Stripe: atributo `.email`."""
    def __init__(self, email):
        self.email = email


class _FakeStripe:
    """Cliente Stripe falso: mapea customer_id → email in-memory, sin red."""
    def __init__(self, emails_por_customer):
        self._emails = emails_por_customer
        self.llamadas = []

        parent = self

        class _Customer:
            @staticmethod
            def retrieve(customer_id):
                parent.llamadas.append(customer_id)
                return _FakeCustomer(parent._emails.get(customer_id))

        self.Customer = _Customer


async def _crear_suscripcion(db, *, subscription_id, telefono, customer_id):
    async with db.async_session() as session:
        session.add(db.SuscripcionStripe(
            subscription_id=subscription_id,
            telefono=telefono,
            customer_id=customer_id,
            plan_codigo="premium",
            price_id="price_x",
            status="active",
            creditos_mensuales=100,
        ))
        await session.commit()


class TestSembrarDesdeStripe:
    @pytest.mark.asyncio
    async def test_siembra_crea_usuarios_desde_customers(self, db, monkeypatch):
        from sqlalchemy import select

        await _crear_suscripcion(db, subscription_id="sub_1", telefono="111", customer_id="cus_1")
        await _crear_suscripcion(db, subscription_id="sub_2", telefono="222", customer_id="cus_2")

        fake = _FakeStripe({"cus_1": "uno@dona.app", "cus_2": "dos@dona.app"})
        monkeypatch.setattr("agent.billing._stripe_client", lambda: fake)

        resumen = await db.sembrar_usuarios_desde_stripe()
        assert resumen["status"] == "ok"
        assert resumen["customers"] == 2
        assert resumen["sembrados"] == 2

        async with db.async_session() as session:
            usuarios = (await session.execute(select(db.Usuario))).scalars().all()
            por_email = {u.email: u for u in usuarios}
            assert por_email["uno@dona.app"].telefono == "111"
            assert por_email["uno@dona.app"].stripe_customer_id == "cus_1"
            assert por_email["dos@dona.app"].telefono == "222"

    @pytest.mark.asyncio
    async def test_siembra_es_idempotente(self, db, monkeypatch):
        from sqlalchemy import func, select

        await _crear_suscripcion(db, subscription_id="sub_1", telefono="111", customer_id="cus_1")
        fake = _FakeStripe({"cus_1": "uno@dona.app"})
        monkeypatch.setattr("agent.billing._stripe_client", lambda: fake)

        await db.sembrar_usuarios_desde_stripe()
        await db.sembrar_usuarios_desde_stripe()  # re-correr

        async with db.async_session() as session:
            total = (await session.execute(
                select(func.count()).select_from(db.Usuario)
            )).scalar_one()
            assert total == 1  # no duplicó

    @pytest.mark.asyncio
    async def test_customer_sin_email_se_omite(self, db, monkeypatch):
        from sqlalchemy import select

        await _crear_suscripcion(db, subscription_id="sub_1", telefono="111", customer_id="cus_con")
        await _crear_suscripcion(db, subscription_id="sub_2", telefono="222", customer_id="cus_sin")

        # cus_sin no tiene email en Stripe → None
        fake = _FakeStripe({"cus_con": "con@dona.app", "cus_sin": None})
        monkeypatch.setattr("agent.billing._stripe_client", lambda: fake)

        resumen = await db.sembrar_usuarios_desde_stripe()
        assert resumen["sembrados"] == 1
        assert resumen["sin_email"] == 1

        async with db.async_session() as session:
            usuarios = (await session.execute(select(db.Usuario))).scalars().all()
            assert len(usuarios) == 1
            assert usuarios[0].email == "con@dona.app"

    @pytest.mark.asyncio
    async def test_customers_repetidos_se_resuelven_una_vez(self, db, monkeypatch):
        """Dos suscripciones del mismo customer → un solo retrieve, un solo usuario."""
        from sqlalchemy import func, select

        await _crear_suscripcion(db, subscription_id="sub_a", telefono="111", customer_id="cus_dup")
        await _crear_suscripcion(db, subscription_id="sub_b", telefono="111", customer_id="cus_dup")

        fake = _FakeStripe({"cus_dup": "dup@dona.app"})
        monkeypatch.setattr("agent.billing._stripe_client", lambda: fake)

        resumen = await db.sembrar_usuarios_desde_stripe()
        assert resumen["customers"] == 1
        assert fake.llamadas == ["cus_dup"]  # un solo retrieve

        async with db.async_session() as session:
            total = (await session.execute(
                select(func.count()).select_from(db.Usuario)
            )).scalar_one()
            assert total == 1

    @pytest.mark.asyncio
    async def test_sin_stripe_configurado_no_falla(self, db, monkeypatch):
        """Si Stripe no está configurado, la siembra retorna sin_stripe (no rompe)."""
        monkeypatch.setattr("agent.billing._stripe_client", lambda: None)
        resumen = await db.sembrar_usuarios_desde_stripe()
        assert resumen["status"] == "sin_stripe"
        assert resumen["sembrados"] == 0
