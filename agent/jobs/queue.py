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


# ── Observabilidad del fallback inproc ──────────────────────────────────────
#
# Correr un job pagado como asyncio.Task dentro del proceso web es un riesgo:
# si Render redeploya a media ejecución, la Task muere y el job queda "running"
# para siempre sin reembolso (ese es el defecto ARQ-01; el reaper de arranque
# lo recupera post-mortem, pero cada activación del fallback merece una alerta
# ANTES para que el operador lo vea). Contamos las activaciones y, si el proceso
# host registró un callback (main.py lo hace con la métrica in-memory), lo
# notificamos. Sin el callback esto igual queda en el WARNING del log.

_inproc_fallback_total = 0
_on_inproc_fallback = None  # callback opcional: () -> None


def registrar_callback_inproc_fallback(cb) -> None:
    """Registra un callback que se dispara cada vez que un job cae al backend
    inproc (sea por diseño —sin Redis— o por fallo de arq al encolar). main.py
    lo usa para incrementar un contador expuesto en /admin/metrics."""
    global _on_inproc_fallback
    _on_inproc_fallback = cb


def inproc_fallback_total() -> int:
    """Total de jobs despachados por el backend inproc en este proceso."""
    return _inproc_fallback_total


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

    Antes esto era SILENCIOSO: un job pagado corriendo dentro del proceso web
    no dejaba rastro. Ahora cada activación cuenta y avisa (WARNING + métrica)
    porque si el proceso muere a media ejecución el usuario pierde créditos
    (defecto ARQ-01). Observarlo permite detectar en prod que arq no está
    tomando los jobs (Redis caído, sin REDIS_URL, etc.).
    """
    global _inproc_fallback_total
    _inproc_fallback_total += 1
    logger.warning(
        f"[JOBS] Fallback INPROC activo — job {job_id} ({tipo}) corre como "
        f"asyncio.Task dentro del proceso web. Si el proceso muere a media "
        f"ejecución el job queda huérfano (el reaper de arranque lo recupera). "
        f"total_inproc={_inproc_fallback_total}"
    )
    if _on_inproc_fallback is not None:
        try:
            _on_inproc_fallback()
        except Exception:
            logger.exception("[JOBS] callback de métrica inproc falló")

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


# ── Reaper de arranque: recupera jobs huérfanos (defecto ARQ-01) ────────────
#
# Un job "running" cuya `actualizado` es ANTERIOR al arranque de ESTE proceso
# fue marcado running por un proceso que ya murió (redeploy de Render, crash,
# OOM). Con el backend inproc, su asyncio.Task murió con el proceso: el job
# nunca llegará a done ni a error por sí solo, y el usuario pagó sin recibir
# nada. El reaper lo cierra como "error" y dispara el reembolso normal.
#
# Detección del huérfano (campo + umbral):
#   - Campo: `JobCreativo.actualizado`. `marcar_running` lo setea a utcnow()
#     al arrancar el job. Es el timestamp que prueba "cuándo un proceso lo
#     tomó por última vez".
#   - Umbral: `corte`, capturado al INICIO del reaper (≈ arranque del proceso).
#     Huérfano ⇔ estado == "running" AND actualizado < corte.
#   - Un job legítimamente en curso del proceso ACTUAL siempre tiene
#     actualizado >= corte (lo marcó este mismo proceso, después del corte),
#     así que nunca se toca. El margen `holgura_s` da aire extra para relojes
#     no monotónicos entre inserción de fila y corte.

async def reaper_jobs_huerfanos(
    corte: datetime | None = None,
    holgura_s: float = 5.0,
) -> list[int]:
    """
    Busca jobs en estado "running" con `actualizado` anterior a `corte` (menos
    una holgura), los marca "error" y reembolsa los créditos ya cobrados.

    `corte` por defecto es utcnow() — apropiado para llamarlo al arranque de
    FastAPI: cualquier "running" preexistente es de un proceso muerto. Se
    parametriza para poder testearlo con un corte explícito.

    Retorna la lista de `job_id` reanimados (marcados error + reembolsados).
    Es idempotente: reembolsa vía `_reembolsar(job_id=...)`, que ancla el
    crédito a la clave `reembolso_job:{job_id}`, así que correrlo dos veces (dos
    instancias web al arrancar, o un restart a media faena) NO doble-acredita.
    """
    from datetime import timedelta

    from sqlalchemy import select

    from agent.memory import JobCreativo, async_session

    if corte is None:
        corte = datetime.utcnow()
    umbral = corte - timedelta(seconds=max(0.0, holgura_s))

    # Snapshot de candidatos (no mutamos mientras iteramos el cursor).
    async with async_session() as session:
        candidatos = (await session.execute(
            select(JobCreativo).where(
                JobCreativo.estado == "running",
                JobCreativo.actualizado < umbral,
            )
        )).scalars().all()
        # Materializar los campos que necesitamos ANTES de cerrar la sesión.
        pendientes = [
            (r.id, r.tipo, r.telefono, _costo_creditos_de_params(r.params_json))
            for r in candidatos
        ]

    if not pendientes:
        return []

    logger.warning(
        f"[JOBS] Reaper: {len(pendientes)} job(s) huérfano(s) detectado(s) "
        f"(running con actualizado < {umbral.isoformat()}). Marcando error + "
        f"reembolsando."
    )

    from agent.jobs.handlers_creativos import _reembolsar

    reanimados: list[int] = []
    for job_id, tipo, telefono, costo in pendientes:
        # Reembolsar ANTES de marcar error. Orden deliberado: el reembolso es
        # idempotente por `job_id` (la clave `reembolso_job:{job_id}` ancla el
        # crédito a ESTE job), así que si `marcar_error` fallara justo después,
        # la próxima corrida del reaper —el job sigue 'running'— re-reembolsa
        # como no-op y re-intenta el error. Al revés (error primero) sacaríamos
        # el job del conjunto de candidatos y podríamos perder el reembolso para
        # siempre. Comparte la MISMA clave que el handler (BILL-01): si el
        # proceso murió tras reembolsar el handler pero antes de marcar estado,
        # el reaper no doble-acredita.
        if costo > 0:
            try:
                await _reembolsar(
                    telefono,
                    costo,
                    "job huérfano (proceso reiniciado)",
                    scope=tipo or "job",
                    job_id=job_id,
                )
            except Exception:
                logger.exception(f"[JOBS] Reaper: no pude reembolsar job {job_id}")
                # No marcamos error: dejarlo 'running' permite reintentar el
                # reembolso en el próximo arranque en vez de perderlo.
                continue

        try:
            await marcar_error(
                job_id,
                "Proceso reiniciado a media ejecución — job huérfano recuperado "
                "por el reaper de arranque (ARQ-01). Créditos reembolsados.",
            )
        except Exception:
            logger.exception(f"[JOBS] Reaper: no pude marcar error job {job_id}")
            # El reembolso ya se aplicó (idempotente); el estado se corrige en
            # el próximo arranque. Igual lo contamos como recuperado.
        reanimados.append(job_id)

    logger.warning(f"[JOBS] Reaper: recuperados {len(reanimados)} job(s): {reanimados}")
    return reanimados


def _costo_creditos_de_params(params_json: str | None) -> int:
    """Extrae `costo_creditos` del params_json del job (lo que cobró
    confirmar_X antes de encolar). 0 si no hay o no parsea."""
    try:
        params = json.loads(params_json or "{}")
        return int(params.get("costo_creditos", 0) or 0)
    except Exception:
        return 0
