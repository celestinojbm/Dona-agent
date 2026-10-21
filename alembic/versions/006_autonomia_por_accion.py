"""Autonomía por acción (F1): config de niveles + autorizaciones persistidas.

Crea `autonomia_por_accion` (nivel 1–4 por usuario+tipo, con UNIQUE y CHECK) y
`autorizaciones_accion` (la autorización que confirmar_X consume: hash de args,
cotización, máximo, origen humana|politica, estado, vencimiento, uso único).
Ambas backend-only: RLS + revoke de anon/authenticated (sólo PostgreSQL).

Nota de integración: parte de `main` (head 003). Al fusionar varias ramas del
plan puede hacer falta una revisión de merge de Alembic. No aplicada a remoto.

Revision ID: 006_autonomia_por_accion
Revises: 003_bienvenida_enviada
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa


revision = "006_autonomia_por_accion"
down_revision = "003_bienvenida_enviada"
branch_labels = None
depends_on = None

_TABLAS = ("autonomia_por_accion", "autorizaciones_accion")


def upgrade() -> None:
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

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for t in _TABLAS:
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


def downgrade() -> None:
    op.drop_table("autorizaciones_accion")
    op.drop_table("autonomia_por_accion")
