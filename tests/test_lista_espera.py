# tests/test_lista_espera.py — Lista de espera e invitaciones (issue #334).

"""
Cubre agent/lista_espera y las rutas POST /internal/lista-espera[/invitacion]:

  - Firma HMAC ausente o inválida → 401 (no se toca la base).
  - Alta: correo válido → en_espera; repetido → idempotente y con la misma
    respuesta (no revela si el correo ya estaba).
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
CODIGO = "7KQ2-M9XW-4HTB-RZ8D"


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
    import agent.lista_espera.limites as _limites
    import agent.lista_espera.models as _modelos
    import agent.lista_espera.servicio as _servicio
    import agent.memory

    # Recargar memory crea un Base nuevo: re-registrar los modelos en él
    # antes de inicializar_db() para que create_all cree sus tablas.
    importlib.reload(agent.memory)
    importlib.reload(_modelos)
    importlib.reload(_limites)
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
    assert r.json() == {"estado": "en_espera"}
    r = _post(client, "/internal/lista-espera", email="dueña@negocio.com")
    assert r.json() == {"estado": "en_espera"}
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
    # Volver a apuntarse no degrada el estado ni lo revela.
    r = _post(client, "/internal/lista-espera", email="ana@negocio.com")
    assert r.json() == {"estado": "en_espera"}
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


# ── Concurrencia: el mismo correo a la vez no puede acabar en 500 ───────────
#
# Antes: SELECT y luego INSERT. En PostgreSQL, dos altas (o canjes) simultáneos
# del mismo correo pasaban ambos el SELECT y el segundo INSERT chocaba con el
# UNIQUE → IntegrityError → 500 ("No pudimos guardar tu correo"). SQLite
# serializa las escrituras y no lo reproduce; el test con PostgreSQL real corre
# solo si DONA_TEST_PG_URL apunta a una base desechable (se vacían las tablas).


async def _altas_y_canjes_concurrentes(servicio, memory):
    import asyncio

    altas = await asyncio.gather(
        *[servicio.registrar("mismo@negocio.com") for _ in range(8)], return_exceptions=True
    )
    canjes = await asyncio.gather(
        *[servicio.canjear_invitacion("otro@negocio.com", CODIGO) for _ in range(8)],
        return_exceptions=True,
    )
    errores = [repr(x) for x in altas + canjes if isinstance(x, BaseException)]
    assert not errores, errores
    assert {a["estado"] for a in altas} == {"en_espera"}
    assert {c["estado"] for c in canjes} == {"invitado"}
    filas = {f.email: f for f in await _filas(memory, servicio)}
    assert set(filas) == {"mismo@negocio.com", "otro@negocio.com"}
    assert filas["otro@negocio.com"].estado == "invitado"
    assert filas["otro@negocio.com"].invitado_en is not None


async def test_concurrencia_mismo_correo_sin_errores(setup):
    _client, servicio, memory = setup
    await _altas_y_canjes_concurrentes(servicio, memory)


async def test_canje_conserva_primer_invitado_en(setup):
    _client, servicio, memory = setup
    await servicio.canjear_invitacion("ana@negocio.com", CODIGO)
    primero = (await _filas(memory, servicio))[0].invitado_en
    await servicio.canjear_invitacion("ana@negocio.com", CODIGO)
    filas = await _filas(memory, servicio)
    assert len(filas) == 1 and filas[0].invitado_en == primero


@pytest.fixture
async def setup_pg(monkeypatch):
    import os

    url = os.getenv("DONA_TEST_PG_URL", "").strip()
    if not url:
        pytest.skip("DONA_TEST_PG_URL no definida (PostgreSQL desechable para concurrencia)")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)
    monkeypatch.setenv("DONA_CODIGOS_INVITACION", CODIGO)

    from sqlalchemy import text

    import agent.dashboard_lockout as _lock
    import agent.lista_espera.limites as _limites
    import agent.lista_espera.models as _modelos
    import agent.lista_espera.servicio as _servicio
    import agent.memory

    importlib.reload(agent.memory)
    importlib.reload(_modelos)
    importlib.reload(_limites)
    importlib.reload(_lock)
    importlib.reload(_servicio)
    await agent.memory.inicializar_db()
    async with agent.memory.engine.begin() as conn:
        await conn.execute(text("DELETE FROM lista_espera"))
        await conn.execute(text("DELETE FROM dashboard_login_intentos"))
        await conn.execute(text("DELETE FROM lista_espera_limite"))
    yield _servicio, agent.memory
    await agent.memory.engine.dispose()


async def test_concurrencia_mismo_correo_postgres(setup_pg):
    servicio, memory = setup_pg
    await _altas_y_canjes_concurrentes(servicio, memory)


async def test_limite_por_ip_concurrente_postgres(setup_pg):
    """El UPSERT del contador es atómico: con N canjes simultáneos desde una IP
    pasan exactamente CANJE_POR_IP (correos distintos: el bloqueo por correo
    no interviene)."""
    import asyncio

    from agent.lista_espera import limites

    servicio, _memory = setup_pg
    total = limites.CANJE_POR_IP + 5
    res = await asyncio.gather(
        *[
            servicio.canjear_invitacion(f"c{i}@negocio.com", "MALO-MALO-1", ip="203.0.113.7")
            for i in range(total)
        ],
        return_exceptions=True,
    )
    tipos = [type(r).__name__ for r in res]
    assert tipos.count("CodigoInvalido") == limites.CANJE_POR_IP, tipos
    assert tipos.count("DemasiadosIntentos") == 5, tipos
