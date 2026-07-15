# agent/google_reauth.py — Mensaje de re-autorización de Google (Fase 2 · B2)

"""
Helper que genera el resultado de tool_use cuando el token de Google no tiene
los scopes necesarios (GmailScopeError y equivalentes).

Extraído de `agent/brain.py` (Fase 2 · Bloque 2) SIN cambios de comportamiento:
mismo link, mismo formato, mismos defaults de BASE_URL. Vive fuera de `brain`
para que los handlers de tools —que no deben depender de `brain`— puedan
reutilizarlo. `brain` lo re-importa con alias `_resultado_reauth_google` para
no tocar sus call sites existentes. Importar este módulo no toca red.
"""

import os
import urllib.parse


def resultado_reauth_google(telefono: str) -> str:
    """
    Genera el resultado de tool_use para cuando el token no tiene los scopes necesarios.
    Usa el mismo patrón que funciona para Calendar: URL como texto plano.
    """
    base_url = (
        os.getenv("BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or "http://localhost:8000"
    ).rstrip("/")
    link = f"{base_url}/auth/google/login?telefono={urllib.parse.quote(telefono)}"
    return (
        f"El token de Google no tiene los permisos necesarios. "
        f"Link de re-autorización generado: {link}\n\n"
        "INSTRUCCIÓN CRÍTICA: Muestra la URL exacta como texto plano, sin formato Markdown. "
        "NO uses [texto](url). La URL debe aparecer directamente para que WhatsApp la haga clickeable. "
        "Formato exacto a usar:\n"
        f"'Para acceder a tu Gmail necesito que re-autorices Google. Abre este enlace:\n{link}'"
    )
