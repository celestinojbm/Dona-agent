"""Placeholder vacío: cierra el hueco de la cadena 005 -> 007.

007_plan_vivo ya apunta a 006_autonomia_por_accion como down_revision. Esta
migración no cambia el esquema; sólo mantiene la cadena lineal de Alembic
(005_recibo_por_accion -> 006_autonomia_por_accion -> 007_plan_vivo -> 008).

Revision ID: 006_autonomia_por_accion
Revises: 005_recibo_por_accion
Create Date: 2026-10-22
"""

revision = "006_autonomia_por_accion"
down_revision = "005_recibo_por_accion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
