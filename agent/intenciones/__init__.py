"""Memoria de intenciones mencionadas una sola vez (F28 · subsección).

Decisión de Celestino (2026-10-22, roadmap F1–F35): Dona puede guardar como
«intención» algo que el usuario dijo de pasada y proponerlo más adelante, pero
una intención nunca es una autorización.

Este paquete es POLÍTICA PURA: detecta, filtra datos sensibles, propone el chip
«¿Lo recuerdo?» y calcula el vencimiento de 30 días. No persiste, no envía, no
autoriza y no está cableado a `main.py` ni al cerebro.

Flag DONA_MEMORIA_INTENCIONES_ENABLED=false por defecto.
"""

from agent.intenciones.politica import (
    DIAS_VIGENCIA,
    PREGUNTA_CHIP,
    DecisionIntencion,
    Intencion,
    PropuestaIntencion,
    aceptar_propuesta,
    es_sensible,
    esta_vigente,
    evaluar_mensaje,
    flag_intenciones_activo,
    redactar_sugerencia,
)

__all__ = [
    "DIAS_VIGENCIA",
    "PREGUNTA_CHIP",
    "DecisionIntencion",
    "Intencion",
    "PropuestaIntencion",
    "aceptar_propuesta",
    "es_sensible",
    "esta_vigente",
    "evaluar_mensaje",
    "flag_intenciones_activo",
    "redactar_sugerencia",
]
