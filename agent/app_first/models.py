# agent/app_first/models.py — Modelo de datos de Dona app-first (J7.1)

"""
Tablas nuevas con prefijo ``app_``. Son ADITIVAS: no tocan ninguna tabla
existente (la ruta de creación es la misma que el resto del repo:
``Base.metadata.create_all`` en ``agent.memory.inicializar_db``, que importa
este módulo para registrar las tablas).

Invariante de aislamiento: TODA fila de negocio lleva ``workspace_id`` y el
repositorio (``agent/app_first/repositorio.py``) filtra siempre por el
workspace de la sesión. Un id de otro workspace se trata como inexistente.

Estados y roles son conjuntos CERRADOS (constantes de este módulo); el
repositorio rechaza cualquier valor fuera de ellos.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agent.memory import Base

# ── Conjuntos cerrados ───────────────────────────────────────────────────

ROLES_MIEMBRO = ("owner", "admin", "miembro")
ROLES_AGENTE = ("responsable", "ejecutor")

ESTADOS_PROYECTO = ("activo", "archivado")

# Estados de una tarea (lo que ve el usuario).
ESTADOS_TAREA = (
    "pendiente",
    "en_ejecucion",
    "necesita_aprobacion",
    "bloqueada",
    "completada",
    "fallida",
    "cancelada",
)
ESTADOS_TAREA_TERMINALES = ("completada", "fallida", "cancelada")

# Motivos de bloqueo (cerrados: no inventar strings en los callers).
MOTIVOS_BLOQUEO = (
    "presupuesto_agotado",
    "aprobacion_rechazada",
    "herramienta_no_permitida",
    "proveedor_no_disponible",
    "criterios_no_cumplidos",
)

# Estados de una ejecución (un intento concreto de un agente sobre una tarea).
ESTADOS_EJECUCION = (
    "encolada",
    "en_curso",
    "esperando_aprobacion",
    "terminada",
    "fallida",
    "cancelada",
    "abandonada",
)

ESTADOS_APROBACION = ("pendiente", "aprobada", "rechazada", "caducada")
RIESGOS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")  # taxonomía de automation/permissions.py
TIPOS_EVIDENCIA = ("texto", "archivo", "enlace", "registro")
TIPOS_ACTOR = ("usuario", "agente", "sistema")


def _ahora() -> datetime:
    return datetime.utcnow()


# ── Identidad y workspace ────────────────────────────────────────────────


class AppUsuario(Base):
    """Cuenta propia de Dona app-first: email + contraseña. Sin teléfono ni
    Stripe (la tabla `usuarios` del producto anterior no se reutiliza)."""

    __tablename__ = "app_usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)  # normalizado
    password_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str] = mapped_column(String(120), default="")
    desactivado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppWorkspace(Base):
    __tablename__ = "app_workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120))
    creado_por: Mapped[int] = mapped_column(ForeignKey("app_usuarios.id"))
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppMembresia(Base):
    __tablename__ = "app_membresias"

    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("app_usuarios.id"), primary_key=True)
    rol: Mapped[str] = mapped_column(String(20))  # ROLES_MIEMBRO
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


# ── Organización del trabajo ─────────────────────────────────────────────


class AppArea(Base):
    __tablename__ = "app_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppProyecto(Base):
    __tablename__ = "app_proyectos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("app_areas.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(160))
    objetivo: Mapped[str] = mapped_column(Text, default="")
    criterios_aceptacion_json: Mapped[str] = mapped_column(Text, default="[]")
    responsable_usuario_id: Mapped[int] = mapped_column(ForeignKey("app_usuarios.id"))
    estado: Mapped[str] = mapped_column(String(20), default="activo")  # ESTADOS_PROYECTO
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppAgente(Base):
    """Definición de un agente. No es un proceso permanente: trabaja en
    ejecuciones (`app_ejecuciones`) con estado y hora reales."""

    __tablename__ = "app_agentes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    rol: Mapped[str] = mapped_column(String(20))  # ROLES_AGENTE
    instrucciones: Mapped[str] = mapped_column(Text, default="")
    herramientas_permitidas_json: Mapped[str] = mapped_column(Text, default="[]")
    modelo: Mapped[str] = mapped_column(String(80), default="simulado")
    presupuesto_max_unidades: Mapped[int] = mapped_column(Integer, default=0)
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppTarea(Base):
    __tablename__ = "app_tareas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("app_proyectos.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    asignada_a_agente_id: Mapped[int | None] = mapped_column(ForeignKey("app_agentes.id"), nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente", index=True)  # ESTADOS_TAREA
    motivo_bloqueo: Mapped[str] = mapped_column(String(40), default="")  # MOTIVOS_BLOQUEO o ""
    creada_por: Mapped[int] = mapped_column(ForeignKey("app_usuarios.id"))
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


# ── Ejecución, aprobación y evidencia ────────────────────────────────────


class AppEjecucion(Base):
    __tablename__ = "app_ejecuciones"
    __table_args__ = (
        Index("ix_app_ejecuciones_estado_lease", "estado", "lease_hasta"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    tarea_id: Mapped[int] = mapped_column(ForeignKey("app_tareas.id"), index=True)
    agente_id: Mapped[int] = mapped_column(ForeignKey("app_agentes.id"))
    intento: Mapped[int] = mapped_column(Integer, default=1)
    estado: Mapped[str] = mapped_column(String(30), default="encolada")  # ESTADOS_EJECUCION
    # Única: reintentar el encolado del MISMO intento no crea otra ejecución.
    clave_idempotencia: Mapped[str] = mapped_column(String(200), unique=True)
    lease_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    iniciada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    terminada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_codigo: Mapped[str] = mapped_column(String(60), default="")
    unidades_consumidas: Mapped[int] = mapped_column(Integer, default=0)
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppAprobacion(Base):
    __tablename__ = "app_aprobaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    ejecucion_id: Mapped[int] = mapped_column(ForeignKey("app_ejecuciones.id"), index=True)
    operacion: Mapped[str] = mapped_column(String(80))
    riesgo: Mapped[str] = mapped_column(String(10))  # RIESGOS
    preview_json: Mapped[str] = mapped_column(Text, default="{}")
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")  # ESTADOS_APROBACION
    decidida_por: Mapped[int | None] = mapped_column(ForeignKey("app_usuarios.id"), nullable=True)
    decidida_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppEvidencia(Base):
    __tablename__ = "app_evidencias"
    __table_args__ = (
        # Un reintento que vuelve a producir la misma evidencia no la duplica.
        UniqueConstraint("ejecucion_id", "hash_sha256", name="uq_app_evidencia_ejecucion_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    ejecucion_id: Mapped[int] = mapped_column(ForeignKey("app_ejecuciones.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # TIPOS_EVIDENCIA
    contenido: Mapped[str] = mapped_column(Text, default="")
    hash_sha256: Mapped[str] = mapped_column(String(64))
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppActividad(Base):
    """Registro de actividad por workspace (datos sanitizados con
    agent.automation.audit.sanitizar_payload)."""

    __tablename__ = "app_actividad"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    actor_tipo: Mapped[str] = mapped_column(String(20))  # TIPOS_ACTOR
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evento: Mapped[str] = mapped_column(String(60))
    objeto_tipo: Mapped[str] = mapped_column(String(40), default="")
    objeto_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    datos_json: Mapped[str] = mapped_column(Text, default="{}")
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora, index=True)


class AppConsumo(Base):
    __tablename__ = "app_consumo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    ejecucion_id: Mapped[int] = mapped_column(ForeignKey("app_ejecuciones.id"), index=True)
    proveedor: Mapped[str] = mapped_column(String(40))
    unidades: Mapped[int] = mapped_column(Integer, default=0)
    simulado: Mapped[bool] = mapped_column(Boolean, default=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class AppMensajeProyecto(Base):
    """Chat del proyecto: mensajes vinculados al proyecto y, opcionalmente,
    a una tarea concreta."""

    __tablename__ = "app_mensajes_proyecto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("app_proyectos.id"), index=True)
    tarea_id: Mapped[int | None] = mapped_column(ForeignKey("app_tareas.id"), nullable=True)
    autor_tipo: Mapped[str] = mapped_column(String(20))  # TIPOS_ACTOR
    autor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contenido: Mapped[str] = mapped_column(Text)
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora, index=True)


class AppEfecto(Base):
    """Efecto de una operación reservada (tras aprobación).

    La clave de idempotencia es única: si un reintento o un worker reiniciado
    vuelve a ejecutar la misma operación aprobada, encuentra la fila y
    devuelve el resultado anterior en vez de repetir el efecto.
    """

    __tablename__ = "app_efectos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("app_workspaces.id"), index=True)
    clave_idempotencia: Mapped[str] = mapped_column(String(200), unique=True)
    operacion: Mapped[str] = mapped_column(String(80))
    ejecucion_id: Mapped[int] = mapped_column(ForeignKey("app_ejecuciones.id"), index=True)
    resultado_json: Mapped[str] = mapped_column(Text, default="{}")
    simulado: Mapped[bool] = mapped_column(Boolean, default=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=_ahora)
