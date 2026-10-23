"""Modelo de preferencia de modelo por chat/agente (F23). Backend-only (RLS)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from agent.memory import Base


class PreferenciaModelo(Base):
    """Modelo elegido para un chat o un agente de un usuario.

    `scope` = 'chat' | 'agente'; `scope_id` identifica el chat/agente concreto.
    `modo_auto` = True guarda que ese chat/agente usa el modo Auto (el modelo se
    elige por tarea/coste en cada turno). UNIQUE por (telefono, scope, scope_id).
    """
    __tablename__ = "preferencia_modelo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    scope: Mapped[str] = mapped_column(String(10))  # chat | agente
    scope_id: Mapped[str] = mapped_column(String(120))
    modelo_id: Mapped[str] = mapped_column(String(80), default="")
    modo_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("telefono", "scope", "scope_id", name="uq_preferencia_modelo"),
    )
