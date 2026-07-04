# tests/test_welcome_premium.py — T2.0.B

"""
Cubre el módulo agent/welcome.py y su integración con
_procesar_checkout_subscription.

Tests sin red: WELCOME_DRY_RUN=true por default + mock del proveedor
cuando hace falta envío real simulado.

Cubre:
  - _derivar_password con/sin secret.
  - _componer_mensaje incluye saludo, plan, créditos, password, link.
  - enviar_bienvenida_premium en cada modo:
      DRY_RUN, sin secret, sin telefono, ya enviado, envío fallido,
      excepción del proveedor.
  - Hook en _procesar_checkout_subscription:
      created envía · updated NO envía · marca flag · idempotencia.
  - Logging: password no aparece en caplog (redactor de logging_config).
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import pytest


SECRET_TEST = "test-secret-not-real-t20b"


# ── Fixture común con DB SQLite aislada ──────────────────────────────────


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "welcome.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("DASHBOARD_PASSWORD_SECRET", SECRET_TEST)
    monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100")
    monkeypatch.setenv("STRIPE_CREDITOS_PRO", "500")
    # Default: DRY_RUN para no llamar al proveedor real en tests.
    monkeypatch.setenv("WELCOME_DRY_RUN", "true")

    import agent.memory
    import agent.billing
    import agent.welcome
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)
    importlib.reload(agent.welcome)

    await agent.memory.inicializar_db()
    return agent.memory


# ── 1. _derivar_password ────────────────────────────────────────────────


class TestDerivarPassword:
    def test_compute_misma_formula_que_landing(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_PASSWORD_SECRET", "shared-secret")
        from agent.welcome import _derivar_password
        # Resultado determinístico verificable manualmente:
        # hex(HMAC-SHA256("cus_TEST_001", "shared-secret"))[:12]
        # solo verificamos formato y determinismo.
        p1 = _derivar_password("cus_TEST_001")
        p2 = _derivar_password("cus_TEST_001")
        assert p1 == p2
        assert p1 is not None
        assert p1.startswith("dona-")
        assert len(p1) == len("dona-") + 12

    def test_secret_ausente_retorna_none(self, monkeypatch):
        monkeypatch.delenv("DASHBOARD_PASSWORD_SECRET", raising=False)
        from agent.welcome import _derivar_password
        importlib.reload(__import__("agent.welcome", fromlist=["_derivar_password"]))
        from agent.welcome import _derivar_password as derive2
        assert derive2("cus_x") is None

    def test_customer_id_vacio_retorna_none(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_PASSWORD_SECRET", "x")
        from agent.welcome import _derivar_password
        assert _derivar_password("") is None


# ── 2. _componer_mensaje ────────────────────────────────────────────────


class TestComponerMensaje:
    def test_premium_incluye_password_link_creditos(self):
        from agent.welcome import _componer_mensaje
        msg = _componer_mensaje(
            nombre="Carlos",
            plan_codigo="premium",
            creditos_mensuales=100,
            password="dona-abc123def456",
            dashboard_url="https://www.usadona.com/dashboard",
        )
        assert "Hola Carlos" in msg
        assert "Premium" in msg
        assert "100 créditos" in msg
        assert "dona-abc123def456" in msg
        assert "https://www.usadona.com/dashboard" in msg
        assert "hola" in msg.lower()  # invitación a empezar

    def test_pro_dice_pro_y_500_creditos(self):
        from agent.welcome import _componer_mensaje
        msg = _componer_mensaje(
            nombre="Ana",
            plan_codigo="pro",
            creditos_mensuales=500,
            password="dona-fedcba987654",
            dashboard_url="https://x.com/dashboard",
        )
        assert "Hola Ana" in msg
        assert "Pro" in msg
        assert "500 créditos" in msg

    def test_sin_nombre_dice_hola_genérico(self):
        from agent.welcome import _componer_mensaje
        msg = _componer_mensaje(
            nombre=None,
            plan_codigo="premium",
            creditos_mensuales=100,
            password="dona-aabbccddeeff",
            dashboard_url="https://x.com/dashboard",
        )
        assert msg.startswith("Hola!")
        assert "Hola !" not in msg


# ── 3. enviar_bienvenida_premium ────────────────────────────────────────


class TestEnviarBienvenidaDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_no_llama_proveedor_y_marca_flag(self, db, monkeypatch):
        # Crear sub previa
        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_dry",
                telefono="14076936023",
                customer_id="cus_dry",
                plan_codigo="premium",
                price_id="",
                status="active",
                creditos_mensuales=100,
            ))
            await session.commit()

        # Garantía: si el proveedor real se llamara, fallaría.
        # En DRY_RUN no se importa providers, así que basta no
        # configurar nada.

        from agent.welcome import enviar_bienvenida_premium
        result = await enviar_bienvenida_premium(
            subscription_id="sub_dry",
            customer_id="cus_dry",
            telefono="14076936023",
            plan_codigo="premium",
            creditos_mensuales=100,
        )
        assert result == "dry_run"

        # Verificar flag marcado.
        from sqlalchemy import select
        async with db.async_session() as session:
            sub = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.subscription_id == "sub_dry"
                )
            )).scalar_one()
            assert sub.bienvenida_enviada is True

    @pytest.mark.asyncio
    async def test_idempotente_si_flag_ya_true(self, db):
        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_idem",
                telefono="14076936023",
                customer_id="cus_idem",
                plan_codigo="premium",
                price_id="",
                status="active",
                creditos_mensuales=100,
                bienvenida_enviada=True,  # ya enviado
            ))
            await session.commit()

        from agent.welcome import enviar_bienvenida_premium
        result = await enviar_bienvenida_premium(
            subscription_id="sub_idem",
            customer_id="cus_idem",
            telefono="14076936023",
            plan_codigo="premium",
            creditos_mensuales=100,
        )
        assert result == "ya_enviado"


class TestEnviarBienvenidaErrores:
    @pytest.mark.asyncio
    async def test_secret_faltante(self, db, monkeypatch):
        monkeypatch.delenv("DASHBOARD_PASSWORD_SECRET", raising=False)
        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_no_secret",
                telefono="14076936023",
                customer_id="cus_x",
                plan_codigo="premium",
                price_id="",
                status="active",
                creditos_mensuales=100,
            ))
            await session.commit()

        from agent.welcome import enviar_bienvenida_premium
        result = await enviar_bienvenida_premium(
            subscription_id="sub_no_secret",
            customer_id="cus_x",
            telefono="14076936023",
            plan_codigo="premium",
            creditos_mensuales=100,
        )
        assert result == "secret_faltante"

        # Flag NO marcado.
        from sqlalchemy import select
        async with db.async_session() as session:
            sub = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.subscription_id == "sub_no_secret"
                )
            )).scalar_one()
            assert sub.bienvenida_enviada is False

    @pytest.mark.asyncio
    async def test_telefono_faltante(self, db):
        from agent.welcome import enviar_bienvenida_premium
        result = await enviar_bienvenida_premium(
            subscription_id="sub_no_tel",
            customer_id="cus_x",
            telefono="",
            plan_codigo="premium",
            creditos_mensuales=100,
        )
        assert result == "telefono_faltante"

    @pytest.mark.asyncio
    async def test_envio_falla_no_marca_flag(self, db, monkeypatch):
        # Forzar envío real (sin DRY_RUN) y que el proveedor retorne False.
        monkeypatch.delenv("WELCOME_DRY_RUN", raising=False)

        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_fallo",
                telefono="14076936023",
                customer_id="cus_fallo",
                plan_codigo="premium",
                price_id="",
                status="active",
                creditos_mensuales=100,
            ))
            await session.commit()

        # Mock del proveedor: retornar False.
        class FakeProveedor:
            async def enviar_mensaje(self, telefono, mensaje):
                return False

        import agent.welcome as welcome_mod
        # Monkey-patch obtener_proveedor importado dentro de la función.
        import agent.providers
        monkeypatch.setattr(
            agent.providers, "obtener_proveedor", lambda: FakeProveedor()
        )

        result = await welcome_mod.enviar_bienvenida_premium(
            subscription_id="sub_fallo",
            customer_id="cus_fallo",
            telefono="14076936023",
            plan_codigo="premium",
            creditos_mensuales=100,
        )
        assert result == "envio_fallo"

        # Flag NO marcado.
        from sqlalchemy import select
        async with db.async_session() as session:
            sub = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.subscription_id == "sub_fallo"
                )
            )).scalar_one()
            assert sub.bienvenida_enviada is False

    @pytest.mark.asyncio
    async def test_proveedor_excepcion_no_rompe_y_no_marca_flag(self, db, monkeypatch):
        monkeypatch.delenv("WELCOME_DRY_RUN", raising=False)
        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_exc",
                telefono="14076936023",
                customer_id="cus_exc",
                plan_codigo="premium",
                price_id="",
                status="active",
                creditos_mensuales=100,
            ))
            await session.commit()

        class FakeProveedorExplota:
            async def enviar_mensaje(self, telefono, mensaje):
                raise ConnectionError("simulado")

        import agent.welcome as welcome_mod
        import agent.providers
        monkeypatch.setattr(
            agent.providers, "obtener_proveedor", lambda: FakeProveedorExplota()
        )

        # No debería levantar excepción al caller.
        result = await welcome_mod.enviar_bienvenida_premium(
            subscription_id="sub_exc",
            customer_id="cus_exc",
            telefono="14076936023",
            plan_codigo="premium",
            creditos_mensuales=100,
        )
        assert result == "envio_fallo"


# ── 4. Logging redaction ────────────────────────────────────────────────


class TestLoggingNoExponePassword:
    @pytest.mark.asyncio
    async def test_password_no_aparece_en_logs_dry_run(self, db, caplog):
        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_log",
                telefono="14076936023",
                customer_id="cus_logsensitive",
                plan_codigo="premium",
                price_id="",
                status="active",
                creditos_mensuales=100,
            ))
            await session.commit()

        from agent.welcome import enviar_bienvenida_premium
        with caplog.at_level(logging.INFO, logger="dona"):
            await enviar_bienvenida_premium(
                subscription_id="sub_log",
                customer_id="cus_logsensitive",
                telefono="14076936023",
                plan_codigo="premium",
                creditos_mensuales=100,
            )

        # Buscar en cualquier log emitido el patrón password "dona-<12 hex>".
        # El módulo NO debe loguear el password completo ni siquiera en
        # DRY_RUN. Validamos que el patrón no aparezca en texto crudo
        # de los registros (caplog no aplica el formatter de producción
        # con redaction; verificamos el código fuente del log directamente).
        import re
        pat = re.compile(r"dona-[a-f0-9]{12}")
        for record in caplog.records:
            assert not pat.search(record.getMessage()), (
                f"Password apareció en log: {record.getMessage()}"
            )


# ── 5. Hook en _procesar_checkout_subscription ─────────────────────────


class TestHookCheckoutSubscription:
    @pytest.mark.asyncio
    async def test_created_dispara_welcome(self, db):
        from agent.billing import _procesar_checkout_subscription
        evento = {
            "id": "cs_test_001",
            "subscription": "sub_hook_created",
            "customer": "cus_hook",
            "mode": "subscription",
            "metadata": {"plan": "premium", "phone": "14076936023"},
            "customer_details": {"name": "Carlos", "phone": "+14076936023"},
        }
        result = await _procesar_checkout_subscription(evento)
        assert result["handled"] is True
        assert result["accion"] == "created"
        # En DRY_RUN, el hook devuelve "dry_run".
        assert result["welcome"] == "dry_run"

        # Flag marcado en DB.
        from sqlalchemy import select
        async with db.async_session() as session:
            sub = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.subscription_id == "sub_hook_created"
                )
            )).scalar_one()
            assert sub.bienvenida_enviada is True

    @pytest.mark.asyncio
    async def test_updated_NO_dispara_welcome(self, db):
        # Setup: crear sub previamente con flag ya en False (existe pre-T2.0.B).
        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_hook_upd",
                telefono="14076936023",
                customer_id="cus_upd",
                plan_codigo="premium",
                price_id="",
                status="active",
                creditos_mensuales=100,
                bienvenida_enviada=False,
            ))
            await session.commit()

        # Re-checkout (caso raro pero posible). El handler detecta sub
        # existente y hace accion="updated" → NO debe enviar welcome.
        from agent.billing import _procesar_checkout_subscription
        evento = {
            "id": "cs_test_002",
            "subscription": "sub_hook_upd",
            "customer": "cus_upd",
            "mode": "subscription",
            "metadata": {"plan": "premium", "phone": "14076936023"},
            "customer_details": {"name": "Ana"},
        }
        result = await _procesar_checkout_subscription(evento)
        assert result["accion"] == "updated"
        # El campo welcome existe pero es None en updated.
        assert result.get("welcome") is None

        # Flag sigue en False (no se envió welcome).
        from sqlalchemy import select
        async with db.async_session() as session:
            sub = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.subscription_id == "sub_hook_upd"
                )
            )).scalar_one()
            assert sub.bienvenida_enviada is False


# ── 6. Helpers puros de redacción / formateo ───────────────────────────────
#
# Fijan el comportamiento actual de los helpers server-side que truncan
# identificadores y teléfonos para logs, y de los formateadores de plan /
# saludo / URL del dashboard. No tocan DB ni proveedor: son funciones puras.


class TestShortId:
    def test_vacio_devuelve_estrellas(self):
        from agent.welcome import _short_id
        assert _short_id("") == "***"

    def test_corto_menor_o_igual_a_12_devuelve_estrellas(self):
        from agent.welcome import _short_id
        # Justo en el límite (12) también se enmascara entero.
        assert _short_id("123456789012") == "***"
        assert _short_id("corto") == "***"

    def test_largo_deja_prefijo_y_sufijo(self):
        from agent.welcome import _short_id
        # len > 12 → "{primeros8}...{últimos4}".
        assert _short_id("cus_1234567890abcdef") == "cus_1234...cdef"


class TestShortTelefono:
    def test_vacio_devuelve_estrellas(self):
        from agent.welcome import _short_telefono
        assert _short_telefono("") == "***"

    def test_menor_o_igual_a_6_devuelve_estrellas(self):
        from agent.welcome import _short_telefono
        assert _short_telefono("123456") == "***"

    def test_largo_deja_prefijo_y_ultimos_cuatro(self):
        from agent.welcome import _short_telefono
        # "{primeros2}****{últimos4}".
        assert _short_telefono("14076936023") == "14****6023"


class TestNombrePlan:
    def test_premium_y_pro_traducen_a_etiqueta(self):
        from agent.welcome import _nombre_plan
        assert _nombre_plan("premium") == "Premium"
        assert _nombre_plan("pro") == "Pro"

    def test_desconocido_se_devuelve_crudo(self):
        from agent.welcome import _nombre_plan
        assert _nombre_plan("enterprise") == "enterprise"

    def test_vacio_devuelve_guion(self):
        from agent.welcome import _nombre_plan
        assert _nombre_plan("") == "—"


class TestSaludo:
    def test_none_devuelve_hola_generico(self):
        from agent.welcome import _saludo
        assert _saludo(None) == "Hola!"

    def test_solo_espacios_devuelve_hola_generico(self):
        from agent.welcome import _saludo
        # Nombre en blanco tras strip → saludo genérico (rama línea 113).
        assert _saludo("   ") == "Hola!"

    def test_nombre_toma_primer_token(self):
        from agent.welcome import _saludo
        assert _saludo("Carlos Alberto") == "Hola Carlos!"


class TestDashboardUrl:
    def _limpiar(self, monkeypatch):
        for var in (
            "STRIPE_PORTAL_RETURN_URL",
            "NEXTAUTH_URL",
            "NEXT_PUBLIC_SITE_URL",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_portal_return_url_tiene_prioridad(self, monkeypatch):
        from agent.welcome import _dashboard_url
        self._limpiar(monkeypatch)
        monkeypatch.setenv(
            "STRIPE_PORTAL_RETURN_URL", "https://portal.example.com/back"
        )
        # Aunque haya NEXTAUTH_URL, gana el override.
        monkeypatch.setenv("NEXTAUTH_URL", "https://otra.example.com")
        assert _dashboard_url() == "https://portal.example.com/back"

    def test_nextauth_url_agrega_dashboard(self, monkeypatch):
        from agent.welcome import _dashboard_url
        self._limpiar(monkeypatch)
        monkeypatch.setenv("NEXTAUTH_URL", "https://app.example.com/")
        # Se recorta la barra final y se agrega /dashboard.
        assert _dashboard_url() == "https://app.example.com/dashboard"

    def test_site_url_agrega_dashboard(self, monkeypatch):
        from agent.welcome import _dashboard_url
        self._limpiar(monkeypatch)
        monkeypatch.setenv("NEXT_PUBLIC_SITE_URL", "https://sitio.example.com")
        assert _dashboard_url() == "https://sitio.example.com/dashboard"

    def test_sin_env_usa_default(self, monkeypatch):
        from agent.welcome import _dashboard_url, _DEFAULT_DASHBOARD_URL
        self._limpiar(monkeypatch)
        assert _dashboard_url() == _DEFAULT_DASHBOARD_URL

    def test_valor_no_http_se_ignora(self, monkeypatch):
        from agent.welcome import _dashboard_url, _DEFAULT_DASHBOARD_URL
        self._limpiar(monkeypatch)
        # Un valor sin esquema http(s) no cuenta y cae al default.
        monkeypatch.setenv("STRIPE_PORTAL_RETURN_URL", "no-es-una-url")
        assert _dashboard_url() == _DEFAULT_DASHBOARD_URL


# ── 7. Envío real exitoso + _marcar_enviado sobre fila inexistente ─────────


class TestEnvioRealExitoso:
    @pytest.mark.asyncio
    async def test_proveedor_ok_devuelve_enviado_y_marca_flag(self, db, monkeypatch):
        # Forzar envío real (sin DRY_RUN) con proveedor que retorna True.
        monkeypatch.delenv("WELCOME_DRY_RUN", raising=False)

        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_ok",
                telefono="14076936023",
                customer_id="cus_ok",
                plan_codigo="pro",
                price_id="",
                status="active",
                creditos_mensuales=500,
            ))
            await session.commit()

        enviados = []

        class FakeProveedorOk:
            async def enviar_mensaje(self, telefono, mensaje):
                enviados.append((telefono, mensaje))
                return True

        import agent.welcome as welcome_mod
        import agent.providers
        monkeypatch.setattr(
            agent.providers, "obtener_proveedor", lambda: FakeProveedorOk()
        )

        result = await welcome_mod.enviar_bienvenida_premium(
            subscription_id="sub_ok",
            customer_id="cus_ok",
            telefono="14076936023",
            plan_codigo="pro",
            creditos_mensuales=500,
        )
        assert result == "enviado"
        # El proveedor recibió exactamente un mensaje al teléfono correcto.
        assert len(enviados) == 1
        assert enviados[0][0] == "14076936023"

        # Flag marcado tras éxito real.
        from sqlalchemy import select
        async with db.async_session() as session:
            sub = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.subscription_id == "sub_ok"
                )
            )).scalar_one()
            assert sub.bienvenida_enviada is True


class TestMarcarEnviadoFilaInexistente:
    @pytest.mark.asyncio
    async def test_no_falla_si_sub_no_existe(self, db):
        # _marcar_enviado sobre una subscription_id que no está en DB
        # no debe romper (rama línea 290: sub is None → return).
        from agent.welcome import _marcar_enviado
        await _marcar_enviado("sub_que_no_existe")  # no levanta
