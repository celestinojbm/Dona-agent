#!/bin/bash
# Dona — Script de inicio para dev
# El usuario ejecuta: bash start.sh

set -e

echo ""
echo "==========================================================="
echo "   Dona — Asistente de WhatsApp con IA"
echo "==========================================================="
echo ""
echo "  Preparando tu entorno de desarrollo..."
echo ""

# ── Verificar Python ──────────────────────────────────────────
echo "  [1/4] Verificando Python..."
if ! command -v python3 &> /dev/null; then
    echo ""
    echo "  ERROR: Python 3 no encontrado."
    echo "  Descargalo en: https://python.org/downloads"
    echo ""
    exit 1
fi

PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo ""
    echo "  ERROR: Necesitas Python 3.11 o superior."
    echo "  Version actual: $(python3 --version)"
    echo "  Descarga la ultima version en: https://python.org/downloads"
    echo ""
    exit 1
fi
echo "  OK — $(python3 --version)"

# ── Verificar Claude Code ────────────────────────────────────
echo "  [2/4] Verificando Claude Code..."
if ! command -v claude &> /dev/null; then
    echo ""
    echo "  Claude Code no esta instalado."
    echo ""
    echo "  Para instalarlo:"
    echo "    npm install -g @anthropic-ai/claude-code"
    echo ""
    echo "  Si no tienes npm/Node.js:"
    echo "    https://nodejs.org (descarga LTS)"
    echo ""
    echo "  Despues de instalar, ejecuta 'claude' una vez para autenticarte"
    echo "  y luego vuelve a correr: bash start.sh"
    echo ""
    exit 1
fi
echo "  OK — Claude Code instalado"

# ── Crear carpetas base ──────────────────────────────────────
echo "  [3/4] Preparando carpetas..."
mkdir -p knowledge
echo "  OK — Estructura lista"

# ── Listo ─────────────────────────────────────────────────────
echo "  [4/4] Todo verificado"

echo ""
echo "==========================================================="
echo ""
echo "  Todo listo. Ahora abre Claude Code:"
echo ""
echo "    claude"
echo ""
echo "  Y escribe:"
echo ""
echo "    /build-agent"
echo ""
echo "  Claude Code te guiara paso a paso para construir"
echo "  tu agente de WhatsApp personalizado con IA."
echo ""
echo "==========================================================="
echo ""
