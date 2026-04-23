# agent/creativos/pendientes.py — Helper centralizado de pendientes creativos

"""
Cada módulo creativo (imagen, voz, pdf, video, video_avatar, bg_remove) mantiene
su propio dict `_PENDIENTES[telefono]` con el flujo preparar→confirmar.

Problema que resuelve este módulo: si el usuario prepara una acción (ej: video
avatar 80cr) y luego prepara otra (ej: video genérico 50cr) sin cancelar la
primera, ambos pendientes quedan vivos. Cuando el usuario escribe "confirmar",
el orden de precedencia en main.py elige uno arbitrariamente — puede no ser
el que el usuario acaba de preparar.

Regla: **un solo pendiente activo por teléfono**. Al llamar cualquier
`preparar_X`, el módulo llama a `cancelar_otros_pendientes(telefono)` primero
para limpiar pendientes de otros tipos. El último pedido siempre gana.

Los imports son diferidos (dentro de la función) para evitar ciclos con los
módulos que a su vez importan desde este.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dona")


# Etiquetas legibles para cada tipo de pendiente — se usan en el preview
# cuando avisamos al usuario "reemplacé tu pedido anterior de X".
_ETIQUETAS = {
    "imagen": "imagen",
    "voz": "nota de voz",
    "documento": "documento",
    "video": "video",
    "video_avatar": "video con avatar",
    "bg_remove": "quitar fondo",
}


def _tipo_pendiente_activo(telefono: str) -> str | None:
    """Devuelve el tipo del pendiente actual si existe, o None."""
    from agent.creativos import imagen, voz, pdf, video, video_avatar, bg_remove
    if imagen.obtener_pendiente(telefono):
        return "imagen"
    if voz.obtener_pendiente(telefono):
        return "voz"
    if pdf.obtener_pendiente(telefono):
        return "documento"
    if video.obtener_pendiente(telefono):
        return "video"
    if video_avatar.obtener_pendiente(telefono):
        return "video_avatar"
    if bg_remove.obtener_pendiente(telefono):
        return "bg_remove"
    return None


def cancelar_otros_pendientes(telefono: str, excepto: str = "") -> str | None:
    """
    Cancela todos los pendientes del teléfono excepto el tipo `excepto`.

    Retorna la etiqueta legible del tipo cancelado (ej: "video con avatar")
    si había uno vivo, o None si no había nada que cancelar. Esa etiqueta se
    usa en el preview para transparencia: "reemplacé tu pedido anterior (X)".

    `excepto` está para uso futuro — hoy ningún caller lo setea porque cada
    preparar_X cancela todo y luego guarda el suyo propio (el orden garantiza
    que no se borre el que se acaba de crear).
    """
    from agent.creativos import imagen, voz, pdf, video, video_avatar, bg_remove

    tipo_cancelado: str | None = None

    if excepto != "imagen" and imagen.cancelar_imagen(telefono):
        tipo_cancelado = "imagen"
    if excepto != "voz" and voz.cancelar_voz(telefono):
        tipo_cancelado = "voz"
    if excepto != "documento" and pdf.cancelar_documento(telefono):
        tipo_cancelado = "documento"
    if excepto != "video" and video.cancelar_video(telefono):
        tipo_cancelado = "video"
    if excepto != "video_avatar" and video_avatar.cancelar_video_avatar(telefono):
        tipo_cancelado = "video_avatar"
    if excepto != "bg_remove" and bg_remove.cancelar_bg_remove(telefono):
        tipo_cancelado = "bg_remove"

    if tipo_cancelado:
        logger.info(f"[PENDIENTES] Cancelado {tipo_cancelado} previo de {telefono}")
        return _ETIQUETAS.get(tipo_cancelado, tipo_cancelado)
    return None


def hay_pendiente_activo(telefono: str) -> bool:
    """True si el teléfono tiene cualquier pendiente creativo vivo."""
    return _tipo_pendiente_activo(telefono) is not None


def cancelar_todos(telefono: str) -> str | None:
    """
    Cancela TODO pendiente del teléfono. Usado cuando el usuario dice
    "cancelar" sin un tipo específico. Retorna etiqueta del último tipo
    cancelado o None.
    """
    return cancelar_otros_pendientes(telefono, excepto="")
