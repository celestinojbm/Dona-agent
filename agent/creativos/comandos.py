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


# ── Quitar fondo (Photoroom) ────────────────────────────────────────────────
# Dos entradas:
#   1) Imagen adjunta con caption → `es_comando_bg_remove(caption)`
#   2) Texto suelto pidiendo hacerlo sobre la última imagen del usuario →
#      `es_comando_bg_remove_ultima(texto)`

# Frases como "quita el fondo", "quitame el fondo", "remueve el fondo",
# "saca el fondo", "sin fondo", "fondo transparente", "remove background",
# "bg remove". Case-insensitive, toleran signos y espacios.
_RE_BG_REMOVE_BASE = re.compile(
    r"(?:"
    r"qu[ií]t(?:a|ame|a\s*me|alo|ar)\s+(?:el\s+)?fondo"
    r"|elim[ií]na(?:me|r|lo)?\s+(?:el\s+)?fondo"
    r"|b[oó]rra(?:me|r|lo)?\s+(?:el\s+)?fondo"
    r"|rem[uú]e?ve(?:me|lo|r)?\s+(?:el\s+)?fondo"
    r"|remover\s+(?:el\s+)?fondo"
    r"|s[aá]ca(?:me|lo|r)?\s+(?:el\s+)?fondo"
    r"|(?:deja(?:lo|la|me)?|d[eé]jalo)\s+sin\s+fondo"
    r"|sin\s+fondo"
    r"|fondo\s+transparente"
    r"|(?:remove|delete|erase)\s+background"
    r"|(?:^|\W)bg\s*remove(?:\W|$)"
    r"|no\s+fondo"
    r")",
    re.IGNORECASE,
)

# Variante "a la última / esta / esa imagen" para texto suelto.
_RE_BG_REMOVE_ULTIMA_HINT = re.compile(
    r"(?:"
    r"(?:a\s+)?(?:la|mi|esa|esta|la\s+última|la\s+ultima|lo|esto)\s+"
    r"(?:im[aá]gen|foto|dibujo|ilustraci[oó]n|imagen)"
    r"|(?:de|a|sobre)\s+(?:la|mi|esa|esta)\s+"
    r"(?:im[aá]gen|foto)"
    r"|(?:\b|_)(?:imagen|foto|dibujo)\s+(?:anterior|de\s+arriba|previa)"
    r")",
    re.IGNORECASE,
)


def es_comando_bg_remove(caption: str) -> bool:
    """
    True si el caption de una imagen adjunta pide quitar el fondo.
    Se llama SOLO cuando llega una imagen con caption.
    """
    if not caption:
        return False
    return bool(_RE_BG_REMOVE_BASE.search(caption))


# ── Voz (ElevenLabs) ────────────────────────────────────────────────────────
# Detecta: "lee esto en voz/audio", "hazme un audio de X", "audio: X",
# "di: X", "léeme: X", "convierte a audio: X", "pasa a audio ...".
# El contenido a leer queda en `group(1)`.

