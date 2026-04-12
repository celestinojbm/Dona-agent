# enhanced/models.py — Modelos de base de datos para Dona 2.0

"""
Tablas nuevas para habilidades avanzadas.
Reutiliza el engine y session de agent/memory.py (misma DB, zero-duplicación).

Tablas:
  - system_catalog       — Catálogo de 60+ sistemas predefinidos (plantillas JSONB)
  - user_systems          — Sistemas instanciados por usuario (datos JSONB)
  - system_activity_logs  — Audit trail de todas las acciones de módulos enhanced
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, Boolean, DateTime, Index

logger = logging.getLogger("dona.enhanced")

# Reutilizar la infraestructura de DB existente
from agent.memory import Base, engine, async_session as async_session_enhanced


class SystemCatalog(Base):
    """
    Catálogo de sistemas predefinidos disponibles para todos los usuarios.
    Cada entrada es una plantilla con estructura JSONB que se instancia en user_systems.
    """
    __tablename__ = "system_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    categoria: Mapped[str] = mapped_column(String(50), index=True)  # "habitos", "finanzas", "salud", etc.
    descripcion: Mapped[str] = mapped_column(Text)
    plantilla_json: Mapped[str] = mapped_column(Text)  # JSON string con la estructura del sistema
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )


class UserSystem(Base):
    """
    Sistema instanciado para un usuario específico.
    Contiene los datos personalizados del usuario en formato JSONB.
    """
    __tablename__ = "user_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    catalog_id: Mapped[int] = mapped_column(Integer, index=True)  # FK lógica a system_catalog.id
    nombre_personalizado: Mapped[str | None] = mapped_column(String(150), nullable=True)
    datos_json: Mapped[str] = mapped_column(Text, default="{}")  # Datos del usuario en JSON
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )
    actualizado: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        Index("ix_user_systems_tel_catalog", "telefono", "catalog_id"),
    )


class SystemActivityLog(Base):
    """
    Audit trail de todas las acciones ejecutadas por módulos enhanced.
    Registra quién, qué, cuándo y si fue privilegiada.
    """
    __tablename__ = "system_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    modulo: Mapped[str] = mapped_column(String(50))     # nombre del SafeModule
    accion: Mapped[str] = mapped_column(String(200))     # qué se hizo
    detalle: Mapped[str] = mapped_column(Text, default="")
    nivel: Mapped[str] = mapped_column(String(20), default="info")  # info, warning, error
    privilegiada: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow(), index=True,
    )


async def inicializar_tablas_enhanced():
    """Crea las tablas de Dona 2.0 si no existen (idempotente)."""
    async with engine.begin() as conn:
        # Solo crea las tablas que faltan, no toca las existentes
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[ENHANCED] Tablas de Dona 2.0 verificadas/creadas")
