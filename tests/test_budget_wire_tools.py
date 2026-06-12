# tests/test_budget_wire_tools.py — Fase 0 · 4.1/4.2 · PR 3: gateo de tools

"""
REGRESIÓN C6 (continuación): las ejecuciones de herramientas en
brain._manejar_tool_use no tenían tope — una respuesta con N bloques
tool_use ejecutaba N herramientas, sin límite por mensaje ni respeto al
tiempo global/kill-switch.

PR 3 cablea reservar_tool() del RuntimeBudgetGuard a cada bloque tool_use:
al agotar max_tool_calls (default 8) — o si el tiempo global del mensaje se
agotó / hay kill-switch — la herramienta NO se ejecuta y Claude recibe el
motivo como tool_result para cerrar con lo que ya tiene.

El test del tope FALLA contra el código viejo (ejecutaba los 12 bloques).
"""

from __future__ import annotations

import time

import pytest

import agent.brain as brain
import agent.presupuesto_runtime as pr


TEL = "15550008888"


@pytest.fixture(autouse=True)
def _budget_limpio(monkeypatch):
    pr._contadores_eventos.clear()
    pr._owners_suspendidos.clear()
    pr._costo_diario_owner.clear()
    monkeypatch.delenv("DONA_LLM_COST_KILL_SWITCH", raising=False)
    yield
    pr._contadores_eventos.clear()
    pr._costo_diario_owner.clear()


# ── Fakes ────────────────────────────────────────────────────────────────


class _Usage:
    input_tokens = 10
    output_tokens = 10


class _BlkText:
    type = "text"
    text = "listo"


class _BlkToolTZ:
    """Bloque tool_use de guardar_zona_horaria (la tool más barata: un
    write a memoria, que mockeamos)."""
    type = "tool_use"
    name = "guardar_zona_horaria"

    def __init__(self, i):
        self.id = f"t{i}"
        self.input = {"offset_minutos": -300}


class _RespTools:
    def __init__(self, n):
        self.stop_reason = "tool_use"
        self.content = [_BlkToolTZ(i) for i in range(n)]
        self.usage = _Usage()


class _RespTexto:
    stop_reason = "end_turn"
    content = [_BlkText()]
    usage = _Usage()


@pytest.fixture
def entorno_tools(monkeypatch):
    """Mockea la tool (guardar_timezone) y la llamada LLM siguiente."""
    ejecuciones = []

    async def _fake_tz(telefono, offset_min, *a, **k):
        ejecuciones.append(offset_min)

    # _manejar_tool_use importa guardar_timezone de agent.memory adentro
    import agent.memory as memoria
    monkeypatch.setattr(memoria, "guardar_timezone", _fake_tz)

    async def _fake_create(**kwargs):
        return _RespTexto()

    monkeypatch.setattr(brain.client.messages, "create", _fake_create)
    return ejecuciones


# ── 1. Tope de tools por mensaje (REGRESIÓN núcleo) ──────────────────────


class TestTopeTools:
    async def test_doce_tools_solo_ejecutan_max_tool_calls(self, entorno_tools):
        """REGRESIÓN: contra el código viejo se ejecutaban las 12."""
        with pr.presupuesto_de_mensaje(TEL) as pres:
            resp = await brain._manejar_tool_use(
                _RespTools(12), [], "system", TEL, None
            )

        assert len(entorno_tools) == pres.config.max_tool_calls  # 8, no 12
        assert isinstance(resp, str) and resp

    async def test_bajo_el_tope_ejecuta_todas(self, entorno_tools):
        """Control anti-sobre-bloqueo: 3 tools ≤ tope → las 3 corren."""
        with pr.presupuesto_de_mensaje(TEL):
            await brain._manejar_tool_use(_RespTools(3), [], "system", TEL, None)

        assert len(entorno_tools) == 3

    async def test_tiempo_global_agotado_no_ejecuta_tools(self, entorno_tools):
        """El mismo reservar_tool deniega cuando el presupuesto de tiempo
        del mensaje ya venció — ninguna tool corre."""
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.iniciado = time.monotonic() - (pres.config.hard_segundos + 1)
            resp = await brain._manejar_tool_use(
                _RespTools(3), [], "system", TEL, None
            )

        assert entorno_tools == []
        assert isinstance(resp, str) and resp

    async def test_sin_presupuesto_no_gatea(self, entorno_tools):
        """Paths sin wiring (jobs/scheduler): comportamiento intacto."""
        await brain._manejar_tool_use(_RespTools(3), [], "system", TEL, None)
        assert len(entorno_tools) == 3
