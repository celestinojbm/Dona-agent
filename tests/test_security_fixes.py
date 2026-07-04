# tests/test_security_fixes.py — Tests para fixes de seguridad críticos

"""
Tests que verifican los fixes de las vulnerabilidades identificadas
en la auditoría de seguridad:

  - CRIT-1: ADMIN_TOKEN timing-safe
  - CRIT-2: OAuth state con nonce + firma HMAC
  - HIGH-7: Validación de formato E.164 en endpoints admin
  - MED-10: _es_owner timing-safe
"""

import os
import time
import hmac
import pytest
from unittest.mock import MagicMock

# agent.main requiere apscheduler (no disponible en ambiente local).
# Skipeamos tests que dependen de main si el import falla.
_main_disponible = True
try:
    from agent.main import _verificar_admin, _telefono_valido  # noqa: F401
except Exception:
    _main_disponible = False

_requiere_main = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler (no instalado en este entorno)",
)


# ── CRIT-2: OAuth state con firma HMAC ──────────────────────────────────────

class TestOAuthState:
    """Verifica protección CSRF en el parámetro state de OAuth."""

    def test_state_firmado_roundtrip(self):
        from agent.google_calendar import codificar_state, decodificar_state
        state = codificar_state("5215551234567")
        telefono = decodificar_state(state)
        assert telefono == "5215551234567"

    def test_state_contiene_firma(self):
        from agent.google_calendar import codificar_state
        state = codificar_state("5215551234567")
        # Formato: payload_b64.firma_hex
        assert "." in state
        payload, firma = state.split(".", 1)
        # firma HMAC-SHA256 → 64 hex chars
        assert len(firma) == 64
        assert all(c in "0123456789abcdef" for c in firma)

    def test_state_manipulado_rechaza(self):
        from agent.google_calendar import codificar_state, decodificar_state
        state = codificar_state("5215551234567")
        # Alterar la firma → debe fallar
        payload, firma = state.split(".", 1)
        firma_falsa = "0" * 64
        with pytest.raises(ValueError, match="Firma"):
            decodificar_state(f"{payload}.{firma_falsa}")

    def test_state_payload_manipulado_rechaza(self):
        from agent.google_calendar import codificar_state, decodificar_state
        import base64
        # Intentar inyectar otro teléfono manteniendo firma original
        state = codificar_state("5215551234567")
        payload, firma = state.split(".", 1)
        # Payload válido con otro teléfono pero firma original
        payload_malicioso = base64.urlsafe_b64encode(
            b"nonce|9999999999|5219999999999"
        ).decode().rstrip("=")
        with pytest.raises(ValueError):
            decodificar_state(f"{payload_malicioso}.{firma}")

    def test_state_expirado_rechaza(self):
        from agent.google_calendar import decodificar_state, _OAUTH_STATE_SECRET
        import base64
        import hashlib
        # Crear state con expiración en el pasado
        expirado_ts = int(time.time()) - 100
        payload = f"test_nonce|{expirado_ts}|5215551234567"
        firma = hmac.new(_OAUTH_STATE_SECRET, payload.encode(), hashlib.sha256).hexdigest()
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        with pytest.raises(ValueError, match="expirado"):
            decodificar_state(f"{payload_b64}.{firma}")

    def test_state_malformado_rechaza(self):
        from agent.google_calendar import decodificar_state
        with pytest.raises(ValueError):
            decodificar_state("esto-no-es-un-state-valido.xxx")

    def test_state_sin_firma_legacy_rechazado(self):
        """REGRESIÓN CSRF: un state legacy sin firma (solo base64 del teléfono,
        sin ".") DEBE rechazarse. Antes se aceptaba en 'modo degradado' y devolvía
        el teléfono, permitiendo account-linking forjado."""
        from agent.google_calendar import decodificar_state
        import base64
        state_forjado = base64.urlsafe_b64encode(b"5219999999999").decode().rstrip("=")
        assert "." not in state_forjado  # sin firma
        with pytest.raises(ValueError):
            decodificar_state(state_forjado)

    def test_state_secret_falla_rapido_en_prod(self, monkeypatch):
        """Sin secret real configurado, en producción debe abortar (RuntimeError)
        en vez de firmar con un fallback público falsificable."""
        import agent.google_calendar as gc
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(gc, "GOOGLE_CLIENT_SECRET", "")
        with pytest.raises(RuntimeError, match="producción"):
            gc._resolver_state_secret()


