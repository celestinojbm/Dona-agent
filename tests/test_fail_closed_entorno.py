# tests/test_fail_closed_entorno.py — Fase 0 · fail-closed por defecto (C8)

"""
REGRESIÓN C8 del audit de readiness (2026-06-09): los controles de seguridad
se activaban solo con ``ENVIRONMENT == "production"`` exacto. Un typo ("prod",
"Production "), la variable ausente o un valor nuevo (staging) desactivaban EN
SILENCIO la verificación de firmas (Stripe/Meta/Whapi), el cifrado de tokens,
los secrets de inbound/bridge y el state de OAuth.

Estos tests fijan la inversión: SOLO ``development``/``test`` explícitos
habilitan paths permisivos; todo lo demás es estricto (fail-closed).
"""

import json
from unittest.mock import MagicMock

import pytest

from agent.entorno import es_entorno_estricto, es_entorno_permisivo


# ── Helper único ─────────────────────────────────────────────────────────────

class TestHelperEntorno:
    @pytest.mark.parametrize("valor", [
        "production", "prod", "Production ", "PRODUCTION", "staging",
        "produccion", "", "   ",
    ])
    def test_valores_no_dev_son_estrictos(self, monkeypatch, valor):
        monkeypatch.setenv("ENVIRONMENT", valor)
        assert es_entorno_estricto() is True
        assert es_entorno_permisivo() is False

    def test_variable_ausente_es_estricto(self, monkeypatch):
        """El caso más peligroso del fail-open: ENVIRONMENT sin configurar."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        assert es_entorno_estricto() is True

    @pytest.mark.parametrize("valor", [
        "development", "test", "DEVELOPMENT", " test ", "Test",
    ])
    def test_dev_y_test_explicitos_son_permisivos(self, monkeypatch, valor):
        monkeypatch.setenv("ENVIRONMENT", valor)
        assert es_entorno_permisivo() is True


# ── Stripe (billing) ─────────────────────────────────────────────────────────

class TestStripeFailClosed:
    def test_typo_de_entorno_rechaza_webhook_sin_secret(self, monkeypatch):
        """REGRESIÓN C8: con ENVIRONMENT="prod" (typo) y sin secret, ANTES se
        aceptaba el payload sin verificar (path 'dev'). Ahora se rechaza."""
        from agent.billing import verificar_firma_stripe
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        payload = json.dumps({"type": "checkout.session.completed"}).encode()
        assert verificar_firma_stripe(payload, "") is None

    def test_dev_explicito_sigue_permisivo(self, monkeypatch):
        from agent.billing import verificar_firma_stripe
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        payload = json.dumps({"type": "checkout.session.completed"}).encode()
        evento = verificar_firma_stripe(payload, "")
        assert evento == {"type": "checkout.session.completed"}

    def test_check_startup_aborta_en_entorno_estricto_sin_secret(self, monkeypatch):
        from agent.billing import _check_stripe_webhook_secret
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
            _check_stripe_webhook_secret()

    def test_creditos_de_plan_sin_env_var_no_acredita_en_estricto(self, monkeypatch):
        from agent.billing import creditos_de_plan, _ENV_VAR_POR_PLAN
        plan = next(iter(_ENV_VAR_POR_PLAN))
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.delenv(_ENV_VAR_POR_PLAN[plan], raising=False)
        assert creditos_de_plan(plan) is None


# ── Crypto (cifrado de tokens OAuth) ─────────────────────────────────────────

class TestCryptoFailClosed:
    def test_sin_key_en_entorno_desconocido_aborta(self, monkeypatch):
        """REGRESIÓN C8: ANTES, sin ENCRYPTION_KEY y ENVIRONMENT="staging", el
        módulo degradaba a texto plano con solo un warning. Ahora aborta."""
        from agent.crypto import _inicializar_fernet
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
            _inicializar_fernet()

    def test_key_invalida_en_entorno_estricto_aborta(self, monkeypatch):
        from agent.crypto import _inicializar_fernet
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.setenv("ENCRYPTION_KEY", "no-es-una-clave-fernet")
        with pytest.raises(RuntimeError, match="inválida"):
            _inicializar_fernet()

    def test_dev_explicito_degrada_con_warning(self, monkeypatch):
        from agent.crypto import _inicializar_fernet
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        assert _inicializar_fernet() is None  # texto plano, solo dev


# ── Inbound tokens ───────────────────────────────────────────────────────────

class TestInboundFailClosed:
    def test_secreto_sin_env_var_aborta_en_estricto(self, monkeypatch):
        from agent.inbound_tokens import _secreto
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="INBOUND_WEBHOOK_SECRET"):
            _secreto()

    def test_check_startup_aborta_en_estricto(self, monkeypatch):
        from agent.inbound_tokens import _check_inbound_secret
        monkeypatch.setenv("ENVIRONMENT", "Production ")  # typo con espacio
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="INBOUND_WEBHOOK_SECRET"):
            _check_inbound_secret()

    def test_dev_explicito_usa_fallback(self, monkeypatch):
        from agent.inbound_tokens import _secreto
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        assert isinstance(_secreto(), bytes)


# ── Providers (Meta y Whapi) ─────────────────────────────────────────────────

class TestProvidersFailClosed:
    def test_meta_typo_de_entorno_rechaza_webhook_sin_secret(self, monkeypatch):
        """REGRESIÓN C8: ANTES, app_secret vacío + ENVIRONMENT="prod" (typo)
        aceptaba el payload sin verificar. Ahora rechaza."""
        from agent.providers.meta import ProveedorMeta
        p = ProveedorMeta.__new__(ProveedorMeta)  # sin __init__: solo el método
        p.app_secret = ""
        monkeypatch.setenv("ENVIRONMENT", "prod")
        assert p._verificar_firma(b"{}", "") is False

    def test_meta_dev_explicito_sigue_permisivo(self, monkeypatch):
        from agent.providers.meta import ProveedorMeta
        p = ProveedorMeta.__new__(ProveedorMeta)
        p.app_secret = ""
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert p._verificar_firma(b"{}", "") is True

    def test_whapi_typo_de_entorno_rechaza_webhook_sin_token(self, monkeypatch):
        from agent.providers.whapi import ProveedorWhapi
        p = ProveedorWhapi.__new__(ProveedorWhapi)
        p.webhook_token = ""
        monkeypatch.setenv("ENVIRONMENT", "prod")
        assert p._verificar_firma(None) is False

    def test_whapi_dev_explicito_sigue_permisivo(self, monkeypatch):
        from agent.providers.whapi import ProveedorWhapi
        p = ProveedorWhapi.__new__(ProveedorWhapi)
        p.webhook_token = ""
        monkeypatch.setenv("ENVIRONMENT", "test")
        assert p._verificar_firma(None) is True


# ── OAuth state (google_calendar) ────────────────────────────────────────────

class TestOAuthStateFailClosed:
    def test_state_secret_aborta_en_entorno_desconocido(self, monkeypatch):
        import agent.google_calendar as gc
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(gc, "GOOGLE_CLIENT_SECRET", "")
        with pytest.raises(RuntimeError, match="OAUTH_STATE_SECRET"):
            gc._resolver_state_secret()


# ── Bridge interno (main + dashboard_lockout) ────────────────────────────────

class TestBridgeFailClosed:
    def test_check_internal_bridge_aborta_en_estricto(self, monkeypatch):
        from agent.main import _check_internal_bridge_secret
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.delenv("INTERNAL_BRIDGE_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="INTERNAL_BRIDGE_SECRET"):
            _check_internal_bridge_secret()

    def test_hash_email_sin_secret_aborta_en_estricto(self, monkeypatch):
        """REGRESIÓN C8: ANTES, sin INTERNAL_BRIDGE_SECRET el hash de email se
        computaba con clave vacía (enumerable por cualquiera). Ahora aborta."""
        from agent.dashboard_lockout import _hash_email
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.delenv("INTERNAL_BRIDGE_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="INTERNAL_BRIDGE_SECRET"):
            _hash_email("a@test.com")

    def test_hash_email_con_secret_funciona(self, monkeypatch):
        from agent.dashboard_lockout import _hash_email
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", "secreto-real")
        h = _hash_email("a@test.com")
        assert len(h) == 64
        # Determinístico y normalizado
        assert h == _hash_email("  A@TEST.com ")


# ── Superficie de diagnóstico (logging y /debug) ─────────────────────────────

class TestSuperficieDiagnosticoFailClosed:
    def test_logging_typo_de_entorno_activa_modo_produccion(self, monkeypatch):
        """REGRESIÓN C8: con ENVIRONMENT="prod" (typo), ANTES el logging quedaba
        en modo dev (DEBUG, sin redaction de PII). Ahora entra en modo
        producción (INFO + JSON + redaction)."""
        import logging as _logging
        from agent.logging_config import configurar_logging
        root = _logging.getLogger()
        nivel_orig, handlers_orig = root.level, list(root.handlers)
        try:
            monkeypatch.setenv("ENVIRONMENT", "prod")
            monkeypatch.delenv("LOG_LEVEL", raising=False)
            configurar_logging()
            assert root.level == _logging.INFO  # producción; en dev sería DEBUG
        finally:
            root.setLevel(nivel_orig)
            root.handlers[:] = handlers_orig

    @pytest.mark.asyncio
    async def test_debug_endpoint_404_en_entorno_estricto(self, monkeypatch):
        """REGRESIÓN C8: /debug (ecoa bodies/headers crudos, incluidos tokens)
        quedaba ACTIVO con un typo de entorno. Ahora responde 404 en todo
        entorno estricto, evaluado por request."""
        from fastapi import HTTPException
        from agent.main import debug_handler
        monkeypatch.setenv("ENVIRONMENT", "prod")
        with pytest.raises(HTTPException) as exc:
            await debug_handler(MagicMock())
        assert exc.value.status_code == 404
