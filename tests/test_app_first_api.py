# tests/test_app_first_api.py — J7.4 · API interna /internal/app/*
#
# Puerta del piloto, firma HMAC, registro solo por invitación, login con
# lockout, flujo completo por la API (runner invocado a mano) y aislamiento entre
# usuarios. Sin red: proveedor simulado.

import asyncio
import hashlib
import hmac
import importlib
import json
import sys

import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret-app-first-bridge"


def _firmar(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
async def api(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET)
    monkeypatch.setenv("DONA_APP_PILOTO_ENABLED", "true")
    monkeypatch.setenv("DONA_APP_INVITADOS", "ana@example.com, beto@example.com")
    # Worker apagado: el test ejecuta el runner a mano (el TestClient sin
    # contexto cierra su event loop tras cada petición; el despacho inproc ya
    # se prueba en tests/test_app_first_ejecucion.py).
    monkeypatch.delenv("DONA_WORKER_ENABLED", raising=False)
    import agent.memory

    importlib.reload(agent.memory)
    for nombre in (
        "agent.dashboard_lockout",
        "agent.app_first.models",
        "agent.app_first.repositorio",
        "agent.app_first.proveedores",
        "agent.app_first.ejecucion",
    ):
        if nombre in sys.modules:
            importlib.reload(sys.modules[nombre])
        else:
            importlib.import_module(nombre)
    await agent.memory.inicializar_db()
    from agent.main import app

    cliente = TestClient(app)

    def llamar(accion: str, payload: dict, firma: str | None = None):
        body = json.dumps(payload).encode()
        return cliente.post(
            f"/internal/app/{accion}",
            content=body,
            headers={"X-Internal-Signature": firma if firma is not None else _firmar(body)},
        )

    return llamar


def _registrar(api, email="ana@example.com"):
    res = api("auth.registro", {"email": email, "password": "contraseña-larga-1", "nombre": "Ana"})
    assert res.status_code == 200, res.text
    return res.json()


async def _esperar_estado(api, base, tarea_id, estados, intentos=60):
    for _ in range(intentos):
        tarea = api("tarea", {**base, "tarea_id": tarea_id}).json()["tarea"]
        if tarea["estado"] in estados:
            return tarea
        await asyncio.sleep(0.05)
    raise AssertionError(f"la tarea no llegó a {estados}: {tarea['estado']}")


class TestPuertas:
    def test_piloto_apagado_es_404_aunque_la_firma_sea_valida(self, api, monkeypatch):
        monkeypatch.delenv("DONA_APP_PILOTO_ENABLED")
        res = api("workspaces", {"usuario_id": 1})
        assert res.status_code == 404
        assert res.json() == {"error": "not_found"}

    def test_firma_ausente_o_invalida_es_401(self, api):
        assert api("workspaces", {"usuario_id": 1}, firma="").status_code == 401
        assert api("workspaces", {"usuario_id": 1}, firma="00" * 32).status_code == 401

    def test_accion_desconocida_es_404(self, api):
        assert api("borrar.todo", {}).status_code == 404

    def test_ruta_plana_en_app_routes(self, api):
        # Todas las rutas deben tener .path: test_smoke_e2e y otros las recorren.
        from agent.main import app

        assert all(hasattr(r, "path") for r in app.routes)
        assert "/internal/app/{accion}" in {r.path for r in app.routes}

    def test_tipos_invalidos_son_400(self, api):
        assert api("workspaces", {"usuario_id": "1"}).status_code == 400
        assert api("workspaces", {"usuario_id": True}).status_code == 400


class TestAcceso:
    def test_registro_solo_por_invitacion(self, api):
        res = api("auth.registro", {"email": "intruso@example.com", "password": "contraseña-larga-1"})
        assert res.status_code == 403
        assert res.json() == {"error": "registro_solo_por_invitacion"}

    def test_registro_crea_workspace_area_y_dos_agentes(self, api):
        r = _registrar(api)
        base = {"usuario_id": r["usuario_id"], "workspace_id": r["workspace_id"]}
        inicio = api("inicio", base).json()
        assert [a["nombre"] for a in inicio["areas"]] == ["General"]
        agentes = api("agentes", base).json()["agentes"]
        assert sorted(a["rol"] for a in agentes) == ["ejecutor", "responsable"]
        assert all(a["modelo"] == "simulado" for a in agentes)

    def test_registro_duplicado_es_409(self, api):
        _registrar(api)
        res = api("auth.registro", {"email": "ana@example.com", "password": "contraseña-larga-2"})
        assert res.status_code == 409

    def test_login_y_lockout(self, api):
        r = _registrar(api)
        ok = api("auth.verificar", {"email": "ANA@example.com", "password": "contraseña-larga-1"})
        assert ok.status_code == 200
        assert ok.json()["usuario_id"] == r["usuario_id"]
        assert [w["rol"] for w in ok.json()["workspaces"]] == ["owner"]
        for _ in range(10):
            assert api("auth.verificar", {"email": "ana@example.com", "password": "mala-mala-mala"}).status_code == 401
        bloqueado = api("auth.verificar", {"email": "ana@example.com", "password": "contraseña-larga-1"})
        assert bloqueado.status_code == 429


class TestFlujo:
    async def test_proyecto_tarea_aprobacion_y_evidencia_por_la_api(self, api):
        r = _registrar(api)
        base = {"usuario_id": r["usuario_id"], "workspace_id": r["workspace_id"]}
        proyecto = api("proyecto.crear", {**base, "area_id": r["area_id"], "nombre": "Lanzamiento",
                                          "objetivo": "Vender más", "criterios_aceptacion": ["Propuesta lista"]})
        assert proyecto.status_code == 200, proyecto.text
        pid = proyecto.json()["id"]
        ejecutor = next(a for a in api("agentes", base).json()["agentes"] if a["rol"] == "ejecutor")
        tarea = api("tarea.crear", {**base, "proyecto_id": pid, "titulo": "Publicar la propuesta",
                                    "agente_id": ejecutor["id"]}).json()["id"]
        assert api("mensaje.crear", {**base, "proyecto_id": pid, "tarea_id": tarea,
                                     "contenido": "Hazlo breve"}).status_code == 200

        ejecutar = api("tarea.ejecutar", {**base, "tarea_id": tarea})
        assert ejecutar.status_code == 200
        run = sys.modules["agent.app_first.ejecucion"]
        assert await run.ejecutar(ejecutar.json()["ejecucion_id"]) == "necesita_aprobacion"
        await _esperar_estado(api, base, tarea, {"necesita_aprobacion"})
        pendiente = api("inicio", base).json()["aprobaciones_pendientes"]
        assert len(pendiente) == 1 and pendiente[0]["preview"]["simulado"] is True

        decision = api("aprobacion.decidir", {**base, "aprobacion_id": pendiente[0]["id"], "aprobar": True})
        assert decision.json() == {"estado": "aprobada"}
        assert await run.ejecutar(ejecutar.json()["ejecucion_id"]) == "completada"
        final = await _esperar_estado(api, base, tarea, {"completada"})
        assert final["estado"] == "completada"
        detalle = api("tarea", {**base, "tarea_id": tarea}).json()
        assert {e["tipo"] for e in detalle["evidencias"]} >= {"texto", "registro"}
        assert api("proyecto", {**base, "proyecto_id": pid}).json()["mensajes"][0]["contenido"] == "Hazlo breve"

    def test_aprobar_debe_ser_booleano(self, api):
        r = _registrar(api)
        base = {"usuario_id": r["usuario_id"], "workspace_id": r["workspace_id"]}
        assert api("aprobacion.decidir", {**base, "aprobacion_id": 1, "aprobar": "sí"}).status_code == 400


class TestAislamiento:
    def test_otro_usuario_no_entra_al_workspace_ni_a_sus_objetos(self, api):
        a = _registrar(api, "ana@example.com")
        b = _registrar(api, "beto@example.com")
        base_a = {"usuario_id": a["usuario_id"], "workspace_id": a["workspace_id"]}
        pid = api("proyecto.crear", {**base_a, "area_id": a["area_id"], "nombre": "Privado",
                                     "objetivo": "x", "criterios_aceptacion": ["c"]}).json()["id"]
        # Beto con el workspace de Ana → 404.
        assert api("inicio", {"usuario_id": b["usuario_id"], "workspace_id": a["workspace_id"]}).status_code == 404
        # Beto en su workspace pidiendo el proyecto de Ana → 404.
        base_b = {"usuario_id": b["usuario_id"], "workspace_id": b["workspace_id"]}
        res = api("proyecto", {**base_b, "proyecto_id": pid})
        assert res.status_code == 404
        assert "Privado" not in res.text
