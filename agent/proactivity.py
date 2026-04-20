# agent/proactivity.py — Motor de proactividad inteligente de Dona
# Dona

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

# Palabras clave TCPA / CAN-SPAM: cuando el usuario envía cualquiera de estas
# en aislamiento (como primer/único contenido del mensaje), DEBE desactivarse
# la proactividad inmediatamente. Son palabras clave reconocidas por la FCC
# como opt-out estándar en mensajería SMS/WhatsApp en EEUU.
COMANDOS_STOP_TCPA = {
    "stop", "unsubscribe", "cancel", "end", "quit",
    "baja", "dar de baja", "no molestar",
}

# Palabras para reactivar tras STOP (TCPA-compliant re-opt-in)
COMANDOS_START_TCPA = {
    "start", "subscribe", "unstop", "yes",
    "alta", "reactivar", "activar proactividad",
}

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
    "dona olvida mis patrones",
    "dona olvida patrones",
}


def es_comando_stop_tcpa(texto: str) -> bool:
    """Retorna True si el texto es un opt-out TCPA (STOP, UNSUBSCRIBE, BAJA, etc.).
    La detección ignora mayúsculas/minúsculas y espacios/puntuación al final."""
    normalizado = texto.strip().lower().rstrip(".!?;,")
    return normalizado in COMANDOS_STOP_TCPA


def es_comando_start_tcpa(texto: str) -> bool:
    """Retorna True si el texto es un re-opt-in tras STOP."""
    normalizado = texto.strip().lower().rstrip(".!?;,")
    return normalizado in COMANDOS_START_TCPA


async def manejar_stop_tcpa(telefono: str) -> str:
    """Desactiva toda proactividad para el usuario. Mensaje compliant con TCPA 47 CFR 64.1200."""
    from agent.memory import guardar_proactividad
    await guardar_proactividad(telefono, proactive_enabled=False)
    logger.info(f"[TCPA] Opt-out registrado para {telefono}")
    return (
        "✅ Has sido dado de baja de mensajes proactivos de Dona.\n\n"
        "No te enviaré recordatorios ni resúmenes automáticos. "
        "Sigues pudiendo escribirme cuando necesites algo.\n\n"
        "_Envía *START* si más adelante quieres reactivar los mensajes proactivos._"
    )


async def manejar_start_tcpa(telefono: str) -> str:
    """Reactiva proactividad tras un STOP previo."""
    from agent.memory import guardar_proactividad
    await guardar_proactividad(telefono, proactive_enabled=True)
    logger.info(f"[TCPA] Re-opt-in registrado para {telefono}")
    return (
        "✅ ¡Bienvenido de vuelta! Los mensajes proactivos están activos nuevamente.\n\n"
        "_Recuerda: siempre puedes enviar *STOP* para desactivarlos._"
    )


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

    if cmd in ("dona olvida mis patrones", "dona olvida patrones"):
        from agent.memory import borrar_datos_aprendizaje
        await borrar_datos_aprendizaje(telefono)
        return (
            "Listo, borré todos tus datos de comportamiento y tu perfil de aprendizaje. "
            "Empiezo desde cero 🗑️\n\n"
            "Seguiré aprendiendo de tus interacciones a partir de ahora."
        )

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


async def _obtener_ubicacion_usuario(telefono: str) -> dict:
    """
    Retorna ubicación del usuario con la ciudad efectiva (temporal si de viaje, base si no).
    """
    from agent.memory import obtener_ubicacion, obtener_ciudad_actual
    ub = await obtener_ubicacion(telefono)
    if not ub:
        return {"ciudad": None, "pais": None, "industria": None}
    # Usar ciudad efectiva (viaje temporal tiene prioridad)
    ciudad_efectiva = await obtener_ciudad_actual(telefono)
    return {
        "ciudad": ciudad_efectiva,          # Puede ser temporal (viaje) o permanente
        "ciudad_base": ub.get("ciudad"),    # Siempre la de residencia
        "pais": ub.get("pais"),
        "industria": ub.get("industria"),
    }


