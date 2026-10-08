#!/usr/bin/env bash
# deploy/msi/estado.sh — Estado del stack "dona" (solo lectura).
#
# Solo lista recursos con la etiqueta com.dona.stack=staging o del proyecto
# compose "dona": nunca otros contenedores de la máquina.
set -euo pipefail

echo "== Contenedores de Dona"
docker ps -a --filter label=com.dona.stack=staging \
  --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

echo; echo "== Consumo (instantánea)"
ids="$(docker ps -q --filter label=com.dona.stack=staging)"
if [[ -n "$ids" ]]; then
  # shellcheck disable=SC2086
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' $ids
else
  echo "(ninguno corriendo)"
fi

echo; echo "== Imagen en ejecución (SHA)"
docker inspect --format '{{.Name}} {{index .Config.Labels "org.opencontainers.image.revision"}}' $ids 2>/dev/null || true

echo; echo "== Volúmenes de Dona"
docker volume ls --filter name=^dona- --format '{{.Name}}'

echo; echo "== Salud (loopback)"
puerto="${DONA_API_PORT:-8010}"
curl -fsS "http://127.0.0.1:$puerto/health/vida" && echo || echo "vida: sin respuesta"
curl -sS "http://127.0.0.1:$puerto/health/listo" && echo || echo "listo: sin respuesta"
