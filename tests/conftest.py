# tests/conftest.py — Configuración global de pytest para Dona

import os
import pytest

# Asegurar que estamos en modo test (no conectar a DB real)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_dona.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-fake-key")

# J4 · Los efectos externos están APAGADOS por defecto (agent/efectos.py).
# La suite existente prueba el comportamiento con los efectos encendidos y
# todos los proveedores mockeados (sin red real), así que aquí se encienden
# explícitamente. Los tests de arranque sin efectos
# (tests/test_efectos_arranque.py) los apagan con monkeypatch.
for _var in (
    "DONA_SCHEDULER_ENABLED",
    "DONA_WORKER_ENABLED",
    "DONA_WHATSAPP_ENABLED",
    "DONA_STRIPE_ENABLED",
    "DONA_LLM_ENABLED",
    "DONA_INBOUND_ENABLED",
):
    os.environ.setdefault(_var, "true")
