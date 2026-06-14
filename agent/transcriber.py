# agent/transcriber.py — Transcripción de notas de voz (OpenAI Whisper preferente, Groq fallback)
"""
Descarga el audio de WhatsApp (Whapi o Meta API) y lo transcribe.

Orden de preferencia:
  1. OpenAI Whisper (whisper-1) — si OPENAI_API_KEY está configurada.
  2. Groq Whisper (whisper-large-v3) — fallback gratuito si OPENAI no está o falla.

Si ninguno está configurado, devuelve None y loggea una advertencia.
"""

import io
import logging
import os

import httpx

logger = logging.getLogger("dona")

# Clientes inicializados de forma lazy para no crashear si las keys o los
# paquetes no están disponibles al arrancar el servidor.
_groq_client = None  # type: ignore[assignment]
_openai_client = None  # type: ignore[assignment]


def _obtener_groq_client():
    """Devuelve el cliente Groq, creándolo la primera vez que se necesita."""
    global _groq_client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    if _groq_client is None:
        try:
            from groq import AsyncGroq
        except ImportError:
            logger.error("[WHISPER] Paquete 'groq' no instalado — no se puede usar Groq Whisper")
            return None
        _groq_client = AsyncGroq(api_key=api_key)
    return _groq_client


def _obtener_openai_client():
    """Devuelve el cliente OpenAI, creándolo la primera vez que se necesita."""
    global _openai_client
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("[WHISPER] Paquete 'openai' no instalado — no se puede usar OpenAI Whisper")
            return None
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


async def descargar_audio_whapi(audio_id: str, token: str) -> bytes | None:
    """
    Descarga un archivo de audio de Whapi usando su ID.

    Args:
        audio_id: ID del archivo de audio en Whapi
        token: Token de autenticación de Whapi

    Returns:
        Bytes del audio, o None si falló
    """
    url = f"https://gate.whapi.cloud/media/{audio_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Descargando audio desde Whapi: {url}")
            r = await client.get(url, headers=headers)
            logger.info(f"Audio Whapi descargado: {r.status_code} {len(r.content)} bytes")
            if r.status_code == 200:
                return r.content
            else:
                logger.error(f"Error descargando audio de Whapi: {r.status_code} — {r.text[:200]}")
                return None
    except Exception as e:
        logger.error(f"Excepción descargando audio Whapi ({type(e).__name__}): {e}")
        return None


async def descargar_audio_meta(audio_id: str, access_token: str) -> bytes | None:
    """
    Descarga un archivo de audio de Meta Cloud API usando su media ID.

    Meta requiere dos pasos:
    1. Obtener la URL de descarga usando el media ID.
    2. Descargar el archivo desde esa URL con el mismo token.

    Args:
        audio_id: Media ID del archivo de audio en Meta
        access_token: META_ACCESS_TOKEN

    Returns:
        Bytes del audio, o None si falló
    """
    api_version = os.getenv("META_API_VERSION", "v21.0")
    url_info = f"https://graph.facebook.com/{api_version}/{audio_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Paso 1: obtener URL de descarga
            r_info = await client.get(url_info, headers=headers)
            if r_info.status_code != 200:
                logger.error(f"[META] Error obteniendo info de media {audio_id}: {r_info.status_code} {r_info.text[:200]}")
                return None

            media_url = r_info.json().get("url")
            if not media_url:
                logger.error(f"[META] No se encontró URL de descarga para media {audio_id}")
                return None

            # Paso 2: descargar el archivo
            logger.info(f"[META] Descargando audio desde: {media_url[:80]}...")
            r_audio = await client.get(media_url, headers=headers)
            if r_audio.status_code == 200:
                logger.info(f"[META] Audio descargado: {len(r_audio.content)} bytes")
                return r_audio.content
            else:
                logger.error(f"[META] Error descargando audio: {r_audio.status_code} {r_audio.text[:200]}")
                return None

    except Exception as e:
        logger.error(f"[META] Excepción descargando audio ({type(e).__name__}): {e}")
        return None


