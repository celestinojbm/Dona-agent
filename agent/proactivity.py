# agent/proactivity.py — Motor de proactividad inteligente de Dona
# Generado por AgentKit

"""
Dona envía mensajes proactivos sin que el usuario los solicite.
Se ejecuta cada hora via el scheduler.

5 tipos de disparadores:
  1. Morning Brief    — resumen personalizado al despertar
  2. Deadline Alert   — aviso 24h antes de un recordatorio importante
  3. Urgent Alert     — aviso 1h antes
  4. Context Conflict — detecta conflictos cruzando tareas y grafo MiroFish
  5. Weekly Review    — resumen semanal los viernes
"""

import os
import logging
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

MAX_MENSAJES_DIARIOS = 2   # Límite para no ser molesto

# Cliente de Claude para generación de mensajes proactivos
_claude = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Comandos que el usuario puede enviar para controlar la proactividad
COMANDOS_PROACTIVIDAD = {
    "dona pausa",
    "dona pausar",
    "dona silencio",
    "dona actívate",
    "dona activar",
    "dona activa",
    "dona resumen",
    "dona semana",
}


def es_comando_proactividad(texto: str) -> bool:
    """Retorna True si el texto es un comando de control de proactividad."""
    return texto.strip().lower() in COMANDOS_PROACTIVIDAD


async def manejar_comando_proactividad(telefono: str, texto: str) -> str:
    """Procesa un comando de proactividad y retorna la respuesta de Dona."""
    from agent.memory import guardar_proactividad, obtener_onboarding

    cmd = texto.strip().lower()

    if cmd in ("dona pausa", "dona pausar", "dona silencio"):
        await guardar_proactividad(telefono, proactive_enabled=False)
        return (
            "Entendido, no te enviaré mensajes proactivos hasta que me digas. "
            "Sigo disponible cuando me escribas 🤫"
        )

    if cmd in ("dona actívate", "dona activar", "dona activa"):
        await guardar_proactividad(telefono, proactive_enabled=True)
        return "De vuelta al modo proactivo. Te avisaré cuando detecte algo importante 🚀"

    if cmd == "dona resumen":
        estado = await obtener_onboarding(telefono)
        nombre = estado.get("nombre", "") if estado else ""
        contexto = estado.get("contexto", "") if estado else ""
        return await _generar_morning_brief(telefono, nombre, contexto, bajo_demanda=True)

    if cmd == "dona semana":
        estado = await obtener_onboarding(telefono)
        nombre = estado.get("nombre", "") if estado else ""
        contexto = estado.get("contexto", "") if estado else ""
        return await _generar_weekly_review(telefono, nombre, contexto)

    return "No reconocí ese comando."


# ─── JOB PRINCIPAL (corre cada hora) ────────────────────────────────────────

async def verificar_proactividad(proveedor):
    """
    Revisión horaria de todos los usuarios activos.
    Evalúa disparadores y envía mensajes proactivos cuando corresponde.
    """
    from agent.memory import (
        obtener_usuarios_proactividad_activos,
        incrementar_mensajes_proactivos,
        guardar_proactividad,
        obtener_timezone,
    )

    try:
        usuarios = await obtener_usuarios_proactividad_activos()
        if not usuarios:
            return

        logger.debug(f"Proactividad: revisando {len(usuarios)} usuario(s)")

        for u in usuarios:
            telefono = u["telefono"]
            nombre = u["nombre"] or ""

            # Límite diario
            if u["mensajes_hoy"] >= MAX_MENSAJES_DIARIOS:
                continue

            # Offset de timezone del usuario
            offset_min = await obtener_timezone(telefono)
            offset_min = offset_min or 0
            ahora_local = datetime.utcnow() + timedelta(minutes=offset_min)

            mensaje = await _evaluar_disparadores(u, ahora_local, offset_min)

            if mensaje:
                enviado = await proveedor.enviar_mensaje(telefono, mensaje)
                if enviado:
                    await incrementar_mensajes_proactivos(telefono)
                    logger.info(f"Proactividad: mensaje enviado a {telefono}")

    except Exception as e:
        logger.error(f"Error en verificar_proactividad: {e}")