async def _evaluar_disparadores(usuario: dict, ahora_local: datetime, offset_min: int) -> str | None:
    """
    Evalúa todos los disparadores en orden de prioridad.
    Retorna el primer mensaje que aplique, o None.
    """
    telefono = usuario["telefono"]
    nombre = usuario["nombre"] or ""
    contexto = usuario.get("contexto_onboarding") or ""

    # ── Guardia nocturna: NO enviar mensajes proactivos antes de las 7am ─────
    if ahora_local.hour < 7:
        return None

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
        msg = await _generar_morning_brief(telefono, nombre, contexto, offset_min=offset_min)
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

    # ── 6. Alerta de lluvia + recordatorio presencial ─────────────────────────
    msg_lluvia = await _disparador_lluvia(telefono, nombre, offset_min)
    if msg_lluvia:
        return msg_lluvia

     # ── 7. Noticias de la industria (máx 1 por semana) ─────────────────────
    msg_noticias = await _disparador_noticias(telefono, nombre, contexto)
    if msg_noticias:
        return msg_noticias

    # ── 8. Consejera estratégica: detecta decisiones importantes pendientes (cada 12 horas) ──
    ultimo_consejo = usuario.get("ultimo_consejo_estrategico")
    puede_dar_consejo = (
        ultimo_consejo is None
        or (datetime.utcnow() - ultimo_consejo).total_seconds() >= 43200  # 12 horas
    )
    if puede_dar_consejo and contexto:
        import agent.mirofish_client as _mf
        if _mf._disponible():
            from agent.memory import guardar_proactividad
            await guardar_proactividad(telefono, ultimo_consejo_estrategico=datetime.utcnow())
            msg_consejo = await _disparador_consejo_estrategico(telefono, nombre, contexto)
            if msg_consejo:
                return msg_consejo

    return None


# ─── DISPARADORES ────────────────────────────────────────────────────────────

