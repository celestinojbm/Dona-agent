# agent/app_first/ejecucion.py — Runner de ejecuciones de agentes (J7.2/J7.3)

"""
Ciclo de una tarea:

  encolar_tarea ─► app_ejecuciones(encolada) ─► despachar (arq / inproc)
      │                                   └─ con DONA_WORKER_ENABLED apagado queda encolada
      ▼
  ejecutar(ejecucion_id)
      1. RECLAMA con un UPDATE atómico (encolada → en_curso + lease). Si otro
         worker la reclamó, no hace nada.
      2. Si la tarea fue cancelada → ejecución cancelada.
      3. Si hay una aprobación ya concedida → ejecuta la operación reservada
         con efecto IDEMPOTENTE (app_efectos) y pasa a revisión.
      4. Presupuesto ANTES de llamar al proveedor: si no alcanza → tarea
         bloqueada (presupuesto_agotado) sin llamar.
      5. Proveedor (simulado en el piloto). Fallo → ejecución fallida
         (proveedor_no_disponible), tarea fallida.
      6. Consumo + evidencia (sin duplicar: única por ejecución y hash).
      7. Operación reservada solicitada → app_aprobaciones(pendiente); la
         tarea queda necesita_aprobacion. Nada se ejecuta sin decisión humana.
      8. Revisión del agente responsable contra los criterios del proyecto →
         completada o bloqueada (criterios_no_cumplidos).

  reaper: ejecuciones en_curso con lease vencido (worker caído) → abandonada
  y, si quedan intentos, un intento nuevo encolado.

Límites (documentados, no ocultos):
  - Cancelar no interrumpe una llamada al proveedor ya en vuelo: termina y
    su resultado se descarta.
  - Los agentes no son procesos permanentes: solo existen ejecuciones con
    estado y hora reales.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from agent.app_first import models as m
from agent.app_first.proveedores import (
    OPERACIONES_RESERVADAS,
    ProveedorNoDisponible,
    obtener_proveedor,
)
from agent.app_first.repositorio import (
    Conflicto,
    Contexto,
    NoEncontrado,
    SinPermiso,
    ValorInvalido,
    _actividad,
    _del_workspace,
    _sesion,
)

logger = logging.getLogger("dona")

LEASE = timedelta(minutes=5)
MAX_INTENTOS = 3


def _ahora() -> datetime:
    return datetime.utcnow()


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ── Encolado ────────────────────────────────────────────────────────────


async def _crear_ejecucion(session, tarea: m.AppTarea, intento: int) -> int:
    clave = f"tarea:{tarea.id}:intento:{intento}"
    ej = m.AppEjecucion(
        workspace_id=tarea.workspace_id,
        tarea_id=tarea.id,
        agente_id=tarea.asignada_a_agente_id,
        intento=intento,
        clave_idempotencia=clave,
    )
    session.add(ej)
    await session.flush()
    _actividad(session, tarea.workspace_id, "sistema", None, "ejecucion_encolada", "ejecucion", ej.id,
               {"tarea_id": tarea.id, "intento": intento})
    return ej.id


async def encolar_tarea(ctx: Contexto, tarea_id: int, despachar: bool = True) -> int:
    """Encola un intento nuevo para una tarea pendiente con agente asignado.

    Idempotente: encolar dos veces la misma tarea pendiente (doble clic,
    reintento de red) devuelve la MISMA ejecución encolada.
    """
    async with _sesion() as session:
        tarea = await _del_workspace(session, m.AppTarea, tarea_id, ctx)
        if tarea.asignada_a_agente_id is None:
            raise ValorInvalido("la tarea no tiene agente asignado")
        if tarea.estado != "pendiente":
            raise Conflicto(f"la tarea está {tarea.estado}, no pendiente")
        existente = await session.scalar(
            select(m.AppEjecucion.id).where(
                m.AppEjecucion.tarea_id == tarea.id, m.AppEjecucion.estado == "encolada"
            )
        )
        if existente:
            return existente
        intentos = await session.scalar(
            select(func.count(m.AppEjecucion.id)).where(m.AppEjecucion.tarea_id == tarea.id)
        )
        try:
            ej_id = await _crear_ejecucion(session, tarea, (intentos or 0) + 1)
            await session.commit()
        except IntegrityError:
            # Carrera con otro encolado del mismo intento: usar el que ganó.
            await session.rollback()
            ej_id = await session.scalar(
                select(m.AppEjecucion.id).where(
                    m.AppEjecucion.tarea_id == tarea_id, m.AppEjecucion.estado == "encolada"
                )
            )
            if ej_id is None:
                raise
    if despachar:
        await despachar_ejecucion(ej_id)
    return ej_id


_TAREAS_INPROC: set[asyncio.Task] = set()


async def despachar_ejecucion(ejecucion_id: int) -> str:
    """Entrega la ejecución a la cola existente. Devuelve el backend usado."""
    from agent.efectos import efecto_habilitado
    from agent.jobs.queue import backend_activo

    if not efecto_habilitado("worker"):
        logger.warning(f"[APP-FIRST] ejecución {ejecucion_id} queda encolada: DONA_WORKER_ENABLED != true")
        return "ninguno"
    if backend_activo() == "arq":
        from agent.jobs.queue import _arq_get_pool

        pool = await _arq_get_pool()
        await pool.enqueue_job("app_ejecutar", ejecucion_id, _job_id=f"app_ejecucion:{ejecucion_id}")
        return "arq"
    tarea = asyncio.create_task(ejecutar(ejecucion_id))
    _TAREAS_INPROC.add(tarea)
    tarea.add_done_callback(_TAREAS_INPROC.discard)
    return "inproc"


# ── Ejecución ───────────────────────────────────────────────────────────


async def _reclamar(ejecucion_id: int) -> bool:
    ahora = _ahora()
    async with _sesion() as session:
        res = await session.execute(
            update(m.AppEjecucion)
            .where(m.AppEjecucion.id == ejecucion_id, m.AppEjecucion.estado == "encolada")
            .values(estado="en_curso", lease_hasta=ahora + LEASE,
                    iniciada=func.coalesce(m.AppEjecucion.iniciada, ahora))
        )
        await session.commit()
        return res.rowcount == 1


async def _cerrar(session, ej: m.AppEjecucion, estado: str, error: str = "") -> None:
    ej.estado = estado
    ej.error_codigo = error
    ej.lease_hasta = None
    if estado in ("terminada", "fallida", "cancelada", "abandonada"):
        ej.terminada = _ahora()
    _actividad(session, ej.workspace_id, "sistema", None, f"ejecucion_{estado}", "ejecucion", ej.id,
               {"tarea_id": ej.tarea_id, "error": error})


def _tarea_a(session, tarea: m.AppTarea, estado: str, motivo: str = "", actor: str = "sistema",
             actor_id: int | None = None) -> None:
    anterior = tarea.estado
    tarea.estado = estado
    tarea.motivo_bloqueo = motivo
    tarea.actualizado = _ahora()
    _actividad(session, tarea.workspace_id, actor, actor_id, "tarea_estado", "tarea", tarea.id,
               {"de": anterior, "a": estado, "motivo_bloqueo": motivo})


async def _efecto_idempotente(session, ej: m.AppEjecucion, aprobacion: m.AppAprobacion) -> dict[str, Any]:
    """Ejecuta la operación reservada aprobada una sola vez por tarea+operación."""
    clave = f"efecto:tarea:{ej.tarea_id}:{aprobacion.operacion}"
    previo = await session.scalar(select(m.AppEfecto).where(m.AppEfecto.clave_idempotencia == clave))
    if previo is not None:
        return json.loads(previo.resultado_json)
    # Piloto: el efecto es simulado (no publica fuera de Dona).
    resultado = {"operacion": aprobacion.operacion, "estado": "publicado_en_dona", "simulado": True}
    session.add(m.AppEfecto(workspace_id=ej.workspace_id, clave_idempotencia=clave,
                            operacion=aprobacion.operacion, ejecucion_id=ej.id,
                            resultado_json=json.dumps(resultado), simulado=True))
    await session.flush()
    return resultado


def _evidencia(session, ej: m.AppEjecucion, tipo: str, contenido: str) -> None:
    session.add(m.AppEvidencia(workspace_id=ej.workspace_id, ejecucion_id=ej.id, tipo=tipo,
                               contenido=contenido, hash_sha256=_hash(contenido)))


async def _guardar_evidencia_sin_duplicar(ejecucion_id: int, tipo: str, contenido: str) -> None:
    async with _sesion() as session:
        ej = await session.get(m.AppEjecucion, ejecucion_id)
        _evidencia(session, ej, tipo, contenido)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()  # misma evidencia ya registrada: no se duplica


async def _revisar_y_cerrar(ejecucion_id: int) -> str:
    """Revisión del responsable contra los criterios y cierre de la tarea."""
    async with _sesion() as session:
        ej = await session.get(m.AppEjecucion, ejecucion_id)
        tarea = await session.get(m.AppTarea, ej.tarea_id)
        proyecto = await session.get(m.AppProyecto, tarea.proyecto_id)
        responsable = await session.scalar(
            select(m.AppAgente).where(m.AppAgente.workspace_id == ej.workspace_id,
                                      m.AppAgente.rol == "responsable").order_by(m.AppAgente.id)
        )
        evidencias = (await session.scalars(
            select(m.AppEvidencia.contenido)
            .join(m.AppEjecucion, m.AppEjecucion.id == m.AppEvidencia.ejecucion_id)
            .where(m.AppEjecucion.tarea_id == tarea.id)
        )).all()
        criterios = json.loads(proyecto.criterios_aceptacion_json or "[]")
        if responsable is None:
            _tarea_a(session, tarea, "completada")
            _actividad(session, ej.workspace_id, "sistema", None, "revision_omitida", "tarea", tarea.id,
                       {"motivo": "sin_agente_responsable"})
        else:
            try:
                revision = await obtener_proveedor(responsable.modelo).revisar(
                    criterios=criterios, evidencias=list(evidencias)
                )
            except ProveedorNoDisponible:
                await _cerrar(session, ej, "fallida", "proveedor_no_disponible")
                _tarea_a(session, tarea, "fallida")
                await session.commit()
                return "fallida"
            _evidencia(session, ej, "registro", revision.comentario)
            if revision.cumple:
                _tarea_a(session, tarea, "completada", actor="agente", actor_id=responsable.id)
            else:
                _tarea_a(session, tarea, "bloqueada", "criterios_no_cumplidos", "agente", responsable.id)
        await _cerrar(session, ej, "terminada")
        try:
            await session.commit()
        except IntegrityError:  # evidencia de revisión idéntica ya existente
            await session.rollback()
            return await _revisar_y_cerrar_sin_evidencia(ejecucion_id)
        return tarea.estado


async def _revisar_y_cerrar_sin_evidencia(ejecucion_id: int) -> str:
    async with _sesion() as session:
        ej = await session.get(m.AppEjecucion, ejecucion_id)
        tarea = await session.get(m.AppTarea, ej.tarea_id)
        if tarea.estado not in m.ESTADOS_TAREA_TERMINALES:
            _tarea_a(session, tarea, "completada")
        await _cerrar(session, ej, "terminada")
        await session.commit()
        return tarea.estado


async def ejecutar(ejecucion_id: int) -> str | None:
    """Procesa una ejecución. Devuelve el estado final de la TAREA, o None si
    la ejecución no se pudo reclamar (otro worker, o ya no estaba encolada)."""
    if not await _reclamar(ejecucion_id):
        return None

    async with _sesion() as session:
        ej = await session.get(m.AppEjecucion, ejecucion_id)
        tarea = await session.get(m.AppTarea, ej.tarea_id)
        agente = await session.get(m.AppAgente, ej.agente_id)
        proyecto = await session.get(m.AppProyecto, tarea.proyecto_id)

        if tarea.estado == "cancelada":
            await _cerrar(session, ej, "cancelada")
            await session.commit()
            return "cancelada"
        if tarea.estado == "pendiente":
            _tarea_a(session, tarea, "en_ejecucion")

        aprobada = await session.scalar(
            select(m.AppAprobacion).where(m.AppAprobacion.ejecucion_id == ej.id,
                                          m.AppAprobacion.estado == "aprobada")
        )
        if aprobada is not None:
            resultado = await _efecto_idempotente(session, ej, aprobada)
            await session.commit()
            await _guardar_evidencia_sin_duplicar(ej.id, "registro", json.dumps(resultado, ensure_ascii=False))
            return await _revisar_y_cerrar(ej.id)

        try:
            proveedor = obtener_proveedor(agente.modelo)
        except ProveedorNoDisponible:
            await _cerrar(session, ej, "fallida", "proveedor_no_disponible")
            _tarea_a(session, tarea, "fallida")
            await session.commit()
            return "fallida"

        # Presupuesto ANTES de llamar al proveedor.
        consumido = await session.scalar(
            select(func.coalesce(func.sum(m.AppConsumo.unidades), 0))
            .join(m.AppEjecucion, m.AppEjecucion.id == m.AppConsumo.ejecucion_id)
            .where(m.AppEjecucion.agente_id == agente.id)
        )
        estimado = proveedor.costo_estimado(tarea.titulo, tarea.descripcion)
        if consumido + estimado > agente.presupuesto_max_unidades:
            await _cerrar(session, ej, "fallida", "presupuesto_agotado")
            _tarea_a(session, tarea, "bloqueada", "presupuesto_agotado")
            await session.commit()
            return "bloqueada"
        datos = dict(instrucciones=agente.instrucciones, titulo=tarea.titulo, descripcion=tarea.descripcion,
                     objetivo=proyecto.objetivo,
                     herramientas=tuple(json.loads(agente.herramientas_permitidas_json or "[]")))
        await session.commit()

    try:
        resultado = await proveedor.generar(**datos)
    except ProveedorNoDisponible:
        async with _sesion() as session:
            ej = await session.get(m.AppEjecucion, ejecucion_id)
            tarea = await session.get(m.AppTarea, ej.tarea_id)
            await _cerrar(session, ej, "fallida", "proveedor_no_disponible")
            if tarea.estado != "cancelada":
                _tarea_a(session, tarea, "fallida")
            await session.commit()
        return "fallida"

    async with _sesion() as session:
        ej = await session.get(m.AppEjecucion, ejecucion_id)
        tarea = await session.get(m.AppTarea, ej.tarea_id)
        session.add(m.AppConsumo(workspace_id=ej.workspace_id, ejecucion_id=ej.id,
                                 proveedor=proveedor.nombre, unidades=resultado.unidades,
                                 simulado=resultado.simulado))
        ej.unidades_consumidas += resultado.unidades
        if tarea.estado == "cancelada":  # se canceló mientras el proveedor trabajaba
            await _cerrar(session, ej, "cancelada")
            await session.commit()
            return "cancelada"
        await session.commit()

    await _guardar_evidencia_sin_duplicar(ejecucion_id, "texto", resultado.texto)

    if resultado.operaciones_solicitadas:
        async with _sesion() as session:
            ej = await session.get(m.AppEjecucion, ejecucion_id)
            tarea = await session.get(m.AppTarea, ej.tarea_id)
            agente = await session.get(m.AppAgente, ej.agente_id)
            permitidas = set(json.loads(agente.herramientas_permitidas_json or "[]"))
            for op in resultado.operaciones_solicitadas:
                if op not in OPERACIONES_RESERVADAS or op not in permitidas:
                    await _cerrar(session, ej, "fallida", "herramienta_no_permitida")
                    _tarea_a(session, tarea, "bloqueada", "herramienta_no_permitida")
                    await session.commit()
                    return "bloqueada"
            for op in resultado.operaciones_solicitadas:
                session.add(m.AppAprobacion(
                    workspace_id=ej.workspace_id, ejecucion_id=ej.id, operacion=op,
                    riesgo=OPERACIONES_RESERVADAS[op],
                    preview_json=json.dumps({"operacion": op, "resumen": resultado.texto[:500],
                                             "simulado": resultado.simulado}, ensure_ascii=False),
                ))
            ej.estado = "esperando_aprobacion"
            ej.lease_hasta = None
            _tarea_a(session, tarea, "necesita_aprobacion")
            _actividad(session, ej.workspace_id, "agente", agente.id, "aprobacion_solicitada",
                       "ejecucion", ej.id, {"operaciones": list(resultado.operaciones_solicitadas)})
            await session.commit()
            return "necesita_aprobacion"

    return await _revisar_y_cerrar(ejecucion_id)


# ── Decisiones humanas ──────────────────────────────────────────────────


async def decidir_aprobacion(ctx: Contexto, aprobacion_id: int, aprobar: bool,
                             despachar: bool = True) -> str:
    """Aprueba o rechaza una operación reservada. Solo el responsable del
    proyecto o un owner/admin. Devuelve el estado nuevo de la aprobación."""
    async with _sesion() as session:
        ap = await _del_workspace(session, m.AppAprobacion, aprobacion_id, ctx)
        ej = await session.get(m.AppEjecucion, ap.ejecucion_id)
        tarea = await session.get(m.AppTarea, ej.tarea_id)
        proyecto = await session.get(m.AppProyecto, tarea.proyecto_id)
        if not (ctx.es_admin or ctx.usuario_id == proyecto.responsable_usuario_id):
            raise SinPermiso("solo el responsable del proyecto o un admin decide")
        if ap.estado != "pendiente":
            raise Conflicto(f"la aprobación ya está {ap.estado}")
        ap.estado = "aprobada" if aprobar else "rechazada"
        ap.decidida_por = ctx.usuario_id
        ap.decidida_en = _ahora()
        _actividad(session, ctx.workspace_id, "usuario", ctx.usuario_id, f"aprobacion_{ap.estado}",
                   "aprobacion", ap.id, {"operacion": ap.operacion})
        if aprobar:
            ej.estado = "encolada"
            _tarea_a(session, tarea, "en_ejecucion", actor="usuario", actor_id=ctx.usuario_id)
        else:
            await _cerrar(session, ej, "cancelada")
            _tarea_a(session, tarea, "bloqueada", "aprobacion_rechazada", "usuario", ctx.usuario_id)
        await session.commit()
        estado, ej_id = ap.estado, ej.id
    if aprobar and despachar:
        await despachar_ejecucion(ej_id)
    return estado


async def cancelar_tarea(ctx: Contexto, tarea_id: int) -> None:
    async with _sesion() as session:
        tarea = await _del_workspace(session, m.AppTarea, tarea_id, ctx)
        if tarea.estado in m.ESTADOS_TAREA_TERMINALES:
            raise Conflicto(f"la tarea ya está {tarea.estado}")
        _tarea_a(session, tarea, "cancelada", actor="usuario", actor_id=ctx.usuario_id)
        activas = (await session.scalars(
            select(m.AppEjecucion).where(m.AppEjecucion.tarea_id == tarea.id,
                                         m.AppEjecucion.estado.in_(("encolada", "esperando_aprobacion")))
        )).all()
        for ej in activas:
            await _cerrar(session, ej, "cancelada")
        await session.execute(
            update(m.AppAprobacion)
            .where(m.AppAprobacion.ejecucion_id.in_(
                select(m.AppEjecucion.id).where(m.AppEjecucion.tarea_id == tarea.id)),
                m.AppAprobacion.estado == "pendiente")
            .values(estado="caducada")
        )
        # Una ejecución en_curso termina su paso actual y ve la cancelación.
        await session.commit()


async def reintentar_tarea(ctx: Contexto, tarea_id: int, despachar: bool = True) -> int:
    """Una tarea fallida o bloqueada vuelve a pendiente y se encola un intento nuevo."""
    async with _sesion() as session:
        tarea = await _del_workspace(session, m.AppTarea, tarea_id, ctx)
        if tarea.estado not in ("fallida", "bloqueada"):
            raise Conflicto(f"solo se reintenta una tarea fallida o bloqueada (está {tarea.estado})")
        _tarea_a(session, tarea, "pendiente", actor="usuario", actor_id=ctx.usuario_id)
        await session.commit()
    return await encolar_tarea(ctx, tarea_id, despachar=despachar)


# ── Recuperación ────────────────────────────────────────────────────────


async def reaper(ahora: datetime | None = None, despachar: bool = True) -> list[int]:
    """Ejecuciones en_curso con lease vencido → abandonada; intento nuevo si
    quedan. Seguro con varios procesos: cada fila se toma con un UPDATE
    condicionado. Devuelve las ejecuciones abandonadas."""
    ahora = ahora or _ahora()
    abandonadas: list[int] = []
    nuevas: list[int] = []
    async with _sesion() as session:
        candidatas = (await session.scalars(
            select(m.AppEjecucion.id).where(m.AppEjecucion.estado == "en_curso",
                                            m.AppEjecucion.lease_hasta < ahora)
        )).all()
    for ej_id in candidatas:
        async with _sesion() as session:
            res = await session.execute(
                update(m.AppEjecucion)
                .where(m.AppEjecucion.id == ej_id, m.AppEjecucion.estado == "en_curso",
                       m.AppEjecucion.lease_hasta < ahora)
                .values(estado="abandonada", lease_hasta=None, terminada=ahora,
                        error_codigo="lease_vencido")
            )
            if res.rowcount != 1:
                await session.rollback()
                continue
            ej = await session.get(m.AppEjecucion, ej_id)
            tarea = await session.get(m.AppTarea, ej.tarea_id)
            _actividad(session, ej.workspace_id, "sistema", None, "ejecucion_abandonada", "ejecucion", ej.id,
                       {"tarea_id": tarea.id, "intento": ej.intento})
            abandonadas.append(ej_id)
            if tarea.estado == "cancelada":
                await session.commit()
                continue
            if ej.intento < MAX_INTENTOS:
                tarea.estado = "pendiente"
                tarea.actualizado = ahora
                nuevas.append(await _crear_ejecucion(session, tarea, ej.intento + 1))
            else:
                _tarea_a(session, tarea, "fallida")
            await session.commit()
    if despachar:
        for nueva in nuevas:
            await despachar_ejecucion(nueva)
    return abandonadas


# ── Lectura para la UI ──────────────────────────────────────────────────


async def listar_ejecuciones(ctx: Contexto, tarea_id: int) -> list[dict[str, Any]]:
    async with _sesion() as session:
        await _del_workspace(session, m.AppTarea, tarea_id, ctx)
        filas = (await session.scalars(
            select(m.AppEjecucion).where(m.AppEjecucion.workspace_id == ctx.workspace_id,
                                         m.AppEjecucion.tarea_id == tarea_id).order_by(m.AppEjecucion.id)
        )).all()
    return [{"id": e.id, "agente_id": e.agente_id, "intento": e.intento, "estado": e.estado,
             "error_codigo": e.error_codigo, "unidades_consumidas": e.unidades_consumidas,
             "iniciada": e.iniciada.isoformat() if e.iniciada else None,
             "terminada": e.terminada.isoformat() if e.terminada else None} for e in filas]


async def listar_evidencias(ctx: Contexto, tarea_id: int) -> list[dict[str, Any]]:
    async with _sesion() as session:
        await _del_workspace(session, m.AppTarea, tarea_id, ctx)
        filas = (await session.scalars(
            select(m.AppEvidencia)
            .join(m.AppEjecucion, m.AppEjecucion.id == m.AppEvidencia.ejecucion_id)
            .where(m.AppEvidencia.workspace_id == ctx.workspace_id, m.AppEjecucion.tarea_id == tarea_id)
            .order_by(m.AppEvidencia.id)
        )).all()
    return [{"id": x.id, "ejecucion_id": x.ejecucion_id, "tipo": x.tipo, "contenido": x.contenido,
             "hash_sha256": x.hash_sha256, "creado": x.creado.isoformat() if x.creado else None}
            for x in filas]


async def listar_aprobaciones(ctx: Contexto, solo_pendientes: bool = True) -> list[dict[str, Any]]:
    consulta = select(m.AppAprobacion).where(m.AppAprobacion.workspace_id == ctx.workspace_id)
    if solo_pendientes:
        consulta = consulta.where(m.AppAprobacion.estado == "pendiente")
    async with _sesion() as session:
        filas = (await session.scalars(consulta.order_by(m.AppAprobacion.id))).all()
    return [{"id": a.id, "ejecucion_id": a.ejecucion_id, "operacion": a.operacion, "riesgo": a.riesgo,
             "preview": json.loads(a.preview_json or "{}"), "estado": a.estado} for a in filas]


__all__ = [
    "NoEncontrado", "encolar_tarea", "despachar_ejecucion", "ejecutar", "decidir_aprobacion",
    "cancelar_tarea", "reintentar_tarea", "reaper", "listar_ejecuciones", "listar_evidencias",
    "listar_aprobaciones",
]