async def _evaluar_disparadores(usuario: dict, ahora_local: datetime, offset_min: int) -> str | None:
    """
    Evalúa todos los disparadores en orden de prioridad.
    Retorna el primer mensaje que aplique, o None.
    """
    telefono = usuario["telefono"]
    nombre = usuario["nombre"] or ""
    contexto = usuario.get("contexto_onboarding") or ""

    # ── 1. Morning Brief ──────────────────────────────────────────────────────
    brief_hour = usuario.get("morning_brief_hour", 8)
    ultimo_brief = usuario.get("ultimo_morning_brief")
    es_hora_brief = ahora_local.hour == brief_hour and ahora_local.minute < 60
    ya_enviado_hoy = (
        ultimo_brief is not None
        and ultimo_brief.date() >= (datetime.utcnow() - timedelta(minutes=offset_min)).date()
    )
    if es_hora_brief and not ya_enviado_hoy:
        from agent.memory import guardar_proactividad
        msg = await _generar_morning_brief(telefono, nombre, contexto)
        if msg:
            await guardar_proactividad(telefono, ultimo_morning_brief=datetime.utcnow())
            return msg

    # ── 2. Deadline Alert: 24 horas ───────────────────────────────────────────
    msg_24h = await _disparador_deadline_24h(telefono, nombre, offset_min)
    if msg_24h:
        return msg_24h

    # ── 3. Urgent Alert: 1 hora ───────────────────────────────────────────────
    msg_1h = await _disparador_deadline_1h(telefono, nombre, offset_min)
    if msg_1h:
        return msg_1h

    # ── 4. Context Conflict (cada 6 horas máximo) ─────────────────────────────
    ultimo_conflict = usuario.get("ultimo_conflict_check")
    puede_chequear_conflict = (
        ultimo_conflict is None
        or (datetime.utcnow() - ultimo_conflict).total_seconds() >= 21600
    )
    if puede_chequear_conflict and contexto:
        from agent.memory import guardar_proactividad
        await guardar_proactividad(telefono, ultimo_conflict_check=datetime.utcnow())
        msg_conflict = await _disparador_conflict(telefono, nombre, contexto)
        if msg_conflict:
            return msg_conflict

    # ── 5. Weekly Review: viernes entre 17:00 y 17:59 hora local ─────────────
    es_viernes_tarde = ahora_local.weekday() == 4 and ahora_local.hour == 17
    ultimo_review = usuario.get("ultimo_weekly_review")
    ya_revisado_esta_semana = (
        ultimo_review is not None
        and (datetime.utcnow() - ultimo_review).days < 5
    )
    if es_viernes_tarde and not ya_revisado_esta_semana and contexto:
        from agent.memory import guardar_proactividad
        msg = await _generar_weekly_review(telefono, nombre, contexto)
        if msg:
            await guardar_proactividad(telefono, ultimo_weekly_review=datetime.utcnow())
            return msg

    return None


# ─── DISPARADORES ────────────────────────────────────────────────────────────

async def _generar_morning_brief(
    telefono: str, nombre: str, contexto: str, bajo_demanda: bool = False
) -> str | None:
    """Genera el resumen matutino personalizado usando Claude."""
    from agent.memory import obtener_recordatorios_proximas_horas

    try:
        proximos = await obtener_recordatorios_proximas_horas(telefono, horas=16)

        recordatorios_str = ""
        if proximos:
            items = [f"- {r['mensaje']} ({_hora_local_str(r['fecha_hora'])})" for r in proximos[:5]]
            recordatorios_str = "\n".join(items)
        else:
            recordatorios_str = "(ninguno programado para hoy)"

        contexto_resumido = contexto[:600] if contexto else "No disponible"

        saludo = "Buenos días" if not bajo_demanda else "Aquí va tu resumen"

        prompt = (
            f"Eres Dona, asistente personal de WhatsApp. "
            f"Tono: cálido, directo, motivador. Máximo 120 palabras. Sin markdown pesado.\n\n"
            f"Genera el resumen matutino para {nombre or 'el usuario'}.\n\n"
            f"Recordatorios de hoy:\n{recordatorios_str}\n\n"
            f"Contexto del usuario (proyectos, rutina, metas):\n{contexto_resumido}\n\n"
            f"El mensaje debe:\n"
            f"1. Saludar con '{saludo} {nombre or ''}' y el día de la semana\n"
            f"2. Mencionar el recordatorio más importante si hay alguno\n"
            f"3. Una motivación corta alineada con sus metas\n"
            f"4. Terminar con una pregunta de acción concreta\n"
            f"5. Emojis con moderación (máx 3)"
        )

        response = await _claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else None

    except Exception as e:
        logger.error(f"Proactividad _generar_morning_brief ({telefono}): {e}")
        return None


async def _disparador_deadline_24h(telefono: str, nombre: str, offset_min: int) -> str | None:
    """Alerta de recordatorio que vence en las próximas 24 horas."""
    from agent.memory import obtener_recordatorios_proximas_horas

    try:
        proximos = await obtener_recordatorios_proximas_horas(telefono, horas=24)
        if not proximos:
            return None

        # Tomar el más próximo
        r = proximos[0]
        horas_restantes = (r["fecha_hora"] - datetime.utcnow()).total_seconds() / 3600

        # Solo disparar si está entre 22h y 26h (ventana de 4h para no repetir)
        if not (22 <= horas_restantes <= 26):
            return None

        hora_str = _hora_local_str(r["fecha_hora"], offset_min)
        horas_int = int(horas_restantes)

        return (
            f"⏰ {nombre}, tienes un recordatorio importante en *{horas_int} horas*:\n\n"
            f"_{r['mensaje']}_\n"
            f"Hora: {hora_str}\n\n"
            f"¿Hay algo que necesites preparar antes?"
        )
    except Exception as e:
        logger.error(f"Proactividad _disparador_deadline_24h ({telefono}): {e}")
        return None


