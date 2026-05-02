# tests/test_procesar_evento_suscripcion.py — Tests T1.3.C dispatcher de eventos Stripe

"""
Cubre el alcance mínimo de T1.3.C — `procesar_evento_suscripcion`:
  - checkout.session.completed (mode=subscription) crea SuscripcionStripe.
  - checkout.session.completed (mode=subscription) actualiza si ya existe.
  - checkout.session.completed (mode=payment) NO se procesa aquí (lo maneja
    `procesar_evento_stripe` legacy).
  - invoice.payment_succeeded acredita `creditos_mensuales` del plan.
  - invoice.payment_succeeded duplicado NO acredita dos veces (idempotencia
    por `ultimo_invoice_acreditado`).
  - event.id duplicado NO procesa dos veces (idempotencia general por
    EventoStripeProcesado).
  - customer.subscription.updated cambia status/plan/price.
  - customer.subscription.updated con plan distinto recalcula creditos_mensuales.
  - customer.subscription.deleted marca canceled y PRESERVA saldo del usuario.
  - Eventos sin telefono / sin subscription_id / con plan desconocido NO
    acreditan ni revientan.
  - Tipo de evento no soportado retorna handled=False sin error.

NO cubre:
  - Endpoint /internal/stripe-event (T1.3.D).
  - Bridge landing → backend (T1.3.E).
"""

import importlib
import pytest

import agent.memory
import agent.billing


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """DB SQLite aislada por test, con env vars de planes seteadas."""
    db_path = tmp_path / "subs.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100")
    monkeypatch.setenv("STRIPE_CREDITOS_PRO", "500")
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)
    await agent.memory.inicializar_db()
    return agent.billing


# ── Helpers ────────────────────────────────────────────────────────────────


def _evento_checkout(
    *,
    event_id="evt_checkout_001",
    subscription_id="sub_001",
    customer_id="cus_001",
    plan="premium",
    phone="14076936023",
    mode="subscription",
):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_001",
                "mode": mode,
                "subscription": subscription_id,
                "customer": customer_id,
                "metadata": {"plan": plan, "phone": phone},
                "customer_details": {"phone": "+" + phone if phone else ""},
            }
        },
    }


def _evento_invoice(
    *,
    event_id="evt_invoice_001",
    invoice_id="in_001",
    subscription_id="sub_001",
):
    return {
        "id": event_id,
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "id": invoice_id,
                "subscription": subscription_id,
            }
        },
    }


def _evento_updated(
    *,
    event_id="evt_updated_001",
    subscription_id="sub_001",
    status="active",
    price_id="price_pro_v2",
    plan=None,
):
    obj = {
        "id": subscription_id,
        "status": status,
        "items": {"data": [{"price": {"id": price_id}}]},
    }
    if plan is not None:
        obj["metadata"] = {"plan": plan}
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "data": {"object": obj},
    }


def _evento_deleted(*, event_id="evt_deleted_001", subscription_id="sub_001"):
    return {
        "id": event_id,
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": subscription_id, "status": "canceled"}},
    }


async def _crear_suscripcion(db, subscription_id, telefono, plan="premium", creditos=100):
    """Helper: simula que ya hubo checkout. Inserta SuscripcionStripe directo."""
    async with db.async_session() if False else agent.memory.async_session() as session:
        session.add(agent.memory.SuscripcionStripe(
            subscription_id=subscription_id,
            telefono=telefono,
            customer_id="cus_x",
            plan_codigo=plan,
            price_id="price_x",
            status="active",
            creditos_mensuales=creditos,
        ))
        await session.commit()


# ── checkout.session.completed ─────────────────────────────────────────────


