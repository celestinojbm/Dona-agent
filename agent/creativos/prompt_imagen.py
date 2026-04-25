# agent/creativos/prompt_imagen.py — Optimizador de prompts para imagen

"""
Transforma la idea en lenguaje natural del usuario en un prompt optimizado
para modelos de generación de imagen (Gemini 2.5 Flash Image, Ideogram, etc).

Por qué existe: los modelos de imagen responden mucho mejor a prompts con
lenguaje fotográfico/de diseño explícito (encuadre, iluminación, estilo,
paleta) que a descripciones conversacionales. El usuario promedio dice
"logo de pizza para mi local" y el modelo devuelve algo genérico — cuando
lo que necesita es "Modern minimalist pizza restaurant logo, hand-lettered
typography, warm tomato red and basil green palette, vector style, white
background, balanced composition, professional brand identity".

Dona usa Claude Haiku para traducir la intención a un prompt optimizado
ANTES de gastar crédito en Gemini/Ideogram. Si el LLM falla, caemos a un
sufijo de calidad genérico — peor que el LLM pero mejor que el prompt raw.

Mismo patrón bilingüe que `prompt_video.py`: devolvemos `{"en": ..., "es": ...}`
para que el modelo reciba inglés (mejor entendimiento) pero el usuario lea
español en el preview.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dona")


# ── System prompts ──────────────────────────────────────────────────────────

_SISTEMA_STANDARD = """Eres un director de arte y experto en prompts para modelos de generación de imagen (Gemini Imagen, Flux, Stable Diffusion).

Tu tarea: recibes la idea en lenguaje natural de un usuario que NO sabe prompting técnico, y la transformas en un prompt optimizado EN DOS IDIOMAS.

Requisitos del prompt optimizado:
- Específica encuadre/composición cuando aporte (close-up / primer plano, wide shot / plano general, flat lay / vista cenital, eye-level / a la altura de los ojos, rule of thirds / regla de tercios).
- Específica iluminación (soft natural light / luz natural suave, golden hour / hora dorada, studio lighting / luz de estudio, dramatic side light / luz lateral dramática, warm tungsten / tungsteno cálido).
- Específica estilo visual (photorealistic / fotorrealista, minimalist / minimalista, vibrant / vibrante, cinematic / cinematográfico, isometric / isométrico, watercolor / acuarela, vector / vector).
- Añade calidad técnica (sharp focus / foco nítido, high detail / alto detalle, professional photography / fotografía profesional, 4K, depth of field / profundidad de campo).
- Si la idea es un logo/banner/flyer/promo: añade elementos de diseño (clean composition / composición limpia, balanced / balanceado, bold typography / tipografía fuerte cuando aplique, brand-ready / listo para marca).
- Mantén la idea y sujetos del usuario EXACTOS — no inventes productos, marcas, personas, lugares ni texto que no dijo. Si menciona un texto específico para mostrar en la imagen, conservalo entre comillas.
- Entre 25 y 70 palabras en cada idioma. Sin listas, un párrafo descriptivo corrido.
- No uses marcas registradas ni nombres de personas reales.

Formato de respuesta OBLIGATORIO — responde EXACTAMENTE con este formato, sin comillas, sin preámbulo:
EN: <prompt optimizado en inglés>
ES: <la misma descripción traducida al español, para que el usuario pueda leerla>

El prompt EN es el que se envía al modelo (que entiende mejor inglés). El ES es solo para mostrárselo al usuario. Ambos deben describir EXACTAMENTE la misma escena."""


_SISTEMA_PREMIUM = """Eres un director de arte senior y experto en prompts para modelos premium de generación de imagen (Ideogram v2, Flux Pro Ultra, Recraft) que destacan en TIPOGRAFÍA y branding.

Tu tarea: recibes la idea en lenguaje natural de un usuario y la transformas en un prompt optimizado EN DOS IDIOMAS, aprovechando que estos modelos manejan texto en imagen mucho mejor.

