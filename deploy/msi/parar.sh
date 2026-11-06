#!/usr/bin/env bash
# deploy/msi/parar.sh — Para SOLO el stack "dona". Conserva volúmenes y datos.
#
# `docker compose stop` detiene los contenedores sin borrarlos. Este paquete
# no tiene ningún comando con `down -v`, `volume rm` ni `system prune`.
set -euo pipefail

dir="$(cd "$(dirname "$0")" && pwd)"
# compose necesita las variables para interpolar el archivo; para parar no
# importan sus valores reales.
DONA_SHA="${DONA_SHA:-parar}" DONA_ENV_FILE="${DONA_ENV_FILE:-/dev/null}" \
  docker compose -f "$dir/compose.yml" --profile arq stop
docker ps -a --filter label=com.dona.stack=staging --format '{{.Names}}\t{{.Status}}'
