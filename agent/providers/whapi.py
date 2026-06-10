# agent/providers/whapi.py — Adaptador para Whapi.cloud
# Dona

import os
import hmac
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("dona")

# Tipos de mensaje de audio que WhatsApp puede enviar
TIPOS_AUDIO = {"audio", "voice", "ptt"}


class ProveedorWhapi(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Whapi.cloud (REST API simple)."""

    def __init__(self):
        self.token = os.getenv("WHAPI_TOKEN")
        self.url_envio = "https://gate.whapi.cloud/messages/text"
        self.webhook_token = os.getenv("WHAPI_WEBHOOK_TOKEN", "").strip()
        self.webhook_header = os.getenv(
            "WHAPI_WEBHOOK_HEADER", "X-Webhook-Token"
        ).strip()

        # Fail-fast: WHAPI_WEBHOOK_TOKEN obligatorio en producción cuando
        # WHATSAPP_PROVIDER=whapi. Whapi no usa HMAC sobre el body; su modelo
        # oficial es shared secret en custom header configurado vía
        # PATCH /settings (parámetro "headers"). Sin ese token la ruta
        # /webhook aceptaría payloads forjados desde cualquier IP, lo que
        # permitiría inyectar mensajes WhatsApp falsos.
        # El check vive aquí (en __init__) y no a nivel módulo porque el
        # factory de agent/providers/__init__.py solo importa este módulo
        # si el provider activo es Whapi — así no bloqueamos deploys con
        # WHATSAPP_PROVIDER=meta/twilio sin necesidad de este token.
        from agent.entorno import es_entorno_estricto
        if es_entorno_estricto() and not self.webhook_token:
            raise RuntimeError(
                "[WHAPI] WHAPI_WEBHOOK_TOKEN no configurado en entorno estricto — "
                "los webhooks aceptarían payloads forjados, lo que permite "
                "a un atacante inyectar mensajes WhatsApp falsos. Configura "
                "la variable o cambia WHATSAPP_PROVIDER antes de reintentar "
                "el deploy."
            )

    def _verificar_firma(self, request: Request) -> bool:
        """Valida que el request incluye el custom header con el valor esperado.

        Whapi no firma HMAC sobre el body; el modelo oficial es shared secret
        en custom header configurado en el panel de Whapi (PATCH /settings con
        parámetro ``headers``). El owner debe configurar allí el header
        ``self.webhook_header`` con el valor de ``self.webhook_token``.

        Comportamiento:
          - Producción sin ``webhook_token``: rechaza (defensa en profundidad).
            El check de ``__init__`` ya debería haber abortado el deploy, pero
            esto cubre el caso de que el provider se haya construido por algún
            path alternativo sin token.
          - Dev/test sin ``webhook_token``: acepta sin verificar (con warning)
            para permitir pruebas locales sin configurar Whapi.
          - Con ``webhook_token``: compara con el header recibido usando
            ``hmac.compare_digest`` (timing-safe).

        ``ENVIRONMENT`` se lee en cada llamada para facilitar tests con
        ``monkeypatch.setenv``.
        """
        from agent.entorno import es_entorno_estricto

        if not self.webhook_token:
            if es_entorno_estricto():
                logger.error(
                    "[WHAPI] WHAPI_WEBHOOK_TOKEN no configurado en entorno "
                    "estricto — rechazando webhook (defensa en profundidad)."
                )
                return False
            logger.warning(
                "[WHAPI] WHAPI_WEBHOOK_TOKEN no configurado — aceptando sin "
                "verificar (INSEGURO, solo dev/test)."
            )
            return True

        received = request.headers.get(self.webhook_header, "")
        if not received:
            logger.warning(
                f"[WHAPI] Header {self.webhook_header} ausente — webhook rechazado."
            )
            return False

        if not hmac.compare_digest(received, self.webhook_token):
            logger.warning(
                f"[WHAPI] Header {self.webhook_header} no coincide — webhook rechazado."
            )
            return False

        return True

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload de Whapi.cloud.
        Soporta mensajes de texto y notas de voz (audio).
        Formatos:
        - Webhook genérico:   {"messages": [{...}, ...]}
        - Webhook por evento: {...mensaje directo...}

        Verifica el custom header de seguridad antes de parsear (T0.10).
        """
        if not self._verificar_firma(request):
            return []  # Rechazo silencioso — no procesar payload

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

    async def _enviar_mensaje_impl(self, telefono: str, mensaje: str) -> bool:
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

    async def _enviar_documento_impl(
        self, telefono: str, archivo_bytes: bytes, filename: str,
        mime_type: str = "application/pdf", caption: str = "",
    ) -> bool:
        """
        Envía un documento (PDF, CSV, etc.) via Whapi.cloud.
        Usa base64 data-URL en el campo `media`.
        """
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado — documento no enviado")
            return False
        if not archivo_bytes:
            return False
        endpoint = "https://gate.whapi.cloud/messages/document"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        import base64
        b64 = base64.b64encode(archivo_bytes).decode("ascii")
        payload: dict = {
            "to": telefono,
            "media": f"data:{mime_type};base64,{b64}",
            "filename": filename,
        }
        if caption:
            payload["caption"] = caption[:1024]

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(endpoint, json=payload, headers=headers)
                if r.status_code != 200:
                    logger.error(f"Error Whapi documento {r.status_code}: {r.text[:200]}")
                    return False
                logger.info(f"Documento enviado a {telefono} via Whapi ({filename}, {len(archivo_bytes)}B)")
                return True
        except Exception as e:
            logger.error(f"Excepción enviando documento Whapi ({type(e).__name__}): {e}")
            return False

    async def _enviar_video_impl(
        self, telefono: str, url: str = "", video_bytes: bytes = b"",
        caption: str = "", mime_type: str = "video/mp4",
    ) -> bool:
        """
        Envía un video via Whapi.cloud. Prefiere URL pública (más eficiente);
        si sólo hay bytes, los manda en base64 vía `media`.
        WhatsApp acepta videos ≤16MB inline.
        """
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado — video no enviado")
            return False
        endpoint = "https://gate.whapi.cloud/messages/video"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload: dict = {"to": telefono}
        if caption:
            payload["caption"] = caption[:1024]

        if url and not url.startswith("file://"):
            payload["media"] = url
        elif video_bytes:
            import base64
            b64 = base64.b64encode(video_bytes).decode("ascii")
            payload["media"] = f"data:{mime_type};base64,{b64}"
        else:
            logger.warning("enviar_video sin url ni bytes")
            return False

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(endpoint, json=payload, headers=headers)
                if r.status_code != 200:
                    logger.error(f"Error Whapi video {r.status_code}: {r.text[:200]}")
                    return False
                logger.info(f"Video enviado a {telefono} via Whapi")
                return True
        except Exception as e:
            logger.error(f"Excepción enviando video Whapi ({type(e).__name__}): {e}")
            return False

    async def _enviar_imagen_impl(
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
