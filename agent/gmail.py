# agent/gmail.py — Integración con Gmail API
"""
Lee y envía correos usando el mismo token OAuth que Calendar y Sheets.
Reutiliza _obtener_token_valido de google_calendar.py.

Scopes necesarios (agregados en google_calendar.py):
  - https://www.googleapis.com/auth/gmail.readonly
  - https://www.googleapis.com/auth/gmail.send
"""

import asyncio
import base64
import logging
import re
from email.mime.text import MIMEText
from email.utils import formatdate

import httpx

logger = logging.getLogger("agentkit")

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailScopeError(Exception):
    """El token no tiene los scopes de Gmail. El usuario debe re-autorizar."""
    pass


# ── Helpers internos ──────────────────────────────────────────────────────────

async def _token(telefono: str) -> str | None:
    """Token válido de Google con refresh automático."""
    from agent.google_calendar import _obtener_token_valido
    return await _obtener_token_valido(telefono)


def _header(headers: list[dict], name: str) -> str:
    """Extrae el valor de un header por nombre (case-insensitive)."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def _decodificar_cuerpo(payload: dict) -> str:
    """
    Extrae el texto del payload de un mensaje Gmail.
    Prioriza text/plain sobre text/html. Maneja mensajes simples y multipart.
    """
    mime_type = payload.get("mimeType", "")

    # Mensaje simple con cuerpo directo
    body_data = payload.get("body", {}).get("data", "")
    if body_data and "text/plain" in mime_type:
        try:
            return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        except Exception:
            return ""

    # Multipart: buscar recursivamente
    partes = payload.get("parts", [])
    if not partes:
        # Intentar body aunque sea html
        if body_data:
            try:
                texto = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
                # Limpiar HTML básico
                texto = re.sub(r"<[^>]+>", " ", texto)
                texto = re.sub(r"\s+", " ", texto).strip()
                return texto
            except Exception:
                return ""
        return ""

    # Primero buscar text/plain
    for parte in partes:
        if parte.get("mimeType") == "text/plain":
            texto = _decodificar_cuerpo(parte)
            if texto:
                return texto

    # Si no hay text/plain, buscar recursivamente en todas las partes
    for parte in partes:
        texto = _decodificar_cuerpo(parte)
        if texto:
            return texto

    return ""


def _formatear_fecha(date_str: str) -> str:
    """Simplifica la fecha del header Date de Gmail para mostrar al usuario."""
    # Date header ejemplo: "Sun, 5 Apr 2026 14:32:00 +0000"
    try:
        # Extraer la parte legible
        partes = date_str.strip().split(",")
        if len(partes) > 1:
            return partes[1].strip()[:20]
        return date_str[:20]
    except Exception:
        return date_str[:20]


async def _obtener_metadata_mensaje(
    client: httpx.AsyncClient,
    token: str,
    message_id: str,
) -> dict | None:
    """Obtiene metadatos (From, Subject, Date, Snippet) de un mensaje."""
    resp = await client.get(
        f"{_GMAIL_API}/messages/{message_id}",
        params={
            "format": "metadata",
            "metadataHeaders": "From,Subject,Date",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 403:
        raise GmailScopeError("Token sin scope de Gmail")
    if resp.status_code != 200:
        return None

    data = resp.json()
    headers = data.get("payload", {}).get("headers", [])
    return {
        "id": data.get("id", ""),
        "thread_id": data.get("threadId", ""),
        "from": _header(headers, "From"),
        "subject": _header(headers, "Subject") or "(sin asunto)",
        "date": _formatear_fecha(_header(headers, "Date")),
        "snippet": data.get("snippet", ""),
        "unread": "UNREAD" in data.get("labelIds", []),
    }


# ── API pública ───────────────────────────────────────────────────────────────

async def listar_correos(
    telefono: str,
    max_results: int = 8,
    solo_no_leidos: bool = True,
    solo_importantes: bool = True,
    after_timestamp: "datetime | None" = None,
) -> list[dict]:
    """
    Lista correos del inbox.

    Args:
        solo_importantes:  Si True (default), filtra category:primary — excluye
                           Promociones, Social, Updates, Foros.
        after_timestamp:   Si se proporciona, solo devuelve correos posteriores a
                           esta fecha (en UTC). Evita repetir correos ya mostrados.

    Returns:
        Lista de dicts con id, from, subject, date, snippet, unread.

    Raises:
        GmailScopeError: si el token no tiene scope de Gmail.
    """
    tok = await _token(telefono)
    if not tok:
        return []

    partes = ["in:inbox"]
    if solo_no_leidos:
        partes.append("is:unread")
    if solo_importantes:
        partes.append("category:primary")
    if after_timestamp:
        # Gmail acepta Unix timestamp en el operador after:
        epoch = int(after_timestamp.timestamp())
        partes.append(f"after:{epoch}")
    query = " ".join(partes)

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Obtener lista de IDs
        resp = await client.get(
            f"{_GMAIL_API}/messages",
            params={"q": query, "maxResults": max_results},
            headers={"Authorization": f"Bearer {tok}"},
        )
        if resp.status_code == 403:
            raise GmailScopeError("Token sin scope de Gmail")
        if resp.status_code != 200:
            logger.error(f"Gmail list: {resp.status_code} {resp.text[:200]}")
            return []

        messages = resp.json().get("messages", [])
        if not messages:
            return []

        # 2. Obtener metadata en paralelo (máx 8 en paralelo)
        tasks = [
            _obtener_metadata_mensaje(client, tok, m["id"])
            for m in messages[:max_results]
        ]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)

        correos = []
        for r in resultados:
            if isinstance(r, GmailScopeError):
                raise r
            if isinstance(r, dict):
                correos.append(r)

        return correos


async def leer_correo(
    telefono: str,
    message_id: str,
) -> dict | None:
    """
    Lee el contenido completo de un correo.

    Returns:
        Dict con id, thread_id, from, subject, date, cuerpo, message_id_header.
    """
    tok = await _token(telefono)
    if not tok:
        return None

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_GMAIL_API}/messages/{message_id}",
            params={"format": "full"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        if resp.status_code == 403:
            raise GmailScopeError("Token sin scope de Gmail")
        if resp.status_code != 200:
            logger.error(f"Gmail get: {resp.status_code} {resp.text[:200]}")
            return None

        data = resp.json()
        headers = data.get("payload", {}).get("headers", [])
        cuerpo = _decodificar_cuerpo(data.get("payload", {}))

        return {
            "id": data.get("id", ""),
            "thread_id": data.get("threadId", ""),
            "from": _header(headers, "From"),
            "subject": _header(headers, "Subject") or "(sin asunto)",
            "date": _formatear_fecha(_header(headers, "Date")),
            "cuerpo": cuerpo[:2000] if cuerpo else "(sin contenido)",
            "message_id_header": _header(headers, "Message-ID"),
        }


async def buscar_correos(
    telefono: str,
    query_gmail: str,
    max_results: int = 8,
) -> list[dict]:
    """
    Busca correos usando query de Gmail (ej: "from:juan subject:reunión").

    Raises:
        GmailScopeError: si el token no tiene scope de Gmail.
    """
    tok = await _token(telefono)
    if not tok:
        return []

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_GMAIL_API}/messages",
            params={"q": query_gmail, "maxResults": max_results},
            headers={"Authorization": f"Bearer {tok}"},
        )
        if resp.status_code == 403:
            raise GmailScopeError("Token sin scope de Gmail")
        if resp.status_code != 200:
            logger.error(f"Gmail search: {resp.status_code} {resp.text[:200]}")
            return []

        messages = resp.json().get("messages", [])
        if not messages:
            return []

        tasks = [
            _obtener_metadata_mensaje(client, tok, m["id"])
            for m in messages[:max_results]
        ]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in resultados if isinstance(r, dict)]


async def enviar_correo(
    telefono: str,
    destinatario: str,
    asunto: str,
    cuerpo: str,
    thread_id: str = "",
    reply_message_id: str = "",
) -> bool:
    """
    Envía un correo. Para replies, pasa thread_id y reply_message_id.

    Returns:
        True si fue exitoso.
    """
    tok = await _token(telefono)
    if not tok:
        return False

    # Construir el mensaje RFC 2822
    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg["Date"] = formatdate(localtime=False)
    if reply_message_id:
        msg["In-Reply-To"] = reply_message_id
        msg["References"] = reply_message_id

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload: dict = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_GMAIL_API}/messages/send",
            json=payload,
            headers={
                "Authorization": f"Bearer {tok}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code == 403:
            raise GmailScopeError("Token sin scope de Gmail")
        if resp.status_code not in (200, 201):
            logger.error(f"Gmail send: {resp.status_code} {resp.text[:300]}")
            return False

        logger.info(f"Correo enviado para {telefono} → {destinatario}")
        return True


def _traducir_query_natural(query_natural: str) -> str:
    """
    Traduce una query en lenguaje natural a sintaxis de Gmail.
    Conversión heurística básica.
    """
    q = query_natural.lower()
    partes = []

    # Patrones comunes
    if "de " in q:
        match = re.search(r"de ([a-záéíóúñ@.\w]+)", q)
        if match:
            partes.append(f"from:{match.group(1)}")

    if "asunto" in q or "subject" in q:
        match = re.search(r"(?:asunto|subject)[:\s]+([^\s,]+)", q)
        if match:
            partes.append(f"subject:{match.group(1)}")

    if "no leído" in q or "sin leer" in q or "nuevos" in q:
        partes.append("is:unread")

    if "hoy" in q:
        partes.append("newer_than:1d")
    elif "esta semana" in q:
        partes.append("newer_than:7d")
    elif "este mes" in q:
        partes.append("newer_than:30d")

    if "adjunto" in q or "archivo" in q:
        partes.append("has:attachment")

    # Si no se detectó nada específico, hacer búsqueda general
    if not partes:
        # Remover palabras comunes y usar el resto como texto libre
        palabras_ignorar = {"correo", "email", "busca", "muéstrame", "sobre", "con", "que", "los", "mis"}
        palabras = [w for w in q.split() if w not in palabras_ignorar and len(w) > 2]
        return " ".join(palabras[:5]) if palabras else "in:inbox"

    return " ".join(partes)
