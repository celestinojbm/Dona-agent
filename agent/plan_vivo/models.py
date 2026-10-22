"""Modelos del plan vivo (F14). Backend-only (RLS en la migración)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from agent.memory import Base

# Estados válidos del plan (el checklist que confirma el usuario).
ESTADOS_PLAN = (
    "preparado",
    "pendiente",
    "en_curso",
    "completado",
    "parcial",
    "fallido",
    "cancelado",
    "requiere_revision",
)

# Estados de un paso individual. Un paso terminado no vuelve a pendiente.
ESTADOS_PASO = ("pendiente", "en_curso", "completado", "fallido")
ESTADOS_PASO_TERMINALES = frozenset({"completado", "fallido"})


class PlanTarea(Base):
    """Plan de una tarea, ligado a la autorización (versión+hash) que se confirmó."""
    __tablename__ = "plan_tarea"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    job_id: Mapped[str] = mapped_column(String(120), default="", index=True)  # arq
    accion_ref: Mapped[str] = mapped_column(String(120), index=True)
    autorizacion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    hash_plan: Mapped[str] = mapped_column(String(64), default="")
    coste_maximo: Mapped[int] = mapped_column(Integer, default=0)
    pasos_json: Mapped[str] = mapped_column(Text, default="[]")  # lista de pasos saneados
    estado: Mapped[str] = mapped_column(String(20), default="preparado", index=True)
    # Concurrencia optimista: cada escritura exige la revisión esperada y la sube.
    revision: Mapped[int] = mapped_column(Integer, default=0)
    mensaje_ref: Mapped[str] = mapped_column(String(200), default="")  # id del mensaje WhatsApp
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("accion_ref", name="uq_plan_accion_ref"),
    )


class NotificacionPlan(Base):
    """Outbox idempotente de notificaciones del plan (coalescidas)."""
    __tablename__ = "notificaciones_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, index=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    # Clave lógica de la notificación (UNIQUE) → reintentos no duplican envíos.
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    tipo: Mapped[str] = mapped_column(String(40), default="actualizacion")
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")  # pendiente|enviada|fallida
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
