# tests/test_creditos_de_plan.py — Tests T1.3.B helper creditos_de_plan

"""
Cubre el alcance mínimo de T1.3.B:
  - premium con env var seteada → int correcto.
  - pro con env var seteada → int correcto.
  - plan desconocido → None + warning.
  - env faltante en producción → None + ERROR (no acreditar).
  - env faltante en dev/test → default conservador (premium=100, pro=500).
  - env mal formado (no int, vacío con espacios, valor <= 0) → None.
  - case-insensitive y trim de plan_codigo.

NO cubre:
  - Procesamiento de eventos Stripe (T1.3.C).
  - Endpoint /internal/stripe-event (T1.3.D).
  - Bridge landing → backend (T1.3.E).
"""

import os
import pytest

from agent.billing import creditos_de_plan


# ── Plan conocido + env var seteada ─────────────────────────────────────────


class TestEnvSeteada:
    def test_premium_devuelve_valor_de_env_var(self, monkeypatch):
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100")
        assert creditos_de_plan("premium") == 100

    def test_pro_devuelve_valor_de_env_var(self, monkeypatch):
        monkeypatch.setenv("STRIPE_CREDITOS_PRO", "500")
        assert creditos_de_plan("pro") == 500

    def test_premium_con_otro_valor_de_env(self, monkeypatch):
        """El helper respeta el valor configurado por el owner, no hardcodea."""
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "250")
        assert creditos_de_plan("premium") == 250

    def test_case_insensitive_y_trim(self, monkeypatch):
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100")
        assert creditos_de_plan("PREMIUM") == 100
        assert creditos_de_plan("  Premium  ") == 100
        assert creditos_de_plan("premium\n") == 100


# ── Plan desconocido ────────────────────────────────────────────────────────


class TestPlanDesconocido:
    def test_plan_vacio_retorna_none(self, monkeypatch):
        # Aunque haya env vars, plan vacío no acredita.
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100")
        monkeypatch.setenv("STRIPE_CREDITOS_PRO", "500")
        assert creditos_de_plan("") is None

    def test_plan_none_safe(self, monkeypatch):
        # type: ignore[arg-type] — el caller podría pasarnos None por error
        assert creditos_de_plan(None) is None  # type: ignore[arg-type]

    def test_plan_random_retorna_none(self, monkeypatch):
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100")
        monkeypatch.setenv("STRIPE_CREDITOS_PRO", "500")
        assert creditos_de_plan("enterprise") is None
        assert creditos_de_plan("unknown") is None
        assert creditos_de_plan("starter") is None


# ── Env var faltante en PRODUCCIÓN ──────────────────────────────────────────


class TestProduccionSinEnv:
    def test_production_premium_sin_env_retorna_none(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("STRIPE_CREDITOS_PREMIUM", raising=False)
        assert creditos_de_plan("premium") is None

    def test_production_pro_sin_env_retorna_none(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("STRIPE_CREDITOS_PRO", raising=False)
        assert creditos_de_plan("pro") is None

    def test_production_premium_con_whitespace_retorna_none(self, monkeypatch):
        """Strings con solo whitespace cuentan como vacío (.strip())."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "   ")
        assert creditos_de_plan("premium") is None

    def test_production_loguea_error_visible(self, monkeypatch, caplog):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("STRIPE_CREDITOS_PREMIUM", raising=False)
        import logging
        with caplog.at_level(logging.ERROR, logger="dona"):
            creditos_de_plan("premium")
        assert any(
            "STRIPE_CREDITOS_PREMIUM" in rec.message and "estricto" in rec.message
            for rec in caplog.records
        )


# ── Env var faltante en DEV/TEST ────────────────────────────────────────────


class TestDevSinEnv:
    def test_dev_premium_sin_env_devuelve_default(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("STRIPE_CREDITOS_PREMIUM", raising=False)
        assert creditos_de_plan("premium") == 100

    def test_dev_pro_sin_env_devuelve_default(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("STRIPE_CREDITOS_PRO", raising=False)
        assert creditos_de_plan("pro") == 500

    def test_test_environment_tambien_devuelve_default(self, monkeypatch):
        """ENVIRONMENT=test (default de conftest.py) tambien usa fallback."""
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.delenv("STRIPE_CREDITOS_PREMIUM", raising=False)
        assert creditos_de_plan("premium") == 100

    def test_dev_loguea_warning_no_error(self, monkeypatch, caplog):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("STRIPE_CREDITOS_PREMIUM", raising=False)
        import logging
        with caplog.at_level(logging.WARNING, logger="dona"):
            creditos_de_plan("premium")
        assert any(
            "STRIPE_CREDITOS_PREMIUM" in rec.message
            and rec.levelno == logging.WARNING
            for rec in caplog.records
        )


# ── Env var con valor invalido ─────────────────────────────────────────────


class TestEnvValorInvalido:
    def test_no_entero_retorna_none(self, monkeypatch):
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "no_es_un_numero")
        assert creditos_de_plan("premium") is None

    def test_entero_negativo_retorna_none(self, monkeypatch):
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "-50")
        assert creditos_de_plan("premium") is None

    def test_cero_retorna_none(self, monkeypatch):
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "0")
        assert creditos_de_plan("premium") is None

    def test_decimal_retorna_none(self, monkeypatch):
        """int("100.5") falla; queremos solo enteros."""
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "100.5")
        assert creditos_de_plan("premium") is None

    def test_valor_invalido_loguea_error(self, monkeypatch, caplog):
        monkeypatch.setenv("STRIPE_CREDITOS_PREMIUM", "not_an_int")
        import logging
        with caplog.at_level(logging.ERROR, logger="dona"):
            creditos_de_plan("premium")
        assert any(
            "STRIPE_CREDITOS_PREMIUM" in rec.message
            for rec in caplog.records
        )
