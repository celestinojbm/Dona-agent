# agent/jobs/worker.py — Worker y dispatcher de jobs creativos

"""
Ejecutor real de jobs. Tiene dos entry-points:

  1. `ejecutar_job_inproc(...)` — llamado por el backend in-proc (dev).
  2. `ejecutar_job(...)` + `WorkerSettings` — usado por arq en prod
     (se levanta con `python -m arq agent.jobs.worker.WorkerSettings`
     o equivalente).

Ambos delegan a `_dispatch(tipo, telefono, params)` que ruta al handler real
según el string `tipo`. En Sprint 1 sólo hay un handler stub (`echo`) para
poder probar la infra end-to-end; los handlers reales (video, web, etc.)
se suman en sprints 2-5.

Contrato del handler:
  async def handler(telefono: str, params: dict) -> int | None
  Retorna `asset_id` si produjo un asset, o None si no.
  Cualquier excepción se captura arriba y se registra como error del job.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Awaitable, Callable

from agent.jobs.queue import marcar_running, marcar_done, marcar_error

logger = logging.getLogger("dona")


# ── Handler registry ───────────────────────────────────────────────────────

_HANDLERS: dict[str, Callable[[str, dict[str, Any]], Awaitable[int | None]]] = {}


def registrar_handler(tipo: str):
    """Decorator para registrar handlers. Usado al final de este archivo y
    en futuros módulos de sprints 2-5."""
    def decor(fn):
        _HANDLERS[tipo] = fn
        return fn
    return decor


def handlers_registrados() -> list[str]:
    return sorted(_HANDLERS.keys())


# ── Dispatcher ──────────────────────────────────────────────────────────────

async def _dispatch(tipo: str, telefono: str, params: dict[str, Any]) -> int | None:
    handler = _HANDLERS.get(tipo)
    if handler is None:
        raise ValueError(f"No hay handler registrado para tipo='{tipo}'")
    return await handler(telefono, params)


async def _ejecutar_con_estado(job_id: int, tipo: str, telefono: str, params: dict) -> None:
    """Loop de ejecución común: marca running → corre handler → marca done/error."""
    await marcar_running(job_id)
    try:
        asset_id = await _dispatch(tipo, telefono, params)
        await marcar_done(job_id, asset_id_resultado=asset_id)
        logger.info(f"[JOBS] Job {job_id} ({tipo}) done asset_id={asset_id}")
    except Exception as e:
        logger.exception(f"[JOBS] Job {job_id} ({tipo}) error: {e}")
        await marcar_error(job_id, str(e))


# ── Entry: in-proc ─────────────────────────────────────────────────────────

async def ejecutar_job_inproc(job_id: int, tipo: str, telefono: str, params: dict) -> None:
    """Ejecutor usado cuando el backend es 'inproc' (sin Redis)."""
    await _ejecutar_con_estado(job_id, tipo, telefono, params)


# ── Entry: arq ──────────────────────────────────────────────────────────────
# Estas funciones son llamadas por arq; no deben ser llamadas directamente.

async def ejecutar_job(ctx, job_id: int, tipo: str, telefono: str, params: dict) -> None:
    """Task de arq. `ctx` es el contexto que inyecta arq (lo ignoramos)."""
    await _ejecutar_con_estado(job_id, tipo, telefono, params)


def _redis_settings():
    # Import diferido para que el módulo cargue sin arq instalado
    from arq.connections import RedisSettings  # type: ignore
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    """Config para `arq` worker. Uso:
        python -m arq agent.jobs.worker.WorkerSettings
    """
    functions = [ejecutar_job]
    max_jobs = int(os.getenv("ARQ_MAX_JOBS", "5"))
    job_timeout = int(os.getenv("ARQ_JOB_TIMEOUT", "600"))  # 10 min
    keep_result = 3600
    # arq espera un atributo RedisSettings, no un método. Se evalúa al
    # definir la clase — requiere arq instalado (ya está en requirements.txt).
    redis_settings = _redis_settings()


# ── Handler de prueba ──────────────────────────────────────────────────────

@registrar_handler("echo")
async def _echo_handler(telefono: str, params: dict) -> int | None:
    """
    Handler trivial que no crea asset — sólo prueba que la infra funciona.
    Usado en tests y como smoke del Sprint 1. Los sprints 2-5 agregan los
    handlers reales (imagen, video, web, ads).
    """
    logger.info(f"[JOBS] echo handler: tel={telefono} params={params}")
    return None
