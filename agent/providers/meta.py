# agent/providers/meta.py — Adaptador para Meta WhatsApp Business API (Cloud API)

"""
Proveedor de WhatsApp usando la API oficial de Meta (Cloud API).
Documentación: https://developers.facebook.com/docs/whatsapp/cloud-api

Variables de entorno requeridas:
  META_ACCESS_TOKEN        — Token de acceso (temporal o permanente)
  META_PHONE_NUMBER_ID     — ID del número de teléfono (Phone Number ID)
  META_WEBHOOK_VERIFY_TOKEN — Token secreto para verificar el webhook (lo defines tú)

Variables opcionales:
  META_API_VERSION         — Versión de la API (default: v21.0)
"""

import os
import hmac
import hashlib
import logging
import httpx
from typing import Optional
from pydantic import BaseModel, Field, ValidationError
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante, BotonRespuesta, OpcionLista

logger = logging.getLogger("agentkit")

# Tipos de mensaje de audio que WhatsApp puede enviar
TIPOS_AUDIO = {"audio", "voice"}

# Tipos de mensaje de imagen/documento que WhatsApp puede enviar
TIPOS_IMAGEN = {"image", "sticker"}
TIPOS_DOCUMENTO = {"document"}


# ── Pydantic models para validación del webhook de Meta ──────────────────────

class MetaMediaPayload(BaseModel):
    """Media object dentro de un mensaje (audio, image, sticker, document)."""
    id: str = ""
    mime_type: str = ""
    caption: str = ""
    filename: str = ""


class MetaMensaje(BaseModel):
    """Un mensaje individual dentro del webhook de Meta."""
    id: str = ""
    type: str = "text"
    timestamp: str = "0"

    # Campo 'from' es palabra reservada en Python → alias
    from_number: str = Field("", alias="from")

    text: Optional[dict] = None
    audio: Optional[MetaMediaPayload] = None
    voice: Optional[MetaMediaPayload] = None
    image: Optional[MetaMediaPayload] = None
    sticker: Optional[MetaMediaPayload] = None
    document: Optional[MetaMediaPayload] = None

    class Config:
        populate_by_name = True


class MetaValue(BaseModel):
    """El objeto 'value' dentro de changes[]."""
    messages: list[MetaMensaje] = []


class MetaChange(BaseModel):
    """Un cambio dentro de entry[].changes[]."""
    value: MetaValue = MetaValue()


class MetaEntry(BaseModel):
    """Una entrada del webhook."""
    changes: list[MetaChange] = []


class MetaWebhookPayload(BaseModel):
    """Payload completo del webhook de Meta WhatsApp Cloud API."""
    object: str = ""
    entry: list[MetaEntry] = []


