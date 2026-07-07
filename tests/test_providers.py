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
import time
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict


def _now_ts() -> str:
    """Timestamp actual en segundos (string) para pasar la validación de replay."""
    return str(int(time.time()))

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
        "timestamp": _now_ts(),
        "type": "text",
        "text": {"body": text},
    }


def _make_audio_msg(from_number: str = "5215551234567") -> dict:
    return {
        "from": from_number,
        "id": "wamid.audio1",
        "timestamp": _now_ts(),
        "type": "audio",
        "audio": {"id": "audio_media_id", "mime_type": "audio/ogg; codecs=opus"},
    }


def _make_image_msg(from_number: str = "5215551234567") -> dict:
    return {
        "from": from_number,
        "id": "wamid.img1",
        "timestamp": _now_ts(),
        "type": "image",
        "image": {"id": "image_media_id", "caption": "foto de producto"},
    }


def _make_document_msg(from_number: str = "5215551234567") -> dict:
    return {
        "from": from_number,
        "id": "wamid.doc1",
        "timestamp": _now_ts(),
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
    """Comportamiento de _verificar_firma en development/test.

    En entornos no-producción mantenemos el path permisivo (acepta sin
    verificar con warning) para permitir pruebas locales sin configurar
    Meta. La firma HMAC sigue validándose si el secret está presente.
    """

    def test_sin_secret_en_dev_permite(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        proveedor = ProveedorMeta()
        proveedor.app_secret = ""
        assert proveedor._verificar_firma(b"body", "") is True

    def test_sin_secret_en_test_permite(self, monkeypatch):
        # ENVIRONMENT=test (default de conftest.py) sigue siendo permisivo.
        monkeypatch.setenv("ENVIRONMENT", "test")
        proveedor = ProveedorMeta()
        proveedor.app_secret = ""
        assert proveedor._verificar_firma(b"body", "sha256=anything") is True

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


class TestVerificacionHMACProduction:
    """T0.3: Comportamiento de ProveedorMeta en producción.

    En producción, sin META_APP_SECRET, el provider debe abortar la
    inicialización (RuntimeError) y, como defensa en profundidad, la
    función _verificar_firma debe rechazar todo payload aunque por
    algún path se haya saltado el __init__.
    """

    def test_production_sin_secret_levanta_runtime_error_en_init(self, monkeypatch):
        """Al instanciar el provider: si production sin secret, RuntimeError aborta."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("META_APP_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="META_APP_SECRET"):
            ProveedorMeta()

    def test_production_secret_vacio_levanta_runtime_error(self, monkeypatch):
        """Strings con solo whitespace cuentan como vacío (.strip() en __init__)."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("META_APP_SECRET", "   ")
        with pytest.raises(RuntimeError, match="META_APP_SECRET"):
            ProveedorMeta()

    def test_production_con_secret_no_levanta_en_init(self, monkeypatch):
        """Con secret configurado, el __init__ en production no aborta."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("META_APP_SECRET", "test_app_secret_dummy")
        proveedor = ProveedorMeta()  # No debe levantar.
        assert proveedor.app_secret == "test_app_secret_dummy"

    def test_production_runtime_sin_secret_rechaza_firma(self, monkeypatch):
        """Defensa en profundidad: aunque el __init__ se haya saltado, runtime rechaza."""
        # Construir el provider en dev/test (donde __init__ no aborta).
        monkeypatch.setenv("ENVIRONMENT", "development")
        proveedor = ProveedorMeta()
        proveedor.app_secret = ""  # Forzar override
        # Simular runtime de production.
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert proveedor._verificar_firma(b"body", "sha256=anything") is False

    def test_production_con_secret_valida_firma_correcta(self, monkeypatch):
        """En production con secret presente, firma válida sigue aceptándose."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        secret = "production_secret_dummy"
        monkeypatch.setenv("META_APP_SECRET", secret)
        proveedor = ProveedorMeta()
        body = b'{"test": true}'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert proveedor._verificar_firma(body, f"sha256={sig}") is True


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
    # Estos tests verifican TRANSPORTE (formato del fallback a texto), no la
    # política del gate de envíos — por eso corren en contexto DIRECTO, que
    # no consulta la DB. La política se cubre en tests/test_envio_gate.py.

    @pytest.mark.asyncio
    async def test_botones_fallback(self):
        """Fallback de botones debe enviar texto con opciones numeradas."""
        from agent.providers.base import ProveedorWhatsApp
        from agent.envio_gate import contexto_envio_directo

        class FakeProveedor(ProveedorWhatsApp):
            async def parsear_webhook(self, request):
                return []
            async def _enviar_mensaje_impl(self, telefono, mensaje):
                self.ultimo_mensaje = mensaje
                return True

        p = FakeProveedor()
        botones = [BotonRespuesta(id="1", titulo="Opción A"), BotonRespuesta(id="2", titulo="Opción B")]
        with contexto_envio_directo("521555"):
            result = await p.enviar_botones("521555", "Elige:", botones)
        assert result is True
        assert "1. Opción A" in p.ultimo_mensaje
        assert "2. Opción B" in p.ultimo_mensaje

    @pytest.mark.asyncio
    async def test_lista_fallback(self):
        """Fallback de lista debe enviar texto con bullets."""
        from agent.providers.base import ProveedorWhatsApp
        from agent.envio_gate import contexto_envio_directo

        class FakeProveedor(ProveedorWhatsApp):
            async def parsear_webhook(self, request):
                return []
            async def _enviar_mensaje_impl(self, telefono, mensaje):
                self.ultimo_mensaje = mensaje
                return True

        p = FakeProveedor()
        opciones = [
            OpcionLista(id="a", titulo="Item A", descripcion="Desc A"),
            OpcionLista(id="b", titulo="Item B"),
        ]
        with contexto_envio_directo("521555"):
            result = await p.enviar_lista("521555", "Menú:", "Ver", opciones)
        assert result is True
        assert "Item A" in p.ultimo_mensaje
        assert "Desc A" in p.ultimo_mensaje


# ── Fase 0 · TEMA 2: Factory falla explícito con proveedor declarado sin módulo ──


class TestFactoryProveedor:
    """El factory obtener_proveedor() no debe delatar un proveedor declarado
    pero sin implementar (Twilio) con un ModuleNotFoundError críptico en el
    primer webhook: falla EXPLÍCITO y temprano con mensaje accionable.
    """

    def test_twilio_declarado_sin_modulo_falla_claro(self, monkeypatch):
        """WHATSAPP_PROVIDER=twilio sin agent/providers/twilio.py → RuntimeError
        con mensaje claro, NO ModuleNotFoundError críptico."""
        from agent.providers import obtener_proveedor
        monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
        with pytest.raises(RuntimeError, match="twilio.py"):
            obtener_proveedor()

    def test_proveedor_no_soportado_falla_con_valueerror(self, monkeypatch):
        """Un valor sin entrada en el factory (telegram) → ValueError lista los
        soportados."""
        from agent.providers import obtener_proveedor
        monkeypatch.setenv("WHATSAPP_PROVIDER", "telegram")
        with pytest.raises(ValueError, match="no soportado"):
            obtener_proveedor()

    def test_whapi_default_instancia_ok(self, monkeypatch):
        """Sin WHATSAPP_PROVIDER, el default whapi tiene módulo y se instancia."""
        from agent.providers import obtener_proveedor
        from agent.providers.whapi import ProveedorWhapi
        monkeypatch.delenv("WHATSAPP_PROVIDER", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")  # no exige token
        assert isinstance(obtener_proveedor(), ProveedorWhapi)

    def test_modulo_de_proveedor_falta_solo_para_twilio(self):
        """El helper reporta faltante SOLO para el proveedor sin módulo real."""
        from agent.providers import modulo_de_proveedor_falta
        assert modulo_de_proveedor_falta("twilio") is True
        assert modulo_de_proveedor_falta("whapi") is False
        assert modulo_de_proveedor_falta("meta") is False
        # Un valor no soportado no es "módulo faltante" (es otro problema).
        assert modulo_de_proveedor_falta("telegram") is False


# ── T0.10: Validación de header personalizado en webhooks Whapi ─────────────


def _make_whapi_text_msg(telefono: str = "5215551234567", texto: str = "hola") -> dict:
    """Mensaje Whapi de texto mínimo para tests de webhook."""
    return {
        "id": "whapi.msg.abc",
        "chat_id": telefono,
        "type": "text",
        "text": {"body": texto},
        "from_me": False,
    }


def _make_whapi_request(payload: dict, headers: dict | None = None) -> AsyncMock:
    """Crea un mock de Request de FastAPI para webhook Whapi.

    A diferencia de _make_request (Meta), Whapi parsea via request.json() y no
    request.body(), así que mockeamos el método json directamente.
    """
    request = AsyncMock()
    request.json = AsyncMock(return_value=payload)
    request.body = AsyncMock(return_value=json.dumps(payload).encode())
    request.headers = headers or {}
    return request


class TestWhapiWebhookValidation:
    """T0.10: validación de header personalizado en webhooks Whapi.

    Whapi no firma HMAC sobre el body; el modelo de seguridad oficial es
    custom header con shared secret configurado en su panel via PATCH /settings.
    """

    def test_dev_sin_token_acepta_payload(self, monkeypatch):
        from agent.providers.whapi import ProveedorWhapi
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("WHAPI_WEBHOOK_TOKEN", raising=False)
        proveedor = ProveedorWhapi()  # No debe levantar.
        # Mensaje sin header → en dev se acepta.
        request = _make_whapi_request({"messages": [_make_whapi_text_msg()]})
        assert proveedor._verificar_firma(request) is True

    def test_production_sin_token_levanta_runtime_error(self, monkeypatch):
        """Al instanciar el provider: si production sin token, RuntimeError aborta."""
        from agent.providers.whapi import ProveedorWhapi
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("WHAPI_WEBHOOK_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="WHAPI_WEBHOOK_TOKEN"):
            ProveedorWhapi()

    def test_production_secret_solo_whitespace_levanta(self, monkeypatch):
        """Strings con solo whitespace cuentan como vacío (.strip() en __init__)."""
        from agent.providers.whapi import ProveedorWhapi
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("WHAPI_WEBHOOK_TOKEN", "   ")
        with pytest.raises(RuntimeError, match="WHAPI_WEBHOOK_TOKEN"):
            ProveedorWhapi()

    def test_production_con_token_no_levanta_en_init(self, monkeypatch):
        """Con token configurado, el __init__ en production no aborta."""
        from agent.providers.whapi import ProveedorWhapi
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("WHAPI_WEBHOOK_TOKEN", "test_token_dummy")
        proveedor = ProveedorWhapi()  # No debe levantar.
        assert proveedor.webhook_token == "test_token_dummy"
        assert proveedor.webhook_header == "X-Webhook-Token"

    @pytest.mark.asyncio
    async def test_production_token_valido_acepta(self, monkeypatch):
        """En production con header correcto, parsear_webhook procesa mensajes."""
        from agent.providers.whapi import ProveedorWhapi
        # Construir provider en dev/test (donde __init__ no aborta) y luego override.
        monkeypatch.setenv("ENVIRONMENT", "development")
        proveedor = ProveedorWhapi()
        proveedor.webhook_token = "shared_token_xyz"
        # Simular runtime de production.
        monkeypatch.setenv("ENVIRONMENT", "production")
        request = _make_whapi_request(
            {"messages": [_make_whapi_text_msg(texto="hola")]},
            headers={"X-Webhook-Token": "shared_token_xyz"},
        )
        mensajes = await proveedor.parsear_webhook(request)
        assert len(mensajes) == 1
        assert mensajes[0].texto == "hola"

    @pytest.mark.asyncio
    async def test_production_token_invalido_rechaza(self, monkeypatch):
        """En production con header presente pero valor incorrecto, parsear retorna []."""
        from agent.providers.whapi import ProveedorWhapi
        monkeypatch.setenv("ENVIRONMENT", "development")
        proveedor = ProveedorWhapi()
        proveedor.webhook_token = "shared_token_xyz"
        monkeypatch.setenv("ENVIRONMENT", "production")
        request = _make_whapi_request(
            {"messages": [_make_whapi_text_msg()]},
            headers={"X-Webhook-Token": "secreto_FALSO"},
        )
        mensajes = await proveedor.parsear_webhook(request)
        assert mensajes == []

    @pytest.mark.asyncio
    async def test_production_sin_header_rechaza(self, monkeypatch):
        """En production sin el header configurado, parsear retorna []."""
        from agent.providers.whapi import ProveedorWhapi
        monkeypatch.setenv("ENVIRONMENT", "development")
        proveedor = ProveedorWhapi()
        proveedor.webhook_token = "shared_token_xyz"
        monkeypatch.setenv("ENVIRONMENT", "production")
        request = _make_whapi_request(
            {"messages": [_make_whapi_text_msg()]},
            headers={},
        )
        mensajes = await proveedor.parsear_webhook(request)
        assert mensajes == []

    def test_header_personalizable_via_env(self, monkeypatch):
        """WHAPI_WEBHOOK_HEADER permite cambiar el nombre del header."""
        from agent.providers.whapi import ProveedorWhapi
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("WHAPI_WEBHOOK_TOKEN", "shared_token_xyz")
        monkeypatch.setenv("WHAPI_WEBHOOK_HEADER", "X-Custom-Auth")
        proveedor = ProveedorWhapi()
        assert proveedor.webhook_header == "X-Custom-Auth"
        # Header con el nombre custom y valor correcto → acepta.
        request = _make_whapi_request(
            {"messages": [_make_whapi_text_msg()]},
            headers={"X-Custom-Auth": "shared_token_xyz"},
        )
        assert proveedor._verificar_firma(request) is True
        # Mismo valor en header default no sirve.
        request2 = _make_whapi_request(
            {"messages": [_make_whapi_text_msg()]},
            headers={"X-Webhook-Token": "shared_token_xyz"},
        )
        assert proveedor._verificar_firma(request2) is False
