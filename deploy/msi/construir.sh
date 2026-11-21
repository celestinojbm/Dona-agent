#!/usr/bin/env bash
# deploy/msi/construir.sh — Construye la imagen dona-api desde un SHA fijo.
#
# Uso: deploy/msi/construir.sh <sha-de-40-hex>
#
# Exporta el árbol EXACTO de ese commit con `git archive` (nunca el working
# tree, que puede tener cambios sin commitear) y construye dona-api:<sha>.
# No arranca nada. No toca otras imágenes.
set -euo pipefail

sha="${1:-}"
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Uso: $0 <sha de 40 caracteres hex>" >&2
  exit 2
fi

repo="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
git -C "$repo" cat-file -e "${sha}^{commit}" 2>/dev/null || {
  echo "El commit $sha no existe en $repo (haz git fetch primero)." >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git -C "$repo" archive --format=tar "$sha" | tar -x -C "$tmp"
docker build \
  --label com.dona.stack=staging \
  --label org.opencontainers.image.revision="$sha" \
  -t "dona-api:$sha" "$tmp"

echo "Imagen lista: dona-api:$sha"