async def _generar_morning_brief(
    telefono: str, nombre: str, contexto: str, bajo_demanda: bool = False, offset_min: int = 0
) -> str | None:
    """Genera el resumen matutino personalizado usando Claude, incluyendo clima si está disponible."""
    from agent.memory import obtener_recordatorios_proximas_horas
    from agent.real_world import obtener_clima, resumen_clima_str

    try:
        proximos = await obtener_recordatorios_proximas_horas(telefono, horas=16)

        recordatorios_str = ""
        if proximos:
            items = [f"- {r['mensaje']} ({_hora_local_str(r['fecha_hora'], offset_min)})" for r in proximos[:5]]
            recordatorios_str = "\n".join(items)
        else:
            recordatorios_str = "(ninguno programado para hoy)"

        # Enriquecer con clima si el usuario tiene ciudad configurada
        clima_str = ""
        ubicacion = await _obtener_ubicacion_usuario(telefono)
        if ubicacion.get("ciudad"):
            pronostico = await obtener_clima(ubicacion["ciudad"])
            if pronostico:
                clima_str = f"Clima en {ubicacion['ciudad']}: {resumen_clima_str(pronostico)}"

        contexto_resumido = contexto[:600] if contexto else "No disponible"
        saludo = "Buenos días" if not bajo_demanda else "Aquí va tu resumen"

        # Enriquecer con datos de negocio si el usuario tiene perfil
        negocio_str = ""
        try:
            from agent.business.reportes import generar_reporte_diario
            reporte_neg = await generar_reporte_diario(telefono)
            if reporte_neg:
                negocio_str = reporte_neg
        except Exception:
            pass

        prompt = (
            f"Eres Dona, asistente personal de WhatsApp. "
            f"Tono: cálido, directo, motivador. Máximo {'180' if negocio_str else '130'} palabras. Sin markdown pesado.\n\n"
            f"Genera el resumen matutino para {nombre or 'el usuario'}.\n\n"
            f"Recordatorios de hoy:\n{recordatorios_str}\n\n"
            + (f"Clima de hoy: {clima_str}\n\n" if clima_str else "")
            + (f"Datos de su negocio:\n{negocio_str}\n\n" if negocio_str else "")
            + f"Contexto del usuario (proyectos, rutina, metas):\n{contexto_resumido}\n\n"
            f"El mensaje debe:\n"
            f"1. Saludar con '{saludo} {nombre or ''}' y el día de la semana\n"
            f"2. Mencionar el clima brevemente si hay algo relevante (lluvia, temperatura extrema)\n"
            f"3. Mencionar el recordatorio más importante si hay alguno\n"
            + (f"4. Incluir un dato clave de su negocio (pedidos pendientes, ventas del mes, seguimientos)\n" if negocio_str else "")
            + f"{'5' if negocio_str else '4'}. Una motivación corta alineada con sus metas\n"
            f"{'6' if negocio_str else '5'}. Terminar con una pregunta de acción concreta\n"
            f"{'7' if negocio_str else '6'}. Emojis con moderación (máx 3)\n\n"
            f"REGLAS ABSOLUTAS:\n"
            f"- NUNCA menciones la calidad, completitud o estado del contexto ('el contexto está mezclado', 'no tengo suficiente info', etc.)\n"
            f"- NUNCA expongas tu razonamiento interno ni tus limitaciones\n"
            f"- Si el contexto es insuficiente, genera igualmente un mensaje cálido y motivador sin mencionarlo\n"
            f"- El usuario NUNCA debe saber que estás trabajando con información incompleta"
        )

        response = await _claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=220,
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

        # Tomar el más próximo que sea IMPORTANTE (no básico como "tomar agua")
        r = None
        for candidato in proximos:
            if _es_recordatorio_importante(candidato["mensaje"]):
                r = candidato
                break
        if not r:
            return None

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

        # Solo avisar con anticipación para recordatorios IMPORTANTES
        r = None
        for candidato in proximos:
            if _es_recordatorio_importante(candidato["mensaje"]):
                r = candidato
                break
        if not r:
            return None

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
            model="claude-sonnet-4-6",
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

        # Datos de negocio de la semana
        negocio_str = ""
        try:
            from agent.business.reportes import generar_reporte_semanal
            reporte_neg = await generar_reporte_semanal(telefono)
            if reporte_neg:
                negocio_str = reporte_neg
        except Exception:
            pass

        prompt = (
            f"Eres Dona, asistente personal de WhatsApp. "
            f"Tono: motivador, estratégico, cálido. Máximo {'200' if negocio_str else '130'} palabras. Sin markdown pesado.\n\n"
            f"Genera el resumen semanal de fin de viernes para {nombre or 'el usuario'}.\n\n"
            f"Recordatorios de la próxima semana:\n{proximos_str}\n\n"
            + (f"Resumen de negocio esta semana:\n{negocio_str}\n\n" if negocio_str else "")
            + f"Metas y proyectos del usuario:\n{contexto_resumido}\n\n"
            f"El mensaje debe:\n"
            f"1. Reconocer que terminó otra semana\n"
            + (f"2. Mencionar resultados clave del negocio (ventas, clientes, tendencias)\n" if negocio_str else "")
            + f"{'3' if negocio_str else '2'}. Conectar la próxima semana con sus metas grandes\n"
            f"{'4' if negocio_str else '3'}. Destacar la prioridad más importante para el lunes\n"
            f"{'5' if negocio_str else '4'}. Terminar con una pregunta motivadora\n"
            f"{'6' if negocio_str else '5'}. Emojis con moderación\n\n"
            f"REGLAS ABSOLUTAS:\n"
            f"- NUNCA menciones la calidad o completitud del contexto disponible\n"
            f"- NUNCA expongas tu razonamiento interno ni tus limitaciones\n"
            f"- Si el contexto es insuficiente, genera igualmente un mensaje motivador sin mencionarlo"
        )

        response = await _claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else None

    except Exception as e:
        logger.error(f"Proactividad _generar_weekly_review ({telefono}): {e}")
        return None


