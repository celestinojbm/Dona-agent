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


# ── Video (Replicate) y Video con avatar (HeyGen) ───────────────────────────
# Dos intents:
#   1) Video genérico: "video de un perro corriendo", "hazme un video de X"
#   2) Video con avatar: "video con avatar diciendo X", "video presentador: X"
# El avatar se chequea ANTES (más específico).

# Hints que identifican "avatar parlante" — palabra distintiva + opcional verbo
# de habla. Basta con una de: avatar, presentador, locutor, vocero, portavoz.
_AVATAR_HINT = r"(?:avatar|presentadora|presentador|locutora|locutor|vocera|vocero|portavoz|anchor)"

# 1) "video (con|de|usando) avatar/presentador (diciendo|que diga|leyendo)(:) X"
_RE_VIDEO_AVATAR = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    r"(?:(?:h[aá]z(?:me)?|genera(?:me)?|cr[eé]a(?:me)?|dame|quiero|necesito)\s+)?"
    r"(?:(?:un|una)\s+)?"
    r"video\s+(?:con|de|usando)\s+"
    r"(?:un\s+|una\s+)?" + _AVATAR_HINT +
    r"\s*(?:(?:diciendo|que\s+diga|leyendo|narrando|presentando)\s*)?"
    r"[:\-]?\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)

# 2) "video presentador: X" / "avatar dice: X"
_RE_VIDEO_AVATAR_CORTO = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    r"(?:video\s+)?" + _AVATAR_HINT +
    r"\s*(?:dice|diga|lee|narra|presenta)?"
    r"\s*[:\-]\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)

_PATRONES_VIDEO_AVATAR = (_RE_VIDEO_AVATAR, _RE_VIDEO_AVATAR_CORTO)

# 3) Video genérico:
#    "dona video <prompt>"
#    "hazme un video de X", "genera un video con Y"
#    "video de X", "video: X"
_RE_VIDEO_DIRECTO = re.compile(
    r"^[\s¿¡]*dona\s+videos?\b[\s:,\-]*"
    r"(?:(?:de|con|que|sobre|para|del)\s+)?"
    r"(.+)$",
    re.IGNORECASE | re.DOTALL,
)

_RE_VIDEO_VERBO = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    r"(?:h[aá]z(?:me)?|haga(?:me)?|genera(?:me)?|gen[eé]ra(?:me)?|"
    r"cr[eé]a(?:me)?|dame|p[oó]n(?:me)?|m[aá]nda(?:me)?|"
    r"quiero|necesito|"
    r"puedes\s+(?:hacer|generar|crear|mandar|dar|enviar)(?:me)?|"
    r"podr[ií]as\s+(?:hacer|generar|crear|mandar|dar|enviar)(?:me)?)"
    r"\s+(?:(?:un|el|mi|unos)\s+)?"
    r"videos?"
    r"(?:\s+(?:de|con|que|sobre|para|del))?"
    r"[\s:,\-]+(.+)$",
    re.IGNORECASE | re.DOTALL,
)

_RE_VIDEO_SUST = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    r"videos?"
    r"\s*(?:[:\-]|de\s+|con\s+|sobre\s+|para\s+|del\s+)\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)

_PATRONES_VIDEO = (_RE_VIDEO_DIRECTO, _RE_VIDEO_VERBO, _RE_VIDEO_SUST)


def _match_video_avatar(texto: str):
    for pat in _PATRONES_VIDEO_AVATAR:
        m = pat.match(texto)
        if m:
            cuerpo = (m.group(1) or "").strip()
            if cuerpo:
                return pat, cuerpo
    return None, ""


def _match_video(texto: str):
    for pat in _PATRONES_VIDEO:
        m = pat.match(texto)
        if m:
            cuerpo = (m.group(1) or "").strip()
            if cuerpo:
                return pat, cuerpo
    return None, ""


def es_comando_video_avatar(texto: str) -> bool:
    if not texto:
        return False
    pat, cuerpo = _match_video_avatar(texto)
    return pat is not None and bool(cuerpo)


def parsear_video_avatar(texto: str) -> dict:
    """Extrae el guion. Asume `es_comando_video_avatar(texto)==True`."""
    _, cuerpo = _match_video_avatar(texto or "")
    return {"texto": cuerpo}


