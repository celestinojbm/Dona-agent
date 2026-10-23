"""Modelos del primer valor (F12). Backend-only (RLS en la migración)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from agent.memory import Base

# Etapas del recorrido (sin respuestas libres: sólo esta enumeración acotada).
ETAPAS = (
    "inicio",
    "eleccion",
    "datos_minimos",
    "preview",
    "confirmado",
    "resultado",
    "abandono",
)

# Tipos de primer resultado implementados hoy.
RESULTADOS = ("borrador_seguimiento", "imagen")


class OnboardingPrimerValor(Base):
    """Métricas del primer valor por usuario. Una fila por teléfono."""
    __tablename__ = "onboarding_primer_valor"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_result_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_action_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    first_result_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventoOnboarding(Base):
    """Evento de etapa del onboarding (sin respuestas libres; sólo la etapa)."""
    __tablename__ = "eventos_onboarding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    etapa: Mapped[str] = mapped_column(String(20))
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
