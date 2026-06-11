# tests/test_automation_endpoints.py — T2.1.B · endpoints HTTP

"""
Tests de los endpoints HTTP del Action Center:
  /admin/automation/*  — ADMIN_TOKEN
  /internal/automation/* — HMAC bridge

Cubre:
- 403 sin token / 401 sin firma
- listar oportunidades / acciones
- generar acciones desde Opportunity Engine
- aprobar / rechazar respeta transiciones
- ejecutar dry-run respeta CRITICAL bloqueado y MEDIUM/HIGH sin aprobación
- IDOR: accion de OTRO usuario → 404
- respuestas no exponen idempotency_key, payload_json crudo, telefono completo
"""

import hashlib
import hmac
import importlib
import json
import pytest
from httpx import AsyncClient, ASGITransport

import agent.memory


ADMIN_TOKEN = "admin-test-token-xyz"
INTERNAL_SECRET = "internal-bridge-test-secret-yyy"


@pytest.fixture
async def app(tmp_path, monkeypatch):
    """SQLite aislada · app FastAPI fresca con env vars de test."""
    db_path = tmp_path / "ep.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", INTERNAL_SECRET)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    import agent.automation.execution as _ex
    import agent.automation.opportunities as _op
    import agent.automation.costos as _co
    # T2.1.D · forzamos costo=0 para que tests legacy de endpoints sigan
    # pasando · la lógica de reservas se valida en test_automation_
    # creditos_reservas.py
    monkeypatch.setattr(_co, "estimar_costo_accion", lambda tipo: 0)
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_ac)
    importlib.reload(_ex)
    importlib.reload(_op)
    monkeypatch.setattr(_co, "estimar_costo_accion", lambda tipo: 0)
    import agent.main as _main
    importlib.reload(_main)
    await agent.memory.inicializar_db()
    # 2.5: el destino compartido de estos tests se siembra como "conocido"
    # (camino best-effort); la política de terceros tiene tests propios.
    await agent.memory.guardar_mensaje("5215551234567", "user", "hola")
    return _main.app


