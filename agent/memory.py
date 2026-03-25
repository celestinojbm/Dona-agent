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
from sqlalchemy import String, Text, DateTime, select, Integer, Boolean, update, text
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Configuración de base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

# Si es PostgreSQL en producción, ajustar el esquema de URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# asyncpg con PostgreSQL requiere SSL explícito y deshabilitar prepared statements
# (PgBouncer transaction mode — usado por Supabase pooler — no los soporta)
_ES_POSTGRES = DATABASE_URL.startswith("postgresql+asyncpg://")
if _ES_POSTGRES:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={
            "ssl": "require",
            "statement_cache_size": 0,  # requerido para PgBouncer
        },
    )
else:
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
    offset_minutos: Mapped[int] = mapped_column(Integer, default=0)   # fallback legacy
    timezone_nombre: Mapped[str | None] = mapped_column(String(60), nullable=True)  # IANA tz (DST-aware)
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


class UsuarioUbicacion(Base):
    """Ciudad, país e industria del usuario — capturados en onboarding."""
    __tablename__ = "usuario_ubicacion"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    ciudad: Mapped[str | None] = mapped_column(String(100), nullable=True)           # Ciudad de residencia (permanente)
    pais: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industria: Mapped[str | None] = mapped_column(String(100), nullable=True)        # Inferida del contexto
    ciudad_actual: Mapped[str | None] = mapped_column(String(100), nullable=True)    # Ciudad temporal (viaje)
    ciudad_actual_expira: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # Cuándo vuelve a residencia
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NoticiaEnviada(Base):
    """Registro de artículos enviados por usuario — para no repetir."""
    __tablename__ = "noticias_enviadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    url_hash: Mapped[str] = mapped_column(String(32))   # MD5 del URL
    enviada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UsuarioEstadoEmocional(Base):
    """Estado emocional actual del usuario — se actualiza en cada mensaje."""
    __tablename__ = "usuario_estado_emocional"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    estado: Mapped[str] = mapped_column(String(20), default="neutral")
    intensidad: Mapped[int] = mapped_column(Integer, default=1)
    actualizado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_aviso_sobrecarga: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EventoEmocional(Base):
    """Historial de estados emocionales — para detectar patrones de sobrecarga."""
    __tablename__ = "eventos_emocionales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    estado: Mapped[str] = mapped_column(String(20))
    intensidad: Mapped[int] = mapped_column(Integer, default=1)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class UsuarioOnboarding(Base):
    """Estado del onboarding conversacional por usuario."""
    __tablename__ = "usuario_onboarding"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), default="")      # Nombre capturado en bienvenida
    fase: Mapped[int] = mapped_column(Integer, default=0)
    # 0=esperando "sí", 1=fase1 activa, 2=fase2 activa, 3=fase3 activa, 4=completado
    paso: Mapped[int] = mapped_column(Integer, default=0)
    # Paso dentro de la fase (0-2). 99=esperando activación del día siguiente.
    contexto: Mapped[str] = mapped_column(Text, default="")            # Texto acumulado para MiroFish
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    registrado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UsuarioProactividad(Base):
    """Configuración y estado del motor de proactividad por usuario."""
    __tablename__ = "usuario_proactividad"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    proactive_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    morning_brief_hour: Mapped[int] = mapped_column(Integer, default=8)  # Hora local preferida (0-23)
    mensajes_hoy: Mapped[int] = mapped_column(Integer, default=0)        # Contador diario
    ultimo_reset: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)      # Cuándo se reseteó el contador
    ultimo_morning_brief: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_weekly_review: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_conflict_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EventoComportamiento(Base):
    """Eventos de comportamiento del usuario — para análisis de patrones semanales."""
    __tablename__ = "eventos_comportamiento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    tipo: Mapped[str] = mapped_column(String(50))
    # Valores: "message_sent", "reminder_created", "reminder_cancelled",
    #          "proactive_sent", "proactive_engaged"
    hora_dia: Mapped[int] = mapped_column(Integer)      # 0-23 en hora local del usuario
    dia_semana: Mapped[int] = mapped_column(Integer)    # 0=lun, 6=dom
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PerfilAprendizaje(Base):
    """Perfil de aprendizaje actualizado semanalmente por el analizador de patrones."""
    __tablename__ = "perfil_aprendizaje"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    perfil: Mapped[str] = mapped_column(Text, default="")   # Texto en lenguaje natural para el prompt
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    eventos_analizados: Mapped[int] = mapped_column(Integer, default=0)


