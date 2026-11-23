# tests/test_lista_espera_limites.py — Límites por IP y globales (issue #334).

"""
Cubre agent/lista_espera/limites.py a través de /internal/lista-espera[/invitacion]:

  - Alta y canje: tope por IP → 429 con Retry-After; otra IP sigue pasando.
  - Rotar correos NO esquiva el límite de canje (el lockout por correo sí se
    esquivaba así: era el agujero).
  - Cupo global: con muchas IPs distintas también se corta.
  - Quien ya superó su tope por IP no gasta el cupo global.
  - IPv6 se agrupa por /64; IPv4 mapeada en IPv6 cuenta como la IPv4.
  - Sin IP o IP inválida → cubo compartido "sin-ip" (fail-closed).
  - Un código válido también consume intento (no se revela si vale).
  - La ventana se reinicia y se limpian las filas viejas.
  - No se guarda la IP en claro.
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
ALTA = "/internal/lista-espera"
CANJE = "/internal/lista-espera/invitacion"


def _post(client, ruta: str, **datos):
    body = json.dumps(datos).encode("utf-8")
    firma = hmac.new(SECRET_TEST.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return client.post(ruta, content=body, headers={"X-Internal-Signature": firma})


@pytest.fixture
async def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'limites.db'}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)
    monkeypatch.setenv("DONA_CODIGOS_INVITACION", CODIGO)

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

    from agent.main import app

    return TestClient(app), _limites, _servicio, agent.memory


async def _todas(memory, modelo):
    from sqlalchemy import select

    async with memory.async_session() as session:
        return (await session.execute(select(modelo))).scalars().all()


# ── normalizar_ip ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("203.0.113.7", "203.0.113.7"),
        ("  203.0.113.7 ", "203.0.113.7"),
        ("2001:db8:1:2:aaaa::1", "2001:db8:1:2::/64"),
        ("2001:db8:1:2:ffff:ffff:ffff:ffff", "2001:db8:1:2::/64"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
        ("", "sin-ip"),
        (None, "sin-ip"),
        ("no-es-ip", "sin-ip"),
        ("203.0.113.7, 10.0.0.1", "sin-ip"),
        ("1" * 100, "sin-ip"),
    ],
)
async def test_normalizar_ip(setup, entrada, esperado):
    _, limites, _, _ = setup
    assert limites.normalizar_ip(entrada) == esperado


# ── Alta ────────────────────────────────────────────────────────────────────


async def test_alta_tope_por_ip_429_y_otra_ip_pasa(setup):
    client, limites, servicio, memory = setup
    for i in range(limites.ALTA_POR_IP):
        r = _post(client, ALTA, email=f"u{i}@negocio.com", ip="203.0.113.7")
        assert r.status_code == 200, i
    r = _post(client, ALTA, email="extra@negocio.com", ip="203.0.113.7")
    assert r.status_code == 429
    assert r.json()["detail"] == "demasiados_intentos"
    assert 0 < int(r.headers["Retry-After"]) <= limites.VENTANA_SEGUNDOS
    # El rechazado no se guardó.
    correos = {f.email for f in await _todas(memory, servicio.ListaEspera)}
    assert "extra@negocio.com" not in correos
    assert len(correos) == limites.ALTA_POR_IP

    r = _post(client, ALTA, email="extra@negocio.com", ip="198.51.100.9")
    assert r.status_code == 200


async def test_alta_repetida_tambien_consume(setup):
    """Repetir el mismo correo no es gratis: si no, serviría para sondear estados."""
    client, limites, _, _ = setup
    for _ in range(limites.ALTA_POR_IP):
        assert _post(client, ALTA, email="misma@negocio.com", ip="203.0.113.7").status_code == 200
    assert _post(client, ALTA, email="misma@negocio.com", ip="203.0.113.7").status_code == 429


async def test_alta_email_invalido_no_consume(setup):
    client, limites, _, _ = setup
    for _ in range(limites.ALTA_POR_IP + 5):
        assert _post(client, ALTA, email="sin-arroba", ip="203.0.113.7").status_code == 400
    assert _post(client, ALTA, email="ok@negocio.com", ip="203.0.113.7").status_code == 200


async def test_alta_cupo_global(setup, monkeypatch):
    client, limites, _, _ = setup
    monkeypatch.setitem(limites._LIMITES, "alta", (limites.ALTA_POR_IP, 3))
    for i in range(3):
        r = _post(client, ALTA, email=f"g{i}@negocio.com", ip=f"198.51.100.{i + 1}")
        assert r.status_code == 200, i
    r = _post(client, ALTA, email="g9@negocio.com", ip="198.51.100.200")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


async def test_ip_excedida_no_gasta_cupo_global(setup, monkeypatch):
    client, limites, _, _ = setup
    monkeypatch.setitem(limites._LIMITES, "alta", (2, 3))
    codigos = [
        _post(client, ALTA, email=f"a{i}@negocio.com", ip="203.0.113.7").status_code
        for i in range(6)
    ]
    assert codigos == [200, 200, 429, 429, 429, 429]
    # Quedó 1 del cupo global (3 - 2): otra IP todavía entra.
    assert _post(client, ALTA, email="b@negocio.com", ip="198.51.100.1").status_code == 200
    assert _post(client, ALTA, email="c@negocio.com", ip="198.51.100.2").status_code == 429


async def test_sin_ip_cae_en_cubo_compartido(setup):
    client, limites, _, _ = setup
    for i in range(limites.ALTA_POR_IP):
        ip = ["", "no-es-ip", None][i % 3]
        datos = {"email": f"s{i}@negocio.com"}
        if ip is not None:
            datos["ip"] = ip
        assert _post(client, ALTA, **datos).status_code == 200, i
    assert _post(client, ALTA, email="s-extra@negocio.com").status_code == 429


async def test_ipv6_misma_red_64_comparte_limite(setup):
    client, limites, _, _ = setup
    for i in range(limites.ALTA_POR_IP):
        ip = f"2001:db8:1:2::{i + 1:x}"
        assert _post(client, ALTA, email=f"v{i}@negocio.com", ip=ip).status_code == 200
    assert _post(client, ALTA, email="v-extra@negocio.com", ip="2001:db8:1:2:dead::1").status_code == 429
    # Otro /64 es otro cliente.
    assert _post(client, ALTA, email="v-otro@negocio.com", ip="2001:db8:1:3::1").status_code == 200


# ── Canje ───────────────────────────────────────────────────────────────────


async def test_rotar_correos_no_esquiva_limite_de_canje(setup):
    """El lockout por correo se esquivaba con un correo nuevo por intento."""
    client, limites, _, _ = setup
    from agent.dashboard_lockout import MAX_INTENTOS

    assert limites.CANJE_POR_IP > MAX_INTENTOS  # el test prueba el límite por IP, no el lockout
    for i in range(limites.CANJE_POR_IP):
        r = _post(client, CANJE, email=f"r{i}@negocio.com", codigo=f"ADIVINA-{i:04d}", ip="203.0.113.7")
        assert r.status_code == 403, i
    r = _post(client, CANJE, email="r-nuevo@negocio.com", codigo="ADIVINA-9999", ip="203.0.113.7")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


async def test_codigo_valido_tambien_consume_y_luego_429(setup):
    client, limites, servicio, memory = setup
    for i in range(limites.CANJE_POR_IP):
        r = _post(client, CANJE, email=f"k{i}@negocio.com", codigo=CODIGO, ip="203.0.113.7")
        assert r.status_code == 200, i
    r = _post(client, CANJE, email="k-extra@negocio.com", codigo=CODIGO, ip="203.0.113.7")
    assert r.status_code == 429
    correos = {f.email for f in await _todas(memory, servicio.ListaEspera)}
    assert "k-extra@negocio.com" not in correos


async def test_canje_cupo_global(setup, monkeypatch):
    client, limites, _, _ = setup
    monkeypatch.setitem(limites._LIMITES, "canje", (limites.CANJE_POR_IP, 4))
    for i in range(4):
        r = _post(client, CANJE, email=f"x{i}@negocio.com", codigo="MALO-MALO-1", ip=f"198.51.100.{i + 1}")
        assert r.status_code == 403, i
    # Ni con el código bueno, ni desde una IP nueva.
    r = _post(client, CANJE, email="x9@negocio.com", codigo=CODIGO, ip="198.51.100.99")
    assert r.status_code == 429


async def test_limites_de_alta_y_canje_son_independientes(setup):
    client, limites, _, _ = setup
    for i in range(limites.ALTA_POR_IP):
        _post(client, ALTA, email=f"i{i}@negocio.com", ip="203.0.113.7")
    assert _post(client, ALTA, email="i-extra@negocio.com", ip="203.0.113.7").status_code == 429
    r = _post(client, CANJE, email="i0@negocio.com", codigo=CODIGO, ip="203.0.113.7")
    assert r.status_code == 200


# ── Ventana y privacidad ────────────────────────────────────────────────────


async def test_ventana_se_reinicia_y_limpia_filas_viejas(setup, monkeypatch):
    client, limites, _, memory = setup
    t0 = 1_800_000_000 - (1_800_000_000 % limites.VENTANA_SEGUNDOS) + 10
    monkeypatch.setattr(limites, "_ahora_epoch", lambda: t0)
    for i in range(limites.ALTA_POR_IP):
        _post(client, ALTA, email=f"w{i}@negocio.com", ip="203.0.113.7")
    r = _post(client, ALTA, email="w-extra@negocio.com", ip="203.0.113.7")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) == limites.VENTANA_SEGUNDOS - 10
    viejas = {f.clave for f in await _todas(memory, limites.ListaEsperaLimite)}

    monkeypatch.setattr(limites, "_ahora_epoch", lambda: t0 + limites.VENTANA_SEGUNDOS)
    assert _post(client, ALTA, email="w-extra@negocio.com", ip="203.0.113.7").status_code == 200
    nuevas = {f.clave for f in await _todas(memory, limites.ListaEsperaLimite)}
    assert nuevas and not (nuevas & viejas)


async def test_no_guarda_ip_en_claro(setup):
    client, limites, _, memory = setup
    _post(client, ALTA, email="p@negocio.com", ip="203.0.113.7")
    _post(client, CANJE, email="p@negocio.com", codigo="MALO-MALO-1", ip="2001:db8:1:2::1")
    filas = await _todas(memory, limites.ListaEsperaLimite)
    assert filas
    for f in filas:
        assert "203.0.113" not in f.clave and "2001:db8" not in f.clave
        assert "@" not in f.clave


async def test_sin_secret_en_entorno_estricto_falla_cerrado(setup, monkeypatch):
    _, limites, _, _ = setup
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", "")
    monkeypatch.setattr("agent.entorno.es_entorno_estricto", lambda: True)
    with pytest.raises(RuntimeError):
        limites._clave_opaca("203.0.113.7")
