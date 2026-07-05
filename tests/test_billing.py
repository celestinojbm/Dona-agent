# tests/test_billing.py — Tests del sistema de créditos

"""
Cubre:
  - Acreditar a usuario nuevo / existente
  - Cobro exitoso, cobro con saldo insuficiente
  - Idempotencia por stripe_session_id
  - cobrar_o_rechazar: happy path y texto de error
  - procesar_evento_stripe con payload válido / inválido
"""

import importlib
import pytest

import agent.memory
import agent.billing


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """DB SQLite aislada por test."""
    db_path = tmp_path / "bill.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)
    await agent.memory.inicializar_db()
    return agent.billing


class TestSaldoYAcreditar:
    @pytest.mark.asyncio
    async def test_saldo_inicial_es_cero(self, db):
        s = await db.obtener_saldo("5551234567")
        assert s == 0

    @pytest.mark.asyncio
    async def test_acreditar_a_usuario_nuevo(self, db):
        saldo = await db.acreditar("5551", 100, "paquete inicial", stripe_session_id="sess_001")
        assert saldo == 100
        assert await db.obtener_saldo("5551") == 100

    @pytest.mark.asyncio
    async def test_acreditar_es_idempotente(self, db):
        await db.acreditar("5551", 100, "compra", stripe_session_id="sess_dup")
        # Reentrega del mismo evento
        saldo = await db.acreditar("5551", 100, "compra", stripe_session_id="sess_dup")
        assert saldo == 100  # no se duplicó

    @pytest.mark.asyncio
    async def test_acreditar_dos_sessions_distintas_suma(self, db):
        await db.acreditar("5551", 100, "primera", stripe_session_id="s1")
        saldo = await db.acreditar("5551", 50, "segunda", stripe_session_id="s2")
        assert saldo == 150

    @pytest.mark.asyncio
    async def test_creditos_negativos_falla(self, db):
        with pytest.raises(ValueError):
            await db.acreditar("5551", -10, "hack")
        with pytest.raises(ValueError):
            await db.acreditar("5551", 0, "hack")


class TestCobrar:
    @pytest.mark.asyncio
    async def test_cobro_exitoso(self, db):
        await db.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        nuevo = await db.cobrar("5551", 30, "generar_imagen")
        assert nuevo == 70

    @pytest.mark.asyncio
    async def test_cobro_saldo_insuficiente(self, db):
        await db.acreditar("5551", 10, "inicial", stripe_session_id="s1")
        with pytest.raises(db.SaldoInsuficienteError) as exc:
            await db.cobrar("5551", 50, "gen_video")
        assert exc.value.saldo == 10
        assert exc.value.requerido == 50

    @pytest.mark.asyncio
    async def test_cobro_sin_fila(self, db):
        with pytest.raises(db.SaldoInsuficienteError):
            await db.cobrar("5551_nunca_existio", 1, "algo")

    @pytest.mark.asyncio
    async def test_cobro_negativo_falla(self, db):
        with pytest.raises(ValueError):
            await db.cobrar("5551", -5, "hack")

    @pytest.mark.asyncio
    async def test_cobros_multiples_exactos(self, db):
        await db.acreditar("5551", 10, "inicial", stripe_session_id="s1")
        await db.cobrar("5551", 3, "a")
        await db.cobrar("5551", 3, "b")
        await db.cobrar("5551", 4, "c")
        assert await db.obtener_saldo("5551") == 0
        with pytest.raises(db.SaldoInsuficienteError):
            await db.cobrar("5551", 1, "d")


class TestCobrarORechazar:
    @pytest.mark.asyncio
    async def test_happy_path(self, db):
        await db.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        ok, err = await db.cobrar_o_rechazar("5551", 10, "gen_imagen")
        assert ok is True
        assert err is None

    @pytest.mark.asyncio
    async def test_rechazo_devuelve_texto_util(self, db):
        await db.acreditar("5551", 5, "inicial", stripe_session_id="s1")
        ok, err = await db.cobrar_o_rechazar("5551", 100, "gen_video")
        assert ok is False
        assert err is not None
        assert "100" in err  # requerido
        assert "5" in err    # saldo actual
        assert "recargar" in err.lower()


