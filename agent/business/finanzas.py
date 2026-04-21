# agent/business/finanzas.py — Registro financiero conversacional

"""
Tracking de ventas, gastos, productos y métricas financieras.
Todo por conversación de WhatsApp.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func

from agent.memory import async_session
from agent.business.models import Transaccion, Producto, PerfilNegocio
from agent.business.crm import actualizar_compras_cliente

logger = logging.getLogger("dona")


# ── Perfil de negocio ────────────────────────────────────────────────────────

async def obtener_perfil_negocio(telefono: str) -> dict | None:
    """Retorna el perfil de negocio del usuario, o None si no tiene."""
    async with async_session() as session:
        result = await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )
        p = result.scalar_one_or_none()
        if not p:
            return None
        return {
            "nombre": p.nombre_negocio, "industria": p.industria,
            "descripcion": p.descripcion, "moneda": p.moneda,
            "meta_mensual": p.meta_mensual,
        }


async def guardar_perfil_negocio(
    telefono: str, nombre: str = "", industria: str = "general",
    descripcion: str = "", moneda: str = "MXN", meta_mensual: float = 0.0
) -> dict:
    """Crea o actualiza el perfil de negocio."""
    async with async_session() as session:
        result = await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )
        p = result.scalar_one_or_none()
        if p:
            if nombre: p.nombre_negocio = nombre
            if industria != "general": p.industria = industria
            if descripcion: p.descripcion = descripcion
            if moneda != "MXN": p.moneda = moneda
            if meta_mensual > 0: p.meta_mensual = meta_mensual
            p.actualizado = datetime.utcnow()
        else:
            p = PerfilNegocio(
                telefono=telefono, nombre_negocio=nombre,
                industria=industria, descripcion=descripcion,
                moneda=moneda, meta_mensual=meta_mensual,
                creado=datetime.utcnow(), actualizado=datetime.utcnow(),
            )
            session.add(p)
        await session.commit()
        logger.info(f"[NEGOCIO] Perfil guardado para {telefono}: {nombre} ({industria})")
        return {"nombre": nombre, "industria": industria, "moneda": moneda}


# ── Productos ────────────────────────────────────────────────────────────────

async def registrar_producto(
    telefono: str, nombre: str, precio: float,
    costo: float = 0.0, categoria: str = "general"
) -> dict:
    """Registra un producto/servicio en el catálogo."""
    async with async_session() as session:
        prod = Producto(
            telefono=telefono, nombre=nombre, precio=precio,
            costo=costo, categoria=categoria, creado=datetime.utcnow(),
        )
        session.add(prod)
        await session.commit()
        await session.refresh(prod)
        margen = round((precio - costo) / precio * 100, 1) if precio > 0 and costo > 0 else None
        logger.info(f"[NEGOCIO] Producto '{nombre}' registrado: ${precio}")
        return {
            "id": prod.id, "nombre": nombre, "precio": precio,
            "costo": costo, "margen_pct": margen,
        }


async def listar_productos(telefono: str) -> list[dict]:
    """Lista productos activos del negocio."""
    async with async_session() as session:
        result = await session.execute(
            select(Producto).where(
                Producto.telefono == telefono, Producto.activo == True,
            ).order_by(Producto.nombre)
        )
        return [
            {
                "id": p.id, "nombre": p.nombre, "precio": p.precio,
                "costo": p.costo, "categoria": p.categoria,
            }
            for p in result.scalars().all()
        ]


async def buscar_producto_por_nombre(telefono: str, nombre: str) -> dict | None:
    """Busca un producto por nombre (case-insensitive)."""
    async with async_session() as session:
        result = await session.execute(
            select(Producto).where(
                Producto.telefono == telefono,
                Producto.nombre.ilike(f"%{nombre}%"),
                Producto.activo == True,
            ).limit(1)
        )
        p = result.scalar_one_or_none()
        if not p:
            return None
        return {"id": p.id, "nombre": p.nombre, "precio": p.precio, "costo": p.costo}


# ── Transacciones ────────────────────────────────────────────────────────────

async def registrar_venta(
    telefono: str, monto: float, descripcion: str = "",
    categoria: str = "venta", cliente_id: int | None = None,
    producto_id: int | None = None,
) -> dict:
    """Registra una venta."""
    async with async_session() as session:
        tx = Transaccion(
            telefono=telefono, tipo="venta", monto=monto,
            descripcion=descripcion, categoria=categoria,
            cliente_id=cliente_id, producto_id=producto_id,
            fecha=datetime.utcnow(),
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)

    # Actualizar stats del cliente si está asociado
    if cliente_id:
        try:
            await actualizar_compras_cliente(telefono, cliente_id, monto)
        except Exception:
            pass

    logger.info(f"[FINANZAS] Venta registrada: ${monto} ({descripcion})")
    return {"id": tx.id, "tipo": "venta", "monto": monto, "descripcion": descripcion}


async def registrar_gasto(
    telefono: str, monto: float, descripcion: str = "",
    categoria: str = "general",
) -> dict:
    """Registra un gasto."""
    async with async_session() as session:
        tx = Transaccion(
            telefono=telefono, tipo="gasto", monto=monto,
            descripcion=descripcion, categoria=categoria,
            fecha=datetime.utcnow(),
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
    logger.info(f"[FINANZAS] Gasto registrado: ${monto} ({descripcion})")
    return {"id": tx.id, "tipo": "gasto", "monto": monto, "descripcion": descripcion}


async def resumen_financiero(telefono: str, periodo: str = "mes") -> dict:
    """
    Resumen financiero del negocio.
    periodo: "hoy", "semana", "mes", "año"
    """
    ahora = datetime.utcnow()
    if periodo == "hoy":
        desde = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        desde = ahora - timedelta(days=ahora.weekday())
        desde = desde.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "año":
        desde = ahora.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # mes
        desde = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async with async_session() as session:
        # Ventas
        r_ventas = await session.execute(
            select(
                func.coalesce(func.sum(Transaccion.monto), 0),
                func.count(Transaccion.id),
            ).where(
                Transaccion.telefono == telefono,
                Transaccion.tipo == "venta",
                Transaccion.fecha >= desde,
            )
        )
        total_ventas, num_ventas = r_ventas.one()

        # Gastos
        r_gastos = await session.execute(
            select(
                func.coalesce(func.sum(Transaccion.monto), 0),
                func.count(Transaccion.id),
            ).where(
                Transaccion.telefono == telefono,
                Transaccion.tipo == "gasto",
                Transaccion.fecha >= desde,
            )
        )
        total_gastos, num_gastos = r_gastos.one()

        utilidad = float(total_ventas) - float(total_gastos)
        margen = round(utilidad / float(total_ventas) * 100, 1) if float(total_ventas) > 0 else 0.0

        # Meta mensual
        perfil = await session.execute(
            select(PerfilNegocio.meta_mensual).where(PerfilNegocio.telefono == telefono)
        )
        meta = perfil.scalar_one_or_none() or 0.0
        progreso_meta = round(float(total_ventas) / meta * 100, 1) if meta > 0 else None

    return {
        "periodo": periodo,
        "ventas": {"total": float(total_ventas), "count": num_ventas},
        "gastos": {"total": float(total_gastos), "count": num_gastos},
        "utilidad": utilidad,
        "margen_pct": margen,
        "meta_mensual": meta,
        "progreso_meta_pct": progreso_meta,
    }


async def top_productos_vendidos(telefono: str, dias: int = 30, limite: int = 5) -> list[dict]:
    """Top productos más vendidos por monto."""
    desde = datetime.utcnow() - timedelta(days=dias)
    async with async_session() as session:
        result = await session.execute(
            select(
                Transaccion.descripcion,
                func.sum(Transaccion.monto).label("total"),
                func.count(Transaccion.id).label("cantidad"),
            ).where(
                Transaccion.telefono == telefono,
                Transaccion.tipo == "venta",
                Transaccion.fecha >= desde,
            ).group_by(Transaccion.descripcion)
            .order_by(func.sum(Transaccion.monto).desc())
            .limit(limite)
        )
        return [
            {"producto": r[0] or "Sin descripción", "total": float(r[1]), "cantidad": r[2]}
            for r in result.all()
        ]