def _hmac_sig(body_str: str) -> str:
    return hmac.new(
        INTERNAL_SECRET.encode("utf-8"), body_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def _seed_perfil_y_sub(telefono: str, sub_id: str = "sub_test1"):
    """Crea perfil_negocio completo + suscripcion_stripe vinculada."""
    from agent.memory import async_session, SuscripcionStripe
    from agent.business.models import PerfilNegocio
    from datetime import datetime
    async with async_session() as session:
        session.add(PerfilNegocio(
            telefono=telefono, nombre_negocio="Test Biz", industria="comida",
            moneda="MXN", meta_mensual=10000.0,
            oferta_principal="Pasteles", cliente_ideal="Familias",
            objetivo_mes="10 ventas", canales_actuales="WhatsApp, Instagram",
            bloqueo_actual="Tiempo", tareas_delegar="seguimiento clientes",
            creado=datetime.utcnow(), actualizado=datetime.utcnow(),
            onboarding_paso=None,
        ))
        session.add(SuscripcionStripe(
            subscription_id=sub_id, telefono=telefono, plan_codigo="premium",
            price_id="price_test", status="active", customer_id="cus_test1",
            creditos_mensuales=200,
            creado=datetime.utcnow(), actualizado=datetime.utcnow(),
            bienvenida_enviada=True,
        ))
        await session.commit()


# ─── /admin/automation/* ─────────────────────────────────────────────────────


class TestAdminAuth:
    @pytest.mark.asyncio
    async def test_sin_token_403(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/admin/automation/oportunidades?telefono=5551")
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_token_invalido_403(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                "/admin/automation/oportunidades?telefono=5551",
                headers={"Authorization": "Bearer wrong-token"},
            )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_token_valido_200(self, app):
        await _seed_perfil_y_sub("5551")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                "/admin/automation/oportunidades?telefono=5551",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        assert r.status_code == 200
        data = r.json()
        assert "oportunidades" in data
        assert data["count"] == len(data["oportunidades"])
        assert len(data["oportunidades"]) >= 4


class TestAdminGenerarAcciones:
    @pytest.mark.asyncio
    async def test_genera_acciones_desde_oportunidades(self, app):
        await _seed_perfil_y_sub("5552")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/admin/automation/acciones/generar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                json={"telefono": "5552"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["oportunidades_evaluadas"] >= 4
        assert len(data["acciones"]) >= 4
        # Cada acción debe tener campos esperados
        for a in data["acciones"]:
            assert "id" in a
            assert "estado" in a
            assert "riesgo" in a
            assert a["estado"] in ("pending", "needs_approval")

    @pytest.mark.asyncio
    async def test_telefono_requerido(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/admin/automation/acciones/generar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                json={},
            )
        assert r.status_code == 400


class TestAdminListarAcciones:
    @pytest.mark.asyncio
    async def test_lista_filtrada_por_estado(self, app):
        await _seed_perfil_y_sub("5553")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post(
                "/admin/automation/acciones/generar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                json={"telefono": "5553"},
            )
            r = await c.get(
                "/admin/automation/acciones?telefono=5553&estado=needs_approval",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        assert r.status_code == 200
        data = r.json()
        for a in data["acciones"]:
            assert a["estado"] == "needs_approval"


class TestAdminAprobarRechazar:
    @pytest.mark.asyncio
    async def test_aprobar_cambia_estado(self, app):
        await _seed_perfil_y_sub("5554")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            gen = await c.post(
                "/admin/automation/acciones/generar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                json={"telefono": "5554"},
            )
            # Buscar una needs_approval
            acciones = gen.json()["acciones"]
            medium = next(
                (a for a in acciones if a["estado"] == "needs_approval"),
                None,
            )
            assert medium is not None, "Debe haber al menos una MEDIUM/HIGH"
            r = await c.post(
                f"/admin/automation/acciones/{medium['id']}/aprobar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        assert r.status_code == 200
        assert r.json()["accion"]["estado"] == "approved"

    @pytest.mark.asyncio
    async def test_rechazar_cambia_estado(self, app):
        await _seed_perfil_y_sub("5555")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            gen = await c.post(
                "/admin/automation/acciones/generar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                json={"telefono": "5555"},
            )
            acciones = gen.json()["acciones"]
            medium = next(
                (a for a in acciones if a["estado"] == "needs_approval"),
                None,
            )
            r = await c.post(
                f"/admin/automation/acciones/{medium['id']}/rechazar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        assert r.status_code == 200
        assert r.json()["accion"]["estado"] == "rejected"

    @pytest.mark.asyncio
    async def test_aprobar_inexistente_404(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/admin/automation/acciones/9999999/aprobar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        assert r.status_code == 404


class TestAdminEjecutar:
    @pytest.mark.asyncio
    async def test_ejecutar_low_pending_devuelve_completed(self, app):
        await _seed_perfil_y_sub("5556")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            gen = await c.post(
                "/admin/automation/acciones/generar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                json={"telefono": "5556"},
            )
            acciones = gen.json()["acciones"]
            low = next(
                (a for a in acciones if a["estado"] == "pending" and a["riesgo"] == "low"),
                None,
            )
            assert low is not None
            r = await c.post(
                f"/admin/automation/acciones/{low['id']}/ejecutar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["ejecucion"]["estado_final"] == "completed"
        assert body["accion"]["estado"] == "completed"

    @pytest.mark.asyncio
    async def test_ejecutar_high_aprobada_bloqueado_por_endpoint_generico(self, app):
        """El endpoint genérico del dashboard no debe disparar acciones HIGH.

        T2.2 tiene un ejecutor HIGH real para enviar WhatsApp, pero hasta que
        exista UX de confirmación dedicada no debe quedar expuesto por el botón
        genérico /acciones/{id}/ejecutar.
        """
        await _seed_perfil_y_sub("5557")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            gen = await c.post(
                "/admin/automation/acciones/generar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                json={"telefono": "5557"},
            )
            high = next(
                (a for a in gen.json()["acciones"] if a["riesgo"] == "high"),
                None,
            )
            assert high is not None
            aprobar = await c.post(
                f"/admin/automation/acciones/{high['id']}/aprobar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
            assert aprobar.status_code == 200
            assert aprobar.json()["accion"]["estado"] == "approved"

            r = await c.post(
                f"/admin/automation/acciones/{high['id']}/ejecutar",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
            listado = await c.get(
                "/admin/automation/acciones?telefono=5557",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )

        assert r.status_code == 409
        assert r.json()["detail"] == "high_requires_dedicated_confirmation"
        accion = next(a for a in listado.json()["acciones"] if a["id"] == high["id"])
        assert accion["estado"] == "approved"


# ─── /internal/automation/* ──────────────────────────────────────────────────


class TestInternalAuth:
    @pytest.mark.asyncio
    async def test_sin_firma_401(self, app):
        body = json.dumps({"subscription_id": "sub_test1"})
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/internal/automation/oportunidades",
                content=body,
                headers={"Content-Type": "application/json"},
            )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_firma_invalida_401(self, app):
        body = json.dumps({"subscription_id": "sub_test1"})
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/internal/automation/oportunidades",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": "0" * 64,
                },
            )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_firma_valida_y_sub_existe_200(self, app):
        await _seed_perfil_y_sub("5560", "sub_test1")
        body = json.dumps({"subscription_id": "sub_test1"})
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/internal/automation/oportunidades",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
        assert r.status_code == 200
        assert r.json()["count"] >= 4

    @pytest.mark.asyncio
    async def test_subscription_no_existe_404(self, app):
        body = json.dumps({"subscription_id": "sub_inexistente"})
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/internal/automation/oportunidades",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
        assert r.status_code == 404


class TestInternalGenerarAprobar:
    @pytest.mark.asyncio
    async def test_flow_completo_internal(self, app):
        await _seed_perfil_y_sub("5570", "sub_internal")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            # 1. Generar
            body = json.dumps({"subscription_id": "sub_internal"})
            r = await c.post(
                "/internal/automation/acciones/generar",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
            assert r.status_code == 200
            acciones = r.json()["acciones"]
            assert len(acciones) >= 4
            # 2. Listar
            r2 = await c.post(
                "/internal/automation/acciones",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
            assert r2.status_code == 200
            assert r2.json()["count"] >= len(acciones)
            # 3. Aprobar uno medium
            medium = next(
                (a for a in acciones if a["estado"] == "needs_approval"),
                None,
            )
            assert medium is not None
            body3 = json.dumps({
                "subscription_id": "sub_internal",
                "accion_id": medium["id"],
            })
            r3 = await c.post(
                "/internal/automation/acciones/aprobar",
                content=body3,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body3),
                },
            )
            assert r3.status_code == 200
            assert r3.json()["accion"]["estado"] == "approved"


class TestInternalEjecutarGuardrails:
    @pytest.mark.asyncio
    async def test_internal_ejecutar_high_aprobada_bloqueado_por_endpoint_generico(self, app):
        """El bridge del dashboard tampoco debe exponer ejecución HIGH real."""
        await _seed_perfil_y_sub("5571", "sub_high_block")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            body_gen = json.dumps({"subscription_id": "sub_high_block"})
            gen = await c.post(
                "/internal/automation/acciones/generar",
                content=body_gen,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body_gen),
                },
            )
            assert gen.status_code == 200
            high = next(
                (a for a in gen.json()["acciones"] if a["riesgo"] == "high"),
                None,
            )
            assert high is not None

            body_aprobar = json.dumps({
                "subscription_id": "sub_high_block",
                "accion_id": high["id"],
            })
            aprobar = await c.post(
                "/internal/automation/acciones/aprobar",
                content=body_aprobar,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body_aprobar),
                },
            )
            assert aprobar.status_code == 200
            assert aprobar.json()["accion"]["estado"] == "approved"

            body_exec = json.dumps({
                "subscription_id": "sub_high_block",
                "accion_id": high["id"],
            })
            r = await c.post(
                "/internal/automation/acciones/ejecutar",
                content=body_exec,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body_exec),
                },
            )
            listado = await c.post(
                "/internal/automation/acciones",
                content=body_gen,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body_gen),
                },
            )

        assert r.status_code == 409
        assert r.json()["detail"] == "high_requires_dedicated_confirmation"
        accion = next(a for a in listado.json()["acciones"] if a["id"] == high["id"])
        assert accion["estado"] == "approved"


