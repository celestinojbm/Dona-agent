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

La lista es viva: incluye tablas que nacen en migraciones posteriores
(``uso_proveedor_accion`` en 005). En un upgrade desde cero esas tablas aún
no existen cuando corre 004, y en el downgrade 005 ya las eliminó. Se omite
la que no esté: no se puede hacer ALTER de una relación ausente, y la
migración que la crea habilita su propio RLS.

Revision ID: 004_rls_tablas_existentes
Revises: 003_bienvenida_enviada
Create Date: 2026-10-20
"""

import logging

from sqlalchemy import inspect as sa_inspect

from agent.rls_policy import (
    TABLAS_RLS,
    sentencias_habilitar_rls,
    sentencias_revertir_rls,
)
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

revision = "004_rls_tablas_existentes"
down_revision = "003_bienvenida_enviada"
branch_labels = None
depends_on = None


def _tablas_presentes() -> tuple[str, ...]:
    """Sólo las tablas que ya existen. El resto lo crea una migración posterior."""
    bind = op.get_bind()
    insp = sa_inspect(bind)
    presentes: list[str] = []
    ausentes: list[str] = []
    for tabla in TABLAS_RLS:
        if insp.has_table(tabla):
            presentes.append(tabla)
        else:
            ausentes.append(tabla)
    if ausentes:
        logger.info(
            "RLS: se omiten tablas que todavía no existen "
            "(las crea una migración posterior, con su propio RLS): %s",
            ", ".join(ausentes),
        )
    return tuple(presentes)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (dev/test): no-op. RLS se verifica en PostgreSQL real.
        return
    for sentencia in sentencias_habilitar_rls(_tablas_presentes()):
        op.execute(sentencia)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # ADVERTENCIA: reabre el acceso directo del navegador. Reverso formal; no
    # usar en producción como atajo (nunca desactivar RLS globalmente).
    # En downgrade, 005 ya eliminó uso_proveedor_accion: se omite si no está.
    for sentencia in sentencias_revertir_rls(_tablas_presentes()):
        op.execute(sentencia)
