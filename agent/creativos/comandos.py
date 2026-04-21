# agent/creativos/comandos.py — Detección y render de comandos creativos

"""
Comandos de generación de imagen (directos tipo "dona imagen <prompt>" y
variantes en lenguaje natural tipo "hazme una imagen de X", "dibuja X",
"imagen de X") + "confirmar" / "cancelar" para el flujo 2 pasos.

Se invocan desde main.py ANTES del routing al LLM para que queden
determinísticos (no dependen de que Claude llame un tool).
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger("dona")


# ── Detectores ──────────────────────────────────────────────────────────────

# Sustantivos que referencian "imagen" en español/inglés usuales
_SUSTANTIVOS_IMG = r"(?:im[aá]gen?|image|foto|dibujo|ilustraci[oó]n|poster|banner)"

# 1) "dona imagen <prompt>" — patrón original, se mantiene por retrocompat.
_RE_IMAGEN_DIRECTO = re.compile(
    r"^[\s¿¡]*dona\s+im[aá]gen?\b\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

# 2) Verbo imperativo DÉBIL (haz/genera/quiero/...) + sustantivo de imagen + prompt.
#    Requiere el sustantivo porque el verbo solo no implica imagen
#    ("quiero un café" no debe matchear, pero "quiero una imagen de X" sí).
_RE_IMAGEN_VERBO_SUST = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    r"(?:h[aá]z(?:me)?|haga(?:me)?|genera(?:me)?|gen[eé]ra(?:me)?|"
    r"cr[eé]a(?:me)?|dame|p[oó]n(?:me)?|m[aá]nda(?:me)?|"
    r"quiero|necesito|"
    r"puedes\s+(?:hacer|generar|crear|dibujar|mandar|dar|enviar)(?:me)?|"
    r"me\s+puedes\s+(?:hacer|generar|crear|dibujar|mandar|dar|enviar)(?:me)?|"
    r"podr[ií]as\s+(?:hacer|generar|crear|dibujar|mandar|dar|enviar)(?:me)?)"
    r"\s+(?:(?:una?|el|la|mi|unos?|unas?)\s+)?"
    + _SUSTANTIVOS_IMG +
    r"(?:\s+(?:de|con|que|sobre|para|del))?"
    r"\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)

# 3) Verbos FUERTES que ya implican imagen (sin sustantivo obligatorio).
#    Ej: "dibuja un gato", "ilústrame una escena", "píntame un paisaje"
_RE_IMAGEN_VERBO_FUERTE = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    r"(?:dib[uú]ja(?:me)?|il[uú]stra(?:me)?|p[ií]nta(?:me)?)"
    r"\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)

# 4) Sustantivo de imagen al inicio + prompt.
#    Ej: "imagen de gato", "foto del logo", "dibujo gato astronauta"
#    Este es el más amplio: por eso se prueba al final.
_RE_IMAGEN_SUSTANTIVO = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    + _SUSTANTIVOS_IMG +
    r"\s+(?:de\s+|con\s+|que\s+|sobre\s+|para\s+|del\s+)?"
    r"(.+)$",
    re.IGNORECASE | re.DOTALL,
)

# Orden: más específico primero (el original "dona imagen" → verbo+sustantivo →
# verbo fuerte → sustantivo solo). El primero que case gana.
_PATRONES_IMAGEN = (
    _RE_IMAGEN_DIRECTO,
    _RE_IMAGEN_VERBO_SUST,
    _RE_IMAGEN_VERBO_FUERTE,
    _RE_IMAGEN_SUSTANTIVO,
)

# Mismos prefijos que los anteriores pero SIN prompt/sujeto. Sirven para detectar
# "genera una imagen" (sin decir de qué) y preguntarle al usuario qué quiere,
# en lugar de dejar que caiga al LLM — que tiende a responder "no puedo".
_PATRONES_IMAGEN_SIN_SUJETO = (
    # "dona imagen" / "dona imagen." / "dona imagen?"
    re.compile(
        r"^[\s¿¡]*dona\s+im[aá]gen?\s*[\.\?\!]*$",
        re.IGNORECASE,
    ),
    # "genera una imagen", "hazme una foto", "dame un dibujo"
    re.compile(
        r"^[\s¿¡]*(?:dona[,\s]+)?"
        r"(?:h[aá]z(?:me)?|haga(?:me)?|genera(?:me)?|gen[eé]ra(?:me)?|"
        r"cr[eé]a(?:me)?|dame|p[oó]n(?:me)?|m[aá]nda(?:me)?|"
        r"quiero|necesito|"
        r"puedes\s+(?:hacer|generar|crear|dibujar|mandar|dar|enviar)(?:me)?|"
        r"me\s+puedes\s+(?:hacer|generar|crear|dibujar|mandar|dar|enviar)(?:me)?|"
        r"podr[ií]as\s+(?:hacer|generar|crear|dibujar|mandar|dar|enviar)(?:me)?)"
        r"\s+(?:(?:una?|el|la|mi|unos?|unas?)\s+)?"
        + _SUSTANTIVOS_IMG +
        r"\s*[\.\?\!]*$",
        re.IGNORECASE,
    ),
    # "dibuja", "ilustra", "pinta" — verbos fuertes solos, sin complemento
    re.compile(
        r"^[\s¿¡]*(?:dona[,\s]+)?"
        r"(?:dib[uú]ja(?:me)?|il[uú]stra(?:me)?|p[ií]nta(?:me)?)"
        r"\s*[\.\?\!]*$",
        re.IGNORECASE,
    ),
)

# Premium: "dona imagen premium <prompt>" o "dona imagen hd <prompt>"
_RE_PREMIUM = re.compile(r"^\s*(premium|hd|pro)\s+(.+)$", re.IGNORECASE | re.DOTALL)

# Aspect ratio: "--16:9 prompt..." o "--vertical prompt..."
_RE_ASPECT = re.compile(r"(?:^|\s)--(16:9|9:16|1:1|4:3|3:4|horizontal|vertical|cuadrado)\b", re.IGNORECASE)

_CONFIRMAR = {"confirmar", "si", "sí", "dale", "ok", "confirmo", "dona confirmar", "dona si", "dona sí"}
_CANCELAR  = {"cancelar", "no", "dona cancelar", "dona no"}


def _match_imagen(texto: str):
    """Devuelve (regex, cuerpo) del primer patrón que acepte el texto, o (None, '')."""
    for pat in _PATRONES_IMAGEN:
        m = pat.match(texto)
        if m:
            cuerpo = (m.group(1) or "").strip()
            if cuerpo:
                return pat, cuerpo
    return None, ""


def es_comando_imagen(texto: str) -> bool:
    """True si el mensaje es una solicitud de generación de imagen (directa o natural)."""
    if not texto:
        return False
    pat, cuerpo = _match_imagen(texto)
    return pat is not None and bool(cuerpo)


def es_solicitud_imagen_sin_sujeto(texto: str) -> bool:
    """
    True si el mensaje tiene intención de imagen pero le falta el sujeto.
    Ej: "genera una imagen", "dona imagen", "dibuja", "hazme una foto".
    Sirve para responder "¿De qué?" en lugar de dejar que caiga al LLM
    (que tiende a negar la capacidad).
    Solo aplica cuando es_comando_imagen(texto) == False.
    """
    if not texto:
        return False
    if es_comando_imagen(texto):
        return False
    t = texto.strip()
    for pat in _PATRONES_IMAGEN_SIN_SUJETO:
        if pat.match(t):
            return True
    return False


def parsear_imagen(texto: str) -> dict:
    """
    Extrae prompt, calidad y aspect_ratio del comando.
    Asume `es_comando_imagen(texto)` == True.
    """
    _, cuerpo = _match_imagen(texto)

    calidad = "standard"
    mp = _RE_PREMIUM.match(cuerpo)
    if mp:
        calidad = "premium"
        cuerpo = mp.group(2).strip()

    aspect = "1:1"
    ma = _RE_ASPECT.search(cuerpo)
    if ma:
        raw = ma.group(1).lower()
        aspect = {
            "horizontal": "16:9",
            "vertical": "9:16",
            "cuadrado": "1:1",
        }.get(raw, raw)
        cuerpo = _RE_ASPECT.sub(" ", cuerpo).strip()

    return {"prompt": cuerpo, "calidad": calidad, "aspect_ratio": aspect}


def es_comando_confirmar(texto: str) -> bool:
    """True si el mensaje es una confirmación (sólo vale si hay pendiente)."""
    if not texto:
        return False
    return texto.strip().lower() in _CONFIRMAR


def es_comando_cancelar(texto: str) -> bool:
    if not texto:
        return False
    return texto.strip().lower() in _CANCELAR


# ── Render de respuestas ────────────────────────────────────────────────────

def texto_preview(preview: dict) -> str:
    """Mensaje mostrado al usuario tras `preparar_imagen`."""
    costo = preview["costo_creditos"]
    saldo = preview["saldo_actual"]
    alcanza = preview["alcanza"]
    calidad = preview["calidad"]
    aspect = preview["aspect_ratio"]
    ttl = preview["ttl_min"]

    partes = [
        "🎨 *Voy a generar:*",
        f"_{preview['prompt']}_",
        "",
        f"• Calidad: {calidad}",
        f"• Proporción: {aspect}",
        f"• Costo: *{costo} créditos* (saldo: {saldo})",
        "",
    ]
    if not alcanza:
        partes.append(
            f"⚠️ No te alcanzan los créditos ({saldo}/{costo}). "
            "Escribe *dona recargar* para comprar más."
        )
    else:
        partes.append(
            f"Responde *confirmar* para generar, o *cancelar* para descartar. "
            f"(Expira en {ttl} min)"
        )
    return "\n".join(partes)


def texto_encolada(job_id: int, prompt: str) -> str:
    return (
        f"⏳ *Generando imagen...*\n_{prompt[:200]}_\n\n"
        f"Te la mando en unos segundos. (job #{job_id})"
    )


def texto_sin_pendiente() -> str:
    return (
        "No tienes ninguna imagen pendiente de confirmar.\n"
        "Envía *dona imagen <descripción>* para generar una."
    )


def texto_pedir_sujeto() -> str:
    """Respuesta cuando el usuario pide imagen pero no especifica sujeto."""
    return (
        "🎨 ¿De qué te gustaría la imagen?\n\n"
        "Dime qué quieres y la genero. Ejemplo:\n"
        "_genera una imagen de un perro astronauta en Marte_"
    )


def texto_cancelada() -> str:
    return "Listo, descarté el pedido. No se cobró nada."
