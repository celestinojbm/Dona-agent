# agent/inbound_tokens.py — Tokens HMAC para webhooks inbound (Zapier/Make/n8n)

"""
Permite a un usuario de Dona generar una URL pública firmada (sin intervención
del dev) que cualquier servicio externo puede llamar para enviar mensajes
proactivos al WhatsApp del usuario.

Ejemplo de uso desde Zapier:
    POST https://dona.app/webhook/inbound/<token>
    Content-Type: application/json
    {"mensaje": "Nueva venta de $100 en Shopify"}

El token codifica (telefono, nonce, timestamp_emision) y va firmado con HMAC-SHA256.
No tiene expiración por diseño — el usuario puede revocarlos rotando `INBOUND_WEBHOOK_SECRET`.

Secreto: lee INBOUND_WEBHOOK_SECRET del entorno; si no está, usa un valor
derivado + warning (solo para desarrollo).
"""

import os
import base64
import hmac
import hashlib
import secrets
import logging

logger = logging.getLogger("dona")


def _secreto() -> bytes:
    """Devuelve el secreto HMAC configurado, o uno derivado en dev con warning."""
    secret = os.getenv("INBOUND_WEBHOOK_SECRET", "").strip()
    if secret:
        return secret.encode("utf-8")
    # Fallback en dev: derivar de ADMIN_TOKEN si existe, sino un valor fijo de dev.
    # En producción siempre debe estar configurado INBOUND_WEBHOOK_SECRET.
    admin = os.getenv("ADMIN_TOKEN", "").strip()
    if admin:
        logger.warning("[INBOUND] INBOUND_WEBHOOK_SECRET no configurado, derivando de ADMIN_TOKEN")
        return hashlib.sha256(b"inbound-webhook-derived|" + admin.encode("utf-8")).digest()
    logger.warning("[INBOUND] INBOUND_WEBHOOK_SECRET no configurado — usando valor de desarrollo INSEGURO")
    return b"dona-inbound-dev-secret-do-not-use-in-prod"


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def generar_token(telefono: str) -> str:
    """
    Genera un token firmado para el teléfono dado.

    Formato: base64url(nonce|telefono).hmac_hex

    Args:
        telefono: número E.164 sin '+' (ej: "14076936023")

    Returns:
        Token opaco listo para embeberse en la URL `/webhook/inbound/<token>`.
    """
    if not telefono:
        raise ValueError("telefono vacío")
    nonce = secrets.token_urlsafe(12)
    payload = f"{nonce}|{telefono}".encode("utf-8")
    firma = hmac.new(_secreto(), payload, hashlib.sha256).hexdigest()
    return f"{_b64u(payload)}.{firma}"


def verificar_token(token: str) -> str | None:
    """
    Verifica el token y devuelve el teléfono asociado, o None si es inválido.

    Usa comparación timing-safe para la firma.
    """
    if not token or "." not in token:
        return None
    try:
        payload_b64, firma_recibida = token.split(".", 1)
        payload = _b64u_decode(payload_b64)
        firma_esperada = hmac.new(_secreto(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma_esperada, firma_recibida):
            return None
        partes = payload.decode("utf-8").split("|", 1)
        if len(partes) != 2:
            return None
        _, telefono = partes
        return telefono if telefono else None
    except Exception as e:
        logger.debug(f"[INBOUND] Token inválido ({type(e).__name__}): {e}")
        return None
