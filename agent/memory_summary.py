# agent/memory_summary.py — Resumen de memoria a largo plazo
# Dona

"""
Sistema de compresión de historial para Dona.

Problema: guardar solo 20 mensajes recientes hace que Dona "olvide" conversaciones
de días anteriores. Aumentar ese límite encarece mucho los tokens de Claude.

Solución: cada 20 mensajes nuevos, Haiku lee el resumen anterior + los mensajes
nuevos y genera un resumen consolidado (~400 palabras) que se inyecta en el
system prompt. Dona siempre tiene contexto histórico sin pasar cientos de mensajes.

Flujo:
  1. Cada mensaje guardado dispara _actualizar_resumen_si_necesario() en background
  2. Se compara el último ID procesado contra el ID actual → si diff >= 20, se activa
  3. Haiku genera un nuevo resumen consolidado (input ~1500 tokens, output ~600 tokens)
  4. El resumen se inyecta en cargar_system_prompt() de brain.py
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Cuántos mensajes nuevos deben acumularse antes de regenerar el resumen
MENSAJES_POR_CICLO = 20

_PROMPT_RESUMEN = """\
Eres el sistema de memoria de Dona, un asistente personal por WhatsApp.

Tu tarea: consolidar la memoria del usuario en un resumen conciso y útil que \
Dona usará como contexto en futuras conversaciones.

RESUMEN ANTERIOR (vacío si es el primer ciclo):
{resumen_anterior}

MENSAJES NUEVOS A INCORPORAR:
{mensajes_nuevos}

Genera un NUEVO RESUMEN CONSOLIDADO que incluya:
- Hechos importantes sobre el usuario (nombre, trabajo, familia, proyectos activos)
- Preferencias y hábitos mencionados explícitamente
- Contexto de conversaciones recientes que aún sea relevante
- Compromisos, fechas o personas mencionadas que puedan importar después

REGLAS:
- Máximo 400 palabras
- Tercera persona: "El usuario...", "Menciona que...", "Trabaja en..."
- Solo información factual del historial, sin inventar nada
- Si el resumen anterior contradice algo de los mensajes nuevos, usa la versión más reciente
- Omite saludos, chistes o conversación trivial sin contenido factual
- Si no hay información útil aún, escribe exactamente: "Sin contexto acumulado aún."

RESUMEN CONSOLIDADO:"""


async def actualizar_resumen_si_necesario(telefono: str) -> bool:
    """
    Verifica si hay ≥20 mensajes nuevos desde el último resumen.
    Si los hay, usa Haiku para generar un nuevo resumen consolidado y lo guarda.

    Returns:
        True si se generó un resumen nuevo, False si todavía no era necesario.
    """
    from agent.memory import (
        obtener_memoria_largo_plazo,
        guardar_memoria_largo_plazo,
        obtener_ultimo_id_mensaje,
        obtener_mensajes_desde_id,
    )

    try:
        memoria = await obtener_memoria_largo_plazo(telefono)
        ultimo_id_procesado = memoria["ultimo_mensaje_id"] if memoria else 0
        resumen_anterior = memoria["resumen_texto"] if memoria else ""

        ultimo_id_actual = await obtener_ultimo_id_mensaje(telefono)
        mensajes_nuevos_count = ultimo_id_actual - ultimo_id_procesado

        if mensajes_nuevos_count < MENSAJES_POR_CICLO:
            logger.debug(
                f"[MEMORIA] {telefono}: {mensajes_nuevos_count}/{MENSAJES_POR_CICLO} "
                f"mensajes nuevos — sin actualizar aún"
            )
            return False

        logger.info(
            f"[MEMORIA] {telefono}: {mensajes_nuevos_count} mensajes nuevos → "
            f"generando resumen consolidado"
        )

        # Recuperar hasta 40 mensajes nuevos para no saturar el contexto de Haiku
        mensajes = await obtener_mensajes_desde_id(telefono, ultimo_id_procesado, limite=40)
        if not mensajes:
            return False

        # Formatear para el prompt (truncar mensajes muy largos)
        lineas = []
        for m in mensajes:
            prefijo = "Usuario" if m["role"] == "user" else "Dona"
            texto = m["content"][:300] + ("…" if len(m["content"]) > 300 else "")
            lineas.append(f"[{prefijo}]: {texto}")
        texto_mensajes = "\n".join(lineas)

        prompt = _PROMPT_RESUMEN.format(
            resumen_anterior=resumen_anterior or "(ninguno — primer ciclo)",
            mensajes_nuevos=texto_mensajes,
        )

        from agent.llm import completar_texto
        nuevo_resumen = await completar_texto(prompt, max_tokens=600)
        if not nuevo_resumen:
            logger.warning(f"[MEMORIA] {telefono}: LLM no generó resumen")
            return False

        nuevo_ultimo_id = mensajes[-1]["id"]

        await guardar_memoria_largo_plazo(telefono, nuevo_resumen, nuevo_ultimo_id)

        logger.info(
            f"[MEMORIA] {telefono}: resumen actualizado → "
            f"id_hasta={nuevo_ultimo_id}, {len(nuevo_resumen)} chars"
        )
        return True

    except Exception as e:
        logger.error(f"[MEMORIA] Error actualizando resumen para {telefono}: {e}")
        return False
