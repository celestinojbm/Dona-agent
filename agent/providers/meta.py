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
import time as _time
import httpx
from typing import Optional
from pydantic import BaseModel, Field, ValidationError
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante, BotonRespuesta, OpcionLista

logger = logging.getLogger("dona")

# Ventana máxima de antigüedad aceptada para mensajes entrantes (replay protection).
# Mensajes con timestamp más viejo que esto se descartan (defensa en profundidad
# además de la firma HMAC y la deduplicación por mensaje_id).
_MAX_MENSAJE_EDAD_SEGUNDOS = 600  # 10 minutos

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
        self.app_secret = os.getenv("META_APP_SECRET", "").strip()
        self.api_version = os.getenv("META_API_VERSION", "v21.0")
        self.url_envio = (
            f"https://graph.facebook.com/{self.api_version}"
            f"/{self.phone_number_id}/messages"
        )

        # Fail-fast: META_APP_SECRET obligatorio en producción cuando
        # WHATSAPP_PROVIDER=meta. Sin secret la verificación HMAC del
        # webhook queda deshabilitada y un atacante podría inyectar
        # mensajes WhatsApp falsos. El check vive aquí (en __init__) y
        # no a nivel módulo porque el factory de agent/providers/__init__.py
        # solo importa este módulo si el provider activo es Meta — así no
        # bloqueamos deploys con WHATSAPP_PROVIDER=whapi/twilio sin secret.
        from agent.entorno import es_entorno_estricto
        if es_entorno_estricto() and not self.app_secret:
            raise RuntimeError(
                "[META] META_APP_SECRET no configurado en entorno estricto — "
                "los webhooks aceptarían payloads forjados, lo que permite "
                "a un atacante inyectar mensajes WhatsApp falsos. Configura "
                "la variable o cambia WHATSAPP_PROVIDER antes de reintentar "
                "el deploy."
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
        Verifica la firma HMAC-SHA256 que Meta envía en ``X-Hub-Signature-256``.

        Comportamiento:
          - En ``ENVIRONMENT=production``: si ``self.app_secret`` está vacío
            (lo que en condiciones normales no debería suceder porque el
            check de ``__init__`` ya habría abortado el deploy), igualmente
            se rechaza el payload retornando ``False``. Defensa en profundidad.
          - En dev/test: si no hay secret, se acepta sin verificar (con
            warning) para permitir pruebas locales sin configurar Meta.
          - Con secret: valida HMAC-SHA256 timing-safe contra el header.

        ``ENVIRONMENT`` se lee en cada llamada (no se cachea) para facilitar
        tests con ``monkeypatch.setenv``.
        """
        from agent.entorno import es_entorno_estricto

        if not self.app_secret:
            if es_entorno_estricto():
                logger.error(
                    "[META] META_APP_SECRET no configurado en entorno estricto — "
                    "rechazando webhook (defensa en profundidad)."
                )
                return False
            logger.warning(
                "[META] META_APP_SECRET no configurado — aceptando sin verificar "
                "(INSEGURO, solo dev/test)."
            )
            return True

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

                        # Replay protection: rechazar mensajes con timestamp muy antiguo.
                        # timestamp==0 se permite (algunos eventos no lo incluyen) pero loguea.
                        if timestamp > 0:
                            edad = int(_time.time()) - timestamp
                            if edad > _MAX_MENSAJE_EDAD_SEGUNDOS:
                                logger.warning(
                                    f"[META] Mensaje descartado por antigüedad: "
                                    f"id={mensaje_id} edad={edad}s (>{_MAX_MENSAJE_EDAD_SEGUNDOS}s)"
                                )
                                continue
                            # Timestamps futuros también son sospechosos (margen 5 min para clock skew)
                            if edad < -300:
                                logger.warning(
                                    f"[META] Mensaje con timestamp futuro descartado: "
                                    f"id={mensaje_id} delta={edad}s"
                                )
                                continue

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

    async def _subir_media(self, archivo_bytes: bytes, mime_type: str, filename: str = "archivo.bin") -> str | None:
        """
        Sube un archivo binario a la Media API de Meta y devuelve el media_id.
        Paso 1 de 2 para enviar audio/imagen/documento.
        """
        if not self.access_token or not self.phone_number_id:
            return None
        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/media"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        # Meta requiere multipart con campos: messaging_product, type, file
        files = {
            "file": (filename, archivo_bytes, mime_type),
        }
        data = {
            "messaging_product": "whatsapp",
            "type": mime_type,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(url, headers=headers, data=data, files=files)
                if r.status_code not in (200, 201):
                    logger.error(f"[META] Subida de media falló {r.status_code}: {r.text[:200]}")
                    return None
                media_id = r.json().get("id")
                if media_id:
                    logger.info(f"[META] Media subida: {media_id}")
                return media_id
        except Exception as e:
            logger.error(f"[META] Excepción subiendo media ({type(e).__name__}): {e}")
            return None

    async def enviar_audio(self, telefono: str, audio_bytes: bytes, mime_type: str = "audio/ogg") -> bool:
        """
        Envía un audio (nota de voz) via Meta Cloud API.
        Sube los bytes a la Media API y luego manda un mensaje tipo 'audio'.
        """
        if not audio_bytes:
            return False
        ext = "ogg" if "ogg" in mime_type or "opus" in mime_type else "bin"
        media_id = await self._subir_media(audio_bytes, mime_type, filename=f"audio.{ext}")
        if not media_id:
            return False
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "audio",
            "audio": {"id": media_id},
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(self.url_envio, json=payload, headers=headers)
                if r.status_code not in (200, 201):
                    logger.error(f"[META] Error {r.status_code} enviando audio: {r.text[:200]}")
                    return False
                logger.info(f"[META] Audio enviado a {telefono}")
                return True
        except Exception as e:
            logger.error(f"[META] Excepción enviando audio ({type(e).__name__}): {e}")
            return False

    async def enviar_imagen(
        self, telefono: str, url: str = "", imagen_bytes: bytes = b"",
        caption: str = "", mime_type: str = "image/png",
    ) -> bool:
        """
        Envía una imagen via Meta Cloud API. Prefiere URL pública (Meta
        la descarga directamente). Si sólo hay bytes, los sube primero via
        `_subir_media` para obtener un `media_id`.
        """
        img_payload: dict = {}
        if url and url.startswith("http"):
            img_payload["link"] = url
        elif imagen_bytes:
            ext = (mime_type.split("/", 1)[-1] or "png").split(";")[0]
            media_id = await self._subir_media(imagen_bytes, mime_type, filename=f"imagen.{ext}")
            if not media_id:
                return False
            img_payload["id"] = media_id
        else:
            logger.warning("[META] enviar_imagen sin url ni bytes")
            return False

        if caption:
            img_payload["caption"] = caption[:1024]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "image",
            "image": img_payload,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(self.url_envio, json=payload, headers=headers)
                if r.status_code not in (200, 201):
                    logger.error(f"[META] Error {r.status_code} enviando imagen: {r.text[:200]}")
                    return False
                logger.info(f"[META] Imagen enviada a {telefono}")
                return True
        except Exception as e:
            logger.error(f"[META] Excepción enviando imagen ({type(e).__name__}): {e}")
            return False

    async def enviar_video(
        self, telefono: str, url: str = "", video_bytes: bytes = b"",
        caption: str = "", mime_type: str = "video/mp4",
    ) -> bool:
        """
        Envía un video via Meta Cloud API. Prefiere URL pública (Meta la
        descarga directamente). Si sólo hay bytes, los sube via `_subir_media`
        para obtener un `media_id`.
        """
        vid_payload: dict = {}
        if url and url.startswith("http"):
            vid_payload["link"] = url
        elif video_bytes:
            ext = (mime_type.split("/", 1)[-1] or "mp4").split(";")[0]
            media_id = await self._subir_media(video_bytes, mime_type, filename=f"video.{ext}")
            if not media_id:
                return False
            vid_payload["id"] = media_id
        else:
            logger.warning("[META] enviar_video sin url ni bytes")
            return False

        if caption:
            vid_payload["caption"] = caption[:1024]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "video",
            "video": vid_payload,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(self.url_envio, json=payload, headers=headers)
                if r.status_code not in (200, 201):
                    logger.error(f"[META] Error {r.status_code} enviando video: {r.text[:200]}")
                    return False
                logger.info(f"[META] Video enviado a {telefono}")
                return True
        except Exception as e:
            logger.error(f"[META] Excepción enviando video ({type(e).__name__}): {e}")
            return False

    async def enviar_documento(
        self, telefono: str, archivo_bytes: bytes, filename: str, mime_type: str = "text/csv", caption: str = ""
    ) -> bool:
        """Envía un documento adjunto (CSV, PDF, etc.) via Meta Cloud API."""
        if not archivo_bytes:
            return False
        media_id = await self._subir_media(archivo_bytes, mime_type, filename=filename)
        if not media_id:
            return False
        doc_payload: dict = {"id": media_id, "filename": filename}
        if caption:
            doc_payload["caption"] = caption[:1024]
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "document",
            "document": doc_payload,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(self.url_envio, json=payload, headers=headers)
                if r.status_code not in (200, 201):
                    logger.error(f"[META] Error {r.status_code} enviando documento: {r.text[:200]}")
                    return False
                logger.info(f"[META] Documento enviado a {telefono}: {filename}")
                return True
        except Exception as e:
            logger.error(f"[META] Excepción enviando documento ({type(e).__name__}): {e}")
            return False