class TestResumen:
    @pytest.mark.asyncio
    async def test_resumen_incluye_transacciones(self, db):
        await db.acreditar("5551", 100, "pack 100", stripe_session_id="s1")
        await db.cobrar("5551", 10, "gen_imagen_01")
        await db.cobrar("5551", 5, "gen_imagen_02")
        r = await db.obtener_resumen("5551")
        assert r["saldo"] == 85
        assert r["total_comprado"] == 100
        assert r["total_consumido"] == 15
        assert len(r["ultimos"]) == 3
        # orden desc por fecha — última transacción primero
        assert r["ultimos"][0]["delta"] == -5


class TestPaquetes:
    def test_solo_paquetes_con_price_id(self, monkeypatch):
        monkeypatch.setenv("STRIPE_PRICE_PAQUETE_100", "price_100")
        monkeypatch.delenv("STRIPE_PRICE_PAQUETE_500", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_PAQUETE_2000", raising=False)
        packs = agent.billing.paquetes_disponibles()
        assert len(packs) == 1
        assert packs[0].codigo == "100"

    def test_paquete_por_codigo(self):
        p = agent.billing.paquete_por_codigo("500")
        assert p is not None
        assert p.creditos == 500
        assert p.precio_usd == 40.0


class TestProcesarEventoStripe:
    @pytest.mark.asyncio
    async def test_evento_ignorado(self, db):
        r = await db.procesar_evento_stripe({"type": "invoice.paid", "data": {"object": {}}})
        assert r["handled"] is False

    @pytest.mark.asyncio
    async def test_checkout_completed_acredita(self, db):
        evento = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_abc",
                "mode": "payment",
                "payment_status": "paid",
                "client_reference_id": "5551234567",
                "metadata": {"telefono": "5551234567", "paquete": "100", "creditos": "100"},
            }},
        }
        r = await db.procesar_evento_stripe(evento)
        assert r["handled"] is True
        assert r["saldo"] == 100
        assert await db.obtener_saldo("5551234567") == 100

    @pytest.mark.asyncio
    async def test_checkout_completed_metadata_faltante(self, db):
        evento = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_x"}},
        }
        r = await db.procesar_evento_stripe(evento)
        assert r["handled"] is False

    @pytest.mark.asyncio
    async def test_checkout_completed_idempotente(self, db):
        evento = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_dup",
                "mode": "payment",
                "payment_status": "paid",
                "client_reference_id": "5551",
                "metadata": {"telefono": "5551", "creditos": "500"},
            }},
        }
        await db.procesar_evento_stripe(evento)
        # Reentrega
        await db.procesar_evento_stripe(evento)
        assert await db.obtener_saldo("5551") == 500  # no duplicado

    @pytest.mark.asyncio
    async def test_checkout_unpaid_no_acredita(self, db):
        # Fable5 · 3.2: payment_status != 'paid' NUNCA acredita (fail-closed),
        # aunque traiga telefono+creditos válidos.
        evento = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_unpaid",
                "mode": "payment",
                "payment_status": "unpaid",
                "client_reference_id": "5559999",
                "metadata": {"telefono": "5559999", "creditos": "100"},
            }},
        }
        r = await db.procesar_evento_stripe(evento)
        assert r["handled"] is False
        assert await db.obtener_saldo("5559999") == 0

    @pytest.mark.asyncio
    async def test_checkout_mode_subscription_no_acredita(self, db):
        # Fable5 · 3.2: mode='subscription' no se acredita por este path (lo
        # maneja el ciclo de invoice); evita crédito indebido si llega directo.
        evento = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_sub",
                "mode": "subscription",
                "payment_status": "paid",
                "client_reference_id": "5558888",
                "metadata": {"telefono": "5558888", "creditos": "100"},
            }},
        }
        r = await db.procesar_evento_stripe(evento)
        assert r["handled"] is False
        assert await db.obtener_saldo("5558888") == 0

    @pytest.mark.asyncio
    async def test_checkout_sin_payment_status_no_acredita(self, db):
        # Fail-closed ante evento sin payment_status (no se asume pagado).
        evento = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_nostatus",
                "mode": "payment",
                "client_reference_id": "5557777",
                "metadata": {"telefono": "5557777", "creditos": "100"},
            }},
        }
        r = await db.procesar_evento_stripe(evento)
        assert r["handled"] is False
        assert await db.obtener_saldo("5557777") == 0

    @pytest.mark.asyncio
    async def test_reentrega_con_event_id_no_reprocesa_ni_renotifica(self, db):
        # Fase 1 · TEMA 3.1: el gate atómico EventoStripeProcesado (por event.id)
        # debe cubrir también el path directo de top-ups one-time. Stripe reentrega
        # (at-least-once); sin el gate, la 2ª entrega volvía a retornar handled=True
        # y el webhook re-disparaba la notificación "gracias por tu compra" (aunque
        # acreditar ya no doblaba el saldo). La reentrega debe devolver handled=False.
        evento = {
            "id": "evt_topup_1",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_evt_1",
                "mode": "payment",
                "payment_status": "paid",
                "client_reference_id": "5551000",
                "metadata": {"telefono": "5551000", "creditos": "300"},
            }},
        }
        r1 = await db.procesar_evento_stripe(evento)
        assert r1["handled"] is True
        assert r1["saldo"] == 300
        # Reentrega EXACTA del mismo evento (mismo event.id).
        r2 = await db.procesar_evento_stripe(evento)
        assert r2["handled"] is False
        assert r2["reason"] == "duplicate_event"
        # El dinero no se duplicó y la notificación no se re-disparará (handled=False).
        assert await db.obtener_saldo("5551000") == 300

    @pytest.mark.asyncio
    async def test_reentrega_concurrente_solo_una_acredita_y_notifica(self, db):
        # Adversarial · concurrencia: dos entregas del mismo event.id llegan a la
        # vez. El PK de EventoStripeProcesado decide la propiedad por construcción:
        # exactamente UNA obtiene handled=True; la otra choca con el PK y devuelve
        # handled=False. Ni doble crédito ni doble notificación.
        import asyncio

        evento = {
            "id": "evt_topup_race",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_evt_race",
                "mode": "payment",
                "payment_status": "paid",
                "client_reference_id": "5552000",
                "metadata": {"telefono": "5552000", "creditos": "150"},
            }},
        }
        r_a, r_b = await asyncio.gather(
            db.procesar_evento_stripe(evento),
            db.procesar_evento_stripe(evento),
        )
        handled = [r for r in (r_a, r_b) if r.get("handled")]
        no_handled = [r for r in (r_a, r_b) if not r.get("handled")]
        assert len(handled) == 1
        assert len(no_handled) == 1
        assert no_handled[0]["reason"] == "duplicate_event"
        assert await db.obtener_saldo("5552000") == 150

    @pytest.mark.asyncio
    async def test_acreditar_revienta_libera_el_gate(self, db, monkeypatch):
        # Si acreditar falla (excepción transitoria), el gate EventoStripeProcesado
        # debe LIBERARSE para que Stripe reintente — sin esto el event_id quedaría
        # envenenado permanentemente y el crédito legítimo se perdería. El dinero
        # sigue protegido por la idempotencia de acreditar en el reintento.
        evento = {
            "id": "evt_boom",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_boom",
                "mode": "payment",
                "payment_status": "paid",
                "client_reference_id": "5554000",
                "metadata": {"telefono": "5554000", "creditos": "100"},
            }},
        }

        original = db.acreditar
        llamadas = {"n": 0}

        async def _acreditar_falla_una_vez(*a, **k):
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                raise RuntimeError("boom transitorio")
            return await original(*a, **k)

        monkeypatch.setattr(db, "acreditar", _acreditar_falla_una_vez)

        # 1ª entrega: acreditar revienta → la excepción propaga y el gate se libera.
        with pytest.raises(RuntimeError):
            await db.procesar_evento_stripe(evento)
        assert await db.obtener_saldo("5554000") == 0

        # Reintento de Stripe (mismo event.id): como el gate se liberó, reprocesa
        # y esta vez acredita.
        r2 = await db.procesar_evento_stripe(evento)
        assert r2["handled"] is True
        assert await db.obtener_saldo("5554000") == 100

    @pytest.mark.asyncio
    async def test_evento_sin_id_mantiene_comportamiento_legacy(self, db):
        # Compat: eventos sin top-level event.id (shape sintético) caen al camino
        # legacy — el gate se omite y acreditar sigue protegiendo el dinero. No se
        # rompe ningún consumidor que construya eventos sin event.id.
        evento = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_sin_evt_id",
                "mode": "payment",
                "payment_status": "paid",
                "client_reference_id": "5553000",
                "metadata": {"telefono": "5553000", "creditos": "77"},
            }},
        }
        r1 = await db.procesar_evento_stripe(evento)
        assert r1["handled"] is True
        # Sin event.id no hay gate; la reentrega vuelve a handled=True pero acreditar
        # (idempotente por session_id) evita el doble crédito.
        r2 = await db.procesar_evento_stripe(evento)
        assert r2["handled"] is True
        assert await db.obtener_saldo("5553000") == 77


