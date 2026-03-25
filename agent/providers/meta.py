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
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")

# Tipos de mensaje de audio que WhatsApp puede enviar
TIPOS_AUDIO = {"audio", "voice"}


class ProveedorMeta(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando la Cloud API oficial de Meta."""

    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN", "")
        self.phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "")
        self.verify_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "dona_webhook_secret")
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

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload de la Cloud API de Meta.
        Estructura: entry[].changes[].value.messages[]
        """
        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"[META] Error al parsear JSON del webhook: {e}")
            return []

        logger.debug(f"[META] Payload recibido: {body}")
        mensajes = []

        try:
            entries = body.get("entry", [])
            for entry in entries:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    msgs = value.get("messages", [])

                    for msg in msgs:
                        tipo = msg.get("type", "text")
                        telefono = msg.get("from", "")
                        mensaje_id = msg.get("id", "")
                        timestamp = int(msg.get("timestamp", 0))

                        if tipo == "text":
                            texto = msg.get("text", {}).get("body", "")
                            mensajes.append(MensajeEntrante(
                                telefono=telefono,
                                texto=texto,
                                mensaje_id=mensaje_id,
                                es_propio=False,
                                timestamp=timestamp,
                            ))

                        elif tipo in TIPOS_AUDIO:
                            audio_data = msg.get("audio") or msg.get("voice") or {}
                            if not isinstance(audio_data, dict):
                                audio_data = {}
                            audio_id = audio_data.get("id", mensaje_id)
                            mime_type = audio_data.get("mime_type", "audio/ogg; codecs=opus")
                            logger.info(f"[META] Nota de voz de {telefono}: audio_id={audio_id} mime={mime_type}")
                            mensajes.append(MensajeEntrante(
                                telefono=telefono,
                                texto="",
                                mensaje_id=mensaje_id,
                                es_propio=False,
                                timestamp=timestamp,
                                audio_id=audio_id,
                                audio_mime=mime_type,
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
