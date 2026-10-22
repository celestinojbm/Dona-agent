"""Outbox idempotente de notificaciones del plan (F14).

Un fallo de notificación (429/timeout de Whapi) NO bloquea ni reejecuta el job
ni rompe el cobro: sólo marca la notificación como fallida para reintento futuro.
La unicidad de `dedupe_key` evita envíos duplicados ante reintentos.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from agent.memory import async_session
from agent.plan_vivo.models import NotificacionPlan

logger = logging.getLogger("dona")


async def encolar(
    *, plan_id: int, telefono: str, dedupe_key: str, tipo: str = "actualizacion"
) -> bool:
    """Encola una notificación. Idempotente: si la dedupe_key ya existe, no
    duplica (devuelve False). Devuelve True si se encoló nueva."""
    n = NotificacionPlan(
        plan_id=plan_id,
        telefono=telefono,
        dedupe_key=dedupe_key[:200],
        tipo=tipo[:40],
        estado="pendiente",
        intentos=0,
        creado=datetime.utcnow(),
    )
    async with async_session() as s:
        s.add(n)
        try:
            await s.commit()
            return True
        except IntegrityError:
            await s.rollback()
            return False


async def marcar_enviada(dedupe_key: str) -> None:
    async with async_session() as s:
        await s.execute(
            update(NotificacionPlan)
            .where(NotificacionPlan.dedupe_key == dedupe_key[:200])
            .values(estado="enviada", enviado_en=datetime.utcnow())
        )
        await s.commit()


async def marcar_fallida(dedupe_key: str) -> None:
    """Registra el fallo (incrementa intentos). No toca el plan ni el cobro."""
    async with async_session() as s:
        n = (await s.execute(
            select(NotificacionPlan).where(
                NotificacionPlan.dedupe_key == dedupe_key[:200]
            )
        )).scalar_one_or_none()
        if n is None:
            return
        await s.execute(
            update(NotificacionPlan)
            .where(NotificacionPlan.id == n.id)
            .values(estado="fallida", intentos=NotificacionPlan.intentos + 1)
        )
        await s.commit()
