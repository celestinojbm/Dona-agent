# tests/test_presupuesto_runtime.py — Fase 0 · 4.1/4.2 · PR 1: RuntimeBudgetGuard

"""
Tests unitarios del guard central de presupuesto (criterio Hermes para PR 1):
under-limit, over-limit, loop/step runaway, bloqueo-antes-de-ejecución sin
consume/refund incorrecto, eventos emitidos y env validada. Más: kill-switch
global y por owner, warning al 80%, timeouts con estado cerrado, costo por
mensaje y diario, tiempo agotado y contador corrupto fail-closed.

El módulo es standalone (sin DB): tests puros con env + estado de módulo
aislado por fixture.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta

import pytest

import agent.presupuesto_runtime as pr


TEL = "15550005555"


@pytest.fixture(autouse=True)
def _estado_limpio(monkeypatch):
    """Aísla estado de módulo y env entre tests."""
    pr._contadores_eventos.clear()
    pr._owners_suspendidos.clear()
    pr._costo_diario_owner.clear()
    pr._costo_diario_global.clear()
    for var in (
        "DONA_LLM_COST_KILL_SWITCH",
        "BUDGET_FG_SOFT_SEGUNDOS", "BUDGET_FG_HARD_SEGUNDOS",
        "BUDGET_LLM_TIMEOUT_SEGUNDOS", "BUDGET_LLM_MAX_REINTENTOS",
        "BUDGET_TOOL_TIMEOUT_SEGUNDOS", "BUDGET_TOOL_TIMEOUT_LENTA_SEGUNDOS",
        "BUDGET_MAX_LLM_CALLS_MENSAJE", "BUDGET_MAX_LLM_AUX_CALLS_MENSAJE",
        "BUDGET_MAX_TOOL_CALLS_MENSAJE",
        "BUDGET_MAX_TOOL_DEPTH", "BUDGET_MAX_PARALLEL_TOOLS",
        "BUDGET_MAX_COSTO_USD_MENSAJE", "BUDGET_MAX_COSTO_USD_DIA_OWNER",
        "BUDGET_MAX_COSTO_USD_DIA_GLOBAL",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    pr._contadores_eventos.clear()
    pr._owners_suspendidos.clear()
    pr._costo_diario_owner.clear()
    pr._costo_diario_global.clear()


def _config_corta(**overrides) -> pr.ConfigPresupuesto:
    """Config de test construida directo (sin pasar por env)."""
    base = dict(
        soft_segundos=45.0, hard_segundos=60.0,
        llm_timeout_segundos=30.0, llm_max_reintentos=1,
        max_llm_aux_calls=3,
        tool_timeout_segundos=10.0, tool_timeout_lenta_segundos=30.0,
        max_llm_calls=3, max_tool_calls=8, max_tool_depth=3,
        max_parallel_tools=3, max_costo_usd_mensaje=0.15,
        max_costo_usd_dia_owner=5.0, max_costo_usd_dia_global=50.0,
    )
    base.update(overrides)
    return pr.ConfigPresupuesto(**base)


# ── 1. Límites por mensaje (under/over/runaway) ──────────────────────────


class TestLimitesPorMensaje:
    def test_under_limit_permite(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            for _ in range(pres.config.max_llm_calls):
                assert pres.reservar_llm().permitido is True

    def test_over_limit_bloquea_llm(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            for _ in range(pres.config.max_llm_calls):
                pres.reservar_llm()
            decision = pres.reservar_llm()
            assert decision.permitido is False
            assert decision.razon == "max_llm_calls"

    def test_runaway_loop_nunca_pasa_del_limite(self):
        """Lo que pinea C6: un loop descontrolado NO genera llamadas
        ilimitadas — exactamente max_llm_calls pasan, el resto se bloquea."""
        with pr.presupuesto_de_mensaje(TEL) as pres:
            permitidas = sum(
                1 for _ in range(50) if pres.reservar_llm().permitido
            )
            assert permitidas == pres.config.max_llm_calls

    def test_tools_over_limit_y_runaway(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            permitidas = sum(
                1 for _ in range(50) if pres.reservar_tool().permitido
            )
            assert permitidas == pres.config.max_tool_calls
            assert pres.reservar_tool().razon == "max_tool_calls"

    def test_tool_depth_y_paralelismo(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            assert pres.reservar_tool(depth=3).permitido is True
            assert pres.reservar_tool(depth=4).razon == "max_tool_depth"
            assert pres.reservar_tool(paralelas=3).permitido is True
            assert pres.reservar_tool(paralelas=4).razon == "max_parallel_tools"

    def test_tiempo_agotado_bloquea(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.iniciado = time.monotonic() - (pres.config.hard_segundos + 1)
            decision = pres.reservar_llm()
            assert decision.permitido is False
            assert decision.razon == "presupuesto_tiempo_agotado"


# ── 2. Reserva/consumo sin corrupción (filosofía créditos) ───────────────


class TestReservaConsumo:
    def test_bloqueo_no_corrompe_contadores(self):
        """Una reserva DENEGADA no consume cupo ni deja residuo."""
        with pr.presupuesto_de_mensaje(TEL) as pres:
            for _ in range(pres.config.max_llm_calls):
                pres.reservar_llm()
            antes = pres.llm_calls
            for _ in range(5):
                pres.reservar_llm()  # denegadas
            assert pres.llm_calls == antes

    def test_liberar_devuelve_cupo(self):
        """Reserva cuya llamada nunca se emitió → liberar restaura el cupo."""
        with pr.presupuesto_de_mensaje(TEL) as pres:
            for _ in range(pres.config.max_llm_calls):
                pres.reservar_llm()
            assert pres.reservar_llm().permitido is False
            pres.liberar_llm()
            assert pres.reservar_llm().permitido is True

    def test_liberar_no_baja_de_cero(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.liberar_llm()
            pres.liberar_tool()
            assert pres.llm_calls == 0
            assert pres.tool_calls == 0
            assert pres.reservar_llm().permitido is True

    def test_contador_corrupto_es_fail_closed(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.llm_calls = -1
            decision = pres.reservar_llm()
            assert decision.permitido is False
            assert decision.razon == "contador_corrupto"


# ── 3. Costo (por mensaje y diario por owner) ────────────────────────────


class TestCosto:
    def test_costo_mensaje_bloquea(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            assert pres.reservar_llm().permitido is True
            pres.consumir_llm(pres.config.max_costo_usd_mensaje)
            decision = pres.reservar_llm()
            assert decision.permitido is False
            assert decision.razon == "max_costo_mensaje"

    def test_costo_diario_owner_acumula_entre_mensajes(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.config = _config_corta(max_costo_usd_dia_owner=0.20)
            pres.reservar_llm()
            pres.consumir_llm(0.25)

        # Mensaje NUEVO del mismo owner: el acumulado diario lo bloquea
        with pr.presupuesto_de_mensaje(TEL) as pres2:
            pres2.config = _config_corta(max_costo_usd_dia_owner=0.20)
            decision = pres2.reservar_llm()
            assert decision.permitido is False
            assert decision.razon == "max_costo_diario_owner"

    def test_otro_owner_no_se_contamina(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.config = _config_corta(max_costo_usd_dia_owner=0.20)
            pres.reservar_llm()
            pres.consumir_llm(0.25)
        with pr.presupuesto_de_mensaje("15550006666") as pres2:
            pres2.config = _config_corta(max_costo_usd_dia_owner=0.20)
            assert pres2.reservar_llm().permitido is True


# ── 3.b Circuit breaker de presupuesto diario GLOBAL (TEMA 4 · 4.4) ───────


class TestCircuitBreakerGlobal:
    """El breaker global corta TODA reserva LLM/aux/tool cuando el costo
    diario acumulado de TODOS los owners alcanza el techo del proceso —
    incluso si cada owner individual está muy por debajo de su tope."""

    def test_acumula_a_traves_de_owners_y_corta(self):
        # Adversarial: sangrado distribuido entre muchos owners "limpios".
        # Techo global bajo (0.30), per-owner alto (5.0) → ningún owner
        # dispara su propio límite, pero la suma sí dispara el global.
        for i in range(3):
            tel = f"1555000{i:04d}"
            with pr.presupuesto_de_mensaje(tel) as pres:
                pres.config = _config_corta(
                    max_costo_usd_dia_global=0.30,
                    max_costo_usd_dia_owner=5.0,
                    max_costo_usd_mensaje=1.0,
                )
                assert pres.reservar_llm().permitido is True
                pres.consumir_llm(0.10)  # cada owner gasta poco

        assert pr.costo_diario_global() >= 0.30
        # Owner NUEVO y limpio: su per-owner está en 0, pero el global ya tronó.
        with pr.presupuesto_de_mensaje("15559999999") as nuevo:
            nuevo.config = _config_corta(
                max_costo_usd_dia_global=0.30, max_costo_usd_dia_owner=5.0,
            )
            decision = nuevo.reservar_llm()
            assert decision.permitido is False
            assert decision.razon == "max_costo_diario_global"

    def test_breaker_global_corta_tambien_tools(self):
        # El global es un circuit breaker de proceso: una vez tronado, ni
        # siquiera las tools (que no tienen costo USD propio) pueden reservar.
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.config = _config_corta(
                max_costo_usd_dia_global=0.20, max_costo_usd_mensaje=1.0,
            )
            assert pres.reservar_llm().permitido is True
            pres.consumir_llm(0.25)  # supera el global
            decision = pres.reservar_tool()
            assert decision.permitido is False
            assert decision.razon == "max_costo_diario_global"

    def test_breaker_global_corta_aux(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.config = _config_corta(
                max_costo_usd_dia_global=0.20, max_costo_usd_mensaje=1.0,
            )
            assert pres.reservar_llm().permitido is True
            pres.consumir_llm(0.25)
            decision = pres.reservar_llm_aux()
            assert decision.permitido is False
            assert decision.razon == "max_costo_diario_global"

    def test_default_no_interfiere(self):
        # Bajo el default (50.0/día) un gasto normal no dispara el global.
        with pr.presupuesto_de_mensaje(TEL) as pres:
            assert pres.reservar_llm().permitido is True
            pres.consumir_llm(0.05)
            assert pres.reservar_llm().permitido is True

    def test_sin_contexto_bloquea(self, monkeypatch):
        # Jobs/scheduler sin presupuesto de mensaje también respetan el techo
        # global: un breaker de proceso no puede tener agujeros por path.
        monkeypatch.setenv("BUDGET_MAX_COSTO_USD_DIA_GLOBAL", "1.0")
        pr._costo_diario_global[pr._clave_dia()] = 1.5  # ya excedido
        decision = pr.reservar_llm(TEL)
        assert decision.permitido is False
        assert decision.razon == "max_costo_diario_global"

    def test_sin_contexto_aux_bloquea(self, monkeypatch):
        monkeypatch.setenv("BUDGET_MAX_COSTO_USD_DIA_GLOBAL", "1.0")
        pr._costo_diario_global[pr._clave_dia()] = 1.5
        decision = pr.reservar_llm_aux(TEL)
        assert decision.permitido is False
        assert decision.razon == "max_costo_diario_global"

    def test_bloqueo_emite_evento(self, caplog):
        with caplog.at_level(logging.WARNING, logger="dona"):
            with pr.presupuesto_de_mensaje(TEL) as pres:
                pres.config = _config_corta(
                    max_costo_usd_dia_global=0.20, max_costo_usd_mensaje=1.0,
                )
                pres.reservar_llm()
                pres.consumir_llm(0.25)
                pres.reservar_llm()
        assert pr.snapshot_eventos().get("budget_blocked", 0) >= 1
        assert any("max_costo_diario_global" in r.message for r in caplog.records)

    def test_env_valida_se_aplica(self, monkeypatch):
        monkeypatch.setenv("BUDGET_MAX_COSTO_USD_DIA_GLOBAL", "12.5")
        assert pr.cargar_config().max_costo_usd_dia_global == 12.5

    def test_env_fuera_de_rango_cae_a_default(self, monkeypatch):
        monkeypatch.setenv("BUDGET_MAX_COSTO_USD_DIA_GLOBAL", "999999")
        assert pr.cargar_config().max_costo_usd_dia_global == 50.0


# ── 4. Kill-switches ─────────────────────────────────────────────────────


class TestKillSwitches:
    def test_global_bloquea_en_contexto(self, monkeypatch):
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        with pr.presupuesto_de_mensaje(TEL) as pres:
            decision = pres.reservar_llm()
            assert decision.permitido is False
            assert decision.razon == "kill_switch_global"

    def test_global_bloquea_sin_contexto(self, monkeypatch):
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        decision = pr.reservar_llm(TEL)
        assert decision.permitido is False
        assert decision.razon == "kill_switch_global"

    def test_owner_suspendido_bloquea_y_expira(self):
        pr.suspender_owner(TEL, datetime.utcnow() + timedelta(hours=1), "cost_block")
        with pr.presupuesto_de_mensaje(TEL) as pres:
            assert pres.reservar_llm().razon == "owner_suspendido"

        pr.levantar_suspension_owner(TEL)
        with pr.presupuesto_de_mensaje(TEL) as pres:
            assert pres.reservar_llm().permitido is True

        # Suspensión ya vencida no bloquea
        pr.suspender_owner(TEL, datetime.utcnow() - timedelta(minutes=1), "viejo")
        with pr.presupuesto_de_mensaje(TEL) as pres:
            assert pres.reservar_llm().permitido is True


# ── 5. Eventos ───────────────────────────────────────────────────────────


class TestEventos:
    def test_bloqueo_emite_evento_con_campos(self, caplog):
        with caplog.at_level(logging.WARNING, logger="dona"):
            with pr.presupuesto_de_mensaje(TEL) as pres:
                for _ in range(pres.config.max_llm_calls + 1):
                    pres.reservar_llm()
        assert pr.snapshot_eventos().get("budget_blocked", 0) >= 1
        linea = next(r.message for r in caplog.records if "budget_blocked" in r.message)
        assert "razon=max_llm_calls" in linea
        assert "limite=" in linea
        assert TEL[-4:] in linea  # owner_short, nunca el teléfono completo
        assert TEL not in linea

    def test_warning_al_80_una_sola_vez(self):
        with pr.presupuesto_de_mensaje(TEL) as pres:
            for _ in range(pres.config.max_tool_calls):
                pres.reservar_tool()
        assert pr.snapshot_eventos().get("budget_warning_80", 0) == 1

    def test_sin_contexto_emite_radar(self):
        decision = pr.reservar_llm(TEL)
        assert decision.permitido is True
        assert pr.snapshot_eventos().get("reserva_sin_contexto", 0) == 1


# ── 6. Config por env validada (fail-closed a default seguro) ────────────


class TestConfigEnv:
    def test_defaults_seguros_sin_env(self):
        config = pr.cargar_config()
        assert config.max_llm_calls == 3
        assert config.max_tool_calls == 8
        assert config.hard_segundos == 60.0
        assert config.max_costo_usd_mensaje == 0.15

    def test_env_valida_se_aplica(self, monkeypatch):
        monkeypatch.setenv("BUDGET_MAX_LLM_CALLS_MENSAJE", "5")
        assert pr.cargar_config().max_llm_calls == 5

    def test_env_ilegible_cae_a_default_con_evento(self, monkeypatch):
        monkeypatch.setenv("BUDGET_MAX_LLM_CALLS_MENSAJE", "muchas")
        config = pr.cargar_config()
        assert config.max_llm_calls == 3  # default seguro, no crash
        assert pr.snapshot_eventos().get("config_invalida", 0) == 1

    def test_env_fuera_de_rango_cae_a_default_con_evento(self, monkeypatch):
        monkeypatch.setenv("BUDGET_MAX_LLM_CALLS_MENSAJE", "999")
        config = pr.cargar_config()
        assert config.max_llm_calls == 3
        assert pr.snapshot_eventos().get("config_invalida", 0) == 1


# ── 7. Timeouts con estado cerrado (4.1) ─────────────────────────────────


class TestTimeouts:
    async def test_timeout_llm_emite_y_lanza(self):
        pres = pr.PresupuestoMensaje(TEL, config=_config_corta(llm_timeout_segundos=0.05))
        token = pr._presupuesto_actual.set(pres)
        try:
            with pytest.raises(pr.TimeoutPresupuesto) as exc:
                await pr.con_timeout_llm(asyncio.sleep(5), TEL)
            assert exc.value.razon == "timeout_llm"
            assert pr.snapshot_eventos().get("timeout_llm", 0) == 1
        finally:
            pr._presupuesto_actual.reset(token)

    async def test_timeout_budget_global_cuando_resta_menos(self):
        """Si al presupuesto del mensaje le queda menos que el timeout por
        llamada, manda el restante global — razón timeout_budget_global."""
        pres = pr.PresupuestoMensaje(TEL, config=_config_corta(hard_segundos=60.0))
        pres.iniciado = time.monotonic() - 59.95  # restan ~0.05s
        token = pr._presupuesto_actual.set(pres)
        try:
            with pytest.raises(pr.TimeoutPresupuesto) as exc:
                await pr.con_timeout_llm(asyncio.sleep(5), TEL)
            assert exc.value.razon == "timeout_budget_global"
        finally:
            pr._presupuesto_actual.reset(token)

    async def test_timeout_tool_normal_y_lenta(self):
        pres = pr.PresupuestoMensaje(
            TEL,
            config=_config_corta(
                tool_timeout_segundos=0.05, tool_timeout_lenta_segundos=1.0
            ),
        )
        token = pr._presupuesto_actual.set(pres)
        try:
            # La normal (0.05s) corta una tool de 0.3s…
            with pytest.raises(pr.TimeoutPresupuesto):
                await pr.con_timeout_tool(asyncio.sleep(0.3), TEL)
            # …que con whitelist de lenta (1s) sí completa.
            async def _tool_lenta():
                await asyncio.sleep(0.3)
                return "ok"
            assert await pr.con_timeout_tool(_tool_lenta(), TEL, lenta=True) == "ok"
        finally:
            pr._presupuesto_actual.reset(token)

    async def test_resultado_pasa_intacto_bajo_timeout(self):
        async def _rapida():
            return 42
        assert await pr.con_timeout_llm(_rapida(), TEL) == 42
