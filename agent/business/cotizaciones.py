# agent/business/cotizaciones.py — Cotizaciones y presupuestos

"""
Crear y gestionar cotizaciones para clientes.
Items almacenados como JSON para flexibilidad.
"""

import json
import logging
from datetime import datetime

from sqlalchemy import select

from agent.business.models import Cotizacion
from agent.memory import async_session

logger = logging.getLogger("dona")


async def crear_cotizacion(
    telefono: str, items: list[dict], notas: str = "",
    cliente_id: int | None = None, cliente_nombre: str = "",
    vigencia_dias: int = 15,
) -> dict:
    """
    Crea una cotización.
    items: [{"concepto": str, "cantidad": int, "precio_unitario": float}]
    """
    # Calcular subtotales y total
    for item in items:
        item["subtotal"] = round(item.get("cantidad", 1) * item.get("precio_unitario", 0), 2)
    total = round(sum(i["subtotal"] for i in items), 2)

    async with async_session() as session:
        cot = Cotizacion(
            telefono=telefono,
            cliente_id=cliente_id,
            cliente_nombre=cliente_nombre,
            items_json=json.dumps(items, ensure_ascii=False),
            total=total,
            notas=notas,
            vigencia_dias=vigencia_dias,
            creado=datetime.utcnow(),
        )
        session.add(cot)
        await session.commit()
        await session.refresh(cot)
        logger.info(f"[COTIZACION] #{cot.id} creada: ${total} para {cliente_nombre or 'sin cliente'}")
        return {
            "id": cot.id, "items": items, "total": total,
            "cliente": cliente_nombre, "estado": "borrador",
            "vigencia_dias": vigencia_dias,
        }


async def obtener_cotizacion(telefono: str, cotizacion_id: int) -> dict | None:
    """Obtiene una cotización por ID."""
    async with async_session() as session:
        result = await session.execute(
            select(Cotizacion).where(
                Cotizacion.id == cotizacion_id, Cotizacion.telefono == telefono
            )
        )
        c = result.scalar_one_or_none()
        if not c:
            return None
        return {
            "id": c.id, "items": json.loads(c.items_json),
            "total": c.total, "cliente": c.cliente_nombre,
            "estado": c.estado, "notas": c.notas,
            "vigencia_dias": c.vigencia_dias,
            "creada": c.creado.isoformat(),
        }


async def listar_cotizaciones(telefono: str, estado: str = "", limite: int = 10) -> list[dict]:
    """Lista cotizaciones, opcionalmente filtradas por estado."""
    async with async_session() as session:
        stmt = select(Cotizacion).where(Cotizacion.telefono == telefono)
        if estado:
            stmt = stmt.where(Cotizacion.estado == estado)
        stmt = stmt.order_by(Cotizacion.creado.desc()).limit(limite)
        result = await session.execute(stmt)
        return [
            {
                "id": c.id, "total": c.total, "cliente": c.cliente_nombre,
                "estado": c.estado, "creada": c.creado.isoformat(),
            }
            for c in result.scalars().all()
        ]


async def actualizar_estado_cotizacion(telefono: str, cotizacion_id: int, estado: str) -> bool:
    """Actualiza el estado de una cotización."""
    estados_validos = {"borrador", "enviada", "aceptada", "rechazada"}
    if estado not in estados_validos:
        return False
    async with async_session() as session:
        result = await session.execute(
            select(Cotizacion).where(
                Cotizacion.id == cotizacion_id, Cotizacion.telefono == telefono
            )
        )
        c = result.scalar_one_or_none()
        if not c:
            return False
        c.estado = estado
        await session.commit()
        return True


def formatear_cotizacion_texto(cotizacion: dict, nombre_negocio: str = "") -> str:
    """Formatea una cotización como texto para enviar por WhatsApp."""
    lineas = []
    if nombre_negocio:
        lineas.append(f"*{nombre_negocio}*")
        lineas.append("")
    lineas.append(f"*Cotización #{cotizacion['id']}*")
    if cotizacion.get("cliente"):
        lineas.append(f"Cliente: {cotizacion['cliente']}")
    lineas.append("")

    for item in cotizacion.get("items", []):
        cant = item.get("cantidad", 1)
        concepto = item.get("concepto", "")
        precio = item.get("precio_unitario", 0)
        subtotal = item.get("subtotal", 0)
        lineas.append(f"• {concepto} x{cant} — ${precio:,.2f} c/u = ${subtotal:,.2f}")

    lineas.append("")
    lineas.append(f"*Total: ${cotizacion['total']:,.2f}*")

    if cotizacion.get("notas"):
        lineas.append(f"\nNotas: {cotizacion['notas']}")

    lineas.append(f"\nVigencia: {cotizacion.get('vigencia_dias', 15)} días")
    return "\n".join(lineas)
