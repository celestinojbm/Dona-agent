# agent/automation/action_center.py — CRUD del Action Center (T2.1.A)

"""
Crear, listar, aprobar, rechazar, cancelar y marcar acciones del
Automation Core.

Diseño:
  - crear_accion(...) idempotente · usa idempotency_key para no
    duplicar misma acción del mismo perfil/tipo/playbook el mismo día.
  - Cada operación que cambia estado emite audit log.
  - No ejecuta la acción · solo actualiza el estado. La ejecución vive
    en agent/automation/execution.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from agent.automation.permissions import (
    NivelRiesgo,
    clasificar_riesgo,
    estado_inicial_para_riesgo,
    requiere_aprobacion,
    transicion_valida,
)
from agent.automation.costos import estimar_costo_accion
from agent.automation.audit import registrar_evento

logger = logging.getLogger("dona")


def _idempotency_key(
    telefono: str,
    tipo_accion: str,
    playbook_id: str,
    opportunity_id: str,
    fecha: datetime | None = None,
) -> str:
    """Hash determinístico para evitar duplicar misma acción el mismo día.

    Formato: sha256(telefono | tipo | playbook | opportunity | YYYYMMDD)
    truncado a 32 chars hex. Si todo cambia menos la fecha, queda igual ·
    si pasa otro día, regenera (intencional · permite que Dona vuelva a
    sugerir lo mismo más tarde).
    """
    f = (fecha or datetime.utcnow()).strftime("%Y%m%d")
    raw = f"{telefono}|{tipo_accion}|{playbook_id}|{opportunity_id}|{f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


async def crear_accion(
    *,
    telefono: str,
    tipo_accion: str,
    titulo: str,
    descripcion: str = "",
    razon_recomendacion: str = "",
    opportunity_id: str = "",
    playbook_id: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crea una acción nueva o retorna la existente si ya hay una para
    misma (telefono, tipo, playbook, opportunity, fecha).

    Returns:
        Dict con la acción · si es nueva incluye 'created':True;
        si es duplicada idempotente, 'created':False y los datos
        existentes.
    """
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion

    riesgo = clasificar_riesgo(tipo_accion)
    estado_inicial = estado_inicial_para_riesgo(riesgo)
    necesita_aprob = requiere_aprobacion(riesgo)
    costo = estimar_costo_accion(tipo_accion)
    idem = _idempotency_key(telefono, tipo_accion, playbook_id, opportunity_id)
    payload_str = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)

    async with async_session() as session:
        # Idempotencia: ¿ya existe?
        existing = await session.execute(
            select(AccionAutomatizacion).where(
                AccionAutomatizacion.idempotency_key == idem
            )
        )
        prev = existing.scalar_one_or_none()
        if prev is not None:
            logger.info(
                f"[ACT-CENTER] dup idem={idem[:8]} accion_id={prev.id} skip"
            )
            return {**_a_dict(prev), "created": False}

        accion = AccionAutomatizacion(
            telefono=telefono,
            opportunity_id=opportunity_id,
            playbook_id=playbook_id,
            tipo_accion=tipo_accion,
            titulo=titulo[:200],
            descripcion=descripcion,
            razon_recomendacion=razon_recomendacion,
            estado=estado_inicial,
            riesgo=riesgo.value,
            costo_creditos_estimado=costo,
            requires_approval=necesita_aprob,
            payload_json=payload_str,
            idempotency_key=idem,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(accion)
        await session.commit()
        await session.refresh(accion)
        accion_id = accion.id
        result = _a_dict(accion)

    await registrar_evento(
        evento="action_created",
        telefono=telefono,
        accion_id=accion_id,
        riesgo=riesgo.value,
        payload={
            "tipo_accion": tipo_accion,
            "playbook_id": playbook_id,
            "opportunity_id": opportunity_id,
            "estado": estado_inicial,
            "costo_creditos_estimado": costo,
            "requires_approval": necesita_aprob,
        },
    )
    return {**result, "created": True}


async def listar_acciones(
    telefono: str,
    *,
    estado: str | None = None,
    limite: int = 50,
) -> list[dict[str, Any]]:
    """Lista acciones del usuario, opcionalmente filtradas por estado."""
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion

    async with async_session() as session:
        q = select(AccionAutomatizacion).where(
            AccionAutomatizacion.telefono == telefono
        )
        if estado:
            q = q.where(AccionAutomatizacion.estado == estado)
        q = q.order_by(AccionAutomatizacion.created_at.desc()).limit(limite)
        rows = (await session.execute(q)).scalars().all()
    return [_a_dict(r) for r in rows]


async def _cambiar_estado(
    accion_id: int,
    *,
    estado_destino: str,
    evento: str,
    error_message: str = "",
    result: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Helper interno · cambia estado validando la transición y emite audit."""
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion

    async with async_session() as session:
        row = (await session.execute(
            select(AccionAutomatizacion).where(
                AccionAutomatizacion.id == accion_id
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        if not transicion_valida(row.estado, estado_destino):
            logger.warning(
                f"[ACT-CENTER] transición inválida accion_id={accion_id} "
                f"actual={row.estado} destino={estado_destino}"
            )
            return _a_dict(row)
        row.estado = estado_destino
        row.updated_at = datetime.utcnow()
        if estado_destino == "approved":
            row.approved_at = datetime.utcnow()
        elif estado_destino == "rejected":
            row.rejected_at = datetime.utcnow()
        elif estado_destino == "completed":
            row.completed_at = datetime.utcnow()
        if error_message:
            row.error_message = error_message[:500]
        if result is not None:
            row.result_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
        await session.commit()
        await session.refresh(row)
        result_dict = _a_dict(row)
        telefono = row.telefono
        riesgo = row.riesgo

    await registrar_evento(
        evento=evento,
        telefono=telefono,
        accion_id=accion_id,
        riesgo=riesgo,
        payload={"estado": estado_destino},
    )
    return result_dict


async def aprobar_accion(accion_id: int) -> dict[str, Any] | None:
    return await _cambiar_estado(
        accion_id, estado_destino="approved", evento="action_approved",
    )


async def rechazar_accion(accion_id: int) -> dict[str, Any] | None:
    return await _cambiar_estado(
        accion_id, estado_destino="rejected", evento="action_rejected",
    )


async def cancelar_accion(accion_id: int) -> dict[str, Any] | None:
    return await _cambiar_estado(
        accion_id, estado_destino="cancelled", evento="action_cancelled",
    )


async def marcar_running(accion_id: int) -> dict[str, Any] | None:
    return await _cambiar_estado(
        accion_id, estado_destino="running", evento="action_started",
    )


async def marcar_completada(
    accion_id: int, *, result: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return await _cambiar_estado(
        accion_id, estado_destino="completed", evento="action_completed",
        result=result,
    )


async def marcar_fallida(
    accion_id: int, *, error_message: str,
) -> dict[str, Any] | None:
    return await _cambiar_estado(
        accion_id, estado_destino="failed", evento="action_failed",
        error_message=error_message,
    )


def _a_dict(row) -> dict[str, Any]:
    """Serializa una fila AccionAutomatizacion · dict seguro de retornar."""
    return {
        "id": row.id,
        "telefono": row.telefono,
        "opportunity_id": row.opportunity_id,
        "playbook_id": row.playbook_id,
        "tipo_accion": row.tipo_accion,
        "titulo": row.titulo,
        "descripcion": row.descripcion,
        "razon_recomendacion": row.razon_recomendacion,
        "estado": row.estado,
        "riesgo": row.riesgo,
        "costo_creditos_estimado": row.costo_creditos_estimado,
        "requires_approval": row.requires_approval,
        "payload_json": row.payload_json,
        "result_json": row.result_json,
        "error_message": row.error_message,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "rejected_at": row.rejected_at.isoformat() if row.rejected_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
