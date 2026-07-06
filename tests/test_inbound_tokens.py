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


def _firmar_payload(payload: bytes) -> str:
    """Firma bytes de payload arbitrarios con el secreto actual del módulo y
    devuelve un token con el mismo formato que ``generar_token`` produce.

    Sirve para construir tokens con firma VÁLIDA pero payload fuera de las
    invariantes que ``generar_token`` garantiza (sin '|', bytes no-utf8),
    y así ejercitar las ramas defensivas de ``verificar_token``.
    """
    firma = hmac.new(inbound_tokens._secreto(), payload, hashlib.sha256).hexdigest()
    return f"{inbound_tokens._b64u(payload)}.{firma}"


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
    """Fija el comportamiento del fallback INSEGURO de ``_secreto()`` en entorno
    permisivo (dev/test), donde no hay ``INBOUND_WEBHOOK_SECRET`` configurado.

    Este path NUNCA corre en producción (lo garantiza el check de import-time y
    la defensa en profundidad ya cubiertos por ``TestSecretoProduction``), pero
    es el que hace correr las pruebas locales sin Zapier/Stripe. Lo cubrimos
    para que un cambio accidental en la derivación no pase inadvertido.
    """

    def test_deriva_de_admin_token_cuando_falta_secret(self, monkeypatch):
        """Sin INBOUND_WEBHOOK_SECRET pero con ADMIN_TOKEN → deriva por SHA-256."""
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("ADMIN_TOKEN", "admin-dev-123")
        esperado = hashlib.sha256(
            b"inbound-webhook-derived|" + b"admin-dev-123"
        ).digest()
        assert inbound_tokens._secreto() == esperado

    def test_admin_token_con_espacios_se_recorta(self, monkeypatch):
        """El ADMIN_TOKEN se normaliza con .strip() antes de derivar."""
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("ADMIN_TOKEN", "  admin-dev-123  ")
        esperado = hashlib.sha256(
            b"inbound-webhook-derived|" + b"admin-dev-123"
        ).digest()
        assert inbound_tokens._secreto() == esperado

    def test_literal_dev_cuando_falta_secret_y_admin_token(self, monkeypatch):
        """Sin INBOUND_WEBHOOK_SECRET ni ADMIN_TOKEN → literal de desarrollo."""
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        assert (
            inbound_tokens._secreto()
            == b"dona-inbound-dev-secret-do-not-use-in-prod"
        )

    def test_admin_token_solo_espacios_cae_al_literal(self, monkeypatch):
        """ADMIN_TOKEN de solo whitespace cuenta como vacío → literal dev."""
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("ADMIN_TOKEN", "   ")
        assert (
            inbound_tokens._secreto()
            == b"dona-inbound-dev-secret-do-not-use-in-prod"
        )

    def test_roundtrip_con_fallback_derivado(self, monkeypatch):
        """Con el fallback derivado de ADMIN_TOKEN, generar/verificar siguen
        siendo consistentes entre sí (mismo secreto en ambos extremos)."""
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.setenv("ADMIN_TOKEN", "admin-dev-123")
        tok = inbound_tokens.generar_token("14076936023")
        assert inbound_tokens.verificar_token(tok) == "14076936023"

    def test_roundtrip_con_fallback_literal(self, monkeypatch):
        """Con el fallback literal, generar/verificar siguen siendo consistentes."""
        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        tok = inbound_tokens.generar_token("14076936023")
        assert inbound_tokens.verificar_token(tok) == "14076936023"


class TestVerificarTokenBordes:
    """Ramas defensivas de ``verificar_token`` con firma VÁLIDA pero payload
    fuera de las invariantes de ``generar_token``."""

    def test_payload_firmado_sin_separador_rechaza(self):
        """Firma válida pero payload sin '|' → None (partes != 2)."""
        tok = _firmar_payload(b"sin-separador-alguno")
        assert inbound_tokens.verificar_token(tok) is None

    def test_payload_firmado_telefono_vacio_rechaza(self):
        """Firma válida, formato 'nonce|' con teléfono vacío → None."""
        tok = _firmar_payload(b"nonce-abc|")
        assert inbound_tokens.verificar_token(tok) is None

    def test_payload_firmado_bytes_no_utf8_rechaza(self):
        """Firma válida pero bytes no decodificables como utf-8 → None
        (se captura la excepción y se rechaza en vez de propagar)."""
        tok = _firmar_payload(b"\xff\xfe-no-utf8")
        assert inbound_tokens.verificar_token(tok) is None

    def test_base64_invalido_en_payload_rechaza(self):
        """Un payload_b64 que no decodifica lanza en _b64u_decode y se captura."""
        # Byte de padding mal colocado / carácter fuera del alfabeto urlsafe.
        assert inbound_tokens.verificar_token("========.deadbeef") is None
