# tests/test_main_internal_usuario_resumen.py — Tests T1.4.C
# Endpoint POST /internal/usuario-resumen (read-only).

"""
Cubre el alcance mínimo de T1.4.C:
  - Firma HMAC inválida o ausente → 401.
  - JSON malformado tras HMAC válida → 400.
  - JSON no es objeto → 400.
  - Body sin subscription_id → 400.
  - subscription_id no existe → 404.
  - Sub existente sin saldo, sin transacciones → 200 estructura completa.
  - Sub existente con saldo y transacciones → 200, datos correctos.
  - Sub canceled → 200 con puede_cancelar=False.
  - Sub past_due → 200 con puede_cancelar=False.
  - El endpoint NO escribe en la base (regresión: contar filas antes/después).
  - El endpoint legacy /internal/stripe-event sigue funcionando.

NO cubre:
  - Bridge landing → backend (T1.4.D).
  - UI del dashboard (T1.4.E).
  - Cancelación cancel_at_period_end (T1.4.F).
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
    reason="agent.main requiere apscheduler (no instalado en este entorno)",
)


SECRET_TEST = "test-secret-not-real-t14c"


def _firmar(body: bytes, secret: str = SECRET_TEST) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _payload(subscription_id: str = "sub_t14c_001") -> bytes:
    return json.dumps({"subscription_id": subscription_id}).encode("utf-8")


# ── Fixture: backend con DB aislada y env vars ─────────────────────────────


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db_path = tmp_path / "usuario_resumen.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)

    import agent.memory
    import agent.billing
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)

    import asyncio
    asyncio.get_event_loop().run_until_complete(agent.memory.inicializar_db())

    from agent.main import app
    return TestClient(app), agent.memory, agent.billing


async def _crear_suscripcion(memory, subscription_id, telefono, plan="premium",
                              creditos=100, status="active",
                              customer_id="cus_t14c_001"):
    """Helper: inserta SuscripcionStripe directo (simula post-checkout)."""
    async with memory.async_session() as session:
        session.add(memory.SuscripcionStripe(
            subscription_id=subscription_id,
            telefono=telefono,
            customer_id=customer_id,
            plan_codigo=plan,
            price_id="price_test",
            status=status,
            creditos_mensuales=creditos,
        ))
        await session.commit()


# ── 1-2. Auth: firma faltante / inválida → 401 ─────────────────────────────


@_requiere_main
class TestAuth:
    def test_sin_header_devuelve_401(self, setup):
        client, _, _ = setup
        r = client.post("/internal/usuario-resumen", content=_payload())
        assert r.status_code == 401
        assert "signature_invalid" in r.json().get("detail", "")

    def test_header_vacio_devuelve_401(self, setup):
        client, _, _ = setup
        r = client.post(
            "/internal/usuario-resumen",
            content=_payload(),
            headers={"X-Internal-Signature": ""},
        )
        assert r.status_code == 401

    def test_firma_invalida_devuelve_401(self, setup):
        client, _, _ = setup
        r = client.post(
            "/internal/usuario-resumen",
            content=_payload(),
            headers={"X-Internal-Signature": "deadbeef"},
        )
        assert r.status_code == 401

    def test_firma_de_otro_secret_devuelve_401(self, setup):
        client, _, _ = setup
        body = _payload()
        sig_atacante = _firmar(body, secret="atacante-secret")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": sig_atacante},
        )
        assert r.status_code == 401

    def test_body_modificado_tras_firmar_devuelve_401(self, setup):
        client, _, _ = setup
        body_original = _payload("sub_original")
        sig = _firmar(body_original)
        body_modificado = _payload("sub_atacante")
        r = client.post(
            "/internal/usuario-resumen",
            content=body_modificado,
            headers={"X-Internal-Signature": sig},
        )
        assert r.status_code == 401


# ── 3. JSON malformado / no-objeto → 400 ───────────────────────────────────


@_requiere_main
class TestJsonInvalido:
    def test_body_no_es_json(self, setup):
        client, _, _ = setup
        body = b"esto no es json"
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 400
        assert "json_invalid" in r.json().get("detail", "")

    def test_body_es_array_no_objeto(self, setup):
        client, _, _ = setup
        body = json.dumps([1, 2, 3]).encode("utf-8")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 400
        assert "json_not_object" in r.json().get("detail", "")

    def test_body_vacio(self, setup):
        client, _, _ = setup
        body = b""
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 400


# ── 4. Body sin subscription_id → 400 ──────────────────────────────────────


@_requiere_main
class TestPayloadInvalido:
    def test_body_sin_subscription_id(self, setup):
        client, _, _ = setup
        body = json.dumps({"otro_campo": "x"}).encode("utf-8")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 400
        assert "missing_subscription_id" in r.json().get("detail", "")

    def test_subscription_id_vacio(self, setup):
        client, _, _ = setup
        body = json.dumps({"subscription_id": ""}).encode("utf-8")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 400

    def test_subscription_id_solo_whitespace(self, setup):
        client, _, _ = setup
        body = json.dumps({"subscription_id": "   "}).encode("utf-8")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 400


# ── 5. subscription_id no existe → 404 ─────────────────────────────────────


@_requiere_main
class TestSubInexistente:
    def test_subscription_inexistente_devuelve_404(self, setup):
        client, _, _ = setup
        body = _payload("sub_nunca_existio")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 404
        assert "subscription_no_persistida" in r.json().get("detail", "")


# ── 6-7. Casos felices ─────────────────────────────────────────────────────


@_requiere_main
class TestRespuestaCompleta:
    @pytest.mark.asyncio
    async def test_sub_sin_saldo_sin_trans(self, setup):
        client, memory, _ = setup
        await _crear_suscripcion(
            memory, "sub_sin_saldo", "14076936023", plan="premium", creditos=100,
        )

        body = _payload("sub_sin_saldo")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 200
        j = r.json()

        # Estructura completa
        assert set(j.keys()) == {
            "usuario", "creditos", "suscripcion",
            "transacciones_recientes", "resumen",
        }

        # Identidad
        assert j["usuario"]["id"] == "sub_sin_saldo"
        assert j["usuario"]["telefono"] == "14076936023"
        assert j["usuario"]["email"] is None  # backend no lo tiene

        # Créditos
        assert j["creditos"]["saldo_actual"] == 0
        assert j["creditos"]["creditos_mensuales"] == 100
        assert j["creditos"]["ultimo_movimiento"] is None

        # Suscripción
        assert j["suscripcion"]["estado"] == "active"
        assert j["suscripcion"]["plan"] == "premium"
        assert j["suscripcion"]["stripe_customer_id"] == "cus_t14c_001"
        assert j["suscripcion"]["stripe_subscription_id"] == "sub_sin_saldo"
        assert j["suscripcion"]["current_period_end"] is None  # de Stripe SDK en T1.4.D
        assert j["suscripcion"]["cancel_at_period_end"] is False

        # Transacciones
        assert j["transacciones_recientes"] == []

        # Resumen
        assert j["resumen"]["puede_cancelar"] is True
        assert j["resumen"]["dashboard_ready"] is True

    @pytest.mark.asyncio
    async def test_sub_con_saldo_y_transacciones(self, setup):
        client, memory, billing = setup
        await _crear_suscripcion(
            memory, "sub_con_saldo", "14076936023", plan="premium", creditos=100,
        )

        # Acreditar y consumir
        await billing.acreditar("14076936023", 100, "Renovación premium",
                                stripe_session_id="in_001")
        await billing.cobrar("14076936023", 30, "generar_imagen")
        await billing.acreditar("14076936023", 50, "Bonus", stripe_session_id="bonus_001")

        body = _payload("sub_con_saldo")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 200
        j = r.json()

        # Saldo: 100 - 30 + 50 = 120
        assert j["creditos"]["saldo_actual"] == 120
        assert j["creditos"]["ultimo_movimiento"] is not None
        # El último por fecha desc + id desc es el bonus_001 (delta=+50)
        assert j["creditos"]["ultimo_movimiento"]["delta"] == 50

        # Transacciones más reciente primero
        txs = j["transacciones_recientes"]
        assert len(txs) == 3
        assert txs[0]["delta"] == 50
        assert txs[0]["razon"] == "Bonus"
        deltas = [t["delta"] for t in txs]
        # Todas las trans presentes
        assert sorted(deltas) == [-30, 50, 100]

    @pytest.mark.asyncio
    async def test_solo_devuelve_ultimas_10(self, setup):
        client, memory, billing = setup
        await _crear_suscripcion(memory, "sub_muchas_trans", "5551112222")
        for i in range(15):
            await billing.acreditar(
                "5551112222", 1, f"Trans {i}",
                stripe_session_id=f"session_{i}",
            )

        body = _payload("sub_muchas_trans")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 200
        assert len(r.json()["transacciones_recientes"]) == 10


# ── 8. Estados de suscripción ──────────────────────────────────────────────


@_requiere_main
class TestEstadosSuscripcion:
    @pytest.mark.asyncio
    async def test_canceled_no_puede_cancelar(self, setup):
        client, memory, _ = setup
        await _crear_suscripcion(
            memory, "sub_canceled", "5559990000", status="canceled",
        )
        body = _payload("sub_canceled")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 200
        assert r.json()["suscripcion"]["estado"] == "canceled"
        assert r.json()["resumen"]["puede_cancelar"] is False

    @pytest.mark.asyncio
    async def test_past_due_no_puede_cancelar(self, setup):
        client, memory, _ = setup
        await _crear_suscripcion(
            memory, "sub_past_due", "5557778888", status="past_due",
        )
        body = _payload("sub_past_due")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 200
        assert r.json()["suscripcion"]["estado"] == "past_due"
        assert r.json()["resumen"]["puede_cancelar"] is False


# ── 9. Read-only: el endpoint no escribe ──────────────────────────────────


@_requiere_main
class TestReadOnly:
    @pytest.mark.asyncio
    async def test_endpoint_no_modifica_db(self, setup):
        """Contar filas antes y después del request: no debe cambiar."""
        from sqlalchemy import select, func

        client, memory, billing = setup
        await _crear_suscripcion(memory, "sub_readonly", "5556660000")
        await billing.acreditar(
            "5556660000", 100, "Setup", stripe_session_id="s_readonly_setup",
        )

        async def _contar():
            async with memory.async_session() as session:
                n_sub = (await session.execute(
                    select(func.count()).select_from(memory.SuscripcionStripe)
                )).scalar_one()
                n_saldo = (await session.execute(
                    select(func.count()).select_from(memory.SaldoCreditos)
                )).scalar_one()
                n_tx = (await session.execute(
                    select(func.count()).select_from(memory.TransaccionCredito)
                )).scalar_one()
                n_eventos = (await session.execute(
                    select(func.count()).select_from(memory.EventoStripeProcesado)
                )).scalar_one()
                return n_sub, n_saldo, n_tx, n_eventos

        antes = await _contar()

        # Llamar endpoint varias veces
        for _ in range(3):
            body = _payload("sub_readonly")
            r = client.post(
                "/internal/usuario-resumen",
                content=body,
                headers={"X-Internal-Signature": _firmar(body)},
            )
            assert r.status_code == 200

        despues = await _contar()
        assert antes == despues, (
            f"El endpoint modificó la DB. Antes={antes} Después={despues}"
        )


# ── 10. Endpoint legacy /internal/stripe-event sigue funcionando ───────────


@_requiere_main
class TestLegacyEndpointsIntactos:
    def test_internal_stripe_event_sigue_registrado(self):
        from agent.main import app
        rutas = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/internal/stripe-event" in rutas
        assert "/internal/usuario-resumen" in rutas
        assert "/webhook/stripe" in rutas

    def test_internal_stripe_event_acepta_request(self, setup):
        """Smoke: el endpoint legacy responde correctamente — un POST con
        firma inválida sigue dando 401, no se rompió."""
        client, _, _ = setup
        r = client.post(
            "/internal/stripe-event",
            content=b"{}",
            headers={"X-Internal-Signature": "invalido"},
        )
        assert r.status_code == 401


# ── Bonus: telefono SÍ aparece en respuesta (decisión owner T1.4.C) ────────


@_requiere_main
class TestEstructuraEsperada:
    @pytest.mark.asyncio
    async def test_telefono_presente_en_respuesta(self, setup):
        """El owner pidió la estructura {usuario.telefono} en T1.4.C.
        Confirma que el campo está y tiene el valor esperado."""
        client, memory, _ = setup
        await _crear_suscripcion(memory, "sub_phone", "14076936023")

        body = _payload("sub_phone")
        r = client.post(
            "/internal/usuario-resumen",
            content=body,
            headers={"X-Internal-Signature": _firmar(body)},
        )
        assert r.status_code == 200
        assert r.json()["usuario"]["telefono"] == "14076936023"
