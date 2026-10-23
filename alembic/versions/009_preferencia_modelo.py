"""Multi-modelo (F23): preferencia_modelo por chat/agente.

Backend-only: RLS + revoke de anon/authenticated (sólo PostgreSQL). UNIQUE por
(telefono, scope, scope_id).

Cadena lineal de Alembic (009 sobre 008, final de la cadena del plan). Resuelve
al fusionar los PRs en orden.

IDEMPOTENTE: el backend crea la tabla con create_all al arrancar, así que este
upgrade comprueba la existencia antes de crearla (evita "relation already
exists"). El habilitado de RLS es idempotente.

Revision ID: 009_preferencia_modelo
Revises: 008_primer_valor_onboarding
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "009_preferencia_modelo"
down_revision = "008_primer_valor_onboarding"
branch_labels = None
depends_on = None

_TABLA = "preferencia_modelo"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if not insp.has_table(_TABLA):
        op.create_table(
            _TABLA,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("telefono", sa.String(length=50), nullable=False),
            sa.Column("scope", sa.String(length=10), nullable=False),
            sa.Column("scope_id", sa.String(length=120), nullable=False),
            sa.Column("modelo_id", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("modo_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("actualizado", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("telefono", "scope", "scope_id", name="uq_preferencia_modelo"),
        )
        op.create_index(f"ix_{_TABLA}_telefono", _TABLA, ["telefono"])

    if bind.dialect.name == "postgresql":
        op.execute(f'ALTER TABLE "{_TABLA}" ENABLE ROW LEVEL SECURITY;')
        op.execute(
            "DO $$\nBEGIN\n"
            "  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN\n"
            f"    EXECUTE 'REVOKE ALL ON TABLE \"{_TABLA}\" FROM anon';\n"
            "  END IF;\n"
            "  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN\n"
            f"    EXECUTE 'REVOKE ALL ON TABLE \"{_TABLA}\" FROM authenticated';\n"
            "  END IF;\n"
            "END\n$$;"
        )


def downgrade() -> None:
    # ADVERTENCIA: hace DROP TABLE → BORRA DATOS en producción (no silencioso:
    # queda advertido aquí). No ejecutar en prod sin respaldo. En CI es una BD
    # efímera vacía.
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if insp.has_table(_TABLA):
        op.drop_table(_TABLA)
