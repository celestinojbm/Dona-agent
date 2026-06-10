# tests/test_tcpa_stop_durable.py — Fase 0 · 2.2 · STOP durable (TCPA)

"""
REGRESIÓN C3 (audit Fable 5 2026-06-09): el opt-out TCPA se persistía con un
solo write sin retry, y si fallaba el caller confirmaba "dado de baja" IGUAL
(fail-open). Resultado: el usuario cree que se dio de baja y Dona le sigue
escribiendo → exposición legal directa ($500-1500/mensaje).

Fix 2.2: persistencia con retry (durable ante fallo transitorio); si falla tras
reintentos → CRITICAL + TCPAOptOutError (no se confirma una baja inexistente).
"""

import logging
from unittest.mock import AsyncMock

import pytest

import agent.proactivity as prox
from agent.proactivity import (
    manejar_stop_tcpa,
    TCPAOptOutError,
    _persistir_proactividad_con_retry,
)


@pytest.fixture(autouse=True)
def _sin_backoff(monkeypatch):
    """Anula el sleep del backoff para que los tests sean rápidos."""
    async def _fast(_segundos):
        return None
    monkeypatch.setattr(prox.asyncio, "sleep", _fast)


@pytest.mark.asyncio
async def test_stop_persiste_y_confirma(monkeypatch):
    llamadas = []

    async def _ok(telefono, **kw):
        llamadas.append((telefono, kw))

    monkeypatch.setattr("agent.memory.guardar_proactividad", _ok)
    msg = await manejar_stop_tcpa("5551234567")
    assert llamadas == [("5551234567", {"proactive_enabled": False})]
    assert "baja" in msg.lower()


@pytest.mark.asyncio
async def test_stop_reintenta_ante_fallo_transitorio(monkeypatch):
    """Falla 2 veces, persiste a la 3ª → el opt-out NO se pierde."""
    n = {"i": 0}

    async def _flaky(telefono, **kw):
        n["i"] += 1
        if n["i"] < 3:
            raise RuntimeError("db blip")

    monkeypatch.setattr("agent.memory.guardar_proactividad", _flaky)
    msg = await manejar_stop_tcpa("5551234567")
    assert n["i"] == 3
    assert "baja" in msg.lower()


@pytest.mark.asyncio
async def test_stop_falla_persistente_lanza_y_alerta(monkeypatch, caplog):
    """Fallo persistente tras reintentos → TCPAOptOutError + CRITICAL (no se
    confirma una baja que no se grabó)."""
    async def _always_fail(telefono, **kw):
        raise RuntimeError("db down")

    monkeypatch.setattr("agent.memory.guardar_proactividad", _always_fail)
    with caplog.at_level(logging.CRITICAL, logger="dona"):
        with pytest.raises(TCPAOptOutError):
            await manejar_stop_tcpa("5551234567")
    assert any(
        rec.levelno == logging.CRITICAL and "TCPA" in rec.message
        for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_retry_helper_agota_intentos(monkeypatch):
    n = {"i": 0}

    async def _fail(telefono, **kw):
        n["i"] += 1
        raise RuntimeError("x")

    monkeypatch.setattr("agent.memory.guardar_proactividad", _fail)
    with pytest.raises(TCPAOptOutError):
        await _persistir_proactividad_con_retry(
            "5551234567", proactive_enabled=False, intentos=4
        )
    assert n["i"] == 4


@pytest.mark.asyncio
async def test_caller_no_confirma_baja_en_falso(monkeypatch, caplog):
    """REGRESIÓN del fail-open: ante fallo de persistencia, el caller NO envía el
    'dado de baja' alegre (que mentía), sino un mensaje honesto + CRITICAL."""
    import agent.main as main
    from agent.providers.base import MensajeEntrante

    fake_msg = MensajeEntrante(
        telefono="5551234567", texto="STOP", mensaje_id="x", es_propio=False
    )
    fake_prov = AsyncMock()
    monkeypatch.setattr(main, "proveedor", fake_prov)
    monkeypatch.setattr(
        main, "manejar_stop_tcpa", AsyncMock(side_effect=TCPAOptOutError("db down"))
    )
    crit_calls = []
    monkeypatch.setattr(main.logger, "critical", lambda *a, **k: crit_calls.append(a))

    manejo = await main._procesar_tcpa_optout(fake_msg)

    assert manejo is True
    args, _ = fake_prov.enviar_mensaje.call_args
    enviado = args[1].lower()
    assert "procesando" in enviado          # honesto
    assert "dado de baja" not in enviado    # ya NO confirma una baja falsa
    assert crit_calls, "un STOP no persistido debe escalar a CRITICAL"
