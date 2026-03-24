# agent/brain.py — Cerebro de Dona: conexión con Claude API
# Generado por AgentKit

"""
Lógica de IA de Dona. Lee el system prompt de prompts.yaml,
genera respuestas con Claude y maneja tool use para recordatorios.
"""

import os
import json
import yaml
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Cliente de Anthropic
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Herramientas que Claude puede llamar
TOOLS = [
    {
        "name": "guardar_zona_horaria",
        "description": (
            "Guarda el offset de zona horaria del usuario cuando puedes inferirlo. "
            "Úsala cuando el usuario mencione la hora actual explícitamente "
            "(ej: 'son las 3pm', 'ya son las 9 de la mañana', 'son las 20:00'). "
            "Compara esa hora local con el timestamp UTC del mensaje para calcular el offset. "
            "Ejemplo: usuario dice 'son las 3pm' y el timestamp es 19:00 UTC → offset = -240 minutos (UTC-4). "
            "Llama esta herramienta ANTES de crear el recordatorio si detectas la hora actual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "offset_minutos": {
                    "type": "integer",
                    "description": (
                        "Diferencia en minutos entre la hora local del usuario y UTC. "
                        "Negativo para zonas al oeste de UTC (Américas). "
                        "Ejemplo: UTC-4 = -240, UTC-5 = -300, UTC+1 = 60"
                    )
                }
            },
            "required": ["offset_minutos"]
        }
    },
    {
        "name": "crear_recordatorio",
        "description": (
            "Guarda un recordatorio para enviarlo automáticamente al usuario "
            "en una fecha y hora específica via WhatsApp. "
            "Úsala SIEMPRE que el usuario pida que le recuerdes algo en un momento futuro. "
            "Para recordatorios recurrentes, incluye el campo 'recurrencia'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mensaje_recordatorio": {
                    "type": "string",
                    "description": "Texto del recordatorio que recibirá el usuario. Sé claro y específico."
                },
                "fecha_hora_utc": {
                    "type": "string",
                    "description": (
                        "Fecha y hora en formato ISO 8601 UTC de la PRIMERA (o única) ocurrencia. "
                        "Usa el offset de zona horaria del usuario para convertir hora local a UTC. "
                        "Ejemplo: '2026-03-20T19:00:00'"
                    )
                },
                "recurrencia": {
                    "type": "object",
                    "description": (
                        "Solo para recordatorios que se repiten. Omitir si es único. "
                        "Ejemplos: "
                        "{\"tipo\": \"diario\"} — todos los días a la misma hora. "
                        "{\"tipo\": \"semanal\", \"dia\": 0} — cada lunes (0=lun,1=mar,...,6=dom). "
                        "{\"tipo\": \"dias_semana\"} — lunes a viernes a la misma hora. "
                        "{\"tipo\": \"mensual\", \"dia\": 15} — el día 15 de cada mes."
                    )
                },
                "fecha_fin_utc": {
                    "type": "string",
                    "description": (
                        "Solo para recurrentes: fecha límite en ISO 8601 UTC. "
                        "Después de esta fecha se deja de enviar. Omitir si no tiene fin."
                    )
                }
            },
            "required": ["mensaje_recordatorio", "fecha_hora_utc"]
        }
    },
    {
        "name": "listar_recordatorios",
        "description": (
            "Muestra al usuario la lista de sus recordatorios activos y futuros. "
            "Úsala cuando el usuario pregunte por sus recordatorios, "
            "qué recordatorios tiene, o quiere ver su lista."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "simular_escenario",
        "description": (
            "Analiza cómo distintas personas o entidades en la vida del usuario reaccionarían "
            "ante un escenario hipotético. Úsala cuando el usuario pregunta '¿qué pasaría si...?', "
            "'simula que...', 'cómo reaccionaría X si...', o pide predecir consecuencias sociales "
            "de una decisión. El análisis toma 1-2 minutos y el resultado llega por este chat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "escenario": {
                    "type": "string",
                    "description": (
                        "Descripción detallada del escenario a simular en lenguaje natural. "
                        "Incluye el contexto y las personas/organizaciones relevantes si las conoces. "
                        "Ejemplo: '¿Qué pasaría si cancelo el contrato con Carlos y le digo "
                        "que el proyecto se retrasó por problemas técnicos?'"
                    )
                }
            },
            "required": ["escenario"]
        }
    },
    {
        "name": "cancelar_recordatorio",
        "description": (
            "Cancela uno o más recordatorios del usuario. "
            "Úsala cuando el usuario quiera borrar, eliminar o cancelar un recordatorio. "
            "Busca coincidencias en el texto del recordatorio con las palabras clave."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "palabras_clave": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Palabras o frases del mensaje del recordatorio a cancelar. "
                        "Ejemplo: ['reunión', 'junta'] cancela recordatorios que contengan "
                        "'reunión' o 'junta'. Al menos una palabra clave."
                    )
                }
            },
            "required": ["palabras_clave"]
        }
    }
]


