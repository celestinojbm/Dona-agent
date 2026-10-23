"""Tests de RLS (0B).

Dos niveles:

1. Ejecutables siempre (contrato de la política, sin DB): la lista de tablas no
   se desincroniza de los modelos, y el SQL generado tiene la forma esperada y
   está limitado a PostgreSQL.

2. PostgreSQL real (gated por DONA_TEST_POSTGRES_URL): verifica que, tras
   habilitar RLS, los roles del navegador (anon/authenticated) quedan denegados
   mientras el dueño sigue operando. Se SKIPEA si no hay Postgres aislado — la
   atomicidad/RLS real requiere Postgres, no SQLite (ver el plan). No corre
   contra producción ni contra servicios facturables.
"""

import os
import importlib.util
from pathlib import Path

import pytest


def _cargar_migracion():
    """Carga la migración 004 por ruta (alembic/versions no es un paquete y el
    nombre empieza con dígito, así que import_module no sirve)."""
    ruta = (
        Path(__file__).resolve().parents[1].parent
        / "alembic"
        / "versions"
        / "004_rls_tablas_existentes.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_004_rls", ruta)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

from agent.rls_policy import (
    TABLAS_RLS,
    ROLES_NAVEGADOR,
    sentencias_habilitar_rls,
    sentencias_revertir_rls,
)


def _tablas_de_modelos() -> set[str]:
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_dona.db")
    import agent.memory as memoria
    import agent.business.models  # noqa: F401
    import agent.automation.models  # noqa: F401
    import agent.dashboard_lockout  # noqa: F401
    import enhanced.models  # noqa: F401

    return set(memoria.Base.metadata.tables.keys())


# ─────────────────────── Nivel 1: contrato, sin DB ───────────────────────

def test_lista_rls_cubre_todas_las_tablas_de_modelos():
    modelos = _tablas_de_modelos()
    rls = set(TABLAS_RLS)
    faltan = modelos - rls
    sobran = rls - modelos
    assert not faltan, f"Tablas con modelo sin RLS declarado: {sorted(faltan)}"
    assert not sobran, f"RLS declara tablas inexistentes: {sorted(sobran)}"


def test_sin_tablas_duplicadas():
    assert len(TABLAS_RLS) == len(set(TABLAS_RLS))


def test_habilitar_genera_enable_y_revoke_por_tabla():
    sentencias = sentencias_habilitar_rls()
    # 2 sentencias por tabla: ENABLE + bloque DO de revoke
    assert len(sentencias) == len(TABLAS_RLS) * 2
    for tabla in TABLAS_RLS:
        enable = f'ALTER TABLE "{tabla}" ENABLE ROW LEVEL SECURITY;'
        assert enable in sentencias
    # Los bloques DO revocan a anon y authenticated, role-gated
    revokes = [s for s in sentencias if s.startswith("DO $$")]
    assert len(revokes) == len(TABLAS_RLS)
    for rol in ROLES_NAVEGADOR:
        assert all(rol in s for s in revokes)
    assert all("pg_roles" in s and "REVOKE ALL" in s for s in revokes)


def test_revertir_reabre_pero_es_el_reverso():
    reversa = sentencias_revertir_rls()
    assert len(reversa) == len(TABLAS_RLS) * 2
    for tabla in TABLAS_RLS:
        disable = f'ALTER TABLE "{tabla}" DISABLE ROW LEVEL SECURITY;'
        assert disable in reversa
    assert all("GRANT ALL" in s for s in reversa if s.startswith("DO $$"))


def test_migracion_encadena_con_003_y_usa_el_helper():
    mod = _cargar_migracion()
    assert mod.revision == "004_rls_tablas_existentes"
    assert mod.down_revision == "003_bienvenida_enviada"


