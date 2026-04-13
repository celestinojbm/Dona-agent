# enhanced/nlp_detector.py — Detector NLP para matching de sistemas del catálogo

"""
Usa Claude Haiku para detectar cuándo un mensaje del usuario
coincide con un sistema del catálogo y retorna el match.

Estrategia de dos pasos:
  1. Filtro rápido por keywords (costo cero) — descarta mensajes irrelevantes
  2. Si pasa el filtro, Claude Haiku clasifica con el catálogo real
"""

import os
import json
import logging
from anthropic import AsyncAnthropic

logger = logging.getLogger("dona.enhanced")

_claude = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Keywords que sugieren que el usuario quiere organizar/trackear algo
_KEYWORDS_SISTEMA = {
    "organizar", "trackear", "registrar", "controlar", "llevar control",
    "sistema", "tracking", "quiero un", "necesito un", "ayúdame a",
    "ayudame a", "cómo puedo", "como puedo", "quiero empezar",
    "lista de", "registro de", "control de", "tracker de",
    "hábito", "habito", "gasto", "presupuesto", "finanza",
    "ejercicio", "agua", "sueño", "lectura", "libro",
    "diario", "journal", "cumpleaños", "crm", "cliente",
    "venta", "compras", "mantenimiento", "rutina", "meta",
    "nota", "aprendizaje",
    # Activaciones directas
    "dona sistemas", "qué sistemas", "que sistemas", "catálogo",
    "catalogo", "mis sistemas",
}


def _pasa_filtro_rapido(texto: str) -> bool:
    """Filtro de costo cero: ¿el mensaje podría ser sobre activar un sistema?"""
    texto_lower = texto.lower()
    # Mensajes muy cortos (< 3 palabras) probablemente no son pedidos de sistema
    if len(texto_lower.split()) < 3:
        # Excepciones: comandos directos
        if any(kw in texto_lower for kw in ("mis sistemas", "dona sistemas", "catálogo", "catalogo")):
            return True
        return False
    return any(kw in texto_lower for kw in _KEYWORDS_SISTEMA)


async def detectar_sistema(texto: str, catalogo: list[dict]) -> dict | None:
    """
    Detecta si el mensaje del usuario coincide con un sistema del catálogo.

    Args:
        texto: Mensaje del usuario
        catalogo: Lista de dicts con {id, nombre, categoria, descripcion}

    Returns:
        Dict con {catalog_id, nombre, confianza, razon} o None si no hay match.
    """
    if not _pasa_filtro_rapido(texto):
        return None

    if not catalogo:
        return None

    # Construir lista de sistemas para el prompt
    sistemas_str = "\n".join(
        f"- ID:{s['id']} | {s['nombre']} ({s['categoria']}): {s['descripcion'][:80]}"
        for s in catalogo
    )

    prompt = f"""Analiza si el siguiente mensaje del usuario indica que quiere activar, usar o necesita uno de estos sistemas:

SISTEMAS DISPONIBLES:
{sistemas_str}

MENSAJE DEL USUARIO: "{texto}"

Si el usuario quiere activar un sistema o su mensaje coincide claramente con uno, responde con JSON:
{{"match": true, "catalog_id": <ID>, "nombre": "<nombre del sistema>", "confianza": <0.0-1.0>, "razon": "<por qué coincide>"}}

Si NO hay coincidencia clara (el usuario solo está conversando, haciendo una pregunta general, o pidiendo algo que no es un sistema), responde:
{{"match": false}}

REGLAS:
- Solo reporta match si la intención es clara (confianza >= 0.7)
- "quiero organizar mis gastos" → match con Control de Gastos
- "cuánto gasté ayer" → NO match (es una pregunta, no activación)
- "hola cómo estás" → NO match
- Responde SOLO el JSON, sin texto adicional."""

    try:
        from agent.llm import completar_texto
        respuesta = await completar_texto(prompt, max_tokens=200)
        if not respuesta:
            return None
        # Limpiar posible markdown
        if respuesta.startswith("```"):
            respuesta = respuesta.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        resultado = json.loads(respuesta)

        if resultado.get("match") and resultado.get("confianza", 0) >= 0.7:
            logger.info(
                f"[NLP] Sistema detectado: {resultado.get('nombre')} "
                f"(confianza={resultado.get('confianza')}) para: '{texto[:60]}'"
            )
            return {
                "catalog_id": resultado["catalog_id"],
                "nombre": resultado["nombre"],
                "confianza": resultado["confianza"],
                "razon": resultado.get("razon", ""),
            }

        return None

    except json.JSONDecodeError:
        logger.warning(f"[NLP] Respuesta no-JSON de Haiku: {respuesta[:100]}")
        return None
    except Exception as e:
        logger.error(f"[NLP] Error en detección: {type(e).__name__}: {e}")
        return None


def es_consulta_catalogo(texto: str) -> bool:
    """Detecta si el usuario quiere ver el catálogo de sistemas disponibles."""
    texto_lower = texto.strip().lower()
    patrones = [
        "dona sistemas", "mis sistemas", "qué sistemas", "que sistemas",
        "catálogo", "catalogo", "sistemas disponibles", "qué puedo organizar",
        "que puedo organizar",
    ]
    return any(p in texto_lower for p in patrones)
