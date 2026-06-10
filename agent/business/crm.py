# agent/business/crm.py — CRM ligero para Dona

"""
Gestión de clientes: registro, búsqueda, interacciones, seguimientos.
Todas las funciones reciben telefono (del dueño del negocio) para aislar datos.
"""

import logging
from datetime import datetime
from sqlalchemy import select, or_, update

from agent.memory import async_session
from agent.business.models import ClienteNegocio, Seguimiento

logger = logging.getLogger("dona")


async def registrar_cliente(
    telefono: str, nombre: str, telefono_cliente: str = "",
    email: str = "", notas: str = ""
) -> dict:
    """Registra un nuevo cliente. Retorna dict con datos del cliente."""
    async with async_session() as session:
        cliente = ClienteNegocio(
            telefono_owner=telefono,
            nombre=nombre,
            telefono_cliente=telefono_cliente,
            email=email,
            notas=notas,
            creado=datetime.utcnow(),
        )
        session.add(cliente)
        await session.commit()
        await session.refresh(cliente)
        logger.info(f"[CRM] Cliente '{nombre}' registrado para {telefono} (id={cliente.id})")
        return {
            "id": cliente.id, "nombre": nombre,
            "telefono_cliente": telefono_cliente, "email": email,
        }


async def buscar_clientes(telefono: str, query: str = "", limite: int = 10) -> list[dict]:
    """Busca clientes por nombre, teléfono o email."""
    async with async_session() as session:
        stmt = select(ClienteNegocio).where(ClienteNegocio.telefono_owner == telefono)
        if query:
            q = f"%{query}%"
            stmt = stmt.where(or_(
                ClienteNegocio.nombre.ilike(q),
                ClienteNegocio.telefono_cliente.ilike(q),
                ClienteNegocio.email.ilike(q),
            ))
        stmt = stmt.order_by(ClienteNegocio.creado.desc()).limit(limite)
        result = await session.execute(stmt)
        clientes = result.scalars().all()
        return [
            {
                "id": c.id, "nombre": c.nombre,
                "telefono": c.telefono_cliente, "email": c.email,
                "total_compras": c.total_compras, "num_compras": c.num_compras,
                "notas": c.notas,
            }
            for c in clientes
        ]


async def obtener_cliente(telefono: str, cliente_id: int) -> dict | None:
    """Obtiene un cliente por ID."""
    async with async_session() as session:
        result = await session.execute(
            select(ClienteNegocio).where(
                ClienteNegocio.id == cliente_id,
                ClienteNegocio.telefono_owner == telefono,
            )
        )
        c = result.scalar_one_or_none()
        if not c:
            return None
        return {
            "id": c.id, "nombre": c.nombre,
            "telefono": c.telefono_cliente, "email": c.email,
            "total_compras": c.total_compras, "num_compras": c.num_compras,
            "ultima_compra": c.ultima_compra.isoformat() if c.ultima_compra else None,
            "notas": c.notas,
        }


async def buscar_cliente_por_nombre(telefono: str, nombre: str) -> dict | None:
    """Busca un cliente por nombre exacto (case-insensitive). Retorna el primero."""
    async with async_session() as session:
        result = await session.execute(
            select(ClienteNegocio).where(
                ClienteNegocio.telefono_owner == telefono,
                ClienteNegocio.nombre.ilike(nombre),
            ).limit(1)
        )
        c = result.scalar_one_or_none()
        if not c:
            return None
        return {"id": c.id, "nombre": c.nombre, "telefono": c.telefono_cliente}


async def actualizar_compras_cliente(telefono: str, cliente_id: int, monto: float):
    """Incrementa total_compras y num_compras del cliente."""
    async with async_session() as session:
        result = await session.execute(
            select(ClienteNegocio).where(
                ClienteNegocio.id == cliente_id,
                ClienteNegocio.telefono_owner == telefono,
            )
        )
        c = result.scalar_one_or_none()
        if c:
            c.total_compras += monto
            c.num_compras += 1
            c.ultima_compra = datetime.utcnow()
            await session.commit()


async def crear_seguimiento(
    telefono: str, descripcion: str, fecha_programada: datetime,
    cliente_id: int | None = None, cliente_nombre: str = ""
) -> dict:
    """Crea un follow-up programado."""
    async with async_session() as session:
        seg = Seguimiento(
            telefono=telefono,
            cliente_id=cliente_id,
            cliente_nombre=cliente_nombre,
            descripcion=descripcion,
            fecha_programada=fecha_programada,
            creado=datetime.utcnow(),
        )
        session.add(seg)
        await session.commit()
        await session.refresh(seg)
        logger.info(f"[CRM] Seguimiento creado para {telefono}: '{descripcion}' ({fecha_programada})")
        return {
            "id": seg.id, "descripcion": descripcion,
            "fecha": fecha_programada.isoformat(),
            "cliente": cliente_nombre,
        }


async def obtener_seguimientos_pendientes(telefono: str, limite: int = 10) -> list[dict]:
    """Lista seguimientos pendientes (no completados) ordenados por fecha."""
    async with async_session() as session:
        result = await session.execute(
            select(Seguimiento).where(
                Seguimiento.telefono == telefono,
                Seguimiento.completado == False,
            ).order_by(Seguimiento.fecha_programada.asc()).limit(limite)
        )
        segs = result.scalars().all()
        return [
            {
                "id": s.id, "descripcion": s.descripcion,
                "cliente": s.cliente_nombre,
                "fecha": s.fecha_programada.isoformat(),
            }
            for s in segs
        ]


async def completar_seguimiento(telefono: str, seguimiento_id: int) -> bool:
    """Marca un seguimiento como completado."""
    async with async_session() as session:
        result = await session.execute(
            select(Seguimiento).where(
                Seguimiento.id == seguimiento_id,
                Seguimiento.telefono == telefono,
            )
        )
        s = result.scalar_one_or_none()
        if s:
            s.completado = True
            await session.commit()
            return True
        return False


async def claim_seguimiento_para_envio(seguimiento_id: int) -> bool:
    """Reclama atómicamente un seguimiento vencido ANTES de enviarlo
    (Fase 0 · 2.3): UPDATE completado false→true, el rowcount decide UN
    ganador entre procesos concurrentes del scheduler. True = enviar."""
    async with async_session() as session:
        result = await session.execute(
            update(Seguimiento)
            .where(
                Seguimiento.id == seguimiento_id,
                Seguimiento.completado == False,
            )
            .values(completado=True)
        )
        await session.commit()
        return result.rowcount == 1


async def revertir_claim_seguimiento(seguimiento_id: int) -> None:
    """Revierte el claim tras un envío FALLIDO para que el próximo ciclo lo
    reintente. Solo la llama el proceso dueño del claim."""
    async with async_session() as session:
        await session.execute(
            update(Seguimiento)
            .where(Seguimiento.id == seguimiento_id)
            .values(completado=False)
        )
        await session.commit()
