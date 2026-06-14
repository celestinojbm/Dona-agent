# agent/business/reportes.py — Reportes de negocio para proactividad

"""
Genera reportes de negocio para integrar en morning brief y weekly review.
"""

import logging
from datetime import datetime

from agent.business.crm import obtener_seguimientos_pendientes
from agent.business.finanzas import (
    obtener_perfil_negocio,
    resumen_financiero,
    top_productos_vendidos,
)
from agent.business.pedidos import listar_pedidos

logger = logging.getLogger("dona")


async def generar_reporte_diario(telefono: str) -> str | None:
    """
    Genera un resumen de negocio para el morning brief.
    Retorna None si el usuario no tiene perfil de negocio.
    """
    perfil = await obtener_perfil_negocio(telefono)
    if not perfil:
        return None

    moneda = perfil.get("moneda", "$")
    lineas = []

    # Pedidos pendientes
    try:
        pedidos = await listar_pedidos(telefono, limite=5)
        if pedidos:
            lineas.append(f"📋 *Pedidos pendientes:* {len(pedidos)}")
            for p in pedidos[:3]:
                fecha = ""
                if p.get("fecha_entrega"):
                    try:
                        dt = datetime.fromisoformat(p["fecha_entrega"])
                        fecha = f" ({dt.strftime('%d/%m %H:%M')})"
                    except Exception:
                        pass
                lineas.append(f"  • #{p['id']} {p['descripcion'][:40]}{fecha}")
            if len(pedidos) > 3:
                lineas.append(f"  ... y {len(pedidos) - 3} más")
    except Exception as e:
        logger.debug(f"reporte_diario pedidos: {e}")

    # Seguimientos pendientes
    try:
        segs = await obtener_seguimientos_pendientes(telefono, limite=3)
        if segs:
            lineas.append(f"\n👤 *Seguimientos pendientes:* {len(segs)}")
            for s in segs:
                lineas.append(f"  • {s['cliente'] or 'Cliente'}: {s['descripcion'][:40]}")
    except Exception as e:
        logger.debug(f"reporte_diario seguimientos: {e}")

    # Resumen financiero del mes
    try:
        fin = await resumen_financiero(telefono, "mes")
        if fin["ventas"]["count"] > 0:
            lineas.append("\n💰 *Mes actual:*")
            lineas.append(f"  Ventas: {moneda}{fin['ventas']['total']:,.0f} ({fin['ventas']['count']} transacciones)")
            if fin["gastos"]["total"] > 0:
                lineas.append(f"  Gastos: {moneda}{fin['gastos']['total']:,.0f}")
                lineas.append(f"  Utilidad: {moneda}{fin['utilidad']:,.0f} ({fin['margen_pct']}% margen)")
            if fin.get("progreso_meta_pct") is not None:
                lineas.append(f"  Meta: {fin['progreso_meta_pct']}% ({moneda}{fin['meta_mensual']:,.0f})")
    except Exception as e:
        logger.debug(f"reporte_diario finanzas: {e}")

    if not lineas:
        return None

    return "\n".join(lineas)


async def generar_reporte_semanal(telefono: str) -> str | None:
    """
    Genera un resumen semanal más detallado para el weekly review.
    Retorna None si el usuario no tiene perfil de negocio.
    """
    perfil = await obtener_perfil_negocio(telefono)
    if not perfil:
        return None

    moneda = perfil.get("moneda", "$")
    lineas = [f"📊 *Resumen semanal — {perfil.get('nombre', 'Tu negocio')}*\n"]

    # Finanzas de la semana
    try:
        fin = await resumen_financiero(telefono, "semana")
        lineas.append(f"💰 *Ventas:* {moneda}{fin['ventas']['total']:,.0f} ({fin['ventas']['count']} transacciones)")
        if fin["gastos"]["total"] > 0:
            lineas.append(f"📉 *Gastos:* {moneda}{fin['gastos']['total']:,.0f}")
            lineas.append(f"💵 *Utilidad:* {moneda}{fin['utilidad']:,.0f} ({fin['margen_pct']}% margen)")
    except Exception as e:
        logger.debug(f"reporte_semanal finanzas: {e}")

    # Top productos
    try:
        top = await top_productos_vendidos(telefono, dias=7, limite=3)
        if top:
            lineas.append("\n🏆 *Más vendidos esta semana:*")
            for i, p in enumerate(top, 1):
                lineas.append(f"  {i}. {p['producto']} — {moneda}{p['total']:,.0f} ({p['cantidad']}x)")
    except Exception as e:
        logger.debug(f"reporte_semanal top: {e}")

    # Pedidos completados vs pendientes
    try:
        pendientes = await listar_pedidos(telefono, limite=50)
        lineas.append(f"\n📋 *Pedidos activos:* {len(pendientes)}")
    except Exception as e:
        logger.debug(f"reporte_semanal pedidos: {e}")

    if len(lineas) <= 1:
        return None

    return "\n".join(lineas)