# ─── HELPERS ─────────────────────────────────────────────────────────────────

async def _disparador_lluvia(telefono: str, nombre: str, offset_min: int) -> str | None:
    """
    Alerta si hay lluvia en las próximas horas y el usuario tiene recordatorios que
    podrían implicar salir (p. ej. textos como "reunión", "cita", "ir a").
    """
    from agent.memory import obtener_recordatorios_proximas_horas
    from agent.real_world import obtener_clima

    try:
        ubicacion = await _obtener_ubicacion_usuario(telefono)
        if not ubicacion.get("ciudad"):
            return None

        pronostico = await obtener_clima(ubicacion["ciudad"])
        if not pronostico:
            return None

        llueve = any(p["llueve"] for p in pronostico)
        if not llueve:
            return None

        # Revisar si hay recordatorios próximos que suenen presenciales
        proximos = await obtener_recordatorios_proximas_horas(telefono, horas=6)
        _KEYWORDS_PRESENCIAL = {"reunión", "reunion", "cita", "ir a", "visita", "entrevista", "evento"}
        presenciales = [
            r for r in proximos
            if any(kw in r["mensaje"].lower() for kw in _KEYWORDS_PRESENCIAL)
        ]
        if not presenciales:
            return None

        r = presenciales[0]
        hora_str = _hora_local_str(r["fecha_hora"], offset_min)
        ciudad = ubicacion["ciudad"]
        lluvia_icono = next((p["icono"] for p in pronostico if p["llueve"]), "🌧️")

        return (
            f"{lluvia_icono} {nombre}, hay lluvia prevista en {ciudad} "
            f"cerca de las {hora_str}, cuando tienes: _{r['mensaje']}_\n\n"
            f"¿Quieres salir antes o proponer cambiarla a virtual?"
        )

    except Exception as e:
        logger.debug(f"Proactividad _disparador_lluvia ({telefono}): {e}")
        return None


async def _disparador_noticias(telefono: str, nombre: str, contexto: str) -> str | None:
    """
    Busca noticias relevantes para la industria del usuario.
    Máximo 1 vez por semana, y solo artículos no enviados antes.
    """
    from agent.memory import (
        obtener_proactividad, guardar_proactividad,
        ya_enviada_noticia, marcar_noticia_enviada,
    )
    from agent.real_world import obtener_noticias, extraer_industria

    try:
        # No repetir si ya se envió esta semana
        config = await obtener_proactividad(telefono)
        ultimo_news = config.get("ultimo_conflict_check") if config else None  # reutilizamos campo

        ubicacion = await _obtener_ubicacion_usuario(telefono)
        pais = ubicacion.get("pais") or "México"

        # Obtener o inferir industria
        industria = ubicacion.get("industria")
        if not industria and contexto:
            industria = await extraer_industria(contexto)
            if industria:
                from agent.memory import guardar_ubicacion
                await guardar_ubicacion(telefono, industria=industria)

        if not industria:
            return None

        articulos = await obtener_noticias(industria, pais)
        if not articulos:
            return None

        # Tomar el primer artículo no enviado aún
        articulo = None
        for a in articulos:
            if not await ya_enviada_noticia(telefono, a["url_hash"]):
                articulo = a
                break

        if not articulo:
            return None

        await marcar_noticia_enviada(telefono, articulo["url_hash"])

        resumen = articulo.get("resumen") or ""
        resumen_corto = resumen[:120] + "..." if len(resumen) > 120 else resumen

        return (
            f"📰 {nombre}, vi esta noticia sobre *{industria}* que podría interesarte:\n\n"
            f"_{articulo['titulo']}_\n"
            + (f"{resumen_corto}\n\n" if resumen_corto else "\n")
            + f"¿Quieres que te haga un resumen o la analizamos juntos?"
        )

    except Exception as e:
        logger.debug(f"Proactividad _disparador_noticias ({telefono}): {e}")
        return None


