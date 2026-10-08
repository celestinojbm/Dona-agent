# tests/test_demo_app_first.py — J7.6 · demo sintético del piloto app-first.
#
# Corre scripts/demo_app_first.py contra la app real en proceso (TestClient
# como context manager: un solo event loop, así el worker inproc avanza) con
# el proveedor simulado. Sin red.

import importlib
import json
import sys

import pytest
from fastapi.testclient import TestClient

from scripts import demo_app_first as demo

SECRET = "test-secret-demo-app-first"


@pytest.fixture
async def llamar(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'demo.db'}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET)
    monkeypatch.setenv("DONA_APP_PILOTO_ENABLED", "true")
    monkeypatch.setenv("DONA_APP_INVITADOS", "demo@example.com")
    monkeypatch.setenv("DONA_WORKER_ENABLED", "true")
    monkeypatch.delenv("REDIS_URL", raising=False)
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

    with TestClient(app) as cliente:
        def _llamar(accion, payload):
            body = json.dumps(payload).encode()
            res = cliente.post(f"/internal/app/{accion}", content=body,
                               headers={"X-Internal-Signature": demo.firmar(body, SECRET)})
            return res.status_code, res.json()

        yield _llamar


def test_demo_completa_y_es_repetible(llamar):
    lineas: list[str] = []
    resumen = demo.ejecutar_demo(llamar, "demo@example.com", "contraseña-de-demo-1",
                                 espera_max=10, pausa=0.05, log=lineas.append)
    assert resumen["estado"] == "completada"
    assert {e["tipo"] for e in resumen["evidencias"]} >= {"texto", "registro"}
    assert any("espera aprobación humana" in linea for linea in lineas)

    # Segunda corrida con la misma cuenta: entra en vez de registrarse.
    otra = demo.ejecutar_demo(llamar, "demo@example.com", "contraseña-de-demo-1",
                              espera_max=10, pausa=0.05, log=lineas.append)
    assert otra["estado"] == "completada" and otra["tarea_id"] != resumen["tarea_id"]
    assert "1. Cuenta de demo existente: entrada correcta." in lineas


def test_demo_sin_invitacion_explica_el_motivo(llamar):
    with pytest.raises(demo.DemoError, match="DONA_APP_INVITADOS"):
        demo.ejecutar_demo(llamar, "otro@example.com", "contraseña-de-demo-1", log=lambda _: None)


def test_worker_apagado_da_una_pista_clara(llamar, monkeypatch):
    monkeypatch.delenv("DONA_WORKER_ENABLED")
    with pytest.raises(demo.DemoError, match="DONA_WORKER_ENABLED"):
        demo.ejecutar_demo(llamar, "demo@example.com", "contraseña-de-demo-1",
                           espera_max=0.3, pausa=0.05, log=lambda _: None)


class TestMain:
    def test_exige_secreto(self, monkeypatch, capsys):
        monkeypatch.delenv("INTERNAL_BRIDGE_SECRET", raising=False)
        assert demo.main([]) == 2
        assert "INTERNAL_BRIDGE_SECRET" in capsys.readouterr().err

    def test_rechaza_backend_remoto_sin_permiso_explicito(self, monkeypatch, capsys):
        monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET)
        monkeypatch.setenv("BACKEND_URL", "https://backend.example.com")
        assert demo.main([]) == 2
        assert "loopback" in capsys.readouterr().err

    def test_backend_caido_es_error_legible(self, monkeypatch, capsys):
        monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET)
        monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:9")
        monkeypatch.setenv("DONA_DEMO_PASSWORD", "contraseña-de-demo-1")
        assert demo.main([]) == 1
        assert "No se pudo hablar con el backend" in capsys.readouterr().err
