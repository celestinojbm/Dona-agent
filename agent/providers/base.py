# agent/providers/base.py — Clase base para proveedores de WhatsApp
# Generado por AgentKit

"""
Define la interfaz común que todos los proveedores de WhatsApp deben implementar.
Esto permite cambiar de proveedor sin modificar el resto del código.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from fastapi import Request


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
    """Interfaz que cada proveedor de WhatsApp debe implementar."""

    @abstractmethod
    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """Extrae y normaliza mensajes del payload del webhook."""
        ...

    @abstractmethod
    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envía un mensaje de texto. Retorna True si fue exitoso."""
        ...

    async def enviar_botones(
        self, telefono: str, texto: str, botones: list[BotonRespuesta]
    ) -> bool:
        """Envía mensaje con botones interactivos (max 3). Fallback a texto si no soportado."""
        # Fallback por defecto: enviar como texto con opciones numeradas
        opciones = "\n".join(f"{i+1}. {b.titulo}" for i, b in enumerate(botones))
        return await self.enviar_mensaje(telefono, f"{texto}\n\n{opciones}")

    async def enviar_lista(
        self, telefono: str, texto: str, boton_menu: str, opciones: list[OpcionLista]
    ) -> bool:
        """Envía mensaje con lista desplegable (max 10). Fallback a texto si no soportado."""
        items = "\n".join(
            f"• {o.titulo}" + (f" — {o.descripcion}" if o.descripcion else "")
            for o in opciones
        )
        return await self.enviar_mensaje(telefono, f"{texto}\n\n{items}")

    async def validar_webhook(self, request: Request) -> dict | int | None:
        """Verificación GET del webhook (solo Meta la requiere). Retorna respuesta o None."""
        return None