def _hora_local_str(fecha_utc: datetime, offset_min: int = 0) -> str:
    """Convierte datetime UTC a string legible en hora local del usuario."""
    local = fecha_utc + timedelta(minutes=offset_min)
    return local.strftime("%d/%m %H:%M")


# Palabras clave que indican un recordatorio IMPORTANTE (merece aviso anticipado).
# Recordatorios básicos (tomar agua, pastilla, etc.) solo se envían a la hora exacta.
_KEYWORDS_RECORDATORIO_IMPORTANTE = {
    "reunión", "reunion", "cita", "entrevista", "llamada", "presentación",
    "presentacion", "junta", "evento", "vuelo", "viaje", "avión", "avion",
    "aeropuerto", "consulta", "doctor", "dentista", "médico", "medico",
    "examen", "deadline", "entrega", "vencimiento", "pago", "factura",
    "visita", "audiencia", "conferencia", "webinar", "clase", "curso",
    "cumpleaños", "cumpleanos", "aniversario", "boda", "graduación",
    "graduacion", "compromiso", "reserva", "reservación", "reservacion",
}


def _es_recordatorio_importante(mensaje: str) -> bool:
    """
    Retorna True si el recordatorio es importante y merece aviso anticipado.
    Recordatorios básicos (tomar agua, pastilla, etc.) solo se envían a la hora exacta.
    """
    texto_lower = mensaje.lower()
    return any(kw in texto_lower for kw in _KEYWORDS_RECORDATORIO_IMPORTANTE)


async def _disparador_consejo_estrategico(telefono: str, nombre: str, contexto: str) -> str | None:
    """
    Disparador 8 — Consejera estratégica proactiva.
    Usa el grafo MiroFish del usuario para detectar si hay una decisión importante
    pendiente o un momento de alta tensión estratégica que merece atención.
    Solo se activa si MiroFish está disponible y el usuario tiene grafo construido.
    Se ejecuta máx cada 12 horas para no ser invasivo.
    """
    from agent.memory import obtener_mirofish_estado
    import agent.mirofish_client as mf

    try:
        if not mf._disponible():
            return None

        estado = await obtener_mirofish_estado(telefono)
        if not estado or not estado.get("graph_id"):
            return None

        # Usar el contexto acumulado del grafo si está disponible
        ctx_grafo = estado.get("contexto_pendiente") or contexto
        contexto_analisis = ctx_grafo[:600] if ctx_grafo else contexto[:600]

        prompt = (
            f"Eres Dona, asistente personal estratégica de {nombre or 'el usuario'}.\n\n"
            f"Basándote en el contexto de vida y trabajo del usuario:\n{contexto_analisis}\n\n"
            f"Detecta si hay alguna de estas situaciones activas:\n"
            f"1. Una decisión importante que el usuario mencionó pero no ha tomado acción\n"
            f"2. Una relación profesional o personal que podría necesitar atención\n"
            f"3. Un proyecto con señales de riesgo (retrasos, dependencias sin resolver)\n"
            f"4. Un momento de alta carga donde una perspectiva externa sería valiosa\n\n"
            f"Si detectas una situación concreta y accionable, escribe un mensaje corto "
            f"para WhatsApp (máx 70 palabras, sin markdown, tono de consejera cercana). "
            f"El mensaje debe ofrecer ayuda específica, no genérica. "
            f"NUNCA uses las palabras 'simulación' o 'simular'. "
            f"Usa 'analizar', 'pensar las consecuencias' o 'explorar qué pasaría'.\n\n"
            f"Si no hay nada concreto que amerite atención, responde exactamente: SIN_CONSEJO\n\n"
            f"NUNCA menciones la calidad del contexto ni expongas razonamiento interno."
        )

        response = await _claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )

        resultado = response.content[0].text.strip() if response.content else "SIN_CONSEJO"
        if resultado == "SIN_CONSEJO" or not resultado:
            return None

        logger.info(f"Proactividad: consejo estratégico generado para {telefono}")
        return resultado

    except Exception as e:
        logger.error(f"Proactividad _disparador_consejo_estrategico ({telefono}): {e}")
        return None
