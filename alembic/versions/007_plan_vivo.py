"""Plan vivo de tarea (F14): plan_tarea + notificaciones_plan (outbox).

Backend-only: RLS + revoke de anon/authenticated (sólo PostgreSQL). `plan_tarea`
tiene concurrencia optimista (`revision`) y UNIQUE por accion_ref;
`notificaciones_plan` es un outbox idempotente (UNIQUE por dedupe_key).

Cadena lineal de Alembic (007 sobre 006). Resuelve al fusionar los PRs en orden.
No aplicada a remoto. La rama NO se pudo actualizar desde origin/main (`git merge`
bloqueado en el entorno); sólo se fijó down_revision.

Revision ID: 007_plan_vivo
Revises: 006_autonomia_por_accion
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa


revision = "007_plan_vivo"
down_revision = "006_autonomia_por_accion"
branch_labels = None
depends_on = None

_TABLAS = ("plan_tarea", "notificaciones_plan")


def upgrade() -> None:
    op.create_table(
        "plan_tarea",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telefono", sa.String(length=50), nullable=False),
        sa.Column("job_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("accion_ref", sa.String(length=120), nullable=False),
        sa.Column("autorizacion_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("hash_plan", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("coste_maximo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pasos_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="preparado"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mensaje_ref", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("creado", sa.DateTime(), nullable=True),
        sa.Column("actualizado", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("accion_ref", name="uq_plan_accion_ref"),
    )
    op.create_index("ix_plan_tarea_telefono", "plan_tarea", ["telefono"])
    op.create_index("ix_plan_tarea_job_id", "plan_tarea", ["job_id"])
    op.create_index("ix_plan_tarea_accion_ref", "plan_tarea", ["accion_ref"])
    op.create_index("ix_plan_tarea_estado", "plan_tarea", ["estado"])

    op.create_table(
        "notificaciones_plan",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("telefono", sa.String(length=50), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False, server_default="actualizacion"),
        sa.Column("estado", sa.String(length=12), nullable=False, server_default="pendiente"),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creado", sa.DateTime(), nullable=True),
        sa.Column("enviado_en", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("dedupe_key", name="uq_notificacion_dedupe"),
    )
    op.create_index("ix_notificaciones_plan_plan_id", "notificaciones_plan", ["plan_id"])
    op.create_index("ix_notificaciones_plan_telefono", "notificaciones_plan", ["telefono"])

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
    op.drop_table("notificaciones_plan")
    op.drop_table("plan_tarea")
