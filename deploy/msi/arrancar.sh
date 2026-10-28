#!/usr/bin/env bash
# deploy/msi/arrancar.sh — Arranca SOLO el stack "dona" (requiere OK de Celestino).
#
# Uso:
#   DONA_SHA=<sha> DONA_ENV_FILE=/ruta/absoluta/dona.env deploy/msi/arrancar.sh [--arq]
#
# Antes de levantar: valida el compose, que la imagen exista con ese SHA y
# que el env file no sea legible por otros. --arq añade Redis y el worker.
set -euo pipefail

dir="$(cd "$(dirname "$0")" && pwd)"
: "${DONA_SHA:?Define DONA_SHA (commit de la imagen)}"
: "${DONA_ENV_FILE:?Define DONA_ENV_FILE (ruta absoluta al env file)}"

[[ "$DONA_ENV_FILE" = /* ]] || { echo "DONA_ENV_FILE debe ser ruta absoluta" >&2; exit 2; }
[[ -f "$DONA_ENV_FILE" ]] || { echo "No existe $DONA_ENV_FILE" >&2; exit 2; }
perms="$(stat -c '%a' "$DONA_ENV_FILE")"
[[ "$perms" =~ ^[46]00$ ]] || { echo "$DONA_ENV_FILE tiene permisos $perms; usa chmod 600" >&2; exit 2; }

docker image inspect "dona-api:$DONA_SHA" >/dev/null 2>&1 || {
  echo "No existe la imagen dona-api:$DONA_SHA (ejecuta construir.sh $DONA_SHA)" >&2
  exit 1
}

perfil=()
[[ "${1:-}" == "--arq" ]] && perfil=(--profile arq)

"$dir/validar.sh"
docker compose -f "$dir/compose.yml" "${perfil[@]}" up -d
docker compose -f "$dir/compose.yml" "${perfil[@]}" ps
