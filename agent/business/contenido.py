# agent/business/contenido.py — Generación de contenido para redes sociales

"""
Genera copy para redes sociales usando el LLM secundario (DeepSeek/Haiku).
El usuario copia y publica — Dona no publica directamente.
"""

import logging
from agent.llm import completar_con_sistema

logger = logging.getLogger("dona")

# Prompts base por tipo de contenido
_PROMPTS_CONTENIDO = {
    "post_instagram": (
        "Genera un post para Instagram de un negocio. "
        "Incluye: texto principal (2-4 líneas), emojis apropiados, "
        "3-5 hashtags relevantes, y un call-to-action. "
        "Tono: {tono}. Tema: {tema}. Negocio: {negocio}."
    ),
    "historia": (
        "Genera el texto para una historia de Instagram/WhatsApp Status. "
        "Debe ser corto (1-2 líneas), impactante, con emoji. "
        "Tono: {tono}. Tema: {tema}. Negocio: {negocio}."
    ),
    "promocion": (
        "Genera un mensaje promocional para enviar por WhatsApp. "
        "Debe ser conciso, persuasivo, con precio claro y call-to-action. "
        "Tono: {tono}. Tema: {tema}. Negocio: {negocio}."
    ),
    "descripcion_producto": (
        "Genera una descripción de producto para catálogo o tienda online. "
        "Incluye: beneficios principales, características, por qué elegirlo. "
        "Tono: {tono}. Producto: {tema}. Negocio: {negocio}."
    ),
}


async def generar_contenido(
    tipo: str, tema: str, negocio: str = "",
    tono: str = "profesional y amigable",
) -> str:
    """
    Genera contenido para redes sociales.

    Args:
        tipo: post_instagram, historia, promocion, descripcion_producto
        tema: De qué trata el contenido
        negocio: Nombre del negocio
        tono: Tono del contenido
    """
    template = _PROMPTS_CONTENIDO.get(tipo, _PROMPTS_CONTENIDO["post_instagram"])
    system = (
        "Eres un copywriter experto en redes sociales para pequeños negocios en Latinoamérica. "
        "Genera contenido listo para copiar y publicar. "
        "Responde SOLO con el contenido, sin explicaciones ni introducciones."
    )
    prompt = template.format(tono=tono, tema=tema, negocio=negocio)

    resultado = await completar_con_sistema(system, prompt, max_tokens=400)
    if not resultado:
        return "No pude generar el contenido. Intenta describir mejor el tema."

    logger.info(f"[CONTENIDO] Generado tipo={tipo} tema='{tema[:50]}'")
    return resultado