def cargar_config_prompts() -> dict:
    """Lee toda la configuración desde config/prompts.yaml."""
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def construir_contexto_tiempo(timestamp_mensaje: int = 0, offset_guardado: int | None = None) -> str:
    """
    Construye el contexto de fecha/hora para Claude.

    - Tiempos RELATIVOS: suma al timestamp UTC del mensaje → siempre correcto sin zona horaria
    - Tiempos ABSOLUTOS: usa el offset guardado del usuario (inferido previamente)
      o el USER_TIMEZONE como fallback inicial
    """
    # Whapi envía segundos Unix. Si llega en milisegundos (>1e11), convertir.
    ts = timestamp_mensaje or 0
    if ts > 1_000_000_000_000:   # milisegundos → segundos
        ts = ts // 1000

    ref_utc = (datetime.fromtimestamp(ts, tz=timezone.utc)
               if ts > 0
               else datetime.now(timezone.utc))

    # Determinar offset: primero el guardado por usuario, luego la env var
    if offset_guardado is not None:
        offset_seg = offset_guardado * 60
        offset_horas = offset_guardado // 60
        ref_local = ref_utc + timedelta(seconds=offset_seg)
        origen_tz = f"UTC{offset_horas:+d}"
    else:
        tz_nombre = os.getenv("USER_TIMEZONE", "America/New_York")
        tz_usuario = ZoneInfo(tz_nombre)
        ref_local = ref_utc.astimezone(tz_usuario)
        offset_seg = ref_local.utcoffset().total_seconds()
        offset_horas = int(offset_seg / 3600)
        origen_tz = f"{tz_nombre} (default)"

    offset_str = f"UTC{offset_horas:+d}"
    dia_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    hoy = dia_semana[ref_local.weekday()]
    hora_local_str = ref_local.strftime("%I:%M %p").lstrip("0")   # "7:37 PM"
    fecha_local_str = ref_local.strftime("%Y-%m-%d")
    manana = ref_local + timedelta(days=1)
    pasado = ref_local + timedelta(days=2)
    en_10min = ref_utc + timedelta(minutes=10)
    en_1h = ref_utc + timedelta(hours=1)
    en_2h = ref_utc + timedelta(hours=2)

    tz_status = ("✓ zona horaria conocida" if offset_guardado is not None
                 else "⚠ zona horaria estimada — si el usuario menciona la hora actual, llama `guardar_zona_horaria`")

    return (
        # ── Instrucción autoritativa de hora — DEBE ir primero ─────────────────
        f"## ⚠️ HORA ACTUAL DEL USUARIO\n"
        f"**{hora_local_str} ({hoy} {fecha_local_str}, {offset_str})**\n"
        f"INSTRUCCIÓN CRÍTICA: Si el usuario pregunta qué hora es, responde EXACTAMENTE "
        f"con **{hora_local_str}**. "
        f"NUNCA uses horas mencionadas en el historial — esas son horas pasadas. "
        f"La única hora válida y actual es la de este system prompt.\n\n"
        # ── Referencia técnica ──────────────────────────────────────────────────
        f"## Referencia de tiempo\n"
        f"- Timestamp UTC: {ref_utc.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"- Hora local: {ref_local.strftime('%Y-%m-%d %H:%M')} ({origen_tz})\n"
        f"- Estado zona horaria: {tz_status}\n"
        f"- Mañana: {manana.strftime('%Y-%m-%d')} ({dia_semana[manana.weekday()]})\n"
        f"- Pasado mañana: {pasado.strftime('%Y-%m-%d')} ({dia_semana[pasado.weekday()]})\n\n"
        f"## Cálculo de recordatorios\n"
        f"TIEMPOS RELATIVOS (no necesitan zona horaria):\n"
        f"- 'en 10 minutos' → {en_10min.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"- 'en 1 hora'     → {en_1h.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"- 'en 2 horas'    → {en_2h.strftime('%Y-%m-%dT%H:%M:%S')}\n\n"
        f"TIEMPOS ABSOLUTOS (offset {offset_str}, resta {-offset_horas}h a la hora local):\n"
        f"- '3pm hoy'    → {(ref_local.replace(hour=15, minute=0, second=0) - timedelta(seconds=offset_seg)).strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"- '9am mañana' → {(manana.replace(hour=9, minute=0, second=0) - timedelta(seconds=offset_seg)).strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"- '8pm hoy'    → {(ref_local.replace(hour=20, minute=0, second=0) - timedelta(seconds=offset_seg)).strftime('%Y-%m-%dT%H:%M:%S')}\n\n"
        f"SIEMPRE: fecha_hora_utc en ISO 8601 sin timezone. "
        f"Llama `crear_recordatorio` para cualquier recordatorio."
    )


def cargar_system_prompt(
    timestamp_mensaje: int = 0,
    offset_guardado: int | None = None,
    tono_emocional: str = "",
    contexto_emocional: str = "",
    perfil_aprendizaje: str = "",
    memoria_largo_plazo: str = "",
) -> str:
    """Lee el system prompt e inyecta contexto de tiempo, memoria histórica, estado emocional y perfil de aprendizaje."""
    config = cargar_config_prompts()
    base = config.get("system_prompt", "Eres Dona, una asistente personal útil. Responde en español.")
    partes = [base, construir_contexto_tiempo(timestamp_mensaje, offset_guardado)]
    if memoria_largo_plazo and memoria_largo_plazo != "Sin contexto acumulado aún.":
        partes.append(
            f"## Memoria histórica del usuario\n"
            f"{memoria_largo_plazo}\n"
            f"Usa este contexto para personalizar tus respuestas y recordar hechos importantes. "
            f"Nunca menciones que tienes un 'resumen' o 'memoria' — úsalo de forma natural."
        )
    if perfil_aprendizaje:
        partes.append(
            f"## Perfil de aprendizaje (comportamiento real observado)\n"
            f"{perfil_aprendizaje}\n"
            f"Usa este perfil para personalizar horarios, tipo de sugerencias y tono. "
            f"Nunca menciones que estás 'aprendiendo' o 'analizando' al usuario — hazlo de forma natural."
        )
    if tono_emocional:
        partes.append(f"## Tono para este mensaje\n{tono_emocional}")
    if contexto_emocional:
        partes.append(contexto_emocional)
    return "\n\n".join(partes)


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Ups, algo salió mal de mi lado 🙁 Intenta de nuevo en un momento.")


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Hmm, no entendí bien eso 😅 ¿Me lo puedes decir de otra forma?")


async def generar_respuesta(mensaje: str, historial: list[dict], telefono: str = "", timestamp_mensaje: int = 0, proveedor=None) -> str:
    """
    Genera una respuesta usando Claude API.
    Si Claude detecta un recordatorio, llama la herramienta crear_recordatorio
    y guarda el recordatorio en la base de datos.

    Args:
        mensaje: El mensaje nuevo del usuario
        historial: Lista de mensajes anteriores
        telefono: Número del usuario (necesario para guardar recordatorios)

    Returns:
        La respuesta de texto de Dona
    """
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    # ── Detección emocional (paralela con carga de timezone) ─────────────────
    from agent.memory import (
        obtener_timezone, obtener_onboarding, obtener_estado_emocional,
        obtener_perfil_aprendizaje, obtener_memoria_largo_plazo,
    )
    from agent.emotion import (
        detectar_emocion, obtener_instrucciones_tono,
        obtener_contexto_emocional_str, MENSAJE_CRISIS,
    )

    async def _none():
        return None

    offset_guardado, estado_onboarding, perfil_aprendizaje, memoria_lp = await asyncio.gather(
        obtener_timezone(telefono) if telefono else _none(),
        obtener_onboarding(telefono) if telefono else _none(),
        obtener_perfil_aprendizaje(telefono) if telefono else _none(),
        obtener_memoria_largo_plazo(telefono) if telefono else _none(),
    )

    resumen_memoria = memoria_lp["resumen_texto"] if memoria_lp else ""

    contexto_usuario = estado_onboarding.get("contexto", "") if estado_onboarding else ""
    nombre_usuario = estado_onboarding.get("nombre", "") if estado_onboarding else ""

    # Detectar emoción (rápido, usa Haiku; falla silenciosamente)
    emotion = await detectar_emocion(mensaje, contexto_usuario)

    # Crisis: respuesta inmediata sin pasar por el flujo normal
    if emotion.get("state") == "crisis":
        return MENSAJE_CRISIS

    # Guardar estado emocional en background
    if telefono:
        asyncio.create_task(
            _guardar_emocion_background(telefono, emotion)
        )

    # Construir instrucciones de tono emocional
    tono_emocional = obtener_instrucciones_tono(emotion, nombre_usuario)

    # Contexto emocional reciente (si aplica)
    estado_previo = await obtener_estado_emocional(telefono) if telefono else None
    ctx_emocional = ""
    if estado_previo:
        ctx_emocional = obtener_contexto_emocional_str(
            estado_previo["estado"],
            estado_previo["intensidad"],
            estado_previo["actualizado"],
        )

    system_prompt = cargar_system_prompt(
        timestamp_mensaje, offset_guardado,
        tono_emocional=tono_emocional,
        contexto_emocional=ctx_emocional,
        perfil_aprendizaje=perfil_aprendizaje or "",
        memoria_largo_plazo=resumen_memoria,
    )

    # Construir lista de mensajes (historial + mensaje actual)
    mensajes = [{"role": m["role"], "content": m["content"]} for m in historial]
    mensajes.append({"role": "user", "content": mensaje})

    try:
        # Primera llamada a Claude — puede responder con texto o con tool_use
        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes,
            tools=TOOLS
        )

        logger.info(f"Claude respuesta ({response.usage.input_tokens} in / {response.usage.output_tokens} out) stop={response.stop_reason}")

        # Si Claude quiere usar una herramienta
        if response.stop_reason == "tool_use":
            return await _manejar_tool_use(response, mensajes, system_prompt, telefono, offset_guardado, proveedor)

        # Respuesta de texto normal
        return _extraer_texto(response)

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()


async def _manejar_tool_use(response, mensajes: list, system_prompt: str, telefono: str, offset_guardado: int | None, proveedor=None) -> str:
    """
    Ejecuta las herramientas que Claude solicitó y obtiene la respuesta final.
    Soporta: guardar_zona_horaria, crear_recordatorio, listar_recordatorios,
             cancelar_recordatorio, simular_escenario.
    """
    from agent.memory import (
        guardar_recordatorio, guardar_timezone,
        obtener_recordatorios_activos, cancelar_recordatorios_por_keyword,
        obtener_mirofish_estado,
    )

    resultados_herramientas = []

    for bloque in response.content:
        if bloque.type != "tool_use":
            continue

        # ── guardar_zona_horaria ──────────────────────────────────────
        if bloque.name == "guardar_zona_horaria":
            try:
                offset_min = int(bloque.input["offset_minutos"])
                await guardar_timezone(telefono, offset_min)
                offset_h = offset_min // 60
                resultado = f"Zona horaria guardada: UTC{offset_h:+d}"
                logger.info(f"Zona horaria inferida para {telefono}: UTC{offset_h:+d}")
            except Exception as e:
                resultado = f"Error guardando zona horaria: {e}"
                logger.error(f"Error guardando timezone: {e}")
            resultados_herramientas.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": resultado
            })

        # ── crear_recordatorio ────────────────────────────────────────
        elif bloque.name == "crear_recordatorio":
            try:
                fecha_hora_str = bloque.input["fecha_hora_utc"]
                fecha_hora = datetime.fromisoformat(fecha_hora_str.replace("Z", ""))
                mensaje_recordatorio = bloque.input["mensaje_recordatorio"]

                # Recurrencia (opcional)
                recurrencia = bloque.input.get("recurrencia") or None

                # Fecha fin (opcional)
                fecha_fin = None
                fecha_fin_str = bloque.input.get("fecha_fin_utc")
                if fecha_fin_str:
                    fecha_fin = datetime.fromisoformat(fecha_fin_str.replace("Z", ""))

                # Guardar offset actual del usuario para que el scheduler pueda recalcular
                offset_snap = offset_guardado

                recordatorio = await guardar_recordatorio(
                    telefono=telefono,
                    mensaje=mensaje_recordatorio,
                    fecha_hora=fecha_hora,
                    recurrencia=recurrencia,
                    offset_tz_minutos=offset_snap,
                    fecha_fin=fecha_fin,
                )

                tipo_str = "recurrente" if recurrencia else "único"
                resultado = (
                    f"Recordatorio {tipo_str} guardado. ID: {recordatorio.id}. "
                    f"Primera ocurrencia: {fecha_hora.strftime('%Y-%m-%d %H:%M')} UTC."
                )
                logger.info(f"Recordatorio #{recordatorio.id} ({tipo_str}) guardado para {telefono} — {fecha_hora}")

            except Exception as e:
                resultado = f"Error al guardar el recordatorio: {e}"
                logger.error(f"Error guardando recordatorio: {e}")

            resultados_herramientas.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": resultado
            })

        # ── listar_recordatorios ──────────────────────────────────────
        elif bloque.name == "listar_recordatorios":
            try:
                activos = await obtener_recordatorios_activos(telefono)
                if not activos:
                    resultado = "El usuario no tiene recordatorios activos."
                else:
                    lineas = []
                    for r in activos:
                        fh = r["fecha_hora"]
                        # Convertir UTC a local si tenemos offset
                        if offset_guardado is not None:
                            fh_local = fh + timedelta(minutes=offset_guardado)
                            fh_str = fh_local.strftime("%d/%m %H:%M")
                        else:
                            fh_str = fh.strftime("%d/%m %H:%M") + " UTC"
                        tipo = r["tipo_str"]
                        fin_str = ""
                        if r["fecha_fin"]:
                            fin_str = f" (hasta {r['fecha_fin'].strftime('%d/%m/%Y')})"
                        lineas.append(f"- ID {r['id']}: \"{r['mensaje']}\" — {tipo} a las {fh_str}{fin_str}")
                    resultado = "Recordatorios activos del usuario:\n" + "\n".join(lineas)
                logger.info(f"Recordatorios listados para {telefono}: {len(activos)} activos")
            except Exception as e:
                resultado = f"Error listando recordatorios: {e}"
                logger.error(f"Error listando recordatorios: {e}")

            resultados_herramientas.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": resultado
            })

        # ── cancelar_recordatorio ─────────────────────────────────────
        elif bloque.name == "cancelar_recordatorio":
            try:
                palabras = bloque.input.get("palabras_clave", [])
                cancelados = await cancelar_recordatorios_por_keyword(telefono, palabras)
                if cancelados:
                    resultado = f"Cancelados {len(cancelados)} recordatorio(s). IDs: {cancelados}"
                else:
                    resultado = "No se encontraron recordatorios activos que coincidan con esas palabras."
                logger.info(f"Cancelar recordatorio para {telefono} con palabras {palabras}: {cancelados}")
            except Exception as e:
                resultado = f"Error cancelando recordatorio: {e}"
                logger.error(f"Error cancelando recordatorio: {e}")

            resultados_herramientas.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": resultado
            })

        # ── simular_escenario ─────────────────────────────────────────
        elif bloque.name == "simular_escenario":
            try:
                import agent.mirofish_client as mf
                if not mf._disponible():
                    resultado = (
                        "La función de simulación no está disponible en este momento "
                        "(MIROFISH_BASE_URL no configurado)."
                    )
                else:
                    estado = await obtener_mirofish_estado(telefono)
                    project_id = estado.get("project_id") if estado else None
                    graph_id = estado.get("graph_id") if estado else None

                    if not project_id or not graph_id:
                        resultado = (
                            "Aún no tengo suficiente contexto sobre tu vida para simular escenarios. "
                            "Sigue usando Dona con mensajes sobre tu trabajo, personas y proyectos. "
                            "En unos días podré hacer simulaciones para ti."
                        )
                    else:
                        escenario = bloque.input["escenario"]
                        # Arrancar simulación en background — resultado llega por WhatsApp
                        asyncio.create_task(
                            _ejecutar_simulacion_background(
                                telefono=telefono,
                                project_id=project_id,
                                graph_id=graph_id,
                                escenario=escenario,
                                proveedor=proveedor,
                            )
                        )
                        resultado = "Simulación iniciada. El análisis toma 1-2 minutos — el resultado llega por este chat."
                        logger.info(f"Simulación MiroFish iniciada en background para {telefono}")
            except Exception as e:
                resultado = f"Error al iniciar la simulación: {e}"
                logger.error(f"Error simular_escenario: {e}")

            resultados_herramientas.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": resultado
            })

    # Siguiente llamada a Claude con los resultados de las herramientas
    mensajes_con_tool = mensajes + [
        {"role": "assistant", "content": response.content},
        {"role": "user", "content": resultados_herramientas}
    ]

    respuesta_final = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=system_prompt,
        messages=mensajes_con_tool,
        tools=TOOLS
    )

    # Claude puede encadenar tool calls (ej: guardar_zona_horaria → crear_recordatorio).
    # Si la respuesta siguiente es también tool_use, procesarla recursivamente.
    if respuesta_final.stop_reason == "tool_use":
        return await _manejar_tool_use(
            respuesta_final, mensajes_con_tool, system_prompt,
            telefono, offset_guardado, proveedor
        )

    return _extraer_texto(respuesta_final)


