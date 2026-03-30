# agent/scheduler.py — Scheduler de recordatorios automáticos
# Generado por AgentKit

"""
Verifica cada minuto si hay recordatorios pendientes y los envía via WhatsApp.
Usa APScheduler con AsyncIOScheduler para correr dentro del proceso de FastAPI.
Soporta recordatorios únicos y recurrentes (diario, semanal, dias_semana, mensual).
"""

import os
import logging
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agent.memory import (
    obtener_recordatorios_pendientes,
    marcar_recordatorio_enviado,
    registrar_fallo_recordatorio,
    obtener_usuarios_onboarding_pendientes,
)
from agent.onboarding import iniciar_siguiente_fase
from agent.proactivity import verificar_proactividad
from agent.learning import actualizar_perfiles_todos

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
                    try:
                        from agent.brain import obtener_mensaje_error
                        aviso = obtener_mensaje_error("recuperacion_recordatorio")
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


async def _verificar_recordatorios_google_calendar(proveedor):
    """
    Job que corre cada 5 minutos.
    Verifica si algún usuario con Google Calendar conectado tiene un evento
    que comienza en los próximos 30 minutos y le envía un recordatorio proactivo.
    Evita enviar el mismo recordatorio dos veces usando un registro en memoria.
    """
    try:
        import agent.google_calendar as gc
        from agent.memory import obtener_todos_con_google_calendar, obtener_timezone

        usuarios = await obtener_todos_con_google_calendar()
        if not usuarios:
            return

        for telefono in usuarios:
            try:
                offset_min = await obtener_timezone(telefono) or 0
                proximos = await gc.obtener_proximos_eventos(
                    telefono,
                    offset_min=offset_min,
                    minutos_anticipacion=30,
                )

                for evento in proximos:
                    # Crear clave única para evitar recordatorio duplicado
                    clave = f"gcal_reminder_{telefono}_{evento['id']}"
                    if clave in _recordatorios_gcal_enviados:
                        continue

                    minutos = evento['minutos_restantes']
                    titulo = evento['titulo']
                    lugar = evento.get('lugar', '')

                    if minutos <= 5:
                        tiempo_str = "en menos de 5 minutos"
                    elif minutos <= 15:
                        tiempo_str = f"en {minutos} minutos"
                    else:
                        tiempo_str = f"en {minutos} minutos"

                    mensaje = f"📅 Recordatorio: *{titulo}* comienza {tiempo_str}."
                    if lugar:
                        mensaje += f"\n📍 {lugar}"

                    enviado = await proveedor.enviar_mensaje(telefono, mensaje)
                    if enviado:
                        _recordatorios_gcal_enviados.add(clave)
                        logger.info(f"[GCAL] Recordatorio enviado a {telefono}: '{titulo}' en {minutos} min")

            except Exception as e_user:
                logger.debug(f"[GCAL] Error verificando eventos para {telefono}: {e_user}")

    except Exception as e:
        logger.error(f"Error en scheduler de Google Calendar ({type(e).__name__}): {e}")


# Registro en memoria de recordatorios de Google Calendar ya enviados (evita duplicados)
# Se limpia al reiniciar el servidor — comportamiento correcto para recordatorios del día
_recordatorios_gcal_enviados: set = set()


async def _verificar_avance_onboarding(proveedor):
    """
    Job que corre cada hora.
    Activa la siguiente fase del onboarding para usuarios que ya esperaron 18+ horas.
    """
    try:
        pendientes = await obtener_usuarios_onboarding_pendientes()
        if not pendientes:
            return
        logger.info(f"Onboarding scheduler: {len(pendientes)} usuario(s) pendiente(s) de avanzar fase")
        for usuario in pendientes:
            activado = await iniciar_siguiente_fase(usuario["telefono"], proveedor)
            if activado:
                logger.info(f"Onboarding: fase avanzada para {usuario['telefono']}")
    except Exception as e:
        logger.error(f"Error en scheduler de onboarding ({type(e).__name__}): {e}")


async def _self_ping():
    """
    Self-ping para mantener vivo el servicio en Render Free Tier.
    Render duerme los servicios gratuitos después de 15 minutos de inactividad.
    Este job hace un GET al propio /health cada 10 minutos para evitarlo.
    """
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not render_url:
        return  # No estamos en Render o no se configuró la URL
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{render_url}/health")
            logger.debug(f"Self-ping: {resp.status_code}")
    except Exception as e:
        logger.debug(f"Self-ping falló (no crítico): {type(e).__name__}")


