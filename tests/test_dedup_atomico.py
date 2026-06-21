# tests/test_dedup_atomico.py — Fase 0 · 1.1 · dedup atómico de mensajes

"""
REGRESIÓN C9 (audit Fable 5 2026-06-09): `_mensaje_ya_procesado` hacía
SELECT-then-INSERT no atómico. Dos webhooks concurrentes con el mismo
`mensaje_id` pasaban ambos el SELECT y se procesaban DOS veces (doble LLM,
doble cobro, doble acción); además una violación de unicidad caía en un
`except` genérico a DEBUG que devolvía False (= procesar).

Fix: INSERT ... ON CONFLICT DO NOTHING + rowcount (1=nuevo→False, 0=dup→True).
Estos tests fijan: dedup persistente en DB (no solo memoria), y —el corazón de
C9— que bajo concurrencia EXACTAMENTE UNO procesa.
"""

import asyncio
import importlib

import pytest

import agent.memory


@pytest.fixture
async def main(tmp_path, monkeypatch):
    db_path = tmp_path / "dedup.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _bm
    import agent.automation.models as _am
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    await agent.memory.inicializar_db()

    import agent.main as _main
    # El cache in-memory per-worker es estado de módulo: limpiarlo entre tests.
    _main._mensajes_procesados_mem.clear()
    return _main


@pytest.mark.asyncio
async def test_primera_vez_nuevo_segunda_vez_duplicado(main):
    assert await main._mensaje_ya_procesado("wamid.1", "5551234567") is False
    assert await main._mensaje_ya_procesado("wamid.1", "5551234567") is True


@pytest.mark.asyncio
async def test_dedup_persiste_en_db_no_solo_memoria(main):
    """Tras registrar y limpiar el cache in-memory, el segundo intento sigue
    siendo duplicado → la dedup la garantiza la DB, no solo la memoria."""
    assert await main._mensaje_ya_procesado("wamid.2", "5551234567") is False
    main._mensajes_procesados_mem.clear()
    assert await main._mensaje_ya_procesado("wamid.2", "5551234567") is True


@pytest.mark.asyncio
async def test_sin_mensaje_id_no_deduplica(main):
    assert await main._mensaje_ya_procesado("", "5551234567") is False


@pytest.mark.asyncio
async def test_ids_distintos_son_independientes(main):
    assert await main._mensaje_ya_procesado("wamid.a", "5551234567") is False
    assert await main._mensaje_ya_procesado("wamid.b", "5551234567") is False


@pytest.mark.asyncio
async def test_db_caida_degrada_a_memoria_best_effort(main, monkeypatch, caplog):
    """Review Hermes: documenta el comportamiento best-effort ante fallo REAL de
    DB. Degrada al dedup in-memory per-worker con WARNING (antes era DEBUG
    invisible + return False silencioso). NO es garantía cross-worker — eso es
    un follow-up fail-closed."""
    import logging
    import agent.memory

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(agent.memory, "async_session", _boom)
    main._mensajes_procesados_mem.clear()

    fallos_antes = main.metricas.snapshot()["dedup_db_fallos"]
    with caplog.at_level(logging.WARNING, logger="dona"):
        r1 = await main._mensaje_ya_procesado("wamid.dberr", "5551234567")
    assert r1 is False  # degrada: trata como nuevo (best-effort), procesa
    assert any("DEDUP" in rec.message for rec in caplog.records), "debe loguear WARNING"
    # 1.1: el fallo de DB del dedup queda registrado como métrica observable.
    assert main.metricas.snapshot()["dedup_db_fallos"] == fallos_antes + 1
    # En el MISMO worker, la memoria sí bloquea el duplicado inmediato.
    assert await main._mensaje_ya_procesado("wamid.dberr", "5551234567") is True


@pytest.mark.asyncio
async def test_concurrencia_exactamente_uno_procesa(main):
    """CORAZÓN DE C9: N reentregas concurrentes del MISMO mensaje_id → solo UNA
    debe verse como nueva (False); el resto, duplicado (True). Con el código
    viejo (SELECT-then-INSERT) varias pasaban el SELECT y devolvían False
    (procesar) → doble cobro/acción. El INSERT ON CONFLICT lo serializa por PK."""
    main._mensajes_procesados_mem.clear()
    resultados = await asyncio.gather(
        *[main._mensaje_ya_procesado("wamid.race", "5551234567") for _ in range(8)]
    )
    assert resultados.count(False) == 1, f"esperaba exactamente 1 nuevo, fue {resultados}"
    assert resultados.count(True) == 7