class TestCheckoutSessionCompleted:
    @pytest.mark.asyncio
    async def test_crea_suscripcion_nueva(self, db):
        ev = _evento_checkout(plan="premium", phone="14076936023")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True
        assert res["accion"] == "created"
        assert res["plan_codigo"] == "premium"
        assert res["creditos_mensuales"] == 100

        # Verificar fila en DB
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            assert sub.telefono == "14076936023"
            assert sub.plan_codigo == "premium"
            assert sub.creditos_mensuales == 100
            assert sub.status == "active"

    @pytest.mark.asyncio
    async def test_pro_plan_credita_500(self, db):
        ev = _evento_checkout(plan="pro", subscription_id="sub_pro")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True
        assert res["creditos_mensuales"] == 500

    @pytest.mark.asyncio
    async def test_no_acredita_creditos_aun(self, db):
        """checkout.session.completed crea la suscripción pero NO acredita.
        Eso lo hace invoice.payment_succeeded."""
        ev = _evento_checkout()
        await db.procesar_evento_suscripcion(ev)
        saldo = await db.obtener_saldo("14076936023")
        assert saldo == 0

    @pytest.mark.asyncio
    async def test_re_checkout_actualiza_no_duplica(self, db):
        """Si llega un segundo checkout para la misma subscription_id (caso raro
        pero posible), actualizamos en lugar de crear duplicado."""
        ev1 = _evento_checkout(event_id="evt_1", plan="premium")
        await db.procesar_evento_suscripcion(ev1)

        ev2 = _evento_checkout(event_id="evt_2", plan="pro", phone="15551112222")
        res = await db.procesar_evento_suscripcion(ev2)
        assert res["accion"] == "updated"
        assert res["plan_codigo"] == "pro"

        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            subs = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalars().all()
            assert len(subs) == 1
            assert subs[0].plan_codigo == "pro"
            assert subs[0].telefono == "15551112222"
            assert subs[0].creditos_mensuales == 500

    @pytest.mark.asyncio
    async def test_mode_payment_no_se_procesa(self, db):
        """Los checkouts mode=payment los maneja procesar_evento_stripe
        (legacy paquetes one-time)."""
        ev = _evento_checkout(mode="payment")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert "subscription" in res["reason"]

    @pytest.mark.asyncio
    async def test_sin_telefono_no_crea(self, db):
        ev = _evento_checkout(phone="")
        # Forzar tambien customer_details.phone vacio
        ev["data"]["object"]["customer_details"]["phone"] = ""
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "missing_telefono"

        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            subs = (await session.execute(
                select(agent.memory.SuscripcionStripe)
            )).scalars().all()
            assert len(subs) == 0

    @pytest.mark.asyncio
    async def test_telefono_de_customer_details_si_metadata_falta(self, db):
        """Si metadata.phone vacío pero customer_details.phone presente, lo usamos."""
        ev = _evento_checkout(phone="")
        ev["data"]["object"]["customer_details"]["phone"] = "+14077777777"
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True
        assert res["telefono"] == "14077777777"  # sin "+"

    @pytest.mark.asyncio
    async def test_sin_subscription_id_no_crea(self, db):
        ev = _evento_checkout(subscription_id="")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "missing_subscription_id"

    @pytest.mark.asyncio
    async def test_plan_desconocido_no_crea(self, db):
        ev = _evento_checkout(plan="enterprise")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert "plan_invalido" in res["reason"]

        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            subs = (await session.execute(
                select(agent.memory.SuscripcionStripe)
            )).scalars().all()
            assert len(subs) == 0


# ── invoice.payment_succeeded ───────────────────────────────────────────────


