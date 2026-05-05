"""bienvenida_enviada en suscripcion_stripe (T2.0.B).

Agrega un flag de idempotencia para el welcome WhatsApp post-checkout
con password derivado del dashboard (T2.0.B).

Diseño:
  - `suscripcion_stripe.bienvenida_enviada BOOLEAN DEFAULT false`.
  - Se setea a true cuando `enviar_bienvenida_premium` logró enviar
    (o simular en DRY_RUN).
  - Antes de enviar, el handler chequea el flag y skip-ea si está en true.
  - Migración aditiva y backwards-compatible: filas existentes quedan
    con default=false, lo que en práctica significa "el welcome no
    se envió" — correcto para suscripciones pre-T2.0.B.

Compatibilidad:
  - SQLite local: se acepta `BOOLEAN DEFAULT 0/1`.
  - PostgreSQL prod: `BOOLEAN DEFAULT FALSE`.
  - `metadata.create_all()` en `agent/main.py:lifespan` también puede
    crear el campo si la tabla se reconstruye en dev/test.

Revision ID: 003_bienvenida_enviada
Revises: 002_suscripcion_stripe
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa


revision = "003_bienvenida_enviada"
down_revision = "002_suscripcion_stripe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suscripcion_stripe",
        sa.Column(
            "bienvenida_enviada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("suscripcion_stripe", "bienvenida_enviada")