Requisitos del prompt optimizado:
- Si hay texto a mostrar en la imagen (precio, nombre del negocio, slogan), conservalo EXACTO entre comillas y específica jerarquía (headline, subheadline, fine print).
- Específica tipo de imagen (logo, flyer, promo, banner, instagram post, menu).
- Específica estilo y paleta (color palette: warm tones, monochrome, pastel, neon; era: retro 70s, modern, hand-drawn).
- Específica composición (centered, asymmetric, grid layout, hero composition).
- Específica iluminación si es escena (soft natural light, dramatic, studio).
- Añade calidad (high quality, sharp typography, professional design, brand-ready, print-ready).
- Mantén la idea, productos, precios y nombres EXACTOS — no inventes nada.
- Entre 30 y 80 palabras en cada idioma, párrafo descriptivo corrido.

Formato de respuesta OBLIGATORIO — responde EXACTAMENTE con este formato, sin comillas, sin preámbulo:
EN: <prompt optimizado en inglés>
ES: <la misma descripción traducida al español, para que el usuario pueda leerla>

Ambos describen EXACTAMENTE la misma escena."""


# Sufijo de fallback si el LLM falla. Menos potente que el LLM pero sigue
# siendo mejor que un prompt crudo.
_SUFIJO_FALLBACK = (
    ", professional photography, soft natural lighting, sharp focus, "
    "high detail, balanced composition, 4K"
)


def _parsear_en_es(texto: str) -> tuple[str, str]:
    """
    Extrae las secciones EN: y ES: del output del LLM.

    Si el LLM cooperó, retorna `(prompt_en, prompt_es)`. Si no pudo parsear
    una de las dos secciones, la que falta queda como string vacío — el
    caller decide el fallback. Tolera variaciones tipo "EN -", "EN:", "**EN:**".
    """
    import re

    texto_norm = re.sub(r"\*+", "", texto or "")

    m_en = re.search(r"EN\s*[:\-]\s*(.+?)(?=\n\s*ES\s*[:\-]|$)", texto_norm, re.DOTALL | re.IGNORECASE)
    m_es = re.search(r"ES\s*[:\-]\s*(.+?)$", texto_norm, re.DOTALL | re.IGNORECASE)

    en = (m_en.group(1).strip() if m_en else "").strip('"').strip("'").strip()
    es = (m_es.group(1).strip() if m_es else "").strip('"').strip("'").strip()
    return en, es


async def optimizar_prompt_imagen(
    idea_usuario: str,
    calidad: str = "standard",
) -> dict:
    """
    Transforma `idea_usuario` (lenguaje natural casual) en un prompt optimizado
    para el modelo de imagen, en inglés (para el modelo) y español (para el
    usuario).

    Args:
      idea_usuario: texto como lo escribió el usuario (en español, casual).
      calidad: "standard" → Gemini Flash. "premium" → Ideogram (mejor texto
        en imagen, prompts más orientados a branding).

    Returns:
      dict `{"en": <prompt inglés>, "es": <prompt español>}`. Si el LLM falla
      o responde mal, fallback: idea raw + sufijo, idea raw como ES.
    """
    from agent.llm import completar_con_sistema

    idea = (idea_usuario or "").strip()
    if not idea:
        return {"en": "", "es": ""}

    sistema = _SISTEMA_PREMIUM if calidad == "premium" else _SISTEMA_STANDARD

    try:
        respuesta = await completar_con_sistema(
            system=sistema,
            mensaje=f"Idea del usuario: {idea}",
            max_tokens=500,
        )
    except Exception as e:
        logger.error(f"[PROMPT_IMAGEN] LLM falló optimizando: {e}")
        respuesta = None

    if not respuesta:
        logger.warning(
            "[PROMPT_IMAGEN] sin LLM → usando fallback con sufijo de calidad"
        )
        return {"en": f"{idea}{_SUFIJO_FALLBACK}", "es": idea}

    prompt_en, prompt_es = _parsear_en_es(respuesta)

    if not prompt_en and not prompt_es:
        limpio = respuesta.strip().strip('"').strip("'").strip()
        prompt_en = limpio
        prompt_es = idea
    elif not prompt_en:
        prompt_en = prompt_es
    elif not prompt_es:
        prompt_es = idea

    logger.info(
        f"[PROMPT_IMAGEN] optimizado ({calidad}): \"{idea[:60]}\" → "
        f"EN:\"{prompt_en[:60]}\" ES:\"{prompt_es[:60]}\""
    )
    return {"en": prompt_en, "es": prompt_es}
