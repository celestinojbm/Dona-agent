# agent/jobs/queue.py — API unificada de encolado de jobs

"""
Abstrae el backend de jobs (arq o in-proc) detrás de funciones simples.

Contrato:
  - `encolar(tipo, telefono, params)` persiste un `JobCreativo(pending)` y
    dispara la ejecución.
  - El worker es responsable de llamar `marcar_running/done/error` conforme
    avanza.
  - `obtener_estado(job_id)` lee el estado actual desde DB — independiente
    del backend.

`tipo` es un string libre (ej: "generar_imagen", "generar_video_runway").
El worker tiene un dispatch map para saber qué función ejecutar.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger("dona")


def backend_activo() -> str:
    """Retorna 'arq' o 'inproc' según env. 'arq' requiere Redis."""
    val = (os.getenv("JOBS_BACKEND") or "").lower()
    if val in ("arq", "inproc"):
        return val
    # Auto-detección: si hay REDIS_URL, usar arq; sino inproc.
    return "arq" if os.getenv("REDIS_URL") else "inproc"


# ── Persistencia del estado del job ─────────────────────────────────────────

async def _crear_fila(telefono: str, tipo: str, params: dict[str, Any], backend: str) -> int:
    from agent.memory import JobCreativo, async_session

    async with async_session() as session:
        row = JobCreativo(
            telefono=telefono,
            tipo=tipo,
            estado="pending",
            params_json=json.dumps(params, ensure_ascii=False)[:16000],
            backend=backend,
            creado=datetime.utcnow(),
            actualizado=datetime.utcnow(),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


async def _set_estado(
    job_id: int,
    estado: str,
    error_msg: str | None = None,
    asset_id_resultado: int | None = None,
    incrementar_intentos: bool = False,
) -> None:
    from sqlalchemy import update

    from agent.memory import JobCreativo, async_session

    valores: dict[str, Any] = {
        "estado": estado,
        "actualizado": datetime.utcnow(),
    }
    if error_msg is not None:
        valores["error_msg"] = error_msg[:4000]
    if asset_id_resultado is not None:
        valores["asset_id_resultado"] = asset_id_resultado

    async with async_session() as session:
        if incrementar_intentos:
            valores["intentos"] = JobCreativo.intentos + 1
        await session.execute(
            update(JobCreativo).where(JobCreativo.id == job_id).values(**valores)
        )
        await session.commit()


async def marcar_running(job_id: int) -> None:
    await _set_estado(job_id, "running", incrementar_intentos=True)


async def marcar_done(job_id: int, asset_id_resultado: int | None = None) -> None:
    await _set_estado(job_id, "done", asset_id_resultado=asset_id_resultado)


async def marcar_error(job_id: int, error_msg: str) -> None:
    await _set_estado(job_id, "error", error_msg=error_msg)


# ── API: Consulta ───────────────────────────────────────────────────────────

async def obtener_estado(job_id: int) -> dict | None:
    from sqlalchemy import select

    from agent.memory import JobCreativo, async_session

    async with async_session() as session:
        row = (await session.execute(
            select(JobCreativo).where(JobCreativo.id == job_id)
        )).scalar_one_or_none()
        if not row:
            return None
        return _job_a_dict(row)


async def listar_jobs_usuario(telefono: str, limite: int = 10) -> list[dict]:
    from sqlalchemy import select

    from agent.memory import JobCreativo, async_session

    async with async_session() as session:
        rows = (await session.execute(
            select(JobCreativo)
            .where(JobCreativo.telefono == telefono)
            .order_by(JobCreativo.creado.desc())
            .limit(limite)
        )).scalars().all()
        return [_job_a_dict(r) for r in rows]


def _job_a_dict(row) -> dict:
    try:
        params = json.loads(row.params_json or "{}")
    except Exception:
        params = {}
    return {
        "id": row.id,
        "telefono": row.telefono,
        "tipo": row.tipo,
        "estado": row.estado,
        "params": params,
        "asset_id_resultado": row.asset_id_resultado,
        "error_msg": row.error_msg,
        "intentos": row.intentos,
        "backend": row.backend,
        "creado": row.creado.isoformat() if row.creado else None,
        "actualizado": row.actualizado.isoformat() if row.actualizado else None,
    }


# ── API: Encolar ────────────────────────────────────────────────────────────

async def encolar(tipo: str, telefono: str, params: dict[str, Any] | None = None) -> int:
    """
    Crea la fila `JobCreativo(pending)` y despacha la ejecución según backend.
    Retorna el `job_id`. El llamador NO espera la ejecución.
    """
    params = params or {}
    backend = backend_activo()
    job_id = await _crear_fila(telefono, tipo, params, backend)

    if backend == "arq":
        try:
            await _encolar_arq(job_id, tipo, telefono, params)
        except Exception as e:
            logger.error(f"[JOBS] arq encolar falló ({e}) — fallback inproc job_id={job_id}")
            _encolar_inproc(job_id, tipo, telefono, params)
    else:
        _encolar_inproc(job_id, tipo, telefono, params)

    return job_id


# ── Backend: arq (Redis) ───────────────────────────────────────────────────

_arq_pool = None


async def _arq_get_pool():
    global _arq_pool
    if _arq_pool is not None:
        return _arq_pool
    from arq import create_pool  # type: ignore
    from arq.connections import RedisSettings  # type: ignore
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    _arq_pool = await create_pool(RedisSettings.from_dsn(url))
    return _arq_pool


async def _encolar_arq(job_id: int, tipo: str, telefono: str, params: dict) -> None:
    pool = await _arq_get_pool()
    # El worker arq recibe el `tipo` y dispatchea internamente (ver worker.py).
    await pool.enqueue_job("ejecutar_job", job_id, tipo, telefono, params)


# ── Backend: inproc (asyncio.create_task) ──────────────────────────────────

# Referencias FUERTES a las tasks inproc en vuelo. asyncio solo guarda
# referencias débiles a las tasks: sin esto, el GC puede recolectar un job
# a media ejecución (job que desaparece sin done ni error). El set también
# permite drenarlas ordenadamente (tests / shutdown).
_tareas_inproc: set[asyncio.Task] = set()


def _encolar_inproc(job_id: int, tipo: str, telefono: str, params: dict) -> None:
    """
    Dispara la tarea en el loop actual. No persiste entre restarts — en dev
    está bien; en prod, usar arq.
    """
    from agent.jobs.worker import ejecutar_job_inproc  # import diferido para evitar ciclos
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No hay loop corriendo — crear uno temporal (casos raros tipo tests)
        logger.warning(f"[JOBS] Sin loop corriendo para job {job_id} — ignorando (se puede re-encolar después)")
        return
    task = loop.create_task(ejecutar_job_inproc(job_id, tipo, telefono, params))
    _tareas_inproc.add(task)
    task.add_done_callback(_tareas_inproc.discard)


async def esperar_tareas_inproc(timeout: float = 10.0) -> None:
    """Espera a que terminen las tasks inproc en vuelo. Para teardown de
    tests (una task viva al cerrar el loop revienta con 'Event loop is
    closed') y shutdown ordenado. Best-effort: al vencer el timeout deja
    de esperar (no cancela)."""
    pendientes = [t for t in _tareas_inproc if not t.done()]
    if pendientes:
        await asyncio.wait(pendientes, timeout=timeout)
