# agent/reporting.py — Reportes y exportes para comandos "dona resumen" / "dona exporta"

"""
Genera resúmenes y exportes de los datos del usuario sin salir de WhatsApp.

Funciones principales:
  - resumen_mes(telefono, año, mes) → texto con totales del mes (ventas, gastos, pedidos)
  - exportar_transacciones_csv(telefono, año, mes=None) → bytes CSV
  - exportar_pedidos_csv(telefono, año, mes=None) → bytes CSV

Todas las funciones filtran estrictamente por `telefono` (tenant isolation) —
nunca mezclan datos entre usuarios.
"""

import io
import csv
import logging
from datetime import datetime, timedelta, UTC

from sqlalchemy import select, and_

from agent.memory import async_session
from agent.business.models import Transaccion, Pedido

logger = logging.getLogger("dona")


def _rango_mes_utc(año: int, mes: int) -> tuple[datetime, datetime]:
    """Devuelve (inicio, fin_exclusivo) del mes en UTC."""
    inicio = datetime(año, mes, 1, tzinfo=UTC).replace(tzinfo=None)
    if mes == 12:
        fin = datetime(año + 1, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    else:
        fin = datetime(año, mes + 1, 1, tzinfo=UTC).replace(tzinfo=None)
    return inicio, fin


async def resumen_mes(telefono: str, año: int | None = None, mes: int | None = None) -> str:
    """
    Genera un resumen en texto del mes indicado (default: mes actual UTC).

    Incluye: total de ventas, total de gastos, utilidad bruta, conteo de pedidos
    y top 3 categorías de gasto.
    """
    ahora = datetime.utcnow()
    año = año or ahora.year
    mes = mes or ahora.month
    inicio, fin = _rango_mes_utc(año, mes)

    async with async_session() as session:
        # Transacciones del mes
        q_tx = select(Transaccion).where(
            and_(
                Transaccion.telefono == telefono,
                Transaccion.fecha >= inicio,
                Transaccion.fecha < fin,
            )
        )
        txs = (await session.execute(q_tx)).scalars().all()

        # Pedidos creados en el mes (campo `creado` en el modelo)
        q_ped = select(Pedido).where(
            and_(
                Pedido.telefono == telefono,
                Pedido.creado >= inicio,
                Pedido.creado < fin,
            )
        )
        pedidos_count = len((await session.execute(q_ped)).scalars().all())

    ventas = sum(t.monto for t in txs if t.tipo == "venta")
    gastos = sum(t.monto for t in txs if t.tipo == "gasto")
    utilidad = ventas - gastos

    # Top 3 categorías de gasto
    from collections import Counter
    cats_gasto: Counter[str] = Counter()
    for t in txs:
        if t.tipo == "gasto":
            cats_gasto[t.categoria or "general"] += t.monto
    top_cats = cats_gasto.most_common(3)

    meses_es = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
        7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
    }
    lineas = [
        f"📊 Resumen de {meses_es[mes]} {año}",
        "",
        f"💰 Ventas:   ${ventas:,.2f}",
        f"💸 Gastos:   ${gastos:,.2f}",
        f"📈 Utilidad: ${utilidad:,.2f}",
        f"📦 Pedidos:  {pedidos_count}",
        f"🧾 Transacciones registradas: {len(txs)}",
    ]
    if top_cats:
        lineas.append("")
        lineas.append("Top gastos por categoría:")
        for cat, monto in top_cats:
            lineas.append(f"  • {cat}: ${monto:,.2f}")

    if not txs and pedidos_count == 0:
        lineas.append("")
        lineas.append("No hay movimientos registrados en este período.")

    return "\n".join(lineas)


