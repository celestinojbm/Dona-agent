"""Primer valor (F12): onboarding_primer_valor + eventos_onboarding.

Backend-only: RLS + revoke de anon/authenticated (sólo PostgreSQL). Mide el
time-to-first-value; `eventos_onboarding` registra sólo la etapa (sin respuestas
libres).

Cadena lineal de Alembic (008 sobre 007). Resuelve al fusionar los PRs en orden.

IDEMPOTENTE: el backend crea las tablas con create_all al arrancar, así que este
upgrade comprueba la existencia de cada tabla antes de crearla (evita "relation
already exists"). El habilitado de RLS es idempotente.

Revision ID: 008_primer_valor_onboarding
Revises: 007_plan_vivo
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "008_primer_valor_onboarding"
down_revision = "007_plan_vivo"
branch_labels = None
depends_on = None

_TABLAS = ("onboarding_primer_valor", "eventos_onboarding")


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

    if not insp.has_table("onboarding_primer_valor"):
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

    if not insp.has_table("eventos_onboarding"):
        op.create_table(
            "eventos_onboarding",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("telefono", sa.String(length=50), nullable=False),
            sa.Column("etapa", sa.String(length=20), nullable=False),
            sa.Column("creado", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_eventos_onboarding_telefono", "eventos_onboarding", ["telefono"])
        op.create_index("ix_eventos_onboarding_creado", "eventos_onboarding", ["creado"])

    if bind.dialect.name == "postgresql":
        for t in _TABLAS:
            _rls_backend_only(t)


def downgrade() -> None:
    # ADVERTENCIA: hace DROP TABLE → BORRA DATOS en producción (no silencioso:
    # queda advertido aquí). No ejecutar en prod sin respaldo. En CI es una BD
    # efímera vacía.
    bind = op.get_bind()
    insp = sa_inspect(bind)
    for t in ("eventos_onboarding", "onboarding_primer_valor"):
        if insp.has_table(t):
            op.drop_table(t)
