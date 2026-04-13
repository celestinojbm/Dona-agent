# enhanced/system_processor.py — Procesador de interacciones con sistemas activos

"""
Cuando un usuario tiene sistemas activos, este módulo determina si su mensaje
se refiere a uno de ellos y lo procesa usando Claude Haiku.

Flujo:
  1. Obtener sistemas activos del usuario
  2. Claude Haiku analiza si el mensaje se refiere a algún sistema
  3. Si hay match, Haiku procesa la acción y retorna datos actualizados + respuesta
  4. Se guardan los datos actualizados en user_systems

Si no hay match, retorna None y el mensaje pasa al flujo normal de Dona.
"""

import os
import json
import logging
from datetime import datetime
from anthropic import AsyncAnthropic

from enhanced.models import UserSystem, async_session_enhanced
from enhanced.system_manager import gestor_sistemas
from sqlalchemy import select

logger = logging.getLogger("dona.enhanced")

_claude = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def _obtener_sistemas_con_datos(telefono: str) -> list[dict]:
    """Obtiene todos los sistemas activos del usuario con sus datos."""
    async with async_session_enhanced() as session:
        result = await session.execute(
            select(UserSystem).where(
                UserSystem.telefono == telefono,
                UserSystem.activo == True,
            )
        )
        sistemas = result.scalars().all()

    return [
        {
            "catalog_id": s.catalog_id,
            "nombre": s.nombre_personalizado or f"Sistema #{s.catalog_id}",
            "datos": json.loads(s.datos_json),
        }
        for s in sistemas
    ]


async def procesar_mensaje_sistema(telefono: str, texto: str) -> str | None:
    """
    Intenta procesar el mensaje contra los sistemas activos del usuario.

    Retorna:
      - str con la respuesta si el mensaje fue procesado por un sistema
      - None si el mensaje no se refiere a ningún sistema activo
    """
    sistemas = await _obtener_sistemas_con_datos(telefono)
    if not sistemas:
        return None

    # Construir contexto de sistemas para el prompt
    sistemas_ctx = []
    for s in sistemas:
        datos_str = json.dumps(s["datos"], ensure_ascii=False, indent=2)
        # Limitar tamaño de datos por sistema para no saturar el prompt
        if len(datos_str) > 2000:
            datos_str = datos_str[:2000] + "\n... (datos truncados)"
        sistemas_ctx.append(
            f"SISTEMA: {s['nombre']} (catalog_id={s['catalog_id']})\n"
            f"DATOS ACTUALES:\n{datos_str}"
        )

    sistemas_texto = "\n---\n".join(sistemas_ctx)
    ahora = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    prompt = f"""El usuario tiene estos sistemas activos en Dona (asistente de WhatsApp):

{sistemas_texto}

MENSAJE DEL USUARIO: "{texto}"
FECHA/HORA ACTUAL: {ahora} UTC

ANALIZA:
1. ¿El mensaje se refiere a alguno de estos sistemas? (registrar gasto, marcar hábito, agregar item, consultar datos, etc.)
2. Si SÍ: procesa la acción, actualiza los datos del sistema, y genera una respuesta breve para el usuario.
3. Si NO: el mensaje es conversación general que no se refiere a ningún sistema.

RESPONDE con JSON exacto:
Si el mensaje SÍ se refiere a un sistema:
{{"match": true, "catalog_id": <ID>, "datos_actualizados": <JSON con los datos completos actualizados>, "respuesta": "<respuesta breve para el usuario>"}}

Si NO se refiere a ningún sistema:
{{"match": false}}

REGLAS:
- "gasté $50 en comida" + sistema Control de Gastos → match, agregar gasto
- "tomé agua" + sistema Hidratación → match, registrar
- "hola qué tal" → NO match (conversación general)
- "qué tengo pendiente" sin sistema de tareas → NO match
- Al agregar datos, CONSERVA todos los datos existentes y solo agrega/modifica lo necesario
- Las fechas van en formato "YYYY-MM-DD"
- Responde SOLO el JSON, sin texto adicional
- La respuesta al usuario debe ser concisa y en español"""

    try:
        from agent.llm import completar_texto
        respuesta_raw = await completar_texto(prompt, max_tokens=1000)
        if not respuesta_raw:
            return None
        # Limpiar markdown
        if respuesta_raw.startswith("```"):
            respuesta_raw = respuesta_raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        resultado = json.loads(respuesta_raw)

        if not resultado.get("match"):
            return None

        catalog_id = resultado["catalog_id"]
        datos_nuevos = resultado["datos_actualizados"]
        respuesta_usuario = resultado["respuesta"]

        # Guardar datos actualizados
        actualizado = await gestor_sistemas.actualizar_datos_sistema(
            telefono, catalog_id, datos_nuevos
        )

        if actualizado:
            logger.info(f"[SYSTEMS] Datos actualizados para {telefono} sistema catalog_id={catalog_id}")
            return respuesta_usuario
        else:
            logger.warning(f"[SYSTEMS] No se pudo actualizar sistema catalog_id={catalog_id} para {telefono}")
            return respuesta_usuario  # Aún así devolver respuesta aunque falle el save

    except json.JSONDecodeError:
        logger.debug(f"[SYSTEMS] Respuesta no-JSON de Haiku: {respuesta_raw[:100] if 'respuesta_raw' in dir() else 'N/A'}")
        return None
    except Exception as e:
        logger.debug(f"[SYSTEMS] Error procesando mensaje: {type(e).__name__}: {e}")
        return None
