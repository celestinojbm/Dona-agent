"""Canales secundarios (F35).

Decisión de Celestino (2026-10-22): WhatsApp queda SOLO para avisos y
aprobaciones; el trabajo vive en la app (app-first). Generaliza la regla de F14
(el plan vivo vive sólo en la app; a WhatsApp sólo un aviso terminal breve, ver
`agent/plan_vivo/formato.py`) a todo el producto.

Este paquete es POLÍTICA PURA: decide qué propósito puede ir a WhatsApp y
redacta copy breve. No envía, no llama a `envio_gate.puede_enviar` y no está
cableado a ningún punto de salida. TCPA, quiet hours, opt-out y límite diario
siguen siendo responsabilidad exclusiva de `agent/envio_gate.py`.

Flag DONA_WHATSAPP_SOLO_AVISOS_ENABLED=false por defecto.
"""

from agent.canales.politica_whatsapp import (
    PROPOSITOS_WHATSAPP,
    DecisionCanal,
    decidir_canal,
    flag_solo_avisos_activo,
    redactar_aprobacion,
    redactar_aviso,
)

__all__ = [
    "PROPOSITOS_WHATSAPP",
    "DecisionCanal",
    "decidir_canal",
    "flag_solo_avisos_activo",
    "redactar_aprobacion",
    "redactar_aviso",
]