# ── HIGH-7: Validación E.164 ─────────────────────────────────────────────────

@_requiere_main
class TestTelefonoValido:
    """Verifica regex E.164 laxo para endpoints admin."""

    def test_acepta_formato_valido(self):
        from agent.main import _telefono_valido
        assert _telefono_valido("14076936023") is True
        assert _telefono_valido("+14076936023") is True
        assert _telefono_valido("5215551234567") is True

    def test_rechaza_no_numerico(self):
        from agent.main import _telefono_valido
        assert _telefono_valido("'; DROP TABLE--") is False
        assert _telefono_valido("abc123") is False
        assert _telefono_valido("1407-693-6023") is False

    def test_rechaza_vacio(self):
        from agent.main import _telefono_valido
        assert _telefono_valido("") is False

    def test_rechaza_muy_corto(self):
        from agent.main import _telefono_valido
        assert _telefono_valido("123") is False

    def test_rechaza_muy_largo(self):
        from agent.main import _telefono_valido
        assert _telefono_valido("1" * 20) is False


# ── CRIT-1: _verificar_admin timing-safe ─────────────────────────────────────

@_requiere_main
class TestVerificarAdmin:
    """Verifica uso de hmac.compare_digest en auth admin."""

    def _mock_request(self, auth_header: str = ""):
        req = MagicMock()
        req.headers = {"authorization": auth_header} if auth_header else {}
        return req

    def test_sin_token_configurado_rechaza(self, monkeypatch):
        from agent.main import _verificar_admin
        monkeypatch.setenv("ADMIN_TOKEN", "")
        assert _verificar_admin(self._mock_request("Bearer x")) is False

    def test_token_correcto_header_acepta(self, monkeypatch):
        from agent.main import _verificar_admin
        monkeypatch.setenv("ADMIN_TOKEN", "secreto123")
        assert _verificar_admin(self._mock_request("Bearer secreto123")) is True

    def test_token_incorrecto_header_rechaza(self, monkeypatch):
        from agent.main import _verificar_admin
        monkeypatch.setenv("ADMIN_TOKEN", "secreto123")
        assert _verificar_admin(self._mock_request("Bearer otro")) is False

    def test_query_string_ya_no_es_valido(self, monkeypatch):
        """SEC-AUTH-03: el fallback legacy de query param se eliminó — el
        token SOLO se acepta vía header Authorization: Bearer <token>.
        _verificar_admin ya no acepta un segundo argumento posicional."""
        from agent.main import _verificar_admin
        monkeypatch.setenv("ADMIN_TOKEN", "secreto123")
        with pytest.raises(TypeError):
            _verificar_admin(self._mock_request(), "secreto123")
        # Sin header (aunque el caller intentara pasar el token por query
        # string a nivel FastAPI, ya no llega a _verificar_admin): rechaza.
        assert _verificar_admin(self._mock_request()) is False

    def test_token_longitud_distinta_no_crashea(self, monkeypatch):
        """compare_digest con longitudes distintas no debe lanzar excepción."""
        from agent.main import _verificar_admin
        monkeypatch.setenv("ADMIN_TOKEN", "secreto123")
        # Token más corto
        assert _verificar_admin(self._mock_request("Bearer ab")) is False
        # Token más largo
        assert _verificar_admin(self._mock_request("Bearer " + "x" * 200)) is False


# ── TCPA: STOP/START handlers ────────────────────────────────────────────────

