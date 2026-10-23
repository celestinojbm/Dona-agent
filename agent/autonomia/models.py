"""Modelos de la autonomía por acción (F1).

Dos tablas, ambas backend-only (RLS en la migración; el navegador nunca las lee
directo):

- `autonomia_por_accion`: configuración por (usuario, tipo_accion): nivel 1–4,
  umbral y topes, periodo y zona horaria, versión. UNIQUE por (telefono,
  tipo_accion).
- `autorizaciones_accion`: la autorización persistida que `confirmar_X` exige —
  hash de argumentos, cotización, máximo, origen (humana|politica), estado,
  vencimiento y consumo (uso único). UNIQUE por accion_ref.

Nada de escritura directa del navegador: estas tablas se escriben sólo desde el
backend tras evaluar la política determinística.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agent.memory import Base


class AutonomiaPorAccion(Base):
    """Nivel de autonomía configurado por usuario y tipo de acción."""
    __tablename__ = "autonomia_por_accion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    tipo_accion: Mapped[str] = mapped_column(String(80))
    nivel: Mapped[int] = mapped_column(Integer, default=1)  # 1..4, default L1
    # L2: umbral de créditos por debajo del cual no pide confirmación.
    umbral_creditos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Topes: por acción y por periodo. NULL = SIN tope ⇒ NO autoriza (nunca
    # significa ilimitado).
    tope_por_accion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tope_periodo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    periodo: Mapped[str] = mapped_column(String(10), default="")  # dia|semana|mes
    zona_horaria: Mapped[str] = mapped_column(String(60), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("telefono", "tipo_accion", name="uq_autonomia_tel_accion"),
        CheckConstraint("nivel >= 1 AND nivel <= 4", name="ck_autonomia_nivel"),
    )


class AutorizacionAccion(Base):
    """Autorización persistida que `confirmar_X` consume (uso único)."""
    __tablename__ = "autorizaciones_accion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    accion_ref: Mapped[str] = mapped_column(String(120), unique=True)  # uso único por acción
    tipo_accion: Mapped[str] = mapped_column(String(80))
    args_hash: Mapped[str] = mapped_column(String(64))  # sha256 de args canónicos
    cotizacion_creditos: Mapped[int] = mapped_column(Integer, default=0)
    maximo_creditos: Mapped[int] = mapped_column(Integer, default=0)  # tope del alcance
    origen: Mapped[str] = mapped_column(String(10), default="humana")  # humana|politica
    estado: Mapped[str] = mapped_column(String(12), default="vigente", index=True)
    # vigente|consumida|revocada|vencida
    vencimiento: Mapped[datetime] = mapped_column(DateTime)
    consumida_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version_politica: Mapped[int] = mapped_column(Integer, default=0)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "origen IN ('humana','politica')", name="ck_autorizacion_origen"
        ),
    )


class ReservaCredito(Base):
    """Reserva write-ahead de créditos (decisión de Celestino #6).

    Modelo de cobro: RESERVAR al iniciar, COBRAR al completar, LIBERAR si falla.
    Esta tabla lleva el estado de la reserva (reservada|consumida|liberada) con
    uso único por `accion_ref` (idempotente). El débito real del saldo lo hace la
    capa de billing al completar (integración F1+F3); aquí vive la máquina de
    estados que evita reservar/consumir/liberar dos veces.
    """
    __tablename__ = "reservas_credito"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    accion_ref: Mapped[str] = mapped_column(String(120), unique=True)  # uso único
    creditos: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(12), default="reservada", index=True)
    # reservada|consumida|liberada
    idempotency_key: Mapped[str | None] = mapped_column(String(250), nullable=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "estado IN ('reservada','consumida','liberada')",
            name="ck_reserva_estado",
        ),
    )
