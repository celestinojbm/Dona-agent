# tests/test_main_internal_stripe.py — Tests T1.3.D endpoint /internal/stripe-event

"""
Cubre el alcance mínimo de T1.3.D:
  - Sin X-Internal-Signature → 401.
  - Firma inválida → 401.
  - Firma válida + JSON malformado → 400.
  - Firma válida + evento válido → 200 + procesa.
  - duplicate_event → 200 (no-retryable).
  - invoice_ya_acreditado → 200 (no-retryable).
  - subscription_no_persistida en invoice.payment_succeeded → 500 (race).
  - subscription_no_persistida en updated/deleted → 200 (no race, no retryable).
  - missing_telefono / plan_invalido → 200.
  - ENVIRONMENT=production sin INTERNAL_BRIDGE_SECRET → fail-fast.
  - /webhook/stripe legacy intacto.

NO cubre:
  - Bridge landing → backend (T1.3.E, código del landing en TypeScript).
  - Mover Stripe Dashboard → backend (T1.3.F).
"""

import hmac
import hashlib
import importlib
import json
import os
import pytest
from fastapi.testclient import TestClient


# agent.main requiere apscheduler. Si no está disponible, saltamos toda la suite.
_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:
    _main_disponible = False


_requiere_main = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler (no instalado en este entorno)",
)


SECRET_TEST = "test-secret-not-real"


def _firmar(body: bytes, secret: str = SECRET_TEST) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _evento_checkout_subscription(
    *,
    event_id="evt_endpoint_001",
    subscription_id="sub_ep_001",
    plan="premium",
    phone="14076936023",
):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_ep_001",
                "mode": "subscription",
                "subscription": subscription_id,
                "customer": "cus_ep_001",
                "metadata": {"plan": plan, "phone": phone},
                "customer_details": {"phone": "+" + phone},
            }
        },
    }


def _evento_invoice(
    *,
    event_id="evt_endpoint_inv_001",
    invoice_id="in_ep_001",
    subscription_id="sub_ep_001",
):
    return {
        "id": event_id,
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {"id": invoice_id, "subscription": subscription_id}
        },
    }


# ── Fixture: backend levantado con DB aislada y env vars válidas ────────────


@pytest.fixture
def setup_endpoint(tmp_path, monkeypatch):
    """
    Configura env vars + DB SQLite + reloads agent.memory y agent.billing,
    inicializa la DB, y retorna un TestClient. NO recarga agent.main (sus
    dependencias asíncronas hacen el reload muy frágil); en su lugar
    monkeypatch.setenv basta porque _verificar_firma_interna y la fail-fast
    leen env vars on demand.
    """
    db_path = tmp_path / "internal_stripe.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100")
    monkeypatch.setenv("STRIPE_CREDITOS_PRO", "500")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)
    # ENVIRONMENT default ya es development/test; no lo cambiamos aquí.

    import agent.memory
    import agent.billing
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)

    # Inicializar tablas en la DB del test.
    import asyncio
    asyncio.get_event_loop().run_until_complete(agent.memory.inicializar_db())

    from agent.main import app
    return TestClient(app), agent.memory, agent.billing


# ── 1-2. Firma faltante o inválida → 401 ───────────────────────────────────