def iniciar_scheduler(proveedor):
    """Registra los jobs y arranca el scheduler."""
    scheduler.add_job(
        _verificar_y_enviar_recordatorios,
        trigger="interval",
        minutes=1,
        args=[proveedor],
        id="verificar_recordatorios",
        replace_existing=True,
    )
    scheduler.add_job(
        _verificar_avance_onboarding,
        trigger="interval",
        hours=1,
        args=[proveedor],
        id="verificar_onboarding",
        replace_existing=True,
    )
    scheduler.add_job(
        verificar_proactividad,
        trigger="interval",
        hours=1,
        args=[proveedor],
        id="verificar_proactividad",
        replace_existing=True,
    )
    scheduler.add_job(
        _verificar_recordatorios_google_calendar,
        trigger="interval",
        minutes=5,
        args=[proveedor],
        id="verificar_recordatorios_gcal",
        replace_existing=True,
    )
    scheduler.add_job(
        actualizar_perfiles_todos,
        trigger="cron",
        day_of_week="sun",
        hour=23,
        minute=0,
        id="actualizar_perfiles_aprendizaje",
        replace_existing=True,
    )
    # Self-ping para mantener vivo el servicio en Render Free Tier
    scheduler.add_job(
        _self_ping,
        trigger="interval",
        minutes=10,
        id="self_ping_keep_alive",
        replace_existing=True,
    )
    # ─── Simulaciones MiroFish programadas ────────────────────────────────────
    # Lunes 2 AM — Optimización de Recursos
    scheduler.add_job(
        _ejecutar_simulacion_mirofish_programada,
        trigger="cron",
        day_of_week="mon",
        hour=2,
        minute=0,
        args=["optimizacion_recursos", proveedor],
        id="mirofish_optimizacion_recursos",
        replace_existing=True,
    )
    # Miércoles 2 AM — Estrategias de Crecimiento
    scheduler.add_job(
        _ejecutar_simulacion_mirofish_programada,
        trigger="cron",
        day_of_week="wed",
        hour=2,
        minute=0,
        args=["crecimiento_usuarios", proveedor],
        id="mirofish_crecimiento_usuarios",
        replace_existing=True,
    )
    # Viernes 2 AM — Riesgos Operacionales
    scheduler.add_job(
        _ejecutar_simulacion_mirofish_programada,
        trigger="cron",
        day_of_week="fri",
        hour=2,
        minute=0,
        args=["riesgos_operacionales", proveedor],
        id="mirofish_riesgos_operacionales",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler iniciado — recordatorios cada minuto, Google Calendar cada 5 min, "
        "onboarding y proactividad cada hora, self-ping cada 10 min, aprendizaje los domingos, "
        "simulaciones MiroFish lunes/miércoles/viernes a las 2 AM UTC"
    )


async def _ejecutar_simulacion_mirofish_programada(escenario_id: str, proveedor):
    """
    Job semanal que ejecuta una simulación MiroFish programada y guarda el insight en Zep.
    Requiere MIROFISH_PROJECT_ID y MIROFISH_GRAPH_ID en las variables de entorno de Render.
    """
    try:
        import agent.mirofish_client as mf

        if not mf._disponible():
            logger.debug("[SCHEDULER-MIROFISH] MiroFish no configurado, saltando simulación")
            return

        escenario = next((e for e in mf.ESCENARIOS_PROGRAMADOS if e["id"] == escenario_id), None)
        if not escenario:
            logger.error(f"[SCHEDULER-MIROFISH] Escenario '{escenario_id}' no encontrado")
            return

        project_id = os.getenv("MIROFISH_PROJECT_ID", "")
        graph_id = os.getenv("MIROFISH_GRAPH_ID", "")

        if not project_id or not graph_id:
            logger.warning(
                "[SCHEDULER-MIROFISH] Faltan MIROFISH_PROJECT_ID o MIROFISH_GRAPH_ID. "
                "Agrégalos en Render → Dona-agent → Environment."
            )
            return

        admin_telefono = os.getenv("ADMIN_WHATSAPP", "")

        async def notificar_admin(nombre_escenario: str, resumen: str):
            if admin_telefono and proveedor:
                mensaje = (
                    f"🧠 *Análisis MiroFish completado*\n"
                    f"Escenario: _{nombre_escenario}_\n\n"
                    f"{resumen[:400]}\n\n"
                    f"_El insight ya está disponible para consultas en Dona._"
                )
                await proveedor.enviar_mensaje(admin_telefono, mensaje)

        resultado = await mf.pipeline_simulacion_programada(
            project_id=project_id,
            graph_id=graph_id,
            escenario=escenario,
            notificar_callback=notificar_admin if admin_telefono else None,
        )

        if resultado["exito"]:
            logger.info(f"[SCHEDULER-MIROFISH] '{escenario_id}' completado exitosamente")
        else:
            logger.error(f"[SCHEDULER-MIROFISH] '{escenario_id}' falló: {resultado.get('error')}")

    except Exception as e:
        logger.error(f"[SCHEDULER-MIROFISH] Error inesperado en '{escenario_id}': {e}")


def detener_scheduler():
    """Detiene el scheduler limpiamente."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")
