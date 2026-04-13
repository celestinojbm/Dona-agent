# enhanced/execution.py — Habilidad 2: Ejecución con Supervisión Humana

"""
Acciones correctivas que el owner puede ejecutar desde WhatsApp.

Todas requieren confirmación explícita via SafeModule:
  - Nivel "owner": CONFIRMAR
  - Nivel "owner_critical": CONFIRMAR + DONA-ADMIN

Comandos:
  !actions           → lista acciones disponibles
  !exec <nombre>     → solicita confirmación para ejecutar una acción

Acciones disponibles:
  - limpiar_rate_limit    (owner)          — Limpia la caché de rate limiting
  - limpiar_dedup         (owner)          — Limpia la caché de deduplicación de mensajes
  - limpiar_gcal_cache    (owner)          — Limpia la caché de recordatorios de Google Calendar
  - reiniciar_db_pool     (owner)          — Recicla las conexiones del pool de DB
  - reiniciar_scheduler   (owner_critical) — Reinicia el scheduler de recordatorios
"""

import logging

from enhanced.safe_module import SafeModule, NivelPermiso, AccionConfirmable

logger = logging.getLogger("dona.enhanced")


# ── Funciones de ejecución (cada una retorna {exito, mensaje}) ───────────────

async def _limpiar_rate_limit() -> dict:
    """Limpia la caché de rate limiting (Redis o memoria)."""
    from agent.rate_limiter import limpiar_rate_limit
    cantidad = limpiar_rate_limit()
    return {
        "exito": True,
        "mensaje": f"Rate limit limpiado. {cantidad} entradas eliminadas.",
    }


async def _limpiar_dedup() -> dict:
    """Limpia la caché de deduplicación de mensajes (memoria + DB)."""
    from agent.main import _mensajes_procesados_mem
    cantidad_mem = len(_mensajes_procesados_mem)
    _mensajes_procesados_mem.clear()

    cantidad_db = 0
    try:
        from agent.memory import async_session, MensajeProcesado
        from sqlalchemy import delete, func, select
        async with async_session() as session:
            count_result = await session.execute(select(func.count(MensajeProcesado.mensaje_id)))
            cantidad_db = count_result.scalar() or 0
            await session.execute(delete(MensajeProcesado))
            await session.commit()
    except Exception:
        pass

    return {
        "exito": True,
        "mensaje": f"Dedup limpiado. {cantidad_mem} en memoria + {cantidad_db} en DB eliminados.",
    }


async def _limpiar_gcal_cache() -> dict:
    """Limpia la caché de recordatorios de Google Calendar enviados (memoria + DB)."""
    from agent.scheduler import _recordatorios_gcal_enviados_mem
    cantidad_mem = len(_recordatorios_gcal_enviados_mem)
    _recordatorios_gcal_enviados_mem.clear()

    cantidad_db = 0
    try:
        from agent.memory import async_session, RecordatorioGCalEnviado
        from sqlalchemy import delete, func, select
        async with async_session() as session:
            count_result = await session.execute(select(func.count()).select_from(RecordatorioGCalEnviado))
            cantidad_db = count_result.scalar() or 0
            await session.execute(delete(RecordatorioGCalEnviado))
            await session.commit()
    except Exception:
        pass

    return {
        "exito": True,
        "mensaje": f"Caché GCal limpiado. {cantidad_mem} en memoria + {cantidad_db} en DB.",
    }


async def _reiniciar_db_pool() -> dict:
    """Recicla todas las conexiones del pool de base de datos."""
    from agent.memory import engine
    await engine.dispose()
    # Verificar que la nueva conexión funciona
    from sqlalchemy import text
    from agent.memory import async_session
    async with async_session() as session:
        await session.execute(text("SELECT 1"))
    return {
        "exito": True,
        "mensaje": "Pool de DB reciclado y nueva conexión verificada.",
    }


async def _reiniciar_scheduler() -> dict:
    """Reinicia el scheduler de APScheduler (detener + iniciar)."""
    from agent.scheduler import scheduler, detener_scheduler
    from agent.main import proveedor

    if scheduler.running:
        detener_scheduler()

    # Re-registrar y arrancar
    from agent.scheduler import iniciar_scheduler
    iniciar_scheduler(proveedor)

    jobs = scheduler.get_jobs()
    return {
        "exito": True,
        "mensaje": f"Scheduler reiniciado. {len(jobs)} jobs activos.",
    }


# ── Registro de acciones ─────────────────────────────────────────────────────

ACCIONES_DISPONIBLES: list[dict] = [
    {
        "nombre": "limpiar_rate_limit",
        "descripcion": "Limpia la caché de rate limiting (desbloquea números)",
        "nivel": NivelPermiso.OWNER,
        "ejecutar": _limpiar_rate_limit,
    },
    {
        "nombre": "limpiar_dedup",
        "descripcion": "Limpia la caché de deduplicación de mensajes",
        "nivel": NivelPermiso.OWNER,
        "ejecutar": _limpiar_dedup,
    },
    {
        "nombre": "limpiar_gcal_cache",
        "descripcion": "Limpia la caché de recordatorios de Google Calendar enviados",
        "nivel": NivelPermiso.OWNER,
        "ejecutar": _limpiar_gcal_cache,
    },
    {
        "nombre": "reiniciar_db_pool",
        "descripcion": "Recicla las conexiones del pool de base de datos",
        "nivel": NivelPermiso.OWNER,
        "ejecutar": _reiniciar_db_pool,
    },
    {
        "nombre": "reiniciar_scheduler",
        "descripcion": "Reinicia el scheduler de recordatorios y proactividad",
        "nivel": NivelPermiso.OWNER_CRITICAL,
        "ejecutar": _reiniciar_scheduler,
    },
]


class ModuloEjecucion(SafeModule):
    nombre = "ejecucion"

    def listar_acciones(self) -> str:
        """Formatea la lista de acciones disponibles para el owner."""
        lineas = ["*Acciones disponibles:*\n"]
        for a in ACCIONES_DISPONIBLES:
            nivel_tag = "CRITICA" if a["nivel"] == NivelPermiso.OWNER_CRITICAL else "owner"
            lineas.append(f"  *{a['nombre']}* [{nivel_tag}]")
            lineas.append(f"    {a['descripcion']}")
            lineas.append("")

        lineas.append("Ejecuta con: *!exec <nombre>*")
        lineas.append("Ejemplo: !exec limpiar_rate_limit")
        return "\n".join(lineas)

    async def iniciar_ejecucion(self, telefono: str, nombre_accion: str) -> str:
        """
        Busca la acción por nombre e inicia el flujo de confirmación.
        Retorna el mensaje a enviar al usuario.
        """
        accion_def = next(
            (a for a in ACCIONES_DISPONIBLES if a["nombre"] == nombre_accion),
            None,
        )
        if not accion_def:
            nombres = ", ".join(a["nombre"] for a in ACCIONES_DISPONIBLES)
            return f"Acción '{nombre_accion}' no encontrada.\nAcciones válidas: {nombres}"

        accion = AccionConfirmable(
            nombre=accion_def["nombre"],
            descripcion=accion_def["descripcion"],
            nivel=accion_def["nivel"],
            ejecutar=accion_def["ejecutar"],
        )

        return await self.solicitar_confirmacion(telefono, accion)


# Singleton
ejecucion = ModuloEjecucion()