class TestInternalConfirmacionDedicadaHigh:
    @pytest.mark.asyncio
    async def test_preview_high_dedicado_expone_preview_solo_si_pertenece_y_aprobada(self, app):
        await _seed_perfil_y_sub("5572", "sub_high_preview")
        from agent.automation.executors import send_message as sm
        from agent.automation import action_center as ac

        accion = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5572",
            numero_destino="+5215551234567",
            mensaje="Hola Ana, confirmo tu pedido.",
        )
        await ac.aprobar_accion(accion["id"])
        body = json.dumps({
            "subscription_id": "sub_high_preview",
            "accion_id": accion["id"],
        })

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/internal/automation/acciones/high-preview",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )

        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["accion_id"] == accion["id"]
        assert data["riesgo"] == "high"
        assert data["destino_short"] == "+5****4567"
        assert data["numero_destino"] == "+5215551234567"
        assert data["mensaje_preview"] == "Hola Ana, confirmo tu pedido."
        assert data["confirmacion_requerida"] == "ENVIAR"

    @pytest.mark.asyncio
    async def test_confirmar_high_dedicado_rechaza_enviar_con_espacios(self, app, monkeypatch):
        await _seed_perfil_y_sub("5573", "sub_high_spaces")
        from agent.automation.executors import send_message as sm
        from agent.automation import action_center as ac
        from agent import billing as bi

        class FakeProveedor:
            invocaciones: list[tuple[str, str]] = []
            async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
                self.invocaciones.append((telefono, mensaje))
                return True

        fake = FakeProveedor()
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)
        await bi.acreditar("5573", 50, "seed")
        accion = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5573",
            numero_destino="+5215551234567",
            mensaje="hola",
        )
        await ac.aprobar_accion(accion["id"])
        body = json.dumps({
            "subscription_id": "sub_high_spaces",
            "accion_id": accion["id"],
            "confirmacion": " ENVIAR ",
        })

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/internal/automation/acciones/high-confirmar",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )

        assert r.status_code == 400
        assert r.json()["detail"] == "confirmacion_invalida"
        assert fake.invocaciones == []

    @pytest.mark.asyncio
    async def test_confirmar_high_dedicado_no_reenvia_si_segunda_confirmacion(self, app, monkeypatch):
        await _seed_perfil_y_sub("5574", "sub_high_twice")
        from agent.automation.executors import send_message as sm
        from agent.automation import action_center as ac
        from agent import billing as bi

        class FakeProveedor:
            def __init__(self):
                self.invocaciones: list[tuple[str, str]] = []
            async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
                self.invocaciones.append((telefono, mensaje))
                return True

        fake = FakeProveedor()
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)
        await bi.acreditar("5574", 50, "seed")
        accion = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5574",
            numero_destino="+5215551234567",
            mensaje="hola",
        )
        await ac.aprobar_accion(accion["id"])
        body = json.dumps({
            "subscription_id": "sub_high_twice",
            "accion_id": accion["id"],
            "confirmacion": "ENVIAR",
        })
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Signature": _hmac_sig(body),
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r1 = await c.post(
                "/internal/automation/acciones/high-confirmar",
                content=body,
                headers=headers,
            )
            r2 = await c.post(
                "/internal/automation/acciones/high-confirmar",
                content=body,
                headers=headers,
            )

        assert r1.status_code == 200
        assert r1.json()["ejecucion"]["estado_final"] == "completed"
        assert r2.status_code == 409
        assert r2.json()["detail"] == "accion_no_aprobada"
        assert len(fake.invocaciones) == 1