class UsuarioMiroFish(Base):
    """Estado MiroFish por usuario — project_id y graph_id del grafo de conocimiento."""
    __tablename__ = "usuario_mirofish"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    graph_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UsuarioGoogleAuth(Base):
    """Tokens OAuth 2.0 de Google Calendar por usuario."""
    __tablename__ = "usuario_google_auth"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text, default="")  # para refrescar sin re-autorizar
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # cuándo vence el access_token
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)         # email de Google (solo para display)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MemoriaLargoPlazo(Base):
    """
    Resumen comprimido del historial de conversación del usuario.
    Se regenera con Haiku cada 20 mensajes nuevos para mantener contexto
    histórico sin necesidad de pasar cientos de mensajes al LLM principal.
    """
    __tablename__ = "memoria_largo_plazo"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    resumen_texto: Mapped[str] = mapped_column(Text, default="")
    # ID del último mensaje de la tabla `mensajes` ya incorporado al resumen
    ultimo_mensaje_id: Mapped[int] = mapped_column(Integer, default=0)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def _migrar_columnas(conn):
    """
    Aplica migraciones incrementales: renombra columnas legacy y agrega columnas nuevas.
    Cada sentencia es idempotente — el except silencia errores de "ya existe / no existe".
    """
    migraciones = [
        # ── Correcciones de nombre legacy ────────────────────────────────────────
        "ALTER TABLE mensajes RENAME COLUMN rol TO role",
        # ── Columnas nuevas ───────────────────────────────────────────────────────
        "ALTER TABLE usuario_ubicacion ADD COLUMN ciudad_actual VARCHAR(100)",
        "ALTER TABLE usuario_ubicacion ADD COLUMN ciudad_actual_expira TIMESTAMP",
        # Soporte DST: nombre IANA de timezone (ej: "America/New_York")
        "ALTER TABLE timezone_usuarios ADD COLUMN timezone_nombre VARCHAR(60)",

        # ── Tablas nuevas (idempotentes — IF NOT EXISTS) ──────────────────────────
        # Estas CREATE TABLE se agregan aquí como respaldo explícito porque create_all
        # puede fallar silenciosamente en Supabase con PgBouncer (transaction mode).
        # Se ejecutan en cada arranque; IF NOT EXISTS las hace seguras de repetir.
        """
        CREATE TABLE IF NOT EXISTS memoria_largo_plazo (
            telefono    VARCHAR(50) PRIMARY KEY,
            resumen_texto TEXT        NOT NULL DEFAULT '',
            ultimo_mensaje_id INTEGER NOT NULL DEFAULT 0,
            actualizado TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS usuario_google_auth (
            telefono      VARCHAR(50) PRIMARY KEY,
            access_token  TEXT        NOT NULL DEFAULT '',
            refresh_token TEXT        NOT NULL DEFAULT '',
            expires_at    TIMESTAMP,
            email         VARCHAR(200),
            actualizado   TIMESTAMP
        )
        """,
    ]
    for sql in migraciones:
        try:
            await conn.execute(text(sql))
            logger.info(f"[DB] Migración OK: {sql[:60]}")
        except Exception:
            pass  # Ya aplicada o no aplica — ignorar


