# agent/scheduler.py — Scheduler de recordatorios automáticos
# Generado por AgentKit

"""
Verifica cada minuto si hay recordatorios pendientes y los envía via WhatsApp.
Usa APScheduler con AsyncIOScheduler para correr dentro del proceso de FastAPI.
Soporta recordatorios únicos y recurrentes (diario, semanal, dias_semana, mensual).
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agent.memory import (
    obtener_recordatorios_pendientes,
    marcar_recordatorio_enviado,
    registrar_fallo_recordatorio,
)

logger = logging.getLogger("agentkit")

# Scheduler global — se inicia en el lifespan de FastAPI
scheduler = AsyncIOScheduler(timezone="UTC")


async def _verificar_y_enviar_recordatorios(proveedor):
    """
    Job que corre cada minuto.
    Busca recordatorios vencidos y los envía via WhatsApp.
    - Si el envío es exitoso: marca como enviado (único) o calcula próxima ocurrencia (recurrente).
    - Si falla: incrementa intentos_fallidos. Al 3er fallo, el recordatorio queda pausado.
    - Al recuperarse (envío exitoso después de fallos), el contador se reinicia.
    """
    try:
        pendientes = await obtener_recordatorios_pendientes()
        if not pendientes:
            return

        logger.info(f"Scheduler: {len(pendientes)} recordatorio(s) pendiente(s)")

        for r in pendientes:
            # Formato del mensaje que le llega al usuario
            if r.recurrencia:
                encabezado = "🔔 Recordatorio recurrente"
            else:
                encabezado = "🔔 Recordatorio"
            mensaje = f"{encabezado}: {r.mensaje}"

            enviado = await proveedor.enviar_mensaje(r.telefono, mensaje)

            if enviado:
                await marcar_recordatorio_enviado(r.id)
                tipo = "recurrente" if r.recurrencia else "único"
                logger.info(f"Recordatorio #{r.id} ({tipo}) enviado a {r.telefono}: {r.mensaje}")

                # Si venía con fallos previos, notificar que el canal se recuperó
                if r.intentos_fallidos and r.intentos_fallidos > 0:
                    aviso = (
                        "✅ El recordatorio que había fallado antes acaba de enviarse correctamente. "
                        "El canal está funcionando de nuevo."
                    )
                    try:
                        await proveedor.enviar_mensaje(r.telefono, aviso)
                    except Exception:
                        pass  # El aviso es best-effort

            else:
                await registrar_fallo_recordatorio(r.id)
                nuevo_fallos = (r.intentos_fallidos or 0) + 1
                logger.warning(
                    f"No se pudo enviar recordatorio #{r.id} a {r.telefono} "
                    f"(intento {nuevo_fallos}/3)"
                )

                if nuevo_fallos >= 3:
                    logger.error(
                        f"Recordatorio #{r.id} pausado tras 3 fallos consecutivos. "
                        f"Se reactiva cuando el envío sea exitoso."
                    )

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
