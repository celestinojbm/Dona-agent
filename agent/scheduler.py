# agent/scheduler.py — Scheduler de recordatorios automáticos
# Dona

"""
Verifica cada minuto si hay recordatorios pendientes y los envía via WhatsApp.
Usa APScheduler con AsyncIOScheduler para correr dentro del proceso de FastAPI.
Soporta recordatorios únicos y recurrentes (diario, semanal, dias_semana, mensual).
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agent.memory import (
    obtener_recordatorios_pendientes,
    marcar_recordatorio_enviado,
    registrar_fallo_recordatorio,
    obtener_usuarios_onboarding_pendientes,
    claim_recordatorio_para_envio,
    liberar_claim_recordatorio,
    claim_gcal_enviado,
    liberar_claim_gcal,
    cancelar_recordatorio_por_id,
    saltar_ocurrencias_atrasadas,
    fecha_fin_efectiva_recordatorio,
    obtener_timezone,
    _tipo_recurrencia,
)
from agent.onboarding import iniciar_siguiente_fase
from agent.proactivity import verificar_proactividad
from agent.learning import actualizar_perfiles_todos
from agent.envio_gate import contexto_envio_automatico, HORA_INICIO_ENVIOS_PROACTIVOS

# Timeout máximo para jobs del scheduler (en segundos).
# Si un job tarda más que esto, se cancela para no bloquear el event loop.
_JOB_TIMEOUT_SEGUNDOS = 30

logger = logging.getLogger("dona")

# Scheduler global — se inicia en el lifespan de FastAPI
scheduler = AsyncIOScheduler(timezone="UTC")

# ── Política de recurrencias atrasadas (Fase 0 · 2.4, criterio Hermes) ──────
# Una ocurrencia atrasada solo se entrega si sigue FRESCA; si no, se sanea
# avanzando la recurrencia al futuro SIN enviar (nunca catch-up múltiple).

_VENTANA_FRESCURA = {
    "cada_30_minutos": timedelta(minutes=45),
    "cada_hora": timedelta(minutes=90),
    "horario": timedelta(minutes=90),
}
_FRESCURA_DEFAULT = timedelta(hours=6)  # diario / semanal / dias_semana / mensual

# Atraso a partir del cual una entrega deja de ser "puntual" y pasa a ser un
# catch-up: para tipos diarios o mayores, un catch-up no debe caer en quiet
# hours (la hora de entrega ya NO es la que eligió el usuario).
_ATRASO_PUNTUAL = timedelta(minutes=15)

# Tope diario de envíos por tarea sub-diaria (hard cap inicial).
# Contador in-memory per-proceso: best-effort — hoy el scheduler corre en UN
# proceso (los claims de 2.3 serializan el cross-proceso) y un restart lo
# resetea acotado por el propio cap. El freno duro de fondo es fecha_fin.
_CAP_DIARIO_SUB_DIARIO = {"cada_30_minutos": 16, "cada_hora": 12, "horario": 12}
_envios_recurrentes_hoy: dict[tuple[int, str], int] = {}


def _clave_dia(ahora: datetime) -> str:
    return ahora.strftime("%Y-%m-%d")


def _cap_diario_alcanzado(recordatorio_id: int, tipo: str, ahora: datetime) -> bool:
    cap = _CAP_DIARIO_SUB_DIARIO.get(tipo)
    if cap is None:
        return False
    return _envios_recurrentes_hoy.get((recordatorio_id, _clave_dia(ahora)), 0) >= cap


def _registrar_envio_recurrente(recordatorio_id: int, tipo: str, ahora: datetime) -> None:
    if tipo not in _CAP_DIARIO_SUB_DIARIO:
        return
    clave = (recordatorio_id, _clave_dia(ahora))
    _envios_recurrentes_hoy[clave] = _envios_recurrentes_hoy.get(clave, 0) + 1


def _podar_contadores_diarios(ahora: datetime) -> None:
    hoy = _clave_dia(ahora)
    for clave in list(_envios_recurrentes_hoy):
        if clave[1] != hoy:
            del _envios_recurrentes_hoy[clave]


async def _en_quiet_hours_local(telefono: str) -> bool:
    """True si para el usuario son quiet hours locales. Sin timezone conocida
    no se aplica (la hora UTC mentiría para usuarios de EEUU); si la LECTURA
    falla, para un catch-up tardío se asume quiet hours (mejor no enviar)."""
    try:
        offset_min = await obtener_timezone(telefono)
    except Exception:
        return True
    if offset_min is None:
        return False
    hora_local = (datetime.utcnow() + timedelta(minutes=offset_min)).hour
    return hora_local < HORA_INICIO_ENVIOS_PROACTIVOS


async def _elegibilidad_recordatorio(r, ahora: datetime) -> str:
    """Decide qué hacer con un recordatorio pendiente:
      'enviar'   — ocurrencia fresca, flujo normal.
      'sanear'   — recurrente atrasado / cap diario / catch-up en quiet hours:
                   avanzar al futuro SIN enviar.
      'cancelar' — fecha_fin (efectiva) vencida.
    Los únicos no se sanean: mejor tarde que nunca para un aviso explícito."""
    if not r.recurrencia:
        return "enviar"

    fin = fecha_fin_efectiva_recordatorio(r.fecha_fin, r.recurrencia, r.creado)
    if fin is not None and ahora > fin:
        return "cancelar"

    tipo = _tipo_recurrencia(r.recurrencia)
    atraso = ahora - r.fecha_hora

    if atraso > _VENTANA_FRESCURA.get(tipo, _FRESCURA_DEFAULT):
        return "sanear"

    if _cap_diario_alcanzado(r.id, tipo, ahora):
        return "sanear"

    # Catch-up de tipos diarios o mayores: no entregar en quiet hours (la
    # hora ya no es la que el usuario eligió). Las sub-diarias quedan
    # cubiertas por su ventana de frescura corta.
    if (
        tipo not in _VENTANA_FRESCURA
        and atraso > _ATRASO_PUNTUAL
        and await _en_quiet_hours_local(r.telefono)
    ):
        return "sanear"

    return "enviar"


async def _verificar_y_enviar_recordatorios(proveedor):
    """
    Job que corre cada minuto.
    Busca recordatorios vencidos y los envía via WhatsApp.
    - Si el envío es exitoso: marca como enviado (único) o calcula próxima ocurrencia (recurrente).
    - Si falla: incrementa intentos_fallidos. Al 3er fallo, el recordatorio queda pausado.
    - Al recuperarse (envío exitoso después de fallos), el contador se reinicia.
    - Tiene un timeout de 30s para evitar que una conexión colgada bloquee el scheduler.
    """
    try:
        await asyncio.wait_for(
            _verificar_y_enviar_recordatorios_impl(proveedor),
            timeout=_JOB_TIMEOUT_SEGUNDOS,
        )
    except TimeoutError:
        logger.error(
            f"[SCHEDULER] _verificar_y_enviar_recordatorios cancelado por timeout "
            f"({_JOB_TIMEOUT_SEGUNDOS}s) — posible conexión de DB colgada"
        )
    except Exception as e:
        logger.error(f"Error en scheduler de recordatorios ({type(e).__name__}): {e}")


async def _verificar_y_enviar_recordatorios_impl(proveedor):
    """Implementación real del job de recordatorios (envuelta en timeout)."""
    pendientes = await obtener_recordatorios_pendientes()
    if not pendientes:
        return

    logger.info(f"Scheduler: {len(pendientes)} recordatorio(s) pendiente(s)")

    ahora = datetime.utcnow()
    _podar_contadores_diarios(ahora)

    for r in pendientes:
        # ── Política de recurrencias (Fase 0 · 2.4): ¿enviar, sanear o cancelar? ──
        accion = await _elegibilidad_recordatorio(r, ahora)
        if accion == "cancelar":
            if await claim_recordatorio_para_envio(r.id):
                await cancelar_recordatorio_por_id(r.id)
                logger.info(f"[RECURRENCIA] #{r.id} cancelado: fecha_fin (efectiva) vencida")
            continue
        if accion == "sanear":
            # Atrasado / cap diario / catch-up en quiet hours: avanzar la
            # recurrencia al futuro SIN enviar (nunca catch-up múltiple).
            # El claim garantiza que UN solo proceso sanea.
            if await claim_recordatorio_para_envio(r.id):
                await saltar_ocurrencias_atrasadas(r.id)
            continue

        # Formato del mensaje que le llega al usuario
        if r.recurrencia:
            encabezado = "🔔 Recordatorio recurrente"
        else:
            encabezado = "🔔 Recordatorio"
        mensaje = f"{encabezado}: {r.mensaje}"

        # Claim atómico ANTES de enviar (Fase 0 · 2.3): con varios procesos
        # corriendo el scheduler, todos ven esta fila pendiente pero solo UNO
        # gana el claim; el resto la salta (antes: todos enviaban duplicado).
        if not await claim_recordatorio_para_envio(r.id):
            continue

        # Contenido programado por el usuario: opt-out aplica (fail-closed),
        # pero sin quiet hours ni límite diario — la hora la eligió él.
        with contexto_envio_automatico():
            enviado = await proveedor.enviar_mensaje(r.telefono, mensaje)

        if enviado:
            await marcar_recordatorio_enviado(r.id)
            _registrar_envio_recurrente(r.id, _tipo_recurrencia(r.recurrencia), ahora)
            tipo = "recurrente" if r.recurrencia else "único"
            logger.info(f"Recordatorio #{r.id} ({tipo}) enviado a {r.telefono}: {r.mensaje}")

            # Si venía con fallos previos, notificar que el canal se recuperó
            if r.intentos_fallidos and r.intentos_fallidos > 0:
                try:
                    from agent.brain import obtener_mensaje_error
                    aviso = obtener_mensaje_error("recuperacion_recordatorio")
                    with contexto_envio_automatico():
                        await proveedor.enviar_mensaje(r.telefono, aviso)
                except Exception:
                    pass  # El aviso es best-effort

        else:
            await registrar_fallo_recordatorio(r.id)
            # Liberar el claim para conservar el reintento por tick (cada
            # minuto); la pausa a los 3 fallos la gobierna el contador.
            await liberar_claim_recordatorio(r.id)
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


async def _verificar_recordatorios_google_calendar(proveedor):
    """
    Job que corre cada 5 minutos.
    Verifica si algún usuario con Google Calendar conectado tiene un evento
    que comienza en los próximos 30 minutos y le envía un recordatorio proactivo.
    Evita enviar el mismo recordatorio dos veces usando un registro en memoria.
    Tiene un timeout de 30s para evitar bloquear el scheduler.
    """
    try:
        await asyncio.wait_for(
            _verificar_recordatorios_google_calendar_impl(proveedor),
            timeout=_JOB_TIMEOUT_SEGUNDOS,
        )
    except TimeoutError:
        logger.error(
            f"[SCHEDULER] _verificar_recordatorios_google_calendar cancelado por timeout "
            f"({_JOB_TIMEOUT_SEGUNDOS}s)"
        )
    except Exception as e:
        logger.error(f"Error en scheduler de Google Calendar ({type(e).__name__}): {e}")


async def _gcal_ya_enviado(clave: str) -> bool:
    """Verifica si un recordatorio GCal ya fue enviado (DB + memoria)."""
    if clave in _recordatorios_gcal_enviados_mem:
        return True
    try:
        from agent.memory import async_session, RecordatorioGCalEnviado
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(
                select(RecordatorioGCalEnviado).where(RecordatorioGCalEnviado.clave == clave)
            )
            if result.scalar_one_or_none():
                _recordatorios_gcal_enviados_mem.add(clave)
                return True
    except Exception:
        pass
    return False


async def _verificar_recordatorios_google_calendar_impl(proveedor):
    """Implementación real del job de Google Calendar (envuelta en timeout)."""
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
                if await _gcal_ya_enviado(clave):
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

                # Claim atómico ANTES de enviar (Fase 0 · 2.3): el INSERT de
                # la clave (PK) decide UN ganador; los procesos que pierden
                # ven el conflicto y saltan (antes: check-then-act duplicaba).
                if not await claim_gcal_enviado(clave):
                    _recordatorios_gcal_enviados_mem.add(clave)
                    continue

                with contexto_envio_automatico():
                    enviado = await proveedor.enviar_mensaje(telefono, mensaje)
                if enviado:
                    _recordatorios_gcal_enviados_mem.add(clave)
                    logger.info(f"[GCAL] Recordatorio enviado a {telefono}: '{titulo}' en {minutos} min")
                else:
                    # Envío fallido: liberar el claim para que el próximo
                    # ciclo (5 min) lo reintente.
                    await liberar_claim_gcal(clave)

        except Exception as e_user:
            logger.debug(f"[GCAL] Error verificando eventos para {telefono}: {e_user}")


# Caché en memoria para lookup rápido (se llena desde DB al consultar)
# Los registros en DB persisten tras restart — la limpieza la hace _limpiar_datos_expirados
_recordatorios_gcal_enviados_mem: set = set()


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


async def _enviar_resumen_semanal(proveedor):
    """
    Job semanal (domingos 19:00 UTC).
    Genera un recap proactivo de los últimos 7 días para cada usuario con
    proactividad habilitada. Si no hay movimientos, `resumen_semana` retorna
    "" y se salta el envío (para no ruidar).
    """
    try:
        from agent.memory import obtener_usuarios_proactividad_activos
        from agent.reporting import resumen_semana

        usuarios = await obtener_usuarios_proactividad_activos()
        if not usuarios:
            return

        logger.info(f"[RESUMEN-SEMANAL] Generando recap para {len(usuarios)} usuario(s)")

        enviados = 0
        for u in usuarios:
            try:
                texto = await resumen_semana(u["telefono"])
                if not texto:
                    continue
                ok = await proveedor.enviar_mensaje(u["telefono"], texto)
                if ok:
                    enviados += 1
            except Exception as e_u:
                logger.debug(f"[RESUMEN-SEMANAL] Error para {u['telefono']}: {e_u}")

        logger.info(f"[RESUMEN-SEMANAL] {enviados}/{len(usuarios)} recaps enviados")
    except Exception as e:
        logger.error(f"[RESUMEN-SEMANAL] Error en job ({type(e).__name__}): {e}")


async def _verificar_seguimientos_vencidos(proveedor):
    """
    Job que corre cada 10 minutos.
    Busca seguimientos de clientes cuya fecha_programada ya pasó y no están
    completados. Manda un recordatorio por WhatsApp al dueño del negocio y
    los marca como completados para no repetir.

    Multi-tenant: cada seguimiento tiene su propio `telefono` (el dueño).
    """
    try:
        from agent.business.models import Seguimiento
        from agent.memory import async_session
        from sqlalchemy import select, and_
        from agent.business.crm import (
            claim_seguimiento_para_envio,
            revertir_claim_seguimiento,
        )

        ahora = datetime.utcnow()
        async with async_session() as session:
            result = await session.execute(
                select(Seguimiento).where(
                    and_(
                        Seguimiento.completado == False,
                        Seguimiento.fecha_programada <= ahora,
                    )
                ).limit(50)  # evitar avalancha si hay backlog
            )
            vencidos = result.scalars().all()

        if not vencidos:
            return

        logger.info(f"[SEGUIMIENTOS] {len(vencidos)} seguimiento(s) vencido(s) a disparar")

        for seg in vencidos:
            # Claim atómico ANTES de enviar (Fase 0 · 2.3): completado
            # false→true decide UN ganador entre procesos concurrentes;
            # si el envío falla, se revierte para reintentar.
            if not await claim_seguimiento_para_envio(seg.id):
                continue

            cliente_str = f" con {seg.cliente_nombre}" if seg.cliente_nombre else ""
            mensaje = (
                f"📞 Recordatorio de seguimiento{cliente_str}:\n"
                f"{seg.descripcion}\n\n"
                f"(Programado para {seg.fecha_programada.strftime('%d/%m %H:%M')} UTC)"
            )
            with contexto_envio_automatico():
                enviado = await proveedor.enviar_mensaje(seg.telefono, mensaje)
            if enviado:
                logger.info(
                    f"[SEGUIMIENTOS] #{seg.id} enviado a {seg.telefono}: "
                    f"'{seg.descripcion[:60]}'"
                )
            else:
                await revertir_claim_seguimiento(seg.id)
                logger.warning(
                    f"[SEGUIMIENTOS] No se pudo enviar #{seg.id} a {seg.telefono} — "
                    "se reintenta en el próximo ciclo"
                )
    except Exception as e:
        logger.error(f"[SEGUIMIENTOS] Error en job ({type(e).__name__}): {e}")


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
            resp = await client.get(f"{render_url}/")
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
    # Dona 2.0: Monitoreo y alertas cada 15 minutos
    from enhanced.monitoring import job_monitoreo
    scheduler.add_job(
        job_monitoreo,
        trigger="interval",
        minutes=15,
        args=[proveedor],
        id="dona2_monitoreo",
        replace_existing=True,
    )
    # Dona 2.0: Reporte semanal de insights — domingos 20:00 UTC
    from enhanced.insights import job_reporte_semanal
    scheduler.add_job(
        job_reporte_semanal,
        trigger="cron",
        day_of_week="sun",
        hour=20,
        minute=0,
        args=[proveedor],
        id="dona2_reporte_semanal",
        replace_existing=True,
    )
    # Seguimientos de clientes (CRM) — cada 10 minutos
    scheduler.add_job(
        _verificar_seguimientos_vencidos,
        trigger="interval",
        minutes=10,
        args=[proveedor],
        id="verificar_seguimientos_vencidos",
        replace_existing=True,
    )
    # Resumen semanal proactivo a cada usuario — domingos 19:00 UTC
    # (1h antes del reporte de insights de Dona 2.0 para no solaparse)
    scheduler.add_job(
        _enviar_resumen_semanal,
        trigger="cron",
        day_of_week="sun",
        hour=19,
        minute=0,
        args=[proveedor],
        id="resumen_semanal_usuarios",
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
    # Limpieza de deduplicación y caché GCal expirados (cada hora)
    scheduler.add_job(
        _limpiar_datos_expirados,
        trigger="interval",
        hours=1,
        id="limpiar_datos_expirados",
        replace_existing=True,
    )
    # T2.1.E · Reconciliación de reservas de automation (opt-in via
    # AUTOMATION_SCHEDULER_ENABLED). registrar_automation_jobs es no-op
    # si la env var no está activa y nunca propaga excepciones, así que
    # no puede tumbar el startup del resto de jobs.
    try:
        from agent.automation.scheduler import registrar_automation_jobs
        registrar_automation_jobs(scheduler)
    except Exception as e:
        logger.error(
            f"[SCHEDULER] error cargando automation scheduler: {e}"
        )
    scheduler.start()
    logger.info(
        "Scheduler iniciado — recordatorios cada minuto, Google Calendar cada 5 min, "
        "onboarding y proactividad cada hora, monitoreo Dona 2.0 cada 15 min, "
        "seguimientos CRM cada 10 min, self-ping cada 10 min, aprendizaje los domingos, "
        "simulaciones MiroFish lunes/miércoles/viernes a las 2 AM UTC"
    )


async def _limpiar_datos_expirados():
    """
    Limpia registros expirados de deduplicación y caché GCal.
    - mensajes_procesados: elimina registros > 2 horas
    - recordatorios_gcal_enviados: elimina registros > 24 horas
    """
    from datetime import datetime, timedelta
    try:
        from agent.memory import async_session, MensajeProcesado, RecordatorioGCalEnviado
        from sqlalchemy import delete

        async with async_session() as session:
            # Dedup: limpiar > 2 horas
            corte_dedup = datetime.utcnow() - timedelta(hours=2)
            result_dedup = await session.execute(
                delete(MensajeProcesado).where(MensajeProcesado.procesado_en < corte_dedup)
            )

            # GCal cache: limpiar > 24 horas
            corte_gcal = datetime.utcnow() - timedelta(hours=24)
            result_gcal = await session.execute(
                delete(RecordatorioGCalEnviado).where(RecordatorioGCalEnviado.enviado_en < corte_gcal)
            )

            await session.commit()

            dedup_limpiados = result_dedup.rowcount
            gcal_limpiados = result_gcal.rowcount
            if dedup_limpiados or gcal_limpiados:
                logger.info(
                    f"[CLEANUP] Limpiados: {dedup_limpiados} dedup expirados, "
                    f"{gcal_limpiados} caché GCal expirados"
                )
    except Exception as e:
        logger.debug(f"[CLEANUP] Error limpiando datos expirados: {e}")


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
                # Notificación operativa al admin — no sujeta a límite diario.
                with contexto_envio_automatico():
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