def es_comando_video(texto: str) -> bool:
    """True si es video genérico (no avatar). Avatar se chequea antes."""
    if not texto:
        return False
    if es_comando_video_avatar(texto):
        return False
    pat, cuerpo = _match_video(texto)
    return pat is not None and bool(cuerpo)


def parsear_video(texto: str) -> dict:
    _, cuerpo = _match_video(texto or "")
    return {"prompt": cuerpo}


# ── Documentos (factura / presupuesto / recibo) ─────────────────────────────
# Detecta pedidos como:
#   "dona factura para Juan $500 por consultoría"
#   "hazme un recibo de $200 a María"
#   "presupuesto para limpiar oficina"
# Devuelve `(tipo, cuerpo)` donde `tipo` ∈ {factura, presupuesto, recibo}.
# El cuerpo entero se pasa al LLM para extracción de campos estructurados.

# Mapa: alias del usuario → tipo canónico
_ALIAS_DOC = {
    "factura": "factura",
    "facturas": "factura",
    "invoice": "factura",
    "presupuesto": "presupuesto",
    "presupuestos": "presupuesto",
    "cotizacion": "presupuesto",
    "cotización": "presupuesto",
    "cotizaciones": "presupuesto",
    "quote": "presupuesto",
    "recibo": "recibo",
    "recibos": "recibo",
    "receipt": "recibo",
}
_SUSTANTIVOS_DOC = (
    r"(?:factura|facturas|invoice|presupuesto|presupuestos|"
    r"cotizaci[oó]n|cotizaciones|quote|recibo|recibos|receipt)"
)

