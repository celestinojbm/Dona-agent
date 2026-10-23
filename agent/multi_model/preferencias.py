"""Persistencia de la preferencia de modelo por chat/agente (F23)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from agent.memory import async_session
from agent.multi_model.catalogo import existe
from agent.multi_model.models import PreferenciaModelo


async def obtener_preferencia(telefono: str, scope: str, scope_id: str) -> dict | None:
    """Preferencia de un chat/agente (sólo del propio usuario). None si no hay."""
    async with async_session() as s:
        row = (await s.execute(
            select(PreferenciaModelo).where(
                PreferenciaModelo.telefono == telefono,
                PreferenciaModelo.scope == scope,
                PreferenciaModelo.scope_id == scope_id,
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        return {
            "modelo_id": row.modelo_id,
            "modo_auto": bool(row.modo_auto),
            "scope": row.scope,
            "scope_id": row.scope_id,
        }


async def fijar_preferencia(
    telefono: str,
    scope: str,
    scope_id: str,
    *,
    modelo_id: str = "",
    modo_auto: bool = False,
) -> dict:
    """Upsert de la preferencia. Valida el modelo si se fija uno explícito."""
    if scope not in ("chat", "agente"):
        raise ValueError("scope debe ser 'chat' o 'agente'")
    if modelo_id and not existe(modelo_id):
        raise ValueError(f"modelo desconocido: {modelo_id}")
    async with async_session() as s:
        row = (await s.execute(
            select(PreferenciaModelo).where(
                PreferenciaModelo.telefono == telefono,
                PreferenciaModelo.scope == scope,
                PreferenciaModelo.scope_id == scope_id,
            )
        )).scalar_one_or_none()
        if row is None:
            row = PreferenciaModelo(
                telefono=telefono, scope=scope, scope_id=scope_id,
                modelo_id=modelo_id, modo_auto=modo_auto,
                actualizado=datetime.utcnow(),
            )
            s.add(row)
        else:
            row.modelo_id = modelo_id
            row.modo_auto = modo_auto
            row.actualizado = datetime.utcnow()
        await s.commit()
        return {"modelo_id": modelo_id, "modo_auto": modo_auto, "scope": scope, "scope_id": scope_id}
