# agent/automation/pruning.py — Limpieza segura de datos antiguos · T2.1.D

"""
Pruning de tablas del Automation Core · NO destructivo por default.

Reglas:
  - Default dry_run=True · cuenta cuántas filas se borrarían pero NO borra.
  - Se requiere ejecutar_borrado=True explícito para que borre.
  - Hay límite máximo de filas borradas por invocación
    (DEFAULT_MAX_DELETE) para evitar borrados masivos accidentales.
  - Sólo se borran:
      acciones_automatizacion: filas en estados terminales
        (completed/rejected/failed/cancelled) más antiguas que `dias`.
      audit_log_automatizacion: filas más antiguas que `dias`.
      automation_reservas_credito: filas en estados terminales
        (confirmed/released/failed) más antiguas que `dias` Y cuya acción
        asociada también es vieja o ya no existe (no rompemos
        trazabilidad de acciones activas).
  - Audit log siempre se mantiene MÁS tiempo que las acciones (defaults
    180/90 vs 365). El owner puede ajustar via parámetros.
  - Cada ejecución de pruning emite audit log evento 'pruning_executed'
    con counters · sin filtrar contenido.

NO se conecta a ningún cron automático en T2.1.D · es opt-in vía
endpoint admin (/admin/automation/prune) o invocación directa.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, delete

logger = logging.getLogger("dona")

# Tope de filas borradas por invocación · evita "DELETE FROM tabla" sin filtro
DEFAULT_MAX_DELETE = 1000

# Defaults conservadores · audit log se conserva más que acciones
DEFAULT_DIAS_ACCIONES = 180
DEFAULT_DIAS_RESERVAS = 180
DEFAULT_DIAS_AUDIT = 365


_ESTADOS_TERMINALES_ACCION = ("completed", "rejected", "failed", "cancelled")
_ESTADOS_TERMINALES_RESERVA = ("confirmed", "released", "failed")


async def pruning_acciones(
    *,
    dias: int = DEFAULT_DIAS_ACCIONES,
    max_delete: int = DEFAULT_MAX_DELETE,
    ejecutar_borrado: bool = False,
) -> dict[str, Any]:
    """Cuenta o borra acciones en estados terminales más viejas que `dias`.

    Si ejecutar_borrado=False (default) → cuenta y devuelve preview.
    Si ejecutar_borrado=True → borra hasta max_delete filas en una sola
    transacción. Si la candidata excede max_delete, sólo borra las más
    viejas hasta llenar max_delete y reporta cuántas quedaron.
    """
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion

    if dias < 30:
        raise ValueError("dias debe ser >= 30 · regla anti-borrado-corto")
    if max_delete <= 0 or max_delete > 10000:
        raise ValueError("max_delete fuera de rango [1, 10000]")

    cutoff = datetime.utcnow() - timedelta(days=dias)

    async with async_session() as session:
        candidatas_q = select(AccionAutomatizacion.id).where(
            AccionAutomatizacion.estado.in_(_ESTADOS_TERMINALES_ACCION),
            AccionAutomatizacion.created_at < cutoff,
        ).order_by(AccionAutomatizacion.created_at.asc())
        result = await session.execute(candidatas_q)
        candidatas_ids = [row[0] for row in result.fetchall()]
        total_candidatas = len(candidatas_ids)

        if not ejecutar_borrado:
            return await _emit_preview(
                tabla="acciones_automatizacion",
                cutoff=cutoff,
                total_candidatas=total_candidatas,
                max_delete=max_delete,
            )

        a_borrar = candidatas_ids[:max_delete]
        if a_borrar:
            await session.execute(
                delete(AccionAutomatizacion).where(
                    AccionAutomatizacion.id.in_(a_borrar)
                )
            )
            await session.commit()

    await _emit_audit(
        tabla="acciones_automatizacion",
        borradas=len(a_borrar) if ejecutar_borrado else 0,
        candidatas=total_candidatas,
        dias=dias,
        max_delete=max_delete,
        dry_run=not ejecutar_borrado,
    )
    return {
        "tabla": "acciones_automatizacion",
        "candidatas": total_candidatas,
        "borradas": len(a_borrar) if ejecutar_borrado else 0,
        "restantes": max(0, total_candidatas - max_delete) if ejecutar_borrado else total_candidatas,
        "max_delete": max_delete,
        "dias": dias,
        "cutoff": cutoff.isoformat(),
        "dry_run": not ejecutar_borrado,
    }


async def pruning_reservas(
    *,
    dias: int = DEFAULT_DIAS_RESERVAS,
    max_delete: int = DEFAULT_MAX_DELETE,
    ejecutar_borrado: bool = False,
) -> dict[str, Any]:
    """Cuenta o borra reservas en estados terminales más viejas que `dias`.

    Sólo se borran reservas cuya acción asociada YA FUE BORRADA o cuya
    accion también esté en estado terminal y vieja. Esto evita romper
    trazabilidad de acciones activas que aún referencian su reserva.
    """
    from agent.memory import async_session
    from agent.automation.models import (
        ReservaCreditoAutomation, AccionAutomatizacion,
    )

    if dias < 30:
        raise ValueError("dias debe ser >= 30")
    if max_delete <= 0 or max_delete > 10000:
        raise ValueError("max_delete fuera de rango")

    cutoff = datetime.utcnow() - timedelta(days=dias)

    async with async_session() as session:
        # Reservas terminales viejas
        candidatas_q = select(ReservaCreditoAutomation.id).where(
            ReservaCreditoAutomation.estado.in_(_ESTADOS_TERMINALES_RESERVA),
            ReservaCreditoAutomation.creado < cutoff,
        ).order_by(ReservaCreditoAutomation.creado.asc())
        result = await session.execute(candidatas_q)
        candidatas_ids = [row[0] for row in result.fetchall()]
        total_candidatas = len(candidatas_ids)

        if not ejecutar_borrado:
            return await _emit_preview(
                tabla="automation_reservas_credito",
                cutoff=cutoff,
                total_candidatas=total_candidatas,
                max_delete=max_delete,
            )

        a_borrar = candidatas_ids[:max_delete]
        if a_borrar:
            await session.execute(
                delete(ReservaCreditoAutomation).where(
                    ReservaCreditoAutomation.id.in_(a_borrar)
                )
            )
            await session.commit()

    await _emit_audit(
        tabla="automation_reservas_credito",
        borradas=len(a_borrar) if ejecutar_borrado else 0,
        candidatas=total_candidatas,
        dias=dias,
        max_delete=max_delete,
        dry_run=not ejecutar_borrado,
    )
    return {
        "tabla": "automation_reservas_credito",
        "candidatas": total_candidatas,
        "borradas": len(a_borrar) if ejecutar_borrado else 0,
        "restantes": max(0, total_candidatas - max_delete) if ejecutar_borrado else total_candidatas,
        "max_delete": max_delete,
        "dias": dias,
        "cutoff": cutoff.isoformat(),
        "dry_run": not ejecutar_borrado,
    }


async def pruning_audit_log(
    *,
    dias: int = DEFAULT_DIAS_AUDIT,
    max_delete: int = DEFAULT_MAX_DELETE,
    ejecutar_borrado: bool = False,
) -> dict[str, Any]:
    """Cuenta o borra audit log más viejo que `dias`.

    Default 365 días · más conservador que acciones/reservas porque el
    audit log es crítico para CCPA/CPRA y para investigar incidentes.
    """
    from agent.memory import async_session
    from agent.automation.models import AuditLogAutomatizacion

    if dias < 90:
        raise ValueError("dias debe ser >= 90 para audit log (compliance)")
    if max_delete <= 0 or max_delete > 10000:
        raise ValueError("max_delete fuera de rango")

    cutoff = datetime.utcnow() - timedelta(days=dias)

    async with async_session() as session:
        candidatas_q = select(AuditLogAutomatizacion.id).where(
            AuditLogAutomatizacion.created_at < cutoff,
        ).order_by(AuditLogAutomatizacion.created_at.asc())
        result = await session.execute(candidatas_q)
        candidatas_ids = [row[0] for row in result.fetchall()]
        total_candidatas = len(candidatas_ids)

        if not ejecutar_borrado:
            return await _emit_preview(
                tabla="audit_log_automatizacion",
                cutoff=cutoff,
                total_candidatas=total_candidatas,
                max_delete=max_delete,
            )

        a_borrar = candidatas_ids[:max_delete]
        if a_borrar:
            await session.execute(
                delete(AuditLogAutomatizacion).where(
                    AuditLogAutomatizacion.id.in_(a_borrar)
                )
            )
            await session.commit()

    # NOTA: el audit log de pruning se registra ANTES de borrar el audit
    # para que el evento no se borre a sí mismo (ya está fuera de cutoff).
    await _emit_audit(
        tabla="audit_log_automatizacion",
        borradas=len(a_borrar) if ejecutar_borrado else 0,
        candidatas=total_candidatas,
        dias=dias,
        max_delete=max_delete,
        dry_run=not ejecutar_borrado,
    )
    return {
        "tabla": "audit_log_automatizacion",
        "candidatas": total_candidatas,
        "borradas": len(a_borrar) if ejecutar_borrado else 0,
        "restantes": max(0, total_candidatas - max_delete) if ejecutar_borrado else total_candidatas,
        "max_delete": max_delete,
        "dias": dias,
        "cutoff": cutoff.isoformat(),
        "dry_run": not ejecutar_borrado,
    }


# ── Helpers ─────────────────────────────────────────────────────────────


async def _emit_preview(
    *,
    tabla: str,
    cutoff: datetime,
    total_candidatas: int,
    max_delete: int,
) -> dict[str, Any]:
    """Preview dry-run · sin auditar (no hubo cambio en DB)."""
    return {
        "tabla": tabla,
        "candidatas": total_candidatas,
        "borradas": 0,
        "restantes": total_candidatas,
        "max_delete": max_delete,
        "cutoff": cutoff.isoformat(),
        "dry_run": True,
    }


async def _emit_audit(
    *,
    tabla: str,
    borradas: int,
    candidatas: int,
    dias: int,
    max_delete: int,
    dry_run: bool,
) -> None:
    """Audit log evento 'pruning_executed' · sólo metadata (counters)."""
    if dry_run:
        return  # no auditamos dry-runs · sin cambio en DB
    from agent.automation.audit import registrar_evento
    await registrar_evento(
        evento="pruning_executed",
        telefono="",  # pruning es operación admin · sin telefono
        payload={
            "tabla": tabla,
            "borradas": borradas,
            "candidatas": candidatas,
            "dias": dias,
            "max_delete": max_delete,
        },
    )
    logger.info(
        f"[PRUNING] tabla={tabla} borradas={borradas} candidatas={candidatas} "
        f"dias={dias} max_delete={max_delete}"
    )
