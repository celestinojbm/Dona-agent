"""Modelo de la lista de espera (Fase 1 · issue #334). Backend-only (RLS en la migración)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from agent.memory import Base

# en_espera: dejó su correo. invitado: canjeó un código de invitación válido.
ESTADOS_LISTA_ESPERA = ("en_espera", "invitado")


class ListaEspera(Base):
    """Una fila por correo (normalizado: trim + minúsculas)."""

    __tablename__ = "lista_espera"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(20), default="en_espera")
    origen: Mapped[str] = mapped_column(String(30), default="web")
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    invitado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
