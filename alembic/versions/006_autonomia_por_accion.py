"""Autonomía por acción (F1): config de niveles + autorizaciones persistidas.

Crea `autonomia_por_accion` (nivel 1–4 por usuario+tipo, con UNIQUE y CHECK) y
`autorizaciones_accion` (la autorización que confirmar_X consume: hash de args,
cotización, máximo, origen humana|politica, estado, vencimiento, uso único).
Ambas backend-only: RLS + revoke de anon/authenticated (sólo PostgreSQL).

Nota de integración: cadena lineal de Alembic (006 sobre 005 sobre 004). Resuelve
al fusionar los PRs en orden.

IDEMPOTENTE: el backend crea las tablas con create_all al arrancar, así que este
upgrade comprueba la existencia de cada tabla antes de crearla (evita el error
"relation already exists" cuando create_all ya corrió). El habilitado de RLS es
idempotente (ENABLE RLS repetido no falla).

Revision ID: 006_autonomia_por_accion
Revises: 005_recibo_por_accion
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "006_autonomia_por_accion"
down_revision = "005_recibo_por_accion"
branch_labels = None
depends_on = None

_TABLAS = ("autonomia_por_accion", "autorizaciones_accion", "reservas_credito")


def _rls_backend_only(t: str) -> None:
    op.execute(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY;')
    op.execute(
        "DO $$\nBEGIN\n"
        "  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN\n"
        f"    EXECUTE 'REVOKE ALL ON TABLE \"{t}\" FROM anon';\n"
        "  END IF;\n"
        "  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN\n"
        f"    EXECUTE 'REVOKE ALL ON TABLE \"{t}\" FROM authenticated';\n"
        "  END IF;\n"
        "END\n$$;"
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if not insp.has_table("autonomia_por_accion"):
        op.create_table(
            "autonomia_por_accion",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("telefono", sa.String(length=50), nullable=False),
            sa.Column("tipo_accion", sa.String(length=80), nullable=False),
            sa.Column("nivel", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("umbral_creditos", sa.Integer(), nullable=True),
            sa.Column("tope_por_accion", sa.Integer(), nullable=True),
            sa.Column("tope_periodo", sa.Integer(), nullable=True),
            sa.Column("periodo", sa.String(length=10), nullable=False, server_default=""),
            sa.Column("zona_horaria", sa.String(length=60), nullable=False, server_default=""),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("actualizado", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("telefono", "tipo_accion", name="uq_autonomia_tel_accion"),
            sa.CheckConstraint("nivel >= 1 AND nivel <= 4", name="ck_autonomia_nivel"),
        )
        op.create_index(
            "ix_autonomia_por_accion_telefono", "autonomia_por_accion", ["telefono"]
        )

    if not insp.has_table("autorizaciones_accion"):
        op.create_table(
            "autorizaciones_accion",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("telefono", sa.String(length=50), nullable=False),
            sa.Column("accion_ref", sa.String(length=120), nullable=False),
            sa.Column("tipo_accion", sa.String(length=80), nullable=False),
            sa.Column("args_hash", sa.String(length=64), nullable=False),
            sa.Column("cotizacion_creditos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("maximo_creditos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("origen", sa.String(length=10), nullable=False, server_default="humana"),
            sa.Column("estado", sa.String(length=12), nullable=False, server_default="vigente"),
            sa.Column("vencimiento", sa.DateTime(), nullable=False),
            sa.Column("consumida_en", sa.DateTime(), nullable=True),
            sa.Column("version_politica", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("creado", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("accion_ref", name="uq_autorizacion_accion_ref"),
            sa.CheckConstraint(
                "origen IN ('humana','politica')", name="ck_autorizacion_origen"
            ),
        )
        op.create_index(
            "ix_autorizaciones_accion_telefono", "autorizaciones_accion", ["telefono"]
        )
        op.create_index(
            "ix_autorizaciones_accion_estado", "autorizaciones_accion", ["estado"]
        )

    # Reserva write-ahead de créditos (decisión de Celestino #6).
    if not insp.has_table("reservas_credito"):
        op.create_table(
            "reservas_credito",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("telefono", sa.String(length=50), nullable=False),
            sa.Column("accion_ref", sa.String(length=120), nullable=False),
            sa.Column("creditos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("estado", sa.String(length=12), nullable=False, server_default="reservada"),
            sa.Column("idempotency_key", sa.String(length=250), nullable=True),
            sa.Column("creado", sa.DateTime(), nullable=True),
            sa.Column("actualizado", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("accion_ref", name="uq_reserva_accion_ref"),
            sa.CheckConstraint(
                "estado IN ('reservada','consumida','liberada')", name="ck_reserva_estado"
            ),
        )
        op.create_index("ix_reservas_credito_telefono", "reservas_credito", ["telefono"])
        op.create_index("ix_reservas_credito_estado", "reservas_credito", ["estado"])

    if bind.dialect.name == "postgresql":
        for t in _TABLAS:
            _rls_backend_only(t)


def downgrade() -> None:
    # ADVERTENCIA: hace DROP TABLE → BORRA DATOS. En producción NO ejecutar este
    # downgrade sin respaldo verificado; la pérdida de datos sería real (no
    # silenciosa: queda advertida aquí). En CI corre contra una BD efímera vacía.
    bind = op.get_bind()
    insp = sa_inspect(bind)
    for t in ("reservas_credito", "autorizaciones_accion", "autonomia_por_accion"):
        if insp.has_table(t):
            op.drop_table(t)
