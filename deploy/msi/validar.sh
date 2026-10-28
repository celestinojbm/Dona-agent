#!/usr/bin/env bash
# deploy/msi/validar.sh — Valida el compose sin arrancar nada (solo lectura).
#
# Comprueba: sintaxis, que solo se publiquen puertos en 127.0.0.1 y que
# Redis no publique puertos. Funciona sin daemon de Docker.
set -euo pipefail

dir="$(cd "$(dirname "$0")" && pwd)"
export DONA_SHA="${DONA_SHA:-0000000000000000000000000000000000000000}"
export DONA_ENV_FILE="${DONA_ENV_FILE:-/dev/null}"

cfg="$(docker compose -f "$dir/compose.yml" --profile arq config --format json)"

python3 - "$cfg" <<'PY'
import json, sys
cfg = json.loads(sys.argv[1])
errores = []
for nombre, svc in cfg.get("services", {}).items():
    for p in svc.get("ports", []) or []:
        if p.get("host_ip") != "127.0.0.1":
            errores.append(f"{nombre}: puerto {p.get('published')} publicado fuera de 127.0.0.1")
    if nombre == "dona-redis" and svc.get("ports"):
        errores.append("dona-redis no debe publicar puertos")
    if svc.get("labels", {}).get("com.dona.stack") != "staging":
        errores.append(f"{nombre}: falta la etiqueta com.dona.stack=staging")
if cfg.get("name") != "dona":
    errores.append("el proyecto compose debe llamarse 'dona'")
if errores:
    print("COMPOSE NO VÁLIDO:\n  - " + "\n  - ".join(errores)); sys.exit(1)
print("compose OK: proyecto 'dona', puertos solo en 127.0.0.1, Redis sin puertos")
PY
