"""Migraciones 010 (lista_espera) y 011 (lista_espera_limite) contra PostgreSQL real.

El job genérico de Alembic (scripts/ci_alembic_check.py) ya corre
``upgrade head`` + ``downgrade base`` en un Postgres limpio, pero ahí no existen
los roles ``anon``/``authenticated``: el bloque ``REVOKE`` de 010/011 nunca se
ejecuta y nadie comprueba que RLS quede activo. Este archivo cubre lo que ese
check no ve:

- upgrade paso a paso 009 → 010 → 011 y el esquema resultante (índices,
  defaults, UNIQUE del correo);
- RLS habilitado y privilegios revocados a los roles del navegador, con los
  roles creados y con grants por defecto al estilo Supabase;
- downgrade 011 → 010 → 009 (010 conserva sus filas al bajar 011) y re-upgrade;
- idempotencia: el backend crea las tablas con ``create_all`` al arrancar, así
  que el upgrade debe pasar si las tablas ya existen y aun así aplicar RLS.

Gated por ``DONA_TEST_POSTGRES_URL`` (mismo convenio que
tests/security/test_rls.py). Sólo acepta un servidor local: cada test crea su
propia base de datos temporal y la borra al terminar, así que nunca toca el
esquema de la base apuntada ni producción.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

_PG_URL = os.getenv("DONA_TEST_POSTGRES_URL")
_HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1"}
_RAIZ = Path(__file__).resolve().parents[1]
_ROLES_NAVEGADOR = ("anon", "authenticated")
_PRIVILEGIOS = ("SELECT", "INSERT", "UPDATE", "DELETE")

try:
    import psycopg2  # type: ignore  # noqa: F401
    import sqlalchemy as sa
    from sqlalchemy.engine import make_url

    _TIENE_DRIVER = True
except Exception:  # pragma: no cover
    _TIENE_DRIVER = False

pytestmark = pytest.mark.skipif(
    not (_PG_URL and _TIENE_DRIVER),
    reason="Requiere PostgreSQL local aislado: fija DONA_TEST_POSTGRES_URL (no prod).",
)


# ─────────────────────────────── utilidades ───────────────────────────────


def _url_sync(url) -> str:
    return url.set(drivername="postgresql+psycopg2").render_as_string(hide_password=False)


def _url_async(url) -> str:
    # alembic/env.py convierte asyncpg → psycopg2 para migrar, y agent.memory
    # (que env.py importa) necesita un driver async para crear su engine.
    return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)


@pytest.fixture
def bd():
    """Base de datos temporal en el servidor local; se borra al terminar."""
    base = make_url(_PG_URL)
    if base.host not in _HOSTS_LOCALES:
        pytest.skip(
            f"DONA_TEST_POSTGRES_URL apunta a '{base.host}': sólo se acepta un servidor local."
        )

    nombre = f"dona_mig_lista_espera_{uuid.uuid4().hex[:8]}"
    admin = sa.create_engine(_url_sync(base), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        for rol in _ROLES_NAVEGADOR:  # constantes del módulo, no entrada externa
            c.execute(
                sa.text(
                    f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rol}') "
                    f"THEN CREATE ROLE {rol} NOLOGIN; END IF; END $$;"
                )
            )
        c.execute(sa.text(f'CREATE DATABASE "{nombre}"'))

    url = base.set(database=nombre)
    motor = sa.create_engine(_url_sync(url))
    # Como en Supabase: los roles del navegador reciben grants sobre toda tabla
    # nueva del esquema public. Sin el REVOKE de la migración conservarían acceso.
    with motor.begin() as c:
        c.execute(sa.text("GRANT USAGE ON SCHEMA public TO anon, authenticated"))
        c.execute(
            sa.text(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT ALL ON TABLES TO anon, authenticated"
            )
        )
    try:
        yield url, motor
    finally:
        motor.dispose()
        with admin.connect() as c:
            c.execute(sa.text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        admin.dispose()


def _alembic(url, *args: str) -> None:
    entorno = {
        **os.environ,
        "DATABASE_URL": _url_async(url),
        "ENVIRONMENT": "test",
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "sk-ant-test-fake-key"),
    }
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(_RAIZ / "alembic.ini"), *args],
        cwd=_RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert r.returncode == 0, (
        f"alembic {' '.join(args)} falló:\n{r.stdout[-2000:]}\n{r.stderr[-4000:]}"
    )


def _version(motor) -> str:
    with motor.connect() as c:
        return c.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()


def _existe(motor, tabla: str) -> bool:
    with motor.connect() as c:
        return (
            c.execute(sa.text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}).scalar()
            is not None
        )


def _rls_activo(motor, tabla: str) -> bool:
    with motor.connect() as c:
        return c.execute(
            sa.text("SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass(:t)"),
            {"t": f"public.{tabla}"},
        ).scalar_one()


def _privilegios_navegador(motor, tabla: str) -> dict[str, list[str]]:
    """Privilegios que conserva cada rol del navegador sobre la tabla."""
    resultado: dict[str, list[str]] = {}
    with motor.connect() as c:
        for rol in _ROLES_NAVEGADOR:
            resultado[rol] = [
                p
                for p in _PRIVILEGIOS
                if c.execute(
                    sa.text("SELECT has_table_privilege(:r, :t, :p)"),
                    {"r": rol, "t": f"public.{tabla}", "p": p},
                ).scalar_one()
            ]
    return resultado


def _indices(motor, tabla: str) -> dict[str, str]:
    with motor.connect() as c:
        filas = c.execute(
            sa.text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = :t"
            ),
            {"t": tabla},
        ).all()
    return {nombre: definicion for nombre, definicion in filas}


def _assert_backend_only(motor, tabla: str) -> None:
    assert _rls_activo(motor, tabla), f"RLS no quedó habilitado en {tabla}"
    restantes = _privilegios_navegador(motor, tabla)
    assert restantes == {rol: [] for rol in _ROLES_NAVEGADOR}, (
        f"Los roles del navegador conservan privilegios sobre {tabla}: {restantes}"
    )


def _assert_esquema_lista_espera(motor) -> None:
    indices = _indices(motor, "lista_espera")
    emails = [d for d in indices.values() if "(email)" in d]
    assert len(emails) == 1, f"Se esperaba un único índice sobre email: {indices}"
    assert "UNIQUE" in emails[0]
    _assert_backend_only(motor, "lista_espera")


def _assert_esquema_limite(motor) -> None:
    indices = _indices(motor, "lista_espera_limite")
    assert any(d.endswith("(clave)") and "UNIQUE" in d for d in indices.values()), indices  # PK
    expira = [d for d in indices.values() if "(expira_en)" in d]
    assert len(expira) == 1, f"Se esperaba un único índice sobre expira_en: {indices}"
    _assert_backend_only(motor, "lista_espera_limite")


# ───────────────────────────────── tests ─────────────────────────────────


def test_upgrade_paso_a_paso_009_010_011(bd):
    url, motor = bd

    _alembic(url, "upgrade", "009_preferencia_modelo")
    assert _version(motor) == "009_preferencia_modelo"
    assert not _existe(motor, "lista_espera")
    assert not _existe(motor, "lista_espera_limite")

    _alembic(url, "upgrade", "010_lista_espera")
    assert _version(motor) == "010_lista_espera"
    assert _existe(motor, "lista_espera")
    assert not _existe(motor, "lista_espera_limite")
    _assert_esquema_lista_espera(motor)

    with motor.begin() as c:
        estado, origen = c.execute(
            sa.text(
                "INSERT INTO lista_espera (email) VALUES ('uno@example.com') RETURNING estado, origen"
            )
        ).one()
    assert (estado, origen) == ("en_espera", "web")
    with pytest.raises(sa.exc.IntegrityError):
        with motor.begin() as c:
            c.execute(sa.text("INSERT INTO lista_espera (email) VALUES ('uno@example.com')"))

    _alembic(url, "upgrade", "011_lista_espera_limite")
    assert _version(motor) == "011_lista_espera_limite"
    assert _existe(motor, "lista_espera_limite")
    _assert_esquema_limite(motor)
    with motor.begin() as c:
        conteo = c.execute(
            sa.text(
                "INSERT INTO lista_espera_limite (clave, expira_en) "
                "VALUES ('alta:global:x:1', now()) RETURNING conteo"
            )
        ).scalar_one()
        filas = c.execute(sa.text("SELECT count(*) FROM lista_espera")).scalar_one()
    assert conteo == 0
    assert filas == 1, "Subir a 011 no debe tocar los datos de lista_espera"


def test_downgrade_011_010_y_reupgrade(bd):
    url, motor = bd
    _alembic(url, "upgrade", "011_lista_espera_limite")
    with motor.begin() as c:
        c.execute(sa.text("INSERT INTO lista_espera (email) VALUES ('dos@example.com')"))
        c.execute(
            sa.text(
                "INSERT INTO lista_espera_limite (clave, expira_en) VALUES ('canje:ip:y:1', now())"
            )
        )

    _alembic(url, "downgrade", "010_lista_espera")
    assert _version(motor) == "010_lista_espera"
    assert not _existe(motor, "lista_espera_limite")
    assert _existe(motor, "lista_espera")
    with motor.connect() as c:
        assert c.execute(sa.text("SELECT email FROM lista_espera")).scalars().all() == [
            "dos@example.com"
        ]

    _alembic(url, "downgrade", "009_preferencia_modelo")
    assert _version(motor) == "009_preferencia_modelo"
    assert not _existe(motor, "lista_espera")

    # Ida y vuelta: el re-upgrade deja el mismo estado que el primero.
    _alembic(url, "upgrade", "011_lista_espera_limite")
    assert _version(motor) == "011_lista_espera_limite"
    _assert_esquema_lista_espera(motor)
    _assert_esquema_limite(motor)


def test_upgrade_idempotente_si_create_all_ya_creo_las_tablas(bd):
    """El backend hace create_all al arrancar: en prod las tablas pueden existir
    antes de que corra Alembic. El upgrade no debe fallar ni duplicar índices, y
    tiene que aplicar RLS/revoke igual."""
    url, motor = bd
    _alembic(url, "upgrade", "009_preferencia_modelo")

    from agent.lista_espera.limites import ListaEsperaLimite
    from agent.lista_espera.models import ListaEspera

    ListaEspera.__table__.create(motor)
    ListaEsperaLimite.__table__.create(motor)
    # Con los grants por defecto, create_all deja las tablas abiertas al navegador.
    assert _privilegios_navegador(motor, "lista_espera")["anon"] == list(_PRIVILEGIOS)
    assert not _rls_activo(motor, "lista_espera")

    _alembic(url, "upgrade", "011_lista_espera_limite")
    assert _version(motor) == "011_lista_espera_limite"
    _assert_esquema_lista_espera(motor)
    _assert_esquema_limite(motor)
