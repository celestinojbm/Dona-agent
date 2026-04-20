# agent/billing_commands.py — Comandos de usuario relacionados a créditos

"""
`dona saldo`, `dona recargar`, `dona mis assets`: comandos de descubrimiento
para el sistema de billing. Viven separados de billing.py para mantener la
lógica pura (billing) aislada de la lógica de presentación (este archivo).

Testeables sin FastAPI ni proveedores de WhatsApp.
"""

from __future__ import annotations

import logging
from agent.billing import (
    obtener_resumen,
    crear_checkout,
    paquetes_disponibles,
)
from agent.storage import listar_assets_usuario

logger = logging.getLogger("agentkit")


# ── Detección ──────────────────────────────────────────────────────────────

_COMANDOS_SALDO = {
    "dona saldo", "dona credit", "dona creditos", "dona créditos",
    "dona mi saldo", "dona cuantos creditos tengo", "dona cuántos créditos tengo",
}

_COMANDOS_RECARGAR = {
    "dona recargar", "dona recarga", "dona comprar creditos", "dona comprar créditos",
    "dona comprar", "dona top up", "dona topup",
}

_COMANDOS_MIS_ASSETS = {
    "dona mis assets", "dona mis archivos", "dona mis creaciones",
    "dona mis imagenes", "dona mis imágenes", "dona mis videos",
    "dona historial creativo", "dona mi galeria", "dona mi galería",
}


def _normalizar(texto: str) -> str:
    return (texto or "").strip().lower()


def es_comando_saldo(texto: str) -> bool:
    return _normalizar(texto) in _COMANDOS_SALDO


def es_comando_recargar(texto: str) -> bool:
    return _normalizar(texto) in _COMANDOS_RECARGAR


def es_comando_mis_assets(texto: str) -> bool:
    return _normalizar(texto) in _COMANDOS_MIS_ASSETS


# ── Render ──────────────────────────────────────────────────────────────────

async def texto_saldo(telefono: str) -> str:
    """Muestra saldo + últimas transacciones + hint para recargar."""
    r = await obtener_resumen(telefono)
    lineas = [
        "💳 *Tu saldo Dona*",
        "",
        f"Disponible: *{r['saldo']} créditos*",
        f"Total comprado: {r['total_comprado']} · consumido: {r['total_consumido']}",
    ]
    if r["ultimos"]:
        lineas.append("")
        lineas.append("*Últimos movimientos:*")
        for tx in r["ultimos"]:
            signo = "+" if tx["delta"] > 0 else ""
            lineas.append(f"• {signo}{tx['delta']} — {tx['razon'] or '(sin razón)'}")
    if r["saldo"] < 20:
        lineas.append("")
        lineas.append("_Escribe *\"dona recargar\"* para comprar más créditos._")
    return "\n".join(lineas)


async def texto_recargar(telefono: str) -> str:
    """
    Lista paquetes disponibles y genera un link de Stripe Checkout para cada uno.
    Si Stripe no está configurado, informa cómo proceder.
    """
    packs = paquetes_disponibles()
    if not packs:
        return (
            "🛒 *Compra de créditos*\n\n"
            "Todavía no está conectado el procesador de pagos.\n"
            "Contacta al equipo de Dona para recargar manualmente."
        )

    lineas = ["🛒 *Elige tu paquete*", ""]
    for p in packs:
        url = await crear_checkout(telefono, p.codigo)
        if url:
            lineas.append(f"*{p.creditos} créditos* — ${p.precio_usd:.0f}")
            lineas.append(f"  {url}")
            lineas.append("")
        else:
            lineas.append(f"*{p.creditos} créditos* — ${p.precio_usd:.0f} (no disponible)")
    lineas.append("_El link expira en 24 h. Pago seguro por Stripe._")
    return "\n".join(lineas)


async def texto_mis_assets(telefono: str) -> str:
    """Últimos 10 assets generados por el usuario."""
    assets = await listar_assets_usuario(telefono, limite=10)
    if not assets:
        return (
            "📂 *Tu galería*\n\n"
            "Todavía no tienes creaciones guardadas.\n"
            "Pídeme imágenes, videos o diseños y los veras acá."
        )

    lineas = ["📂 *Tus últimas creaciones*", ""]
    for a in assets:
        tipo = a.get("tipo", "?")
        modelo = a.get("modelo") or "-"
        url = a.get("url") or ""
        # Resumen compacto para WhatsApp
        prompt_prev = (a.get("prompt") or "").strip().replace("\n", " ")[:60]
        if prompt_prev:
            lineas.append(f"• [{tipo}] {prompt_prev}…")
        else:
            lineas.append(f"• [{tipo}] ({modelo})")
        if url:
            lineas.append(f"  {url}")
    return "\n".join(lineas)
