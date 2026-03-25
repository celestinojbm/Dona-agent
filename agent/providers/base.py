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

    async def validar_webhook(self, request: Request) -> dict | int | None:
        """Verificación GET del webhook (solo Meta la requiere). Retorna respuesta o None."""
        return None