class TestInternalIDOR:
    @pytest.mark.asyncio
    async def test_aprobar_accion_de_otro_usuario_404(self, app):
        """Si alguien firma correctamente con otro subscription_id pero
        intenta aprobar una accion_id que NO le pertenece, debe 404."""
        await _seed_perfil_y_sub("5580", "sub_a")
        await _seed_perfil_y_sub("5581", "sub_b")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            # Generar acciones para sub_a
            body = json.dumps({"subscription_id": "sub_a"})
            gen = await c.post(
                "/internal/automation/acciones/generar",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
            accion_id_a = gen.json()["acciones"][0]["id"]
            # Intentar aprobarla con sub_b (otro usuario)
            body2 = json.dumps({
                "subscription_id": "sub_b",
                "accion_id": accion_id_a,
            })
            r = await c.post(
                "/internal/automation/acciones/aprobar",
                content=body2,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body2),
                },
            )
        assert r.status_code == 404


class TestRespuestasNoExponenSensibles:
    @pytest.mark.asyncio
    async def test_no_expone_idempotency_key_ni_telefono(self, app):
        """idempotency_key es interno · telefono completo no debe ir."""
        await _seed_perfil_y_sub("5215559999999", "sub_priv")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            body = json.dumps({"subscription_id": "sub_priv"})
            await c.post(
                "/internal/automation/acciones/generar",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
            r = await c.post(
                "/internal/automation/acciones",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
        body_text = r.text
        # Telefono completo NO en respuesta
        assert "5215559999999" not in body_text
        # idempotency_key NO en respuesta
        assert "idempotency_key" not in body_text
        # payload_json crudo NO se expone (los ejecutores T2.1.A no
        # generan payloads sensibles, pero el filtro lo descarta igual)
        assert "payload_json" not in body_text


class TestPerfilEstadoEnEndpoints:
    """Hotfix action-center-perfil-insuficiente: los endpoints incluyen
    perfil_estado para que el dashboard explique al usuario por qué no
    se generaron acciones."""

    @pytest.mark.asyncio
    async def test_admin_oportunidades_sin_perfil_reporta_missing(self, app):
        await _seed_perfil_y_sub("5810", "sub_p1")
        # _seed crea perfil COMPLETO; necesitamos uno sin perfil ·
        # creamos solo la sub:
        from agent.memory import async_session, SuscripcionStripe
        from datetime import datetime
        async with async_session() as session:
            session.add(SuscripcionStripe(
                subscription_id="sub_p2", telefono="5811",
                plan_codigo="premium", price_id="price_test",
                status="active", customer_id="cus_p2",
                creditos_mensuales=200,
                creado=datetime.utcnow(), actualizado=datetime.utcnow(),
                bienvenida_enviada=True,
            ))
            await session.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                "/admin/automation/oportunidades?telefono=5811",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        data = r.json()
        assert r.status_code == 200
        assert data["perfil_estado"] == "missing"
        assert data["oportunidades"] == []
        assert data["perfil_siguiente_paso"]

    @pytest.mark.asyncio
    async def test_admin_oportunidades_perfil_completo_es_ready(self, app):
        await _seed_perfil_y_sub("5820", "sub_p3")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                "/admin/automation/oportunidades?telefono=5820",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            )
        data = r.json()
        assert data["perfil_estado"] == "ready"
        assert data["count"] >= 4

    @pytest.mark.asyncio
    async def test_internal_generar_sin_perfil_devuelve_perfil_estado(self, app):
        from agent.memory import async_session, SuscripcionStripe
        from datetime import datetime
        async with async_session() as session:
            session.add(SuscripcionStripe(
                subscription_id="sub_p4", telefono="5830",
                plan_codigo="premium", price_id="price_test",
                status="active", customer_id="cus_p4",
                creditos_mensuales=200,
                creado=datetime.utcnow(), actualizado=datetime.utcnow(),
                bienvenida_enviada=True,
            ))
            await session.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            body = json.dumps({"subscription_id": "sub_p4"})
            r = await c.post(
                "/internal/automation/acciones/generar",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
        data = r.json()
        assert r.status_code == 200
        assert data["acciones"] == []
        assert data["perfil_estado"] == "missing"
        assert data["perfil_siguiente_paso"]


class TestEjecutarCriticalBloqueado:
    @pytest.mark.asyncio
    async def test_critical_aun_aprobado_falla(self, app):
        """Una acción CRITICAL creada manualmente y aprobada · al ejecutar
        debe ser bloqueada por execution.ejecutar_accion."""
        await _seed_perfil_y_sub("5599", "sub_c")
        from agent.automation.action_center import crear_accion, aprobar_accion
        a = await crear_accion(
            telefono="5599",
            tipo_accion="envio_masivo_clientes",
            titulo="Mass send",
        )
        await aprobar_accion(a["id"])
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            body = json.dumps({
                "subscription_id": "sub_c",
                "accion_id": a["id"],
            })
            r = await c.post(
                "/internal/automation/acciones/ejecutar",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Signature": _hmac_sig(body),
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["ejecucion"]["estado_final"] == "failed"
        assert body["accion"]["estado"] == "failed"
