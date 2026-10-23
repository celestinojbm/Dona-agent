"""Recibo por acción (F3): columnas de recibo + tabla de uso por proveedor.

Añade a `transacciones_credito` las columnas aditivas `accion_ref`,
`idempotency_key` (UNIQUE — idempotencia del débito) y `desglose_json`, y crea
`uso_proveedor_accion` (telemetría durable por proveedor) con RLS backend-only.

Columnas nullable → filas históricas quedan en NULL; el UNIQUE sobre
idempotency_key admite múltiples NULL (Postgres y SQLite) así que no hay que
retrofittear ni reescribir débitos históricos.

RLS/grants de la tabla nueva: sólo PostgreSQL (dialect-guarded). En SQLite es
no-op. El contrato es el mismo que 0B: backend-only, sin acceso de
anon/authenticated.

Nota de integración: cadena lineal de Alembic. 005 va encadenada sobre 004
(ya fusionada en `main` vía PR 298). Resuelve del todo cuando los PRs se fusionan
en orden (004→005→006→…). No se aplicó ninguna migración a remoto. La rama NO se
pudo actualizar desde origin/main por `git merge` bloqueado en el entorno; sólo
se fijó down_revision.

Revision ID: 005_recibo_por_accion
Revises: 004_rls_tablas_existentes
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa


revision = "005_recibo_por_accion"
down_revision = "004_rls_tablas_existentes"
branch_labels = None
depends_on = None

_TABLA_USO = "uso_proveedor_accion"


def upgrade() -> None:
    # Guard: en BD vacia (CI) transacciones_credito no existe (la crea
    # metadata.create_all()); en la BD real existe y el efecto es identico.
    if sa.inspect(op.get_bind()).has_table("transacciones_credito"):
        op.add_column(
            "transacciones_credito",
            sa.Column("accion_ref", sa.String(length=120), nullable=True),
        )
        op.create_index(
            "ix_transacciones_credito_accion_ref",
            "transacciones_credito",
            ["accion_ref"],
        )
        op.add_column(
            "transacciones_credito",
            sa.Column("idempotency_key", sa.String(length=250), nullable=True),
        )
        op.create_index(
            "uq_transaccion_idempotency_key",
            "transacciones_credito",
            ["idempotency_key"],
            unique=True,
        )
        op.add_column(
            "transacciones_credito",
            sa.Column("desglose_json", sa.Text(), nullable=True),
        )

    op.create_table(
        _TABLA_USO,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telefono", sa.String(length=50), nullable=False),
        sa.Column("accion_ref", sa.String(length=120), nullable=False),
        sa.Column("proveedor", sa.String(length=60), nullable=False),
        sa.Column("modelo", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("intento", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_ref", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("usage_json", sa.Text(), nullable=True),
        sa.Column("costo_base", sa.String(length=40), nullable=True),
        sa.Column("moneda", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="estimado"),
        sa.Column("creado", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "accion_ref", "proveedor", "intento", name="uq_uso_prov_ejecucion"
        ),
    )
    op.create_index(f"ix_{_TABLA_USO}_telefono", _TABLA_USO, ["telefono"])
    op.create_index(f"ix_{_TABLA_USO}_accion_ref", _TABLA_USO, ["accion_ref"])
    op.create_index(f"ix_{_TABLA_USO}_creado", _TABLA_USO, ["creado"])

    # RLS backend-only de la tabla nueva — sólo PostgreSQL.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f'ALTER TABLE "{_TABLA_USO}" ENABLE ROW LEVEL SECURITY;')
        op.execute(
            "DO $$\nBEGIN\n"
            "  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN\n"
            f"    EXECUTE 'REVOKE ALL ON TABLE \"{_TABLA_USO}\" FROM anon';\n"
            "  END IF;\n"
            "  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN\n"
            f"    EXECUTE 'REVOKE ALL ON TABLE \"{_TABLA_USO}\" FROM authenticated';\n"
            "  END IF;\n"
            "END\n$$;"
        )


def downgrade() -> None:
    op.drop_table(_TABLA_USO)
    if sa.inspect(op.get_bind()).has_table("transacciones_credito"):
        op.drop_index("uq_transaccion_idempotency_key", table_name="transacciones_credito")
        op.drop_index(
            "ix_transacciones_credito_accion_ref", table_name="transacciones_credito"
        )
        op.drop_column("transacciones_credito", "desglose_json")
        op.drop_column("transacciones_credito", "idempotency_key")
        op.drop_column("transacciones_credito", "accion_ref")
