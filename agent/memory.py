# agent/memory.py — Memoria de conversaciones con SQLite
# Dona

"""
Sistema de memoria de Dona. Guarda el historial de conversaciones
por número de teléfono usando SQLite (local) o PostgreSQL (producción).
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from sqlalchemy import Boolean, DateTime, Integer, String, Text, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

load_dotenv()
logger = logging.getLogger("dona")

# Configuración de base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dona.db")

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
        pool_size=5,
        max_overflow=2,
        pool_timeout=10,       # máx 10s esperando una conexión libre
        pool_recycle=300,      # reciclar conexiones cada 5 min (evita cuelgues de PgBouncer)
        pool_pre_ping=True,    # verificar que la conexión esté viva antes de usarla
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

    # Último INTENTO de envío (UTC). Además de informativo, funciona como
    # marcador de claim del scheduler (Fase 0 · 2.3): un recordatorio con
    # ultimo_envio reciente está "reclamado" y otro proceso no debe enviarlo.
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
    # Disparador 8: última vez que se envió un consejo estratégico (MiroFish)
    ultimo_consejo_estrategico: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Gmail: última vez que el usuario pidió revisar correos (para filtrar duplicados)
    ultimo_revision_correo: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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
    # Contexto acumulado pendiente de sincronizar con el grafo
    contexto_pendiente: Mapped[str] = mapped_column(Text, default="")
    # Número de mensajes relevantes acumulados desde la última sincronización
    mensajes_desde_sync: Mapped[int] = mapped_column(Integer, default=0)


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


# ── Modelos de productividad (antes en memoria, ahora persistentes) ─────────

class Tarea(Base):
    """Tarea de productividad del usuario — persistente en PostgreSQL."""
    __tablename__ = "tareas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    descripcion: Mapped[str] = mapped_column(Text)
    prioridad: Mapped[str] = mapped_column(String(20), default="normal")
    completada: Mapped[bool] = mapped_column(Boolean, default=False)
    creada: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Lista(Base):
    """Lista personalizada del usuario (compras, metas, ideas, etc.)."""
    __tablename__ = "listas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    nombre: Mapped[str] = mapped_column(String(100))
    creada: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ItemLista(Base):
    """Ítem dentro de una lista del usuario."""
    __tablename__ = "items_lista"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lista_id: Mapped[int] = mapped_column(Integer, index=True)
    texto: Mapped[str] = mapped_column(Text)
    completado: Mapped[bool] = mapped_column(Boolean, default=False)
    agregado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventoUsuario(Base):
    """Evento de calendario local del usuario — persistente en PostgreSQL."""
    __tablename__ = "eventos_usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    fecha_hora: Mapped[str] = mapped_column(String(50))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    cancelado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MensajeProcesado(Base):
    """Deduplicación de mensajes de webhook — persistente tras restart."""
    __tablename__ = "mensajes_procesados"

    mensaje_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    telefono: Mapped[str] = mapped_column(String(50))
    procesado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RecordatorioGCalEnviado(Base):
    """Registro de recordatorios de Google Calendar ya enviados — evita duplicados tras restart."""
    __tablename__ = "recordatorios_gcal_enviados"

    clave: Mapped[str] = mapped_column(String(200), primary_key=True)
    enviado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SesionConversacion(Base):
    """Sesión de conversación — agrupa mensajes por ventana de inactividad."""
    __tablename__ = "sesiones_conversacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ultimo_mensaje: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    mensajes_count: Mapped[int] = mapped_column(Integer, default=0)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Sprint 1 — Fundaciones creativas ──────────────────────────────────────
# Assets generados (imágenes/videos/audios/webs), jobs asíncronos y billing.
# Estas tablas son la infra sobre la que montamos las capacidades creativas.

class AssetGenerado(Base):
    """
    Registro de un asset creativo generado por Dona (imagen, video, audio, web, etc.).
    El contenido binario vive en R2 / filesystem; acá sólo metadatos + URL.
    """
    __tablename__ = "assets_generados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    tipo: Mapped[str] = mapped_column(String(30), index=True)        # image | video | audio | web | doc
    url_publica: Mapped[str] = mapped_column(Text, default="")
    key_storage: Mapped[str] = mapped_column(Text, default="")       # key en R2 o path relativo filesystem
    backend: Mapped[str] = mapped_column(String(20), default="r2")   # r2 | fs
    prompt: Mapped[str] = mapped_column(Text, default="")
    modelo: Mapped[str] = mapped_column(String(80), default="")      # "nanobanana", "ideogram-v2", etc.
    costo_usd: Mapped[str] = mapped_column(String(20), default="0")  # decimal serializado — evita float
    costo_creditos: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(80), default="")
    bytes_size: Mapped[int] = mapped_column(Integer, default=0)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")       # extras libres (dimensiones, duración, etc.)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class JobCreativo(Base):
    """
    Tracking de jobs asíncronos (generación de video/imagen lenta, publicación web, etc.).
    No guarda el payload completo — sólo estado + referencia al asset resultante.
    """
    __tablename__ = "jobs_creativos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    tipo: Mapped[str] = mapped_column(String(60))                    # "generar_video_runway", etc.
    estado: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|running|done|error|cancelled
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    asset_id_resultado: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    backend: Mapped[str] = mapped_column(String(20), default="arq")  # arq | inproc
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SaldoCreditos(Base):
    """Balance de créditos prepagos del usuario. 1 fila por número."""
    __tablename__ = "saldo_creditos"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    saldo: Mapped[int] = mapped_column(Integer, default=0)
    total_comprado: Mapped[int] = mapped_column(Integer, default=0)
    total_consumido: Mapped[int] = mapped_column(Integer, default=0)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TransaccionCredito(Base):
    """
    Audit trail de movimientos de créditos. INSERT-only, nunca se edita.
    `delta` positivo = acreditación (compra, regalo), negativo = consumo.
    """
    __tablename__ = "transacciones_credito"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    razon: Mapped[str] = mapped_column(String(120), default="")
    stripe_session_id: Mapped[str] = mapped_column(String(200), default="", index=True)  # idempotencia
    asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saldo_resultante: Mapped[int] = mapped_column(Integer, default=0)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class IdempotenciaCredito(Base):
    """Cerrojo de idempotencia ATÓMICO para acreditaciones (Fase 1 · 3.1).

    `acreditar()` deduplicaba por `stripe_session_id` con un SELECT-then-INSERT
    que racea bajo concurrencia (dos entregas del mismo evento Stripe → doble
    crédito). Esta tabla da la barrera atómica: `acreditar` inserta la `clave`
    en la MISMA transacción que el incremento de saldo; un segundo INSERT con la
    misma PK lanza IntegrityError y TODA la transacción (incluido el saldo) hace
    rollback → no doble-acredita ni en reentrega secuencial ni concurrente.

    Tabla NUEVA y vacía a propósito: evita retrofittear un UNIQUE sobre
    transacciones_credito (que con duplicados previos haría fallar el índice, y
    el filtro de _migrar_columnas se tragaría el error en silencio dejando el
    fix inerte). La crea create_all (fail-closed por 0.3)."""
    __tablename__ = "idempotencia_credito"

    clave: Mapped[str] = mapped_column(String(250), primary_key=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SuscripcionStripe(Base):
    """
    Suscripción Stripe activa de un usuario (T1.3.A).

    Una fila por suscripción Stripe (PK = subscription_id). Permite mapear
    eventos de Stripe (renovaciones, cambios de plan, cancelaciones) al
    teléfono del usuario y al plan vigente.

    `creditos_mensuales` se acredita cada vez que llega `invoice.payment_succeeded`
    (decisión owner: créditos acumulables, no se resetean). `ultimo_invoice_acreditado`
    es la llave de idempotencia: si el mismo invoice.id se reentrega no acreditamos
    dos veces.

    Esta tabla **no** se usa todavía — T1.3.A solo crea la estructura.
    Los handlers que la pueblan se agregan en T1.3.C/D/E.
    """
    __tablename__ = "suscripcion_stripe"

    subscription_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(String(200), index=True)
    plan_codigo: Mapped[str] = mapped_column(String(50))   # "premium" | "pro"
    price_id: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40))         # active | past_due | canceled | incomplete
    creditos_mensuales: Mapped[int] = mapped_column(Integer)
    ultimo_invoice_acreditado: Mapped[str] = mapped_column(String(200), default="")
    # T2.0.B — flag de idempotencia para el welcome con password.
    # Se setea a True cuando enviar_bienvenida_premium logró enviar (o
    # simular en DRY_RUN). Si Stripe reintenta el webhook o el evento
    # llega de nuevo por algún motivo, _procesar_checkout_subscription
    # NO reenvía el welcome.
    bienvenida_enviada: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventoStripeProcesado(Base):
    """
    Marca de eventos Stripe ya procesados — idempotencia a nivel de evento (T1.3.A).

    Cada evento Stripe tiene un `event.id` único. Antes de procesar un evento
    hacemos lookup por `event_id`; si ya está, retornamos sin reprocesar.

    Esta tabla **no** se usa todavía — T1.3.A solo crea la estructura.
    """
    __tablename__ = "evento_stripe_procesado"

    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(80), index=True)
    recibido_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Timeout de sesión: 30 minutos de inactividad → nueva sesión
SESION_TIMEOUT_MINUTOS = 30


_MIGRACIONES = [
    # ── Correcciones de nombre legacy ────────────────────────────────────────
    "ALTER TABLE mensajes RENAME COLUMN rol TO role",
    # ── Columnas nuevas ───────────────────────────────────────────────
    "ALTER TABLE usuario_ubicacion ADD COLUMN ciudad_actual VARCHAR(100)",
    "ALTER TABLE usuario_ubicacion ADD COLUMN ciudad_actual_expira TIMESTAMP",
    "ALTER TABLE timezone_usuarios ADD COLUMN timezone_nombre VARCHAR(60)",
    "ALTER TABLE usuario_mirofish ADD COLUMN contexto_pendiente TEXT DEFAULT ''",
    "ALTER TABLE usuario_mirofish ADD COLUMN mensajes_desde_sync INTEGER DEFAULT 0",
    "ALTER TABLE usuario_proactividad ADD COLUMN ultimo_consejo_estrategico TIMESTAMP",
    "ALTER TABLE usuario_proactividad ADD COLUMN ultimo_revision_correo TIMESTAMP",
    # T2.0.B — flag de idempotencia para welcome con password derivado.
    # Equivalente a alembic/versions/003_bienvenida_enviada.py. Se aplica
    # en runtime para PostgreSQL prod (Render) ya que el backend no
    # ejecuta `alembic upgrade head` automáticamente.
    "ALTER TABLE suscripcion_stripe ADD COLUMN bienvenida_enviada BOOLEAN DEFAULT FALSE",
    # ── Tablas nuevas (respaldo explícito) ──────────────────────────────────
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
    # ── Fase 1: Persistencia de tools.py ─────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS tareas (
        id          SERIAL PRIMARY KEY,
        telefono    VARCHAR(50) NOT NULL,
        descripcion TEXT        NOT NULL,
        prioridad   VARCHAR(20) NOT NULL DEFAULT 'normal',
        completada  BOOLEAN     NOT NULL DEFAULT FALSE,
        creada      TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_tareas_telefono ON tareas (telefono)",
    """
    CREATE TABLE IF NOT EXISTS listas (
        id       SERIAL PRIMARY KEY,
        telefono VARCHAR(50)  NOT NULL,
        nombre   VARCHAR(100) NOT NULL,
        creada   TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_listas_telefono ON listas (telefono)",
    """
    CREATE TABLE IF NOT EXISTS items_lista (
        id         SERIAL PRIMARY KEY,
        lista_id   INTEGER NOT NULL,
        texto      TEXT    NOT NULL,
        completado BOOLEAN NOT NULL DEFAULT FALSE,
        agregado   TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_items_lista_lista_id ON items_lista (lista_id)",
    """
    CREATE TABLE IF NOT EXISTS eventos_usuario (
        id          SERIAL PRIMARY KEY,
        telefono    VARCHAR(50)  NOT NULL,
        titulo      VARCHAR(200) NOT NULL,
        fecha_hora  VARCHAR(50)  NOT NULL,
        descripcion TEXT         NOT NULL DEFAULT '',
        cancelado   BOOLEAN      NOT NULL DEFAULT FALSE,
        creado      TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_eventos_usuario_telefono ON eventos_usuario (telefono)",
    # ── Fase 1: Deduplicación persistente ────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS mensajes_procesados (
        mensaje_id   VARCHAR(100) PRIMARY KEY,
        telefono     VARCHAR(50)  NOT NULL,
        procesado_en TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_mensajes_procesados_fecha ON mensajes_procesados (procesado_en)",
    # ── Fase 1: Caché GCal persistente ───────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS recordatorios_gcal_enviados (
        clave      VARCHAR(200) PRIMARY KEY,
        enviado_en TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_gcal_enviados_fecha ON recordatorios_gcal_enviados (enviado_en)",
    # ── Fase 4: Tracking de uso de tokens por usuario ────────────────────────
    """
    CREATE TABLE IF NOT EXISTS uso_tokens (
        id              SERIAL PRIMARY KEY,
        telefono        VARCHAR(50)  NOT NULL,
        fecha           DATE         NOT NULL,
        tokens_entrada  INTEGER      NOT NULL DEFAULT 0,
        tokens_salida   INTEGER      NOT NULL DEFAULT 0,
        requests_count  INTEGER      NOT NULL DEFAULT 0,
        UNIQUE(telefono, fecha)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_uso_tokens_tel_fecha ON uso_tokens (telefono, fecha)",
    # ── Fase 5: Sesiones de conversación ─────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS sesiones_conversacion (
        id               SERIAL PRIMARY KEY,
        telefono         VARCHAR(50)  NOT NULL,
        inicio           TIMESTAMP    NOT NULL,
        ultimo_mensaje   TIMESTAMP    NOT NULL,
        mensajes_count   INTEGER      NOT NULL DEFAULT 0,
        activa           BOOLEAN      NOT NULL DEFAULT TRUE
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_sesiones_conv_tel ON sesiones_conversacion (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_sesiones_conv_activa ON sesiones_conversacion (telefono, activa)",
    # ── Sprint 1: Storage + Jobs + Billing ───────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS assets_generados (
        id             SERIAL PRIMARY KEY,
        telefono       VARCHAR(50)  NOT NULL,
        tipo           VARCHAR(30)  NOT NULL,
        url_publica    TEXT         NOT NULL DEFAULT '',
        key_storage    TEXT         NOT NULL DEFAULT '',
        backend        VARCHAR(20)  NOT NULL DEFAULT 'r2',
        prompt         TEXT         NOT NULL DEFAULT '',
        modelo         VARCHAR(80)  NOT NULL DEFAULT '',
        costo_usd      VARCHAR(20)  NOT NULL DEFAULT '0',
        costo_creditos INTEGER      NOT NULL DEFAULT 0,
        mime_type      VARCHAR(80)  NOT NULL DEFAULT '',
        bytes_size     INTEGER      NOT NULL DEFAULT 0,
        meta_json      TEXT         NOT NULL DEFAULT '{}',
        creado         TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_assets_tel ON assets_generados (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_assets_tipo ON assets_generados (tipo)",
    "CREATE INDEX IF NOT EXISTS ix_assets_creado ON assets_generados (creado)",
    """
    CREATE TABLE IF NOT EXISTS jobs_creativos (
        id                 SERIAL PRIMARY KEY,
        telefono           VARCHAR(50) NOT NULL,
        tipo               VARCHAR(60) NOT NULL,
        estado             VARCHAR(20) NOT NULL DEFAULT 'pending',
        params_json        TEXT        NOT NULL DEFAULT '{}',
        asset_id_resultado INTEGER,
        error_msg          TEXT        NOT NULL DEFAULT '',
        intentos           INTEGER     NOT NULL DEFAULT 0,
        backend            VARCHAR(20) NOT NULL DEFAULT 'arq',
        creado             TIMESTAMP,
        actualizado        TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_jobs_tel ON jobs_creativos (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_estado ON jobs_creativos (estado)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_creado ON jobs_creativos (creado)",
    """
    CREATE TABLE IF NOT EXISTS saldo_creditos (
        telefono        VARCHAR(50) PRIMARY KEY,
        saldo           INTEGER     NOT NULL DEFAULT 0,
        total_comprado  INTEGER     NOT NULL DEFAULT 0,
        total_consumido INTEGER     NOT NULL DEFAULT 0,
        actualizado     TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transacciones_credito (
        id                 SERIAL PRIMARY KEY,
        telefono           VARCHAR(50) NOT NULL,
        delta              INTEGER     NOT NULL,
        razon              VARCHAR(120) NOT NULL DEFAULT '',
        stripe_session_id  VARCHAR(200) NOT NULL DEFAULT '',
        asset_id           INTEGER,
        job_id             INTEGER,
        saldo_resultante   INTEGER      NOT NULL DEFAULT 0,
        creado             TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_trans_tel ON transacciones_credito (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_trans_stripe ON transacciones_credito (stripe_session_id)",
    "CREATE INDEX IF NOT EXISTS ix_trans_creado ON transacciones_credito (creado)",
]


async def _migrar_columnas():
    """
    Aplica migraciones incrementales, cada una en su PROPIA transacción.

    Esto evita el problema de PgBouncer/Supabase donde un error en un ALTER TABLE
    aborta toda la transacción y las migraciones siguientes fallan con
    'InFailedSQLTransactionError: current transaction is aborted'.
    """
    # Incluir migraciones del módulo de negocio
    try:
        from agent.business.models import MIGRACIONES_NEGOCIO
        todas = _MIGRACIONES + MIGRACIONES_NEGOCIO
    except ImportError:
        todas = _MIGRACIONES
    # Incluir migraciones del módulo de automation (T2.1.A)
    try:
        from agent.automation.models import MIGRACIONES_AUTOMATION
        todas = todas + MIGRACIONES_AUTOMATION
    except ImportError:
        pass

    for sql in todas:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
            logger.info(f"[DB] Migración OK: {sql.strip()[:60]}")
        except Exception as e:
            err_str = str(e).lower()
            if any(kw in err_str for kw in ("already exists", "does not exist", "duplicate")):
                logger.debug(f"[DB] Migración ya aplicada: {sql.strip()[:60]}")
            else:
                logger.error(f"[DB] Migración FALLÓ: {sql.strip()[:80]} — {e}")


# Clave fija para pg_advisory_xact_lock: serializa el DDL de arranque entre
# workers/pods concurrentes (un solo create_all a la vez → sin races de DDL).
# Valor arbitrario estable ('dona' en hex).
_LOCK_KEY_INIT_DB = 0x646F6E61


async def inicializar_db():
    """Crea las tablas si no existen y aplica migraciones.

    Fail-closed (0.3): en entorno estricto, si el esquema no se puede crear ni
    verificar tras reintentos, ABORTA el arranque en vez de seguir con un
    esquema roto (antes: '# No relanzar' → fail-open, errores silenciosos en
    cada query). Un pg_advisory_xact_lock serializa el DDL entre workers
    concurrentes (evita races de create_all). Dev/test: lenient (loguea)."""
    # Registrar modelos cuyas tablas se crean por create_all pero cuyos módulos
    # solo se importan lazy desde sus endpoints. El import fuerza el registro en
    # Base.metadata.
    from agent.dashboard_lockout import DashboardLoginIntento  # noqa: F401
    from agent.entorno import es_entorno_estricto

    tablas_esperadas = set(Base.metadata.tables.keys())
    logger.info(f"[DB] Driver: {'PostgreSQL/asyncpg' if _ES_POSTGRES else 'SQLite'}")
    logger.info(f"[DB] Tablas en metadata ({len(tablas_esperadas)}): {sorted(tablas_esperadas)}")

    estricto = es_entorno_estricto()
    intentos = 3 if estricto else 1
    ultimo_error: Exception | None = None

    for intento in range(1, intentos + 1):
        try:
            async with engine.begin() as conn:
                if _ES_POSTGRES:
                    # Lock de transacción (se libera al commit): solo un worker
                    # corre el DDL a la vez; el resto espera y ve las tablas ya
                    # creadas (create_all es idempotente).
                    await conn.execute(
                        text("SELECT pg_advisory_xact_lock(:k)").bindparams(
                            k=_LOCK_KEY_INIT_DB
                        )
                    )

                # Paso 1: create_all — crea las tablas que no existen
                logger.info("[DB] Ejecutando create_all...")
                await conn.run_sync(Base.metadata.create_all)
                logger.info("[DB] create_all completado")

                # Paso 2: verificar qué tablas existen realmente en schema public
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
                            from sqlalchemy.schema import CreateTable
                            # compile(dialect=...) — pasar el dialect como `bind`
                            # posicional fallaba con AttributeError (bind.dialect).
                            ddl_str = str(CreateTable(tabla).compile(dialect=conn.dialect))
                            ddl_str = ddl_str.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
                            logger.info(f"[DB] Creando tabla '{nombre}' explícitamente...")
                            await conn.execute(text(ddl_str))
                            logger.info(f"[DB] Tabla '{nombre}' creada OK")
                        # Re-verificar: si TODAVÍA faltan, es un fallo real de
                        # esquema (no un timeout) — no se puede operar así.
                        resultado2 = await conn.execute(text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        ))
                        faltantes_post = tablas_esperadas - {row[0] for row in resultado2.fetchall()}
                        if faltantes_post:
                            raise RuntimeError(
                                f"[DB] Tablas faltantes tras create_all + creación "
                                f"explícita: {sorted(faltantes_post)}"
                            )
                    else:
                        logger.info("[DB] Todas las tablas presentes en Supabase ✓")

            ultimo_error = None
            break
        except Exception as e:
            ultimo_error = e
            logger.error(
                f"[DB] ERROR en inicializar_db (intento {intento}/{intentos}): "
                f"{type(e).__name__}: {e}",
                exc_info=True,
            )
            if intento < intentos:
                await asyncio.sleep(2 * intento)  # backoff lineal para transitorios

    if ultimo_error is not None:
        if estricto:
            # Fail-closed: arrancar con un esquema roto es peor que no arrancar
            # (errores silenciosos en cada query). Render reintenta el deploy.
            raise RuntimeError(
                f"[DB] inicializar_db falló tras {intentos} intento(s) en entorno "
                f"estricto — se aborta el arranque para no operar con un esquema "
                f"incompleto: {type(ultimo_error).__name__}: {ultimo_error}"
            ) from ultimo_error
        logger.error(
            "[DB] inicializar_db falló; en entorno no-estricto (dev/test) se "
            "continúa para no bloquear el desarrollo."
        )

    # Paso 3: migraciones de columnas — FUERA del engine.begin() principal.
    # Cada migración corre en su propia transacción para evitar cascading failures.
    await _migrar_columnas()
    logger.info("[DB] Migraciones aplicadas")


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


# ── Recurrencias: topes y saneamiento (Fase 0 · 2.4) ────────────────────────
# Una recurrencia sub-diaria sin fecha_fin envía mensajes cada 30/60 minutos
# PARA SIEMPRE (riesgo TCPA + molestia). Y tras un downtime, avanzar la
# próxima ocurrencia de a UN paso producía un "catch-up storm": un tick por
# minuto reenviando hasta ponerse al día. Política (confirmada con Hermes):
# el atraso se SANEA avanzando hasta el futuro, no reenviando.

# Tipos de recurrencia con período menor a un día.
RECURRENCIAS_SUB_DIARIAS = {"cada_30_minutos", "cada_hora", "horario"}

# Conjunto canónico de tipos de recurrencia que el scheduler sabe avanzar
# (intervalos fijos + calendario). Cualquier otro tipo —p.ej. alucinado por el
# LLM, que deja 'recurrencia.tipo' libre en el schema de la tool— NO se persiste
# como recurrencia: el scheduler no podría calcular su próxima ocurrencia y
# quedaría sin tope. Validación server-side; no dependemos del enum de la tool.
TIPOS_RECURRENCIA_VALIDOS = RECURRENCIAS_SUB_DIARIAS | {
    "diario",
    "semanal",
    "dias_semana",
    "mensual",
}

# fecha_fin default para recurrencias sub-diarias creadas sin límite explícito.
DIAS_FECHA_FIN_DEFAULT_SUB_DIARIA = 7

# Tope defensivo de iteraciones al avanzar ocurrencias (semanal/mensual con
# años de atraso). Si se excede, el recordatorio se cancela con ERROR.
_MAX_SALTOS_AVANCE = 2000


def _tipo_recurrencia(recurrencia_json: str | dict | None) -> str:
    """Extrae el tipo de la recurrencia ('' si no hay o es inválida)."""
    if not recurrencia_json:
        return ""
    try:
        rec = json.loads(recurrencia_json) if isinstance(recurrencia_json, str) else recurrencia_json
        return rec.get("tipo", "")
    except Exception:
        return ""


def fecha_fin_efectiva_recordatorio(
    fecha_fin: datetime | None, recurrencia_json: str | None, creado: datetime | None
) -> datetime | None:
    """fecha_fin a aplicar: la explícita, o —para sub-diarias viejas creadas
    sin límite (antes del default)— una contención lógica de
    DIAS_FECHA_FIN_DEFAULT_SUB_DIARIA días desde su creación. Sin migración:
    las filas no se tocan, el límite se evalúa al despachar."""
    if fecha_fin is not None:
        return fecha_fin
    if _tipo_recurrencia(recurrencia_json) in RECURRENCIAS_SUB_DIARIAS and creado is not None:
        return creado + timedelta(days=DIAS_FECHA_FIN_DEFAULT_SUB_DIARIA)
    return None


def avanzar_recurrencia_hasta_futuro(
    fecha_hora: datetime,
    recurrencia_json: str,
    offset_tz_minutos: int | None,
) -> tuple[datetime | None, int]:
    """Calcula la PRIMERA ocurrencia estrictamente futura desde fecha_hora.

    Retorna (proxima, ocurrencias_saltadas). Nunca produce una fecha en el
    pasado (eso causaba el catch-up storm: reenvío en cada tick hasta
    alcanzar el presente). (None, n) si la recurrencia es inválida o el
    avance excede el tope defensivo — el caller debe cancelar.
    """
    ahora = datetime.utcnow()
    tipo = _tipo_recurrencia(recurrencia_json)

    # Intervalos fijos: salto analítico (un downtime largo no itera miles
    # de veces).
    _INTERVALOS_FIJOS = {
        "cada_30_minutos": timedelta(minutes=30),
        "cada_hora": timedelta(hours=1),
        "horario": timedelta(hours=1),
        "diario": timedelta(days=1),
    }
    if tipo in _INTERVALOS_FIJOS:
        intervalo = _INTERVALOS_FIJOS[tipo]
        saltos = 1
        if fecha_hora < ahora:
            atraso = ahora - fecha_hora
            saltos = int(atraso / intervalo) + 1
        proxima = fecha_hora + intervalo * saltos
        return proxima, saltos - 1

    # Tipos con calendario (semanal, dias_semana, mensual): iterar con tope.
    proxima = fecha_hora
    saltadas = -1
    for _ in range(_MAX_SALTOS_AVANCE):
        siguiente = _calcular_proxima_ocurrencia(proxima, recurrencia_json, offset_tz_minutos)
        if siguiente is None:
            return None, max(saltadas, 0)
        proxima = siguiente
        saltadas += 1
        if proxima > ahora:
            return proxima, saltadas
    logger.error(
        f"avanzar_recurrencia_hasta_futuro excedió {_MAX_SALTOS_AVANCE} saltos "
        f"(tipo={tipo}) — recurrencia corrupta o atraso absurdo"
    )
    return None, saltadas


async def saltar_ocurrencias_atrasadas(recordatorio_id: int) -> tuple[datetime | None, int]:
    """Reagenda un recordatorio recurrente atrasado a su próxima ocurrencia
    FUTURA sin enviar nada (catch-up suprimido). Cancela si la recurrencia ya
    no produce fechas válidas o superó su fecha_fin (efectiva).

    Retorna (nueva_fecha | None si canceló, ocurrencias_saltadas)."""
    async with async_session() as session:
        result = await session.execute(
            select(Recordatorio).where(Recordatorio.id == recordatorio_id)
        )
        r = result.scalar_one_or_none()
        if not r or not r.recurrencia:
            return None, 0

        proxima, saltadas = avanzar_recurrencia_hasta_futuro(
            r.fecha_hora, r.recurrencia, r.offset_tz_minutos
        )
        fin = fecha_fin_efectiva_recordatorio(r.fecha_fin, r.recurrencia, r.creado)
        if proxima is None or (fin is not None and proxima > fin):
            r.cancelado = True
            await session.commit()
            logger.info(
                f"[CATCHUP] Recordatorio #{r.id} cancelado al sanear atraso "
                f"(saltadas={saltadas}, fin={fin})"
            )
            return None, saltadas

        r.fecha_hora = proxima
        await session.commit()
        logger.info(
            f"[CATCHUP] Recordatorio #{r.id} saneado sin envío: "
            f"{saltadas} ocurrencia(s) perdida(s) saltada(s), próxima {proxima}"
        )
        return proxima, saltadas


async def guardar_recordatorio(
    telefono: str,
    mensaje: str,
    fecha_hora: datetime,
    recurrencia: dict | None = None,
    offset_tz_minutos: int | None = None,
    fecha_fin: datetime | None = None,
) -> Recordatorio:
    """Guarda un recordatorio en la base de datos.

    Recurrencias sub-diarias sin fecha_fin reciben un límite default de
    DIAS_FECHA_FIN_DEFAULT_SUB_DIARIA días — "cada 30 minutos para siempre"
    no es un default aceptable (Fase 0 · 2.4)."""
    # 2.4: un tipo de recurrencia desconocido (el schema de la tool lo deja
    # libre) no es agendable — el scheduler no puede avanzarlo y quedaría sin
    # tope. Degradar a recordatorio de una sola vez explícito, en vez de
    # persistir una recurrencia que se auto-cancelaría tras un único envío.
    if recurrencia and recurrencia.get("tipo", "") not in TIPOS_RECURRENCIA_VALIDOS:
        logger.warning(
            f"Recordatorio con recurrencia desconocida "
            f"({recurrencia.get('tipo')!r}): se guarda como una sola vez."
        )
        recurrencia = None
    if (
        fecha_fin is None
        and recurrencia
        and recurrencia.get("tipo", "") in RECURRENCIAS_SUB_DIARIAS
    ):
        fecha_fin = datetime.utcnow() + timedelta(days=DIAS_FECHA_FIN_DEFAULT_SUB_DIARIA)
        logger.info(
            f"Recordatorio sub-diario ({recurrencia.get('tipo')}) sin fecha_fin: "
            f"se aplica default de {DIAS_FECHA_FIN_DEFAULT_SUB_DIARIA} días → {fecha_fin}"
        )
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
            # Recurrente: reagendar SIEMPRE a una ocurrencia futura. Avanzar
            # de a un paso dejaba fecha_hora en el pasado tras un downtime y
            # cada tick reenviaba hasta ponerse al día (catch-up storm, 2.4).
            proxima, saltadas = avanzar_recurrencia_hasta_futuro(
                r.fecha_hora, r.recurrencia, r.offset_tz_minutos
            )
            fin = fecha_fin_efectiva_recordatorio(r.fecha_fin, r.recurrencia, r.creado)
            if proxima and (fin is None or proxima <= fin):
                r.fecha_hora = proxima
                extra = f" ({saltadas} ocurrencia(s) atrasada(s) saltada(s))" if saltadas else ""
                logger.info(f"Recordatorio #{r.id} reagendado para {proxima}{extra}")
            else:
                # Se acabó la recurrencia (llegó fecha_fin o ya no hay fechas)
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


# ── Claims atómicos del scheduler (Fase 0 · 2.3) ────────────────────────────
# Con >1 proceso corriendo el scheduler (gunicorn --workers N, segunda
# instancia), el flujo SELECT pendientes → enviar → marcar enviado duplica
# envíos: todos los procesos pasan el SELECT antes de que alguno marque.
# El claim es un UPDATE condicional cuyo rowcount decide UN solo ganador
# (misma familia que el dedup atómico de C9). Sin migración: reutiliza
# ultimo_envio como marcador, con ventana de expiración para autosanar si
# un proceso muere después de reclamar y antes de enviar.

# Minutos durante los cuales un claim bloquea re-claims. Debe ser mayor que
# lo que tarda un tick del scheduler (timeout 30s) y menor que la recurrencia
# más corta soportada (30 min).
VENTANA_CLAIM_RECORDATORIO_MIN = 5


async def claim_recordatorio_para_envio(
    recordatorio_id: int, ventana_minutos: int = VENTANA_CLAIM_RECORDATORIO_MIN
) -> bool:
    """Reclama atómicamente un recordatorio para enviarlo. True = este proceso
    ganó la fila y debe enviar; False = otro proceso la tiene (o ya no está
    pendiente). El claim expira tras `ventana_minutos` (crash mid-send →
    la ocurrencia se reintenta en el siguiente tick pasada la ventana)."""
    ahora = datetime.utcnow()
    corte = ahora - timedelta(minutes=ventana_minutos)
    async with async_session() as session:
        result = await session.execute(
            update(Recordatorio)
            .where(
                Recordatorio.id == recordatorio_id,
                Recordatorio.cancelado == False,
                Recordatorio.enviado == False,
                (Recordatorio.ultimo_envio.is_(None)) | (Recordatorio.ultimo_envio <= corte),
            )
            .values(ultimo_envio=ahora)
        )
        await session.commit()
        return result.rowcount == 1


async def liberar_claim_recordatorio(recordatorio_id: int) -> None:
    """Libera el claim tras un envío FALLIDO para conservar la cadencia de
    reintento por tick (sin esto, el reintento esperaría la ventana entera).
    Solo la llama el proceso dueño del claim."""
    async with async_session() as session:
        await session.execute(
            update(Recordatorio)
            .where(Recordatorio.id == recordatorio_id)
            .values(ultimo_envio=None)
        )
        await session.commit()


async def claim_gcal_enviado(clave: str) -> bool:
    """Reclama atómicamente un recordatorio de Google Calendar ANTES de
    enviarlo: INSERT ... ON CONFLICT DO NOTHING sobre la PK `clave`, el
    rowcount decide (patrón del dedup C9). True = ganador, enviar."""
    if _ES_POSTGRES:
        from sqlalchemy.dialects.postgresql import insert as _insert
    else:
        from sqlalchemy.dialects.sqlite import insert as _insert

    stmt = (
        _insert(RecordatorioGCalEnviado)
        .values(clave=clave)
        .on_conflict_do_nothing(index_elements=["clave"])
    )
    async with async_session() as session:
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount == 1


async def liberar_claim_gcal(clave: str) -> None:
    """Borra el claim de GCal tras un envío FALLIDO (best-effort) para que el
    siguiente ciclo lo reintente. Solo la llama el proceso dueño del claim."""
    from sqlalchemy import delete as _delete

    async with async_session() as session:
        await session.execute(
            _delete(RecordatorioGCalEnviado).where(RecordatorioGCalEnviado.clave == clave)
        )
        await session.commit()


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

        if tipo in ("cada_hora", "horario"):
            return fecha_actual + timedelta(hours=1)

        elif tipo == "cada_30_minutos":
            return fecha_actual + timedelta(minutes=30)

        elif tipo == "diario":
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
            "ultimo_consejo_estrategico": r.ultimo_consejo_estrategico,
            "ultimo_revision_correo": r.ultimo_revision_correo,
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
                "ultimo_consejo_estrategico": prov.ultimo_consejo_estrategico if prov else None,
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
            "contexto_pendiente": registro.contexto_pendiente or "",
            "mensajes_desde_sync": registro.mensajes_desde_sync or 0,
        }


# ══════════════════════════════════════════════════════════════════════════════
# NOTAS DE USUARIO
# ══════════════════════════════════════════════════════════════════════════════

async def guardar_nota_db(
    telefono: str,
    titulo: str,
    contenido: str,
    etiquetas: list | None = None,
    embedding: list | None = None,
) -> int:
    """Guarda una nota en notas_usuario. Retorna el ID creado."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as session:
        if embedding:
            result = await session.execute(
                text("""
                    INSERT INTO notas_usuario (telefono, titulo, contenido, etiquetas, embedding)
                    VALUES (:telefono, :titulo, :contenido, CAST(:etiquetas AS jsonb), CAST(:embedding AS vector))
                    RETURNING id
                """),
                {
                    "telefono": telefono,
                    "titulo": titulo[:200],
                    "contenido": contenido[:4000],
                    "etiquetas": json.dumps(etiquetas or []),
                    "embedding": str(embedding),
                }
            )
        else:
            result = await session.execute(
                text("""
                    INSERT INTO notas_usuario (telefono, titulo, contenido, etiquetas)
                    VALUES (:telefono, :titulo, :contenido, CAST(:etiquetas AS jsonb))
                    RETURNING id
                """),
                {
                    "telefono": telefono,
                    "titulo": titulo[:200],
                    "contenido": contenido[:4000],
                    "etiquetas": json.dumps(etiquetas or []),
                }
            )
        await session.commit()
        row = result.fetchone()
        return row[0] if row else 0


async def buscar_notas_db(
    telefono: str,
    embedding_consulta: list | None = None,
    limite: int = 5,
    umbral: float = 0.55,
) -> list[dict]:
    """
    Busca notas por similitud vectorial (si hay embedding) o devuelve las más recientes.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as session:
        if embedding_consulta:
            result = await session.execute(
                text("""
                    SELECT id, titulo, contenido, etiquetas, fecha_creacion,
                           1 - (embedding <=> CAST(:embedding AS vector)) AS similitud
                    FROM notas_usuario
                    WHERE telefono = :telefono
                      AND embedding IS NOT NULL
                      AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :umbral
                    ORDER BY embedding <=> CAST(:embedding AS vector)
                    LIMIT :limite
                """),
                {
                    "telefono": telefono,
                    "embedding": str(embedding_consulta),
                    "umbral": umbral,
                    "limite": limite,
                }
            )
        else:
            result = await session.execute(
                text("""
                    SELECT id, titulo, contenido, etiquetas, fecha_creacion, 1.0 AS similitud
                    FROM notas_usuario
                    WHERE telefono = :telefono
                    ORDER BY fecha_creacion DESC
                    LIMIT :limite
                """),
                {"telefono": telefono, "limite": limite}
            )
        rows = result.fetchall()

        def _parse_etiquetas(val):
            if not val:
                return []
            if isinstance(val, (list, dict)):
                return val  # asyncpg ya deserializó el JSONB
            try:
                return json.loads(val)
            except Exception:
                return []

        return [
            {
                "id": row[0],
                "titulo": row[1],
                "contenido": row[2],
                "etiquetas": _parse_etiquetas(row[3]),
                "fecha": row[4].strftime("%d/%m/%Y") if row[4] else "",
                "similitud": round(float(row[5]), 3),
            }
            for row in rows
        ]

# ══════════════════════════════════════════════════════════════════════════════
# HOJAS DE CÁLCULO REGISTRADAS
# ══════════════════════════════════════════════════════════════════════════════

async def registrar_hoja_db(
    telefono: str,
    nombre: str,
    spreadsheet_id: str,
    hoja_nombre: str = "Sheet1",
    descripcion: str = "",
) -> int:
    """Registra o actualiza una hoja en hojas_registradas. Retorna el ID."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as session:
        # Upsert: si ya existe (telefono + nombre), actualiza
        result = await session.execute(
            text("""
                INSERT INTO hojas_registradas (telefono, nombre, spreadsheet_id, hoja_nombre, descripcion)
                VALUES (:telefono, :nombre, :spreadsheet_id, :hoja_nombre, :descripcion)
                ON CONFLICT (telefono, nombre)
                DO UPDATE SET
                    spreadsheet_id = EXCLUDED.spreadsheet_id,
                    hoja_nombre    = EXCLUDED.hoja_nombre,
                    descripcion    = EXCLUDED.descripcion
                RETURNING id
            """),
            {
                "telefono": telefono,
                "nombre": nombre,
                "spreadsheet_id": spreadsheet_id,
                "hoja_nombre": hoja_nombre,
                "descripcion": descripcion,
            }
        )
        await session.commit()
        row = result.fetchone()
        return row[0] if row else 0


async def obtener_hoja_db(telefono: str, nombre: str) -> dict | None:
    """Obtiene una hoja registrada por su nombre/alias."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text("""
                SELECT id, nombre, spreadsheet_id, hoja_nombre, descripcion, created_at
                FROM hojas_registradas
                WHERE telefono = :telefono
                  AND lower(nombre) = lower(:nombre)
                LIMIT 1
            """),
            {"telefono": telefono, "nombre": nombre}
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "nombre": row[1],
            "spreadsheet_id": row[2],
            "hoja_nombre": row[3],
            "descripcion": row[4] or "",
            "created_at": row[5],
        }


async def listar_hojas_db(telefono: str) -> list[dict]:
    """Lista todas las hojas registradas del usuario."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text("""
                SELECT nombre, spreadsheet_id, hoja_nombre, descripcion, created_at
                FROM hojas_registradas
                WHERE telefono = :telefono
                ORDER BY created_at DESC
            """),
            {"telefono": telefono}
        )
        rows = result.fetchall()
        return [
            {
                "nombre": r[0],
                "spreadsheet_id": r[1],
                "hoja_nombre": r[2],
                "descripcion": r[3] or "",
                "created_at": r[4],
            }
            for r in rows
        ]


async def guardar_mirofish_estado(
    telefono: str,
    project_id: str | None = None,
    graph_id: str | None = None,
    contexto_pendiente: str | None = None,
    mensajes_desde_sync: int | None = None,
    resetear_sync: bool = False,
):
    """
    Guarda o actualiza el estado MiroFish de un usuario.
    - resetear_sync=True: limpia contexto_pendiente y pone mensajes_desde_sync=0
      (se usa después de una sincronización exitosa del grafo).
    """
    async with async_session() as session:
        query = select(UsuarioMiroFish).where(UsuarioMiroFish.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if registro:
            if project_id is not None:
                registro.project_id = project_id
            if graph_id is not None:
                registro.graph_id = graph_id
            if contexto_pendiente is not None:
                registro.contexto_pendiente = contexto_pendiente
            if mensajes_desde_sync is not None:
                registro.mensajes_desde_sync = mensajes_desde_sync
            if resetear_sync:
                registro.contexto_pendiente = ""
                registro.mensajes_desde_sync = 0
            registro.actualizado = datetime.utcnow()
        else:
            session.add(UsuarioMiroFish(
                telefono=telefono,
                project_id=project_id,
                graph_id=graph_id,
                contexto_pendiente=contexto_pendiente or "",
                mensajes_desde_sync=mensajes_desde_sync or 0,
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
    """Guarda o actualiza los tokens de OAuth de Google Calendar del usuario (cifrados)."""
    from agent.crypto import cifrar

    access_token_enc = cifrar(access_token)
    refresh_token_enc = cifrar(refresh_token) if refresh_token else ""

    async with async_session() as session:
        query = select(UsuarioGoogleAuth).where(UsuarioGoogleAuth.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if registro:
            registro.access_token = access_token_enc
            if refresh_token:                       # no sobreescribir con vacío
                registro.refresh_token = refresh_token_enc
            registro.expires_at = expires_at
            if email:
                registro.email = email
            registro.actualizado = datetime.utcnow()
        else:
            session.add(UsuarioGoogleAuth(
                telefono=telefono,
                access_token=access_token_enc,
                refresh_token=refresh_token_enc,
                expires_at=expires_at,
                email=email,
                actualizado=datetime.utcnow(),
            ))
        await session.commit()


async def obtener_google_auth(telefono: str) -> dict | None:
    """Retorna los tokens de Google Calendar del usuario (descifrados), o None si no está conectado."""
    from agent.crypto import descifrar

    async with async_session() as session:
        query = select(UsuarioGoogleAuth).where(UsuarioGoogleAuth.telefono == telefono)
        result = await session.execute(query)
        registro = result.scalar_one_or_none()
        if not registro:
            return None
        return {
            "access_token": descifrar(registro.access_token),
            "refresh_token": descifrar(registro.refresh_token),
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


async def registrar_uso_tokens(telefono: str, tokens_in: int, tokens_out: int):
    """Registra el uso de tokens de una llamada a Claude. Acumula por usuario/día."""
    try:
        from datetime import date
        hoy = date.today()
        async with async_session() as session:
            from sqlalchemy import text
            # UPSERT: incrementar si ya existe, crear si no
            await session.execute(
                text("""
                    INSERT INTO uso_tokens (telefono, fecha, tokens_entrada, tokens_salida, requests_count)
                    VALUES (:tel, :fecha, :tin, :tout, 1)
                    ON CONFLICT (telefono, fecha)
                    DO UPDATE SET
                        tokens_entrada = uso_tokens.tokens_entrada + :tin,
                        tokens_salida = uso_tokens.tokens_salida + :tout,
                        requests_count = uso_tokens.requests_count + 1
                """),
                {"tel": telefono, "fecha": hoy, "tin": tokens_in, "tout": tokens_out},
            )
            await session.commit()
    except Exception as e:
        logger.debug(f"registrar_uso_tokens: {e}")


async def obtener_uso_tokens(telefono: str, dias: int = 30) -> list[dict]:
    """Obtiene el uso de tokens de un usuario en los últimos N días."""
    try:
        from datetime import date, timedelta
        desde = date.today() - timedelta(days=dias)
        async with async_session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("""
                    SELECT fecha, tokens_entrada, tokens_salida, requests_count
                    FROM uso_tokens
                    WHERE telefono = :tel AND fecha >= :desde
                    ORDER BY fecha DESC
                """),
                {"tel": telefono, "desde": desde},
            )
            return [
                {"fecha": str(r[0]), "tokens_in": r[1], "tokens_out": r[2], "requests": r[3]}
                for r in result.fetchall()
            ]
    except Exception as e:
        logger.debug(f"obtener_uso_tokens: {e}")
        return []


async def borrar_datos_usuario(telefono: str) -> dict:
    """
    Elimina TODOS los datos de un usuario de todas las tablas.
    Implementa el derecho al olvido (CCPA/CPRA §1798.105 + GDPR Art. 17 + estados similares).

    Cobertura:
      - Tablas principales de agent/memory.py (perfil, mensajes, recordatorios, etc.)
      - Tablas de agent/business/models.py (clientes, productos, ventas, pedidos, etc.)
      - Tablas de enhanced/models.py (sistemas de usuario, activity log)
      - Deduplicación y caché con referencias al teléfono

    Returns:
        dict con el conteo de registros eliminados por tabla.
    """
    from sqlalchemy import delete

    conteos = {}

    # Tablas del módulo principal (agent/memory.py)
    tablas_principales = [
        ("mensajes", Mensaje, Mensaje.telefono),
        ("recordatorios", Recordatorio, Recordatorio.telefono),
        ("timezone", TimezoneUsuario, TimezoneUsuario.telefono),
        ("ubicacion", UsuarioUbicacion, UsuarioUbicacion.telefono),
        ("estado_emocional", UsuarioEstadoEmocional, UsuarioEstadoEmocional.telefono),
        ("eventos_emocionales", EventoEmocional, EventoEmocional.telefono),
        ("onboarding", UsuarioOnboarding, UsuarioOnboarding.telefono),
        ("proactividad", UsuarioProactividad, UsuarioProactividad.telefono),
        ("comportamiento", EventoComportamiento, EventoComportamiento.telefono),
        ("perfil_aprendizaje", PerfilAprendizaje, PerfilAprendizaje.telefono),
        ("mirofish", UsuarioMiroFish, UsuarioMiroFish.telefono),
        ("google_auth", UsuarioGoogleAuth, UsuarioGoogleAuth.telefono),
        ("memoria_largo_plazo", MemoriaLargoPlazo, MemoriaLargoPlazo.telefono),
        ("noticias", NoticiaEnviada, NoticiaEnviada.telefono),
        ("tareas", Tarea, Tarea.telefono),
        ("eventos_usuario", EventoUsuario, EventoUsuario.telefono),
        ("mensajes_procesados", MensajeProcesado, MensajeProcesado.telefono),
    ]

    async with async_session() as session:
        for nombre, modelo, col_telefono in tablas_principales:
            try:
                result = await session.execute(
                    delete(modelo).where(col_telefono == telefono)
                )
                conteos[nombre] = result.rowcount
            except Exception as e:
                conteos[nombre] = f"error: {e}"
                logger.error(f"[BORRAR] Error borrando {nombre} para {telefono}: {e}")

        # Listas: borrar items primero, luego listas
        try:
            listas_result = await session.execute(
                select(Lista.id).where(Lista.telefono == telefono)
            )
            lista_ids = [row[0] for row in listas_result.all()]
            items_borrados = 0
            if lista_ids:
                for lid in lista_ids:
                    r = await session.execute(delete(ItemLista).where(ItemLista.lista_id == lid))
                    items_borrados += r.rowcount
            r_listas = await session.execute(delete(Lista).where(Lista.telefono == telefono))
            conteos["items_lista"] = items_borrados
            conteos["listas"] = r_listas.rowcount
        except Exception as e:
            conteos["listas"] = f"error: {e}"

        # Tabla uso_tokens
        try:
            from sqlalchemy import text as _text
            r_tokens = await session.execute(
                _text("DELETE FROM uso_tokens WHERE telefono = :tel"),
                {"tel": telefono},
            )
            conteos["uso_tokens"] = r_tokens.rowcount
        except Exception as e:
            conteos["uso_tokens"] = f"error: {e}"

        # Tabla sesiones_conversacion
        try:
            r_sesiones = await session.execute(
                delete(SesionConversacion).where(SesionConversacion.telefono == telefono)
            )
            conteos["sesiones"] = r_sesiones.rowcount
        except Exception as e:
            conteos["sesiones"] = f"error: {e}"

        # Tablas enhanced/ (si existen)
        try:
            from enhanced.models import SystemActivityLog, UserSystem
            r_sys = await session.execute(delete(UserSystem).where(UserSystem.telefono == telefono))
            conteos["sistemas_usuario"] = r_sys.rowcount
            r_log = await session.execute(delete(SystemActivityLog).where(SystemActivityLog.telefono == telefono))
            conteos["activity_log"] = r_log.rowcount
        except Exception as e:
            conteos["enhanced"] = f"error: {e}"

        # Tablas de business/ (negocio self-service)
        try:
            from agent.business.models import (
                ClienteNegocio,
                Cotizacion,
                Pedido,
                PerfilNegocio,
                Producto,
                Seguimiento,
                Transaccion,
            )
            for nombre, modelo, col in [
                ("perfil_negocio", PerfilNegocio, PerfilNegocio.telefono),
                ("productos_negocio", Producto, Producto.telefono),
                ("transacciones_negocio", Transaccion, Transaccion.telefono),
                ("pedidos_negocio", Pedido, Pedido.telefono),
                ("seguimientos_negocio", Seguimiento, Seguimiento.telefono),
                ("cotizaciones_negocio", Cotizacion, Cotizacion.telefono),
            ]:
                try:
                    r = await session.execute(delete(modelo).where(col == telefono))
                    conteos[nombre] = r.rowcount
                except Exception as e:
                    conteos[nombre] = f"error: {e}"
            # ClienteNegocio usa telefono_owner
            try:
                r_cli = await session.execute(
                    delete(ClienteNegocio).where(ClienteNegocio.telefono_owner == telefono)
                )
                conteos["clientes_negocio"] = r_cli.rowcount
            except Exception as e:
                conteos["clientes_negocio"] = f"error: {e}"
        except ImportError as e:
            conteos["business"] = f"módulo no disponible: {e}"

        # Caché de recordatorios GCal enviados — la clave tiene la forma
        # `gcal_reminder_{telefono}_{evento_id}` (ver scheduler.py). CCPA 7.3:
        # el match debe ser ANCLADO al prefijo exacto del usuario, nunca por
        # subcadena. Un `LIKE '%{telefono}%'` borraría datos de OTRO usuario
        # cuyo teléfono contenga a este (p. ej. "5511" ⊂ "115511") y, al perder
        # su marca de dedup, ese tercero recibiría recordatorios duplicados
        # (exposición TCPA). Escapamos '%'/'_'/'\' del teléfono para que se
        # traten literalmente y anclamos con el delimitador '_' posterior.
        try:
            from sqlalchemy import text as _text
            tel_like = (
                telefono.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            r_gcal = await session.execute(
                _text(
                    "DELETE FROM recordatorios_gcal_enviados "
                    "WHERE clave LIKE :patron ESCAPE '\\'"
                ),
                {"patron": f"gcal_reminder_{tel_like}\\_%"},
            )
            conteos["recordatorios_gcal_enviados"] = r_gcal.rowcount
        except Exception as e:
            conteos["recordatorios_gcal_enviados"] = f"error: {e}"

        await session.commit()

    total = sum(v for v in conteos.values() if isinstance(v, int))
    logger.info(f"[BORRAR] Datos eliminados para {telefono}: {total} registros en {len(conteos)} tablas")
    return conteos


async def exportar_datos_usuario(telefono: str) -> dict:
    """
    Retorna un dict con todos los datos del usuario (CCPA/CPRA derecho de portabilidad).
    Formato JSON-serializable. Incluye conteo por tabla y un total global.

    El llamador es responsable de enviar el resultado por un canal seguro
    (email firmado, descarga autenticada, etc.) — no por WhatsApp en claro.
    """
    export = {}
    total = 0

    async with async_session() as session:
        # Helper genérico: todas las filas de una tabla por teléfono
        async def _dump(nombre: str, modelo, col):
            nonlocal total
            try:
                result = await session.execute(select(modelo).where(col == telefono))
                filas = result.scalars().all()
                dumped = []
                for f in filas:
                    fila_dict = {}
                    for c in f.__table__.columns:
                        val = getattr(f, c.name, None)
                        if isinstance(val, datetime):
                            fila_dict[c.name] = val.isoformat()
                        elif isinstance(val, (str, int, float, bool)) or val is None:
                            fila_dict[c.name] = val
                        else:
                            fila_dict[c.name] = str(val)
                    dumped.append(fila_dict)
                export[nombre] = dumped
                total += len(dumped)
            except Exception as e:
                export[nombre] = {"error": str(e)}

        # Tablas principales
        await _dump("mensajes", Mensaje, Mensaje.telefono)
        await _dump("recordatorios", Recordatorio, Recordatorio.telefono)
        await _dump("timezone", TimezoneUsuario, TimezoneUsuario.telefono)
        await _dump("ubicacion", UsuarioUbicacion, UsuarioUbicacion.telefono)
        await _dump("onboarding", UsuarioOnboarding, UsuarioOnboarding.telefono)
        await _dump("proactividad", UsuarioProactividad, UsuarioProactividad.telefono)
        await _dump("memoria_largo_plazo", MemoriaLargoPlazo, MemoriaLargoPlazo.telefono)
        await _dump("tareas", Tarea, Tarea.telefono)
        await _dump("listas", Lista, Lista.telefono)
        await _dump("eventos_usuario", EventoUsuario, EventoUsuario.telefono)
        # Google auth: enmascarar tokens para evitar leaks si se imprime
        try:
            from sqlalchemy import select as _sel
            res = await session.execute(_sel(UsuarioGoogleAuth).where(UsuarioGoogleAuth.telefono == telefono))
            ga = res.scalar_one_or_none()
            if ga:
                export["google_auth"] = [{
                    "telefono": ga.telefono,
                    "email": getattr(ga, "email", ""),
                    "access_token": "***REDACTED***",
                    "refresh_token": "***REDACTED***",
                    "expires_at": ga.expires_at.isoformat() if getattr(ga, "expires_at", None) else None,
                }]
                total += 1
            else:
                export["google_auth"] = []
        except Exception as e:
            export["google_auth"] = {"error": str(e)}

        # Tablas business (si existen)
        try:
            from agent.business.models import (
                ClienteNegocio,
                Cotizacion,
                Pedido,
                PerfilNegocio,
                Producto,
                Seguimiento,
                Transaccion,
            )
            await _dump("perfil_negocio", PerfilNegocio, PerfilNegocio.telefono)
            await _dump("productos_negocio", Producto, Producto.telefono)
            await _dump("transacciones_negocio", Transaccion, Transaccion.telefono)
            await _dump("pedidos_negocio", Pedido, Pedido.telefono)
            await _dump("seguimientos_negocio", Seguimiento, Seguimiento.telefono)
            await _dump("cotizaciones_negocio", Cotizacion, Cotizacion.telefono)
            await _dump("clientes_negocio", ClienteNegocio, ClienteNegocio.telefono_owner)
        except ImportError:
            pass

    export["_total_registros"] = total
    logger.info(f"[PRIVACY] Export generado para {telefono}: {total} registros")
    return export


# ── Sesiones de conversación ────────────────────────────────────────────────

async def registrar_interaccion_sesion(telefono: str) -> int:
    """
    Registra una interacción en la sesión activa del usuario.
    Si no hay sesión activa o la última expiró (>SESION_TIMEOUT_MINUTOS),
    crea una nueva sesión.

    Returns:
        ID de la sesión activa.
    """
    ahora = datetime.utcnow()
    timeout = timedelta(minutes=SESION_TIMEOUT_MINUTOS)

    async with async_session() as session:
        # Buscar sesión activa más reciente
        result = await session.execute(
            select(SesionConversacion)
            .where(
                SesionConversacion.telefono == telefono,
                SesionConversacion.activa == True,
            )
            .order_by(SesionConversacion.ultimo_mensaje.desc())
            .limit(1)
        )
        sesion_activa = result.scalar_one_or_none()

        if sesion_activa and (ahora - sesion_activa.ultimo_mensaje) < timeout:
            # Sesión aún activa — actualizar
            sesion_activa.ultimo_mensaje = ahora
            sesion_activa.mensajes_count += 1
            await session.commit()
            return sesion_activa.id
        else:
            # Cerrar sesión anterior si existe
            if sesion_activa:
                sesion_activa.activa = False

            # Crear nueva sesión
            nueva = SesionConversacion(
                telefono=telefono,
                inicio=ahora,
                ultimo_mensaje=ahora,
                mensajes_count=1,
                activa=True,
            )
            session.add(nueva)
            await session.commit()
            await session.refresh(nueva)
            logger.debug(f"[SESION] Nueva sesión #{nueva.id} para {telefono}")
            return nueva.id


async def obtener_sesion_activa(telefono: str) -> dict | None:
    """Retorna datos de la sesión activa del usuario, o None si no hay."""
    ahora = datetime.utcnow()
    timeout = timedelta(minutes=SESION_TIMEOUT_MINUTOS)

    async with async_session() as session:
        result = await session.execute(
            select(SesionConversacion)
            .where(
                SesionConversacion.telefono == telefono,
                SesionConversacion.activa == True,
            )
            .order_by(SesionConversacion.ultimo_mensaje.desc())
            .limit(1)
        )
        s = result.scalar_one_or_none()
        if not s or (ahora - s.ultimo_mensaje) >= timeout:
            return None
        return {
            "id": s.id,
            "inicio": s.inicio.isoformat(),
            "ultimo_mensaje": s.ultimo_mensaje.isoformat(),
            "mensajes_count": s.mensajes_count,
            "duracion_min": round((s.ultimo_mensaje - s.inicio).total_seconds() / 60, 1),
        }


async def obtener_stats_sesiones(telefono: str, dias: int = 30) -> dict:
    """Estadísticas de sesiones de un usuario en los últimos N días."""
    desde = datetime.utcnow() - timedelta(days=dias)
    async with async_session() as session:
        result = await session.execute(
            select(SesionConversacion)
            .where(
                SesionConversacion.telefono == telefono,
                SesionConversacion.inicio >= desde,
            )
            .order_by(SesionConversacion.inicio.desc())
        )
        sesiones = result.scalars().all()
        if not sesiones:
            return {"total_sesiones": 0, "total_mensajes": 0, "duracion_promedio_min": 0}

        total_msgs = sum(s.mensajes_count for s in sesiones)
        duraciones = [(s.ultimo_mensaje - s.inicio).total_seconds() / 60 for s in sesiones]
        return {
            "total_sesiones": len(sesiones),
            "total_mensajes": total_msgs,
            "duracion_promedio_min": round(sum(duraciones) / len(duraciones), 1),
            "mensajes_por_sesion": round(total_msgs / len(sesiones), 1),
        }
