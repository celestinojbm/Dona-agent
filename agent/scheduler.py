# agent/scheduler.py — Scheduler de recordatorios automáticos
# Generado por AgentKit

"""
Verifica cada minuto si hay recordatorios pendientes y los envía via WhatsApp.
Usa APScheduler con AsyncIOScheduler para correr dentro del proceso de FastAPI.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agent.memory import obtener_recordatorios_pendientes, marcar_recordatorio_enviado

logger = logging.getLogger("agentkit")

# Scheduler global — se inicia en el lifespan de FastAPI
scheduler = AsyncIOScheduler(timezone="UTC")


async def _verificar_y_enviar_recordatorios(proveedor):
    """
    Job que corre cada minuto.
    Busca recordatorios vencidos y los envía via WhatsApp.
    """
    try:
        pendientes = await obtener_recordatorios_pendientes()
        if not pendientes:
            return

        logger.info(f"Scheduler: {len(pendientes)} recordatorio(s) pendiente(s)")

        for r in pendientes:
            # Formato del mensaje que le llega al usuario
            mensaje = f"🔔 Recordatorio: {r.mensaje}"
            enviado = await proveedor.enviar_mensaje(r.telefono, mensaje)
            if enviado:
                await marcar_recordatorio_enviado(r.id)
                logger.info(f"Recordatorio #{r.id} enviado a {r.telefono}: {r.mensaje}")
            else:
                logger.warning(f"No se pudo enviar recordatorio #{r.id} a {r.telefono}")

    except Exception as e:
        logger.error(f"Error en scheduler de recordatorios ({type(e).__name__}): {e}")


def iniciar_scheduler(proveedor):
    """Registra el job y arranca el scheduler."""
    scheduler.add_job(
        _verificar_y_enviar_recordatorios,
        trigger="interval",
        minutes=1,
        args=[proveedor],
        id="verificar_recordatorios",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado — verificando recordatorios cada minuto")


def detener_scheduler():
    """Detiene el scheduler limpiamente."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")
