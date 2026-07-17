# tests/test_email_crypto.py — PR 1 · Cifrado estricto del payload de correo

import importlib
import json

import pytest
from cryptography.fernet import Fernet

from agent.automation import email_crypto
from agent.automation.email_crypto import (
    ENVELOPE_PURGADO,
    EmailCryptoNoDisponibleError,
    EmailEnvelopeInvalidoError,
    EmailPayloadIndescifrableError,
    EmailPayloadPurgadoError,
)

PAYLOAD = {
    "destinatario": "cliente@ejemplo.com",
    "asunto": "Propuesta comercial",
    "cuerpo": "Hola, te comparto la propuesta acordada.",
    "thread_id": "",
    "reply_message_id": "",
}


@pytest.fixture
def con_clave(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("EMAIL_CRYPTO_PERMITIR_PLAINTEXT", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")


class TestRoundTrip:
    def test_round_trip_fernet(self, con_clave):
        envelope = email_crypto.cifrar_payload_email(PAYLOAD)
        assert email_crypto.descifrar_payload_email(envelope) == PAYLOAD

    def test_envelope_tiene_forma_esperada(self, con_clave):
        envelope = json.loads(email_crypto.cifrar_payload_email(PAYLOAD))
        assert envelope["v"] == 1
        assert envelope["alg"] == "fernet"
        assert envelope["ct"]
        assert envelope["fingerprint"] == email_crypto.calcular_fingerprint(PAYLOAD)
        assert envelope["longitud_cuerpo"] == len(PAYLOAD["cuerpo"])
        assert envelope["tiene_thread"] is False

    def test_envelope_no_contiene_plaintext(self, con_clave):
        envelope = email_crypto.cifrar_payload_email(PAYLOAD)
        assert "cliente@ejemplo.com" not in envelope
        assert "Propuesta comercial" not in envelope
        assert "propuesta acordada" not in envelope

    def test_tiene_thread_true(self, con_clave):
        payload = dict(PAYLOAD, thread_id="t-123", reply_message_id="<m@id>")
        envelope = json.loads(email_crypto.cifrar_payload_email(payload))
        assert envelope["tiene_thread"] is True
        assert email_crypto.descifrar_payload_email(json.dumps(envelope)) == payload


class TestErroresTipados:
    def test_ciphertext_corrupto(self, con_clave):
        envelope = json.loads(email_crypto.cifrar_payload_email(PAYLOAD))
        envelope["ct"] = envelope["ct"][:-4] + "XXXX"
        with pytest.raises(EmailPayloadIndescifrableError):
            email_crypto.descifrar_payload_email(json.dumps(envelope))

    def test_ciphertext_corrupto_no_se_reinterpreta_como_plaintext(self, con_clave):
        # Fail-closed: jamás el comportamiento de agent.crypto.descifrar
        # (devolver el valor original ante error).
        envelope = json.loads(email_crypto.cifrar_payload_email(PAYLOAD))
        envelope["ct"] = "no-es-fernet"
        with pytest.raises(EmailPayloadIndescifrableError):
            email_crypto.descifrar_payload_email(json.dumps(envelope))

    def test_version_desconocida(self, con_clave):
        envelope = json.loads(email_crypto.cifrar_payload_email(PAYLOAD))
        envelope["v"] = 2
        with pytest.raises(EmailEnvelopeInvalidoError):
            email_crypto.descifrar_payload_email(json.dumps(envelope))

    def test_algoritmo_desconocido(self, con_clave):
        envelope = json.loads(email_crypto.cifrar_payload_email(PAYLOAD))
        envelope["alg"] = "rot13"
        with pytest.raises(EmailEnvelopeInvalidoError):
            email_crypto.descifrar_payload_email(json.dumps(envelope))

    def test_envelope_no_json(self, con_clave):
        with pytest.raises(EmailEnvelopeInvalidoError):
            email_crypto.descifrar_payload_email("esto no es json")

    def test_fingerprint_no_corresponde(self, con_clave):
        envelope = json.loads(email_crypto.cifrar_payload_email(PAYLOAD))
        envelope["fingerprint"] = "0" * 64
        with pytest.raises(EmailPayloadIndescifrableError):
            email_crypto.descifrar_payload_email(json.dumps(envelope))

    def test_purged(self, con_clave):
        assert email_crypto.es_envelope_purgado(ENVELOPE_PURGADO)
        with pytest.raises(EmailPayloadPurgadoError):
            email_crypto.descifrar_payload_email(ENVELOPE_PURGADO)


class TestPlaintextControlado:
    def test_envelope_plano_sin_autorizacion(self, con_clave):
        # Aunque el entorno es test, SIN la flag el envelope plano se rechaza.
        envelope = {
            "v": 1,
            "alg": "plaintext",
            "payload": dict(PAYLOAD),
            "fingerprint": email_crypto.calcular_fingerprint(PAYLOAD),
            "longitud_cuerpo": len(PAYLOAD["cuerpo"]),
            "tiene_thread": False,
        }
        with pytest.raises(EmailEnvelopeInvalidoError):
            email_crypto.descifrar_payload_email(json.dumps(envelope))

    def test_plaintext_con_flag_y_entorno_permisivo(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("EMAIL_CRYPTO_PERMITIR_PLAINTEXT", "true")
        monkeypatch.setenv("ENVIRONMENT", "test")
        envelope = email_crypto.cifrar_payload_email(PAYLOAD)
        assert json.loads(envelope)["alg"] == "plaintext"
        assert email_crypto.descifrar_payload_email(envelope) == PAYLOAD

    def test_plaintext_bloqueado_en_entorno_estricto(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("EMAIL_CRYPTO_PERMITIR_PLAINTEXT", "true")
        monkeypatch.setenv("ENVIRONMENT", "production")
        with pytest.raises(EmailCryptoNoDisponibleError):
            email_crypto.cifrar_payload_email(PAYLOAD)

    def test_plaintext_bloqueado_con_entorno_desconocido(self, monkeypatch):
        # Fail-closed del helper de entorno: valor raro == estricto.
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("EMAIL_CRYPTO_PERMITIR_PLAINTEXT", "true")
        monkeypatch.setenv("ENVIRONMENT", "staging")
        with pytest.raises(EmailCryptoNoDisponibleError):
            email_crypto.cifrar_payload_email(PAYLOAD)


class TestSinClave:
    def test_sin_key_cifrar_falla_cerrado(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("EMAIL_CRYPTO_PERMITIR_PLAINTEXT", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "test")
        with pytest.raises(EmailCryptoNoDisponibleError):
            email_crypto.cifrar_payload_email(PAYLOAD)

    def test_sin_key_descifrar_fernet_falla_cerrado(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        monkeypatch.setenv("ENVIRONMENT", "test")
        envelope = email_crypto.cifrar_payload_email(PAYLOAD)
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        with pytest.raises(EmailCryptoNoDisponibleError):
            email_crypto.descifrar_payload_email(envelope)

    def test_clave_invalida_es_como_ausente(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", "no-es-una-clave-fernet")
        monkeypatch.delenv("EMAIL_CRYPTO_PERMITIR_PLAINTEXT", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "test")
        assert not email_crypto.crypto_email_disponible()
        with pytest.raises(EmailCryptoNoDisponibleError):
            email_crypto.cifrar_payload_email(PAYLOAD)


class TestOAuthLegacyIntacto:
    def test_agent_crypto_sigue_fail_open_para_tokens(self, monkeypatch):
        """El comportamiento legacy de agent.crypto (OAuth) NO cambia:
        cifra/descifra con la misma ENCRYPTION_KEY y su descifrar sigue
        siendo tolerante con valores plaintext legacy."""
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        monkeypatch.setenv("ENVIRONMENT", "test")
        import agent.crypto as _crypto
        importlib.reload(_crypto)
        try:
            token = "ya29.token-de-prueba"
            cifrado = _crypto.cifrar(token)
            assert cifrado != token
            assert _crypto.descifrar(cifrado) == token
            # fail-open legacy intacto (solo para OAuth, no para email)
            assert _crypto.descifrar("valor-plano-legacy") == "valor-plano-legacy"
        finally:
            importlib.reload(_crypto)
