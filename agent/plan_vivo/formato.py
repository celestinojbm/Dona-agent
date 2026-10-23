"""Notificaciones del plan (F14).

Decisión de Celestino (2026-10-21): el **plan vivo vive sólo en la app** (panel
`PlanVivoPanel`). **No hay plan vivo en WhatsApp** — no se manda el checklist en
vivo ni se reedita un mensaje con el avance paso a paso.

Lo único que puede ir a WhatsApp es un aviso TERMINAL breve (listo / falló),
opcional, cuando la tarea ya concluyó — eso no es "plan vivo", es una
notificación de cierre. Durante la ejecución no se envía nada a WhatsApp.
"""

from __future__ import annotations

# Estados terminales para los que tiene sentido un aviso breve de cierre.
_AVISO_TERMINAL = {
    "completado": "Listo.",
    "parcial": "Terminé con algunos pasos pendientes. Revisa el detalle en la app.",
    "fallido": "No pude completar la tarea. Revisa el detalle en la app.",
    "cancelado": "Tarea cancelada.",
}


def notificacion_terminal(plan: dict) -> str | None:
    """Aviso breve para WhatsApp SÓLO en estados terminales. Devuelve None para
    estados en curso/preparado (no se notifica el plan vivo por WhatsApp)."""
    return _AVISO_TERMINAL.get(plan.get("estado", ""))
