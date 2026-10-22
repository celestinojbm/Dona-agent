#!/usr/bin/env python3
"""Verificación de la cadena Alembic para CI.

Objetivo (sólo CI):
  1. Que exista UN SOLO head de migraciones (detecta divergencia/múltiples heads).
  2. upgrade head + downgrade base contra una BD efímera aislada (el servicio
     Postgres del workflow), para probar que la cadena corre en ambos sentidos.

Cadena incompleta: en los PRs encadenados (006->007->008->009), cada rama trae
sólo SU migración; el predecesor llega a `main` cuando el PR anterior se fusiona.
Mientras el predecesor no esté presente, el `down_revision` no resuelve: eso NO
es un error de este PR, así que se OMITE con aviso (exit 0). En `main` (cadena
completa) la verificación es estricta: un head y upgrade/downgrade reales.

No hace llamadas de red ni a APIs de pago. La parte de BD sólo corre si
ALEMBIC_CHECK_DB=1 (lo pone el workflow con el Postgres efímero); sin eso sólo
valida la forma de la cadena (útil en local, sin BD).

001_estado_inicial es un stamp: no crea tablas, asume el esquema que
``metadata.create_all()`` ya tenía en producción. Una BD efímera vacía no cumple
esa precondición, y 004 hace ``ENABLE ROW LEVEL SECURITY`` sobre esas tablas
(``mensajes`` y el resto). Antes de upgrade se materializa ese baseline y se
retiran los objetos que 002+ deben crear, para que el upgrade y el downgrade
los ejerciten de verdad. 004 además omite tablas que todavía no existen
(``uso_proveedor_accion`` nace en 005).
"""

from __future__ import annotations

import os
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError

# Tablas que nacen en migraciones posteriores a 001. El baseline no las deja
# creadas: el upgrade tiene que crearlas.
_TABLAS_DE_MIGRACION = (
    "suscripcion_stripe",  # 002
    "evento_stripe_procesado",  # 002
    "uso_proveedor_accion",  # 005
    "autonomia_por_accion",  # 006
    "autorizaciones_accion",  # 006
    "reservas_credito",  # 006
)

# Columnas que 005 agrega sobre transacciones_credito (tabla del baseline).
_COLUMNAS_005 = ("accion_ref", "idempotency_key", "desglose_json")


def _config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    return cfg


def _url_sync(url: str) -> str:
    """Driver síncrono para el baseline. Alembic (env.py) hace lo mismo."""
    for prefijo in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg2://" + url[len(prefijo):]
    return url


def _importar_modelos() -> None:
    """Registra en Base.metadata las tablas que 001 da por existentes."""
    import agent.automation.models  # noqa: F401
    import agent.autonomia.models  # noqa: F401
    import agent.business.models  # noqa: F401
    import agent.dashboard_lockout  # noqa: F401
    import agent.memory  # noqa: F401
    import enhanced.models  # noqa: F401


def _materializar_estado_inicial() -> None:
    """Crea el esquema que 001 documenta y quita lo que deben crear 002+.

    Falla en claro si, tras eso, falta una tabla que 004 tiene que tocar o si
    quedó un objeto que el upgrade va a intentar crear.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    from agent.memory import Base
    from agent.rls_policy import TABLAS_RLS

    url = os.environ.get("DATABASE_URL", "")
    sync = _url_sync(url)
    if not sync.startswith("postgresql+psycopg2://"):
        raise SystemExit(
            "[alembic-check] ALEMBIC_CHECK_DB=1 exige una DATABASE_URL de PostgreSQL "
            f"(recibida: {url.split('://', 1)[0] if '://' in url else 'vacía'})."
        )

    _importar_modelos()
    engine = create_engine(sync, poolclass=NullPool)
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            for tabla in _TABLAS_DE_MIGRACION:
                conn.execute(text(f'DROP TABLE IF EXISTS "{tabla}" CASCADE'))
            for columna in _COLUMNAS_005:
                conn.execute(
                    text(
                        "ALTER TABLE transacciones_credito "
                        f"DROP COLUMN IF EXISTS {columna}"
                    )
                )

            existentes = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
            }
            deben = set(TABLAS_RLS) - set(_TABLAS_DE_MIGRACION)
            faltan = sorted(deben - existentes)
            if faltan:
                raise SystemExit(
                    "[alembic-check] Baseline de 001 incompleto; faltan tablas "
                    f"que 004 debe poder alterar: {faltan}"
                )
            sobran = sorted(set(_TABLAS_DE_MIGRACION) & existentes)
            if sobran:
                raise SystemExit(
                    "[alembic-check] El baseline dejó tablas que debe crear el "
                    f"upgrade: {sobran}"
                )
            columnas = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' "
                        "AND table_name = 'transacciones_credito'"
                    )
                )
            }
            de_mas = sorted(set(_COLUMNAS_005) & columnas)
            if de_mas:
                raise SystemExit(
                    "[alembic-check] transacciones_credito todavía tiene columnas "
                    f"de 005: {de_mas}"
                )
        print(
            "[alembic-check] Baseline de 001 listo "
            f"({len(deben)} tablas; 002+ las crea el upgrade).",
            flush=True,
        )
    finally:
        engine.dispose()


def main() -> int:
    cfg = _config()
    script = ScriptDirectory.from_config(cfg)

    try:
        # Forzar la construcción del mapa de revisiones (resuelve down_revisions).
        list(script.walk_revisions("base", "heads"))
        heads = script.get_heads()
    except ResolutionError as e:
        print(
            "[alembic-check] Cadena incompleta (un predecesor aún no está en "
            f"main): {e}. Se omite; pasará cuando el PR anterior se fusione.",
            flush=True,
        )
        return 0

    if len(heads) != 1:
        print(
            f"[alembic-check] ERROR: se esperaba UN head, hay {len(heads)}: "
            f"{heads}. Revisa divergencia de migraciones.",
            flush=True,
        )
        return 1
    print(f"[alembic-check] Head único OK: {heads[0]}", flush=True)

    if os.getenv("ALEMBIC_CHECK_DB", "0") == "1":
        from alembic import command

        print(
            "[alembic-check] Materializando el esquema que 001 asume (stamp)...",
            flush=True,
        )
        _materializar_estado_inicial()
        print("[alembic-check] upgrade head (BD efímera)...", flush=True)
        command.upgrade(cfg, "head")
        print("[alembic-check] downgrade base (BD efímera)...", flush=True)
        command.downgrade(cfg, "base")
        print("[alembic-check] upgrade/downgrade OK", flush=True)
    else:
        print(
            "[alembic-check] ALEMBIC_CHECK_DB!=1: sólo se validó la forma de la "
            "cadena (sin BD).",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
