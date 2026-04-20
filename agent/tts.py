# agent/tts.py — Text-to-speech con OpenAI para responder con audio en WhatsApp

"""
Cuando el usuario manda una nota de voz, Dona responde también con audio.
Usa OpenAI TTS (modelo tts-1, voz "alloy" neutra por defecto).

Salida: bytes en formato OGG Opus — compatible directo con WhatsApp sin
transcodificación.

Si OPENAI_API_KEY no está configurada, devuelve None silenciosamente para
que el caller caiga al fallback de texto.
"""

import os
import logging

logger = logging.getLogger("agentkit")

_openai_client = None  # lazy init


def _obtener_client():
    global _openai_client
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("[TTS] Paquete 'openai' no instalado")
            return None
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


# Límite conservador de caracteres para TTS — evita audios demasiado largos y caros.
# WhatsApp además corta audios de >60s; 600 chars ≈ 40-50s de audio.
_MAX_CHARS_TTS = 600


async def sintetizar_audio(texto: str, voz: str = "alloy") -> bytes | None:
    """
    Sintetiza un texto a audio OGG Opus con OpenAI TTS.

    Args:
        texto: Texto a sintetizar (se trunca si supera _MAX_CHARS_TTS)
        voz: "alloy" | "echo" | "fable" | "onyx" | "nova" | "shimmer"

    Returns:
        Bytes del audio en formato opus, o None si falló / OPENAI_API_KEY no está
    """
    if not texto or not texto.strip():
        return None
    client = _obtener_client()
    if not client:
        return None

    texto_trunc = texto[:_MAX_CHARS_TTS]
    try:
        response = await client.audio.speech.create(
            model="tts-1",
            voice=voz,
            input=texto_trunc,
            response_format="opus",  # OGG Opus — compatible WhatsApp
        )
        # El SDK devuelve un AsyncHttpxBinaryResponseContent
        audio_bytes = await response.aread() if hasattr(response, "aread") else response.content
        if audio_bytes:
            logger.info(f"[TTS] Audio generado: {len(audio_bytes)} bytes ({len(texto_trunc)} chars)")
            return audio_bytes
        return None
    except Exception as e:
        logger.error(f"[TTS] Error generando audio ({type(e).__name__}): {e}")
        return None
