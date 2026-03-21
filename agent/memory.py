# agent/memory.py — Memoria de conversaciones con SQLite
# Generado por AgentKit

"""
Sistema de memoria de Dona. Guarda el historial de conversaciones
por número de teléfono usando SQLite (local) o PostgreSQL (producción).
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, select, Integer, Boolean, update
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

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
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC próxima ocurrencia
    enviado: Mapped[bool] = mapped_column(Boolean, default=False)       # True solo si es único y ya se envió
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Campos para recordatorios recurrentes
    # JSON con forma: {"tipo": "diario"} | {"tipo": "semanal", "dia": 0} |
    #                 {"tipo": "dias_semana"} | {"tipo": "mensual", "dia": 15}
    recurrencia: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    cancelado: Mapped[bool] = mapped_column(Boolean, default=False)

    # Offset UTC en minutos del usuario en el momento de creación (para recalcular correctamente)
    offset_tz_minutos: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    # Fecha límite: dejar de enviar después de esta fecha (UTC)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    # Cuántas veces falló el envío consecutivamente (reset al enviar exitosamente)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)

    # Cuándo se envió por última vez (UTC)
    ultimo_envio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)


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


async def guardar_recordatorio(
    telefono: str,
    mensaje: str,
    fecha_hora: datetime,
    recurrencia: dict | None = None,
    offset_tz_minutos: int | None = None,
    fecha_fin: datetime | None = None,
) -> Recordatorio:
    """Guarda un recordatorio en la base de datos."""
    async with async_session() as session:
        recordatorio = Recordatorio(
            telefono=telefono,
            mensaje=mensaje,
            fecha_hora=fecha_hora,
            enviado=False,
            creado=datetime.utcnow(),
            recurrencia=json.dumps(recurrencia) if recurrencia else None,
            cancelado=False,
            offset_tz_minutos=offset_tz_minutos,
            fecha_fin=fecha_fin,
            intentos_fallidos=0,
            ultimo_envio=None,
        )
        session.add(recordatorio)
        await session.commit()
        await session.refresh(recordatorio)
        return recordatorio


async def obtener_recordatorios_pendientes() -> list[Recordatorio]:
    """Retorna los recordatorios activos (no cancelados, no vencidos) que ya llegó su hora."""
    async with async_session() as session:
        ahora = datetime.utcnow()
        query = (
            select(Recordatorio)
            .where(Recordatorio.cancelado == False)
            .where(Recordatorio.enviado == False)
            .where(Recordatorio.fecha_hora <= ahora)
            .where(Recordatorio.intentos_fallidos < 3)
            .order_by(Recordatorio.fecha_hora)
        )
        result = await session.execute(query)
        return result.scalars().all()


async def obtener_recordatorios_activos(telefono: str) -> list[dict]:
    """Retorna los recordatorios futuros activos de un usuario, para mostrarle la lista."""
    async with async_session() as session:
        ahora = datetime.utcnow()
        query = (
            select(Recordatorio)
            .where(Recordatorio.telefono == telefono)
            .where(Recordatorio.cancelado == False)
            .where(Recordatorio.enviado == False)
            .where(Recordatorio.fecha_hora > ahora)
            .order_by(Recordatorio.fecha_hora)
            .limit(20)
        )
        result = await session.execute(query)
        registros = result.scalars().all()

        lista = []
        for r in registros:
            rec = json.loads(r.recurrencia) if r.recurrencia else None
            tipo_str = _describir_recurrencia(rec)
            lista.append({
                "id": r.id,
                "mensaje": r.mensaje,
                "fecha_hora": r.fecha_hora,
                "recurrencia": rec,
                "tipo_str": tipo_str,
                "fecha_fin": r.fecha_fin,
            })
        return lista


def _describir_recurrencia(recurrencia: dict | None) -> str:
    """Convierte el dict de recurrencia a texto legible."""
    if not recurrencia:
        return "único"
    tipo = recurrencia.get("tipo", "")
    if tipo == "diario":
        return "diario"
    if tipo == "semanal":
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        dia_num = recurrencia.get("dia", 0)
        return f"cada {dias[dia_num]}"
    if tipo == "dias_semana":
        return "lunes a viernes"
    if tipo == "mensual":
        dia = recurrencia.get("dia", 1)
        return f"mensual (día {dia})"
    return tipo


async def marcar_recordatorio_enviado(recordatorio_id: int):
    """
    Para recordatorios únicos: los marca como enviados (no se vuelven a disparar).
    Para recurrentes: calcula la próxima ocurrencia y actualiza fecha_hora.
    """
    async with async_session() as session:
        query = select(Recordatorio).where(Recordatorio.id == recordatorio_id)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if not r:
            return

        ahora = datetime.utcnow()
        r.ultimo_envio = ahora
        r.intentos_fallidos = 0

        if r.recurrencia:
            # Recurrente: calcular próxima ocurrencia
            proxima = _calcular_proxima_ocurrencia(r.fecha_hora, r.recurrencia, r.offset_tz_minutos)
            if proxima and (r.fecha_fin is None or proxima <= r.fecha_fin):
                r.fecha_hora = proxima
                logger.info(f"Recordatorio #{r.id} reagendado para {proxima}")
            else:
                # Se acabó la recurrencia (llegó fecha_fin)
                r.cancelado = True
                logger.info(f"Recordatorio #{r.id} recurrente finalizado (fecha_fin alcanzada)")
        else:
            # Único: marcar como enviado definitivamente
            r.enviado = True

        await session.commit()


async def registrar_fallo_recordatorio(recordatorio_id: int):
    """Incrementa el contador de fallos. Si llega a 3, pausa el recordatorio."""
    async with async_session() as session:
        query = select(Recordatorio).where(Recordatorio.id == recordatorio_id)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if not r:
            return
        r.intentos_fallidos = (r.intentos_fallidos or 0) + 1
        await session.commit()
        if r.intentos_fallidos >= 3:
            logger.warning(f"Recordatorio #{r.id} pausado por 3 fallos consecutivos")


async def cancelar_recordatorio_por_id(recordatorio_id: int):
    """Cancela un recordatorio específico por ID."""
    async with async_session() as session:
        query = select(Recordatorio).where(Recordatorio.id == recordatorio_id)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if r:
            r.cancelado = True
            await session.commit()


async def cancelar_recordatorios_por_keyword(telefono: str, palabras: list[str]) -> list[int]:
    """
    Cancela los recordatorios de un usuario que contienen alguna de las palabras clave.
    Retorna los IDs cancelados.
    """
    async with async_session() as session:
        ahora = datetime.utcnow()
        query = (
            select(Recordatorio)
            .where(Recordatorio.telefono == telefono)
            .where(Recordatorio.cancelado == False)
            .where(Recordatorio.enviado == False)
        )
        result = await session.execute(query)
        todos = result.scalars().all()

        cancelados = []
        for r in todos:
            if any(p.lower() in r.mensaje.lower() for p in palabras):
                r.cancelado = True
                cancelados.append(r.id)

        if cancelados:
            await session.commit()
        return cancelados


def _calcular_proxima_ocurrencia(
    fecha_actual: datetime,
    recurrencia_json: str,
    offset_tz_minutos: int | None,
) -> datetime | None:
    """
    Calcula la siguiente ocurrencia UTC a partir de fecha_actual.

    recurrencia_json: string JSON como '{"tipo": "diario"}' o '{"tipo": "semanal", "dia": 0}'
    offset_tz_minutos: offset del usuario (ej: -240 para UTC-4), usado para saltar fines de semana
    """
    try:
        recurrencia = json.loads(recurrencia_json) if isinstance(recurrencia_json, str) else recurrencia_json
        tipo = recurrencia.get("tipo", "")
        offset_seg = (offset_tz_minutos or 0) * 60

        if tipo == "diario":
            return fecha_actual + timedelta(days=1)

        elif tipo == "semanal":
            dia_objetivo = recurrencia.get("dia", 0)  # 0=lun … 6=dom
            proxima = fecha_actual + timedelta(days=1)
            for _ in range(7):
                if proxima.weekday() == dia_objetivo:
                    return proxima
                proxima += timedelta(days=1)
            return proxima

        elif tipo == "dias_semana":
            # Lunes a viernes en hora local del usuario
            proxima = fecha_actual + timedelta(days=1)
            for _ in range(7):
                # Convertir UTC a local para ver qué día es
                local = proxima + timedelta(seconds=offset_seg)
                if local.weekday() < 5:  # 0=lun … 4=vie
                    return proxima
                proxima += timedelta(days=1)
            return proxima

        elif tipo == "mensual":
            dia_mes = recurrencia.get("dia", fecha_actual.day)
            # Avanzar al mes siguiente
            mes = fecha_actual.month + 1
            anio = fecha_actual.year
            if mes > 12:
                mes = 1
                anio += 1
            # Ajustar si el día no existe en ese mes (ej: 31 de feb)
            import calendar
            ultimo_dia = calendar.monthrange(anio, mes)[1]
            dia_real = min(dia_mes, ultimo_dia)
            proxima = fecha_actual.replace(year=anio, month=mes, day=dia_real)
            return proxima

        else:
            logger.warning(f"Tipo de recurrencia desconocido: {tipo}")
            return None

    except Exception as e:
        logger.error(f"Error calculando próxima ocurrencia: {e}")
        return None


async def limpiar_historial(telefono: str):
    """Borra todo el historial de una conversación."""
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono)
        result = await session.execute(query)
        mensajes = result.scalars().all()
        for msg in mensajes:
            await session.delete(msg)
        await session.commit()
