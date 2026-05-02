# tests/test_suscripcion_stripe_models.py — Tests T1.3.A modelos suscripción Stripe

"""
Cubre el alcance mínimo de T1.3.A:
  - Las dos tablas nuevas (`suscripcion_stripe`, `evento_stripe_procesado`) se
    crean correctamente vía `metadata.create_all()` (lo que ejecuta
    `inicializar_db()` en cada arranque del backend).
  - Insert + select básico funciona.
  - PK `subscription_id` y `event_id` previenen duplicados (IntegrityError).
  - Defaults (`creado`, `actualizado`, `recibido_en`, `ultimo_invoice_acreditado`)
    se aplican.

NO cubre:
  - Lógica de acreditación (T1.3.C).
  - Endpoint `/internal/stripe-event` (T1.3.D).
  - Bridge landing → backend (T1.3.E).

Sigue el mismo patrón de fixture que `tests/test_billing.py`: SQLite en
tmp_path con `importlib.reload(agent.memory)` para aislar engine.
"""

import importlib
import pytest
from datetime import datetime, timedelta

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """DB SQLite aislada por test, con tablas nuevas creadas vía metadata.create_all."""
    db_path = tmp_path / "suscripcion.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    await agent.memory.inicializar_db()
    return agent.memory


# ── SuscripcionStripe ────────────────────────────────────────────────────────


class TestSuscripcionStripe:
    @pytest.mark.asyncio
    async def test_insert_y_select_basico(self, db):
        async with db.async_session() as session:
            sub = db.SuscripcionStripe(
                subscription_id="sub_test_001",
                telefono="14076936023",
                customer_id="cus_test_001",
                plan_codigo="premium",
                price_id="price_test_premium",
                status="active",
                creditos_mensuales=100,
            )
            session.add(sub)
            await session.commit()

        from sqlalchemy import select
        async with db.async_session() as session:
            row = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.subscription_id == "sub_test_001"
                )
            )).scalar_one()
            assert row.telefono == "14076936023"
            assert row.customer_id == "cus_test_001"
            assert row.plan_codigo == "premium"
            assert row.creditos_mensuales == 100
            assert row.status == "active"

    @pytest.mark.asyncio
    async def test_defaults_se_aplican(self, db):
        """`ultimo_invoice_acreditado` default vacio; `creado`/`actualizado` autopobla."""
        async with db.async_session() as session:
            sub = db.SuscripcionStripe(
                subscription_id="sub_test_002",
                telefono="5215551",
                customer_id="cus_test_002",
                plan_codigo="pro",
                price_id="price_test_pro",
                status="active",
                creditos_mensuales=500,
            )
            session.add(sub)
            await session.commit()

        from sqlalchemy import select
        async with db.async_session() as session:
            row = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.subscription_id == "sub_test_002"
                )
            )).scalar_one()
            assert row.ultimo_invoice_acreditado == ""
            assert row.creado is not None
            assert row.actualizado is not None
            # Ambos timestamps son recientes (< 5 segundos del now()).
            ahora = datetime.utcnow()
            assert ahora - row.creado < timedelta(seconds=5)

    @pytest.mark.asyncio
    async def test_pk_subscription_id_previene_duplicados(self, db):
        """Insertar dos veces el mismo subscription_id debe fallar."""
        from sqlalchemy.exc import IntegrityError

        async with db.async_session() as session:
            session.add(db.SuscripcionStripe(
                subscription_id="sub_dup",
                telefono="555", customer_id="cus_dup",
                plan_codigo="premium", price_id="price_x",
                status="active", creditos_mensuales=100,
            ))
            await session.commit()

        with pytest.raises(IntegrityError):
            async with db.async_session() as session:
                session.add(db.SuscripcionStripe(
                    subscription_id="sub_dup",
                    telefono="556", customer_id="cus_other",
                    plan_codigo="pro", price_id="price_y",
                    status="active", creditos_mensuales=500,
                ))
                await session.commit()

    @pytest.mark.asyncio
    async def test_indexes_telefono_y_customer_funcionan(self, db):
        """Insertar varias suscripciones y filtrar por telefono / customer_id."""
        from sqlalchemy import select

        async with db.async_session() as session:
            for i, (tel, cus) in enumerate([
                ("5551", "cus_A"),
                ("5551", "cus_B"),  # mismo telefono, otro customer
                ("5552", "cus_C"),
            ]):
                session.add(db.SuscripcionStripe(
                    subscription_id=f"sub_idx_{i}",
                    telefono=tel, customer_id=cus,
                    plan_codigo="premium", price_id="price_x",
                    status="active", creditos_mensuales=100,
                ))
            await session.commit()

        async with db.async_session() as session:
            por_tel = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.telefono == "5551"
                )
            )).scalars().all()
            assert len(por_tel) == 2

            por_cus = (await session.execute(
                select(db.SuscripcionStripe).where(
                    db.SuscripcionStripe.customer_id == "cus_C"
                )
            )).scalars().all()
            assert len(por_cus) == 1
            assert por_cus[0].telefono == "5552"


# ── EventoStripeProcesado ───────────────────────────────────────────────────


class TestEventoStripeProcesado:
    @pytest.mark.asyncio
    async def test_insert_y_select_basico(self, db):
        async with db.async_session() as session:
            ev = db.EventoStripeProcesado(
                event_id="evt_test_001",
                tipo="invoice.payment_succeeded",
            )
            session.add(ev)
            await session.commit()

        from sqlalchemy import select
        async with db.async_session() as session:
            row = (await session.execute(
                select(db.EventoStripeProcesado).where(
                    db.EventoStripeProcesado.event_id == "evt_test_001"
                )
            )).scalar_one()
            assert row.tipo == "invoice.payment_succeeded"
            assert row.recibido_en is not None

    @pytest.mark.asyncio
    async def test_pk_event_id_previene_duplicados(self, db):
        """Insertar dos veces el mismo event_id debe fallar — base de la idempotencia."""
        from sqlalchemy.exc import IntegrityError

        async with db.async_session() as session:
            session.add(db.EventoStripeProcesado(
                event_id="evt_dup",
                tipo="checkout.session.completed",
            ))
            await session.commit()

        with pytest.raises(IntegrityError):
            async with db.async_session() as session:
                session.add(db.EventoStripeProcesado(
                    event_id="evt_dup",
                    tipo="checkout.session.completed",  # mismo tipo, mismo id
                ))
                await session.commit()

    @pytest.mark.asyncio
    async def test_index_tipo_funciona(self, db):
        """Filtrar por tipo retorna solo eventos del tipo pedido."""
        from sqlalchemy import select

        async with db.async_session() as session:
            for i, tipo in enumerate([
                "checkout.session.completed",
                "invoice.payment_succeeded",
                "invoice.payment_succeeded",
                "customer.subscription.deleted",
            ]):
                session.add(db.EventoStripeProcesado(
                    event_id=f"evt_idx_{i}",
                    tipo=tipo,
                ))
            await session.commit()

        async with db.async_session() as session:
            invoices = (await session.execute(
                select(db.EventoStripeProcesado).where(
                    db.EventoStripeProcesado.tipo == "invoice.payment_succeeded"
                )
            )).scalars().all()
            assert len(invoices) == 2
