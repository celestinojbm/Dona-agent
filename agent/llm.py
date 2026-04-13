# agent/llm.py — Cliente centralizado para modelos secundarios (tareas ligeras)

"""
Reemplaza las llamadas directas a Claude Haiku por DeepSeek (más barato).
Fallback a Claude Haiku si DeepSeek falla.

Uso:
    from agent.llm import completar_texto
    respuesta = await completar_texto(prompt, max_tokens=500)

Tareas que usan este módulo:
  - Análisis emocional (emotion.py)
  - Detección NLP de sistemas (nlp_detector.py)
  - Procesador de sistemas activos (system_processor.py)
  - Perfil de aprendizaje (learning.py)
  - Resumen de memoria (memory_summary.py)
  - Detección de ubicación (location.py)
  - Onboarding NLP (onboarding.py)
  - Contexto real-world (real_world.py)
"""

import os
import logging

logger = logging.getLogger("agentkit")

_DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Cliente primario: DeepSeek (barato, rápido, bueno en JSON/clasificación)
_deepseek = None
if _DEEPSEEK_KEY:
    from openai import AsyncOpenAI
    _deepseek = AsyncOpenAI(api_key=_DEEPSEEK_KEY, base_url="https://api.deepseek.com")

# Fallback: Claude Haiku
_anthropic = None
if _ANTHROPIC_KEY:
    from anthropic import AsyncAnthropic
    _anthropic = AsyncAnthropic(api_key=_ANTHROPIC_KEY)


async def completar_texto(prompt: str, max_tokens: int = 500) -> str | None:
    """
    Envía un prompt simple y retorna la respuesta como texto.
    Usa DeepSeek si disponible, sino Claude Haiku.

    Args:
        prompt: El prompt completo (instrucciones + datos)
        max_tokens: Máximo de tokens en la respuesta

    Returns:
        El texto de la respuesta, o None si todos los modelos fallan.
    """
    # Intento 1: DeepSeek
    if _deepseek:
        try:
            resp = await _deepseek.chat.completions.create(
                model="deepseek-chat",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            texto = resp.choices[0].message.content
            if texto:
                return texto.strip()
        except Exception as e:
            logger.warning(f"[LLM] DeepSeek falló, intentando Haiku: {e}")

    # Intento 2: Claude Haiku (fallback)
    if _anthropic:
        try:
            resp = await _anthropic.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            texto = resp.content[0].text
            if texto:
                return texto.strip()
        except Exception as e:
            logger.error(f"[LLM] Haiku también falló: {e}")

    return None


async def completar_con_sistema(system: str, mensaje: str, max_tokens: int = 500) -> str | None:
    """
    Envía un mensaje con system prompt separado.
    Útil para tareas que necesitan instrucciones de sistema explícitas.
    """
    # Intento 1: DeepSeek
    if _deepseek:
        try:
            resp = await _deepseek.chat.completions.create(
                model="deepseek-chat",
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": mensaje},
                ],
            )
            texto = resp.choices[0].message.content
            if texto:
                return texto.strip()
        except Exception as e:
            logger.warning(f"[LLM] DeepSeek falló, intentando Haiku: {e}")

    # Intento 2: Claude Haiku
    if _anthropic:
        try:
            resp = await _anthropic.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": mensaje}],
            )
            texto = resp.content[0].text
            if texto:
                return texto.strip()
        except Exception as e:
            logger.error(f"[LLM] Haiku también falló: {e}")

    return None
