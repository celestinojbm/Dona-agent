# tests/test_inbound_tokens.py — Tests para tokens HMAC de webhook inbound

"""
Verifica generación y verificación timing-safe de tokens del webhook inbound
(Zapier/Make/n8n).
"""

import hashlib
import hmac

import pytest
from agent import inbound_tokens


@pytest.fixture(autouse=True)
def _secreto_fijo(monkeypatch):
    """Fija un secreto determinístico para los tests."""
    monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "test-secret-xyz")


class TestInboundTokens:
    def test_roundtrip(self):
        tok = inbound_tokens.generar_token("14076936023")
        assert inbound_tokens.verificar_token(tok) == "14076936023"

    def test_formato_contiene_firma(self):
        tok = inbound_tokens.generar_token("14076936023")
        assert "." in tok
        payload_b64, firma = tok.split(".", 1)
        assert len(firma) == 64  # HMAC-SHA256 hex
        assert all(c in "0123456789abcdef" for c in firma)

    def test_firma_manipulada_rechaza(self):
        tok = inbound_tokens.generar_token("14076936023")
        payload_b64, _ = tok.split(".", 1)
        tok_malo = f"{payload_b64}.{'0' * 64}"
        assert inbound_tokens.verificar_token(tok_malo) is None

    def test_payload_manipulado_rechaza(self):
        tok = inbound_tokens.generar_token("14076936023")
        _, firma = tok.split(".", 1)
        # Mismo formato pero otro teléfono, firma original → no valida
        payload_malo = inbound_tokens._b64u(b"xxxx|9999999999")
        assert inbound_tokens.verificar_token(f"{payload_malo}.{firma}") is None

    def test_formato_invalido_rechaza(self):
        assert inbound_tokens.verificar_token("") is None
        assert inbound_tokens.verificar_token("no-tiene-punto") is None
        assert inbound_tokens.verificar_token(".") is None
        assert inbound_tokens.verificar_token("basura.masbasura") is None

    def test_telefono_vacio_no_permitido(self):
        with pytest.raises(ValueError):
            inbound_tokens.generar_token("")

    def test_dos_tokens_del_mismo_telefono_son_distintos(self):
        """El nonce aleatorio hace cada token único, así se pueden revocar individualmente."""
        t1 = inbound_tokens.generar_token("14076936023")
        t2 = inbound_tokens.generar_token("14076936023")
        assert t1 != t2

    def test_rotar_secreto_invalida_tokens(self, monkeypatch):
        tok = inbound_tokens.generar_token("14076936023")
        assert inbound_tokens.verificar_token(tok) == "14076936023"
        # Simular rotación del secreto
        monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "otro-secreto")
        assert inbound_tokens.verificar_token(tok) is None


class TestSecretoProduction:
    """T0.4: el módulo no debe arrancar en producción sin INBOUND_WEBHOOK_SECRET.

    Patrón idéntico a TestVerificarFirmaProduction de tests/test_billing.py:
    el check al import-time aborta el deploy si falta el secret; el `_secreto()`
    también rechaza en producción como defensa en profundidad.
    """

    def test_production_sin_secret_levanta_runtime_error_al_reload(self, monkeypatch):
        """Al import-time: si production sin secret, RuntimeError aborta el deploy."""
        import importlib
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        try:
            with pytest.raises(RuntimeError, match="INBOUND_WEBHOOK_SECRET"):
                importlib.reload(inbound_tokens)
        finally:
            # Restaurar el módulo en estado limpio para tests posteriores.
            monkeypatch.setenv("ENVIRONMENT", "test")
            monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "test-secret-xyz")
            importlib.reload(inbound_tokens)

    def test_production_secret_solo_whitespace_levanta(self, monkeypatch):
        """Strings con solo whitespace cuentan como vacío (.strip() en el check)."""
        import importlib
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "   ")
        try:
            with pytest.raises(RuntimeError, match="INBOUND_WEBHOOK_SECRET"):
                importlib.reload(inbound_tokens)
        finally:
            monkeypatch.setenv("ENVIRONMENT", "test")
            monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "test-secret-xyz")
            importlib.reload(inbound_tokens)

    def test_production_runtime_sin_secret_levanta_en_secreto(self, monkeypatch):
        """Defensa en profundidad: si el secret desaparece después del import,
        _secreto() rechaza con RuntimeError en lugar de caer a fallback."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="INBOUND_WEBHOOK_SECRET"):
            inbound_tokens._secreto()

    def test_production_con_secret_no_levanta_al_reload(self, monkeypatch):
        """Con secret configurado, el import en production no aborta."""
        import importlib
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "production_secret_dummy")
        try:
            importlib.reload(inbound_tokens)  # No debe levantar.
            # _secreto() retorna los bytes correctos.
            assert inbound_tokens._secreto() == b"production_secret_dummy"
        finally:
            monkeypatch.setenv("ENVIRONMENT", "test")
            monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "test-secret-xyz")
            importlib.reload(inbound_tokens)

    def test_production_no_cae_a_admin_token_derivado(self, monkeypatch):
        """En production, ADMIN_TOKEN seteado NO debe activar el fallback derivado."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("ADMIN_TOKEN", "admin_token_dummy")
        # _secreto() debe levantar RuntimeError en producción aunque ADMIN_TOKEN exista.
        with pytest.raises(RuntimeError, match="INBOUND_WEBHOOK_SECRET"):
            inbound_tokens._secreto()


