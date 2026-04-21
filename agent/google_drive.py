# agent/google_drive.py — Subir archivos al Google Drive del usuario

"""
Permite a Dona crear/subir archivos (PDFs, CSVs, imágenes) al Drive del usuario
y devolver un link compartible. Reutiliza el token OAuth de Google Calendar.

Requiere scope: https://www.googleapis.com/auth/drive.file
(solo da acceso a archivos creados por Dona, no al resto del Drive del usuario).
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger("dona")

_DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_DRIVE_API = "https://www.googleapis.com/drive/v3/files"


async def _token(telefono: str) -> str | None:
    """Token OAuth válido (con refresh automático)."""
    from agent.google_calendar import _obtener_token_valido
    return await _obtener_token_valido(telefono)


async def subir_archivo(
    telefono: str,
    nombre: str,
    contenido: bytes,
    mime_type: str = "application/octet-stream",
    carpeta_id: Optional[str] = None,
    descripcion: str = "",
) -> dict | None:
    """
    Sube un archivo al Drive del usuario usando multipart upload.

    Args:
        telefono: usuario dueño del Drive
        nombre: nombre del archivo (ej: "cotizacion_123.pdf")
        contenido: bytes del archivo
        mime_type: MIME type (ej: "application/pdf", "text/csv")
        carpeta_id: si se indica, sube dentro de esa carpeta; si no, raíz
        descripcion: descripción opcional del archivo

    Returns:
        dict con {id, name, webViewLink, webContentLink} o None si falló.
    """
    tok = await _token(telefono)
    if not tok:
        return None
    if not contenido:
        return None

    metadata: dict = {"name": nombre, "mimeType": mime_type}
    if carpeta_id:
        metadata["parents"] = [carpeta_id]
    if descripcion:
        metadata["description"] = descripcion[:2048]

    # Multipart upload: boundary en RFC 2387 / Google multipart
    boundary = "dona-drive-upload-boundary"
    cuerpo = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + contenido + f"\r\n--{boundary}--".encode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                _DRIVE_UPLOAD,
                params={
                    "uploadType": "multipart",
                    "fields": "id,name,webViewLink,webContentLink,mimeType",
                },
                content=cuerpo,
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": f"multipart/related; boundary={boundary}",
                },
            )
            if resp.status_code == 403:
                logger.warning(f"[DRIVE] 403 — falta scope drive.file (re-autorizar)")
                return None
            if resp.status_code not in (200, 201):
                logger.error(f"[DRIVE] Upload falló {resp.status_code}: {resp.text[:300]}")
                return None
            data = resp.json()
            logger.info(f"[DRIVE] Subido '{nombre}' → id={data.get('id')}")
            return data
    except Exception as e:
        logger.error(f"[DRIVE] Excepción subiendo ({type(e).__name__}): {e}")
        return None


async def compartir_con_link(telefono: str, file_id: str) -> str | None:
    """
    Da permiso de lectura a "cualquiera con el link" y devuelve el webViewLink.

    Úsalo cuando el usuario quiere enviar por WhatsApp un link a un PDF/doc
    que Dona acaba de generar y subir al Drive.
    """
    tok = await _token(telefono)
    if not tok:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1) Crear permiso "anyone with link"
            r_perm = await client.post(
                f"{_DRIVE_API}/{file_id}/permissions",
                json={"role": "reader", "type": "anyone"},
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/json",
                },
            )
            if r_perm.status_code not in (200, 201, 204):
                logger.error(f"[DRIVE] Permiso falló {r_perm.status_code}: {r_perm.text[:200]}")
                return None
            # 2) Obtener webViewLink actualizado
            r_meta = await client.get(
                f"{_DRIVE_API}/{file_id}",
                params={"fields": "webViewLink"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            if r_meta.status_code != 200:
                return None
            return r_meta.json().get("webViewLink")
    except Exception as e:
        logger.error(f"[DRIVE] Excepción compartiendo ({type(e).__name__}): {e}")
        return None


async def listar_sheets(telefono: str, limite: int = 20) -> list[dict]:
    """
    Lista los Google Sheets del usuario (top `limite` más recientes).
    Usa scope drive.readonly. Devuelve [{id, name, modifiedTime}, ...].
    """
    tok = await _token(telefono)
    if not tok:
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _DRIVE_API,
                params={
                    "q": "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
                    "orderBy": "modifiedTime desc",
                    "pageSize": min(limite, 100),
                    "fields": "files(id,name,modifiedTime)",
                },
                headers={"Authorization": f"Bearer {tok}"},
            )
            if resp.status_code != 200:
                logger.error(f"[DRIVE] listar_sheets {resp.status_code}: {resp.text[:200]}")
                return []
            return resp.json().get("files", [])
    except Exception as e:
        logger.error(f"[DRIVE] Excepción listando sheets ({type(e).__name__}): {e}")
        return []
