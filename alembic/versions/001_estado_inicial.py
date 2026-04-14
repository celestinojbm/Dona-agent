"""Estado inicial — snapshot de todas las tablas existentes en producción.

Esta migración no ejecuta nada: la DB ya tiene las tablas creadas por
metadata.create_all() y las migraciones manuales en _MIGRACIONES.

Solo sirve como punto de partida para que Alembic sepa el estado actual.

Revision ID: 001_estado_inicial
Create Date: 2026-04-14
"""
from alembic import op

revision = "001_estado_inicial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Todas las tablas ya existen en producción.
    # Este migration es un "stamp" del estado actual.
    pass


def downgrade() -> None:
    # No se puede hacer downgrade del estado inicial
    pass
