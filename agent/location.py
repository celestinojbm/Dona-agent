# agent/location.py — Detección inteligente de ubicación dinámica de Dona
# Dona

"""
Detecta dos situaciones de ubicación:
  1. Viaje temporal: usuario menciona que está en otra ciudad → guardar ciudad con expiración
  2. Ciudad suelta: usuario envía solo el nombre de su ciudad sin haberla configurado → bug fix

Usa Claude Haiku para inferencia, con pre-filtros baratos para evitar llamadas innecesarias.
"""

import logging

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("dona")

# Pre-filtro de palabras clave para detectar viajes sin LLM
_PALABRAS_VIAJE = {
    "viaj", "llegué", "llegue", "estoy en ", "me encuentro en ",
    "estoy de paso", "de visita en", "vine a ", "fui a ", "estoy visitando",
    "viajé", "viaje", "aterricé", "aterrize", "llegamos a",
}

# Respuestas comunes que nunca son nombres de ciudades
_NO_CIUDADES = {
    "sí", "si", "no", "ok", "bien", "hola", "gracias", "buenas", "hey",
    "listo", "claro", "dale", "perfecto", "exacto", "correcto", "entendido",
    "ya", "ahí", "aquí", "ahi", "aqui",
}

# Primera palabra de frases que nunca son solo el nombre de una ciudad
_VERBOS_INICIO_FRASE = {
    "vivo", "soy", "estoy", "me", "mi", "yo", "resido", "nací", "naci",
    "tengo", "vive", "viven", "somos", "vivimos",
}


def parece_viaje(texto: str) -> bool:
    """Pre-filtro barato: ¿el texto menciona viaje o ubicación temporal?"""
    t = texto.lower()
    return any(kw in t for kw in _PALABRAS_VIAJE)


async def detectar_viaje(texto: str) -> dict | None:
    """
    Detecta si el usuario menciona que está temporalmente en otra ciudad.

    Retorna: {"ciudad": "Miami", "dias": 3}
    Retorna None si no hay viaje o si el pre-filtro no pasa.

    Solo llama al LLM si el texto contiene palabras clave de viaje.
    """
    if not parece_viaje(texto):
        return None

    try:
        from agent.llm import completar_texto
        prompt = (
            f"¿Este mensaje indica que el usuario está temporalmente en otra ciudad?\n"
            f"Mensaje: \"{texto[:200]}\"\n\n"
            f"Si SÍ → responde solo: VIAJE: <ciudad>, <días_estimados>\n"
            f"Si NO → responde solo: NO\n\n"
            f"Ejemplos:\n"
            f"'estoy en Bogotá esta semana' → VIAJE: Bogotá, 7\n"
            f"'llegué a Miami ayer' → VIAJE: Miami, 3\n"
            f"'viaje de trabajo a Monterrey 2 días' → VIAJE: Monterrey, 2\n"
            f"'tengo reunión mañana' → NO"
        )
        resp_text = await completar_texto(prompt, max_tokens=40)
        resp = (resp_text or "NO").strip()

        if resp.upper().startswith("VIAJE:"):
            partes = resp[6:].strip().split(",")
            if partes:
                ciudad = partes[0].strip().title()
                dias = 3
                if len(partes) >= 2:
                    try:
                        dias = max(1, min(int(partes[1].strip()), 30))
                    except ValueError:
                        pass
                if ciudad:
                    return {"ciudad": ciudad, "dias": dias}

        return None

    except Exception as e:
        logger.debug(f"location.detectar_viaje: {e}")
        return None


async def es_ciudad_suelta(texto: str) -> str | None:
    """
    Detecta si un mensaje corto (≤ 4 palabras) es solo el nombre de una ciudad.

    Retorna el nombre de la ciudad normalizado, o None.
    Se llama SOLO cuando el usuario no tiene ciudad configurada.

    Pre-filtros baratos evitan la llamada al LLM en la mayoría de los casos.
    """
    palabras = texto.strip().split()

    # Debe ser ≤ 4 palabras y ≥ 3 caracteres
    if not palabras or len(palabras) > 4 or len(texto.strip()) < 3:
        return None

    # Si empieza con verbo o pronombre, es una oración — no es solo el nombre de una ciudad
    if palabras[0].lower() in _VERBOS_INICIO_FRASE:
        return None

    # Al menos una palabra con inicial mayúscula (ciudades suelen capitalizar)
    if not any(w and w[0].isupper() for w in palabras):
        return None

    # Descartar respuestas comunes que no son ciudades
    if texto.strip().lower() in _NO_CIUDADES:
        return None

    try:
        from agent.llm import completar_texto
        prompt = (
            f"¿Es '{texto}' el nombre de una ciudad, municipio o localidad real?\n"
            f"Si SÍ → responde solo: CIUDAD: <nombre_exacto>\n"
            f"Si NO → responde solo: NO"
        )
        resp_text = await completar_texto(prompt, max_tokens=25)
        resp = (resp_text or "NO").strip()

        if resp.upper().startswith("CIUDAD:"):
            ciudad = resp[7:].strip().title()
            return ciudad if ciudad else None

        return None

    except Exception as e:
        logger.debug(f"location.es_ciudad_suelta: {e}")
        return None
