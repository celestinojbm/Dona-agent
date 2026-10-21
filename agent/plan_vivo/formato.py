"""Formato del plan vivo para WhatsApp (F14).

En WhatsApp (sin CSS) el plan es una lista con marcadores por estado. Si Whapi
permite editar el mismo mensaje, el caller reedita `mensaje_ref`; si no,
actualizaciones coalescidas (menos frecuentes). El soporte de edición de Whapi
está pendiente de confirmación (ver preguntas-celestino.md #10).
"""

from __future__ import annotations

_MARCADOR = {
    "pendiente": "◻︎",
    "en_curso": "▶︎",
    "completado": "✅",
    "fallido": "⚠️",
}

_ENCABEZADO_ESTADO = {
    "preparado": "Esto es lo que haré. ¿Lo confirmo o ajustamos el plan?",
    "en_curso": "Dona trabajando…",
    "completado": "Listo.",
    "parcial": "Terminé con algunos pasos pendientes.",
    "fallido": "No pude completar el plan.",
    "cancelado": "Plan cancelado.",
    "requiere_revision": "Necesito que revises el plan.",
    "pendiente": "Plan en espera.",
}


def render_whatsapp(plan: dict) -> str:
    """Renderiza el checklist del plan como texto para WhatsApp."""
    lineas = [f"*{_ENCABEZADO_ESTADO.get(plan.get('estado', ''), 'Plan')}*"]
    pasos = plan.get("pasos", [])
    for i, paso in enumerate(pasos, 1):
        marca = _MARCADOR.get(paso.get("estado", "pendiente"), "◻︎")
        titulo = paso.get("titulo", "")
        linea = f"{marca} {i}. {titulo}"
        if paso.get("estado") == "fallido" and paso.get("resultado"):
            linea += f" — {paso['resultado']}"
        lineas.append(linea)
    coste = plan.get("coste_maximo")
    if coste:
        lineas.append("")
        lineas.append(f"Coste máximo: {coste} créditos.")
    return "\n".join(lineas)
