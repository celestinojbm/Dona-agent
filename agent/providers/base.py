# agent/providers/base.py — Clase base para proveedores de WhatsApp
# Dona

"""
Define la interfaz común que todos los proveedores de WhatsApp deben implementar.
Esto permite cambiar de proveedor sin modificar el resto del código.

Los métodos públicos `enviar_*` son el CHOKE POINT del gate central de
envíos (agent/envio_gate.py — Fase 0 · 2.1): consultan `puede_enviar()` y
solo entonces delegan en `_enviar_*_impl`. Los proveedores concretos
implementan los `_enviar_*_impl`; NUNCA deben sobreescribir los públicos,
o el opt-out TCPA dejaría de aplicarse.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from fastapi import Request

from agent.envio_gate import puede_enviar, registrar_envio_realizado


@dataclass
class MensajeEntrante:
    """Mensaje normalizado — mismo formato sin importar el proveedor."""
    telefono: str       # Número del remitente
    texto: str          # Contenido del mensaje de texto
    mensaje_id: str     # ID único del mensaje
    es_propio: bool     # True si lo envió el agente (se ignora)
    timestamp: int = field(default=0)       # Timestamp Unix UTC del mensaje (de WhatsApp)
    audio_id: str = field(default="")       # ID del audio en Whapi (si es nota de voz)
    audio_mime: str = field(default="")     # Tipo MIME del audio
    image_id: str = field(default="")       # Media ID de la imagen (Meta API)
    image_caption: str = field(default="") # Caption/texto adjunto a la imagen


@dataclass
class BotonRespuesta:
    """Botón interactivo para mensajes de WhatsApp."""
    id: str          # ID único del botón (max 256 chars)
    titulo: str      # Texto visible (max 20 chars)


@dataclass
class OpcionLista:
    """Opción dentro de una lista interactiva de WhatsApp."""
    id: str          # ID único (max 200 chars)
    titulo: str      # Texto visible (max 24 chars)
    descripcion: str = ""  # Descripción opcional (max 72 chars)


class ProveedorWhatsApp(ABC):
    """Interfaz que cada proveedor de WhatsApp debe implementar.

    Los métodos públicos `enviar_*` aplican el gate central y NO se
    sobreescriben; los proveedores implementan los `_enviar_*_impl`.
    """

    @abstractmethod
    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """Extrae y normaliza mensajes del payload del webhook."""
        ...

    # ── Métodos públicos (gateados) ──────────────────────────────────────

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envía un mensaje de texto. Retorna True si fue exitoso.
        Retorna False sin tocar la API si el gate bloquea el envío."""
        if not await puede_enviar(telefono):
            return False
        ok = await self._enviar_mensaje_impl(telefono, mensaje)
        if ok:
            await registrar_envio_realizado(telefono)
        return ok

    async def enviar_botones(
        self, telefono: str, texto: str, botones: list[BotonRespuesta]
    ) -> bool:
        """Envía mensaje con botones interactivos (max 3). Fallback a texto si no soportado."""
        if not await puede_enviar(telefono):
            return False
        ok = await self._enviar_botones_impl(telefono, texto, botones)
        if ok:
            await registrar_envio_realizado(telefono)
        return ok

    async def enviar_lista(
        self, telefono: str, texto: str, boton_menu: str, opciones: list[OpcionLista]
    ) -> bool:
        """Envía mensaje con lista desplegable (max 10). Fallback a texto si no soportado."""
        if not await puede_enviar(telefono):
            return False
        ok = await self._enviar_lista_impl(telefono, texto, boton_menu, opciones)
        if ok:
            await registrar_envio_realizado(telefono)
        return ok

    async def enviar_audio(self, telefono: str, audio_bytes: bytes, mime_type: str = "audio/ogg") -> bool:
        """Envía una nota de voz. Los proveedores sin soporte devuelven False (no fallback a texto;
        el caller decide si manda el texto por separado)."""
        if not await puede_enviar(telefono):
            return False
        ok = await self._enviar_audio_impl(telefono, audio_bytes, mime_type)
        if ok:
            await registrar_envio_realizado(telefono)
        return ok

    async def enviar_documento(
        self, telefono: str, archivo_bytes: bytes, filename: str, mime_type: str = "text/csv", caption: str = ""
    ) -> bool:
        """Envía un documento adjunto. Devuelve False si no hay soporte nativo."""
        if not await puede_enviar(telefono):
            return False
        ok = await self._enviar_documento_impl(telefono, archivo_bytes, filename, mime_type, caption)
        if ok:
            await registrar_envio_realizado(telefono)
        return ok

    async def enviar_imagen(
        self, telefono: str, url: str = "", imagen_bytes: bytes = b"",
        caption: str = "", mime_type: str = "image/png",
    ) -> bool:
        """Envía una imagen (ver _enviar_imagen_impl)."""
        if not await puede_enviar(telefono):
            return False
        ok = await self._enviar_imagen_impl(telefono, url, imagen_bytes, caption, mime_type)
        if ok:
            await registrar_envio_realizado(telefono)
        return ok

    async def enviar_video(
        self, telefono: str, url: str = "", video_bytes: bytes = b"",
        caption: str = "", mime_type: str = "video/mp4",
    ) -> bool:
        """Envía un video (ver _enviar_video_impl)."""
        if not await puede_enviar(telefono):
            return False
        ok = await self._enviar_video_impl(telefono, url, video_bytes, caption, mime_type)
        if ok:
            await registrar_envio_realizado(telefono)
        return ok

    # ── Implementaciones por proveedor ───────────────────────────────────

    @abstractmethod
    async def _enviar_mensaje_impl(self, telefono: str, mensaje: str) -> bool:
        """Transporte real del mensaje de texto. Retorna True si fue exitoso."""
        ...

    async def _enviar_botones_impl(
        self, telefono: str, texto: str, botones: list[BotonRespuesta]
    ) -> bool:
        # Fallback por defecto: enviar como texto con opciones numeradas.
        # Llama al _impl (no al público) — el gate ya corrió una vez.
        opciones = "\n".join(f"{i+1}. {b.titulo}" for i, b in enumerate(botones))
        return await self._enviar_mensaje_impl(telefono, f"{texto}\n\n{opciones}")

    async def _enviar_lista_impl(
        self, telefono: str, texto: str, boton_menu: str, opciones: list[OpcionLista]
    ) -> bool:
        items = "\n".join(
            f"• {o.titulo}" + (f" — {o.descripcion}" if o.descripcion else "")
            for o in opciones
        )
        return await self._enviar_mensaje_impl(telefono, f"{texto}\n\n{items}")

    async def _enviar_audio_impl(self, telefono: str, audio_bytes: bytes, mime_type: str = "audio/ogg") -> bool:
        return False

    async def _enviar_documento_impl(
        self, telefono: str, archivo_bytes: bytes, filename: str, mime_type: str = "text/csv", caption: str = ""
    ) -> bool:
        return False

    async def _enviar_imagen_impl(
        self, telefono: str, url: str = "", imagen_bytes: bytes = b"",
        caption: str = "", mime_type: str = "image/png",
    ) -> bool:
        """
        Envía una imagen. El proveedor decide si usar `url` (si es pública,
        preferente — más barato que reupload) o `imagen_bytes` (fallback).
        Default: sin soporte → devolver False; el caller puede mandar la URL
        como texto.
        """
        return False

    async def _enviar_video_impl(
        self, telefono: str, url: str = "", video_bytes: bytes = b"",
        caption: str = "", mime_type: str = "video/mp4",
    ) -> bool:
        """
        Envía un video. El proveedor decide si usar `url` (pública, preferente
        — WhatsApp la descarga directamente) o `video_bytes` (fallback, base64
        o multipart según proveedor). Default: sin soporte → False.
        """
        return False

    async def validar_webhook(self, request: Request) -> dict | int | None:
        """Verificación GET del webhook (solo Meta la requiere). Retorna respuesta o None."""
        return None