async def inicializar_db():
    """Crea las tablas si no existen y aplica migraciones."""
    tablas_esperadas = set(Base.metadata.tables.keys())
    logger.info(f"[DB] Driver: {'PostgreSQL/asyncpg' if _ES_POSTGRES else 'SQLite'}")
    logger.info(f"[DB] Tablas en metadata ({len(tablas_esperadas)}): {sorted(tablas_esperadas)}")

    try:
        async with engine.begin() as conn:
            # Paso 1: create_all — crea las tablas que no existen
            logger.info("[DB] Ejecutando create_all...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("[DB] create_all completado")

            # Paso 2: verificar qué tablas existen realmente en el schema public
            if _ES_POSTGRES:
                resultado = await conn.execute(text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                ))
                tablas_en_db = {row[0] for row in resultado.fetchall()}
                logger.info(f"[DB] Tablas en Supabase/public: {sorted(tablas_en_db)}")

                faltantes = tablas_esperadas - tablas_en_db
                if faltantes:
                    logger.warning(f"[DB] Tablas faltantes después de create_all: {sorted(faltantes)}")
                    # Forzar creación explícita con CREATE TABLE IF NOT EXISTS
                    for nombre in sorted(faltantes):
                        tabla = Base.metadata.tables[nombre]
                        ddl = str(tabla.compile(dialect=conn.dialect)) if hasattr(tabla, "compile") else None
                        # Usar CreateTable de SQLAlchemy para generar el DDL correcto
                        from sqlalchemy.schema import CreateTable
                        ddl_str = str(CreateTable(tabla).compile(conn.dialect))
                        # Insertar IF NOT EXISTS manualmente
                        ddl_str = ddl_str.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
                        logger.info(f"[DB] Creando tabla '{nombre}' explícitamente...")
                        await conn.execute(text(ddl_str))
                        logger.info(f"[DB] Tabla '{nombre}' creada OK")
                else:
                    logger.info("[DB] Todas las tablas presentes en Supabase ✓")

            # Paso 3: migraciones de columnas
            await _migrar_columnas(conn)
            logger.info("[DB] Migraciones aplicadas")

    except Exception as e:
        logger.error(f"[DB] ERROR en inicializar_db: {type(e).__name__}: {e}", exc_info=True)
        raise


