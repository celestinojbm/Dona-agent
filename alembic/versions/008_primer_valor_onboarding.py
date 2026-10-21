"""Primer valor (F12): onboarding_primer_valor + eventos_onboarding.

Backend-only: RLS + revoke de anon/authenticated (sólo PostgreSQL). Mide el
time-to-first-value; `eventos_onboarding` registra sólo la etapa (sin respuestas
libres).

Cadena lineal de Alembic (008 sobre 007). Resuelve al fusionar los PRs en orden.
No aplicada a remoto. La rama NO se pudo actualizar desde origin/main (`git merge`
bloqueado en el entorno); sólo se fijó down_revision.

Revision ID: 008_primer_valor_onboarding
Revises: 007_plan_vivo
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa


revision = "008_primer_valor_onboarding"
down_revision = "007_plan_vivo"
branch_labels = None
depends_on = None

_TABLAS = ("onboarding_primer_valor", "eventos_onboarding")


def upgrade() -> None:
    op.create_table(
        "onboarding_primer_valor",
        sa.Column("telefono", sa.String(length=50), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("first_result_at", sa.DateTime(), nullable=True),
        sa.Column("first_action_ref", sa.String(length=120), nullable=True),
        sa.Column("first_result_kind", sa.String(length=40), nullable=True),
        sa.Column("actualizado", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "eventos_onboarding",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telefono", sa.String(length=50), nullable=False),
        sa.Column("etapa", sa.String(length=20), nullable=False),
        sa.Column("creado", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_eventos_onboarding_telefono", "eventos_onboarding", ["telefono"])
    op.create_index("ix_eventos_onboarding_creado", "eventos_onboarding", ["creado"])

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
    op.drop_table("eventos_onboarding")
    op.drop_table("onboarding_primer_valor")
