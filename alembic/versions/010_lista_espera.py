"""Lista de espera e invitaciones (Fase 1 · issue #334).

Backend-only: RLS + revoke de anon/authenticated (sólo PostgreSQL). Un
correo por fila (UNIQUE).

IDEMPOTENTE: el backend crea la tabla con create_all al arrancar, así que este
upgrade comprueba la existencia antes de crearla. El habilitado de RLS es
idempotente.

Revision ID: 010_lista_espera
Revises: 009_preferencia_modelo
Create Date: 2026-11-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "010_lista_espera"
down_revision = "009_preferencia_modelo"
branch_labels = None
depends_on = None

_TABLA = "lista_espera"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if not insp.has_table(_TABLA):
        op.create_table(
            _TABLA,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("email", sa.String(length=254), nullable=False),
            sa.Column("estado", sa.String(length=20), nullable=False, server_default="en_espera"),
            sa.Column("origen", sa.String(length=30), nullable=False, server_default="web"),
            sa.Column("creado", sa.DateTime(), nullable=True),
            sa.Column("invitado_en", sa.DateTime(), nullable=True),
        )
        op.create_index(f"ix_{_TABLA}_email", _TABLA, ["email"], unique=True)

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
    # ADVERTENCIA: hace DROP TABLE → BORRA los correos de la lista de espera.
    # No ejecutar en prod sin respaldo.
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if insp.has_table(_TABLA):
        op.drop_table(_TABLA)