@_requiere_main
class TestFirmaInvalida:
    def test_sin_header_devuelve_401(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = json.dumps(_evento_checkout_subscription()).encode("utf-8")
        r = client.post("/internal/stripe-event", content=body)
        assert r.status_code == 401
        assert "signature_invalid" in r.json().get("detail", "")

    def test_header_vacio_devuelve_401(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = json.dumps(_evento_checkout_subscription()).encode("utf-8")
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": ""},
        )
        assert r.status_code == 401

    def test_firma_invalida_devuelve_401(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = json.dumps(_evento_checkout_subscription()).encode("utf-8")
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": "deadbeef"},
        )
        assert r.status_code == 401

    def test_firma_de_otro_secret_devuelve_401(self, setup_endpoint):
        """Si el atacante firma con su propio secret, debe rechazarse."""
        client, _, _ = setup_endpoint
        body = json.dumps(_evento_checkout_subscription()).encode("utf-8")
        sig_atacante = _firmar(body, secret="atacante-secret")
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig_atacante},
        )
        assert r.status_code == 401

    def test_firma_correcta_pero_body_modificado_devuelve_401(self, setup_endpoint):
        """Si el body cambia tras firmar, la verificación falla."""
        client, _, _ = setup_endpoint
        body_original = json.dumps(_evento_checkout_subscription()).encode("utf-8")
        sig = _firmar(body_original)
        # Servidor recibe un body distinto que el firmado.
        body_modificado = body_original.replace(b"premium", b"pro")
        r = client.post(
            "/internal/stripe-event",
            content=body_modificado,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 401


# ── 3. Firma válida + evento válido → 200 + procesa ────────────────────────


@_requiere_main
class TestFirmaValidaProcesa:
    def test_checkout_valido_devuelve_200_y_crea_suscripcion(self, setup_endpoint):
        client, memory, billing = setup_endpoint
        body = json.dumps(_evento_checkout_subscription()).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "ok"
        assert j["handled"] is True
        assert j["plan_codigo"] == "premium"

        # Verificar que la suscripción se creó en DB.
        from sqlalchemy import select
        import asyncio

        async def _check():
            async with memory.async_session() as session:
                row = (await session.execute(
                    select(memory.SuscripcionStripe).where(
                        memory.SuscripcionStripe.subscription_id == "sub_ep_001"
                    )
                )).scalar_one()
                return row.plan_codigo, row.creditos_mensuales

        plan, creditos = asyncio.get_event_loop().run_until_complete(_check())
        assert plan == "premium"
        assert creditos == 100

    def test_invoice_acredita_via_endpoint(self, setup_endpoint):
        client, memory, billing = setup_endpoint
        # Setup: crear suscripción primero (usar mismo flujo: checkout)
        body_co = json.dumps(_evento_checkout_subscription()).encode("utf-8")
        sig_co = _firmar(body_co)
        r1 = client.post(
            "/internal/stripe-event",
            content=body_co,
            headers={"X-Internal-Signature": sig_co},
        )
        assert r1.status_code == 200

        # Invoice
        body_inv = json.dumps(_evento_invoice()).encode("utf-8")
        sig_inv = _firmar(body_inv)
        r2 = client.post(
            "/internal/stripe-event",
            content=body_inv,
            headers={"X-Internal-Signature": sig_inv},
        )
        assert r2.status_code == 200
        j = r2.json()
        assert j["handled"] is True
        assert j["creditos"] == 100


# ── 4. JSON inválido tras firma válida → 400 ───────────────────────────────


@_requiere_main
class TestJsonInvalido:
    def test_body_no_es_json_devuelve_400(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = b"esto no es json"
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 400
        assert "json_invalid" in r.json().get("detail", "")

    def test_body_json_pero_no_objeto_devuelve_400(self, setup_endpoint):
        """Un array o un string es JSON válido pero no aceptamos."""
        client, _, _ = setup_endpoint
        body = json.dumps([1, 2, 3]).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 400
        assert "json_not_object" in r.json().get("detail", "")

    def test_body_vacio_devuelve_400(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = b""
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 400


# ── 5. duplicate_event → 200 (no-retryable) ────────────────────────────────


@_requiere_main
class TestDuplicateEvent:
    def test_evento_duplicado_devuelve_200(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = json.dumps(
            _evento_checkout_subscription(event_id="evt_dup_endpoint")
        ).encode("utf-8")
        sig = _firmar(body)

        r1 = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r1.status_code == 200
        assert r1.json()["handled"] is True

        # Segundo POST con mismo body (mismo event.id) → 200 + handled=False
        r2 = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r2.status_code == 200
        assert r2.json()["handled"] is False
        assert r2.json()["reason"] == "duplicate_event"


# ── 6. invoice_ya_acreditado → 200 ────────────────────────────────────────


@_requiere_main
class TestInvoiceYaAcreditado:
    def test_invoice_acreditado_dos_veces_devuelve_200(self, setup_endpoint):
        client, memory, _ = setup_endpoint

        # Setup checkout
        body_co = json.dumps(_evento_checkout_subscription()).encode("utf-8")
        client.post(
            "/internal/stripe-event",
            content=body_co,
            headers={"X-Internal-Signature": _firmar(body_co)},
        )

        # Invoice 1
        body_inv1 = json.dumps(_evento_invoice(event_id="evt_inv_a")).encode("utf-8")
        r1 = client.post(
            "/internal/stripe-event",
            content=body_inv1,
            headers={"X-Internal-Signature": _firmar(body_inv1)},
        )
        assert r1.status_code == 200
        assert r1.json()["handled"] is True

        # Invoice 2: mismo invoice.id, distinto event.id (Stripe re-envía
        # un evento regenerado).
        body_inv2 = json.dumps(_evento_invoice(event_id="evt_inv_b")).encode("utf-8")
        r2 = client.post(
            "/internal/stripe-event",
            content=body_inv2,
            headers={"X-Internal-Signature": _firmar(body_inv2)},
        )
        assert r2.status_code == 200  # no es 500
        assert r2.json()["reason"] == "invoice_ya_acreditado"


# ── 7. subscription_no_persistida en invoice → 500 (race) ──────────────────


@_requiere_main
class TestRaceInvoiceCheckout:
    def test_invoice_sin_suscripcion_devuelve_500(self, setup_endpoint):
        """Race: invoice llegó antes que checkout. Necesitamos retry."""
        client, _, _ = setup_endpoint
        body = json.dumps(
            _evento_invoice(subscription_id="sub_no_persistida")
        ).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 500
        assert "subscription_no_persistida_retry" in r.json().get("detail", "")

    def test_subscription_updated_sin_persistida_NO_retryable(self, setup_endpoint):
        """customer.subscription.updated para sub desconocida: no es race,
        es legitimamente desconocida — no retryable, 200."""
        client, _, _ = setup_endpoint
        body = json.dumps({
            "id": "evt_upd_no_pers",
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_inexistente", "status": "active"}},
        }).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200
        assert r.json()["reason"] == "subscription_no_persistida"

    def test_subscription_deleted_sin_persistida_NO_retryable(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = json.dumps({
            "id": "evt_del_no_pers",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_inexistente", "status": "canceled"}},
        }).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200


# ── 8. Otros handled=False → 200 (no retryable) ────────────────────────────


@_requiere_main
class TestNoRetryable:
    def test_missing_telefono_devuelve_200(self, setup_endpoint):
        client, _, _ = setup_endpoint
        ev = _evento_checkout_subscription(phone="")
        ev["data"]["object"]["customer_details"]["phone"] = ""
        body = json.dumps(ev).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200
        assert r.json()["reason"] == "missing_telefono"

    def test_plan_invalido_devuelve_200(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = json.dumps(
            _evento_checkout_subscription(plan="enterprise")
        ).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200
        assert "plan_invalido" in r.json().get("reason", "")

    def test_missing_event_id_devuelve_200(self, setup_endpoint):
        client, _, _ = setup_endpoint
        ev = _evento_checkout_subscription(event_id="")
        body = json.dumps(ev).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200
        assert r.json()["reason"] == "missing_event_id"

    def test_tipo_no_soportado_devuelve_200(self, setup_endpoint):
        client, _, _ = setup_endpoint
        body = json.dumps({
            "id": "evt_random",
            "type": "ping.test",
            "data": {"object": {}},
        }).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200
        assert "no soportado" in r.json().get("reason", "")

    def test_checkout_mode_payment_va_a_path_topup(self, setup_endpoint):
        """T1.7: mode=payment ya NO se rechaza con 'subscription' — ahora
        despacha a procesar_evento_stripe (top-ups one-time). Sin
        metadata.creditos, ese path retorna 'metadata faltante'."""
        client, _, _ = setup_endpoint
        ev = _evento_checkout_subscription()
        ev["data"]["object"]["mode"] = "payment"
        # Sin metadata.creditos el legacy no acredita.
        body = json.dumps(ev).encode("utf-8")
        sig = _firmar(body)
        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200
        # El path nuevo (procesar_evento_stripe) reporta motivo distinto.
        reason = r.json().get("reason", "")
        assert "metadata" in reason or "subscription" not in reason


# ── 9. Fail-fast: ENVIRONMENT=production sin INTERNAL_BRIDGE_SECRET ────────


class TestFailFastProduccion:
    """No requiere _requiere_main porque testea la función helper directamente."""

    def test_production_sin_secret_levanta_runtimeerror(self, monkeypatch):
        from agent.main import _check_internal_bridge_secret

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("INTERNAL_BRIDGE_SECRET", raising=False)

        with pytest.raises(RuntimeError) as exc:
            _check_internal_bridge_secret()
        msg = str(exc.value)
        assert "INTERNAL_BRIDGE_SECRET" in msg
        assert "estricto" in msg  # fail-closed: producción O entorno desconocido
        # No debe filtrar valores reales del secret en el error.
        assert "test-secret" not in msg

    def test_production_con_whitespace_solo_falla(self, monkeypatch):
        from agent.main import _check_internal_bridge_secret

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", "   ")

        with pytest.raises(RuntimeError):
            _check_internal_bridge_secret()

    def test_production_con_secret_real_no_falla(self, monkeypatch):
        from agent.main import _check_internal_bridge_secret

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", "valor-cualquiera")
        # No debe levantar.
        _check_internal_bridge_secret()

    def test_dev_sin_secret_no_falla_pero_endpoint_rechaza(self, monkeypatch):
        """En dev no abortamos al import. El endpoint igual rechaza 401
        sin secret configurado (no hay path permisivo)."""
        from agent.main import _check_internal_bridge_secret, _verificar_firma_interna

        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("INTERNAL_BRIDGE_SECRET", raising=False)
        # No levanta:
        _check_internal_bridge_secret()
        # Pero el verificador retorna False sin secret:
        assert _verificar_firma_interna(b"body", "anything") is False


# ── 10. /webhook/stripe legacy intacto ─────────────────────────────────────


@_requiere_main
class TestLegacyWebhookIntacto:
    def test_webhook_stripe_existe(self):
        """El endpoint legacy /webhook/stripe sigue registrado en la app."""
        from agent.main import app

        rutas = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/webhook/stripe" in rutas
        assert "/internal/stripe-event" in rutas

    def test_webhook_stripe_funcion_existe(self):
        """La función webhook_stripe sigue existiendo y no fue alterada."""
        from agent import main
        assert hasattr(main, "webhook_stripe")
        # Smoke: la firma de la función no cambió
        import inspect
        params = inspect.signature(main.webhook_stripe).parameters
        assert "request" in params