class ProveedorMeta(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando la Cloud API oficial de Meta."""

    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN", "")
        self.phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "")
        self.verify_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "dona_webhook_secret")
        self.app_secret = os.getenv("META_APP_SECRET", "")
        self.api_version = os.getenv("META_API_VERSION", "v21.0")
        self.url_envio = (
            f"https://graph.facebook.com/{self.api_version}"
            f"/{self.phone_number_id}/messages"
        )

    async def validar_webhook(self, request: Request):
        """
        Verificación GET del webhook requerida por Meta.
        Meta envía: hub.mode, hub.verify_token, hub.challenge
        Si el verify_token coincide, responde con hub.challenge.
        """
        params = dict(request.query_params)
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        if mode == "subscribe" and token == self.verify_token:
            logger.info("[META] Webhook verificado correctamente")
            return int(challenge) if challenge and challenge.isdigit() else challenge
        else:
            logger.warning(f"[META] Verificación de webhook fallida: mode={mode} token={token}")
            return None

    def _verificar_firma(self, body_bytes: bytes, signature_header: str) -> bool:
        """
        Verifica la firma HMAC-SHA256 que Meta envía en X-Hub-Signature-256.
        Retorna True si la firma es válida o si META_APP_SECRET no está configurado
        (modo degradado con warning).
        """
        if not self.app_secret:
            logger.warning(
                "[META] META_APP_SECRET no configurado — webhook sin verificación HMAC. "
                "Configura esta variable para proteger el webhook contra payloads falsos."
            )
            return True  # Permitir sin firma si no se configuró (backwards compatible)

        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning("[META] Webhook recibido sin firma X-Hub-Signature-256 válida — rechazado")
            return False

        expected = hmac.new(
            self.app_secret.encode(), body_bytes, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature_header[7:], expected):
            logger.warning("[META] Firma HMAC del webhook NO coincide — payload rechazado")
            return False

        return True

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload de la Cloud API de Meta.
        Estructura: entry[].changes[].value.messages[]
        Verifica firma HMAC-SHA256 antes de procesar.
        """
        # Verificar firma HMAC antes de procesar
        body_bytes = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not self._verificar_firma(body_bytes, signature):
            return []  # Rechazar payload sin firma válida

        # Validar y parsear con Pydantic
        try:
            import json as _json
            raw = _json.loads(body_bytes)
        except Exception as e:
            logger.error(f"[META] Error al parsear JSON del webhook: {e}")
            return []

        try:
            payload = MetaWebhookPayload.model_validate(raw)
        except ValidationError as e:
            logger.warning(f"[META] Payload no pasó validación Pydantic: {e.error_count()} errores")
            logger.debug(f"[META] Detalle validación: {e}")
            return []

        logger.debug(f"[META] Payload validado: {raw}")
        mensajes = []

        try:
            for entry in payload.entry:
                for change in entry.changes:
                    for msg in change.value.messages:
                        tipo = msg.type
                        telefono = msg.from_number
                        mensaje_id = msg.id
                        timestamp = int(msg.timestamp) if msg.timestamp.isdigit() else 0

                        if tipo == "text":
                            texto = (msg.text or {}).get("body", "")
                            mensajes.append(MensajeEntrante(
                                telefono=telefono,
                                texto=texto,
                                mensaje_id=mensaje_id,
                                es_propio=False,
                                timestamp=timestamp,
                            ))

                        elif tipo in TIPOS_AUDIO:
                            audio_data = msg.audio or msg.voice
                            audio_id = audio_data.id if audio_data else mensaje_id
                            mime_type = audio_data.mime_type if audio_data else "audio/ogg; codecs=opus"
                            logger.info(f"[META] Nota de voz de {telefono}: audio_id={audio_id} mime={mime_type}")
                            mensajes.append(MensajeEntrante(
                                telefono=telefono,
                                texto="",
                                mensaje_id=mensaje_id,
                                es_propio=False,
                                timestamp=timestamp,
                                audio_id=audio_id or mensaje_id,
                                audio_mime=mime_type or "audio/ogg; codecs=opus",
                            ))

                        elif tipo in TIPOS_IMAGEN:
                            image_data = msg.image or msg.sticker
                            image_id = image_data.id if image_data else ""
                            caption = image_data.caption if image_data else ""
                            logger.info(f"[META] Imagen de {telefono}: image_id={image_id}")
                            if image_id:
                                mensajes.append(MensajeEntrante(
                                    telefono=telefono,
                                    texto="",
                                    mensaje_id=mensaje_id,
                                    es_propio=False,
                                    timestamp=timestamp,
                                    image_id=image_id,
                                    image_caption=caption,
                                ))

                        elif tipo in TIPOS_DOCUMENTO:
                            doc_data = msg.document
                            doc_id = doc_data.id if doc_data else ""
                            filename = doc_data.filename if doc_data else "documento"
                            caption = doc_data.caption if doc_data else ""
                            logger.info(f"[META] Documento de {telefono}: doc_id={doc_id} filename={filename}")
                            if doc_id:
                                texto_doc = f"[El usuario envió un documento: {filename or 'documento'}]"
                                if caption:
                                    texto_doc += f" con el mensaje: {caption}"
                                mensajes.append(MensajeEntrante(
                                    telefono=telefono,
                                    texto=texto_doc,
                                    mensaje_id=mensaje_id,
                                    es_propio=False,
                                    timestamp=timestamp,
                                ))

                        else:
                            logger.debug(f"[META] Tipo de mensaje ignorado: {tipo}")

        except Exception as e:
            logger.error(f"[META] Error al procesar payload del webhook: {e}")

        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """
        Envía mensaje de texto via Meta Cloud API.
        El número de teléfono debe incluir código de país sin '+' (ej: 521234567890).
        """
        if not self.access_token:
            logger.warning("[META] META_ACCESS_TOKEN no configurado — mensaje no enviado")
            return False
        if not self.phone_number_id:
            logger.warning("[META] META_PHONE_NUMBER_ID no configurado — mensaje no enviado")
            return False

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "text",
            "text": {"body": mensaje},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(self.url_envio, json=payload, headers=headers)
                if r.status_code not in (200, 201):
                    logger.error(f"[META] Error {r.status_code} al enviar mensaje: {r.text}")
                    return False
                logger.info(f"[META] Mensaje enviado a {telefono}")
                return True
        except Exception as e:
            logger.error(f"[META] Excepción al enviar mensaje ({type(e).__name__}): {e}")
            return False

    async def enviar_botones(
        self, telefono: str, texto: str, botones: list[BotonRespuesta]
    ) -> bool:
        """Envía mensaje con botones interactivos via Meta Cloud API (max 3 botones)."""
        if not self.access_token or not self.phone_number_id:
            return await super().enviar_botones(telefono, texto, botones)

        # Meta permite máximo 3 botones
        botones = botones[:3]
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": texto[:1024]},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": b.id[:256], "title": b.titulo[:20]},
                        }
                        for b in botones
                    ]
                },
            },
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(self.url_envio, json=payload, headers=headers)
                if r.status_code not in (200, 201):
                    logger.warning(f"[META] Botones fallaron ({r.status_code}), fallback a texto")
                    return await super().enviar_botones(telefono, texto, botones)
                return True
        except Exception as e:
            logger.error(f"[META] Error enviando botones: {e}")
            return await super().enviar_botones(telefono, texto, botones)

    async def enviar_lista(
        self, telefono: str, texto: str, boton_menu: str, opciones: list[OpcionLista]
    ) -> bool:
        """Envía mensaje con lista desplegable via Meta Cloud API (max 10 opciones)."""
        if not self.access_token or not self.phone_number_id:
            return await super().enviar_lista(telefono, texto, boton_menu, opciones)

        opciones = opciones[:10]
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": texto[:1024]},
                "action": {
                    "button": boton_menu[:20],
                    "sections": [
                        {
                            "title": "Opciones",
                            "rows": [
                                {
                                    "id": o.id[:200],
                                    "title": o.titulo[:24],
                                    **({"description": o.descripcion[:72]} if o.descripcion else {}),
                                }
                                for o in opciones
                            ],
                        }
                    ],
                },
            },
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(self.url_envio, json=payload, headers=headers)
                if r.status_code not in (200, 201):
                    logger.warning(f"[META] Lista falló ({r.status_code}), fallback a texto")
                    return await super().enviar_lista(telefono, texto, boton_menu, opciones)
                return True
        except Exception as e:
            logger.error(f"[META] Error enviando lista: {e}")
            return await super().enviar_lista(telefono, texto, boton_menu, opciones)
