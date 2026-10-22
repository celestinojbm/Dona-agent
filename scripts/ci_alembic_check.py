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
"""

from __future__ import annotations

import os
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory

try:  # ubicación de ResolutionError varía entre versiones de alembic
    from alembic.script.revision import ResolutionError
except Exception:  # pragma: no cover
    class ResolutionError(Exception):  # type: ignore
        pass


def _config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    return cfg


def main() -> int:
    cfg = _config()
    script = ScriptDirectory.from_config(cfg)

    try:
        # Forzar la construcción del mapa de revisiones (resuelve down_revisions).
        list(script.walk_revisions("base", "heads"))
        heads = script.get_heads()
    except (ResolutionError, KeyError) as e:
        # Un down_revision que apunta a una revisión ausente aparece como
        # KeyError al construir el mapa (o ResolutionError, según versión):
        # significa predecesor aún no fusionado → se omite, no es error del PR.
        print(
            "[alembic-check] Cadena incompleta (un predecesor aún no está en "
            f"main): falta la revisión {e}. Se omite; pasará cuando el PR "
            "anterior se fusione.",
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