class TestTCPAOptOut:
    """Verifica opt-out TCPA (47 CFR 64.1200): respuesta inmediata a STOP/UNSUBSCRIBE."""

    def test_stop_basico(self):
        from agent.proactivity import es_comando_stop_tcpa
        assert es_comando_stop_tcpa("STOP") is True
        assert es_comando_stop_tcpa("stop") is True
        assert es_comando_stop_tcpa("Stop") is True
        assert es_comando_stop_tcpa("  STOP  ") is True
        assert es_comando_stop_tcpa("stop.") is True
        assert es_comando_stop_tcpa("STOP!") is True

    def test_stop_palabras_clave(self):
        from agent.proactivity import es_comando_stop_tcpa
        assert es_comando_stop_tcpa("UNSUBSCRIBE") is True
        assert es_comando_stop_tcpa("cancel") is True
        assert es_comando_stop_tcpa("end") is True
        assert es_comando_stop_tcpa("quit") is True
        assert es_comando_stop_tcpa("baja") is True

    def test_stop_no_matchea_dentro_de_texto(self):
        """STOP debe ser el texto completo, no parte de otra oración."""
        from agent.proactivity import es_comando_stop_tcpa
        assert es_comando_stop_tcpa("no me gusta, STOP por favor") is False
        assert es_comando_stop_tcpa("stoplight") is False
        assert es_comando_stop_tcpa("no stop ahora") is False

    def test_start_basico(self):
        from agent.proactivity import es_comando_start_tcpa
        assert es_comando_start_tcpa("START") is True
        assert es_comando_start_tcpa("start") is True
        assert es_comando_start_tcpa("subscribe") is True
        assert es_comando_start_tcpa("yes") is True
        assert es_comando_start_tcpa("alta") is True

    def test_stop_y_start_no_se_confunden(self):
        from agent.proactivity import es_comando_stop_tcpa, es_comando_start_tcpa
        assert not es_comando_stop_tcpa("start")
        assert not es_comando_start_tcpa("stop")


# ── Legal pages ──────────────────────────────────────────────────────────────

class TestLegalPages:
    """Verifica que Privacy Policy y ToS contienen secciones requeridas por CCPA/FTC."""

    def test_privacy_policy_contiene_ccpa(self):
        from agent.legal_pages import privacy_policy_html
        html = privacy_policy_html()
        assert "CCPA" in html or "California" in html
        assert "Derecho" in html or "derechos" in html.lower()
        assert "eliminar" in html.lower() or "borrar" in html.lower()

    def test_privacy_policy_menciona_ia(self):
        """FTC Section 5 requiere disclosure de IA."""
        from agent.legal_pages import privacy_policy_html
        html = privacy_policy_html()
        assert "inteligencia artificial" in html.lower() or "IA" in html

    def test_privacy_policy_menciona_subprocesores(self):
        from agent.legal_pages import privacy_policy_html
        html = privacy_policy_html()
        assert "Anthropic" in html
        assert "Claude" in html

    def test_privacy_policy_contiene_contacto(self):
        from agent.legal_pages import privacy_policy_html
        html = privacy_policy_html()
        assert "@" in html
        assert "mailto:" in html

    def test_terms_disclaimer_ia(self):
        from agent.legal_pages import terms_html
        html = terms_html()
        assert "IA" in html or "inteligencia artificial" in html.lower()
        assert "errores" in html.lower() or "alucinaci" in html.lower()

    def test_terms_limitacion_responsabilidad(self):
        from agent.legal_pages import terms_html
        html = terms_html()
        assert "responsabilidad" in html.lower()


# ── MED-10: _es_owner timing-safe ────────────────────────────────────────────

class TestEsOwner:
    """Verifica que _es_owner usa hmac.compare_digest."""

    def test_sin_owner_configurado_rechaza(self, monkeypatch):
        monkeypatch.setattr("enhanced.safe_module.OWNER_PHONE", "")
        from enhanced.safe_module import _es_owner
        assert _es_owner("14076936023") is False

    def test_owner_correcto_acepta(self, monkeypatch):
        monkeypatch.setattr("enhanced.safe_module.OWNER_PHONE", "14076936023")
        from enhanced.safe_module import _es_owner
        assert _es_owner("14076936023") is True
        # Con formato distinto pero mismos dígitos
        assert _es_owner("+1-407-693-6023") is True

    def test_no_owner_rechaza(self, monkeypatch):
        monkeypatch.setattr("enhanced.safe_module.OWNER_PHONE", "14076936023")
        from enhanced.safe_module import _es_owner
        assert _es_owner("15551234567") is False
