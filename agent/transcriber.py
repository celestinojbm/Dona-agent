# agent/transcriber.py — Transcripción de notas de voz con OpenAI Whisper
# Generado por AgentKit

"""
Descarga el audio de WhatsApp y lo transcribe a texto usando OpenAI Whisper API.
"""

import os
import io
import logging
import httpx
from openai import AsyncOpenAI

logger = logging.getLogger("agentkit")

# Cliente de OpenAI para Whisper
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def descargar_audio_whapi(audio_id: str, token: str) -> bytes | None:
    """
    Descarga un archivo de audio de Whapi usando su ID.

    Args:
        audio_id: ID del archivo de audio en Whapi
        token: Token de autenticación de Whapi

    Returns:
        Bytes del audio, o None si falló
    """
    url = f"https://gate.whapi.cloud/files/{audio_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                logger.info(f"Audio descargado: {len(r.content)} bytes")
                return r.content
            else:
                logger.error(f"Error descargando audio de Whapi: {r.status_code} — {r.text}")
                return None
    except Exception as e:
        logger.error(f"Excepción descargando audio ({type(e).__name__}): {e}")
        return None


async def transcribir_audio(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str | None:
    """
    Transcribe audio a texto usando OpenAI Whisper API.

    Args:
        audio_bytes: Bytes del archivo de audio
        mime_type: Tipo MIME del audio (WhatsApp usa audio/ogg; codecs=opus)

    Returns:
        Texto transcrito, o None si falló
    """
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY no configurada — transcripción no disponible")
        return None

    # Determinar extensión según mime type
    if "ogg" in mime_type or "opus" in mime_type:
        extension = "ogg"
    elif "mp4" in mime_type or "m4a" in mime_type:
        extension = "m4a"
    elif "mp3" in mime_type:
        extension = "mp3"
    elif "wav" in mime_type:
        extension = "wav"
    else:
        extension = "ogg"  # WhatsApp usa OGG por defecto

    try:
        archivo = io.BytesIO(audio_bytes)
        archivo.name = f"audio.{extension}"

        response = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=archivo,
            language="es"  # Español
        )

        texto = response.text.strip()
        logger.info(f"Audio transcrito: \"{texto[:80]}{'...' if len(texto) > 80 else ''}\"")
        return texto if texto else None

    except Exception as e:
        logger.error(f"Error transcribiendo audio con Whisper ({type(e).__name__}): {e}")
        return None


async def procesar_audio_whapi(audio_id: str, mime_type: str, token: str) -> str | None:
    """
    Pipeline completo: descarga el audio de Whapi y lo transcribe.

    Returns:
        Texto transcrito, o None si falló algún paso
    """
    audio_bytes = await descargar_audio_whapi(audio_id, token)
    if not audio_bytes:
        return None
    return await transcribir_audio(audio_bytes, mime_type)
