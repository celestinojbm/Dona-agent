# agent/automation/scheduler.py — T2.1.E · scheduler de mantenimiento

"""
Scheduler periódico opt-in que ejecuta tareas de mantenimiento del
Automation Core. Versión inicial: reconciliación de reservas de
créditos en estado 'preparing' (safety net para crashes entre
billing.cobrar y el UPDATE de la reserva).

Diseño:
  - Se monta sobre el AsyncIOScheduler de APScheduler existente
    (agent/scheduler.py). No introduce un segundo loop ni nueva
    dependencia.
  - Default OFF: requiere AUTOMATION_SCHEDULER_ENABLED=true para
    registrar el job. Esto evita correrlo accidentalmente en local /
    en CI y obliga a opt-in explícito en producción.
  - Anti-concurrencia doble: APScheduler con max_instances=1 +
    asyncio.Lock interno (testeable sin booteado de FastAPI).
  - Manejo de excepciones: cualquier fallo en el tick se loguea y
    NO se propaga · el siguiente tick sigue programado.
  - Sin PII en logs: solo conteos (promoted, marked_failed, intactas).

Variables de entorno:
  AUTOMATION_SCHEDULER_ENABLED          on|true|1 → activado. Default off.
  AUTOMATION_SCHEDULER_INTERVAL_SECONDS  Intervalo entre ticks. Default 300 (5 min). Clamp [30, 3600].
  AUTOMATION_SCHEDULER_RECONCILE_EDAD_SEGUNDOS
                                         Edad mínima para marcar failed. Default 120s. Min 30.
  AUTOMATION_SCHEDULER_RECONCILE_LIMIT   Máximo de filas por tick. Default 500. Clamp [1, 5000].
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger("dona")

# Lock anti-concurrencia. Si un tick previo aún corre, el siguiente se
# salta (no se acumula backlog).
_lock = asyncio.Lock()

# Snapshot in-memory del estado del scheduler · expuesto vía admin
# endpoint. No persiste; se resetea al reinicio del proceso.
_estado: dict[str, Any] = {
    "habilitado": False,
    "intervalo_segundos": 0,
    "max_edad_segundos": 0,
    "limit": 0,
    "ultima_corrida_inicio": None,
    "ultima_corrida_fin": None,
    "ultimo_resultado": None,
    "corridas_totales": 0,
    "corridas_saltadas_por_lock": 0,
    "corridas_fallidas": 0,
}


# ── Helpers de configuración (leen env vars en cada llamada) ─────────


def _truthy(val: str | None) -> bool:
    if not val:
        return False
    return val.strip().lower() in ("1", "true", "yes", "on")


def scheduler_habilitado() -> bool:
    """Lee AUTOMATION_SCHEDULER_ENABLED. Default: deshabilitado."""
    return _truthy(os.getenv("AUTOMATION_SCHEDULER_ENABLED"))


def intervalo_segundos() -> int:
    """Lee AUTOMATION_SCHEDULER_INTERVAL_SECONDS. Default 300. Clamp [30, 3600]."""
    try:
        v = int(os.getenv("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", "300") or 300)
    except ValueError:
        v = 300
    return max(30, min(3600, v))


def edad_min_segundos() -> int:
    """Lee AUTOMATION_SCHEDULER_RECONCILE_EDAD_SEGUNDOS. Default 120. Min 30."""
    try:
        v = int(os.getenv("AUTOMATION_SCHEDULER_RECONCILE_EDAD_SEGUNDOS", "120") or 120)
    except ValueError:
        v = 120
    return max(30, v)


def limit_corrida() -> int:
    """Lee AUTOMATION_SCHEDULER_RECONCILE_LIMIT. Default 500. Clamp [1, 5000]."""
    try:
        v = int(os.getenv("AUTOMATION_SCHEDULER_RECONCILE_LIMIT", "500") or 500)
    except ValueError:
        v = 500
    return max(1, min(5000, v))


# ── Tick de trabajo ──────────────────────────────────────────────────


async def tick_reconciliacion_reservas() -> dict[str, Any]:
    """Una ejecución del scheduler: llama reconciliar_reservas con los
    parámetros leídos de env y registra el resultado en `_estado`.

    Returns:
        {"status": "ok"|"skipped_lock"|"error", ...} · nunca raises.
    """
    if _lock.locked():
        _estado["corridas_saltadas_por_lock"] += 1
        logger.info(
            "[AUT-SCHED] tick saltado · ciclo anterior aún corre"
        )
        return {"status": "skipped_lock"}

    async with _lock:
        inicio = datetime.utcnow()
        _estado["ultima_corrida_inicio"] = inicio.isoformat()
        try:
            from agent.automation.credits import reconciliar_reservas
            resultado = await reconciliar_reservas(
                max_edad_segundos=edad_min_segundos(),
                limit=limit_corrida(),
                dry_run=False,
            )
            _estado["corridas_totales"] += 1
            _estado["ultimo_resultado"] = resultado
            promoted = int(resultado.get("promoted", 0) or 0)
            failed = int(resultado.get("marked_failed", 0) or 0)
            intactas = int(resultado.get("intactas", 0) or 0)
            if promoted or failed:
                logger.warning(
                    f"[AUT-SCHED] reconciliación con cambios · "
                    f"promoted={promoted} marked_failed={failed} "
                    f"intactas={intactas}"
                )
            else:
                logger.debug(
                    f"[AUT-SCHED] reconciliación OK · "
                    f"intactas={intactas}"
                )
            return {"status": "ok", "resultado": resultado}
        except Exception as e:
            _estado["corridas_fallidas"] += 1
            logger.error(
                f"[AUT-SCHED] reconciliación falló "
                f"({type(e).__name__}): {str(e)[:200]}"
            )
            return {"status": "error", "error": type(e).__name__}
        finally:
            _estado["ultima_corrida_fin"] = datetime.utcnow().isoformat()


# ── Registro en APScheduler ──────────────────────────────────────────


def registrar_automation_jobs(apscheduler) -> bool:
    """Registra el job de reconciliación en el AsyncIOScheduler global.

    No-op si AUTOMATION_SCHEDULER_ENABLED no está en truthy. Esto
    permite que main.py llame siempre a esta función desde el lifespan
    sin temor de que algún ambiente la dispare sin opt-in.

    Returns: True si quedó registrado · False si está deshabilitado.
    Cualquier excepción se loguea y retorna False (no rompe startup).
    """
    try:
        habilitado = scheduler_habilitado()
        if not habilitado:
            _estado["habilitado"] = False
            logger.info(
                "[AUT-SCHED] deshabilitado · "
                "AUTOMATION_SCHEDULER_ENABLED no está activo"
            )
            return False

        intervalo = intervalo_segundos()
        edad = edad_min_segundos()
        limit = limit_corrida()

        apscheduler.add_job(
            tick_reconciliacion_reservas,
            trigger="interval",
            seconds=intervalo,
            id="automation_reconcile_reservas",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        _estado["habilitado"] = True
        _estado["intervalo_segundos"] = intervalo
        _estado["max_edad_segundos"] = edad
        _estado["limit"] = limit
        logger.info(
            f"[AUT-SCHED] reconciliación registrada · "
            f"intervalo={intervalo}s · max_edad={edad}s · limit={limit}"
        )
        return True
    except Exception as e:
        # No rompemos startup por una falla del scheduler de mantenimiento.
        _estado["habilitado"] = False
        logger.error(
            f"[AUT-SCHED] error registrando job "
            f"({type(e).__name__}): {str(e)[:200]}"
        )
        return False


def obtener_estado() -> dict[str, Any]:
    """Snapshot del estado actual · para admin endpoint."""
    # Releer config en cada llamada (env podría haber cambiado).
    snapshot = dict(_estado)
    snapshot["habilitado_actual"] = scheduler_habilitado()
    snapshot["intervalo_actual_segundos"] = intervalo_segundos()
    snapshot["max_edad_actual_segundos"] = edad_min_segundos()
    snapshot["limit_actual"] = limit_corrida()
    return snapshot
