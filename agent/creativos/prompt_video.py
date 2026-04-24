# agent/creativos/prompt_video.py — Optimizador de prompts para video

"""
Transforma la idea en lenguaje natural del usuario en un prompt técnicamente
correcto para modelos de text/image-to-video (Replicate seedance, Kling, etc).

Por qué existe: los modelos de video responden mucho mejor a prompts con
lenguaje cinematográfico explícito (tipo de plano, movimiento de cámara,
iluminación, estética) que a descripciones conversacionales. El usuario
promedio no sabe escribir así — dice "video de mi tiramisú en un
restaurante" cuando lo que el modelo necesita es algo como "Cinematic
close-up shot of a tiramisu dessert on an elegant restaurant table...".

Dona usa Claude Haiku para traducir la intención a un prompt optimizado
ANTES de gastar crédito en el modelo de video. Si el LLM falla, caemos a
un sufijo cinematográfico genérico — peor que el LLM pero mejor que el
prompt raw.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dona")


# ── System prompts ──────────────────────────────────────────────────────────

_SISTEMA_TEXTO_A_VIDEO = """Eres un director de fotografía y experto en prompts para modelos de generación de video (Replicate seedance, Kling, Runway).

Tu tarea: recibes la idea en lenguaje natural de un usuario que NO sabe prompting técnico, y la transformas en un prompt optimizado EN DOS IDIOMAS.

Requisitos del prompt optimizado:
- Específica tipo de plano (close-up / primer plano, medium shot / plano medio, wide shot / plano general, aerial / cenital).
- Específica movimiento de cámara cuando aporte (slow pan / paneo lento, dolly in / acercamiento, static / estática, orbit / órbita, tracking shot / seguimiento).
- Específica iluminación (golden hour / hora dorada, soft natural light / luz natural suave, warm candlelight / luz cálida de velas, neon, cinematic rim light).
- Añade estética y calidad (cinematic, photorealistic, shallow depth of field / profundidad de campo reducida, 4K, professional cinematography).
- Mantén la idea y sujetos del usuario EXACTOS — no inventes productos, marcas, personas ni lugares que no dijo.
- Entre 30 y 80 palabras en cada idioma. Sin listas, un párrafo descriptivo corrido.
- No uses marcas registradas ni nombres de actores reales.

Formato de respuesta OBLIGATORIO — responde EXACTAMENTE con este formato, sin comillas, sin preámbulo:
EN: <prompt optimizado en inglés>
ES: <la misma descripción traducida al español, para que el usuario pueda leerla>

El prompt EN es el que se envía al modelo (que entiende mejor inglés). El ES es solo para mostrárselo al usuario. Ambos deben describir EXACTAMENTE la misma escena."""


_SISTEMA_IMAGEN_A_VIDEO = """Eres un director de fotografía y experto en prompts para modelos de image-to-video (Replicate seedance, Kling).

Contexto: el usuario adjuntó una IMAGEN DE REFERENCIA y quiere animarla / generar un video que mantenga el sujeto visible en la imagen. El modelo ya tiene acceso a la imagen — tu trabajo es describir el MOVIMIENTO y la ESCENA, no el sujeto (que se infiere de la imagen).

Tu tarea: transformar la idea del usuario en un prompt optimizado EN DOS IDIOMAS.

Requisitos:
- Enfócate en movimiento, cámara, iluminación y mood — no describas el sujeto principal en detalle (ya está en la imagen).
- Usa verbos de movimiento: "slowly rotating / girando lentamente", "gentle camera orbit / órbita suave de cámara", "smooth dolly in / acercamiento fluido", "subtle motion of / movimiento sutil de".
- Específica iluminación y ambientación del escenario.
- Añade calidad cinematográfica (cinematic, photorealistic, 4K, smooth motion).
- Mantén los elementos que el usuario sí mencionó (ej: "en la playa" → "coastal setting with waves / escenario costero con olas").
- Entre 30 y 70 palabras en cada idioma, un párrafo corrido.

Formato de respuesta OBLIGATORIO — responde EXACTAMENTE con este formato, sin comillas, sin preámbulo:
EN: <prompt optimizado en inglés para el modelo>
ES: <la misma descripción traducida al español, para el usuario>

