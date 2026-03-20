# agent/providers/whapi.py — Adaptador para Whapi.cloud
# Generado por AgentKit

import os
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")

# Tipos de mensaje de audio que WhatsApp puede enviar
TIPOS_AUDIO = {"audio", "voice", "ptt"}


class ProveedorWhapi(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Whapi.cloud (REST API simple)."""

    def __init__(self):
        self.token = os.getenv("WHAPI_TOKEN")
        self.url_envio = "https://gate.whapi.cloud/messages/text"

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload de Whapi.cloud.
        Soporta mensajes de texto y notas de voz (audio).
        Formatos:
        - Webhook genérico:   {"messages": [{...}, ...]}
        - Webhook por evento: {...mensaje directo...}
        """
        body = await request.json()
        logger.debug(f"Payload Whapi recibido: {body}")
        mensajes = []

        # Normalizar a lista
        if "messages" in body:
            lista = body["messages"]
        elif "chat_id" in body:
            lista = [body]
        else:
            logger.warning(f"Formato de webhook desconocido: {list(body.keys())}")
            return []

        for msg in lista:
            tipo = msg.get("type", "text")
            telefono = msg.get("chat_id", "")
            mensaje_id = msg.get("id", "")
            es_propio = msg.get("from_me", False)

            if tipo == "text":
                # Mensaje de texto normal
                texto = msg.get("text", {}).get("body", "") if isinstance(msg.get("text"), dict) else ""
                mensajes.append(MensajeEntrante(
                    telefono=telefono,
                    texto=texto,
                    mensaje_id=mensaje_id,
                    es_propio=es_propio,
                ))

            elif tipo in TIPOS_AUDIO:
                # Nota de voz — extraer el ID y mime type del audio
                audio_data = msg.get("audio") or msg.get("voice") or {}
                if not isinstance(audio_data, dict):
                    audio_data = {}
                audio_id = audio_data.get("id", mensaje_id)
                mime_type = audio_data.get("mime_type", "audio/ogg; codecs=opus")
                logger.info(f"Nota de voz recibida de {telefono}: id={audio_id}")
                mensajes.append(MensajeEntrante(
                    telefono=telefono,
                    texto="",           # Se llenará tras transcribir
                    mensaje_id=mensaje_id,
                    es_propio=es_propio,
                    audio_id=audio_id,
                    audio_mime=mime_type,
                ))

            else:
                logger.debug(f"Tipo de mensaje ignorado: {tipo}")

        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envía mensaje de texto via Whapi.cloud."""
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado — mensaje no enviado")
            return False
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    self.url_envio,
                    json={"to": telefono, "body": mensaje},
                    headers=headers,
                )
                if r.status_code != 200:
                    logger.error(f"Error Whapi {r.status_code}: {r.text}")
                    return False
                logger.info(f"Mensaje enviado a {telefono} via Whapi")
                return True
        except Exception as e:
            logger.error(f"Excepción al enviar mensaje Whapi ({type(e).__name__}): {e}")
            return False
