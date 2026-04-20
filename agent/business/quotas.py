# agent/business/quotas.py — Sistema de quotas por usuario

"""
Límites por usuario para el plan gratuito.
Cada función de creación verifica la quota antes de insertar.
Si se excede, retorna un mensaje amigable en vez de un error.
"""

import logging
from sqlalchemy import select, func

from agent.memory import async_session
from agent.business.models import (
    ClienteNegocio, Producto, Transaccion, Pedido, Cotizacion, Seguimiento,
)

logger = logging.getLogger("agentkit")

# ── Límites del plan gratuito ───────────────────────────────────────────────
# Se pueden sobrescribir con variables de entorno en el futuro.

LIMITES = {
    "clientes": 50,
    "productos": 30,
    "transacciones_mes": 200,
    "pedidos_activos": 30,
    "cotizaciones_mes": 20,
    "seguimientos_activos": 20,
    "contenido_dia": 10,
}

# Contadores en memoria para contenido (no amerita DB)
_contenido_contadores: dict[str, dict] = {}


async def verificar_quota(telefono: str, recurso: str) -> tuple[bool, str]:
    """
    Verifica si el usuario puede crear un recurso más.

    Returns:
        (True, "") si hay espacio
        (False, mensaje) si excede la quota
    """
    limite = LIMITES.get(recurso)
    if limite is None:
        return True, ""

    conteo = await _contar_recurso(telefono, recurso)

    if conteo >= limite:
        msg = _mensaje_limite(recurso, limite)
        logger.info(f"[QUOTAS] {telefono} alcanzó límite de {recurso}: {conteo}/{limite}")
        return False, msg

    return True, ""


async def obtener_uso(telefono: str) -> dict:
    """Retorna el uso actual vs límites para todos los recursos."""
    uso = {}
    for recurso, limite in LIMITES.items():
        conteo = await _contar_recurso(telefono, recurso)
        uso[recurso] = {"usado": conteo, "limite": limite}
    return uso


async def _contar_recurso(telefono: str, recurso: str) -> int:
    """Cuenta cuántos recursos tiene el usuario."""
    from datetime import datetime, timedelta

    async with async_session() as session:
        if recurso == "clientes":
            r = await session.execute(
                select(func.count(ClienteNegocio.id)).where(
                    ClienteNegocio.telefono_owner == telefono
                )
            )
            return r.scalar_one()

        elif recurso == "productos":
            r = await session.execute(
                select(func.count(Producto.id)).where(
                    Producto.telefono == telefono,
                    Producto.activo == True,
                )
            )
            return r.scalar_one()

        elif recurso == "transacciones_mes":
            inicio_mes = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            r = await session.execute(
                select(func.count(Transaccion.id)).where(
                    Transaccion.telefono == telefono,
                    Transaccion.fecha >= inicio_mes,
                )
            )
            return r.scalar_one()

        elif recurso == "pedidos_activos":
            r = await session.execute(
                select(func.count(Pedido.id)).where(
                    Pedido.telefono == telefono,
                    Pedido.estado.notin_(["entregado", "cancelado"]),
                )
            )
            return r.scalar_one()

        elif recurso == "cotizaciones_mes":
            inicio_mes = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            r = await session.execute(
                select(func.count(Cotizacion.id)).where(
                    Cotizacion.telefono == telefono,
                    Cotizacion.creado >= inicio_mes,
                )
            )
            return r.scalar_one()

        elif recurso == "seguimientos_activos":
            r = await session.execute(
                select(func.count(Seguimiento.id)).where(
                    Seguimiento.telefono == telefono,
                    Seguimiento.completado == False,
                )
            )
            return r.scalar_one()

        elif recurso == "contenido_dia":
            return _contar_contenido_hoy(telefono)

    return 0


def _contar_contenido_hoy(telefono: str) -> int:
    """Cuenta generaciones de contenido hoy (in-memory)."""
    from datetime import date
    hoy = date.today().isoformat()
    datos = _contenido_contadores.get(telefono, {})
    if datos.get("fecha") != hoy:
        return 0
    return datos.get("conteo", 0)


def registrar_uso_contenido(telefono: str):
    """Registra una generación de contenido."""
    from datetime import date
    hoy = date.today().isoformat()
    datos = _contenido_contadores.get(telefono, {})
    if datos.get("fecha") != hoy:
        _contenido_contadores[telefono] = {"fecha": hoy, "conteo": 1}
    else:
        datos["conteo"] = datos.get("conteo", 0) + 1
        _contenido_contadores[telefono] = datos


def _mensaje_limite(recurso: str, limite: int) -> str:
    """Mensaje amigable cuando se alcanza un límite."""
    mensajes = {
        "clientes": f"Has alcanzado el límite de {limite} clientes registrados.",
        "productos": f"Has alcanzado el límite de {limite} productos activos.",
        "transacciones_mes": f"Has alcanzado el límite de {limite} transacciones este mes.",
        "pedidos_activos": f"Tienes {limite} pedidos activos. Completa o cancela algunos para crear más.",
        "cotizaciones_mes": f"Has alcanzado el límite de {limite} cotizaciones este mes.",
        "seguimientos_activos": f"Tienes {limite} seguimientos activos. Completa algunos para crear más.",
        "contenido_dia": f"Has alcanzado el límite de {limite} contenidos por día.",
    }
    return mensajes.get(recurso, f"Límite de {recurso} alcanzado ({limite}).")
