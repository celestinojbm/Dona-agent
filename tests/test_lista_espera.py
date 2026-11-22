# tests/test_lista_espera.py — Lista de espera e invitaciones (issue #334).

"""
Cubre agent/lista_espera y las rutas POST /internal/lista-espera[/invitacion]:

  - Firma HMAC ausente o inválida → 401 (no se toca la base).
  - Alta: correo válido → en_espera; repetido → idempotente (nuevo=False).
  - Correo inválido → 400 email_invalido.
  - Invitación: sin códigos configurados → 403 (fail-closed); código válido
    (sin distinguir mayúsculas) → invitado; un invitado que vuelve a
    apuntarse sigue invitado.
  - Fuerza bruta: tras MAX_INTENTOS fallidos → 429 con Retry-After, aunque
    luego llegue el código bueno.
  - Correos: la bandera de envío está apagada y no se envía nada.
"""

import hashlib
import hmac
import importlib
import json

import pytest
from fastapi.testclient import TestClient

_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:
    _main_disponible = False

pytestmark = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler (no instalado en este entorno)",
)

SECRET_TEST = "test-secret-not-real-lista-espera"
CODIGO = "DONA-PILOTO-2026"


def _firmar(body: bytes, secret: str = SECRET_TEST) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _post(client, ruta: str, firma: str | None = None, **datos):
    body = json.dumps(datos).encode("utf-8")
    return client.post(
        ruta,
        content=body,
        headers={"X-Internal-Signature": firma if firma is not None else _firmar(body)},
    )


@pytest.fixture
async def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'lista.db'}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)
    monkeypatch.setenv("DONA_CODIGOS_INVITACION", f"{CODIGO}, corto")

    import agent.dashboard_lockout as _lock
    import agent.lista_espera.models as _modelos
    import agent.lista_espera.servicio as _servicio
    import agent.memory

    # Recargar memory crea un Base nuevo: re-registrar los modelos en él
    # antes de inicializar_db() para que create_all cree sus tablas.
    importlib.reload(agent.memory)
    importlib.reload(_modelos)
    importlib.reload(_lock)
    importlib.reload(_servicio)
    await agent.memory.inicializar_db()

    from agent.main import app

    return TestClient(app), _servicio, agent.memory


async def _filas(memory, servicio):
    from sqlalchemy import select

    async with memory.async_session() as session:
        return (await session.execute(select(servicio.ListaEspera))).scalars().all()


async def test_firma_invalida_401(setup):
    client, servicio, memory = setup
    r = _post(client, "/internal/lista-espera", firma="00", email="a@b.com")
    assert r.status_code == 401
    r = _post(client, "/internal/lista-espera/invitacion", firma="", email="a@b.com", codigo=CODIGO)
    assert r.status_code == 401
    assert await _filas(memory, servicio) == []


async def test_alta_idempotente(setup):
    client, servicio, memory = setup
    r = _post(client, "/internal/lista-espera", email="  Dueña@Negocio.com ")
    assert r.status_code == 200
    assert r.json() == {"estado": "en_espera", "nuevo": True}
    r = _post(client, "/internal/lista-espera", email="dueña@negocio.com")
    assert r.json() == {"estado": "en_espera", "nuevo": False}
    filas = await _filas(memory, servicio)
    assert [f.email for f in filas] == ["dueña@negocio.com"]


@pytest.mark.parametrize("email", ["", "sin-arroba", "a@b", "a b@c.com", "x" * 250 + "@a.com"])
async def test_email_invalido_400(setup, email):
    client, _, _ = setup
    r = _post(client, "/internal/lista-espera", email=email)
    assert r.status_code == 400
    assert r.json()["detail"] == "email_invalido"


async def test_invitacion_valida_marca_invitado(setup):
    client, servicio, memory = setup
    _post(client, "/internal/lista-espera", email="ana@negocio.com")
    r = _post(client, "/internal/lista-espera/invitacion", email="ana@negocio.com", codigo=CODIGO.lower())
    assert r.status_code == 200
    assert r.json() == {"estado": "invitado"}
    # Volver a apuntarse no degrada el estado.
    r = _post(client, "/internal/lista-espera", email="ana@negocio.com")
    assert r.json() == {"estado": "invitado", "nuevo": False}
    (fila,) = await _filas(memory, servicio)
    assert fila.estado == "invitado" and fila.invitado_en is not None


async def test_codigo_invalido_o_corto_403(setup):
    client, _, _ = setup
    for codigo in ["OTRO-CODIGO-1", "corto", ""]:
        r = _post(client, "/internal/lista-espera/invitacion", email="b@negocio.com", codigo=codigo)
        assert r.status_code == 403, codigo
        assert r.json()["detail"] == "codigo_invalido"


async def test_sin_codigos_configurados_ninguno_vale(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setenv("DONA_CODIGOS_INVITACION", "")
    r = _post(client, "/internal/lista-espera/invitacion", email="c@negocio.com", codigo=CODIGO)
    assert r.status_code == 403


async def test_fuerza_bruta_bloquea_429(setup):
    client, _, _ = setup
    from agent.dashboard_lockout import MAX_INTENTOS

    for _ in range(MAX_INTENTOS):
        _post(client, "/internal/lista-espera/invitacion", email="d@negocio.com", codigo="MALO-MALO-1")
    r = _post(client, "/internal/lista-espera/invitacion", email="d@negocio.com", codigo=CODIGO)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


async def test_no_envia_correos(setup, monkeypatch):
    client, servicio, _ = setup
    assert servicio.LISTA_ESPERA_ENVIO_CORREO_ACTIVO is False
    # La implementación real, apagada, no envía y lo dice.
    assert await servicio._notificar_alta("e@negocio.com", "en_espera") is False

    llamadas = []

    async def _espia(email, estado):
        llamadas.append(estado)
        return False

    monkeypatch.setattr(servicio, "_notificar_alta", _espia)
    _post(client, "/internal/lista-espera", email="e@negocio.com")
    assert llamadas == ["en_espera"]
