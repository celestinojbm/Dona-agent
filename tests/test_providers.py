# tests/test_providers.py — Tests para proveedores de WhatsApp

"""
Tests automatizados para el módulo de proveedores.
Cubre: validación Pydantic del webhook de Meta, parseo de mensajes,
envío de botones/listas, y verificación HMAC.
"""

import pytest
import json
import hmac
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

# ── Pydantic models ─────────────────────────────────────────────────────────

from agent.providers.meta import (
    MetaWebhookPayload,
    MetaMensaje,
    MetaMediaPayload,
    MetaValue,
    MetaChange,
    MetaEntry,
    ProveedorMeta,
)
from agent.providers.base import MensajeEntrante, BotonRespuesta, OpcionLista


# ── Fixtures ────────────────────────────────────────────────────────────────

def _make_meta_payload(messages: list[dict]) -> dict:
    """Genera un payload de webhook de Meta con mensajes dados."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": messages,
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def _make_text_msg(text: str, from_number: str = "5215551234567") -> dict:
    return {
        "from": from_number,
        "id": "wamid.abc123",
        "timestamp": "1700000000",
        "type": "text",
        "text": {"body": text},
    }


def _make_audio_msg(from_number: str = "5215551234567") -> dict:
    return {
        "from": from_number,
        "id": "wamid.audio1",
        "timestamp": "1700000000",
        "type": "audio",
        "audio": {"id": "audio_media_id", "mime_type": "audio/ogg; codecs=opus"},
    }


def _make_image_msg(from_number: str = "5215551234567") -> dict:
    return {
        "from": from_number,
        "id": "wamid.img1",
        "timestamp": "1700000000",
        "type": "image",
        "image": {"id": "image_media_id", "caption": "foto de producto"},
    }


def _make_document_msg(from_number: str = "5215551234567") -> dict:
    return {
        "from": from_number,
        "id": "wamid.doc1",
        "timestamp": "1700000000",
        "type": "document",
        "document": {"id": "doc_media_id", "filename": "reporte.pdf", "caption": ""},
    }


def _make_request(payload: dict, app_secret: str = "") -> AsyncMock:
    """Crea un mock de Request de FastAPI."""
    body_bytes = json.dumps(payload).encode()
    request = AsyncMock()
    request.body = AsyncMock(return_value=body_bytes)

    # Generar firma HMAC si hay secret
    if app_secret:
        sig = hmac.new(app_secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        request.headers = {"X-Hub-Signature-256": f"sha256={sig}"}
    else:
        request.headers = {}

    return request


# ── Tests de Pydantic models ───────────────────────────────────────────────

class TestPydanticModels:
    def test_payload_valido_texto(self):
        raw = _make_meta_payload([_make_text_msg("Hola Dona")])
        payload = MetaWebhookPayload.model_validate(raw)
        assert len(payload.entry) == 1
        assert len(payload.entry[0].changes) == 1
        msgs = payload.entry[0].changes[0].value.messages
        assert len(msgs) == 1
        assert msgs[0].from_number == "5215551234567"
        assert msgs[0].type == "text"
        assert msgs[0].text == {"body": "Hola Dona"}

    def test_payload_valido_audio(self):
        raw = _make_meta_payload([_make_audio_msg()])
        payload = MetaWebhookPayload.model_validate(raw)
        msg = payload.entry[0].changes[0].value.messages[0]
        assert msg.type == "audio"
        assert msg.audio is not None
        assert msg.audio.id == "audio_media_id"

    def test_payload_valido_imagen(self):
        raw = _make_meta_payload([_make_image_msg()])
        payload = MetaWebhookPayload.model_validate(raw)
        msg = payload.entry[0].changes[0].value.messages[0]
        assert msg.type == "image"
        assert msg.image.caption == "foto de producto"

    def test_payload_vacio(self):
        payload = MetaWebhookPayload.model_validate({"object": "whatsapp_business_account"})
        assert payload.entry == []

    def test_payload_sin_messages(self):
        raw = {"entry": [{"changes": [{"value": {}}]}]}
        payload = MetaWebhookPayload.model_validate(raw)
        assert payload.entry[0].changes[0].value.messages == []

    def test_multiple_mensajes(self):
        raw = _make_meta_payload([
            _make_text_msg("Hola"),
            _make_text_msg("Mundo"),
        ])
        payload = MetaWebhookPayload.model_validate(raw)
        msgs = payload.entry[0].changes[0].value.messages
        assert len(msgs) == 2


# ── Tests de parseo del webhook ─────────────────────────────────────────────

class TestParsearWebhook:
    @pytest.fixture
    def proveedor(self):
        with patch.dict("os.environ", {
            "META_ACCESS_TOKEN": "test_token",
            "META_PHONE_NUMBER_ID": "12345",
            "META_APP_SECRET": "",  # Sin verificación HMAC
        }):
            return ProveedorMeta()

    @pytest.mark.asyncio
    async def test_texto_simple(self, proveedor):
        payload = _make_meta_payload([_make_text_msg("Hola Dona")])
        request = _make_request(payload)
        mensajes = await proveedor.parsear_webhook(request)
        assert len(mensajes) == 1
        assert mensajes[0].texto == "Hola Dona"
        assert mensajes[0].telefono == "5215551234567"
        assert mensajes[0].es_propio is False

    @pytest.mark.asyncio
    async def test_audio(self, proveedor):
        payload = _make_meta_payload([_make_audio_msg()])
        request = _make_request(payload)
        mensajes = await proveedor.parsear_webhook(request)
        assert len(mensajes) == 1
        assert mensajes[0].audio_id == "audio_media_id"
        assert "ogg" in mensajes[0].audio_mime

    @pytest.mark.asyncio
    async def test_imagen(self, proveedor):
        payload = _make_meta_payload([_make_image_msg()])
        request = _make_request(payload)
        mensajes = await proveedor.parsear_webhook(request)
        assert len(mensajes) == 1
        assert mensajes[0].image_id == "image_media_id"
        assert mensajes[0].image_caption == "foto de producto"

    @pytest.mark.asyncio
    async def test_documento(self, proveedor):
        payload = _make_meta_payload([_make_document_msg()])
        request = _make_request(payload)
        mensajes = await proveedor.parsear_webhook(request)
        assert len(mensajes) == 1
        assert "reporte.pdf" in mensajes[0].texto

    @pytest.mark.asyncio
    async def test_payload_vacio(self, proveedor):
        payload = {"object": "whatsapp_business_account", "entry": []}
        request = _make_request(payload)
        mensajes = await proveedor.parsear_webhook(request)
        assert mensajes == []

    @pytest.mark.asyncio
    async def test_json_invalido(self, proveedor):
        request = AsyncMock()
        request.body = AsyncMock(return_value=b"not json{{{")
        request.headers = {}
        mensajes = await proveedor.parsear_webhook(request)
        assert mensajes == []

    @pytest.mark.asyncio
    async def test_tipo_ignorado(self, proveedor):
        msg = {"from": "521555", "id": "w1", "timestamp": "0", "type": "reaction"}
        payload = _make_meta_payload([msg])
        request = _make_request(payload)
        mensajes = await proveedor.parsear_webhook(request)
        assert mensajes == []


# ── Tests de verificación HMAC ──────────────────────────────────────────────

class TestVerificacionHMAC:
    def test_sin_secret_permite_todo(self):
        proveedor = ProveedorMeta()
        proveedor.app_secret = ""
        assert proveedor._verificar_firma(b"body", "") is True

    def test_firma_valida(self):
        proveedor = ProveedorMeta()
        proveedor.app_secret = "mi_secreto"
        body = b'{"test": true}'
        sig = hmac.new(b"mi_secreto", body, hashlib.sha256).hexdigest()
        assert proveedor._verificar_firma(body, f"sha256={sig}") is True

    def test_firma_invalida(self):
        proveedor = ProveedorMeta()
        proveedor.app_secret = "mi_secreto"
        assert proveedor._verificar_firma(b"body", "sha256=000000") is False

    def test_sin_header_firma(self):
        proveedor = ProveedorMeta()
        proveedor.app_secret = "mi_secreto"
        assert proveedor._verificar_firma(b"body", "") is False

    @pytest.mark.asyncio
    async def test_webhook_rechaza_firma_invalida(self):
        with patch.dict("os.environ", {
            "META_ACCESS_TOKEN": "t",
            "META_PHONE_NUMBER_ID": "1",
            "META_APP_SECRET": "secreto_real",
        }):
            proveedor = ProveedorMeta()
        payload = _make_meta_payload([_make_text_msg("hola")])
        request = _make_request(payload, app_secret="secreto_FALSO")
        mensajes = await proveedor.parsear_webhook(request)
        assert mensajes == []

    @pytest.mark.asyncio
    async def test_webhook_acepta_firma_valida(self):
        secret = "mi_app_secret"
        with patch.dict("os.environ", {
            "META_ACCESS_TOKEN": "t",
            "META_PHONE_NUMBER_ID": "1",
            "META_APP_SECRET": secret,
        }):
            proveedor = ProveedorMeta()
        payload = _make_meta_payload([_make_text_msg("hola")])
        request = _make_request(payload, app_secret=secret)
        mensajes = await proveedor.parsear_webhook(request)
        assert len(mensajes) == 1


# ── Tests de validación webhook GET ─────────────────────────────────────────

class TestValidarWebhook:
    @pytest.fixture
    def proveedor(self):
        with patch.dict("os.environ", {
            "META_WEBHOOK_VERIFY_TOKEN": "my_token",
        }):
            p = ProveedorMeta()
            p.verify_token = "my_token"
            return p

    @pytest.mark.asyncio
    async def test_verificacion_correcta(self, proveedor):
        request = MagicMock()
        request.query_params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "my_token",
            "hub.challenge": "12345",
        }
        result = await proveedor.validar_webhook(request)
        assert result == 12345

    @pytest.mark.asyncio
    async def test_token_incorrecto(self, proveedor):
        request = MagicMock()
        request.query_params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "12345",
        }
        result = await proveedor.validar_webhook(request)
        assert result is None


# ── Tests de base.py fallback ───────────────────────────────────────────────

class TestFallbackTexto:
    @pytest.mark.asyncio
    async def test_botones_fallback(self):
        """Fallback de botones debe enviar texto con opciones numeradas."""
        from agent.providers.base import ProveedorWhatsApp

        class FakeProveedor(ProveedorWhatsApp):
            async def parsear_webhook(self, request):
                return []
            async def enviar_mensaje(self, telefono, mensaje):
                self.ultimo_mensaje = mensaje
                return True

        p = FakeProveedor()
        botones = [BotonRespuesta(id="1", titulo="Opción A"), BotonRespuesta(id="2", titulo="Opción B")]
        result = await p.enviar_botones("521555", "Elige:", botones)
        assert result is True
        assert "1. Opción A" in p.ultimo_mensaje
        assert "2. Opción B" in p.ultimo_mensaje

    @pytest.mark.asyncio
    async def test_lista_fallback(self):
        """Fallback de lista debe enviar texto con bullets."""
        from agent.providers.base import ProveedorWhatsApp

        class FakeProveedor(ProveedorWhatsApp):
            async def parsear_webhook(self, request):
                return []
            async def enviar_mensaje(self, telefono, mensaje):
                self.ultimo_mensaje = mensaje
                return True

        p = FakeProveedor()
        opciones = [
            OpcionLista(id="a", titulo="Item A", descripcion="Desc A"),
            OpcionLista(id="b", titulo="Item B"),
        ]
        result = await p.enviar_lista("521555", "Menú:", "Ver", opciones)
        assert result is True
        assert "Item A" in p.ultimo_mensaje
        assert "Desc A" in p.ultimo_mensaje