# Patrones de voz en orden de especificidad (más específico primero).
# El primero que matchee gana — evita que "lee esto en voz alta: X" capture
# "esto en voz alta: X" como contenido cuando debería capturar solo "X".
_PATRONES_VOZ = (
    # "lee esto en voz alta/audio: X"
    re.compile(
        r"^[\s¿¡]*(?:dona[,\s]+)?"
        r"(?:l[eé]e|di|dime|cuenta)\s+(?:esto|lo\s+siguiente)\s+"
        r"(?:en\s+(?:voz|audio)(?:\s+alta)?|como\s+audio|con\s+voz)"
        r"\s*[:\-]\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    # "convierte/pasa/transforma (esto) a/en audio(:) X"
    re.compile(
        r"^[\s¿¡]*(?:dona[,\s]+)?"
        r"(?:convierte|pasa|transforma)\s+(?:esto\s+)?(?:a|en)\s+(?:audio|voz|nota\s+de\s+voz)"
        r"\s*[:\-]?\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    # "hazme/genera/crea (un/una) audio/voz/nota de voz (de|con|que diga|diciendo)(:) X"
    re.compile(
        r"^[\s¿¡]*(?:dona[,\s]+)?"
        r"(?:h[aá]z(?:me)?|haga(?:me)?|genera(?:me)?|gen[eé]ra(?:me)?|cr[eé]a(?:me)?|dame|quiero|necesito|graba(?:me)?)"
        r"\s+(?:(?:una?|un|el|la|mi)\s+)?"
        r"(?:audio|nota\s+de\s+voz|voz|locuci[oó]n|mensaje\s+de\s+voz)"
        r"\s+(?:de|con|que\s+diga|diciendo|para|sobre)"
        r"\s*[:\-]?\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    # "audio/voz/nota de voz: X" — siempre requiere ":"
    re.compile(
        r"^[\s¿¡]*(?:dona[,\s]+)?"
        r"(?:audio|voz|nota\s+de\s+voz|locuci[oó]n)"
        r"\s*[:\-]\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    # "di/dime/dilo/léeme/narra (eso)(:) X" — verbos imperativos de "hablar"
    # Se pone al final para no capturar "lee esto en voz alta: X" (ya cubierto arriba).
    re.compile(
        r"^[\s¿¡]*(?:dona[,\s]+)?"
        r"(?:d[ií](?:me|lo|la|selo)?|l[eé]e(?:me|lo|la)?|narr(?:a|ame|alo|ala))"
        r"\s*[:\-]\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    # "léeme esta frase X" — verbo + objeto implícito, sin dos puntos
    re.compile(
        r"^[\s¿¡]*(?:dona[,\s]+)?"
        r"l[eé]e(?:me|lo|la)\s+(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
)


def _match_voz(texto: str):
    for pat in _PATRONES_VOZ:
        m = pat.match(texto)
        if m:
            cuerpo = (m.group(1) or "").strip()
            if cuerpo:
                return pat, cuerpo
    return None, ""


def es_comando_voz(texto: str) -> bool:
    if not texto:
        return False
    pat, cuerpo = _match_voz(texto)
    return pat is not None and bool(cuerpo)


def parsear_voz(texto: str) -> dict:
    """Extrae el `texto` a convertir en voz. Asume `es_comando_voz(texto)==True`."""
    _, cuerpo = _match_voz(texto or "")
    return {"texto": cuerpo}


def es_comando_bg_remove_ultima(texto: str) -> bool:
    """
    True si el texto suelto (sin imagen adjunta) pide quitar el fondo a una
    imagen previa. Requiere ambos: frase de 'quitar fondo' Y referencia a
    imagen ('la imagen', 'la última', etc.).
    """
    if not texto:
        return False
    if not _RE_BG_REMOVE_BASE.search(texto):
        return False
    return bool(_RE_BG_REMOVE_ULTIMA_HINT.search(texto))


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


# ── Render: bg_remove ───────────────────────────────────────────────────────

def texto_bg_remove_preview(preview: dict) -> str:
    """Mensaje mostrado al usuario tras `preparar_bg_remove_*`."""
    costo = preview["costo_creditos"]
    saldo = preview["saldo_actual"]
    alcanza = preview["alcanza"]
    ttl = preview["ttl_min"]

    partes = [
        "✂️ *Voy a quitar el fondo de la imagen*",
        "",
        f"• Costo: *{costo} crédito* (saldo: {saldo})",
        "",
    ]
    if not alcanza:
        partes.append(
            f"⚠️ No te alcanzan los créditos ({saldo}/{costo}). "
            "Escribe *dona recargar* para comprar más."
        )
    else:
        partes.append(
            f"Responde *confirmar* para procesar, o *cancelar* para descartar. "
            f"(Expira en {ttl} min)"
        )
    return "\n".join(partes)


def texto_bg_remove_encolada(job_id: int) -> str:
    return (
        f"⏳ *Quitando el fondo...*\n\n"
        f"Te mando la versión sin fondo en unos segundos. (job #{job_id})"
    )


def texto_bg_remove_sin_imagen() -> str:
    return (
        "No encuentro ninguna imagen tuya reciente.\n\n"
        "Envíame una foto con el mensaje _quita el fondo_ y lo hago al toque."
    )


def texto_voz_preview(preview: dict) -> str:
    """Mensaje mostrado tras `preparar_voz`."""
    costo = preview["costo_creditos"]
    saldo = preview["saldo_actual"]
    alcanza = preview["alcanza"]
    chars = preview["chars"]
    ttl = preview["ttl_min"]
    preview_txt = preview["texto"][:150] + ("..." if len(preview["texto"]) > 150 else "")

    partes = [
        "🎙️ *Voy a grabar esto en voz:*",
        f"_{preview_txt}_",
        "",
        f"• Largo: {chars} caracteres",
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
            f"Responde *confirmar* para grabar, o *cancelar* para descartar. "
            f"(Expira en {ttl} min)"
        )
    return "\n".join(partes)


def texto_voz_encolada(job_id: int) -> str:
    return (
        f"⏳ *Grabando...*\n\n"
        f"Te mando la nota de voz en unos segundos. (job #{job_id})"
    )


def texto_bg_remove_no_servible() -> str:
    return (
        "Tengo registro de tu imagen pero está en almacenamiento local y "
        "no puedo procesarla. Vuelve a enviármela con el mensaje _quita el fondo_."
    )
