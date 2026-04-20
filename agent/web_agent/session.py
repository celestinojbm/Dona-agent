# agent/web_agent/session.py — Sesiones cifradas por usuario (scaffold)

"""
Persistencia de cookies/localStorage para que el web-agent pueda
retomar sesiones sin volver a loguear.

Diseño (NO implementado aún — placeholder para cuando haya primer caso real):
  - Una tabla nueva `web_sessions(telefono, dominio, cookies_cifradas, creado, actualizado)`.
  - Cifrado con `agent.crypto.cifrar_texto` / `descifrar_texto` (Fernet con ENCRYPTION_KEY).
  - Las cookies se serializan a JSON antes de cifrar.
  - Borrado automático cuando el usuario ejecuta `dona borrar mis datos` (integrar en
    `borrar_datos_usuario` de agent/memory.py).

Este archivo deja las firmas públicas listas. Implementarlas cuando se cablee
el primer caso de uso real (evita agregar código muerto y migraciones
innecesarias a la DB hoy).
"""

import logging

logger = logging.getLogger("agentkit")


async def cargar_sesion(telefono: str, dominio: str) -> list[dict]:
    """Devuelve cookies guardadas para (telefono, dominio) o [] si no hay."""
    logger.debug(f"[WEB_AGENT] cargar_sesion stub: {telefono[:4]}*** dominio={dominio}")
    return []


async def guardar_sesion(telefono: str, dominio: str, cookies: list[dict]) -> None:
    """Cifra y persiste las cookies actualizadas."""
    logger.debug(f"[WEB_AGENT] guardar_sesion stub: {telefono[:4]}*** dominio={dominio} cookies={len(cookies)}")
    return None


async def borrar_sesiones(telefono: str) -> int:
    """Borra todas las sesiones del usuario. Retorna la cantidad borrada.

    Se llama desde `borrar_datos_usuario` cuando el usuario ejerce su derecho
    CCPA/GDPR de eliminación.
    """
    logger.debug(f"[WEB_AGENT] borrar_sesiones stub: {telefono[:4]}***")
    return 0
