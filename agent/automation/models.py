# agent/automation/models.py — Modelos DB de automatización (T2.1.A)

"""
Tablas:
  - acciones_automatizacion · acciones generadas, lifecycle completo
  - audit_log_automatizacion · trazabilidad de eventos del pipeline

Ambas son aditivas · no tocan tablas existentes. Migraciones idempotentes
(DO $$ IF NOT EXISTS pattern) en MIGRACIONES_AUTOMATION, integradas al
runtime via _migrar_columnas() de agent/memory.py.
"""

from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, Boolean, DateTime

from agent.memory import Base


class AccionAutomatizacion(Base):
    """Una acción generada por el Automation Core.

    Lifecycle:
      pending|needs_approval → approved → running → completed
                            ↘ rejected
                            ↘ cancelled
                            ↘ failed
    """
    __tablename__ = "acciones_automatizacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Owner del negocio · matching contra perfil_negocio.telefono
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    # Identificador del oportunidad/playbook que generó la acción
    opportunity_id: Mapped[str] = mapped_column(String(100), default="")
    playbook_id: Mapped[str] = mapped_column(String(100), default="")
    # Tipo de acción · gobierna su clasificación de riesgo
    # (ver agent/automation/permissions.py:RIESGO_POR_TIPO_ACCION)
    tipo_accion: Mapped[str] = mapped_column(String(80), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    razon_recomendacion: Mapped[str] = mapped_column(Text, default="")
    # Estado del lifecycle
    estado: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # Riesgo · low|medium|high|critical
    riesgo: Mapped[str] = mapped_column(String(20), default="medium")
    # Costo estimado en créditos (no se descuenta hoy · solo estimación)
    costo_creditos_estimado: Mapped[int] = mapped_column(Integer, default=0)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    # Payload de entrada y resultado · JSON serializado
    # (str para portabilidad cross-DB · Postgres/SQLite)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    # Errores sanitizados · NUNCA stack traces ni PII cruda
    error_message: Mapped[str] = mapped_column(Text, default="")
    # Hash de idempotencia · evita duplicar mismo (telefono, opportunity_id,
    # playbook_id, fecha) · ver action_center.crear_accion para construcción
    idempotency_key: Mapped[str] = mapped_column(String(120), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReservaCreditoAutomation(Base):
    """T2.1.D · Reserva de créditos por acción del Automation Core.

    Patrón "cobrar al crear, reembolsar si falla":
      pending   · créditos ya descontados (cobrar() ejecutado) ·
                  esperando que la acción complete o falle.
      confirmed · acción completada · el descuento queda firme.
      released  · acción falló/canceled · créditos reembolsados.
      failed    · no se pudo crear reserva (saldo insuficiente).
                  Sin descuento. Útil solo para audit.

    Idempotencia: 1:1 con accion_id (UNIQUE). Re-llamar reservar_*()
    para la misma acción NO crea nueva fila ni vuelve a cobrar.
    """
    __tablename__ = "automation_reservas_credito"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    accion_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    creditos: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(
        String(20), default="pending", index=True,
    )
    razon: Mapped[str] = mapped_column(Text, default="")
    transaccion_credito_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLogAutomatizacion(Base):
    """Trazabilidad del pipeline de automatización.

    Cada paso significativo (oportunidad detectada, acción creada,
    aprobada, rechazada, ejecutada, completada, fallida) queda como una
    fila aquí. Se sanitiza el payload · ver agent/automation/audit.py.

    NO guardar:
      - emails completos
      - telefonos completos (solo truncados)
      - customer.id completos
      - valores de DASHBOARD_PASSWORD_SECRET / API keys
      - cuerpo de respuestas del usuario en el onboarding
    """
    __tablename__ = "audit_log_automatizacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Telefono truncado para queries (NO guardar el completo)
    telefono_short: Mapped[str] = mapped_column(String(20), index=True)
    # Tipo de evento · ver agent/automation/audit.py:EVENTOS_VALIDOS
    evento: Mapped[str] = mapped_column(String(60), index=True)
    accion_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    riesgo: Mapped[str] = mapped_column(String(20), default="")
    # Resumen sanitizado del payload · solo metadata segura
    payload_summary: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ConsentimientoTerceroAutomation(Base):
    """Consentimiento afirmativo del OWNER para contactar a un TERCERO
    (Fase 0 · 2.5 — política Hermes: block-until-consent por destino).

    Append-only: cada confirmación dedicada (ENVIAR tras un preview que
    muestra el texto de permiso) inserta una fila. Sirve como registro de
    consentimiento (quién, cuándo, con qué texto, para qué acción) y la
    existencia de una fila reciente es lo que el ejecutor exige antes de
    enviar a un destino frío. Guarda teléfonos completos: es estado
    operativo de la política (como acciones_automatizacion), no audit log.
    """
    __tablename__ = "automation_consentimientos_tercero"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono_owner: Mapped[str] = mapped_column(String(50), index=True)
    # Destino normalizado (solo dígitos) — clave de lookup de la política
    destino: Mapped[str] = mapped_column(String(50), index=True)
    # Alcance del consentimiento · v1: "este_mensaje" (cada envío re-confirma)
    scope: Mapped[str] = mapped_column(String(40), default="este_mensaje")
    # Texto de permiso que el owner vio al confirmar (evidencia)
    texto_confirmacion: Mapped[str] = mapped_column(Text, default="")
    source_accion_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class EnvioTerceroAutomation(Base):
    """Log de envíos HIGH efectivamente realizados a terceros (2.5).

    Una fila por envío exitoso. Base de los límites de la política:
    primer contacto (cero filas previas del destino), mensajes por
    destino/día y /7 días, y terceros nuevos por owner/día y /7 días.
    """
    __tablename__ = "automation_envios_tercero"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono_owner: Mapped[str] = mapped_column(String(50), index=True)
    destino: Mapped[str] = mapped_column(String(50), index=True)
    accion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enviado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# ── SQL de migración para PostgreSQL · todo aditivo, idempotente ────────────

MIGRACIONES_AUTOMATION = [
    """
    CREATE TABLE IF NOT EXISTS acciones_automatizacion (
        id                      SERIAL PRIMARY KEY,
        telefono                VARCHAR(50)  NOT NULL,
        opportunity_id          VARCHAR(100) NOT NULL DEFAULT '',
        playbook_id             VARCHAR(100) NOT NULL DEFAULT '',
        tipo_accion             VARCHAR(80)  NOT NULL,
        titulo                  VARCHAR(200) NOT NULL,
        descripcion             TEXT         NOT NULL DEFAULT '',
        razon_recomendacion     TEXT         NOT NULL DEFAULT '',
        estado                  VARCHAR(20)  NOT NULL DEFAULT 'pending',
        riesgo                  VARCHAR(20)  NOT NULL DEFAULT 'medium',
        costo_creditos_estimado INTEGER      NOT NULL DEFAULT 0,
        requires_approval       BOOLEAN      NOT NULL DEFAULT TRUE,
        payload_json            TEXT         NOT NULL DEFAULT '{}',
        result_json             TEXT         NOT NULL DEFAULT '{}',
        error_message           TEXT         NOT NULL DEFAULT '',
        idempotency_key         VARCHAR(120) NOT NULL DEFAULT '',
        created_at              TIMESTAMP    NOT NULL DEFAULT NOW(),
        updated_at              TIMESTAMP    NOT NULL DEFAULT NOW(),
        approved_at             TIMESTAMP,
        rejected_at             TIMESTAMP,
        completed_at            TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_acciones_aut_tel ON acciones_automatizacion (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_acciones_aut_estado ON acciones_automatizacion (estado)",
    "CREATE INDEX IF NOT EXISTS ix_acciones_aut_idem ON acciones_automatizacion (idempotency_key)",
    "CREATE INDEX IF NOT EXISTS ix_acciones_aut_tipo ON acciones_automatizacion (tipo_accion)",
    """
    CREATE TABLE IF NOT EXISTS audit_log_automatizacion (
        id              SERIAL PRIMARY KEY,
        telefono_short  VARCHAR(20)  NOT NULL,
        evento          VARCHAR(60)  NOT NULL,
        accion_id       INTEGER,
        riesgo          VARCHAR(20)  NOT NULL DEFAULT '',
        payload_summary TEXT         NOT NULL DEFAULT '{}',
        created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_audit_aut_tel ON audit_log_automatizacion (telefono_short)",
    "CREATE INDEX IF NOT EXISTS ix_audit_aut_evento ON audit_log_automatizacion (evento)",
    "CREATE INDEX IF NOT EXISTS ix_audit_aut_accion ON audit_log_automatizacion (accion_id)",
    "CREATE INDEX IF NOT EXISTS ix_audit_aut_creado ON audit_log_automatizacion (created_at)",
    # T2.1.D — Reservas de créditos para acciones del Automation Core.
    """
    CREATE TABLE IF NOT EXISTS automation_reservas_credito (
        id                       SERIAL PRIMARY KEY,
        accion_id                INTEGER      NOT NULL UNIQUE,
        telefono                 VARCHAR(50)  NOT NULL,
        creditos                 INTEGER      NOT NULL,
        estado                   VARCHAR(20)  NOT NULL DEFAULT 'pending',
        razon                    TEXT         NOT NULL DEFAULT '',
        transaccion_credito_id   INTEGER,
        creado                   TIMESTAMP    NOT NULL DEFAULT NOW(),
        actualizado              TIMESTAMP    NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_aut_reserva_accion ON automation_reservas_credito (accion_id)",
    "CREATE INDEX IF NOT EXISTS ix_aut_reserva_tel ON automation_reservas_credito (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_aut_reserva_estado ON automation_reservas_credito (estado)",
    # 2.5 — Consentimiento de terceros + log de envíos (política Hermes).
    """
    CREATE TABLE IF NOT EXISTS automation_consentimientos_tercero (
        id                  SERIAL PRIMARY KEY,
        telefono_owner      VARCHAR(50)  NOT NULL,
        destino             VARCHAR(50)  NOT NULL,
        scope               VARCHAR(40)  NOT NULL DEFAULT 'este_mensaje',
        texto_confirmacion  TEXT         NOT NULL DEFAULT '',
        source_accion_id    INTEGER,
        creado              TIMESTAMP    NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_aut_consent_owner ON automation_consentimientos_tercero (telefono_owner)",
    "CREATE INDEX IF NOT EXISTS ix_aut_consent_destino ON automation_consentimientos_tercero (destino)",
    "CREATE INDEX IF NOT EXISTS ix_aut_consent_accion ON automation_consentimientos_tercero (source_accion_id)",
    "CREATE INDEX IF NOT EXISTS ix_aut_consent_creado ON automation_consentimientos_tercero (creado)",
    """
    CREATE TABLE IF NOT EXISTS automation_envios_tercero (
        id              SERIAL PRIMARY KEY,
        telefono_owner  VARCHAR(50)  NOT NULL,
        destino         VARCHAR(50)  NOT NULL,
        accion_id       INTEGER,
        enviado_en      TIMESTAMP    NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_aut_envio3_owner ON automation_envios_tercero (telefono_owner)",
    "CREATE INDEX IF NOT EXISTS ix_aut_envio3_destino ON automation_envios_tercero (destino)",
    "CREATE INDEX IF NOT EXISTS ix_aut_envio3_fecha ON automation_envios_tercero (enviado_en)",
]
