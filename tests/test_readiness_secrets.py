# tests/test_readiness_secrets.py — Fase 0 · 0.2 readiness check de secrets

"""
Pinea el contrato del readiness check de startup (agent/readiness.py):
en entorno estricto, secrets críticos faltantes abortan el arranque con la
lista COMPLETA de nombres (una sola iteración de deploy para arreglar todo);
en dev/test solo warning. Nunca se exponen valores.
"""

import pytest

from agent.readiness import (
    secrets_faltantes,
    verificar_secrets_criticos,
    _SECRETS_BASE,
)

_WHAPI = ("WHAPI_TOKEN", "WHAPI_WEBHOOK_TOKEN")
_META = ("META_ACCESS_TOKEN", "META_APP_SECRET", "META_WEBHOOK_VERIFY_TOKEN")


def _setear_todos(monkeypatch, provider="whapi"):
    monkeypatch.setenv("WHATSAPP_PROVIDER", provider)
    for n in _SECRETS_BASE:
        monkeypatch.setenv(n, "valor-de-prueba")
    extras = _WHAPI if provider == "whapi" else _META
    for n in extras:
        monkeypatch.setenv(n, "valor-de-prueba")


def _borrar(monkeypatch, *nombres):
    for n in nombres:
        monkeypatch.delenv(n, raising=False)


class TestEntornoEstricto:
    def test_faltantes_abortan_con_lista_completa(self, monkeypatch):
        """El error debe listar TODOS los faltantes, no solo el primero."""
        _setear_todos(monkeypatch)
        monkeypatch.setenv("ENVIRONMENT", "production")
        _borrar(monkeypatch, "STRIPE_WEBHOOK_SECRET", "ENCRYPTION_KEY", "ADMIN_TOKEN")
        with pytest.raises(RuntimeError) as exc:
            verificar_secrets_criticos()
        msg = str(exc.value)
        assert "STRIPE_WEBHOOK_SECRET" in msg
        assert "ENCRYPTION_KEY" in msg
        assert "ADMIN_TOKEN" in msg
        # Nunca valores.
        assert "valor-de-prueba" not in msg

    def test_typo_de_entorno_tambien_aborta(self, monkeypatch):
        """C8: 'prod' (typo) es estricto — el readiness check aplica igual."""
        _setear_todos(monkeypatch)
        monkeypatch.setenv("ENVIRONMENT", "prod")
        _borrar(monkeypatch, "DATABASE_URL")
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            verificar_secrets_criticos()

    def test_todo_presente_no_aborta(self, monkeypatch):
        _setear_todos(monkeypatch)
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert verificar_secrets_criticos() == []

    def test_whitespace_cuenta_como_faltante(self, monkeypatch):
        _setear_todos(monkeypatch)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ADMIN_TOKEN", "   ")
        with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
            verificar_secrets_criticos()


class TestDevPermisivo:
    def test_faltantes_solo_warnean(self, monkeypatch, caplog):
        import logging
        _setear_todos(monkeypatch)
        monkeypatch.setenv("ENVIRONMENT", "test")
        _borrar(monkeypatch, "STRIPE_WEBHOOK_SECRET")
        with caplog.at_level(logging.WARNING, logger="dona"):
            faltantes = verificar_secrets_criticos()  # no lanza
        assert faltantes == ["STRIPE_WEBHOOK_SECRET"]
        assert any("READINESS" in r.message for r in caplog.records)


class TestPorProvider:
    def test_provider_default_es_whapi_y_exige_sus_tokens(self, monkeypatch):
        """Misma resolución que el factory: sin WHATSAPP_PROVIDER → whapi."""
        _setear_todos(monkeypatch)
        monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
        _borrar(monkeypatch, "WHAPI_WEBHOOK_TOKEN")
        assert secrets_faltantes() == ["WHAPI_WEBHOOK_TOKEN"]

    def test_meta_exige_sus_secrets_y_no_los_de_whapi(self, monkeypatch):
        _setear_todos(monkeypatch, provider="meta")
        _borrar(monkeypatch, *_WHAPI)  # whapi ausente NO debe importar
        _borrar(monkeypatch, "META_APP_SECRET")
        assert secrets_faltantes() == ["META_APP_SECRET"]

    def test_provider_desconocido_solo_exige_base(self, monkeypatch):
        _setear_todos(monkeypatch, provider="twilio")
        _borrar(monkeypatch, *_WHAPI, *_META)
        assert secrets_faltantes() == []
