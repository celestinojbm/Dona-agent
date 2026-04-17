# agent/business/pedidos.py — Gestión de pedidos/órdenes

"""
CRUD de pedidos: crear, actualizar estado, listar pendientes.
Integrado con CRM (asocia pedidos a clientes).
"""

import logging
from datetime import datetime
from sqlalchemy import select

from agent.memory import async_session
from agent.business.models import Pedido

logger = logging.getLogger("agentkit")


async def crear_pedido(
    telefono: str, descripcion: str, monto: float = 0.0,
    cliente_id: int | None = None, cliente_nombre: str = "",
    fecha_entrega: datetime | None = None,
    direccion: str = "", notas: str = "",
) -> dict:
    """Crea un nuevo pedido."""
    async with async_session() as session:
        pedido = Pedido(
            telefono=telefono, descripcion=descripcion, monto=monto,
            cliente_id=cliente_id, cliente_nombre=cliente_nombre,
            fecha_entrega=fecha_entrega, direccion=direccion, notas=notas,
            estado="pendiente",
            creado=datetime.utcnow(), actualizado=datetime.utcnow(),
        )
        session.add(pedido)
        await session.commit()
        await session.refresh(pedido)
        logger.info(f"[PEDIDOS] Pedido #{pedido.id} creado: {descripcion}")
        return {
            "id": pedido.id, "descripcion": descripcion,
            "cliente": cliente_nombre, "monto": monto,
            "estado": "pendiente",
            "fecha_entrega": fecha_entrega.isoformat() if fecha_entrega else None,
        }


async def actualizar_estado_pedido(telefono: str, pedido_id: int, nuevo_estado: str) -> dict | None:
    """Actualiza el estado de un pedido. Retorna el pedido actualizado o None."""
    estados_validos = {"pendiente", "en_preparacion", "listo", "entregado", "cancelado"}
    if nuevo_estado not in estados_validos:
        return None

    async with async_session() as session:
        result = await session.execute(
            select(Pedido).where(Pedido.id == pedido_id, Pedido.telefono == telefono)
        )
        p = result.scalar_one_or_none()
        if not p:
            return None

        estado_anterior = p.estado
        p.estado = nuevo_estado
        p.actualizado = datetime.utcnow()
        await session.commit()
        logger.info(f"[PEDIDOS] Pedido #{pedido_id}: {estado_anterior} → {nuevo_estado}")
        return {
            "id": p.id, "descripcion": p.descripcion,
            "estado_anterior": estado_anterior, "estado_nuevo": nuevo_estado,
            "cliente": p.cliente_nombre,
        }


async def listar_pedidos(telefono: str, estado: str = "", limite: int = 15) -> list[dict]:
    """Lista pedidos. Si estado está vacío, lista todos los no-entregados/cancelados."""
    async with async_session() as session:
        stmt = select(Pedido).where(Pedido.telefono == telefono)
        if estado:
            stmt = stmt.where(Pedido.estado == estado)
        else:
            stmt = stmt.where(Pedido.estado.notin_(["entregado", "cancelado"]))
        stmt = stmt.order_by(Pedido.fecha_entrega.asc().nulls_last(), Pedido.creado.desc()).limit(limite)

        result = await session.execute(stmt)
        pedidos = result.scalars().all()
        return [
            {
                "id": p.id, "descripcion": p.descripcion,
                "cliente": p.cliente_nombre, "monto": p.monto,
                "estado": p.estado,
                "fecha_entrega": p.fecha_entrega.isoformat() if p.fecha_entrega else None,
                "direccion": p.direccion,
            }
            for p in pedidos
        ]


async def obtener_pedido(telefono: str, pedido_id: int) -> dict | None:
    """Obtiene un pedido por ID."""
    async with async_session() as session:
        result = await session.execute(
            select(Pedido).where(Pedido.id == pedido_id, Pedido.telefono == telefono)
        )
        p = result.scalar_one_or_none()
        if not p:
            return None
        return {
            "id": p.id, "descripcion": p.descripcion,
            "cliente": p.cliente_nombre, "monto": p.monto,
            "estado": p.estado,
            "fecha_entrega": p.fecha_entrega.isoformat() if p.fecha_entrega else None,
            "direccion": p.direccion, "notas": p.notas,
        }
