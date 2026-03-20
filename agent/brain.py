# agent/brain.py — Cerebro de Dona: conexión con Claude API
# Generado por AgentKit

"""
Lógica de IA de Dona. Lee el system prompt de prompts.yaml,
genera respuestas con Claude y maneja tool use para recordatorios.
"""

import os
import yaml
import logging
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Cliente de Anthropic
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Herramienta que Claude puede llamar para crear recordatorios
TOOLS = [
    {
        "name": "crear_recordatorio",
        "description": (
            "Guarda un recordatorio para enviarlo automáticamente al usuario "
            "en una fecha y hora específica via WhatsApp. "
            "Úsala SIEMPRE que el usuario pida que le recuerdes algo en un momento futuro."
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
                        "Fecha y hora en formato ISO 8601 UTC cuando enviar el recordatorio. "
                        "Ejemplo: '2026-03-20T21:00:00'. "
                        "Convierte la hora local del usuario (UTC-5) a UTC sumando 5 horas."
                    )
                }
            },
            "required": ["mensaje_recordatorio", "fecha_hora_utc"]
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


def cargar_system_prompt() -> str:
    """
    Lee el system prompt desde config/prompts.yaml
    e inyecta la fecha/hora UTC actual para que Claude calcule tiempos correctamente.
    """
    config = cargar_config_prompts()
    base = config.get("system_prompt", "Eres Dona, una asistente personal útil. Responde en español.")

    # Inyectar fecha/hora actual para que Claude pueda calcular "mañana", "a las 3pm", etc.
    ahora_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ahora_local = datetime.now(timezone.utc).replace(tzinfo=None)
    # Asumir UTC-5 (hora del usuario)
    from datetime import timedelta
    ahora_usuario = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

    return (
        f"{base}\n\n"
        f"## Fecha y hora actual\n"
        f"- UTC: {ahora_utc}\n"
        f"- Hora del usuario (UTC-5): {ahora_usuario}\n\n"
        f"## Recordatorios\n"
        f"Cuando el usuario pida un recordatorio, SIEMPRE usa la herramienta `crear_recordatorio`.\n"
        f"Convierte la hora local del usuario (UTC-5) a UTC sumando 5 horas antes de guardar."
    )


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Ups, algo salió mal de mi lado 🙁 Intenta de nuevo en un momento.")


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Hmm, no entendí bien eso 😅 ¿Me lo puedes decir de otra forma?")


async def generar_respuesta(mensaje: str, historial: list[dict], telefono: str = "") -> str:
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

    system_prompt = cargar_system_prompt()

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

        # Si Claude quiere usar una herramienta (crear recordatorio)
        if response.stop_reason == "tool_use":
            return await _manejar_tool_use(response, mensajes, system_prompt, telefono)

        # Respuesta de texto normal
        return _extraer_texto(response)

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()


async def _manejar_tool_use(response, mensajes: list, system_prompt: str, telefono: str) -> str:
    """
    Ejecuta las herramientas que Claude solicitó y obtiene la respuesta final.
    """
    from agent.memory import guardar_recordatorio

    resultados_herramientas = []

    for bloque in response.content:
        if bloque.type != "tool_use":
            continue

        if bloque.name == "crear_recordatorio":
            try:
                fecha_hora_str = bloque.input["fecha_hora_utc"]
                # Parsear ISO 8601 — puede venir con o sin microsegundos
                fecha_hora = datetime.fromisoformat(fecha_hora_str.replace("Z", ""))
                mensaje_recordatorio = bloque.input["mensaje_recordatorio"]

                recordatorio = await guardar_recordatorio(
                    telefono=telefono,
                    mensaje=mensaje_recordatorio,
                    fecha_hora=fecha_hora
                )

                hora_local = (fecha_hora.replace(tzinfo=timezone.utc)
                              .astimezone(None)
                              .strftime("%Y-%m-%d %H:%M"))

                resultado = f"Recordatorio guardado correctamente. ID: {recordatorio.id}. Se enviará a las {hora_local} (hora UTC)."
                logger.info(f"Recordatorio #{recordatorio.id} guardado para {telefono} a las {fecha_hora}")

            except Exception as e:
                resultado = f"Error al guardar el recordatorio: {e}"
                logger.error(f"Error guardando recordatorio: {e}")

            resultados_herramientas.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": resultado
            })

    # Segunda llamada a Claude con los resultados de las herramientas
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

    return _extraer_texto(respuesta_final)


def _extraer_texto(response) -> str:
    """Extrae el texto de la respuesta de Claude."""
    for bloque in response.content:
        if hasattr(bloque, "text"):
            return bloque.text
    return obtener_mensaje_fallback()