async def guardar_timezone(telefono: str, offset_minutos: int, timezone_nombre: str | None = None):
    """
    Guarda la zona horaria del usuario.
    Si se provee timezone_nombre (IANA, ej: 'America/New_York'), se usa para cálculo DST.
    offset_minutos se mantiene como fallback legacy.
    """
    async with async_session() as session:
        query = select(TimezoneUsuario).where(TimezoneUsuario.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if registro:
            registro.offset_minutos = offset_minutos
            if timezone_nombre:
                registro.timezone_nombre = timezone_nombre
            registro.actualizado = datetime.utcnow()
        else:
            session.add(TimezoneUsuario(
                telefono=telefono,
                offset_minutos=offset_minutos,
                timezone_nombre=timezone_nombre,
                actualizado=datetime.utcnow()
            ))
        await session.commit()


async def obtener_timezone(telefono: str) -> int | None:
    """
    Retorna el offset ACTUAL en minutos considerando DST.
    Si hay timezone_nombre (IANA), computa el offset real para hoy.
    Si solo hay offset_minutos (legacy), lo retorna como fallback.
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    async with async_session() as session:
        query = select(TimezoneUsuario).where(TimezoneUsuario.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if not registro:
            return None
        if registro.timezone_nombre:
            try:
                tz = ZoneInfo(registro.timezone_nombre)
                offset_actual = int(datetime.now(tz).utcoffset().total_seconds() / 60)
                return offset_actual
            except (ZoneInfoNotFoundError, Exception):
                pass  # fallback al offset fijo
        return registro.offset_minutos


async def guardar_mensaje(telefono: str, role: str, content: str):
    """Guarda un mensaje en el historial de conversación."""
    try:
        async with async_session() as session:
            mensaje = Mensaje(
                telefono=telefono,
                role=role,
                content=content,
                timestamp=datetime.utcnow()
            )
            session.add(mensaje)
            await session.commit()
    except Exception as e:
        logger.error(f"[DB] Error guardando mensaje de {telefono}: {type(e).__name__}: {e}")


async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:  # noqa: C901
    """
    Recupera los últimos N mensajes de una conversación.

    Args:
        telefono: Número de teléfono del cliente
        limite: Máximo de mensajes a recuperar (default: 20)

    Returns:
        Lista de diccionarios con role y content
    """
    try:
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
    except Exception as e:
        logger.error(f"[DB] Error obteniendo historial de {telefono}: {type(e).__name__}: {e}")
        return []


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


async def obtener_ubicacion(telefono: str) -> dict | None:
    """Retorna ciudad, país, industria y datos de ciudad temporal del usuario, o None si no existe."""
    async with async_session() as session:
        query = select(UsuarioUbicacion).where(UsuarioUbicacion.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if not r:
            return None
        return {
            "ciudad": r.ciudad,
            "pais": r.pais,
            "industria": r.industria,
            "ciudad_actual": r.ciudad_actual,
            "ciudad_actual_expira": r.ciudad_actual_expira,
        }


async def obtener_ciudad_actual(telefono: str) -> str | None:
    """
    Retorna la ciudad efectiva del usuario para clima/tráfico.
    Prioriza la ciudad temporal (viaje) si está activa.
    Al expirar, limpia automáticamente y retorna la ciudad de residencia.
    """
    async with async_session() as session:
        query = select(UsuarioUbicacion).where(UsuarioUbicacion.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if not r:
            return None

        ahora = datetime.utcnow()

        # Ciudad temporal activa y vigente
        if r.ciudad_actual and r.ciudad_actual_expira and ahora < r.ciudad_actual_expira:
            return r.ciudad_actual

        # Ciudad temporal expirada — limpiarla
        if r.ciudad_actual and r.ciudad_actual_expira and ahora >= r.ciudad_actual_expira:
            r.ciudad_actual = None
            r.ciudad_actual_expira = None
            r.actualizado = ahora
            await session.commit()

        return r.ciudad


async def guardar_ciudad_temporal(telefono: str, ciudad: str, dias: int = 3):
    """Guarda una ciudad temporal (viaje) con expiración automática."""
    expira = datetime.utcnow() + timedelta(days=max(1, min(dias, 30)))
    async with async_session() as session:
        query = select(UsuarioUbicacion).where(UsuarioUbicacion.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if r:
            r.ciudad_actual = ciudad
            r.ciudad_actual_expira = expira
            r.actualizado = datetime.utcnow()
        else:
            session.add(UsuarioUbicacion(
                telefono=telefono,
                ciudad_actual=ciudad,
                ciudad_actual_expira=expira,
                actualizado=datetime.utcnow(),
            ))
        await session.commit()


async def limpiar_ciudad_temporal(telefono: str):
    """Borra la ciudad temporal del usuario (volvió de viaje)."""
    async with async_session() as session:
        query = select(UsuarioUbicacion).where(UsuarioUbicacion.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if r:
            r.ciudad_actual = None
            r.ciudad_actual_expira = None
            r.actualizado = datetime.utcnow()
            await session.commit()


async def guardar_ubicacion(telefono: str, ciudad: str | None = None, pais: str | None = None, industria: str | None = None):
    """Guarda o actualiza la ubicación del usuario."""
    async with async_session() as session:
        query = select(UsuarioUbicacion).where(UsuarioUbicacion.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if r:
            if ciudad is not None:
                r.ciudad = ciudad
            if pais is not None:
                r.pais = pais
            if industria is not None:
                r.industria = industria
            r.actualizado = datetime.utcnow()
        else:
            session.add(UsuarioUbicacion(
                telefono=telefono, ciudad=ciudad, pais=pais, industria=industria,
                actualizado=datetime.utcnow()
            ))
        await session.commit()


async def ya_enviada_noticia(telefono: str, url_hash: str) -> bool:
    """Retorna True si el artículo ya fue enviado a este usuario (en los últimos 7 días)."""
    async with async_session() as session:
        desde = datetime.utcnow() - timedelta(days=7)
        query = (
            select(NoticiaEnviada)
            .where(NoticiaEnviada.telefono == telefono)
            .where(NoticiaEnviada.url_hash == url_hash)
            .where(NoticiaEnviada.enviada_en >= desde)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none() is not None


async def marcar_noticia_enviada(telefono: str, url_hash: str):
    """Registra que un artículo fue enviado al usuario."""
    async with async_session() as session:
        session.add(NoticiaEnviada(telefono=telefono, url_hash=url_hash, enviada_en=datetime.utcnow()))
        await session.commit()


async def guardar_estado_emocional(telefono: str, estado: str, intensidad: int):
    """Guarda el estado emocional actual del usuario."""
    async with async_session() as session:
        query = select(UsuarioEstadoEmocional).where(UsuarioEstadoEmocional.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        ahora = datetime.utcnow()
        if r:
            r.estado = estado
            r.intensidad = intensidad
            r.actualizado = ahora
        else:
            session.add(UsuarioEstadoEmocional(
                telefono=telefono, estado=estado, intensidad=intensidad, actualizado=ahora
            ))
        # Guardar evento en historial
        session.add(EventoEmocional(
            telefono=telefono, estado=estado, intensidad=intensidad, timestamp=ahora
        ))
        await session.commit()


async def obtener_estado_emocional(telefono: str) -> dict | None:
    """Retorna el estado emocional actual del usuario."""
    async with async_session() as session:
        query = select(UsuarioEstadoEmocional).where(UsuarioEstadoEmocional.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if not r:
            return None
        return {
            "estado": r.estado,
            "intensidad": r.intensidad,
            "actualizado": r.actualizado,
            "ultimo_aviso_sobrecarga": r.ultimo_aviso_sobrecarga,
        }


async def contar_eventos_estres_recientes(telefono: str, horas: int = 24) -> int:
    """Cuenta eventos de estrés/agotamiento (intensidad ≥ 2) en las últimas N horas."""
    async with async_session() as session:
        desde = datetime.utcnow() - timedelta(hours=horas)
        query = (
            select(EventoEmocional)
            .where(EventoEmocional.telefono == telefono)
            .where(EventoEmocional.estado.in_(["stress", "exhaustion"]))
            .where(EventoEmocional.intensidad >= 2)
            .where(EventoEmocional.timestamp >= desde)
        )
        result = await session.execute(query)
        return len(result.scalars().all())


async def ya_avisado_sobrecarga_hoy(telefono: str) -> bool:
    """Retorna True si ya se envió un aviso de sobrecarga hoy (UTC)."""
    async with async_session() as session:
        query = select(UsuarioEstadoEmocional).where(UsuarioEstadoEmocional.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if not r or not r.ultimo_aviso_sobrecarga:
            return False
        return r.ultimo_aviso_sobrecarga.date() >= datetime.utcnow().date()


async def marcar_aviso_sobrecarga(telefono: str):
    """Registra que se envió un aviso de sobrecarga hoy."""
    async with async_session() as session:
        query = select(UsuarioEstadoEmocional).where(UsuarioEstadoEmocional.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if r:
            r.ultimo_aviso_sobrecarga = datetime.utcnow()
            await session.commit()


async def obtener_onboarding(telefono: str) -> dict | None:
    """Retorna el estado de onboarding del usuario, o None si no existe registro."""
    async with async_session() as session:
        query = select(UsuarioOnboarding).where(UsuarioOnboarding.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if not r:
            return None
        return {
            "telefono": r.telefono,
            "nombre": r.nombre,
            "fase": r.fase,
            "paso": r.paso,
            "contexto": r.contexto,
            "actualizado": r.actualizado,
            "completado_en": r.completado_en,
            "registrado_en": r.registrado_en,
        }


async def guardar_onboarding(telefono: str, **kwargs):
    """Crea o actualiza el estado de onboarding de un usuario."""
    async with async_session() as session:
        query = select(UsuarioOnboarding).where(UsuarioOnboarding.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if r:
            for key, val in kwargs.items():
                setattr(r, key, val)
            r.actualizado = datetime.utcnow()
        else:
            nuevo = UsuarioOnboarding(
                telefono=telefono,
                registrado_en=datetime.utcnow(),
                actualizado=datetime.utcnow(),
            )
            for key, val in kwargs.items():
                setattr(nuevo, key, val)
            session.add(nuevo)
        await session.commit()


async def obtener_usuarios_onboarding_pendientes() -> list[dict]:
    """
    Retorna usuarios que están en paso=99 (esperando activación del siguiente día)
    y han pasado al menos 18 horas desde la última actualización.
    """
    async with async_session() as session:
        limite = datetime.utcnow() - timedelta(hours=18)
        query = (
            select(UsuarioOnboarding)
            .where(UsuarioOnboarding.paso == 99)
            .where(UsuarioOnboarding.fase.in_([1, 2]))
            .where(UsuarioOnboarding.actualizado <= limite)
        )
        result = await session.execute(query)
        registros = result.scalars().all()
        return [
            {
                "telefono": r.telefono,
                "nombre": r.nombre,
                "fase": r.fase,
                "paso": r.paso,
                "contexto": r.contexto,
            }
            for r in registros
        ]


async def obtener_proactividad(telefono: str) -> dict | None:
    """Retorna el estado de proactividad del usuario, o None si no existe."""
    async with async_session() as session:
        query = select(UsuarioProactividad).where(UsuarioProactividad.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if not r:
            return None
        return {
            "proactive_enabled": r.proactive_enabled,
            "morning_brief_hour": r.morning_brief_hour,
            "mensajes_hoy": r.mensajes_hoy,
            "ultimo_reset": r.ultimo_reset,
            "ultimo_morning_brief": r.ultimo_morning_brief,
            "ultimo_weekly_review": r.ultimo_weekly_review,
            "ultimo_conflict_check": r.ultimo_conflict_check,
        }


async def guardar_proactividad(telefono: str, **kwargs):
    """Crea o actualiza el estado de proactividad de un usuario."""
    async with async_session() as session:
        query = select(UsuarioProactividad).where(UsuarioProactividad.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if r:
            for key, val in kwargs.items():
                setattr(r, key, val)
        else:
            nuevo = UsuarioProactividad(telefono=telefono)
            for key, val in kwargs.items():
                setattr(nuevo, key, val)
            session.add(nuevo)
        await session.commit()


async def incrementar_mensajes_proactivos(telefono: str):
    """Incrementa el contador diario de mensajes proactivos, reseteando si es un día nuevo."""
    async with async_session() as session:
        query = select(UsuarioProactividad).where(UsuarioProactividad.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        ahora = datetime.utcnow()

        if not r:
            session.add(UsuarioProactividad(
                telefono=telefono,
                mensajes_hoy=1,
                ultimo_reset=ahora,
            ))
        else:
            # Resetear contador si es un día nuevo (UTC)
            if r.ultimo_reset is None or r.ultimo_reset.date() < ahora.date():
                r.mensajes_hoy = 1
                r.ultimo_reset = ahora
            else:
                r.mensajes_hoy = (r.mensajes_hoy or 0) + 1
        await session.commit()


async def obtener_usuarios_proactividad_activos() -> list[dict]:
    """
    Retorna todos los usuarios con onboarding completado (fase=4) y proactividad habilitada.
    """
    async with async_session() as session:
        # JOIN entre onboarding y proactividad (o usuarios sin registro en proactividad aún)
        query_onboarding = (
            select(UsuarioOnboarding)
            .where(UsuarioOnboarding.fase == 4)
        )
        result = await session.execute(query_onboarding)
        usuarios_completados = result.scalars().all()

        activos = []
        for u in usuarios_completados:
            # Obtener config de proactividad (puede no existir → defaults)
            q2 = select(UsuarioProactividad).where(UsuarioProactividad.telefono == u.telefono)
            r2 = await session.execute(q2)
            prov = r2.scalar_one_or_none()

            enabled = prov.proactive_enabled if prov else True
            if not enabled:
                continue

            # Resetear contador diario si es un día nuevo
            ahora = datetime.utcnow()
            mensajes_hoy = 0
            if prov:
                if prov.ultimo_reset is None or prov.ultimo_reset.date() < ahora.date():
                    mensajes_hoy = 0
                else:
                    mensajes_hoy = prov.mensajes_hoy or 0

            activos.append({
                "telefono": u.telefono,
                "nombre": u.nombre,
                "contexto_onboarding": u.contexto,
                "morning_brief_hour": prov.morning_brief_hour if prov else 8,
                "mensajes_hoy": mensajes_hoy,
                "ultimo_morning_brief": prov.ultimo_morning_brief if prov else None,
                "ultimo_weekly_review": prov.ultimo_weekly_review if prov else None,
                "ultimo_conflict_check": prov.ultimo_conflict_check if prov else None,
            })

        return activos


async def obtener_recordatorios_proximas_horas(telefono: str, horas: int) -> list[dict]:
    """Retorna recordatorios activos que vencen en las próximas N horas."""
    async with async_session() as session:
        ahora = datetime.utcnow()
        limite = ahora + timedelta(hours=horas)
        query = (
            select(Recordatorio)
            .where(Recordatorio.telefono == telefono)
            .where(Recordatorio.cancelado == False)
            .where(Recordatorio.enviado == False)
            .where(Recordatorio.fecha_hora >= ahora)
            .where(Recordatorio.fecha_hora <= limite)
            .order_by(Recordatorio.fecha_hora)
        )
        result = await session.execute(query)
        return [
            {"id": r.id, "mensaje": r.mensaje, "fecha_hora": r.fecha_hora}
            for r in result.scalars().all()
        ]


async def obtener_mirofish_estado(telefono: str) -> dict | None:
    """Retorna el estado MiroFish del usuario (project_id, graph_id) o None si no existe."""
    async with async_session() as session:
        query = select(UsuarioMiroFish).where(UsuarioMiroFish.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if not registro:
            return None
        return {
            "project_id": registro.project_id,
            "graph_id": registro.graph_id,
            "actualizado": registro.actualizado,
        }


async def guardar_mirofish_estado(
    telefono: str,
    project_id: str | None = None,
    graph_id: str | None = None,
):
    """Guarda o actualiza el estado MiroFish de un usuario."""
    async with async_session() as session:
        query = select(UsuarioMiroFish).where(UsuarioMiroFish.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if registro:
            if project_id is not None:
                registro.project_id = project_id
            if graph_id is not None:
                registro.graph_id = graph_id
            registro.actualizado = datetime.utcnow()
        else:
            session.add(UsuarioMiroFish(
                telefono=telefono,
                project_id=project_id,
                graph_id=graph_id,
                actualizado=datetime.utcnow(),
            ))
        await session.commit()


async def guardar_evento_comportamiento(
    telefono: str, tipo: str, hora_dia: int, dia_semana: int, metadata: dict | None = None
):
    """Registra un evento de comportamiento del usuario."""
    async with async_session() as session:
        session.add(EventoComportamiento(
            telefono=telefono,
            tipo=tipo,
            hora_dia=hora_dia,
            dia_semana=dia_semana,
            metadata_json=json.dumps(metadata) if metadata else None,
            timestamp=datetime.utcnow(),
        ))
        await session.commit()


async def obtener_eventos_comportamiento(telefono: str, dias: int = 30) -> list[dict]:
    """Retorna los eventos de comportamiento de los últimos N días."""
    async with async_session() as session:
        desde = datetime.utcnow() - timedelta(days=dias)
        query = (
            select(EventoComportamiento)
            .where(EventoComportamiento.telefono == telefono)
            .where(EventoComportamiento.timestamp >= desde)
            .order_by(EventoComportamiento.timestamp)
        )
        result = await session.execute(query)
        return [
            {
                "tipo": e.tipo,
                "hora_dia": e.hora_dia,
                "dia_semana": e.dia_semana,
                "metadata": json.loads(e.metadata_json) if e.metadata_json else {},
                "timestamp": e.timestamp,
            }
            for e in result.scalars().all()
        ]


async def contar_eventos_comportamiento(telefono: str, dias: int = 30) -> int:
    """Cuenta el total de eventos de comportamiento en los últimos N días."""
    async with async_session() as session:
        desde = datetime.utcnow() - timedelta(days=dias)
        query = (
            select(EventoComportamiento)
            .where(EventoComportamiento.telefono == telefono)
            .where(EventoComportamiento.timestamp >= desde)
        )
        result = await session.execute(query)
        return len(result.scalars().all())


async def guardar_perfil_aprendizaje(telefono: str, perfil: str, eventos_count: int = 0):
    """Guarda o actualiza el perfil de aprendizaje del usuario."""
    async with async_session() as session:
        query = select(PerfilAprendizaje).where(PerfilAprendizaje.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        if r:
            r.perfil = perfil
            r.actualizado = datetime.utcnow()
            r.eventos_analizados = eventos_count
        else:
            session.add(PerfilAprendizaje(
                telefono=telefono,
                perfil=perfil,
                actualizado=datetime.utcnow(),
                eventos_analizados=eventos_count,
            ))
        await session.commit()


async def obtener_perfil_aprendizaje(telefono: str) -> str | None:
    """Retorna el perfil de aprendizaje del usuario o None si no existe."""
    async with async_session() as session:
        query = select(PerfilAprendizaje).where(PerfilAprendizaje.telefono == telefono)
        result = await session.execute(query)
        r = result.scalar_one_or_none()
        return r.perfil if r and r.perfil else None


async def borrar_datos_aprendizaje(telefono: str):
    """Borra todos los eventos de comportamiento y el perfil del usuario."""
    async with async_session() as session:
        # Borrar eventos
        q1 = select(EventoComportamiento).where(EventoComportamiento.telefono == telefono)
        r1 = await session.execute(q1)
        for e in r1.scalars().all():
            await session.delete(e)
        # Borrar perfil
        q2 = select(PerfilAprendizaje).where(PerfilAprendizaje.telefono == telefono)
        r2 = await session.execute(q2)
        p = r2.scalar_one_or_none()
        if p:
            await session.delete(p)
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


# ─── MEMORIA A LARGO PLAZO ────────────────────────────────────────────────────

async def obtener_memoria_largo_plazo(telefono: str) -> dict | None:
    """Retorna el resumen de memoria acumulada del usuario, o None si aún no existe."""
    async with async_session() as session:
        query = select(MemoriaLargoPlazo).where(MemoriaLargoPlazo.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if not registro:
            return None
        return {
            "resumen_texto": registro.resumen_texto,
            "ultimo_mensaje_id": registro.ultimo_mensaje_id,
            "actualizado": registro.actualizado,
        }


async def guardar_memoria_largo_plazo(telefono: str, resumen_texto: str, ultimo_mensaje_id: int):
    """Guarda o actualiza el resumen de memoria a largo plazo del usuario."""
    async with async_session() as session:
        query = select(MemoriaLargoPlazo).where(MemoriaLargoPlazo.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if registro:
            registro.resumen_texto = resumen_texto
            registro.ultimo_mensaje_id = ultimo_mensaje_id
            registro.actualizado = datetime.utcnow()
        else:
            session.add(MemoriaLargoPlazo(
                telefono=telefono,
                resumen_texto=resumen_texto,
                ultimo_mensaje_id=ultimo_mensaje_id,
                actualizado=datetime.utcnow(),
            ))
        await session.commit()


async def obtener_mensajes_desde_id(telefono: str, desde_id: int, limite: int = 40) -> list[dict]:
    """
    Recupera mensajes con ID estrictamente mayor a `desde_id`.
    Usado por el generador de resúmenes para saber qué hay de nuevo desde el último ciclo.
    """
    async with async_session() as session:
        query = (
            select(Mensaje)
            .where(Mensaje.telefono == telefono)
            .where(Mensaje.id > desde_id)
            .order_by(Mensaje.id.asc())
            .limit(limite)
        )
        result = await session.execute(query)
        mensajes = result.scalars().all()
        return [{"id": m.id, "role": m.role, "content": m.content} for m in mensajes]


async def obtener_ultimo_id_mensaje(telefono: str) -> int:
    """Retorna el ID del mensaje más reciente del usuario (0 si no hay ninguno)."""
    async with async_session() as session:
        query = (
            select(Mensaje.id)
            .where(Mensaje.telefono == telefono)
            .order_by(Mensaje.id.desc())
            .limit(1)
        )
        result = await session.execute(query)
        row = result.scalar_one_or_none()
        return row or 0


# ─── GOOGLE CALENDAR AUTH ─────────────────────────────────────────────────────

async def guardar_google_auth(
    telefono: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    email: str = "",
):
    """Guarda o actualiza los tokens de OAuth de Google Calendar del usuario."""
    async with async_session() as session:
        query = select(UsuarioGoogleAuth).where(UsuarioGoogleAuth.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if registro:
            registro.access_token = access_token
            if refresh_token:                       # no sobreescribir con vacío
                registro.refresh_token = refresh_token
            registro.expires_at = expires_at
            if email:
                registro.email = email
            registro.actualizado = datetime.utcnow()
        else:
            session.add(UsuarioGoogleAuth(
                telefono=telefono,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                email=email,
                actualizado=datetime.utcnow(),
            ))
        await session.commit()


async def obtener_google_auth(telefono: str) -> dict | None:
    """Retorna los tokens de Google Calendar del usuario, o None si no está conectado."""
    async with async_session() as session:
        query = select(UsuarioGoogleAuth).where(UsuarioGoogleAuth.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if not registro:
            return None
        return {
            "access_token": registro.access_token,
            "refresh_token": registro.refresh_token,
            "expires_at": registro.expires_at,
            "email": registro.email or "",
        }


async def obtener_todos_con_google_calendar() -> list[str]:
    """
    Retorna la lista de teléfonos de todos los usuarios que tienen Google Calendar conectado.
    Usado por el scheduler para verificar recordatorios proactivos de eventos próximos.
    """
    async with async_session() as session:
        query = select(UsuarioGoogleAuth.telefono)
        result = await session.execute(query)
        return [row[0] for row in result.fetchall()]
