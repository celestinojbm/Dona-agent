"""Límites por IP y globales de la lista de espera (issue #334).

Contadores por ventana de 1 hora (agent/lista_espera/limites.py). Sin PII:
la IP va como HMAC truncado dentro de la clave. Backend-only: RLS + revoke de
anon/authenticated (sólo PostgreSQL).

IDEMPOTENTE: el backend crea la tabla con create_all al arrancar, así que este
upgrade comprueba la existencia antes de crearla.

Revision ID: 011_lista_espera_limite
Revises: 010_lista_espera
Create Date: 2026-11-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "011_lista_espera_limite"
down_revision = "010_lista_espera"
branch_labels = None
depends_on = None

_TABLA = "lista_espera_limite"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa_inspect(bind)

    if not insp.has_table(_TABLA):
        op.create_table(
            _TABLA,
            sa.Column("clave", sa.String(length=120), primary_key=True),
            sa.Column("conteo", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expira_en", sa.DateTime(), nullable=False),
        )
        op.create_index(f"ix_{_TABLA}_expira_en", _TABLA, ["expira_en"])

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
    # Solo contadores temporales: borrarlos reinicia los límites, nada más.
    bind = op.get_bind()
    insp = sa_inspect(bind)
    if insp.has_table(_TABLA):
        op.drop_table(_TABLA)
