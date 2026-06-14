# agent/learning.py — Motor de aprendizaje continuo de Dona
# Dona

"""
Dona aprende de cada interacción y ajusta su comportamiento con el tiempo.

Flujo:
  1. registrar_interaccion() — se llama en background en cada mensaje del usuario
  2. analizar_patrones() — se ejecuta semanalmente (domingo 23:00 UTC)
  3. El perfil generado se inyecta en el system prompt de Dona

Los 4 patrones que aprende:
  - Horas de mayor actividad (cuándo escribe más el usuario)
  - Días de mayor estrés (basado en estados emocionales)
  - Tipos de eventos frecuentes (recordatorios creados, proactividad ignorada)
  - Preferencia de brevedad (longitud promedio de sus mensajes)

Mínimo 20 eventos para activar el análisis.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("dona")

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

MIN_EVENTOS = 20   # Mínimo de eventos para que el análisis sea significativo


# ─── TRACKER ─────────────────────────────────────────────────────────────────

async def registrar_interaccion(telefono: str, tipo: str, metadata: dict | None = None, offset_min: int = 0):
    """
    Registra silenciosamente una interacción del usuario.
    Convierte la hora UTC a hora local usando el offset del usuario.

    Tipos válidos:
      "message_sent"       — el usuario envió un mensaje
      "reminder_created"   — se creó un recordatorio
      "reminder_cancelled" — se canceló un recordatorio
      "proactive_sent"     — Dona envió un mensaje proactivo
      "proactive_engaged"  — el usuario respondió a un proactivo
    """
    from agent.memory import guardar_evento_comportamiento

    ahora_utc = datetime.utcnow()
    ahora_local = ahora_utc + timedelta(minutes=offset_min)

    try:
        await guardar_evento_comportamiento(
            telefono=telefono,
            tipo=tipo,
            hora_dia=ahora_local.hour,
            dia_semana=ahora_local.weekday(),
            metadata=metadata or {},
        )
    except Exception as e:
        logger.debug(f"learning.registrar_interaccion ({telefono}): {e}")


# ─── ANALIZADOR DE PATRONES ───────────────────────────────────────────────────

async def analizar_patrones(telefono: str) -> str | None:
    """
    Analiza los eventos de comportamiento de los últimos 30 días y genera
    un perfil de aprendizaje en lenguaje natural.

    Retorna el perfil como texto listo para inyectar en el system prompt,
    o None si no hay suficientes datos.
    """
    from sqlalchemy import select

    from agent.memory import (
        EventoEmocional,
        async_session,
        contar_eventos_comportamiento,
        guardar_perfil_aprendizaje,
        obtener_eventos_comportamiento,
    )

    total = await contar_eventos_comportamiento(telefono, dias=30)
    if total < MIN_EVENTOS:
        logger.debug(f"learning: {telefono} solo tiene {total} eventos (mínimo {MIN_EVENTOS})")
        return None

    eventos = await obtener_eventos_comportamiento(telefono, dias=30)

    # ── Patrón 1: Horas de mayor actividad ───────────────────────────────────
    horas_actividad = [e["hora_dia"] for e in eventos if e["tipo"] == "message_sent"]
    horas_pico = []
    if horas_actividad:
        conteo_horas = Counter(horas_actividad)
        horas_pico = [f"{h}:00" for h, _ in conteo_horas.most_common(3)]

    # ── Patrón 2: Días de mayor actividad ────────────────────────────────────
    dias_actividad = [e["dia_semana"] for e in eventos if e["tipo"] == "message_sent"]
    dias_pico = []
    if dias_actividad:
        conteo_dias = Counter(dias_actividad)
        dias_pico = [_DIAS[d] for d, _ in conteo_dias.most_common(2)]

    # ── Patrón 3: Días de mayor estrés (de EventoEmocional) ──────────────────
    dias_estres = []
    try:
        async with async_session() as session:
            desde = datetime.utcnow() - timedelta(days=30)
            q = (
                select(EventoEmocional)
                .where(EventoEmocional.telefono == telefono)
                .where(EventoEmocional.estado.in_(["stress", "exhaustion"]))
                .where(EventoEmocional.intensidad >= 2)
                .where(EventoEmocional.timestamp >= desde)
            )
            result = await session.execute(q)
            for ev in result.scalars().all():
                dias_estres.append(ev.timestamp.weekday())
    except Exception as e:
        logger.debug(f"learning: error leyendo eventos emocionales: {e}")

    dias_estres_nombres = []
    if dias_estres:
        conteo_estres = Counter(dias_estres)
        dias_estres_nombres = [_DIAS[d] for d, _ in conteo_estres.most_common(2)]

    # ── Patrón 4: Preferencia de brevedad (longitud promedio de mensajes) ─────
    longitudes = [e["metadata"].get("longitud", 0) for e in eventos
                  if e["tipo"] == "message_sent" and e["metadata"].get("longitud")]
    avg_longitud = sum(longitudes) / len(longitudes) if longitudes else 0
    prefiere_brevedad = avg_longitud < 60 if longitudes else None

    # ── Patrón 5: Frecuencia de uso de recordatorios ──────────────────────────
    recordatorios_creados = sum(1 for e in eventos if e["tipo"] == "reminder_created")

    # ── Generar perfil con Claude Haiku ──────────────────────────────────────
    datos_crudos = {
        "horas_pico": horas_pico or "sin datos suficientes",
        "dias_mas_activos": dias_pico or "sin datos suficientes",
        "dias_de_estres": dias_estres_nombres or "ninguno detectado",
        "prefiere_respuestas": "cortas" if prefiere_brevedad else ("detalladas" if prefiere_brevedad is False else "sin datos"),
        "recordatorios_creados_30d": recordatorios_creados,
        "total_interacciones_30d": total,
    }

    perfil = await _generar_perfil_texto(datos_crudos)
    if not perfil:
        return None

    await guardar_perfil_aprendizaje(telefono, perfil, eventos_count=total)
    logger.info(f"learning: perfil actualizado para {telefono} ({total} eventos)")
    return perfil


async def _generar_perfil_texto(datos: dict) -> str | None:
    """
    Convierte los patrones crudos en un perfil legible para el system prompt
    usando Claude Haiku (rápido y barato).
    """
    try:
        from agent.llm import completar_texto
        prompt = (
            f"Convierte estos patrones de comportamiento en un perfil de aprendizaje "
            f"conciso para un asistente de IA personal. "
            f"Máximo 120 palabras. Escríbelo como instrucciones para el asistente, "
            f"en segunda persona, en español.\n\n"
            f"Patrones detectados:\n{datos}\n\n"
            f"Ejemplo de formato:\n"
            f"'El usuario es más activo entre las 9:00 y 11:00. "
            f"Los lunes y martes tienen más estrés — reduce la carga proactiva esos días. "
            f"Prefiere respuestas cortas. Usa recordatorios frecuentemente — "
            f"es un buen canal para conectar con él.'"
        )
        return await completar_texto(prompt, max_tokens=200)
    except Exception as e:
        logger.error(f"learning._generar_perfil_texto: {e}")
        return None


# ─── JOB SEMANAL ─────────────────────────────────────────────────────────────

async def actualizar_perfiles_todos():
    """
    Job semanal (domingos 23:00 UTC).
    Actualiza el perfil de aprendizaje de todos los usuarios con onboarding completo
    que tienen al menos 20 eventos de comportamiento en los últimos 30 días.
    """
    from agent.memory import obtener_usuarios_proactividad_activos

    try:
        usuarios = await obtener_usuarios_proactividad_activos()
        if not usuarios:
            return

        logger.info(f"learning: actualizando perfiles de {len(usuarios)} usuario(s)")
        actualizados = 0

        for u in usuarios:
            try:
                perfil = await analizar_patrones(u["telefono"])
                if perfil:
                    actualizados += 1
            except Exception as e:
                logger.error(f"learning: error analizando {u['telefono']}: {e}")

        logger.info(f"learning: {actualizados}/{len(usuarios)} perfiles actualizados")

    except Exception as e:
        logger.error(f"learning.actualizar_perfiles_todos: {e}")
