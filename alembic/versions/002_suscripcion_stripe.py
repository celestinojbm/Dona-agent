"""Suscripcion Stripe + idempotencia de eventos (T1.3.A).

Crea las tablas para persistir suscripciones de Stripe ($20 Premium / $40 Pro)
y para idempotencia de eventos webhook por `event.id`. Esta migración no toca
las tablas existentes ni las columnas de `transacciones_credito` ni
`saldo_creditos`.

Diseño:
  - `suscripcion_stripe.subscription_id` (PK) — un solo registro por
    suscripción Stripe; permite upsert sin lookup previo.
  - `suscripcion_stripe.telefono` indexado — para encontrar la suscripción
    activa de un usuario sin escanear toda la tabla.
  - `suscripcion_stripe.customer_id` indexado — para reconciliación con la
    API de Stripe si llega un evento sin metadata directa.
  - `evento_stripe_procesado.event_id` (PK) — idempotencia: cualquier
    reentrega del mismo evento Stripe es no-op.
  - `evento_stripe_procesado.tipo` indexado — para filtrar por tipo en
    diagnóstico (ej. "todos los invoice.payment_succeeded del último mes").

Compatibilidad:
  - En SQLite local: tipos String(N) se mapean a TEXT, DateTime a TIMESTAMP.
  - En PostgreSQL prod: VARCHAR(N) y TIMESTAMP nativos.
  - `metadata.create_all()` en `agent/main.py:lifespan` también las crea
    automáticamente; esta migración Alembic deja un baseline explícito por si
    en el futuro se mueve a `alembic upgrade head` (T4.3).

Revision ID: 002_suscripcion_stripe
Revises: 001_estado_inicial
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa


revision = "002_suscripcion_stripe"
down_revision = "001_estado_inicial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suscripcion_stripe",
        sa.Column("subscription_id", sa.String(length=200), primary_key=True),
        sa.Column("telefono", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=200), nullable=False),
        sa.Column("plan_codigo", sa.String(length=50), nullable=False),
        sa.Column("price_id", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("creditos_mensuales", sa.Integer(), nullable=False),
        sa.Column(
            "ultimo_invoice_acreditado",
            sa.String(length=200),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "creado",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "actualizado",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_suscripcion_stripe_telefono",
        "suscripcion_stripe",
        ["telefono"],
    )
    op.create_index(
        "ix_suscripcion_stripe_customer_id",
        "suscripcion_stripe",
        ["customer_id"],
    )

    op.create_table(
        "evento_stripe_procesado",
        sa.Column("event_id", sa.String(length=200), primary_key=True),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column(
            "recibido_en",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_evento_stripe_procesado_tipo",
        "evento_stripe_procesado",
        ["tipo"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evento_stripe_procesado_tipo",
        table_name="evento_stripe_procesado",
    )
    op.drop_table("evento_stripe_procesado")

    op.drop_index(
        "ix_suscripcion_stripe_customer_id",
        table_name="suscripcion_stripe",
    )
    op.drop_index(
        "ix_suscripcion_stripe_telefono",
        table_name="suscripcion_stripe",
    )
    op.drop_table("suscripcion_stripe")
