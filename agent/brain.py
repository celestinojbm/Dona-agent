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
import urllib.parse
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
                    "description": (
                        "Solo el texto del recordatorio, sin ninguna referencia temporal. "
                        "NUNCA incluyas 'en X minutos', 'a las X', 'en 1 hora' ni similar. "
                        "Ejemplos correctos: 'Tomar agua', 'Tomar suplementos', 'Reunión con cliente'. "
                        "La hora ya está definida en fecha_hora_utc."
                    )
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
                        "{\"tipo\": \"cada_hora\"} — cada hora. Usa fecha_fin_utc para limitar duración. "
                        "{\"tipo\": \"cada_30_minutos\"} — cada 30 minutos. "
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
                },
                "aviso_anticipado_minutos": {
                    "type": "integer",
                    "description": (
                        "Minutos antes del recordatorio para enviar un aviso anticipado. "
                        "SOLO para reuniones, citas, entrevistas, eventos que requieren preparación. "
                        "NO usar para hábitos o acciones inmediatas: tomar agua, pastillas, ejercicio, meditar. "
                        "Valor recomendado: 15 o 30. Omitir completamente si no aplica."
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
            "Analiza qué pasaría si el usuario tomara una decisión o enfrentara una situación específica, "
            "considerando cómo reaccionarían las personas y entidades relevantes en su vida. "
            "Úsala cuando el usuario pregunta '¿qué pasaría si...?', '¿cómo reaccionaría X si...?', "
            "'ayúdame a pensar las consecuencias de...', o pide analizar el impacto de una decisión. "
            "El análisis toma 1-2 minutos y el resultado llega por este chat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "escenario": {
                    "type": "string",
                    "description": (
                        "Descripción detallada de la situación o decisión a analizar, en lenguaje natural. "
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
        "name": "conectar_google_calendar",
        "description": (
            "Genera y devuelve el enlace de autorización para que el usuario conecte "
            "su Google Calendar con Dona. "
            "Úsala cuando el usuario pida agendar un evento en su calendario real y "
            "no esté conectado aún, o cuando pida conectar Google Calendar explícitamente. "
            "Presenta el enlace claramente para que el usuario lo abra en su navegador."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "gestionar_calendario",
        "description": (
            "Interactúa con el Google Calendar real del usuario (solo si ya lo autorizó). "
            "Permite listar los eventos de hoy o crear nuevos eventos. "
            "Úsala cuando el usuario pregunte qué tiene hoy, quiera ver su agenda, "
            "o pida agendar algo con fecha y hora concretas. "
            "Si el usuario no está conectado, usa primero conectar_google_calendar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "accion": {
                    "type": "string",
                    "enum": ["listar_hoy", "listar_rango", "crear_evento", "editar_evento", "eliminar_evento"],
                    "description": (
                        "'listar_hoy' → muestra los eventos del día actual. "
                        "'listar_rango' → muestra eventos en un rango de fechas (requiere inicio_iso y fin_iso). "
                        "'crear_evento' → crea un nuevo evento (requiere titulo, inicio_iso, fin_iso). "
                        "'editar_evento' → edita un evento existente (requiere evento_id y los campos a cambiar). "
                        "'eliminar_evento' → elimina un evento (requiere evento_id)."
                    )
                },
                "evento_id": {
                    "type": "string",
                    "description": "ID del evento en Google Calendar. Requerido para editar_evento y eliminar_evento. Obtenerlo de listar_hoy o listar_rango."
                },
                "titulo": {
                    "type": "string",
                    "description": "Título del evento a crear. Solo para accion='crear_evento'."
                },
                "inicio_iso": {
                    "type": "string",
                    "description": (
                        "Fecha y hora de inicio en ISO 8601 con offset de zona horaria. "
                        "Usa el offset del usuario de la sección 'TIEMPOS ABSOLUTOS'. "
                        "Ejemplo: '2026-03-24T15:00:00-04:00'. "
                        "Solo para accion='crear_evento'."
                    )
                },
                "fin_iso": {
                    "type": "string",
                    "description": (
                        "Fecha y hora de fin en ISO 8601 con offset de zona horaria. "
                        "Si el usuario no especifica duración, asume 1 hora después del inicio. "
                        "Ejemplo: '2026-03-24T16:00:00-04:00'. "
                        "Solo para accion='crear_evento'."
                    )
                },
                "descripcion": {
                    "type": "string",
                    "description": "Descripción adicional del evento (opcional)."
                },
                "lugar": {
                    "type": "string",
                    "description": "Ubicación o enlace del evento (opcional)."
                }
            },
            "required": ["accion"]
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
        f"- '8pm hoy'    → {(ref_local.replace(hour=20, minute=0, second=0) - timedelta(seconds=offset_seg)).strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"- '2am hoy'    → {(ref_local.replace(hour=2, minute=0, second=0) - timedelta(seconds=offset_seg)).strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"- '2:50am hoy' → {(ref_local.replace(hour=2, minute=50, second=0) - timedelta(seconds=offset_seg)).strftime('%Y-%m-%dT%H:%M:%S')}\n\n"
        f"NOTA: Si la hora ya pasó hoy, usa la fecha de mañana ({manana.strftime('%Y-%m-%d')}).\n\n"
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
    memoria_vectorial: str = "",
) -> str:
    """Lee el system prompt e inyecta contexto de tiempo, memoria histórica, estado emocional y perfil de aprendizaje."""
    config = cargar_config_prompts()
    base = config.get("system_prompt", "Eres Dona, una asistente personal útil. Responde en español.")
    partes = [base, construir_contexto_tiempo(timestamp_mensaje, offset_guardado)]
    if memoria_vectorial:
        partes.append(
            f"## Recuerdos específicos relevantes para este mensaje\n"
            f"{memoria_vectorial}\n"
            f"Usa estos recuerdos de forma natural en tu respuesta. "
            f"Nunca menciones 'memoria vectorial' ni 'base de datos' — úsalos como si los recordaras."
        )
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


def obtener_mensaje_error(tipo: str = "general") -> str:
    """Retorna un mensaje de error amigable. Acepta un tipo específico de error."""
    config = cargar_config_prompts()
    mensajes = config.get("mensajes_error", {})
    if tipo and tipo in mensajes:
        return mensajes[tipo]
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

    # return_exceptions=True evita que un fallo de DB silencioso apague todas las respuestas.
    # Sin esto, si una tabla nueva no existe en Supabase, la excepción sale de aquí sin capturar,
    # llega al except externo de procesar_webhook, y Dona nunca envía nada al usuario.
    _resultados_db = await asyncio.gather(
        obtener_timezone(telefono) if telefono else _none(),
        obtener_onboarding(telefono) if telefono else _none(),
        obtener_perfil_aprendizaje(telefono) if telefono else _none(),
        obtener_memoria_largo_plazo(telefono) if telefono else _none(),
        return_exceptions=True,
    )

    def _unwrap(r, default=None):
        """Devuelve default si el resultado es una excepción (error de DB no fatal)."""
        return default if isinstance(r, BaseException) else r

    offset_guardado    = _unwrap(_resultados_db[0])
    estado_onboarding  = _unwrap(_resultados_db[1])
    perfil_aprendizaje = _unwrap(_resultados_db[2])
    memoria_lp         = _unwrap(_resultados_db[3])

    # Loguear cualquier error de DB para poder diagnosticarlo sin crashear
    _nombres_db = ["timezone", "onboarding", "perfil_aprendizaje", "memoria_largo_plazo"]
    for _i, _r in enumerate(_resultados_db):
        if isinstance(_r, BaseException):
            logger.error(f"[BRAIN] Error cargando {_nombres_db[_i]} de DB: {type(_r).__name__}: {_r}")

    resumen_memoria = memoria_lp["resumen_texto"] if isinstance(memoria_lp, dict) else ""

    contexto_usuario = estado_onboarding.get("contexto", "") if estado_onboarding else ""
    nombre_usuario = estado_onboarding.get("nombre", "") if estado_onboarding else ""

    # ── Búsqueda vectorial (en paralelo con detección emocional) ─────────────────
    from agent.vector_memory import (
        buscar_memoria_relevante, formatear_memoria_vectorial,
        guardar_en_memoria_vectorial,
    )
    try:
        resultados_vector = await buscar_memoria_relevante(telefono, mensaje) if telefono else []
        ctx_vectorial = await formatear_memoria_vectorial(resultados_vector)
    except Exception as e:
        logger.error(f"[BRAIN] buscar_memoria_relevante falló: {type(e).__name__}: {e}")
        ctx_vectorial = ""

    # Guardar el mensaje del usuario en memoria vectorial (si es relevante)
    if telefono:
        asyncio.create_task(
            guardar_en_memoria_vectorial(telefono, mensaje, tipo="usuario")
        )

    # Detectar emoción (usa Haiku — puede fallar por timeout de API o de red)
    try:
        emotion = await detectar_emocion(mensaje, contexto_usuario)
    except Exception as e:
        logger.error(f"[BRAIN] detectar_emocion falló, continuando sin detección emocional: {type(e).__name__}: {e}")
        emotion = {}

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

    # Contexto emocional reciente (consulta DB — puede fallar con PgBouncer)
    try:
        estado_previo = await obtener_estado_emocional(telefono) if telefono else None
    except Exception as e:
        logger.error(f"[BRAIN] obtener_estado_emocional falló: {type(e).__name__}: {e}")
        estado_previo = None
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
        memoria_vectorial=ctx_vectorial,
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
    # Extraer el último mensaje real del usuario para validaciones
    _ultimo_msg_usuario = ""
    for m in reversed(mensajes):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            _ultimo_msg_usuario = m["content"].lower()
            break
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

           # ── crear_recordatorio ────────────────────────────────────
        elif bloque.name == "crear_recordatorio":
            # Validación anti-fantasma: verificar que el usuario realmente pidió un recordatorio
            _INDICADORES_RECORDATORIO = (
                "recuérdame", "recordarme", "recuerdame", "recordatorio",
                "avísame", "avisame", "agenda", "agéndame", "agendame",
                "anota", "apunta", "pon", "crea", "programa",
                "a las", "mañana", "lunes", "martes", "miércoles", "miercoles",
                "jueves", "viernes", "sábado", "sabado", "domingo",
                "todos los días", "cada día", "cada semana", "cada lunes",
                "en 1 hora", "en 2 horas", "en 30 minutos", "esta tarde",
                "esta noche", "ojo que", "no olvidar", "tengo que",
                "debo", "necesito", "hay que",
            )
            if _ultimo_msg_usuario and not any(ind in _ultimo_msg_usuario for ind in _INDICADORES_RECORDATORIO):
                logger.warning(
                    f"RECORDATORIO BLOQUEADO para {telefono}: Claude intentó crear "
                    f"'{bloque.input.get('mensaje_recordatorio', '?')}' pero el mensaje del usuario "
                    f"no contiene indicadores de recordatorio. Mensaje: '{_ultimo_msg_usuario[:100]}'"
                )
                resultado = (
                    "ERROR: No se creó el recordatorio porque el usuario no lo solicitó explícitamente. "
                    "Solo crea recordatorios cuando el usuario lo pida directamente en su mensaje."
                )
                resultados_herramientas.append({
                    "type": "tool_result",
                    "tool_use_id": bloque.id,
                    "content": resultado
                })
                continue
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

                # ── Aviso anticipado (solo eventos que requieren preparación, no hábitos) ──
                aviso_anticipado_str = ""
                aviso_min = bloque.input.get("aviso_anticipado_minutos")
                if aviso_min and isinstance(aviso_min, int) and aviso_min > 0 and not recurrencia:
                    fecha_aviso = fecha_hora - timedelta(minutes=aviso_min)
                    ahora_utc = datetime.utcnow()
                    if fecha_aviso > ahora_utc:
                        mensaje_aviso = f"⏰ En {aviso_min} minutos: {mensaje_recordatorio}"
                        await guardar_recordatorio(
                            telefono=telefono,
                            mensaje=mensaje_aviso,
                            fecha_hora=fecha_aviso,
                            recurrencia=None,
                            offset_tz_minutos=offset_snap,
                        )
                        aviso_anticipado_str = f" Se enviará un aviso anticipado {aviso_min} minutos antes."
                        logger.info(f"Aviso anticipado guardado para {telefono} — {fecha_aviso} ({aviso_min} min antes)")

                # Calcular hora local para que Claude confirme en formato legible
                if offset_guardado is not None:
                    hora_local = fecha_hora + timedelta(minutes=offset_guardado)
                    hora_local_str = hora_local.strftime('%d/%m/%Y %I:%M %p').lstrip('0')
                else:
                    hora_local_str = fecha_hora.strftime('%d/%m/%Y %H:%M') + " UTC"

                resultado = (
                    f"ÉXITO: Recordatorio {tipo_str} creado correctamente. "
                    f"Mensaje: '{mensaje_recordatorio}'. "
                    f"Hora local del usuario: {hora_local_str}.{aviso_anticipado_str} "
                    f"INSTRUCCIÓN: Confirma al usuario que el recordatorio fue creado. "
                    f"Usa un formato breve y claro como: 'Listo 🔔 Te recuerdo [día] a las [hora] [mensaje]'. "
                    f"NUNCA muestres IDs internos, timestamps UTC ni detalles técnicos."
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

        # ── conectar_google_calendar ──────────────────────────────
        elif bloque.name == "conectar_google_calendar":
            try:
                import agent.google_calendar as gc
                if not gc.esta_disponible():
                    resultado = (
                        "Google Calendar no está configurado en este servidor. "
                        "El administrador debe agregar GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET."
                    )
                else:
                    base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
                    link = (
                        f"{base_url}/auth/google/login"
                        f"?telefono={urllib.parse.quote(telefono)}"
                    )
                    resultado = (
                        f"Enlace de conexión generado: {link}\n"
                        "El usuario debe abrirlo en su navegador para autorizar el acceso."
                    )
                    logger.info(f"[GOOGLE] Enlace OAuth generado para {telefono}")
            except Exception as e:
                resultado = f"Error generando enlace de Google Calendar: {e}"
                logger.error(f"conectar_google_calendar error: {e}")

            resultados_herramientas.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": resultado
            })

        # ── gestionar_calendario ──────────────────────────────────
        elif bloque.name == "gestionar_calendario":
            try:
                import agent.google_calendar as gc
                accion = bloque.input.get("accion", "")

                # Verificar que el usuario tiene Google Calendar conectado
                token = await gc._obtener_token_valido(telefono)
                if not token:
                    resultado = (
                        "El usuario no tiene Google Calendar conectado todavía. "
                        "Usa la herramienta conectar_google_calendar para ofrecerle el enlace de autorización."
                    )
                elif accion == "listar_hoy":
                    eventos = await gc.listar_eventos_hoy(telefono, offset_min=offset_guardado or 0)
                    if not eventos:
                        resultado = "No hay eventos en Google Calendar para hoy."
                    else:
                        lineas = []
                        for e in eventos:
                            # Extraer la hora del inicio (formato ISO con offset)
                            inicio_raw = e["inicio"]
                            if "T" in inicio_raw:
                                hora_str = inicio_raw.split("T")[1][:5]   # "15:00"
                            else:
                                hora_str = "todo el día"
                            linea = f"- {hora_str}: {e['titulo']}"
                            if e["lugar"]:
                                linea += f" ({e['lugar']})"
                            lineas.append(linea)
                        resultado = "Eventos de hoy en Google Calendar:\n" + "\n".join(lineas)
                    logger.info(f"[GOOGLE] Eventos listados para {telefono}: {len(eventos)}")

                elif accion == "crear_evento":
                    titulo = bloque.input.get("titulo", "Evento")
                    inicio_iso = bloque.input.get("inicio_iso", "")
                    fin_iso = bloque.input.get("fin_iso", "")
                    descripcion = bloque.input.get("descripcion", "")
                    lugar = bloque.input.get("lugar", "")

                    if not inicio_iso or not fin_iso:
                        resultado = (
                            "Se necesita inicio_iso y fin_iso para crear el evento. "
                            "Usa el offset del usuario del system prompt para construirlos."
                        )
                    else:
                        evento = await gc.crear_evento(
                            telefono, titulo, inicio_iso, fin_iso, descripcion, lugar
                        )
                        if evento:
                            link_str = f"\nVer en calendario: {evento['link']}" if evento.get("link") else ""
                            resultado = (
                                f"Evento '{evento['titulo']}' creado en Google Calendar.{link_str}"
                            )
                        else:
                            resultado = (
                                "No se pudo crear el evento en Google Calendar. "
                                "Verifica que el usuario tenga permisos activos."
                            )
                elif accion == "listar_rango":
                    inicio_iso = bloque.input.get("inicio_iso", "")
                    fin_iso = bloque.input.get("fin_iso", "")
                    if not inicio_iso or not fin_iso:
                        resultado = "Se necesita inicio_iso y fin_iso para listar eventos en un rango."
                    else:
                        eventos = await gc.listar_eventos_rango(telefono, inicio_iso, fin_iso)
                        if not eventos:
                            resultado = "No hay eventos en Google Calendar para ese rango de fechas."
                        else:
                            lineas = []
                            for e in eventos:
                                inicio_raw = e["inicio"]
                                if "T" in inicio_raw:
                                    fecha_hora = inicio_raw.split("T")
                                    fecha_str = fecha_hora[0]
                                    hora_str = fecha_hora[1][:5]
                                    linea = f"- {fecha_str} {hora_str}: {e['titulo']} (id: {e['id']})"
                                else:
                                    linea = f"- {inicio_raw}: {e['titulo']} (id: {e['id']})"
                                if e["lugar"]:
                                    linea += f" ({e['lugar']})"
                                lineas.append(linea)
                            resultado = f"Eventos en el rango solicitado:\n" + "\n".join(lineas)
                    logger.info(f"[GOOGLE] Eventos rango listados para {telefono}")

                elif accion == "editar_evento":
                    evento_id = bloque.input.get("evento_id", "")
                    if not evento_id:
                        resultado = "Se necesita evento_id para editar el evento. Usa listar_hoy o listar_rango para obtener los IDs."
                    else:
                        evento_editado = await gc.editar_evento(
                            telefono,
                            evento_id,
                            titulo=bloque.input.get("titulo"),
                            inicio_iso=bloque.input.get("inicio_iso"),
                            fin_iso=bloque.input.get("fin_iso"),
                            descripcion=bloque.input.get("descripcion"),
                            lugar=bloque.input.get("lugar"),
                        )
                        if evento_editado:
                            resultado = f"Evento '{evento_editado['titulo']}' actualizado en Google Calendar."
                        else:
                            resultado = "No se pudo editar el evento. Verifica que el ID sea correcto."
                    logger.info(f"[GOOGLE] Evento editado para {telefono}: {evento_id}")

                elif accion == "eliminar_evento":
                    evento_id = bloque.input.get("evento_id", "")
                    if not evento_id:
                        resultado = "Se necesita evento_id para eliminar el evento. Usa listar_hoy o listar_rango para obtener los IDs."
                    else:
                        eliminado = await gc.eliminar_evento(telefono, evento_id)
                        if eliminado:
                            resultado = f"Evento eliminado de Google Calendar correctamente."
                        else:
                            resultado = "No se pudo eliminar el evento. Verifica que el ID sea correcto."
                    logger.info(f"[GOOGLE] Evento eliminado para {telefono}: {evento_id}")

                else:
                    resultado = f"Acción desconocida: '{accion}'. Opciones: listar_hoy, listar_rango, crear_evento, editar_evento, eliminar_evento."

            except Exception as e:
                resultado = f"Error en gestionar_calendario: {e}"
                logger.error(f"gestionar_calendario error para {telefono}: {e}")

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
                        "Esta función de análisis no está disponible en este momento "
                        "(MIROFISH_BASE_URL no configurado)."
                    )
                else:
                    estado = await obtener_mirofish_estado(telefono)
                    project_id = estado.get("project_id") if estado else None
                    graph_id = estado.get("graph_id") if estado else None

                    if not project_id or not graph_id:
                        resultado = (
                            "Aún no tengo suficiente contexto sobre tu vida para analizar este tipo de situaciones. "
                            "Sigue usando Dona con mensajes sobre tu trabajo, personas y proyectos. "
                            "En unos días podré ayudarte a pensar las consecuencias de tus decisiones."
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
                        resultado = "Analizando tu situación. Esto toma 1-2 minutos — el resultado llega por este chat."
                        logger.info(f"Simulación MiroFish iniciada en background para {telefono}")
            except Exception as e:
                resultado = f"Error al iniciar el análisis: {e}"
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


async def _postprocesar_reporte_mirofish(reporte_raw: str, escenario: str) -> list[str]:
    """
    Post-procesa el reporte bruto de MiroFish con Claude para:
    1. Traducirlo a lenguaje natural amigable para WhatsApp.
    2. Estructurarlo en secciones accionables.
    3. Dividirlo en máltiples mensajes si es largo (máx 1500 chars cada uno).
    Retorna una lista de mensajes listos para enviar.
    """
    import anthropic as _anthropic
    import os

    try:
        cliente = _anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        prompt = (
            f"Eres Dona, asistente personal estratégica. "
            f"Recibes el resultado de un análisis de consecuencias y debes presentarlo "
            f"de forma clara, accionable y en lenguaje natural para WhatsApp.\n\n"
            f"Escenario analizado: {escenario}\n\n"
            f"Resultado del análisis:\n{reporte_raw[:4000]}\n\n"
            f"Instrucciones:\n"
            f"- Escribe en español, tono cercano y estratégico\n"
            f"- Estructura: 1) Qué probablemente pasaría, 2) Riesgos principales, "
            f"3) Recomendación concreta de acción\n"
            f"- Máximo 3 secciones cortas, cada una con 2-3 oraciones\n"
            f"- NUNCA uses las palabras 'simulación' o 'simular'\n"
            f"- Usa 'análisis', 'proyección' o 'exploración de consecuencias'\n"
            f"- Sin markdown pesado (no tablas, no listas de 6+ ítems)\n"
            f"- Termina con una pregunta que invite al usuario a actuar"
        )
        response = await cliente.messages.create(
            model="claude-haiku-4-5",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        texto_procesado = response.content[0].text.strip() if response.content else reporte_raw

        # Dividir en múltiples mensajes si supera 1500 chars
        mensajes = []
        if len(texto_procesado) <= 1500:
            mensajes = [texto_procesado]
        else:
            # Dividir por párrafos respetando el límite
            parrafos = texto_procesado.split("\n\n")
            bloque_actual = ""
            for parrafo in parrafos:
                if len(bloque_actual) + len(parrafo) + 2 <= 1500:
                    bloque_actual = (bloque_actual + "\n\n" + parrafo).strip()
                else:
                    if bloque_actual:
                        mensajes.append(bloque_actual)
                    bloque_actual = parrafo
            if bloque_actual:
                mensajes.append(bloque_actual)

        return mensajes if mensajes else [texto_procesado]

    except Exception as e:
        logger.error(f"MiroFish postprocesar_reporte error: {e}")
        # Fallback: dividir el reporte crudo en trozos de 1500 chars
        if len(reporte_raw) <= 1500:
            return [reporte_raw]
        return [
            reporte_raw[i:i+1500]
            for i in range(0, min(len(reporte_raw), 4500), 1500)
        ]


async def _ejecutar_simulacion_background(
    telefono: str, project_id: str, graph_id: str, escenario: str, proveedor
):
    """
    Corre el pipeline completo de simulación MiroFish, post-procesa el reporte
    con Claude para hacerlo legible y accionable, y lo envía por WhatsApp.
    Diseñada para ejecutarse como asyncio.create_task (fire and forget).
    """
    import agent.mirofish_client as mf

    try:
        logger.info(f"MiroFish background: iniciando análisis para {telefono}")
        reporte_raw = await mf.pipeline_simulacion(project_id, graph_id, escenario)

        if reporte_raw and proveedor:
            # Post-procesar con Claude para lenguaje natural y estructura accionable
            mensajes = await _postprocesar_reporte_mirofish(reporte_raw, escenario)

            # Enviar encabezado
            await proveedor.enviar_mensaje(telefono, "*Aquí está el análisis:* 🧠")

            # Enviar cada bloque con pequeña pausa para evitar spam
            import asyncio as _asyncio_local
            for i, bloque in enumerate(mensajes):
                await proveedor.enviar_mensaje(telefono, bloque)
                if i < len(mensajes) - 1:
                    await _asyncio_local.sleep(0.8)  # Pausa entre mensajes

            logger.info(
                f"MiroFish background: análisis enviado a {telefono} "
                f"({len(mensajes)} mensaje(s))"
            )
        elif proveedor:
            await proveedor.enviar_mensaje(
                telefono,
                "No pude completar el análisis. Por favor intenta de nuevo."
            )
    except Exception as e:
        logger.error(f"MiroFish background error para {telefono}: {e}")
        if proveedor:
            try:
                await proveedor.enviar_mensaje(
                    telefono,
                    "Hubo un error al procesar el análisis. Intenta de nuevo más tarde."
                )
            except Exception:
                pass


def _extraer_texto(response) -> str:
    """Extrae el texto de la respuesta de Claude, filtrando contenido técnico."""
    import re
    for bloque in response.content:
        if hasattr(bloque, "text"):
            texto = bloque.text
            # Filtrar líneas que parecen debug interno (IDs, timestamps UTC, etc.)
            # Ejemplo: "Recordatorio #42 (único) guardado para 14076936023"
            texto = re.sub(
                r'Recordatorio\s*#\d+.*?guardado\s+para\s+\d+[^\n]*',
                '', texto
            ).strip()
            if texto:
                return texto
    return obtener_mensaje_fallback()