# 1) "dona <tipo> <cuerpo>"
_RE_DOC_DIRECTO = re.compile(
    r"^[\s¿¡]*dona\s+(" + _SUSTANTIVOS_DOC + r")\b[\s:,-]*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

# 2) Verbo imperativo + (un|una)? + <tipo> + cuerpo
#    Ej: "hazme una factura para X", "genera un recibo de Y", "crea un presupuesto"
_RE_DOC_VERBO = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    r"(?:h[aá]z(?:me)?|haga(?:me)?|genera(?:me)?|gen[eé]ra(?:me)?|"
    r"cr[eé]a(?:me)?|dame|p[oó]n(?:me)?|m[aá]nda(?:me)?|"
    r"quiero|necesito|emite|emitir|escribe|escr[ií]beme|"
    r"puedes\s+(?:hacer|generar|crear|emitir|dar|mandar|enviar)(?:me)?|"
    r"me\s+puedes\s+(?:hacer|generar|crear|emitir|dar|mandar|enviar)(?:me)?|"
    r"podr[ií]as\s+(?:hacer|generar|crear|emitir|dar|mandar|enviar)(?:me)?)"
    r"\s+(?:(?:una?|un|el|la|mi)\s+)?"
    r"(" + _SUSTANTIVOS_DOC + r")"
    r"\b[\s:,-]*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

# 3) "<tipo>: cuerpo" o "<tipo> para/de/a cuerpo"
#    Requiere que tras el sustantivo venga una preposición o ":" — evita
#    que "factura" suelto matchee (no hay cuerpo suficiente).
_RE_DOC_SUST = re.compile(
    r"^[\s¿¡]*(?:dona[,\s]+)?"
    r"(" + _SUSTANTIVOS_DOC + r")"
    r"\s*(?:[:\-]|para|de(?:\s+cliente)?|a(?:\s+nombre\s+de)?|por)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)

_PATRONES_DOC = (_RE_DOC_DIRECTO, _RE_DOC_VERBO, _RE_DOC_SUST)


def _match_documento(texto: str):
    """Devuelve (tipo, cuerpo) o (None, '')."""
    for pat in _PATRONES_DOC:
        m = pat.match(texto)
        if m:
            alias = (m.group(1) or "").lower()
            tipo = _ALIAS_DOC.get(alias) or _ALIAS_DOC.get(alias.replace("ó", "o"))
            cuerpo = (m.group(2) or "").strip()
            if tipo and cuerpo:
                return tipo, cuerpo
    return None, ""


def es_comando_documento(texto: str) -> bool:
    if not texto:
        return False
    tipo, cuerpo = _match_documento(texto)
    return tipo is not None and bool(cuerpo)


def parsear_documento(texto: str) -> dict:
    """Extrae `tipo` y `cuerpo`. Asume `es_comando_documento(texto)==True`."""
    tipo, cuerpo = _match_documento(texto or "")
    return {"tipo": tipo, "cuerpo": cuerpo}


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


# Tokens inequívocos — sólo disparan el aviso "no hay pendiente" cuando el
# usuario escribe algo claramente dirigido al flujo preparar/confirmar, no
# un "sí" o "no" conversacional que podría estar respondiendo a otra cosa.
_CONFIRMAR_INEQUIVOCO = {"confirmar", "confirmo", "dona confirmar"}
_CANCELAR_INEQUIVOCO = {"cancelar", "dona cancelar"}


def es_confirmar_inequivoco(texto: str) -> bool:
    if not texto:
        return False
    return texto.strip().lower() in _CONFIRMAR_INEQUIVOCO


def es_cancelar_inequivoco(texto: str) -> bool:
    if not texto:
        return False
    return texto.strip().lower() in _CANCELAR_INEQUIVOCO


# ── Render de respuestas ────────────────────────────────────────────────────

def _linea_reemplazo(preview: dict) -> str:
    """
    Si `preparar_X` canceló un pedido anterior (otro tipo de creativo), el
    preview incluye `reemplazo` con su etiqueta legible. Retorna una línea
    de aviso para prepender, o "" si no había nada que reemplazar.
    """
    etiqueta = preview.get("reemplazo")
    if not etiqueta:
        return ""
    return f"🔄 Reemplacé tu pedido anterior ({etiqueta}) por este.\n\n"


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
    return _linea_reemplazo(preview) + "\n".join(partes)


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


def texto_sin_nada_que_confirmar() -> str:
    """Respuesta cuando el usuario dice `confirmar` sin tener nada pendiente."""
    return (
        "No tienes nada pendiente por confirmar.\n"
        "Cuando me pidas una imagen, video, nota de voz o documento te mostraré "
        "un preview y podrás responder *confirmar* para generarlo."
    )


def texto_sin_nada_que_cancelar() -> str:
    """Respuesta cuando el usuario dice `cancelar` sin tener nada pendiente."""
    return "No tienes nada pendiente por cancelar."


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
    return _linea_reemplazo(preview) + "\n".join(partes)


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
    return _linea_reemplazo(preview) + "\n".join(partes)


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


# ── Render: documento (factura / presupuesto / recibo) ──────────────────────

_ICONOS_DOC = {"factura": "🧾", "presupuesto": "📄", "recibo": "🧾"}

_TIPO_DISPLAY = {
    "factura": "factura",
    "presupuesto": "presupuesto",
    "recibo": "recibo",
}


def _fmt_moneda(valor: float, moneda: str) -> str:
    simbolo = {"USD": "$", "MXN": "$", "EUR": "€", "GBP": "£"}.get((moneda or "").upper(), "")
    try:
        return f"{simbolo}{float(valor):,.2f}"
    except (TypeError, ValueError):
        return f"{simbolo}0.00"


def texto_documento_preview(preview: dict) -> str:
    """Mensaje mostrado tras `preparar_documento`."""
    tipo = preview.get("tipo", "factura")
    icono = _ICONOS_DOC.get(tipo, "📄")
    display = _TIPO_DISPLAY.get(tipo, tipo)
    costo = preview["costo_creditos"]
    saldo = preview["saldo_actual"]
    alcanza = preview["alcanza"]
    ttl = preview["ttl_min"]
    moneda = preview.get("moneda", "USD")

    partes = [
        f"{icono} *Voy a generar {display}:*",
        f"• Para: _{preview.get('cliente', '(sin cliente)')}_",
        f"• De: _{preview.get('nombre_negocio', 'Mi Negocio')}_",
        "",
    ]

    items = preview.get("items") or []
    if items:
        partes.append("*Ítems:*")
        for it in items[:6]:
            cant = it.get("cantidad", 1)
            desc = str(it.get("descripcion", ""))[:60]
            subtotal = it.get("subtotal", 0)
            partes.append(f"• {desc} x{cant:g} — {_fmt_moneda(subtotal, moneda)}")
        if len(items) > 6:
            partes.append(f"• …y {len(items) - 6} más")
        partes.append("")

    if preview.get("impuesto"):
        partes.append(f"• Subtotal: {_fmt_moneda(preview['subtotal'], moneda)}")
        partes.append(f"• Impuesto: {_fmt_moneda(preview['impuesto'], moneda)}")
    partes.append(f"• *Total: {_fmt_moneda(preview['total'], moneda)}*")
    partes.append("")
    partes.append(f"• Costo: *{costo} créditos* (saldo: {saldo})")
    partes.append("")

    if not alcanza:
        partes.append(
            f"⚠️ No te alcanzan los créditos ({saldo}/{costo}). "
            "Escribe *dona recargar* para comprar más."
        )
    else:
        partes.append(
            f"Responde *confirmar* para generar el PDF, o *cancelar* para descartar. "
            f"(Expira en {ttl} min)"
        )
    return _linea_reemplazo(preview) + "\n".join(partes)


def texto_documento_encolada(job_id: int, tipo: str) -> str:
    display = _TIPO_DISPLAY.get(tipo, tipo)
    return (
        f"⏳ *Generando {display}...*\n\n"
        f"Te mando el PDF en unos segundos. (job #{job_id})"
    )


# ── Render: video genérico (Replicate) ──────────────────────────────────────

def texto_video_preview(preview: dict) -> str:
    costo = preview["costo_creditos"]
    saldo = preview["saldo_actual"]
    alcanza = preview["alcanza"]
    ttl = preview["ttl_min"]
    modelo = preview.get("modelo", "").split("/")[-1].split(":")[0]
    con_referencia = bool(preview.get("image_url"))
    duracion = preview.get("duration_s") or 10
    idea = preview.get("idea_usuario") or preview.get("prompt", "")
    optimizado = preview.get("prompt_optimizado") or ""

    titulo = (
        "🎬 *Voy a generar un video usando tu imagen como referencia:*"
        if con_referencia
        else "🎬 *Voy a generar un video:*"
    )

    partes = [
        titulo,
        f"_{idea}_",
        "",
    ]
    if optimizado and optimizado.strip() != idea.strip():
        # Transparencia: mostramos al usuario cómo Dona refinó su idea para
        # sacar mejor resultado del modelo de video.
        partes.append("*Prompt optimizado para el modelo:*")
        partes.append(f"_{optimizado[:400]}_")
        partes.append("")
    partes.extend([
        f"• Modelo: {modelo}",
        f"• Duración: {duracion}s",
        f"• Costo: *{costo} créditos* (saldo: {saldo})",
        "• Tiempo estimado: 1–3 min",
        "",
    ])
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
    return _linea_reemplazo(preview) + "\n".join(partes)


def texto_video_encolada(job_id: int) -> str:
    return (
        f"⏳ *Generando video...*\n\n"
        f"Puede tardar 1–3 minutos. Te lo mando apenas esté. (job #{job_id})"
    )


# ── Render: video con avatar (HeyGen) ───────────────────────────────────────

def texto_video_avatar_preview(preview: dict) -> str:
    costo = preview["costo_creditos"]
    saldo = preview["saldo_actual"]
    alcanza = preview["alcanza"]
    chars = preview["chars"]
    ttl = preview["ttl_min"]
    texto_preview = preview["texto"][:150] + ("..." if len(preview["texto"]) > 150 else "")

    partes = [
        "🎥 *Voy a grabar video con avatar diciendo:*",
        f"_{texto_preview}_",
        "",
        f"• Largo: {chars} caracteres",
        f"• Costo: *{costo} créditos* (saldo: {saldo})",
        "• Duración estimada: 1–4 minutos",
        "",
    ]
    if preview.get("sin_configurar"):
        partes.append(
            "⚠️ HeyGen no está configurado (falta avatar/voice ID). "
            "El video que generaré será un placeholder."
        )
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
    return _linea_reemplazo(preview) + "\n".join(partes)


def texto_video_avatar_encolada(job_id: int) -> str:
    return (
        f"⏳ *Grabando video con avatar...*\n\n"
        f"Puede tardar 2–5 minutos. Te lo mando apenas esté. (job #{job_id})"
    )
