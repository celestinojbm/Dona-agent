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

Tu tarea: recibes la idea en lenguaje natural de un usuario que NO sabe prompting técnico, y la transformas en un prompt optimizado en INGLÉS para el modelo de video.

Requisitos del prompt optimizado:
- Específica tipo de plano (close-up, medium shot, wide shot, aerial, etc.)
- Específica movimiento de cámara cuando aporte (slow pan, dolly in, static, orbit, tracking shot)
- Específica iluminación (golden hour, soft natural light, warm candlelight, neon, cinematic rim light, etc.)
- Añade estética y calidad (cinematic, photorealistic, shallow depth of field, 4K, film grain, professional cinematography)
- Mantén la idea y sujetos del usuario EXACTOS — no inventes productos, marcas, personas ni lugares que no dijo
- Entre 30 y 80 palabras. Sin listas, un párrafo descriptivo corrido.
- No uses marcas registradas ni nombres de actores reales.

Responde ÚNICAMENTE con el prompt optimizado en inglés. Sin explicaciones, sin comillas, sin preámbulo."""


_SISTEMA_IMAGEN_A_VIDEO = """Eres un director de fotografía y experto en prompts para modelos de image-to-video (Replicate seedance, Kling).

Contexto: el usuario adjuntó una IMAGEN DE REFERENCIA y quiere animarla / generar un video que mantenga el sujeto visible en la imagen. El modelo ya tiene acceso a la imagen — tu trabajo es describir el MOVIMIENTO y la ESCENA, no el sujeto (que se infiere de la imagen).

Tu tarea: transformar la idea en lenguaje natural del usuario en un prompt optimizado en INGLÉS para image-to-video.

Requisitos:
- Enfócate en movimiento, cámara, iluminación y mood — no describas el sujeto principal en detalle (ya está en la imagen)
- Usa verbos de movimiento: "slowly rotating", "gentle camera orbit", "smooth dolly in", "the subject comes to life with...", "subtle motion of..."
- Específica iluminación y ambientación del escenario
- Añade calidad cinematográfica (cinematic, photorealistic, 4K, smooth motion)
- Mantén los elementos que el usuario sí mencionó (ej: "en la playa" → "coastal setting with waves")
- Entre 30 y 70 palabras, un párrafo corrido.

Responde ÚNICAMENTE con el prompt optimizado en inglés. Sin explicaciones, sin comillas."""


# Sufijo de fallback si el LLM falla. Menos potente que el LLM pero sigue
# siendo mejor que un prompt crudo.
_SUFIJO_FALLBACK = (
    ", cinematic shot, smooth camera motion, natural lighting, "
    "shallow depth of field, photorealistic, 4K, professional cinematography"
)


async def optimizar_prompt_video(
    idea_usuario: str,
    tiene_imagen_referencia: bool = False,
) -> str:
    """
    Transforma `idea_usuario` (lenguaje natural del usuario) en un prompt
    técnicamente optimizado para el modelo de video.

    Args:
      idea_usuario: texto como lo escribió el usuario (en español, casual).
      tiene_imagen_referencia: True si hay una imagen fuente (image-to-video)
        — cambia el system prompt para enfocarse en movimiento en vez de sujeto.

    Returns:
      Prompt optimizado en inglés, listo para enviar a Replicate.
      Si el LLM falla, retorna `idea_usuario + sufijo cinematográfico` como
      fallback (mejor que crudo, peor que LLM).
    """
    from agent.llm import completar_con_sistema

    idea = (idea_usuario or "").strip()
    if not idea:
        return idea

    sistema = (
        _SISTEMA_IMAGEN_A_VIDEO if tiene_imagen_referencia
        else _SISTEMA_TEXTO_A_VIDEO
    )

    try:
        optimizado = await completar_con_sistema(
            system=sistema,
            mensaje=f"Idea del usuario: {idea}",
            max_tokens=250,
        )
    except Exception as e:
        logger.error(f"[PROMPT_VIDEO] LLM falló optimizando: {e}")
        optimizado = None

    if not optimizado:
        logger.warning(
            "[PROMPT_VIDEO] sin LLM → usando fallback con sufijo cinematográfico"
        )
        return f"{idea}{_SUFIJO_FALLBACK}"

    # Limpieza defensiva: a veces el LLM devuelve con comillas o prefijos tipo
    # "Here's the optimized prompt:". Los quitamos si aparecen.
    optimizado = optimizado.strip().strip('"').strip("'").strip()
    if optimizado.lower().startswith(("here", "aquí", "prompt:", "optimized")):
        # Quedarnos con lo que viene después de los dos puntos, si existe
        if ":" in optimizado:
            optimizado = optimizado.split(":", 1)[1].strip().strip('"').strip("'")

    logger.info(
        f"[PROMPT_VIDEO] optimizado: \"{idea[:60]}...\" → \"{optimizado[:80]}...\""
    )
    return optimizado