class TestSecretoFallbackDevTest:
    """Fallbacks inseguros de `_secreto()` — SOLO válidos en dev/test permisivo.

    Fija el comportamiento actual: sin `INBOUND_WEBHOOK_SECRET`, en entorno
    permisivo (ENVIRONMENT=test/development), `_secreto()` deriva de
    `ADMIN_TOKEN` si existe, y si no, cae a un literal de desarrollo. Ambos
    paths van con warning y NUNCA se ejecutan en producción (ver
    TestSecretoProduction). No prueban seguridad, sino que el fallback local
    sea determinístico y no rompa el arranque en dev/test.
    """

    def test_dev_deriva_secreto_de_admin_token(self, monkeypatch):
        """Sin INBOUND_WEBHOOK_SECRET pero con ADMIN_TOKEN → deriva por SHA-256."""
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("ADMIN_TOKEN", "admin-local-xyz")
        esperado = hashlib.sha256(
            b"inbound-webhook-derived|" + b"admin-local-xyz"
        ).digest()
        assert inbound_tokens._secreto() == esperado

    def test_dev_admin_token_solo_whitespace_cae_a_literal(self, monkeypatch):
        """ADMIN_TOKEN con solo espacios cuenta como vacío (.strip()) → literal dev."""
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("ADMIN_TOKEN", "   ")
        assert (
            inbound_tokens._secreto()
            == b"dona-inbound-dev-secret-do-not-use-in-prod"
        )

    def test_dev_sin_admin_token_cae_a_literal(self, monkeypatch):
        """Sin INBOUND_WEBHOOK_SECRET ni ADMIN_TOKEN → literal de desarrollo."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        assert (
            inbound_tokens._secreto()
            == b"dona-inbound-dev-secret-do-not-use-in-prod"
        )

    def test_token_generado_con_fallback_admin_es_verificable(self, monkeypatch):
        """El roundtrip funciona bajo el fallback derivado de ADMIN_TOKEN."""
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("ADMIN_TOKEN", "admin-local-xyz")
        tok = inbound_tokens.generar_token("14076936023")
        assert inbound_tokens.verificar_token(tok) == "14076936023"


class TestVerificarTokenBordes:
    """Ramas de rechazo de `verificar_token()` con firma VÁLIDA pero payload roto.

    Estos casos pasan la comparación HMAC (firma correcta) y ejercen la
    validación posterior del payload, que las pruebas de firma manipulada no
    alcanzan.
    """

    @pytest.fixture(autouse=True)
    def _secreto_fijo(self, monkeypatch):
        monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "test-secret-xyz")

    def _firmar(self, payload: bytes) -> str:
        """Construye un token con firma válida para un payload arbitrario."""
        firma = hmac.new(
            inbound_tokens._secreto(), payload, hashlib.sha256
        ).hexdigest()
        return f"{inbound_tokens._b64u(payload)}.{firma}"

    def test_payload_sin_separador_pipe_rechaza(self):
        """Firma válida pero payload sin '|' → None (len(partes) != 2)."""
        tok = self._firmar(b"no-tiene-separador")
        assert inbound_tokens.verificar_token(tok) is None

    def test_payload_con_telefono_vacio_rechaza(self):
        """Firma válida, formato 'nonce|' con teléfono vacío → None."""
        tok = self._firmar(b"nonce123|")
        assert inbound_tokens.verificar_token(tok) is None

    def test_base64_invalido_en_payload_rechaza(self):
        """Payload que no es base64url decodificable → excepción capturada → None."""
        # '@' no pertenece al alfabeto base64url → binascii.Error en el decode.
        assert inbound_tokens.verificar_token("@@@@.deadbeef") is None

    def test_payload_no_utf8_rechaza(self):
        """Firma válida pero bytes no decodificables como UTF-8 → None."""
        tok = self._firmar(b"\xff\xfe|123")
        assert inbound_tokens.verificar_token(tok) is None
