# tests/test_lista_espera_codigos.py — Entropía mínima de códigos de invitación (issue #334).

"""
Cubre agent/lista_espera/codigos.py y su uso en servicio.codigo_valido:

  - El generador produce 16 símbolos Crockford base32 (80 bits), agrupados,
    distintos entre sí, y que pasan el propio filtro.
  - Códigos débiles configurados (DONA2026, cortos, patrones humanos) se
    ignoran: no valen nunca y se avisa en el log sin revelar el código.
  - Normalización: mayúsculas, guiones/espacios y O→0, I/L→1.
  - Un candidato mal formado no vale aunque coincida con algo configurado.
"""

import logging
import math

import pytest

from agent.lista_espera import codigos

FUERTE = "7KQ2-M9XW-4HTB-RZ8D"


@pytest.fixture(autouse=True)
def _limpiar_cache():
    codigos.cargar.cache_clear()
    yield
    codigos.cargar.cache_clear()


def test_entropia_minima_declarada():
    assert len(codigos.ALFABETO) == 32 == len(set(codigos.ALFABETO))
    assert codigos.ENTROPIA_MINIMA_BITS == codigos.LARGO_CODIGO * math.log2(len(codigos.ALFABETO))
    assert codigos.ENTROPIA_MINIMA_BITS >= 80


def test_generar_formato_y_fuerza():
    vistos = set()
    for _ in range(300):
        c = codigos.generar()
        assert len(c) == 19 and c.count("-") == 3
        n = codigos.normalizar(c)
        assert len(n) == codigos.LARGO_CODIGO
        assert set(n) <= set(codigos.ALFABETO)
        assert codigos.motivo_debil(n) is None
        vistos.add(n)
    assert len(vistos) == 300


@pytest.mark.parametrize(
    "codigo",
    [
        "DONA2026",  # el ejemplo de la #342: 8 símbolos
        "DONA-PILOTO-2026",  # 14 símbolos
        "ABCDEFGH",
        "AAAAAAAAAAAAAAAA",  # pocos símbolos distintos
        "AAAA7KQ2M9XW4HTB",  # racha de 4 iguales
        "0123K7Q2M9XW4HTB",  # secuencia ascendente
        "ZYXWK7Q2M9AB4HTC",  # secuencia descendente
        "K7Q2M9XWK7Q2M9XW",  # bloque repetido: 40 bits reales
        "DONADONADONADONA",
        "7KQ2M9XW4HTBRZ8U",  # U no es Crockford
        "7KQ2M9XW4HTBRZ8!",
        "7KQ2M9XW4HTBRZ8D" * 3,  # más largo que el máximo
        "",
    ],
)
def test_codigos_debiles(codigo):
    assert codigos.motivo_debil(codigos.normalizar(codigo)) is not None


def test_normalizacion_tolera_errores_de_copia():
    base = codigos.normalizar(FUERTE)
    assert codigos.normalizar("7kq2 m9xw 4htb rz8d") == base
    assert codigos.normalizar("7KQ2M9XW4HTBRZ8D") == base
    # O→0, I/L→1
    assert codigos.normalizar("O1IL") == "0111"


def test_cargar_descarta_debiles_y_avisa_sin_revelar(caplog):
    with caplog.at_level(logging.ERROR, logger="dona"):
        validos = codigos.cargar(f" {FUERTE} ,DONA2026,, corto ")
    assert validos == (codigos.normalizar(FUERTE),)
    mensajes = [
        r.getMessage() for r in caplog.records if "DONA_CODIGOS_INVITACION" in r.getMessage()
    ]
    assert len(mensajes) == 2
    assert any("#2" in m for m in mensajes) and any("#4" in m for m in mensajes)
    assert not any("DONA2026" in m or "corto" in m for m in mensajes)


def test_cargar_avisa_una_vez_por_configuracion(caplog):
    with caplog.at_level(logging.ERROR, logger="dona"):
        for _ in range(5):
            codigos.cargar("DONA2026")
    assert len([r for r in caplog.records if "DONA_CODIGOS_INVITACION" in r.getMessage()]) == 1


# ── Integración con servicio.codigo_valido ──────────────────────────────────


@pytest.fixture
def servicio():
    from agent.lista_espera import servicio as _servicio

    return _servicio


def test_codigo_debil_configurado_no_vale(servicio, monkeypatch):
    monkeypatch.setenv("DONA_CODIGOS_INVITACION", "DONA2026,DONA-PILOTO-2026")
    assert servicio.codigo_valido("DONA2026") is False
    assert servicio.codigo_valido("dona-piloto-2026") is False


def test_codigo_fuerte_vale_con_variantes(servicio, monkeypatch):
    monkeypatch.setenv("DONA_CODIGOS_INVITACION", f"DONA2026,{FUERTE}")
    assert servicio.codigo_valido(FUERTE)
    assert servicio.codigo_valido("7kq2m9xw4htbrz8d")
    assert servicio.codigo_valido(" 7KQ2 M9XW 4HTB RZ8D ")
    assert not servicio.codigo_valido("7KQ2-M9XW-4HTB-RZ8E")
    assert not servicio.codigo_valido("7KQ2-M9XW-4HTB")


def test_codigo_generado_es_canjeable(servicio, monkeypatch):
    nuevos = [codigos.generar() for _ in range(3)]
    monkeypatch.setenv("DONA_CODIGOS_INVITACION", ",".join(nuevos))
    assert all(servicio.codigo_valido(c.lower()) for c in nuevos)


def test_sin_codigos_ninguno_vale(servicio, monkeypatch):
    monkeypatch.setenv("DONA_CODIGOS_INVITACION", "")
    assert servicio.codigo_valido(FUERTE) is False