async def _guardar_emocion_background(telefono: str, emotion: dict):
    """Guarda el estado emocional en background sin bloquear la respuesta."""
    from agent.memory import guardar_estado_emocional
    try:
        await guardar_estado_emocional(
            telefono,
            emotion.get("state", "neutral"),
            emotion.get("intensity", 1),
        )
    except Exception as e:
        logger.debug(f"Error guardando emoción: {e}")


async def _ejecutar_simulacion_background(
    telefono: str, project_id: str, graph_id: str, escenario: str, proveedor
):
    """
    Corre el pipeline completo de simulación MiroFish y envía el resultado por WhatsApp.
    Diseñada para ejecutarse como asyncio.create_task (fire and forget).
    """
    import agent.mirofish_client as mf

    try:
        logger.info(f"MiroFish background: iniciando simulación para {telefono}")
        reporte = await mf.pipeline_simulacion(project_id, graph_id, escenario)

        if reporte and proveedor:
            # WhatsApp tiene límite práctico ~4000 chars por mensaje
            if len(reporte) > 3800:
                reporte = reporte[:3800] + "\n\n_(reporte truncado por límite de WhatsApp)_"
            mensaje_resultado = f"*Análisis de escenario completado:*\n\n{reporte}"
            await proveedor.enviar_mensaje(telefono, mensaje_resultado)
            logger.info(f"MiroFish background: resultado enviado a {telefono}")
        elif proveedor:
            await proveedor.enviar_mensaje(
                telefono,
                "No pude completar el análisis del escenario. Por favor intenta de nuevo."
            )
    except Exception as e:
        logger.error(f"MiroFish background error para {telefono}: {e}")
        if proveedor:
            try:
                await proveedor.enviar_mensaje(
                    telefono,
                    "Hubo un error al analizar el escenario. Intenta de nuevo más tarde."
                )
            except Exception:
                pass


def _extraer_texto(response) -> str:
    """Extrae el texto de la respuesta de Claude."""
    for bloque in response.content:
        if hasattr(bloque, "text"):
            return bloque.text
    return obtener_mensaje_fallback()
