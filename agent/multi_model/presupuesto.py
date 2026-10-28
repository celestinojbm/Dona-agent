"""Presupuesto diario por agente (F23 · riesgo 3 de PR #306 / issue #310).

Cada agente (scope `agente` de `preferencia_modelo`) tiene un tope de gasto
diario en USD. Antes de CUALQUIER llamada a un proveedor (real o simulado) se
verifica ese tope; al llegar al 80% se avisa (una vez por agente/día, sin
bloquear) y al 100% se bloquea con `PresupuestoAgenteAgotadoError` — ninguna
llamada nueva sale para ese agente hasta el reset diario.

Misma filosofía que `agent.presupuesto_runtime` (guard central de costo LLM,
la "decisión de créditos del roadmap"): reserva ANTES de llamar, consume
DESPUÉS, config validada con fallback fail-closed, estado in-memory
per-proceso (mismo trade-off ya declarado ahí: se resetea con el deploy; la
persistencia cross-restart queda fuera de este alcance — este módulo cierra
el riesgo "sin tope", no pretende ser el ledger de créditos del usuario).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger("dona")

# Tope diario por defecto (USD) si no se configura por env o el valor es
# inválido. Conservador: cierra el riesgo "sin tope" sin bloquear agentes de
# uso normal de buenas a primeras.
LIMITE_USD_DIA_AGENTE_DEFAULT = 5.0

_UMBRAL_AVISO = 0.8


class PresupuestoAgenteAgotadoError(RuntimeError):
    """El agente alcanzó (o superó) su tope diario de gasto: bloqueo duro,
    ninguna llamada a proveedor debe salir mientras esta excepción se lance."""

    def __init__(self, agente: str, gastado: float, limite: float):
        self.agente = agente
        self.gastado = gastado
        self.limite = limite
        super().__init__(
            f"presupuesto diario agotado para agente {agente!r}: "
            f"{gastado:.4f}/{limite:.4f} USD"
        )


def limite_usd_dia_agente() -> float:
    """Tope diario USD por agente (env `DONA_PRESUPUESTO_AGENTE_USD_DIA`).

    Fail-closed: valor ausente, no numérico o <= 0 → default seguro (nunca se
    adopta un límite no confiable). Se lee en cada llamada (no se cachea) para
    respetar `monkeypatch.setenv` en tests y permitir ajustar sin redeploy."""
    crudo = os.getenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "").strip()
    if not crudo:
        return LIMITE_USD_DIA_AGENTE_DEFAULT
    try:
        valor = float(crudo)
    except ValueError:
        logger.warning(
            "[MULTI_MODEL] DONA_PRESUPUESTO_AGENTE_USD_DIA inválido (%r); "
            "usando default %.2f", crudo, LIMITE_USD_DIA_AGENTE_DEFAULT,
        )
        return LIMITE_USD_DIA_AGENTE_DEFAULT
    if valor <= 0:
        logger.warning(
            "[MULTI_MODEL] DONA_PRESUPUESTO_AGENTE_USD_DIA debe ser > 0 (%s); "
            "usando default %.2f", valor, LIMITE_USD_DIA_AGENTE_DEFAULT,
        )
        return LIMITE_USD_DIA_AGENTE_DEFAULT
    return valor


# Estado in-memory per-proceso. Mismo trade-off que
# agent.presupuesto_runtime._costo_diario_owner: se resetea con cada
# deploy/restart; la persistencia cross-restart no es parte de este riesgo.
_gasto_diario: dict[tuple[str, str], float] = {}
_avisados_80_hoy: set[tuple[str, str]] = set()


def _clave_dia() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _podar_dias_viejos() -> None:
    hoy = _clave_dia()
    for k in [k for k in _gasto_diario if k[1] != hoy]:
        del _gasto_diario[k]
    for k in [k for k in _avisados_80_hoy if k[1] != hoy]:
        _avisados_80_hoy.discard(k)


def gasto_diario_de(agente: str) -> float:
    """Gasto acumulado HOY para `agente` (0.0 si no hay actividad o no se
    declaró agente)."""
    if not agente:
        return 0.0
    return _gasto_diario.get((agente, _clave_dia()), 0.0)


def reiniciar_estado() -> None:
    """Limpia todo el estado in-memory. Uso: tests y un futuro job de reset
    diario explícito (hoy el reset es implícito por cambio de `_clave_dia`)."""
    _gasto_diario.clear()
    _avisados_80_hoy.clear()


def verificar_presupuesto(agente: str) -> None:
    """Lanza `PresupuestoAgenteAgotadoError` si `agente` ya alcanzó/superó su
    tope diario. DEBE llamarse ANTES de cualquier llamada a un proveedor (real
    o simulado) — es una reserva previa, no una revisión posterior."""
    if not agente:
        return  # sin agente declarado, esta dimensión no aplica (compat).
    _podar_dias_viejos()
    limite = limite_usd_dia_agente()
    gastado = gasto_diario_de(agente)
    if gastado >= limite:
        raise PresupuestoAgenteAgotadoError(agente, gastado, limite)


def registrar_gasto(agente: str, costo_usd) -> None:
    """Acumula el costo (real o estimado) de una llamada YA hecha, y avisa
    (una vez por agente/día) al cruzar el 80% del tope diario. No bloquea: el
    bloqueo lo hace `verificar_presupuesto` en el SIGUIENTE intento."""
    if not agente:
        return
    try:
        costo = max(float(costo_usd or 0), 0.0)
    except (TypeError, ValueError):
        costo = 0.0
    _podar_dias_viejos()
    clave = (agente, _clave_dia())
    nuevo = _gasto_diario.get(clave, 0.0) + costo
    _gasto_diario[clave] = nuevo

    limite = limite_usd_dia_agente()
    if limite > 0 and nuevo / limite >= _UMBRAL_AVISO and clave not in _avisados_80_hoy:
        _avisados_80_hoy.add(clave)
        logger.warning(
            "[MULTI_MODEL] presupuesto del agente %r al %.0f%% (%.4f/%.4f USD) "
            "del tope diario",
            agente, (nuevo / limite) * 100, nuevo, limite,
        )
