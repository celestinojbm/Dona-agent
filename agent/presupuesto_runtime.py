# agent/presupuesto_runtime.py — RuntimeBudgetGuard (Fase 0 · 4.1/4.2 · PR 1)
# Dona

"""
Guard CENTRAL de presupuesto de ejecución LLM/tools (criterio Hermes, C6 del
audit Fable 5: "costo LLM sin control"). Misma filosofía que el ciclo de
créditos: cada llamada LLM/tool RESERVA presupuesto antes de ejecutar y
CONSUME (o LIBERA) después. El tope vive aquí, no repartido en prompts.

Este PR (1 de 4) entrega el guard standalone: config validada por env,
estado por mensaje vía ContextVar, kill-switches, eventos cerrados y API de
reserva/consumo. Los PRs siguientes envuelven las llamadas LLM (PR 2) y las
tools/HTTP externo (PR 3) con este guard; el PR 4 es la batería adversarial.

Dimensiones controladas por mensaje foreground:
  - tiempo total (soft 45s / hard 60s)
  - llamadas LLM (máx 3) · llamadas tool (máx 8) · profundidad (máx 3) ·
    tools paralelas (máx 3)
  - costo USD por mensaje (default 0.15) y costo USD diario por owner
    (default 5.00; contador in-memory per-proceso en este PR — la
    persistencia cross-restart llega con el wiring)

Kill-switches:
  - global: DONA_LLM_COST_KILL_SWITCH=true bloquea nuevas reservas LLM
  - por owner: suspender_owner(telefono, hasta, razon)

Fail-closed (criterio Hermes):
  - config inválida → default SEGURO + evento config_invalida (no se adopta
    un límite no confiable);
  - contadores corruptos (negativos) → denegar con contador_corrupto;
  - al 80% de cualquier dimensión → evento warning (una vez por dimensión);
  - al 100% → denegar con razón cerrada; el caller responde de forma segura.

Dimensión auxiliar (entregable F · F-1, criterio Hermes): las llamadas LLM
ligeras de soporte (detección emocional, clasificación NLP, postprocesos)
NO compiten por el cupo principal del loop (max_llm_calls) — tienen cupo
propio `max_llm_aux_calls` (default 3). El COSTO sí es compartido (entra a
max_costo_usd_mensaje y al diario por owner), y timeout/kill-switch aplican
idéntico. Invariante: ninguna llamada real al provider sin guard, en
ninguna dimensión.

Razones de bloqueo (set CERRADO — no inventar strings nuevos en callers):
  kill_switch_global · owner_suspendido · presupuesto_tiempo_agotado ·
  max_llm_calls · max_llm_aux_calls · max_tool_calls · max_tool_depth ·
  max_parallel_tools · max_costo_mensaje · max_costo_diario_owner ·
  contador_corrupto
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("dona")

# ── Razones cerradas ─────────────────────────────────────────────────────

RAZONES_BLOQUEO = {
    "kill_switch_global",
    "owner_suspendido",
    "presupuesto_tiempo_agotado",
    "max_llm_calls",
    "max_llm_aux_calls",
    "max_tool_calls",
    "max_tool_depth",
    "max_parallel_tools",
    "max_costo_mensaje",
    "max_costo_diario_owner",
    "contador_corrupto",
}

# Eventos cerrados (para contadores/observabilidad)
EVENTOS = {
    "budget_blocked",
    "budget_warning_80",
    "config_invalida",
    "reserva_sin_contexto",
    "timeout_llm",
    "timeout_tool",
    "timeout_budget_global",
    "owner_suspendido_set",
}

# Contadores in-memory de eventos (para /admin/metrics en PRs siguientes)
_contadores_eventos: dict[str, int] = {}


def snapshot_eventos() -> dict[str, int]:
    return dict(_contadores_eventos)


def _emitir_evento(tipo: str, nivel: int = logging.WARNING, **campos) -> None:
    """Evento cerrado con campos mínimos (criterio Hermes): scope/user,
    run/action id, límite, razón, estimated/actual/remaining, modelo/tool —
    los que existan en cada caso. Nunca contenido de mensajes ni secretos."""
    if tipo not in EVENTOS:
        # No inventar eventos: registrar el intento y normalizar.
        logger.error(f"[BUDGET] evento desconocido '{tipo}' — normalizado a budget_blocked")
        tipo = "budget_blocked"
    _contadores_eventos[tipo] = _contadores_eventos.get(tipo, 0) + 1
    detalle = " ".join(f"{k}={v}" for k, v in campos.items() if v is not None)
    logger.log(nivel, f"[BUDGET] {tipo} {detalle}")


# ── Config validada por env ──────────────────────────────────────────────


def _leer_num(nombre: str, default: float, minimo: float, maximo: float) -> float:
    """Lee un número de env con validación fail-closed: valor ilegible o
    fuera de rango → default SEGURO + evento config_invalida. Nunca se
    adopta un límite no confiable."""
    crudo = os.getenv(nombre)
    if crudo is None or crudo.strip() == "":
        return default
    try:
        valor = float(crudo)
    except (TypeError, ValueError):
        _emitir_evento(
            "config_invalida", nivel=logging.CRITICAL,
            variable=nombre, valor=repr(crudo), default_aplicado=default,
        )
        return default
    if not (minimo <= valor <= maximo):
        _emitir_evento(
            "config_invalida", nivel=logging.CRITICAL,
            variable=nombre, valor=valor, rango=f"[{minimo},{maximo}]",
            default_aplicado=default,
        )
        return default
    return valor


@dataclass(frozen=True)
class ConfigPresupuesto:
    """Límites vigentes. Se relee de env en cada mensaje (barato y permite
    ajustar sin redeploy de código, solo env)."""
    soft_segundos: float
    hard_segundos: float
    llm_timeout_segundos: float
    llm_max_reintentos: int
    max_llm_aux_calls: int
    tool_timeout_segundos: float
    tool_timeout_lenta_segundos: float
    max_llm_calls: int
    max_tool_calls: int
    max_tool_depth: int
    max_parallel_tools: int
    max_costo_usd_mensaje: float
    max_costo_usd_dia_owner: float


def cargar_config() -> ConfigPresupuesto:
    return ConfigPresupuesto(
        soft_segundos=_leer_num("BUDGET_FG_SOFT_SEGUNDOS", 45.0, 5.0, 300.0),
        hard_segundos=_leer_num("BUDGET_FG_HARD_SEGUNDOS", 60.0, 10.0, 600.0),
        llm_timeout_segundos=_leer_num("BUDGET_LLM_TIMEOUT_SEGUNDOS", 30.0, 5.0, 120.0),
        llm_max_reintentos=int(_leer_num("BUDGET_LLM_MAX_REINTENTOS", 1, 0, 2)),
        max_llm_aux_calls=int(_leer_num("BUDGET_MAX_LLM_AUX_CALLS_MENSAJE", 3, 0, 20)),
        tool_timeout_segundos=_leer_num("BUDGET_TOOL_TIMEOUT_SEGUNDOS", 10.0, 1.0, 60.0),
        tool_timeout_lenta_segundos=_leer_num("BUDGET_TOOL_TIMEOUT_LENTA_SEGUNDOS", 30.0, 1.0, 120.0),
        max_llm_calls=int(_leer_num("BUDGET_MAX_LLM_CALLS_MENSAJE", 3, 1, 20)),
        max_tool_calls=int(_leer_num("BUDGET_MAX_TOOL_CALLS_MENSAJE", 8, 1, 50)),
        max_tool_depth=int(_leer_num("BUDGET_MAX_TOOL_DEPTH", 3, 1, 10)),
        max_parallel_tools=int(_leer_num("BUDGET_MAX_PARALLEL_TOOLS", 3, 1, 10)),
        max_costo_usd_mensaje=_leer_num("BUDGET_MAX_COSTO_USD_MENSAJE", 0.15, 0.01, 5.0),
        max_costo_usd_dia_owner=_leer_num("BUDGET_MAX_COSTO_USD_DIA_OWNER", 5.0, 0.10, 100.0),
    )


def kill_switch_global_activo() -> bool:
    """DONA_LLM_COST_KILL_SWITCH=true bloquea nuevas reservas LLM no
    críticas. Se lee en cada reserva (activable sin redeploy)."""
    return os.getenv("DONA_LLM_COST_KILL_SWITCH", "").strip().lower() in (
        "true", "1", "yes", "on",
    )


# ── Suspensión por owner (kill-switch granular, in-memory) ───────────────

_owners_suspendidos: dict[str, tuple[datetime, str]] = {}


def suspender_owner(telefono: str, hasta: datetime, razon: str) -> None:
    _owners_suspendidos[telefono] = (hasta, razon)
    _emitir_evento(
        "owner_suspendido_set", nivel=logging.CRITICAL,
        owner_short=telefono[-4:] if telefono else "?", hasta=hasta.isoformat(),
        razon=razon,
    )


def levantar_suspension_owner(telefono: str) -> None:
    _owners_suspendidos.pop(telefono, None)


def owner_suspendido(telefono: str) -> str | None:
    """Retorna la razón si el owner está suspendido y vigente, si no None."""
    entrada = _owners_suspendidos.get(telefono)
    if not entrada:
        return None
    hasta, razon = entrada
    if datetime.utcnow() >= hasta:
        _owners_suspendidos.pop(telefono, None)
        return None
    return razon


# ── Costo diario por owner (in-memory per-proceso en este PR) ────────────
# Best-effort declarado: se resetea con cada deploy/restart. La persistencia
# cross-restart se decide en el PR de wiring (tabla, mismo patrón create_all).

_costo_diario_owner: dict[tuple[str, str], float] = {}


def _clave_dia() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def costo_diario_de(telefono: str) -> float:
    return _costo_diario_owner.get((telefono, _clave_dia()), 0.0)


def _acumular_costo_owner(telefono: str, usd: float) -> None:
    if not telefono:
        return
    clave = (telefono, _clave_dia())
    _costo_diario_owner[clave] = _costo_diario_owner.get(clave, 0.0) + max(usd, 0.0)
    # Poda barata de días anteriores
    hoy = _clave_dia()
    for k in [k for k in _costo_diario_owner if k[1] != hoy]:
        del _costo_diario_owner[k]


# ── Decisión ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DecisionPresupuesto:
    """Resultado de una reserva. Consultar SIEMPRE `.permitido` explícito —
    a propósito NO define __bool__: la verdad implícita de un objeto-decisión
    es ambigua (¿"hay decisión" o "está permitido"?) y ese tipo de azúcar
    produce exactamente los fail-open que este guard existe para impedir."""
    permitido: bool
    razon: str = ""          # "" si permitido; si no, una de RAZONES_BLOQUEO
    limite: float | None = None
    usado: float | None = None
    restante: float | None = None


_PERMITIDO = DecisionPresupuesto(permitido=True)


# ── Estado por mensaje ───────────────────────────────────────────────────


@dataclass
class PresupuestoMensaje:
    telefono: str
    config: ConfigPresupuesto = field(default_factory=cargar_config)
    iniciado: float = field(default_factory=time.monotonic)
    llm_calls: int = 0
    llm_aux_calls: int = 0
    tool_calls: int = 0
    depth_actual: int = 0
    paralelas_actual: int = 0
    costo_usd: float = 0.0
    # Warnings de 80% ya emitidos (una vez por dimensión por mensaje)
    _warnings_emitidos: set = field(default_factory=set)

    # ── helpers internos ──────────────────────────────────────────────

    def transcurrido(self) -> float:
        return time.monotonic() - self.iniciado

    def tiempo_restante(self) -> float:
        return max(0.0, self.config.hard_segundos - self.transcurrido())

    def _contadores_sanos(self) -> bool:
        return (
            self.llm_calls >= 0 and self.llm_aux_calls >= 0
            and self.tool_calls >= 0
            and self.depth_actual >= 0 and self.paralelas_actual >= 0
            and self.costo_usd >= 0.0
        )

    def _warn_80(self, dimension: str, usado: float, limite: float) -> None:
        if limite <= 0 or dimension in self._warnings_emitidos:
            return
        if usado / limite >= 0.8:
            self._warnings_emitidos.add(dimension)
            _emitir_evento(
                "budget_warning_80",
                owner_short=self.telefono[-4:] if self.telefono else "?",
                dimension=dimension, usado=round(usado, 4), limite=limite,
            )

    def _bloquear(self, razon: str, limite=None, usado=None) -> DecisionPresupuesto:
        assert razon in RAZONES_BLOQUEO, f"razón no cerrada: {razon}"
        _emitir_evento(
            "budget_blocked",
            owner_short=self.telefono[-4:] if self.telefono else "?",
            razon=razon, limite=limite, usado=usado,
            transcurrido_s=round(self.transcurrido(), 1),
        )
        return DecisionPresupuesto(
            permitido=False, razon=razon, limite=limite, usado=usado,
            restante=self.tiempo_restante(),
        )

    def _checks_comunes(self) -> DecisionPresupuesto | None:
        if not self._contadores_sanos():
            # Fail-closed: un contador corrupto no es base para permitir nada.
            return self._bloquear("contador_corrupto")
        if kill_switch_global_activo():
            return self._bloquear("kill_switch_global")
        razon_susp = owner_suspendido(self.telefono)
        if razon_susp:
            return self._bloquear("owner_suspendido", usado=razon_susp)
        if self.transcurrido() >= self.config.hard_segundos:
            return self._bloquear(
                "presupuesto_tiempo_agotado",
                limite=self.config.hard_segundos,
                usado=round(self.transcurrido(), 1),
            )
        return None

    # ── API de reserva/consumo (filosofía créditos) ───────────────────

    def reservar_llm(self) -> DecisionPresupuesto:
        bloqueo = self._checks_comunes()
        if bloqueo is not None:
            return bloqueo
        if self.llm_calls >= self.config.max_llm_calls:
            return self._bloquear(
                "max_llm_calls", limite=self.config.max_llm_calls,
                usado=self.llm_calls,
            )
        if self.costo_usd >= self.config.max_costo_usd_mensaje:
            return self._bloquear(
                "max_costo_mensaje", limite=self.config.max_costo_usd_mensaje,
                usado=round(self.costo_usd, 4),
            )
        if costo_diario_de(self.telefono) >= self.config.max_costo_usd_dia_owner:
            return self._bloquear(
                "max_costo_diario_owner",
                limite=self.config.max_costo_usd_dia_owner,
                usado=round(costo_diario_de(self.telefono), 4),
            )
        self.llm_calls += 1
        self._warn_80("llm_calls", self.llm_calls, self.config.max_llm_calls)
        self._warn_80("tiempo", self.transcurrido(), self.config.hard_segundos)
        return _PERMITIDO

    def liberar_llm(self) -> None:
        """La llamada reservada nunca se ejecutó (bloqueo posterior antes de
        emitirla). NO usar tras una llamada realizada, ni siquiera fallida —
        un intento real consume cupo (evita retries infinitos)."""
        self.llm_calls = max(0, self.llm_calls - 1)

    def reservar_llm_aux(self) -> DecisionPresupuesto:
        """Reserva una llamada LLM AUXILIAR (ligera, de soporte). Cupo propio
        (max_llm_aux_calls) para no competir con el loop principal; el costo
        comparte los topes de mensaje y diario (un aux puede agotar el costo
        y bloquear al principal — eso es correcto: el techo real es USD)."""
        bloqueo = self._checks_comunes()
        if bloqueo is not None:
            return bloqueo
        if self.llm_aux_calls >= self.config.max_llm_aux_calls:
            return self._bloquear(
                "max_llm_aux_calls", limite=self.config.max_llm_aux_calls,
                usado=self.llm_aux_calls,
            )
        if self.costo_usd >= self.config.max_costo_usd_mensaje:
            return self._bloquear(
                "max_costo_mensaje", limite=self.config.max_costo_usd_mensaje,
                usado=round(self.costo_usd, 4),
            )
        if costo_diario_de(self.telefono) >= self.config.max_costo_usd_dia_owner:
            return self._bloquear(
                "max_costo_diario_owner",
                limite=self.config.max_costo_usd_dia_owner,
                usado=round(costo_diario_de(self.telefono), 4),
            )
        self.llm_aux_calls += 1
        self._warn_80("llm_aux_calls", self.llm_aux_calls, self.config.max_llm_aux_calls)
        return _PERMITIDO

    def liberar_llm_aux(self) -> None:
        """La llamada aux reservada nunca se ejecutó. Mismas reglas que
        liberar_llm: un intento real consume cupo."""
        self.llm_aux_calls = max(0, self.llm_aux_calls - 1)

    def consumir_llm(self, costo_usd: float, modelo: str = "") -> None:
        """Registra el costo REAL post-llamada (estimado si el proveedor no
        lo da). El cupo ya se tomó en reservar_llm."""
        costo = max(float(costo_usd or 0.0), 0.0)
        self.costo_usd += costo
        _acumular_costo_owner(self.telefono, costo)
        self._warn_80("costo_mensaje", self.costo_usd, self.config.max_costo_usd_mensaje)
        self._warn_80(
            "costo_diario_owner",
            costo_diario_de(self.telefono),
            self.config.max_costo_usd_dia_owner,
        )

    def reservar_tool(self, depth: int = 1, paralelas: int = 1) -> DecisionPresupuesto:
        bloqueo = self._checks_comunes()
        if bloqueo is not None:
            return bloqueo
        if self.tool_calls >= self.config.max_tool_calls:
            return self._bloquear(
                "max_tool_calls", limite=self.config.max_tool_calls,
                usado=self.tool_calls,
            )
        if depth > self.config.max_tool_depth:
            return self._bloquear(
                "max_tool_depth", limite=self.config.max_tool_depth, usado=depth,
            )
        if paralelas > self.config.max_parallel_tools:
            return self._bloquear(
                "max_parallel_tools", limite=self.config.max_parallel_tools,
                usado=paralelas,
            )
        self.tool_calls += 1
        self._warn_80("tool_calls", self.tool_calls, self.config.max_tool_calls)
        return _PERMITIDO

    def liberar_tool(self) -> None:
        """La tool reservada nunca se ejecutó. Mismas reglas que liberar_llm."""
        self.tool_calls = max(0, self.tool_calls - 1)


# ── Contexto por mensaje ─────────────────────────────────────────────────

_presupuesto_actual: ContextVar[PresupuestoMensaje | None] = ContextVar(
    "presupuesto_actual", default=None
)


@contextmanager
def presupuesto_de_mensaje(telefono: str):
    """Abre el presupuesto del procesamiento de UN mensaje inbound. El
    wiring (PR 2) lo coloca en el entry point del webhook; todo lo anidado
    (incl. tasks creadas dentro) hereda el mismo presupuesto."""
    pres = PresupuestoMensaje(telefono=telefono)
    token = _presupuesto_actual.set(pres)
    try:
        yield pres
    finally:
        _presupuesto_actual.reset(token)


def abrir_presupuesto_mensaje(telefono: str):
    """Variante imperativa de `presupuesto_de_mensaje` para el loop del webhook
    (donde un `with` obligaría a re-indentar cientos de líneas). Devuelve el
    token; cerrar con `cerrar_presupuesto_mensaje(token)`."""
    return _presupuesto_actual.set(PresupuestoMensaje(telefono=telefono))


def cerrar_presupuesto_mensaje(token) -> None:
    _presupuesto_actual.reset(token)


def presupuesto_actual() -> PresupuestoMensaje | None:
    return _presupuesto_actual.get()


def consumir_llm(costo_usd: float, modelo: str = "") -> None:
    """Registra el costo real de una llamada LLM contra el presupuesto del
    mensaje activo (post-llamada). No-op fuera de un contexto de mensaje —
    el costo per-owner se acumula solo dentro del presupuesto del mensaje."""
    pres = presupuesto_actual()
    if pres is not None:
        pres.consumir_llm(costo_usd, modelo)


def reservar_llm(telefono: str = "") -> DecisionPresupuesto:
    """Reserva una llamada LLM contra el presupuesto del mensaje activo.

    Fuera de un contexto de mensaje (jobs/scheduler aún sin wiring) aplica
    solo los kill-switches globales/por-owner y emite `reserva_sin_contexto`
    en WARNING — ese evento es el radar del PR 2 para cazar paths sin
    envolver. NO es un bypass del kill-switch."""
    pres = presupuesto_actual()
    if pres is not None:
        return pres.reservar_llm()

    if kill_switch_global_activo():
        _emitir_evento(
            "budget_blocked", razon="kill_switch_global",
            owner_short=telefono[-4:] if telefono else "?", contexto="sin_presupuesto",
        )
        return DecisionPresupuesto(permitido=False, razon="kill_switch_global")
    razon_susp = owner_suspendido(telefono) if telefono else None
    if razon_susp:
        _emitir_evento(
            "budget_blocked", razon="owner_suspendido",
            owner_short=telefono[-4:] if telefono else "?", contexto="sin_presupuesto",
        )
        return DecisionPresupuesto(permitido=False, razon="owner_suspendido")
    _emitir_evento(
        "reserva_sin_contexto",
        owner_short=telefono[-4:] if telefono else "?",
    )
    return _PERMITIDO


def reservar_llm_aux(telefono: str = "") -> DecisionPresupuesto:
    """Reserva una llamada LLM AUXILIAR contra el presupuesto del mensaje
    activo. Fuera de contexto: mismo comportamiento fail-safe que
    reservar_llm (kill-switches aplican, radar reserva_sin_contexto) —
    el camino normal es que TODA unidad de trabajo tenga presupuesto
    (foreground via webhook; background abre el suyo por unidad)."""
    pres = presupuesto_actual()
    if pres is not None:
        return pres.reservar_llm_aux()

    if kill_switch_global_activo():
        _emitir_evento(
            "budget_blocked", razon="kill_switch_global",
            owner_short=telefono[-4:] if telefono else "?", contexto="sin_presupuesto",
        )
        return DecisionPresupuesto(permitido=False, razon="kill_switch_global")
    razon_susp = owner_suspendido(telefono) if telefono else None
    if razon_susp:
        _emitir_evento(
            "budget_blocked", razon="owner_suspendido",
            owner_short=telefono[-4:] if telefono else "?", contexto="sin_presupuesto",
        )
        return DecisionPresupuesto(permitido=False, razon="owner_suspendido")
    _emitir_evento(
        "reserva_sin_contexto",
        owner_short=telefono[-4:] if telefono else "?",
    )
    return _PERMITIDO


# ── Timeouts (4.1) ───────────────────────────────────────────────────────


class TimeoutPresupuesto(RuntimeError):
    """Timeout aplicado por el guard. `razon` ∈ {timeout_llm, timeout_tool,
    timeout_budget_global} — estado CERRADO, nunca colgado."""

    def __init__(self, razon: str):
        super().__init__(razon)
        self.razon = razon


async def con_timeout_llm(coro, telefono: str = ""):
    """Ejecuta una corrutina LLM con el menor entre el timeout por llamada y
    el tiempo restante del presupuesto del mensaje (si hay contexto)."""
    import asyncio

    config = (presupuesto_actual().config if presupuesto_actual() else cargar_config())
    limite = config.llm_timeout_segundos
    razon = "timeout_llm"
    pres = presupuesto_actual()
    if pres is not None and pres.tiempo_restante() < limite:
        limite = max(pres.tiempo_restante(), 0.001)
        razon = "timeout_budget_global"
    try:
        return await asyncio.wait_for(coro, timeout=limite)
    except TimeoutError:
        _emitir_evento(
            razon, owner_short=telefono[-4:] if telefono else "?",
            limite_s=round(limite, 1),
        )
        raise TimeoutPresupuesto(razon) from None


async def con_timeout_tool(coro, telefono: str = "", lenta: bool = False):
    """Ejecuta una corrutina de tool/HTTP externo con timeout (10s default,
    30s para tools lentas whitelisted por el caller)."""
    import asyncio

    config = (presupuesto_actual().config if presupuesto_actual() else cargar_config())
    limite = config.tool_timeout_lenta_segundos if lenta else config.tool_timeout_segundos
    razon = "timeout_tool"
    pres = presupuesto_actual()
    if pres is not None and pres.tiempo_restante() < limite:
        limite = max(pres.tiempo_restante(), 0.001)
        razon = "timeout_budget_global"
    try:
        return await asyncio.wait_for(coro, timeout=limite)
    except TimeoutError:
        _emitir_evento(
            razon, owner_short=telefono[-4:] if telefono else "?",
            limite_s=round(limite, 1),
        )
        raise TimeoutPresupuesto(razon) from None
