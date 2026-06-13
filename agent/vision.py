# agent/vision.py — Procesamiento de imágenes con Claude Vision
"""
Descarga imágenes de Meta Cloud API y las analiza con Claude Vision (claude-3-5-haiku).
Permite a Dona entender fotos, flyers, recibos, listas escritas a mano, etc.
"""

import os
import base64
import logging
import httpx
import anthropic

logger = logging.getLogger("dona")

# Prompt del sistema para análisis de imágenes
_SYSTEM_VISION = """Eres Dona, una asistente personal que analiza imágenes enviadas por el usuario.
Tu trabajo es extraer información útil de la imagen y presentarla de forma que Dona pueda actuar sobre ella.

Según el tipo de imagen:
- **Texto/lista escrita**: transcribe el texto exactamente
- **Flyer/evento**: extrae nombre del evento, fecha, hora, lugar y detalles relevantes
- **Recibo/factura**: extrae total, items principales, fecha y establecimiento
- **Foto de lugar/viaje**: describe brevemente dónde parece estar
- **Screenshot**: describe qué muestra y extrae información relevante
- **Cualquier otra imagen**: describe lo que ves de forma concisa y útil

Responde siempre en español. Sé conciso pero completo. No uses markdown innecesario."""


async def descargar_imagen_meta(image_id: str) -> tuple[bytes, str] | tuple[None, None]:
    """
    Descarga una imagen de Meta Cloud API usando su media ID.

    Returns:
        (bytes_imagen, mime_type) o (None, None) si falló
    """
    access_token = os.getenv("META_ACCESS_TOKEN", "")
    api_version = os.getenv("META_API_VERSION", "v21.0")

    if not access_token:
        logger.warning("[VISION] META_ACCESS_TOKEN no configurado")
        return None, None

    url_info = f"https://graph.facebook.com/{api_version}/{image_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Paso 1: obtener URL de descarga y mime_type
            r_info = await client.get(url_info, headers=headers)
            if r_info.status_code != 200:
                logger.error(f"[VISION] Error obteniendo info de imagen {image_id}: {r_info.status_code}")
                return None, None

            info = r_info.json()
            media_url = info.get("url")
            mime_type = info.get("mime_type", "image/jpeg")

            if not media_url:
                logger.error(f"[VISION] No se encontró URL de descarga para imagen {image_id}")
                return None, None

            # Paso 2: descargar la imagen
            r_img = await client.get(media_url, headers=headers)
            if r_img.status_code == 200:
                logger.info(f"[VISION] Imagen descargada: {len(r_img.content)} bytes ({mime_type})")
                return r_img.content, mime_type
            else:
                logger.error(f"[VISION] Error descargando imagen: {r_img.status_code}")
                return None, None

    except Exception as e:
        logger.error(f"[VISION] Excepción descargando imagen ({type(e).__name__}): {e}")
        return None, None


async def analizar_imagen_con_claude(
    image_bytes: bytes,
    mime_type: str,
    caption: str = ""
) -> str | None:
    """
    Analiza una imagen con Claude Vision (claude-3-5-haiku-20241022).

    Args:
        image_bytes: Bytes de la imagen
        mime_type: Tipo MIME (image/jpeg, image/png, image/webp, image/gif)
        caption: Texto/caption que el usuario envió junto a la imagen (opcional)

    Returns:
        Descripción/transcripción de la imagen, o None si falló
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[VISION] ANTHROPIC_API_KEY no configurada")
        return None

    # Normalizar mime_type para Claude (solo acepta jpeg, png, gif, webp)
    mime_map = {
        "image/jpg": "image/jpeg",
        "image/jfif": "image/jpeg",
    }
    mime_type = mime_map.get(mime_type, mime_type)
    if mime_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime_type = "image/jpeg"  # fallback

    # Codificar imagen en base64
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    # Construir el mensaje con la imagen
    user_content = []
    user_content.append({
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": mime_type,
            "data": image_b64,
        }
    })

    if caption:
        user_content.append({
            "type": "text",
            "text": f"El usuario envió esta imagen con el mensaje: \"{caption}\""
        })
    else:
        user_content.append({
            "type": "text",
            "text": "Analiza esta imagen y extrae la información más relevante."
        })

    # Gateo del RuntimeBudgetGuard (entregable F · F-1): el análisis de
    # imagen es trabajo PRINCIPAL (alimenta la respuesta al usuario) —
    # reserva cupo principal del presupuesto del mensaje. Bloqueado →
    # None: el pipeline ya degrada (mensaje de "no pude procesarla").
    from agent.presupuesto_runtime import (
        reservar_llm, con_timeout_llm, consumir_llm, TimeoutPresupuesto,
    )

    decision = reservar_llm()
    if not decision.permitido:
        logger.warning(f"[VISION] Análisis bloqueado por presupuesto: {decision.razon}")
        return None

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await con_timeout_llm(client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=_SYSTEM_VISION,
            messages=[{"role": "user", "content": user_content}]
        ))
        try:
            # Precios aprox. Haiku (USD/Mtok) — alimenta los topes de costo
            costo = (response.usage.input_tokens * 1.0 + response.usage.output_tokens * 5.0) / 1_000_000
            consumir_llm(costo, modelo="claude-haiku-4-5")
        except Exception:
            consumir_llm(0.0)
        texto = response.content[0].text.strip() if response.content else None
        if texto:
            logger.info(f"[VISION] Imagen analizada: \"{texto[:80]}{'...' if len(texto) > 80 else ''}\"")
        return texto

    except TimeoutPresupuesto as t:
        logger.warning(f"[VISION] Análisis cortado por timeout del guard: {t.razon}")
        return None
    except Exception as e:
        logger.error(f"[VISION] Error analizando imagen con Claude ({type(e).__name__}): {e}")
        return None


async def procesar_imagen(image_id: str, caption: str = "") -> str | None:
    """
    Pipeline completo: descarga la imagen de Meta y la analiza con Claude Vision.

    El resultado es un texto que describe/transcribe la imagen, listo para que
    Dona lo procese como si fuera un mensaje de texto del usuario.

    Returns:
        Texto con el análisis de la imagen, o None si falló algún paso
    """
    image_bytes, mime_type = await descargar_imagen_meta(image_id)
    if not image_bytes:
        return None

    analisis = await analizar_imagen_con_claude(image_bytes, mime_type, caption)
    if not analisis:
        return None

    # Envolver el análisis para que Dona sepa que viene de una imagen
    if caption:
        return f"[Imagen recibida — {caption}]\n\n{analisis}"
    else:
        return f"[Imagen recibida]\n\n{analisis}"