class TestInvoicePaymentSucceeded:
    @pytest.mark.asyncio
    async def test_acredita_creditos_del_plan(self, db):
        # Setup: crear suscripción primero
        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)

        ev = _evento_invoice(invoice_id="in_001", subscription_id="sub_001")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True
        assert res["creditos"] == 100
        assert res["telefono"] == "14076936023"
        assert res["saldo"] == 100

        saldo = await db.obtener_saldo("14076936023")
        assert saldo == 100

    @pytest.mark.asyncio
    async def test_invoice_duplicado_no_acredita_dos_veces(self, db):
        """Mismo invoice.id, distinto event.id (Stripe regenera el evento) →
        ultimo_invoice_acreditado bloquea."""
        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)

        ev1 = _evento_invoice(event_id="evt_1", invoice_id="in_001")
        await db.procesar_evento_suscripcion(ev1)

        ev2 = _evento_invoice(event_id="evt_2", invoice_id="in_001")
        res = await db.procesar_evento_suscripcion(ev2)
        assert res["handled"] is False
        assert res["reason"] == "invoice_ya_acreditado"

        saldo = await db.obtener_saldo("14076936023")
        assert saldo == 100  # NO 200

    @pytest.mark.asyncio
    async def test_event_id_duplicado_no_procesa(self, db):
        """Mismo event.id reentregado por Stripe → EventoStripeProcesado bloquea."""
        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)

        ev = _evento_invoice(event_id="evt_dup", invoice_id="in_001")
        await db.procesar_evento_suscripcion(ev)
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "duplicate_event"

        saldo = await db.obtener_saldo("14076936023")
        assert saldo == 100

    @pytest.mark.asyncio
    async def test_renovaciones_son_acumulables(self, db):
        """Decisión owner: cada periodo SUMA, no resetea. Si el usuario tiene
        80 al final del mes, el día 30 le quedan 80+100=180."""
        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)

        ev1 = _evento_invoice(event_id="evt_m1", invoice_id="in_m1")
        await db.procesar_evento_suscripcion(ev1)

        # Simular gasto parcial
        await db.cobrar("14076936023", 20, "test_gasto")
        assert await db.obtener_saldo("14076936023") == 80

        # Renovación segundo mes
        ev2 = _evento_invoice(event_id="evt_m2", invoice_id="in_m2")
        await db.procesar_evento_suscripcion(ev2)
        assert await db.obtener_saldo("14076936023") == 180

    @pytest.mark.asyncio
    async def test_invoice_sin_subscription_persistida_no_acredita(self, db):
        """Race: invoice llega antes que checkout.session.completed.
        Rechazamos para que Stripe reintente."""
        ev = _evento_invoice(subscription_id="sub_inexistente")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "subscription_no_persistida"

    @pytest.mark.asyncio
    async def test_invoice_sin_subscription_id_rechaza(self, db):
        ev = _evento_invoice(subscription_id="")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "missing_subscription_id"

    @pytest.mark.asyncio
    async def test_invoice_sin_id_rechaza(self, db):
        ev = _evento_invoice(invoice_id="")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "missing_invoice_id"

    @pytest.mark.asyncio
    async def test_invoice_reactiva_si_estaba_past_due(self, db):
        """Si la suscripción venía de past_due y ahora se pagó, status → active."""
        from sqlalchemy import select

        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)
        # Forzar past_due manualmente
        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            sub.status = "past_due"
            await session.commit()

        ev = _evento_invoice(invoice_id="in_recovery")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True

        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            assert sub.status == "active"

    @pytest.mark.asyncio
    async def test_invoice_no_resucita_si_estaba_canceled(self, db):
        """Si la suscripción está canceled y por alguna razón llega un invoice
        tardío, NO la reactivamos a active."""
        from sqlalchemy import select

        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)
        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            sub.status = "canceled"
            await session.commit()

        ev = _evento_invoice(invoice_id="in_late")
        res = await db.procesar_evento_suscripcion(ev)
        # El invoice se acredita igual (lo que ya pagaron es suyo) PERO el
        # status NO regresa a active.
        assert res["handled"] is True

        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            assert sub.status == "canceled"


# ── customer.subscription.updated ───────────────────────────────────────────


class TestSubscriptionUpdated:
    @pytest.mark.asyncio
    async def test_cambia_status(self, db):
        from sqlalchemy import select

        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)
        ev = _evento_updated(status="past_due", price_id="price_old")
        # No cambiamos price_id real para no contaminar la assertion del status
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True
        assert any("status:" in c for c in res["cambios"])

        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            assert sub.status == "past_due"

    @pytest.mark.asyncio
    async def test_cambia_plan_recalcula_creditos_mensuales(self, db):
        """Premium → Pro: creditos_mensuales debe pasar de 100 a 500."""
        from sqlalchemy import select

        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)
        ev = _evento_updated(plan="pro", price_id="price_pro_v1")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True

        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            assert sub.plan_codigo == "pro"
            assert sub.creditos_mensuales == 500

    @pytest.mark.asyncio
    async def test_no_toca_saldo(self, db):
        """Cambio de plan NO afecta el saldo actual del usuario; aplica al
        próximo invoice."""
        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)
        # Acreditar 100 simulando un invoice previo
        await db.acreditar("14076936023", 100, "previo", stripe_session_id="in_prev")
        assert await db.obtener_saldo("14076936023") == 100

        ev = _evento_updated(plan="pro")
        await db.procesar_evento_suscripcion(ev)
        # Saldo no cambia
        assert await db.obtener_saldo("14076936023") == 100

    @pytest.mark.asyncio
    async def test_plan_desconocido_no_actualiza_creditos(self, db):
        """Si llega un plan que no conocemos, mantenemos plan_codigo y
        creditos_mensuales anteriores."""
        from sqlalchemy import select

        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)
        ev = _evento_updated(plan="enterprise")
        res = await db.procesar_evento_suscripcion(ev)
        # handled=True igual: actualizamos lo que sí pudimos (status/price);
        # el plan rechazado se anota en cambios.
        assert res["handled"] is True

        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            assert sub.plan_codigo == "premium"  # no cambió
            assert sub.creditos_mensuales == 100  # no cambió

    @pytest.mark.asyncio
    async def test_subscription_no_persistida(self, db):
        ev = _evento_updated(subscription_id="sub_inexistente")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "subscription_no_persistida"


# ── customer.subscription.deleted ───────────────────────────────────────────


