# tests/test_readiness_secrets.py — Fase 0 · 0.2 · readiness check de secrets

"""
Hermes (review de PR #70): "0.2 debe hacer que producción ni siquiera arranque
si le faltan precondiciones críticas... reportando todo lo que falta de una vez".

Estos tests fijan: en entorno estricto un secret faltante aborta el arranque;
se reportan TODOS los faltantes juntos; el secret exigido es el del proveedor
ACTIVO (no el de los otros); y dev/test explícitos no abortan.
"""

import pytest

from agent.readiness import (
    evaluar_readiness,
    verificar_readiness,
    ReadinessError,
    _SECRETS_REQUERIDOS,
)


# Set completo de secrets que dejan el readiness en verde (con provider=meta).
def _setear_todos(monkeypatch, proveedor="meta"):
    for var, _ in _SECRETS_REQUERIDOS:
        monkeypatch.setenv(var, f"valor-{var}")
    monkeypatch.setenv("WHATSAPP_PROVIDER", proveedor)
    secret_provider = {
        "meta": "META_APP_SECRET",
        "whapi": "WHAPI_WEBHOOK_TOKEN",
        "twilio": "TWILIO_AUTH_TOKEN",
    }[proveedor]
    monkeypatch.setenv(secret_provider, "valor-provider")


class TestReadinessEstricto:
    def test_todo_configurado_no_aborta(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        assert evaluar_readiness() == []
        verificar_readiness()  # no lanza

    def test_secret_faltante_aborta_en_estricto(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        with pytest.raises(ReadinessError, match="STRIPE_WEBHOOK_SECRET"):
            verificar_readiness()

    def test_typo_de_entorno_tambien_es_estricto(self, monkeypatch):
        """REGRESIÓN C8 + 0.2: con ENVIRONMENT="prod" (typo) la readiness debe
        exigir igual que en producción exacta."""
        monkeypatch.setenv("ENVIRONMENT", "prod")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        with pytest.raises(ReadinessError, match="ENCRYPTION_KEY"):
            verificar_readiness()

    def test_reporta_TODOS_los_faltantes_de_una_vez(self, monkeypatch):
        """El valor de 0.2 sobre los checks per-módulo: una sola corrida lista
        todo lo que falta, no de a uno por redeploy."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        problemas = evaluar_readiness()
        assert len(problemas) == 3
        joined = " ".join(problemas)
        assert "ENCRYPTION_KEY" in joined
        assert "ADMIN_TOKEN" in joined
        assert "INBOUND_WEBHOOK_SECRET" in joined
        with pytest.raises(ReadinessError, match="faltan 3 precondici"):
            verificar_readiness()

    def test_variable_de_entorno_ausente_es_estricto(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("INTERNAL_BRIDGE_SECRET", raising=False)
        with pytest.raises(ReadinessError, match="INTERNAL_BRIDGE_SECRET"):
            verificar_readiness()

    def test_database_url_es_requerido(self, monkeypatch):
        """Hermes (review #72): no arrancar 'vivo pero sin persistencia'."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ReadinessError, match="DATABASE_URL"):
            verificar_readiness()

    def test_dashboard_password_secret_es_requerido(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("DASHBOARD_PASSWORD_SECRET", raising=False)
        with pytest.raises(ReadinessError, match="DASHBOARD_PASSWORD_SECRET"):
            verificar_readiness()


class TestReadinessProveedorActivo:
    def test_solo_exige_el_secret_del_proveedor_activo(self, monkeypatch):
        """Con provider=meta, la ausencia de WHAPI_WEBHOOK_TOKEN/TWILIO no
        importa; solo META_APP_SECRET. (Es el caso real de producción.)"""
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("WHAPI_WEBHOOK_TOKEN", raising=False)
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        assert evaluar_readiness() == []

    def test_provider_meta_sin_su_secret_aborta(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("META_APP_SECRET", raising=False)
        problemas = evaluar_readiness()
        assert any("META_APP_SECRET" in p for p in problemas)

    def test_provider_whapi_exige_su_token(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "whapi")
        monkeypatch.delenv("WHAPI_WEBHOOK_TOKEN", raising=False)
        problemas = evaluar_readiness()
        assert any("WHAPI_WEBHOOK_TOKEN" in p for p in problemas)

    def test_provider_ausente_es_problema(self, monkeypatch):
        """Hermes (review #72): no adivinar el provider en estricto."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
        problemas = evaluar_readiness()
        assert any("WHATSAPP_PROVIDER" in p and "no configurado" in p for p in problemas)

    def test_provider_invalido_es_problema(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "meta")
        monkeypatch.setenv("WHATSAPP_PROVIDER", "telegram")
        problemas = evaluar_readiness()
        assert any("no soportado" in p for p in problemas)

    def test_provider_declarado_sin_modulo_es_problema(self, monkeypatch):
        """Fase 0 · TEMA 2: WHATSAPP_PROVIDER=twilio está declarado y su token
        existe, pero agent/providers/twilio.py NO existe. Antes readiness pasaba
        en verde y el web service reventaba en el primer webhook con
        ModuleNotFoundError. Ahora debe ser una alarma temprana en el arranque."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        _setear_todos(monkeypatch, "twilio")  # incluye TWILIO_AUTH_TOKEN
        problemas = evaluar_readiness()
        assert any("agent/providers/twilio.py" in p for p in problemas)
        with pytest.raises(ReadinessError, match="twilio.py"):
            verificar_readiness()


class TestReadinessPermisivo:
    @pytest.mark.parametrize("entorno", ["development", "test"])
    def test_dev_y_test_no_abortan_aunque_falte_todo(self, monkeypatch, entorno):
        monkeypatch.setenv("ENVIRONMENT", entorno)
        for var, _ in _SECRETS_REQUERIDOS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.delenv("META_APP_SECRET", raising=False)
        # No lanza: dev/test pueden arrancar sin secrets para pruebas locales.
        verificar_readiness()
