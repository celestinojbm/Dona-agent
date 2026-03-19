# agent/providers/whapi.py — Adaptador para Whapi.cloud
# Generado por AgentKit

import os
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


class ProveedorWhapi(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Whapi.cloud (REST API simple)."""

    def __init__(self):
        self.token = os.getenv("WHAPI_TOKEN")
        self.url_envio = "https://gate.whapi.cloud/messages/text"

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload de Whapi.cloud.
        Soporta dos formatos:
        - Webhook genérico (/webhook):        {"messages": [{...}, ...]}
        - Webhook por evento (/webhook/messages): {...mensaje directo...}
        """
        body = await request.json()
        logger.debug(f"Payload Whapi recibido: {body}")
        mensajes = []

        # Formato genérico: {"messages": [...]}
        if "messages" in body:
            lista = body["messages"]
        # Formato evento específico: el body ES el mensaje directamente
        elif "chat_id" in body:
            lista = [body]
        else:
            logger.warning(f"Formato de webhook desconocido: {list(body.keys())}")
            return []

        for msg in lista:
            texto = msg.get("text", {}).get("body", "") if isinstance(msg.get("text"), dict) else ""
            mensajes.append(MensajeEntrante(
                telefono=msg.get("chat_id", ""),
                texto=texto,
                mensaje_id=msg.get("id", ""),
                es_propio=msg.get("from_me", False),
            ))
        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envía mensaje via Whapi.cloud."""
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