class TestSubscriptionDeleted:
    @pytest.mark.asyncio
    async def test_marca_canceled(self, db):
        from sqlalchemy import select

        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)
        ev = _evento_deleted()
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True

        async with agent.memory.async_session() as session:
            sub = (await session.execute(
                select(agent.memory.SuscripcionStripe).where(
                    agent.memory.SuscripcionStripe.subscription_id == "sub_001"
                )
            )).scalar_one()
            assert sub.status == "canceled"

    @pytest.mark.asyncio
    async def test_preserva_saldo_del_usuario(self, db):
        """Decisión owner: cancelar NO borra créditos. Lo que el cliente ya
        pagó es suyo."""
        await _crear_suscripcion(db, "sub_001", "14076936023", "premium", 100)
        await db.acreditar("14076936023", 100, "previo", stripe_session_id="in_prev")
        saldo_antes = await db.obtener_saldo("14076936023")
        assert saldo_antes == 100

        ev = _evento_deleted()
        await db.procesar_evento_suscripcion(ev)

        saldo_despues = await db.obtener_saldo("14076936023")
        assert saldo_despues == 100  # se conserva

    @pytest.mark.asyncio
    async def test_subscription_no_persistida(self, db):
        ev = _evento_deleted(subscription_id="sub_inexistente")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "subscription_no_persistida"


# ── Idempotencia general por event.id ──────────────────────────────────────


class TestIdempotenciaEventId:
    @pytest.mark.asyncio
    async def test_event_id_duplicado_skip(self, db):
        ev = _evento_checkout(event_id="evt_only")
        await db.procesar_evento_suscripcion(ev)
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "duplicate_event"

    @pytest.mark.asyncio
    async def test_evento_no_handled_no_se_marca(self, db):
        """Si el handler retorna handled=False (ej. plan inválido),
        NO marcamos el evento como procesado: si Stripe reintenta tras
        que el owner arregle config, se vuelve a procesar."""
        from sqlalchemy import select

        ev = _evento_checkout(event_id="evt_plan_malo", plan="enterprise")
        await db.procesar_evento_suscripcion(ev)

        async with agent.memory.async_session() as session:
            registros = (await session.execute(
                select(agent.memory.EventoStripeProcesado).where(
                    agent.memory.EventoStripeProcesado.event_id == "evt_plan_malo"
                )
            )).scalars().all()
            assert len(registros) == 0  # no se marcó

    @pytest.mark.asyncio
    async def test_evento_handled_si_se_marca(self, db):
        """Camino feliz: se inserta fila en EventoStripeProcesado."""
        from sqlalchemy import select

        ev = _evento_checkout(event_id="evt_ok", plan="premium")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is True

        async with agent.memory.async_session() as session:
            registro = (await session.execute(
                select(agent.memory.EventoStripeProcesado).where(
                    agent.memory.EventoStripeProcesado.event_id == "evt_ok"
                )
            )).scalar_one()
            assert registro.tipo == "checkout.session.completed"

    @pytest.mark.asyncio
    async def test_evento_sin_id_rechaza(self, db):
        ev = _evento_checkout(event_id="")
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert res["reason"] == "missing_event_id"


# ── Tipo de evento no soportado ────────────────────────────────────────────


class TestTipoNoSoportado:
    @pytest.mark.asyncio
    async def test_tipo_random_no_revienta(self, db):
        ev = {
            "id": "evt_random",
            "type": "ping.test",
            "data": {"object": {}},
        }
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False
        assert "tipo no soportado" in res["reason"]

    @pytest.mark.asyncio
    async def test_invoice_payment_failed_no_se_procesa(self, db):
        """payment_failed NO está en T1.3.C — solo payment_succeeded."""
        ev = {
            "id": "evt_failed",
            "type": "invoice.payment_failed",
            "data": {"object": {"id": "in_x", "subscription": "sub_x"}},
        }
        res = await db.procesar_evento_suscripcion(ev)
        assert res["handled"] is False


# ── Legacy procesar_evento_stripe sigue funcionando ────────────────────────


class TestLegacyOneTimeIntacto:
    @pytest.mark.asyncio
    async def test_procesar_evento_stripe_legacy_one_time(self, db):
        """Asegura que la T1.3.C no rompió el path one-time existente."""
        ev_legacy = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_legacy_001",
                    "client_reference_id": "5551231234",
                    "metadata": {"telefono": "5551231234", "creditos": "100"},
                }
            },
        }
        res = await db.procesar_evento_stripe(ev_legacy)
        assert res["handled"] is True
        assert res["creditos"] == 100
        assert await db.obtener_saldo("5551231234") == 100
