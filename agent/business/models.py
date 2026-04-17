# agent/business/models.py — Modelos de base de datos para funcionalidades de negocio

"""
Modelos SQLAlchemy para el módulo de negocio de Dona:
- PerfilNegocio: configuración del negocio del usuario
- ClienteNegocio: CRM ligero
- Producto: catálogo de productos/servicios
- Transaccion: registro financiero (ventas + gastos)
- Pedido: gestión de órdenes
- Seguimiento: follow-ups programados para clientes
- Cotizacion: presupuestos y cotizaciones
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, Date

from agent.memory import Base


class PerfilNegocio(Base):
    """Perfil de negocio del usuario — configura cómo Dona lo asiste."""
    __tablename__ = "perfil_negocio"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    nombre_negocio: Mapped[str] = mapped_column(String(200), default="")
    industria: Mapped[str] = mapped_column(String(50), default="general")
    # Valores: restaurante, servicios, retail, freelancer, otro
    descripcion: Mapped[str] = mapped_column(Text, default="")
    moneda: Mapped[str] = mapped_column(String(10), default="MXN")
    meta_mensual: Mapped[float] = mapped_column(Float, default=0.0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClienteNegocio(Base):
    """Cliente del negocio del usuario — CRM ligero."""
    __tablename__ = "clientes_negocio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono_owner: Mapped[str] = mapped_column(String(50), index=True)  # dueño del negocio
    nombre: Mapped[str] = mapped_column(String(200))
    telefono_cliente: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    notas: Mapped[str] = mapped_column(Text, default="")
    total_compras: Mapped[float] = mapped_column(Float, default=0.0)
    num_compras: Mapped[int] = mapped_column(Integer, default=0)
    ultima_compra: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Producto(Base):
    """Producto o servicio del catálogo del negocio."""
    __tablename__ = "productos_negocio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    precio: Mapped[float] = mapped_column(Float, default=0.0)
    costo: Mapped[float] = mapped_column(Float, default=0.0)  # para cálculo de margen
    categoria: Mapped[str] = mapped_column(String(100), default="general")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Transaccion(Base):
    """Transacción financiera: venta o gasto."""
    __tablename__ = "transacciones_negocio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # "venta" o "gasto"
    monto: Mapped[float] = mapped_column(Float)
    descripcion: Mapped[str] = mapped_column(Text, default="")
    categoria: Mapped[str] = mapped_column(String(100), default="general")
    cliente_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    producto_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Pedido(Base):
    """Pedido/orden de un cliente."""
    __tablename__ = "pedidos_negocio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    cliente_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cliente_nombre: Mapped[str] = mapped_column(String(200), default="")
    descripcion: Mapped[str] = mapped_column(Text, default="")
    monto: Mapped[float] = mapped_column(Float, default=0.0)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente")
    # Estados: pendiente, en_preparacion, listo, entregado, cancelado
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    direccion: Mapped[str] = mapped_column(Text, default="")
    notas: Mapped[str] = mapped_column(Text, default="")
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Seguimiento(Base):
    """Follow-up programado para un cliente."""
    __tablename__ = "seguimientos_negocio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    cliente_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cliente_nombre: Mapped[str] = mapped_column(String(200), default="")
    descripcion: Mapped[str] = mapped_column(Text)
    fecha_programada: Mapped[datetime] = mapped_column(DateTime, index=True)
    completado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Cotizacion(Base):
    """Cotización/presupuesto para un cliente."""
    __tablename__ = "cotizaciones_negocio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    cliente_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cliente_nombre: Mapped[str] = mapped_column(String(200), default="")
    items_json: Mapped[str] = mapped_column(Text, default="[]")
    # JSON: [{"concepto": str, "cantidad": int, "precio_unitario": float, "subtotal": float}]
    total: Mapped[float] = mapped_column(Float, default=0.0)
    estado: Mapped[str] = mapped_column(String(20), default="borrador")
    # Estados: borrador, enviada, aceptada, rechazada
    notas: Mapped[str] = mapped_column(Text, default="")
    vigencia_dias: Mapped[int] = mapped_column(Integer, default=15)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── SQL de migración para PostgreSQL ────────────────────────────────────────

MIGRACIONES_NEGOCIO = [
    """
    CREATE TABLE IF NOT EXISTS perfil_negocio (
        telefono        VARCHAR(50) PRIMARY KEY,
        nombre_negocio  VARCHAR(200) NOT NULL DEFAULT '',
        industria       VARCHAR(50)  NOT NULL DEFAULT 'general',
        descripcion     TEXT         NOT NULL DEFAULT '',
        moneda          VARCHAR(10)  NOT NULL DEFAULT 'MXN',
        meta_mensual    FLOAT        NOT NULL DEFAULT 0.0,
        activo          BOOLEAN      NOT NULL DEFAULT TRUE,
        creado          TIMESTAMP,
        actualizado     TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS clientes_negocio (
        id               SERIAL PRIMARY KEY,
        telefono_owner   VARCHAR(50)  NOT NULL,
        nombre           VARCHAR(200) NOT NULL,
        telefono_cliente VARCHAR(50)  NOT NULL DEFAULT '',
        email            VARCHAR(200) NOT NULL DEFAULT '',
        notas            TEXT         NOT NULL DEFAULT '',
        total_compras    FLOAT        NOT NULL DEFAULT 0.0,
        num_compras      INTEGER      NOT NULL DEFAULT 0,
        ultima_compra    TIMESTAMP,
        creado           TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_clientes_neg_owner ON clientes_negocio (telefono_owner)",
    """
    CREATE TABLE IF NOT EXISTS productos_negocio (
        id        SERIAL PRIMARY KEY,
        telefono  VARCHAR(50)  NOT NULL,
        nombre    VARCHAR(200) NOT NULL,
        precio    FLOAT        NOT NULL DEFAULT 0.0,
        costo     FLOAT        NOT NULL DEFAULT 0.0,
        categoria VARCHAR(100) NOT NULL DEFAULT 'general',
        activo    BOOLEAN      NOT NULL DEFAULT TRUE,
        creado    TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_productos_neg_tel ON productos_negocio (telefono)",
    """
    CREATE TABLE IF NOT EXISTS transacciones_negocio (
        id           SERIAL PRIMARY KEY,
        telefono     VARCHAR(50)  NOT NULL,
        tipo         VARCHAR(20)  NOT NULL,
        monto        FLOAT        NOT NULL,
        descripcion  TEXT         NOT NULL DEFAULT '',
        categoria    VARCHAR(100) NOT NULL DEFAULT 'general',
        cliente_id   INTEGER,
        producto_id  INTEGER,
        fecha        TIMESTAMP    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_transacciones_neg_tel ON transacciones_negocio (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_transacciones_neg_fecha ON transacciones_negocio (fecha)",
    """
    CREATE TABLE IF NOT EXISTS pedidos_negocio (
        id              SERIAL PRIMARY KEY,
        telefono        VARCHAR(50)  NOT NULL,
        cliente_id      INTEGER,
        cliente_nombre  VARCHAR(200) NOT NULL DEFAULT '',
        descripcion     TEXT         NOT NULL DEFAULT '',
        monto           FLOAT        NOT NULL DEFAULT 0.0,
        estado          VARCHAR(30)  NOT NULL DEFAULT 'pendiente',
        fecha_entrega   TIMESTAMP,
        direccion       TEXT         NOT NULL DEFAULT '',
        notas           TEXT         NOT NULL DEFAULT '',
        creado          TIMESTAMP,
        actualizado     TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_pedidos_neg_tel ON pedidos_negocio (telefono)",
    """
    CREATE TABLE IF NOT EXISTS seguimientos_negocio (
        id               SERIAL PRIMARY KEY,
        telefono         VARCHAR(50)  NOT NULL,
        cliente_id       INTEGER,
        cliente_nombre   VARCHAR(200) NOT NULL DEFAULT '',
        descripcion      TEXT         NOT NULL,
        fecha_programada TIMESTAMP    NOT NULL,
        completado       BOOLEAN      NOT NULL DEFAULT FALSE,
        creado           TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_seguimientos_neg_tel ON seguimientos_negocio (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_seguimientos_neg_fecha ON seguimientos_negocio (fecha_programada)",
    """
    CREATE TABLE IF NOT EXISTS cotizaciones_negocio (
        id              SERIAL PRIMARY KEY,
        telefono        VARCHAR(50)  NOT NULL,
        cliente_id      INTEGER,
        cliente_nombre  VARCHAR(200) NOT NULL DEFAULT '',
        items_json      TEXT         NOT NULL DEFAULT '[]',
        total           FLOAT        NOT NULL DEFAULT 0.0,
        estado          VARCHAR(20)  NOT NULL DEFAULT 'borrador',
        notas           TEXT         NOT NULL DEFAULT '',
        vigencia_dias   INTEGER      NOT NULL DEFAULT 15,
        creado          TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_cotizaciones_neg_tel ON cotizaciones_negocio (telefono)",
]
