# agent/providers/whapi.py — Adaptador para Whapi.cloud
# Dona

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
                    timestamp=msg.get("timestamp", 0),
                ))

            elif tipo in TIPOS_AUDIO:
                # Nota de voz — loguear payload completo para diagnóstico
                logger.info(f"AUDIO MSG completo: {msg}")
                audio_data = msg.get("audio") or msg.get("voice") or {}
                if not isinstance(audio_data, dict):
                    audio_data = {}
                audio_id = audio_data.get("id", mensaje_id)
                mime_type = audio_data.get("mime_type", "audio/ogg; codecs=opus")
                logger.info(f"Nota de voz de {telefono}: tipo={tipo} audio_id={audio_id} mime={mime_type}")
                mensajes.append(MensajeEntrante(
                    telefono=telefono,
                    texto="",           # Se llenará tras transcribir
                    mensaje_id=mensaje_id,
                    es_propio=es_propio,
                    timestamp=msg.get("timestamp", 0),
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

    async def enviar_imagen(
        self, telefono: str, url: str = "", imagen_bytes: bytes = b"",
        caption: str = "", mime_type: str = "image/png",
    ) -> bool:
        """
        Envía una imagen via Whapi.cloud. Prefiere URL pública (más eficiente);
        si sólo hay bytes, los manda en base64 vía `media` del endpoint.
        """
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado — imagen no enviada")
            return False
        endpoint = "https://gate.whapi.cloud/messages/image"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload: dict = {"to": telefono}
        if caption:
            payload["caption"] = caption[:1024]

        if url and not url.startswith("file://"):
            payload["media"] = url
        elif imagen_bytes:
            import base64
            b64 = base64.b64encode(imagen_bytes).decode("ascii")
            payload["media"] = f"data:{mime_type};base64,{b64}"
        else:
            logger.warning("enviar_imagen sin url ni bytes")
            return False

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(endpoint, json=payload, headers=headers)
                if r.status_code != 200:
                    logger.error(f"Error Whapi imagen {r.status_code}: {r.text}")
                    return False
                logger.info(f"Imagen enviada a {telefono} via Whapi")
                return True
        except Exception as e:
            logger.error(f"Excepción enviando imagen Whapi ({type(e).__name__}): {e}")
            return False
