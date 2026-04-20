# tests/test_inbound_tokens.py — Tests para tokens HMAC de webhook inbound

"""
Verifica generación y verificación timing-safe de tokens del webhook inbound
(Zapier/Make/n8n).
"""

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