async def _disparador_deadline_1h(telefono: str, nombre: str, offset_min: int) -> str | None:
    """Alerta urgente de recordatorio que vence en menos de 1 hora."""
    from agent.memory import obtener_recordatorios_proximas_horas

    try:
        proximos = await obtener_recordatorios_proximas_horas(telefono, horas=1)
        if not proximos:
            return None

        r = proximos[0]
        minutos = int((r["fecha_hora"] - datetime.utcnow()).total_seconds() / 60)

        # No duplicar con el scheduler de recordatorios (que también lo envía al vencer)
        if minutos < 5:
            return None

        return (
            f"🚨 {nombre}, en *{minutos} minutos*:\n\n"
            f"_{r['mensaje']}_\n\n"
            f"¿Estás listo o necesitas algo?"
        )
    except Exception as e:
        logger.error(f"Proactividad _disparador_deadline_1h ({telefono}): {e}")
        return None


async def _disparador_conflict(telefono: str, nombre: str, contexto: str) -> str | None:
    """
    Usa Claude + MiroFish para detectar conflictos entre tareas/relaciones.
    Solo se llama cada 6 horas por usuario.
    """
    from agent.memory import (
        obtener_recordatorios_proximas_horas,
        obtener_mirofish_estado,
    )
    import agent.mirofish_client as mf

    try:
        proximos = await obtener_recordatorios_proximas_horas(telefono, horas=48)
        if not proximos:
            return None

        tareas_str = "\n".join([f"- {r['mensaje']} ({_hora_local_str(r['fecha_hora'])})" for r in proximos[:5]])

        # Enriquecer con contexto MiroFish si está disponible
        mirofish_ctx = ""
        if mf._disponible():
            estado = await obtener_mirofish_estado(telefono)
            if estado and estado.get("graph_id"):
                # Usamos el contexto del onboarding como proxy del grafo
                mirofish_ctx = f"Contexto de relaciones del usuario:\n{contexto[:400]}"

        prompt = (
            f"Eres Dona, asistente personal. Analiza si hay un conflicto o riesgo real.\n\n"
            f"Recordatorios próximos de {nombre}:\n{tareas_str}\n\n"
            f"{mirofish_ctx}\n\n"
            f"Si detectas un conflicto real y accionable (dos compromisos que chocan, "
            f"una dependencia de alguien que no ha respondido, un riesgo inminente), "
            f"escribe un mensaje corto para WhatsApp (máx 80 palabras, sin markdown). "
            f"Si no hay nada urgente, responde exactamente: SIN_CONFLICTO"
        )

        response = await _claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )

        resultado = response.content[0].text.strip() if response.content else "SIN_CONFLICTO"
        if resultado == "SIN_CONFLICTO" or not resultado:
            return None
        return resultado

    except Exception as e:
        logger.error(f"Proactividad _disparador_conflict ({telefono}): {e}")
        return None


async def _generar_weekly_review(telefono: str, nombre: str, contexto: str) -> str | None:
    """Genera el resumen semanal conectando logros con metas."""
    from agent.memory import obtener_recordatorios_proximas_horas

    try:
        proximos = await obtener_recordatorios_proximas_horas(telefono, horas=168)  # próxima semana
        proximos_str = (
            "\n".join([f"- {r['mensaje']}" for r in proximos[:5]])
            if proximos else "(ninguno programado)"
        )
        contexto_resumido = contexto[:500] if contexto else "No disponible"

        prompt = (
            f"Eres Dona, asistente personal de WhatsApp. "
            f"Tono: motivador, estratégico, cálido. Máximo 130 palabras. Sin markdown pesado.\n\n"
            f"Genera el resumen semanal de fin de viernes para {nombre or 'el usuario'}.\n\n"
            f"Recordatorios de la próxima semana:\n{proximos_str}\n\n"
            f"Metas y proyectos del usuario:\n{contexto_resumido}\n\n"
            f"El mensaje debe:\n"
            f"1. Reconocer que terminó otra semana\n"
            f"2. Conectar la próxima semana con sus metas grandes\n"
            f"3. Destacar la prioridad más importante para el lunes\n"
            f"4. Terminar con una pregunta motivadora\n"
            f"5. Emojis con moderación"
        )

        response = await _claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else None

    except Exception as e:
        logger.error(f"Proactividad _generar_weekly_review ({telefono}): {e}")
        return None


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _hora_local_str(fecha_utc: datetime, offset_min: int = 0) -> str:
    """Convierte datetime UTC a string legible en hora local del usuario."""
    local = fecha_utc + timedelta(minutes=offset_min)
    return local.strftime("%d/%m %H:%M")