def _extension_desde_mime(mime_type: str) -> str:
    """Mapea mime type de WhatsApp a extensión de archivo para los clientes Whisper."""
    if "ogg" in mime_type or "opus" in mime_type:
        return "ogg"
    if "mp4" in mime_type or "m4a" in mime_type:
        return "m4a"
    if "mp3" in mime_type:
        return "mp3"
    if "wav" in mime_type:
        return "wav"
    return "ogg"  # WhatsApp usa OGG por defecto


async def _transcribir_con_openai(audio_bytes: bytes, extension: str) -> str | None:
    """Intenta transcribir con OpenAI Whisper. Devuelve None si falla o no está configurado."""
    openai_client = _obtener_openai_client()
    if not openai_client:
        return None
    try:
        archivo = io.BytesIO(audio_bytes)
        archivo.name = f"audio.{extension}"
        response = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=archivo,
            language="es",
            response_format="text",
        )
        texto = response.strip() if isinstance(response, str) else response.text.strip()
        if texto:
            logger.info(f"[WHISPER-OPENAI] \"{texto[:80]}{'...' if len(texto) > 80 else ''}\"")
            return texto
        return None
    except Exception as e:
        logger.error(f"[WHISPER-OPENAI] Error transcribiendo ({type(e).__name__}): {e}")
        return None


async def _transcribir_con_groq(audio_bytes: bytes, extension: str) -> str | None:
    """Intenta transcribir con Groq Whisper. Devuelve None si falla o no está configurado."""
    groq_client = _obtener_groq_client()
    if not groq_client:
        return None
    try:
        archivo = io.BytesIO(audio_bytes)
        archivo.name = f"audio.{extension}"
        response = await groq_client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=archivo,
            language="es",
            response_format="text",
        )
        texto = response.strip() if isinstance(response, str) else response.text.strip()
        if texto:
            logger.info(f"[WHISPER-GROQ] \"{texto[:80]}{'...' if len(texto) > 80 else ''}\"")
            return texto
        return None
    except Exception as e:
        logger.error(f"[WHISPER-GROQ] Error transcribiendo ({type(e).__name__}): {e}")
        return None


async def transcribir_audio(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str | None:
    """
    Transcribe audio a texto. Preferencia: OpenAI Whisper, fallback Groq Whisper.

    Args:
        audio_bytes: Bytes del archivo de audio
        mime_type: Tipo MIME del audio (WhatsApp usa audio/ogg; codecs=opus)

    Returns:
        Texto transcrito, o None si ningún proveedor está disponible / todos fallan
    """
    extension = _extension_desde_mime(mime_type)

    # 1) Preferir OpenAI si está configurado
    texto = await _transcribir_con_openai(audio_bytes, extension)
    if texto:
        return texto

    # 2) Fallback Groq
    texto = await _transcribir_con_groq(audio_bytes, extension)
    if texto:
        return texto

    # Ninguno disponible o ambos fallaron
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("GROQ_API_KEY"):
        logger.warning("[WHISPER] Ni OPENAI_API_KEY ni GROQ_API_KEY configuradas — transcripción no disponible")
    else:
        logger.error("[WHISPER] Todos los proveedores de transcripción fallaron")
    return None


async def procesar_audio_whapi(audio_id: str, mime_type: str, token: str) -> str | None:
    """
    Pipeline completo para Whapi: descarga el audio y lo transcribe con Groq Whisper.

    Returns:
        Texto transcrito, o None si falló algún paso
    """
    audio_bytes = await descargar_audio_whapi(audio_id, token)
    if not audio_bytes:
        return None
    return await transcribir_audio(audio_bytes, mime_type)


async def procesar_audio_meta(audio_id: str, mime_type: str) -> str | None:
    """
    Pipeline completo para Meta API: descarga el audio con el token de Meta y lo transcribe.

    Returns:
        Texto transcrito, o None si falló algún paso
    """
    access_token = os.getenv("META_ACCESS_TOKEN", "")
    if not access_token:
        logger.warning("[META] META_ACCESS_TOKEN no configurado — transcripción de audio no disponible")
        return None

    audio_bytes = await descargar_audio_meta(audio_id, access_token)
    if not audio_bytes:
        return None
    return await transcribir_audio(audio_bytes, mime_type)
