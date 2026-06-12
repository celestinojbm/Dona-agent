# tests/test_budget_wire_brain.py — Fase 0 · 4.1/4.2 · PR 2: wiring del guard en brain

"""
REGRESIÓN C6 (audit Fable 5): brain.generar_respuesta podía hacer llamadas
LLM ILIMITADAS — la recursión de tool_use en _manejar_tool_use no tenía tope
de profundidad (un Claude que siga pidiendo tools recursa para siempre).

PR 2 cablea el RuntimeBudgetGuard (#82) a las llamadas LLM reales: cada
client.messages.create reserva una llamada del presupuesto del mensaje, corre
bajo timeout con estado cerrado, y consume el costo. Al agotar el presupuesto
(o con kill-switch), generar_respuesta responde de forma SEGURA en vez de
seguir llamando a la API.

El test del runaway FALLA contra el código viejo (recursa sin fin con un mock
que siempre devuelve tool_use).
"""

from __future__ import annotations

import pytest

import agent.brain as brain
import agent.presupuesto_runtime as pr


TEL = "15550007777"


@pytest.fixture(autouse=True)
def _budget_limpio(monkeypatch):
    pr._contadores_eventos.clear()
    pr._owners_suspendidos.clear()
    pr._costo_diario_owner.clear()
    for v in ("DONA_LLM_COST_KILL_SWITCH", "BUDGET_MAX_LLM_CALLS_MENSAJE"):
        monkeypatch.delenv(v, raising=False)
    yield
    pr._contadores_eventos.clear()
    pr._costo_diario_owner.clear()


# ── Fakes del cliente Anthropic ──────────────────────────────────────────


class _Usage:
    def __init__(self, i=10, o=10):
        self.input_tokens = i
        self.output_tokens = o


class _BlkText:
    type = "text"
    def __init__(self, txt):
        self.text = txt


class _BlkTool:
    type = "tool_use"
    def __init__(self, name="tool_inexistente_test", id="t1", input=None):
        self.name = name
        self.id = id
        self.input = input or {}


class _Resp:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content
        self.usage = _Usage()


def _resp_texto(txt="hola desde claude"):
    return _Resp("end_turn", [_BlkText(txt)])


def _resp_tool():
    # Tool desconocida: el handler la salta sin efectos (sin DB/red), y el
    # flujo vuelve a llamar a Claude → recursión que el presupuesto debe topar.
    return _Resp("tool_use", [_BlkTool()])


def _mock_create(monkeypatch, secuencia):
    """Mockea client.messages.create. `secuencia`: callable(n)->resp o lista."""
    llamadas = {"n": 0}

    async def _fake(**kwargs):
        i = llamadas["n"]
        llamadas["n"] += 1
        r = secuencia(i) if callable(secuencia) else secuencia[min(i, len(secuencia) - 1)]
        return r

    monkeypatch.setattr(brain.client.messages, "create", _fake)
    return llamadas


async def _generar(monkeypatch_tel=TEL, mensaje="hola"):
    # seleccionar_tools puede tocar config; lo neutralizamos a [] para aislar.
    return await brain.generar_respuesta(mensaje, [], telefono=monkeypatch_tel)


# ── 1. Runaway de tool_use topado (REGRESIÓN núcleo) ─────────────────────


class TestRunawayTopado:
    async def test_tool_use_infinito_se_corta_en_max_llm_calls(self, monkeypatch):
        """REGRESIÓN: un Claude que siempre pide tools recursaba sin fin.
        Ahora se corta en max_llm_calls (3) y responde de forma segura."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: _resp_tool())

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain.generar_respuesta("hazme todo", [], telefono=TEL)

        # Exactamente 3 llamadas reales (reservas 1-3 OK; la 4ª se deniega
        # ANTES de llamar a la API).
        assert llamadas["n"] == 3
        assert isinstance(resp, str) and resp  # mensaje seguro, no excepción

    async def test_sin_guard_no_topa_pero_mock_finito(self, monkeypatch):
        """Sanidad: con respuesta de texto (no tool), una sola llamada."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto("ok"))

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 1
        assert "ok" in resp


# ── 2. Over-budget y kill-switch → respuesta segura sin llamar API ───────


class TestBloqueoRespuestaSegura:
    async def test_presupuesto_agotado_no_llama_api(self, monkeypatch):
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto())

        with pr.presupuesto_de_mensaje(TEL) as pres:
            # Agotar las 3 llamadas del presupuesto a mano
            for _ in range(pres.config.max_llm_calls):
                pres.reservar_llm()
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 0  # NO se llamó a la API
        assert isinstance(resp, str) and resp

    async def test_kill_switch_global_no_llama_api(self, monkeypatch):
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto())

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 0
        assert "límite de seguridad" in resp.lower() or "no puedo seguir" in resp.lower()


# ── 3. Timeout → estado cerrado + respuesta segura ───────────────────────


class TestTimeout:
    async def test_timeout_llm_responde_seguro(self, monkeypatch):
        import asyncio
        monkeypatch.setenv("BUDGET_LLM_TIMEOUT_SEGUNDOS", "5")  # ignorado: forzamos pres
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])

        async def _lento(**kwargs):
            await asyncio.sleep(5)
            return _resp_texto()

        monkeypatch.setattr(brain.client.messages, "create", _lento)

        # Presupuesto con timeout LLM minúsculo
        pres = pr.PresupuestoMensaje(TEL, config=pr.cargar_config().__class__(
            **{**pr.cargar_config().__dict__, "llm_timeout_segundos": 0.05}))
        token = pr._presupuesto_actual.set(pres)
        try:
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)
        finally:
            pr._presupuesto_actual.reset(token)

        assert isinstance(resp, str) and resp
        assert pr.snapshot_eventos().get("timeout_llm", 0) >= 1


# ── 4. Consumo de costo ──────────────────────────────────────────────────


class TestConsumo:
    async def test_llamada_consume_costo(self, monkeypatch):
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        _mock_create(monkeypatch, lambda n: _resp_texto())

        with pr.presupuesto_de_mensaje(TEL) as pres:
            await brain.generar_respuesta("hola", [], telefono=TEL)
            assert pres.llm_calls == 1
            assert pres.costo_usd > 0  # input+output tokens estimados


# ── 5. Sin presupuesto activo (scheduler) — kill-switch igual aplica ─────


class TestSinContexto:
    async def test_sin_presupuesto_llama_normal(self, monkeypatch):
        """Path sin presupuesto (jobs): la llamada procede (radar
        reserva_sin_contexto), no rompe."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto("ok"))

        resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 1
        assert "ok" in resp
        assert pr.snapshot_eventos().get("reserva_sin_contexto", 0) >= 1

    async def test_sin_presupuesto_kill_switch_bloquea(self, monkeypatch):
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto())

        resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 0
        assert isinstance(resp, str) and resp