class TestVerificarFirmaDev:
    """Comportamiento de verificar_firma_stripe en development/test.

    En entornos no-producción mantenemos el path permisivo (parsea sin
    verificar) para permitir pruebas locales sin configurar Stripe. El
    aviso en logs deja claro que es inseguro.
    """

    def test_sin_secret_en_dev_acepta_payload(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        payload = b'{"type":"ping","data":{"object":{}}}'
        ev = agent.billing.verificar_firma_stripe(payload, "no-sig")
        assert ev is not None
        assert ev["type"] == "ping"

    def test_sin_secret_en_test_acepta_payload(self, monkeypatch):
        # ENVIRONMENT=test (default de conftest.py) sigue siendo permisivo.
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        payload = b'{"type":"ping"}'
        ev = agent.billing.verificar_firma_stripe(payload, "no-sig")
        assert ev is not None
        assert ev["type"] == "ping"

    def test_payload_invalido_retorna_none(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        ev = agent.billing.verificar_firma_stripe(b"{not json", "")
        assert ev is None


class TestVerificarFirmaProduction:
    """T0.2: Comportamiento de verificar_firma_stripe en producción.

    En producción, sin secret, el endpoint debe rechazar todos los webhooks.
    Esto cierra la superficie de ataque pública del endpoint /webhook/stripe
    (un atacante que descubra la URL no puede acreditar créditos forjados).
    """

    def test_production_sin_secret_rechaza_payload(self, monkeypatch):
        """Path runtime: aunque el módulo se haya cargado, en prod sin secret
        la función retorna None (defensa en profundidad)."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        # webhook_secret="" como argumento explícito = sin secret pasado.
        ev = agent.billing.verificar_firma_stripe(
            b'{"type":"checkout.session.completed"}',
            "no-sig",
            webhook_secret="",
        )
        assert ev is None

    def test_production_con_secret_firma_invalida_retorna_none(self, monkeypatch):
        """Con secret presente pero firma inválida, retorna None (Stripe SDK rechaza)."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        ev = agent.billing.verificar_firma_stripe(
            b'{"type":"checkout.session.completed"}',
            "t=123,v1=invalid",
            webhook_secret="whsec_test_dummy_secret_for_unit_test",
        )
        assert ev is None

    def test_production_sin_secret_levanta_runtime_error_al_reload(self, monkeypatch):
        """Al import-time: si production sin secret, RuntimeError aborta el deploy."""
        import importlib
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        try:
            with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
                importlib.reload(agent.billing)
        finally:
            # Restaurar el módulo en estado limpio para tests posteriores.
            monkeypatch.setenv("ENVIRONMENT", "test")
            importlib.reload(agent.billing)

    def test_production_con_secret_no_levanta_al_reload(self, monkeypatch):
        """Con secret configurado, el import en production no aborta."""
        import importlib
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_dummy_secret")
        try:
            importlib.reload(agent.billing)  # No debe levantar.
        finally:
            monkeypatch.setenv("ENVIRONMENT", "test")
            importlib.reload(agent.billing)
