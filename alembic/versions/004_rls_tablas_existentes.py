"""Habilita Row Level Security en las tablas existentes (0B).

Contrato (a) — acceso sólo-backend. Con RLS habilitado y sin políticas para
`anon`/`authenticated`, esos roles (los del navegador vía PostgREST) quedan
denegados por defecto. El backend conecta con el rol dueño/`service_role`, que
evita RLS, así que FastAPI y el worker arq siguen operando sin cambios.

Además se revoca (defensa en profundidad, role-gated) todo grant de
`anon`/`authenticated` sobre cada tabla.

Sólo tiene efecto en PostgreSQL. En SQLite (dev/test) es un no-op: SQLite no
soporta RLS y la protección real se prueba contra un PostgreSQL aislado
(tests/security/test_rls.py, gated por DONA_TEST_POSTGRES_URL).

La lista de tablas y el SQL viven en agent/rls_policy.py (fuente única de
verdad), cruzada contra los modelos por el test.

Revision ID: 004_rls_tablas_existentes
Revises: 003_bienvenida_enviada
Create Date: 2026-10-20
"""

from alembic import op

from agent.rls_policy import sentencias_habilitar_rls, sentencias_revertir_rls


revision = "004_rls_tablas_existentes"
down_revision = "003_bienvenida_enviada"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (dev/test): no-op. RLS se verifica en PostgreSQL real.
        return
    for sentencia in sentencias_habilitar_rls():
        op.execute(sentencia)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # ADVERTENCIA: reabre el acceso directo del navegador. Reverso formal; no
    # usar en producción como atajo (nunca desactivar RLS globalmente).
    for sentencia in sentencias_revertir_rls():
        op.execute(sentencia)
