# agent/creativos/comandos.py — Detección y render de comandos creativos

"""
Comandos tipo "dona imagen <prompt>" + "confirmar" / "cancelar" para
el flujo 2 pasos. Se invocan desde main.py antes del routing al LLM,
para que queden determinísticos (no dependen de que Claude llame un tool).
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger("agentkit")


# ── Detectores ──────────────────────────────────────────────────────────────

# "dona imagen <prompt>" o "dona imágen <prompt>" o "dona image <prompt>"
_RE_IMAGEN = re.compile(
    r"^\s*dona\s+im[aá]gen?\b\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

# Premium: "dona imagen premium <prompt>" o "dona imagen hd <prompt>"
_RE_PREMIUM = re.compile(r"^\s*(premium|hd|pro)\s+(.+)$", re.IGNORECASE | re.DOTALL)

# Aspect ratio: "--16:9 prompt..." o "--vertical prompt..."
_RE_ASPECT = re.compile(r"(?:^|\s)--(16:9|9:16|1:1|4:3|3:4|horizontal|vertical|cuadrado)\b", re.IGNORECASE)

_CONFIRMAR = {"confirmar", "si", "sí", "dale", "ok", "confirmo", "dona confirmar", "dona si", "dona sí"}
_CANCELAR  = {"cancelar", "no", "dona cancelar", "dona no"}


def es_comando_imagen(texto: str) -> bool:
    """True si el mensaje inicia con 'dona imagen' y trae prompt."""
    if not texto:
        return False
    m = _RE_IMAGEN.match(texto)
    if not m:
        return False
    return bool((m.group(1) or "").strip())


def parsear_imagen(texto: str) -> dict:
    """
    Extrae prompt, calidad y aspect_ratio del comando.
    Asume `es_comando_imagen(texto)` == True.
    """
    m = _RE_IMAGEN.match(texto)
    cuerpo = (m.group(1) or "").strip() if m else ""

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


def texto_cancelada() -> str:
    return "Listo, descarté el pedido. No se cobró nada."
