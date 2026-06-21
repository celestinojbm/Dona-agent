# tests/test_internal_stripe_topup_dispatch.py — T1.7

"""
Cubre el dispatch dual del endpoint /internal/stripe-event:
  - mode=subscription → procesar_evento_suscripcion (T1.3.C, ya cubierto
    en otros tests).
  - mode=payment → procesar_evento_stripe (legacy one-time, T1.7).

NO toca DB real. Usa fixture aislada con DB SQLite en tmp_path.
NO llama Stripe. Solo testea el dispatch interno.
"""

import hmac
import hashlib
import importlib
import json
import pytest
from fastapi.testclient import TestClient


_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:
    _main_disponible = False


_requiere_main = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler",
)


SECRET_TEST = "test-secret-not-real-t17"


def _firmar(body: bytes, secret: str = SECRET_TEST) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _evento_topup(
    *,
    event_id: str = "evt_topup_001",
    session_id: str = "cs_topup_001",
    telefono: str = "14076936023",
    creditos: int = 100,
):
    """Construye un checkout.session.completed con mode=payment (top-up)."""
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "mode": "payment",   # ← clave del dispatch T1.7
                "payment_status": "paid",  # checkout pagado (Fase 0 · 3.2)
                "client_reference_id": telefono,
                "metadata": {
                    "kind": "topup",
                    "paquete": str(creditos),
                    "creditos": str(creditos),
                    "telefono": telefono,
                },
            }
        },
    }


def _evento_subscription(
    *,
    event_id: str = "evt_sub_001",
    subscription_id: str = "sub_001",
    plan: str = "premium",
    phone: str = "14076936023",
):
    """Construye un checkout.session.completed con mode=subscription."""
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_sub_001",
                "mode": "subscription",
                "subscription": subscription_id,
                "customer": "cus_001",
                "metadata": {"plan": plan, "phone": phone},
                "customer_details": {"phone": "+" + phone},
            }
        },
    }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db_path = tmp_path / "topup_dispatch.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)
    monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100")
    monkeypatch.setenv("STRIPE_CREDITOS_PRO", "500")

    import agent.memory
    import agent.billing
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)

    import asyncio
    asyncio.get_event_loop().run_until_complete(agent.memory.inicializar_db())

    from agent.main import app
    return TestClient(app), agent.memory, agent.billing


# ── Test 1 · Dispatch a procesar_evento_stripe cuando mode=payment ──────


@_requiere_main
class TestDispatchTopup:
    def test_topup_acredita_y_devuelve_200(self, setup):
        client, memory, billing = setup
        ev = _evento_topup(creditos=100, telefono="14076936023")
        body = json.dumps(ev).encode("utf-8")
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
        # procesar_evento_stripe devuelve telefono + creditos + saldo.
        assert j["telefono"] == "14076936023"
        assert j["creditos"] == 100
        assert j["saldo"] == 100

    def test_topup_idempotente_por_session_id(self, setup):
        """Reentregar el mismo evento (mismo session.id) NO duplica créditos."""
        client, memory, billing = setup
        ev = _evento_topup(
            event_id="evt_topup_dup",
            session_id="cs_topup_dup",
            creditos=200,
        )
        body = json.dumps(ev).encode("utf-8")
        sig = _firmar(body)

        # Primera entrega.
        r1 = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r1.status_code == 200
        assert r1.json()["saldo"] == 200

        # Reentrega (mismo body → mismo session_id).
        r2 = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r2.status_code == 200
        # Saldo NO sumó otra vez.
        assert r2.json()["saldo"] == 200

    def test_topup_sin_metadata_creditos_no_acredita(self, setup):
        """Si falta metadata.creditos, procesar_evento_stripe responde 'metadata faltante'."""
        client, memory, billing = setup
        ev = _evento_topup(telefono="14076936023")
        # Vaciar metadata.creditos.
        del ev["data"]["object"]["metadata"]["creditos"]
        body = json.dumps(ev).encode("utf-8")
        sig = _firmar(body)

        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        # No retryable: 200 con detalle (no-handled).
        assert r.status_code == 200
        assert r.json()["handled"] is False
        assert "metadata" in r.json()["reason"]


# ── Test 2 · Subscription sigue funcionando · sin regresión ──────────────


@_requiere_main
class TestDispatchSubscriptionIntacto:
    def test_subscription_no_va_al_path_topup(self, setup):
        """Un checkout.session.completed mode=subscription debe ir a
        procesar_evento_suscripcion (no a procesar_evento_stripe legacy).

        Verificamos esto comprobando que el response trae los campos
        que devuelve procesar_evento_suscripcion (subscription_id,
        accion, plan_codigo) y NO los del path legacy
        (creditos+saldo top-level).
        """
        client, memory, billing = setup
        ev = _evento_subscription(
            event_id="evt_sub_dispatch",
            subscription_id="sub_dispatch_001",
            plan="premium",
            phone="14076936023",
        )
        body = json.dumps(ev).encode("utf-8")
        sig = _firmar(body)

        r = client.post(
            "/internal/stripe-event",
            content=body,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 200
        j = r.json()
        assert j["handled"] is True
        # Campos que solo los devuelve procesar_evento_suscripcion (T1.3.C).
        assert "subscription_id" in j
        assert j["subscription_id"] == "sub_dispatch_001"
        assert "accion" in j
        assert j["accion"] == "created"
        assert "plan_codigo" in j


# ── Test 3 · Auth HMAC sigue gateando ambos paths ────────────────────────


@_requiere_main
class TestAuthGate:
    def test_topup_sin_firma_devuelve_401(self, setup):
        client, _, _ = setup
        body = json.dumps(_evento_topup()).encode("utf-8")
        r = client.post("/internal/stripe-event", content=body)
        assert r.status_code == 401
