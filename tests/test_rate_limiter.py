# tests/test_rate_limiter.py — Cobertura del rate limiting por teléfono.
#
# CLAUDE.md §3.5: "Rate limiting por teléfono en rate_limiter.py. No bypassar."
# La auditoría encontró este módulo SIN cobertura. Estos tests ejercitan el path
# in-memory (sin REDIS_URL en CI): límite por usuario, aislamiento entre usuarios,
# reseteo por ventana, tope global y limpieza.

import pytest

import agent.rate_limiter as rl


@pytest.fixture(autouse=True)
def _reset_rate_limit(monkeypatch):
    """Fuerza el path in-memory y limpia el estado antes y después de cada test."""
    monkeypatch.setattr(rl, "_redis", None, raising=False)
    rl.limpiar_rate_limit()
    yield
    rl.limpiar_rate_limit()


def test_permite_hasta_el_maximo_y_bloquea_el_siguiente():
    tel = "+15550001111"
    for i in range(rl._RATE_LIMIT_MAX):
        assert rl.dentro_de_limite(tel) is True, f"la llamada {i + 1} debería pasar"
    # El mensaje N+1 dentro de la ventana se bloquea.
    assert rl.dentro_de_limite(tel) is False


def test_limite_es_por_usuario_no_compartido_entre_usuarios():
    a, b = "+15550000001", "+15550000002"
    for _ in range(rl._RATE_LIMIT_MAX):
        assert rl.dentro_de_limite(a) is True
    assert rl.dentro_de_limite(a) is False  # A bloqueado
    assert rl.dentro_de_limite(b) is True   # B intacto (límite es por teléfono)


def test_la_ventana_se_resetea_al_pasar_el_tiempo(monkeypatch):
    tel = "+15550003333"
    reloj = [1000.0]
    monkeypatch.setattr(rl, "_time", lambda: reloj[0])
    for _ in range(rl._RATE_LIMIT_MAX):
        assert rl.dentro_de_limite(tel) is True
    assert rl.dentro_de_limite(tel) is False
    # Avanzar más allá de la ventana deslizante → vuelve a permitir.
    reloj[0] += rl._RATE_LIMIT_VENTANA + 1
    assert rl.dentro_de_limite(tel) is True


def test_tope_global_bloquea_aunque_sea_otro_usuario(monkeypatch):
    # Bajar el tope global para no iterar 1000 veces.
    monkeypatch.setattr(rl, "_RATE_LIMIT_GLOBAL", 3)
    assert rl.dentro_de_limite("+15550000010") is True
    assert rl.dentro_de_limite("+15550000011") is True
    assert rl.dentro_de_limite("+15550000012") is True
    # El 4º excede el tope GLOBAL aunque sea un teléfono distinto y sin límite propio.
    assert rl.dentro_de_limite("+15550000013") is False


def test_limpiar_rate_limit_resetea_el_estado():
    tel = "+15550004444"
    for _ in range(rl._RATE_LIMIT_MAX):
        rl.dentro_de_limite(tel)
    assert rl.dentro_de_limite(tel) is False
    rl.limpiar_rate_limit()
    assert rl.dentro_de_limite(tel) is True
