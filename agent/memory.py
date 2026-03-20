# agent/memory.py — Memoria de conversaciones con SQLite
# Generado por AgentKit

"""
Sistema de memoria de Dona. Guarda el historial de conversaciones
por número de teléfono usando SQLite (local) o PostgreSQL (producción).
"""

import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, select, Integer, Boolean
from dotenv import load_dotenv

load_dotenv()

# Configuración de base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

# Si es PostgreSQL en producción, ajustar el esquema de URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Mensaje(Base):
    """Modelo de mensaje en la base de datos."""
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20))  # "user" o "assistant"
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TimezoneUsuario(Base):
    """Zona horaria inferida por usuario — se actualiza automáticamente."""
    __tablename__ = "timezone_usuarios"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    offset_minutos: Mapped[int] = mapped_column(Integer, default=0)  # ej: -240 para UTC-4
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Recordatorio(Base):
    """Recordatorio programado para enviar al usuario en una fecha/hora específica."""
    __tablename__ = "recordatorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    mensaje: Mapped[str] = mapped_column(Text)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def inicializar_db():
    """Crea las tablas si no existen."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def guardar_timezone(telefono: str, offset_minutos: int):
    """Guarda o actualiza el offset de zona horaria de un usuario."""
    async with async_session() as session:
        query = select(TimezoneUsuario).where(TimezoneUsuario.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if registro:
            registro.offset_minutos = offset_minutos
            registro.actualizado = datetime.utcnow()
        else:
            session.add(TimezoneUsuario(
                telefono=telefono,
                offset_minutos=offset_minutos,
                actualizado=datetime.utcnow()
            ))
        await session.commit()


async def obtener_timezone(telefono: str) -> int | None:
    """Retorna el offset en minutos guardado para este usuario, o None si no existe."""
    async with async_session() as session:
        query = select(TimezoneUsuario).where(TimezoneUsuario.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        return registro.offset_minutos if registro else None


async def guardar_mensaje(telefono: str, role: str, content: str):
    """Guarda un mensaje en el historial de conversación."""
    async with async_session() as session:
        mensaje = Mensaje(
            telefono=telefono,
            role=role,
            content=content,
            timestamp=datetime.utcnow()
        )
        session.add(mensaje)
        await session.commit()


async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:
    """
    Recupera los últimos N mensajes de una conversación.

    Args:
        telefono: Número de teléfono del cliente
        limite: Máximo de mensajes a recuperar (default: 20)

    Returns:
        Lista de diccionarios con role y content
    """
    async with async_session() as session:
        query = (
            select(Mensaje)
            .where(Mensaje.telefono == telefono)
            .order_by(Mensaje.timestamp.desc())
            .limit(limite)
        )
        result = await session.execute(query)
        mensajes = result.scalars().all()

        # Invertir para orden cronológico (los más recientes están primero)
        mensajes.reverse()

        return [
            {"role": msg.role, "content": msg.content}
            for msg in mensajes
        ]


async def guardar_recordatorio(telefono: str, mensaje: str, fecha_hora: datetime) -> Recordatorio:
    """Guarda un recordatorio en la base de datos."""
    async with async_session() as session:
        recordatorio = Recordatorio(
            telefono=telefono,
            mensaje=mensaje,
            fecha_hora=fecha_hora,
            enviado=False,
            creado=datetime.utcnow()
        )
        session.add(recordatorio)
        await session.commit()
        await session.refresh(recordatorio)
        return recordatorio


async def obtener_recordatorios_pendientes() -> list[Recordatorio]:
    """Retorna los recordatorios que ya vencieron y no han sido enviados."""
    async with async_session() as session:
        ahora = datetime.utcnow()
        query = (
            select(Recordatorio)
            .where(Recordatorio.enviado == False)
            .where(Recordatorio.fecha_hora <= ahora)
            .order_by(Recordatorio.fecha_hora)
        )
        result = await session.execute(query)
        return result.scalars().all()


async def marcar_recordatorio_enviado(recordatorio_id: int):
    """Marca un recordatorio como enviado."""
    async with async_session() as session:
        query = select(Recordatorio).where(Recordatorio.id == recordatorio_id)
        result = await session.execute(query)
        recordatorio = result.scalar_one_or_none()
        if recordatorio:
            recordatorio.enviado = True
            await session.commit()


async def limpiar_historial(telefono: str):
    """Borra todo el historial de una conversación."""
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono)
        result = await session.execute(query)
        mensajes = result.scalars().all()
        for msg in mensajes:
            await session.delete(msg)
        await session.commit()
