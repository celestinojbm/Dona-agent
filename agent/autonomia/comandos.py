"""Comandos determinísticos de autonomía (F1), gratis y antes del LLM.

- "autonomía ver"  → muestra los niveles configurados.
- "autonomía <acción> nivel <1-4>" → fija el nivel. SUBIR exige confirmación
  propia (repetir con la palabra "confirmar"); BAJAR es inmediato. El modelo no
  cambia niveles: esto es determinístico, fuera de su routing.
"""

from __future__ import annotations

import re

from agent.autonomia.autorizaciones import fijar_nivel, obtener_config

_RE_VER = re.compile(r"^(?:dona\s+)?autonom[ií]a\s+ver\s*$", re.IGNORECASE)
_RE_NIVEL = re.compile(
    r"^(?:dona\s+)?autonom[ií]a\s+([a-z_]+)\s+nivel\s+([1-4])\s*(confirmar)?\s*$",
    re.IGNORECASE,
)


def es_comando_autonomia(texto: str) -> bool:
    t = (texto or "").strip()
    return bool(_RE_VER.match(t) or _RE_NIVEL.match(t))


async def manejar_comando_autonomia(telefono: str, texto: str) -> str:
    """Devuelve el texto de respuesta para el usuario. Asume que
    es_comando_autonomia(texto) es True."""
    t = (texto or "").strip()
    if _RE_VER.match(t):
        return await _texto_ver(telefono)

    m = _RE_NIVEL.match(t)
    if not m:
        return "No entendí ese comando de autonomía."
    tipo_accion = m.group(1).lower()
    nuevo = int(m.group(2))
    confirmado = bool(m.group(3))

    actual_cfg = await obtener_config(telefono, tipo_accion)
    actual = int(actual_cfg.nivel) if actual_cfg else 1

    if nuevo > actual and not confirmado:
        # Subir autonomía exige confirmación propia explícita.
        return (
            f"Subir *{tipo_accion}* de L{actual} a *L{nuevo}* da más autonomía a Dona.\n"
            f"Para confirmar, escribe:\n"
            f"*autonomía {tipo_accion} nivel {nuevo} confirmar*"
        )

    await fijar_nivel(telefono, tipo_accion, nuevo)
    verbo = "subió" if nuevo > actual else ("bajó" if nuevo < actual else "quedó en")
    return f"Autonomía de *{tipo_accion}* {verbo} a *L{nuevo}*."


async def _texto_ver(telefono: str) -> str:
    from sqlalchemy import select

    from agent.autonomia.models import AutonomiaPorAccion
    from agent.memory import async_session

    async with async_session() as s:
        filas = (await s.execute(
            select(AutonomiaPorAccion)
            .where(AutonomiaPorAccion.telefono == telefono)
            .order_by(AutonomiaPorAccion.tipo_accion)
        )).scalars().all()

    if not filas:
        return (
            "🔐 *Autonomía*\n\n"
            "Todas tus acciones están en *L1* (siempre pido confirmación).\n"
            "Cambia con: *autonomía <acción> nivel <1-4>*"
        )
    lineas = ["🔐 *Autonomía por acción*", ""]
    for f in filas:
        detalle = f"L{f.nivel}"
        if f.nivel == 2 and f.umbral_creditos is not None:
            detalle += f" (umbral {f.umbral_creditos} cr)"
        if f.nivel == 4 and f.tope_periodo is not None:
            detalle += f" (tope {f.tope_periodo} cr/{f.periodo or 'periodo'})"
        lineas.append(f"• {f.tipo_accion}: *{detalle}*")
    lineas.append("")
    lineas.append("_L1 siempre confirma · subir pide confirmación · bajar es inmediato._")
    return "\n".join(lineas)
