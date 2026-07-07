# agent/reporting.py — Reportes y exportes para comandos "dona resumen" / "dona exporta"

"""
Genera resúmenes y exportes de los datos del usuario sin salir de WhatsApp.

Funciones principales:
  - resumen_mes(telefono, año, mes) → texto con totales del mes (ventas, gastos, pedidos)
  - resumen_semana(telefono, desde) → texto con totales de la semana
  - resumen_mes_datos(telefono, año, mes) → dict con los mismos números (para la web)
  - resumen_semana_datos(telefono, desde) → dict con los mismos números (para la web)
  - exportar_transacciones_csv(telefono, año, mes=None) → bytes CSV
  - exportar_pedidos_csv(telefono, año, mes=None) → bytes CSV

Los `*_datos` reusan la MISMA agregación que los strings de WhatsApp (helpers
`_agregar_mes` / `_agregar_semana`), para que la web y el chat nunca diverjan.

Todas las funciones filtran estrictamente por `telefono` (tenant isolation) —
nunca mezclan datos entre usuarios.
"""

import csv
import io
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select

from agent.business.models import Pedido, Transaccion
from agent.memory import async_session

logger = logging.getLogger("dona")

_MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre",
    12: "diciembre",
}


def _rango_mes_utc(año: int, mes: int) -> tuple[datetime, datetime]:
    """Devuelve (inicio, fin_exclusivo) del mes en UTC."""
    inicio = datetime(año, mes, 1, tzinfo=UTC).replace(tzinfo=None)
    if mes == 12:
        fin = datetime(año + 1, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    else:
        fin = datetime(año, mes + 1, 1, tzinfo=UTC).replace(tzinfo=None)
    return inicio, fin


def _top_categorias_gasto(txs, limite: int = 3) -> list[tuple[str, float]]:
    """Top N categorías por monto de gasto (más alto primero)."""
    cats_gasto: Counter[str] = Counter()
    for t in txs:
        if t.tipo == "gasto":
            cats_gasto[t.categoria or "general"] += t.monto
    return cats_gasto.most_common(limite)


async def _agregar_mes(telefono: str, año: int, mes: int) -> dict:
    """Núcleo de agregación mensual · comparte lógica entre el string de
    WhatsApp (`resumen_mes`) y el JSON de la web (`resumen_mes_datos`).

    Devuelve un dict con los campos crudos ya calculados. NO formatea: quien
    llama decide si arma un string con emojis o lo serializa a JSON.
    """
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

    return {
        "año": año,
        "mes": mes,
        "inicio": inicio,
        "fin": fin,
        "ventas": ventas,
        "gastos": gastos,
        "utilidad": ventas - gastos,
        "num_pedidos": pedidos_count,
        "num_transacciones": len(txs),
        "top_categorias": _top_categorias_gasto(txs),
    }


async def _agregar_semana(telefono: str, inicio: datetime, fin: datetime) -> dict:
    """Núcleo de agregación semanal · comparte lógica entre `resumen_semana`
    (string WhatsApp) y `resumen_semana_datos` (JSON web).

    Incluye la comparación de ventas contra la semana previa (mismo largo de
    ventana, inmediatamente anterior a `inicio`). `delta_ventas_pct` es None
    cuando no hay ventas previas contra las que comparar.
    """
    async with async_session() as session:
        q_tx = select(Transaccion).where(
            and_(
                Transaccion.telefono == telefono,
                Transaccion.fecha >= inicio,
                Transaccion.fecha <= fin,
            )
        )
        txs = (await session.execute(q_tx)).scalars().all()

        q_ped = select(Pedido).where(
            and_(
                Pedido.telefono == telefono,
                Pedido.creado >= inicio,
                Pedido.creado <= fin,
            )
        )
        pedidos = (await session.execute(q_ped)).scalars().all()

        # Semana previa (misma duración, justo antes de `inicio`).
        inicio_prev = inicio - (fin - inicio)
        q_tx_prev = select(Transaccion).where(
            and_(
                Transaccion.telefono == telefono,
                Transaccion.fecha >= inicio_prev,
                Transaccion.fecha < inicio,
            )
        )
        txs_prev = (await session.execute(q_tx_prev)).scalars().all()

    ventas = sum(t.monto for t in txs if t.tipo == "venta")
    gastos = sum(t.monto for t in txs if t.tipo == "gasto")

    pedidos_entregados = sum(1 for p in pedidos if p.estado == "entregado")
    pedidos_pendientes = sum(
        1 for p in pedidos if p.estado in ("pendiente", "en_preparacion", "listo")
    )

    delta_ventas_pct: float | None = None
    if txs_prev:
        ventas_prev = sum(t.monto for t in txs_prev if t.tipo == "venta")
        if ventas_prev > 0:
            delta_ventas_pct = ((ventas - ventas_prev) / ventas_prev) * 100

    return {
        "inicio": inicio,
        "fin": fin,
        "ventas": ventas,
        "gastos": gastos,
        "utilidad": ventas - gastos,
        "num_pedidos": len(pedidos),
        "num_transacciones": len(txs),
        "pedidos_entregados": pedidos_entregados,
        "pedidos_pendientes": pedidos_pendientes,
        "top_categorias": _top_categorias_gasto(txs),
        "delta_ventas_pct": delta_ventas_pct,
    }


async def resumen_mes(telefono: str, año: int | None = None, mes: int | None = None) -> str:
    """
    Genera un resumen en texto del mes indicado (default: mes actual UTC).

    Incluye: total de ventas, total de gastos, utilidad bruta, conteo de pedidos
    y top 3 categorías de gasto.
    """
    ahora = datetime.utcnow()
    año = año or ahora.year
    mes = mes or ahora.month

    d = await _agregar_mes(telefono, año, mes)

    lineas = [
        f"📊 Resumen de {_MESES_ES[mes]} {año}",
        "",
        f"💰 Ventas:   ${d['ventas']:,.2f}",
        f"💸 Gastos:   ${d['gastos']:,.2f}",
        f"📈 Utilidad: ${d['utilidad']:,.2f}",
        f"📦 Pedidos:  {d['num_pedidos']}",
        f"🧾 Transacciones registradas: {d['num_transacciones']}",
    ]
    if d["top_categorias"]:
        lineas.append("")
        lineas.append("Top gastos por categoría:")
        for cat, monto in d["top_categorias"]:
            lineas.append(f"  • {cat}: ${monto:,.2f}")

    if d["num_transacciones"] == 0 and d["num_pedidos"] == 0:
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

    d = await _agregar_semana(telefono, inicio, ahora)

    # Si no hay movimientos en la semana, el caller puede saltarse el aviso
    if d["num_transacciones"] == 0 and d["num_pedidos"] == 0:
        return ""

    lineas = [
        f"📅 Resumen de tu semana ({inicio.strftime('%d/%m')} → {ahora.strftime('%d/%m')})",
        "",
        f"💰 Ventas:   ${d['ventas']:,.2f}",
        f"💸 Gastos:   ${d['gastos']:,.2f}",
        f"📈 Utilidad: ${d['utilidad']:,.2f}",
    ]
    if d["num_pedidos"]:
        lineas.append(
            f"📦 Pedidos:  {d['num_pedidos']} "
            f"({d['pedidos_entregados']} entregados, {d['pedidos_pendientes']} en curso)"
        )
    if d["num_transacciones"]:
        lineas.append(f"🧾 Transacciones: {d['num_transacciones']}")

    if d["delta_ventas_pct"] is not None:
        flecha = "↗️" if d["delta_ventas_pct"] >= 0 else "↘️"
        lineas.append("")
        lineas.append(f"{flecha} vs. semana pasada: {d['delta_ventas_pct']:+.1f}% en ventas")

    return "\n".join(lineas)


# ── Datos estructurados (JSON) para la web ─────────────────────────────────
#
# Fase 1 (plataforma web): el dashboard muestra los mismos números que el
# usuario obtiene por WhatsApp, pero como dict/JSON en vez de string con
# emojis. La agregación es EXACTAMENTE la misma (helpers `_agregar_*`); aquí
# sólo cambiamos el empaquetado a un contrato estable para el frontend.


def _categorias_a_lista(top_cats: list[tuple[str, float]]) -> list[dict]:
    """Convierte [(cat, monto), ...] → [{"categoria": cat, "total": monto}]."""
    return [{"categoria": cat, "total": round(monto, 2)} for cat, monto in top_cats]


async def resumen_mes_datos(
    telefono: str, año: int | None = None, mes: int | None = None
) -> dict:
    """
    Datos estructurados del resumen mensual (para el dashboard web).

    Devuelve el mismo cálculo que `resumen_mes` pero como dict serializable a
    JSON (montos redondeados a 2 decimales). `hay_datos` es False cuando no
    hubo transacciones ni pedidos en el período → el frontend muestra su
    empty state.

    Forma:
        {
          "periodo": "mes",
          "etiqueta": "octubre 2026",
          "año": 2026, "mes": 10,
          "inicio": "2026-10-01T00:00:00", "fin": "2026-11-01T00:00:00",
          "ventas": 0.0, "gastos": 0.0, "utilidad": 0.0,
          "num_pedidos": 0, "num_transacciones": 0,
          "top_categorias": [{"categoria": "insumos", "total": 120.0}, ...],
          "hay_datos": false
        }
    """
    ahora = datetime.utcnow()
    año = año or ahora.year
    mes = mes or ahora.month

    d = await _agregar_mes(telefono, año, mes)
    return {
        "periodo": "mes",
        "etiqueta": f"{_MESES_ES[mes]} {año}",
        "año": año,
        "mes": mes,
        "inicio": d["inicio"].isoformat(),
        "fin": d["fin"].isoformat(),
        "ventas": round(d["ventas"], 2),
        "gastos": round(d["gastos"], 2),
        "utilidad": round(d["utilidad"], 2),
        "num_pedidos": d["num_pedidos"],
        "num_transacciones": d["num_transacciones"],
        "top_categorias": _categorias_a_lista(d["top_categorias"]),
        "hay_datos": bool(d["num_transacciones"] or d["num_pedidos"]),
    }


async def resumen_semana_datos(telefono: str, desde: datetime | None = None) -> dict:
    """
    Datos estructurados del resumen semanal (para el dashboard web).

    Mismo cálculo que `resumen_semana` (incluida la comparación vs. semana
    previa), pero como dict serializable a JSON. A diferencia del string de
    WhatsApp, NO se abstiene si no hay datos: siempre devuelve el dict con
    `hay_datos=False` para que el frontend decida el empty state.

    Forma:
        {
          "periodo": "semana",
          "etiqueta": "30/06 → 07/07",
          "inicio": "...", "fin": "...",
          "ventas": 0.0, "gastos": 0.0, "utilidad": 0.0,
          "num_pedidos": 0, "num_transacciones": 0,
          "pedidos_entregados": 0, "pedidos_pendientes": 0,
          "top_categorias": [...],
          "comparacion_semana_previa": {"delta_ventas_pct": 12.5} | null,
          "hay_datos": false
        }
    """
    ahora = datetime.utcnow()
    inicio = desde or (ahora - timedelta(days=7))

    d = await _agregar_semana(telefono, inicio, ahora)

    comparacion = None
    if d["delta_ventas_pct"] is not None:
        comparacion = {"delta_ventas_pct": round(d["delta_ventas_pct"], 1)}

    return {
        "periodo": "semana",
        "etiqueta": f"{inicio.strftime('%d/%m')} → {ahora.strftime('%d/%m')}",
        "inicio": d["inicio"].isoformat(),
        "fin": d["fin"].isoformat(),
        "ventas": round(d["ventas"], 2),
        "gastos": round(d["gastos"], 2),
        "utilidad": round(d["utilidad"], 2),
        "num_pedidos": d["num_pedidos"],
        "num_transacciones": d["num_transacciones"],
        "pedidos_entregados": d["pedidos_entregados"],
        "pedidos_pendientes": d["pedidos_pendientes"],
        "top_categorias": _categorias_a_lista(d["top_categorias"]),
        "comparacion_semana_previa": comparacion,
        "hay_datos": bool(d["num_transacciones"] or d["num_pedidos"]),
    }


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
