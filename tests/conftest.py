# tests/conftest.py — Configuración global de pytest para Dona

import os
import pytest

# Asegurar que estamos en modo test (no conectar a DB real)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_dona.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-fake-key")