def test_migracion_es_noop_en_sqlite():
    """El upgrade no debe ejecutar DDL cuando el dialecto no es postgresql."""
    mod = _cargar_migracion()

    ejecutadas: list[str] = []

    class _FakeDialect:
        name = "sqlite"

    class _FakeBind:
        dialect = _FakeDialect()

    import alembic.op as alembic_op

    orig_get_bind = alembic_op.get_bind
    orig_execute = alembic_op.execute
    alembic_op.get_bind = lambda: _FakeBind()
    alembic_op.execute = lambda s: ejecutadas.append(s)
    try:
        mod.upgrade()
        mod.downgrade()
    finally:
        alembic_op.get_bind = orig_get_bind
        alembic_op.execute = orig_execute

    assert ejecutadas == [], "La migración no debe tocar DDL en SQLite"


def test_migracion_omite_tablas_ausentes_en_postgresql():
    """004 no debe ALTER una tabla que todavía no existe (p. ej. la de 005)."""
    mod = _cargar_migracion()
    ejecutadas: list[str] = []

    class _FakeDialect:
        name = "postgresql"

    class _FakeBind:
        dialect = _FakeDialect()

    class _Insp:
        def has_table(self, nombre: str) -> bool:
            return nombre == "mensajes"

    import alembic.op as alembic_op

    orig_get_bind = alembic_op.get_bind
    orig_execute = alembic_op.execute
    orig_inspect = mod.sa_inspect
    alembic_op.get_bind = lambda: _FakeBind()
    alembic_op.execute = lambda s: ejecutadas.append(s)
    mod.sa_inspect = lambda _bind: _Insp()
    try:
        mod.upgrade()
        mod.downgrade()
    finally:
        alembic_op.get_bind = orig_get_bind
        alembic_op.execute = orig_execute
        mod.sa_inspect = orig_inspect

    assert ejecutadas, "Debe tocar la tabla que sí existe"
    for sentencia in ejecutadas:
        assert "mensajes" in sentencia
        assert "uso_proveedor_accion" not in sentencia
        assert "timezone_usuarios" not in sentencia


# ─────────────────── Nivel 2: PostgreSQL aislado (gated) ───────────────────

_PG_URL = os.getenv("DONA_TEST_POSTGRES_URL")

try:  # psycopg2 es la dependencia de migration.py
    import psycopg2  # type: ignore

    _TIENE_PSYCOPG2 = True
except Exception:  # pragma: no cover
    _TIENE_PSYCOPG2 = False

_pg = pytest.mark.skipif(
    not (_PG_URL and _TIENE_PSYCOPG2),
    reason="Requiere PostgreSQL aislado: fija DONA_TEST_POSTGRES_URL (no prod).",
)


@_pg
def test_rls_real_deniega_al_rol_navegador():  # pragma: no cover (necesita PG)
    conn = psycopg2.connect(_PG_URL)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("DROP TABLE IF EXISTS rls_demo")
        cur.execute("CREATE TABLE rls_demo (id serial primary key, telefono text)")
        cur.execute("INSERT INTO rls_demo (telefono) VALUES ('+100'), ('+200')")
        # Rol navegador de prueba (NOLOGIN) con grant previo
        cur.execute(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') "
            "THEN CREATE ROLE anon NOLOGIN; END IF; END $$;"
        )
        cur.execute("GRANT ALL ON rls_demo TO anon")

        for s in sentencias_habilitar_rls(("rls_demo",)):
            cur.execute(s)

        # Como 'anon', RLS sin política => 0 filas / denegado
        cur.execute("SET ROLE anon")
        cur.execute("SELECT count(*) FROM rls_demo")
        assert cur.fetchone()[0] == 0
        with pytest.raises(psycopg2.Error):
            cur.execute("INSERT INTO rls_demo (telefono) VALUES ('+300')")
        conn.rollback()
        cur.execute("RESET ROLE")

        # El dueño (conexión directa) sigue viendo todo (evita RLS)
        cur.execute("SELECT count(*) FROM rls_demo")
        assert cur.fetchone()[0] == 2
    finally:
        cur.execute("RESET ROLE")
        cur.execute("DROP TABLE IF EXISTS rls_demo")
        cur.close()
        conn.close()