async def resumen_semana(telefono: str, desde: datetime | None = None) -> str:
    """
    Resumen de los últimos 7 días (o desde `desde` si se indica).

    Pensado para disparar un "weekly recap" proactivo los domingos. Se abstiene
    de generar mensaje si no hay movimientos (retorna string vacío, el caller
    debe chequear).
    """
    ahora = datetime.utcnow()
    inicio = desde or (ahora - timedelta(days=7))

    async with async_session() as session:
        q_tx = select(Transaccion).where(
            and_(
                Transaccion.telefono == telefono,
                Transaccion.fecha >= inicio,
                Transaccion.fecha <= ahora,
            )
        )
        txs = (await session.execute(q_tx)).scalars().all()

        q_ped = select(Pedido).where(
            and_(
                Pedido.telefono == telefono,
                Pedido.creado >= inicio,
                Pedido.creado <= ahora,
            )
        )
        pedidos = (await session.execute(q_ped)).scalars().all()

    # Si no hay movimientos en la semana, el caller puede saltarse el aviso
    if not txs and not pedidos:
        return ""

    ventas = sum(t.monto for t in txs if t.tipo == "venta")
    gastos = sum(t.monto for t in txs if t.tipo == "gasto")
    utilidad = ventas - gastos

    pedidos_entregados = sum(1 for p in pedidos if p.estado == "entregado")
    pedidos_pendientes = sum(1 for p in pedidos if p.estado in ("pendiente", "en_preparacion", "listo"))

    lineas = [
        f"📅 Resumen de tu semana ({inicio.strftime('%d/%m')} → {ahora.strftime('%d/%m')})",
        "",
        f"💰 Ventas:   ${ventas:,.2f}",
        f"💸 Gastos:   ${gastos:,.2f}",
        f"📈 Utilidad: ${utilidad:,.2f}",
    ]
    if pedidos:
        lineas.append(f"📦 Pedidos:  {len(pedidos)} ({pedidos_entregados} entregados, {pedidos_pendientes} en curso)")
    if txs:
        lineas.append(f"🧾 Transacciones: {len(txs)}")

    # Comparación con semana anterior (si hay datos)
    inicio_prev = inicio - timedelta(days=7)
    async with async_session() as session:
        q_tx_prev = select(Transaccion).where(
            and_(
                Transaccion.telefono == telefono,
                Transaccion.fecha >= inicio_prev,
                Transaccion.fecha < inicio,
            )
        )
        txs_prev = (await session.execute(q_tx_prev)).scalars().all()

    if txs_prev:
        ventas_prev = sum(t.monto for t in txs_prev if t.tipo == "venta")
        if ventas_prev > 0:
            delta = ((ventas - ventas_prev) / ventas_prev) * 100
            flecha = "↗️" if delta >= 0 else "↘️"
            lineas.append("")
            lineas.append(f"{flecha} vs. semana pasada: {delta:+.1f}% en ventas")

    return "\n".join(lineas)


async def exportar_transacciones_csv(
    telefono: str, año: int | None = None, mes: int | None = None
) -> bytes:
    """
    Exporta las transacciones del período como CSV (encoding UTF-8 con BOM
    para compatibilidad con Excel).

    Si `mes` es None, exporta todo el año.
    """
    ahora = datetime.utcnow()
    año = año or ahora.year

    if mes:
        inicio, fin = _rango_mes_utc(año, mes)
    else:
        inicio = datetime(año, 1, 1)
        fin = datetime(año + 1, 1, 1)

    async with async_session() as session:
        q = select(Transaccion).where(
            and_(
                Transaccion.telefono == telefono,
                Transaccion.fecha >= inicio,
                Transaccion.fecha < fin,
            )
        ).order_by(Transaccion.fecha.asc())
        txs = (await session.execute(q)).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["fecha_utc", "tipo", "monto", "categoria", "descripcion"])
    for t in txs:
        writer.writerow([
            t.fecha.isoformat() if t.fecha else "",
            t.tipo,
            f"{t.monto:.2f}",
            t.categoria or "",
            (t.descripcion or "").replace("\n", " "),
        ])
    # BOM para que Excel detecte UTF-8
    return "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")


def detectar_comando_reporte(texto: str) -> dict | None:
    """
    Detecta si el texto es un comando de reporte financiero. Devuelve un dict con
    {"tipo": "resumen"|"exportar", "año": int|None, "mes": int|None,
     "destino": "whatsapp"|"email"} o None.

    `destino` vale "email" cuando el usuario pide el export por correo
    (ej: "dona exporta por correo octubre"). Default "whatsapp".

    Matchea (intencionalmente específico para no colisionar con "dona resumen"
    del morning brief):
      - "dona resumen del mes" / "dona resumen financiero" / "dona resumen de ventas"
      - "dona resumen octubre" / "dona resumen de octubre"
      - "dona reporte" / "dona reporte del mes"
      - "dona exporta" / "dona exporta csv" / "dona exporta ventas"
      - "dona exporta por correo" / "dona exporta por email" / "dona exporta por gmail"
    """
    if not texto:
        return None
    t = texto.strip().lower()
    if not t.startswith("dona "):
        return None
    # Normalizar acentos
    t = (t.replace("á", "a").replace("é", "e").replace("í", "i")
           .replace("ó", "o").replace("ú", "u"))

    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
        "noviembre": 11, "diciembre": 12,
    }
    mes_detectado = None
    for nombre, n in meses.items():
        if nombre in t:
            mes_detectado = n
            break

    # Destino: email si el usuario lo pide explícitamente.
    destino = "whatsapp"
    if any(kw in t for kw in (
        "por correo", "al correo", "a mi correo", "por email", "al email",
        "a mi email", "por gmail", "al gmail", "manda el correo", "mandame el correo",
    )):
        destino = "email"

    # Exportar CSV
    if "exporta" in t or "exportar" in t or " csv" in t:
        return {"tipo": "exportar", "año": None, "mes": mes_detectado, "destino": destino}

    # Reporte financiero (alternativa no ambigua)
    if "reporte" in t:
        return {"tipo": "resumen", "año": None, "mes": mes_detectado, "destino": destino}

    # "resumen" solo cuando va con calificador financiero
    # (para no pisar "dona resumen" del morning brief)
    if "resumen" in t and (
        "del mes" in t or "mensual" in t or "financier" in t
        or "ventas" in t or "gastos" in t or "utilidad" in t
        or mes_detectado is not None
    ):
        return {"tipo": "resumen", "año": None, "mes": mes_detectado, "destino": destino}

    return None