Ambos describen EXACTAMENTE la misma escena."""


# Sufijo de fallback si el LLM falla. Menos potente que el LLM pero sigue
# siendo mejor que un prompt crudo.
_SUFIJO_FALLBACK = (
    ", cinematic shot, smooth camera motion, natural lighting, "
    "shallow depth of field, photorealistic, 4K, professional cinematography"
)


def _parsear_en_es(texto: str) -> tuple[str, str]:
    """
    Extrae las secciones EN: y ES: del output del LLM.

    Si el LLM cooperó, retorna `(prompt_en, prompt_es)`. Si no pudo parsear
    una de las dos secciones, la que falta queda como string vacío — el
    caller decide el fallback. Tolera variaciones tipo "EN -", "EN:", "**EN:**".
    """
    import re

    # Normalizamos: quitamos markdown pesado al principio de cada línea y
    # asteriscos alrededor de EN/ES por si el modelo los agrega.
    texto_norm = re.sub(r"\*+", "", texto or "")

    # Buscamos EN: ... (hasta ES: o fin de string). La flag DOTALL permite
    # que el prompt optimizado cruce varias líneas.
    m_en = re.search(r"EN\s*[:\-]\s*(.+?)(?=\n\s*ES\s*[:\-]|$)", texto_norm, re.DOTALL | re.IGNORECASE)
    m_es = re.search(r"ES\s*[:\-]\s*(.+?)$", texto_norm, re.DOTALL | re.IGNORECASE)

    en = (m_en.group(1).strip() if m_en else "").strip('"').strip("'").strip()
    es = (m_es.group(1).strip() if m_es else "").strip('"').strip("'").strip()
    return en, es


async def optimizar_prompt_video(
    idea_usuario: str,
    tiene_imagen_referencia: bool = False,
) -> dict:
    """
    Transforma `idea_usuario` (lenguaje natural del usuario) en un prompt
    técnicamente optimizado para el modelo de video, en inglés (para el
    modelo) y español (para mostrárselo al usuario).

    Args:
      idea_usuario: texto como lo escribió el usuario (en español, casual).
      tiene_imagen_referencia: True si hay una imagen fuente (image-to-video)
        — cambia el system prompt para enfocarse en movimiento en vez de sujeto.

    Returns:
      dict `{"en": <prompt inglés>, "es": <prompt español>}`. Si el LLM falla
      o responde mal, se usa fallback: la idea raw + sufijo cinematográfico
      como `en`, y la idea del usuario como `es`.
    """
    from agent.llm import completar_con_sistema

    idea = (idea_usuario or "").strip()
    if not idea:
        return {"en": "", "es": ""}

    sistema = (
        _SISTEMA_IMAGEN_A_VIDEO if tiene_imagen_referencia
        else _SISTEMA_TEXTO_A_VIDEO
    )

    try:
        respuesta = await completar_con_sistema(
            system=sistema,
            mensaje=f"Idea del usuario: {idea}",
            max_tokens=500,
        )
    except Exception as e:
        logger.error(f"[PROMPT_VIDEO] LLM falló optimizando: {e}")
        respuesta = None

    if not respuesta:
        logger.warning(
            "[PROMPT_VIDEO] sin LLM → usando fallback con sufijo cinematográfico"
        )
        return {"en": f"{idea}{_SUFIJO_FALLBACK}", "es": idea}

    prompt_en, prompt_es = _parsear_en_es(respuesta)

    # Fallbacks si el modelo no respetó el formato:
    if not prompt_en and not prompt_es:
        # Ninguna sección parseó — usamos la respuesta entera como inglés
        limpio = respuesta.strip().strip('"').strip("'").strip()
        prompt_en = limpio
        prompt_es = idea  # lo que el usuario escribió, al menos es legible
    elif not prompt_en:
        prompt_en = prompt_es  # usamos el español como fallback (no ideal)
    elif not prompt_es:
        prompt_es = idea  # usamos la idea original

    logger.info(
        f"[PROMPT_VIDEO] optimizado: \"{idea[:60]}\" → EN:\"{prompt_en[:60]}\" ES:\"{prompt_es[:60]}\""
    )
    return {"en": prompt_en, "es": prompt_es}
