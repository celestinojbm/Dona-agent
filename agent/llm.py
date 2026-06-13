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

Presupuesto (entregable F · F-1): este módulo ES la vía AUXILIAR del
RuntimeBudgetGuard por contrato — todas sus tareas son ligeras y de
soporte; el trabajo principal (respuesta al usuario, tool-loop, decisiones
de acción) va por brain.py. Cada invocación reserva cupo auxiliar
(max_llm_aux_calls), corre bajo timeout del guard y consume costo contra
los topes COMPARTIDOS del mensaje/día. Bloqueado → retorna None: todos los
callers ya degradan ante None (emotion → neutral, timezone → sin inferir,
etc.). Un caller futuro que produzca respuesta final o decisiones de
acción NO debe usar este módulo: eso es trabajo principal y va gateado
por brain (reservar_llm).
"""

import os
import logging

logger = logging.getLogger("dona")

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

# Precios aprox. (USD por millón de tokens) para estimar el costo consumido.
# No tienen que ser exactos: alimentan los topes de costo del guard.
_PRECIO_DEEPSEEK_USD_MTOK = 0.3      # sobre total_tokens
_PRECIO_HAIKU_IN_USD_MTOK = 1.0
_PRECIO_HAIKU_OUT_USD_MTOK = 5.0


def _reservar_aux(telefono: str) -> bool:
    """Reserva cupo auxiliar; False = bloqueado (el caller degrada)."""
    from agent.presupuesto_runtime import reservar_llm_aux

    decision = reservar_llm_aux(telefono)
    if not decision.permitido:
        logger.warning(f"[LLM] llamada auxiliar bloqueada por presupuesto: {decision.razon}")
        return False
    return True


async def _completar(mensajes_openai: list, system: str | None, max_tokens: int, telefono: str) -> str | None:
    """Núcleo gateado: una reserva auxiliar cubre el intento lógico
    (DeepSeek + fallback Haiku). Timeout del guard por proveedor; el costo
    se consume con el proveedor que respondió."""
    from agent.presupuesto_runtime import con_timeout_llm, consumir_llm, TimeoutPresupuesto

    # Intento 1: DeepSeek
    if _deepseek:
        try:
            resp = await con_timeout_llm(
                _deepseek.chat.completions.create(
                    model="deepseek-chat",
                    max_tokens=max_tokens,
                    messages=mensajes_openai,
                ),
                telefono,
            )
            texto = resp.choices[0].message.content
            if texto:
                try:
                    consumir_llm(resp.usage.total_tokens * _PRECIO_DEEPSEEK_USD_MTOK / 1_000_000, modelo="deepseek-chat")
                except Exception:
                    consumir_llm(0.0)
                return texto.strip()
        except TimeoutPresupuesto as t:
            if t.razon == "timeout_budget_global":
                return None  # sin tiempo global: no intentar el fallback
            logger.warning("[LLM] DeepSeek timeout, intentando Haiku")
        except Exception as e:
            logger.warning(f"[LLM] DeepSeek falló, intentando Haiku: {e}")

    # Intento 2: Claude Haiku (fallback, misma reserva lógica)
    if _anthropic:
        try:
            kwargs = dict(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                messages=[m for m in mensajes_openai if m["role"] != "system"],
            )
            if system:
                kwargs["system"] = system
            resp = await con_timeout_llm(_anthropic.messages.create(**kwargs), telefono)
            texto = resp.content[0].text
            if texto:
                try:
                    costo = (
                        resp.usage.input_tokens * _PRECIO_HAIKU_IN_USD_MTOK
                        + resp.usage.output_tokens * _PRECIO_HAIKU_OUT_USD_MTOK
                    ) / 1_000_000
                    consumir_llm(costo, modelo="claude-haiku")
                except Exception:
                    consumir_llm(0.0)
                return texto.strip()
        except TimeoutPresupuesto:
            logger.warning("[LLM] Haiku timeout — sin más fallbacks")
        except Exception as e:
            logger.error(f"[LLM] Haiku también falló: {e}")

    return None


async def completar_texto(prompt: str, max_tokens: int = 500, telefono: str = "") -> str | None:
    """
    Envía un prompt simple y retorna la respuesta como texto.
    Usa DeepSeek si disponible, sino Claude Haiku.

    Gateada como llamada AUXILIAR del presupuesto: bloqueada → None
    (los callers degradan).

    Args:
        prompt: El prompt completo (instrucciones + datos)
        max_tokens: Máximo de tokens en la respuesta
        telefono: Owner para kill-switch/suspensión cuando no hay
            presupuesto de mensaje activo (background sin contexto)

    Returns:
        El texto de la respuesta, o None si todos los modelos fallan
        o el presupuesto la bloquea.
    """
    if not _reservar_aux(telefono):
        return None
    return await _completar(
        [{"role": "user", "content": prompt}], None, max_tokens, telefono,
    )


async def completar_con_sistema(system: str, mensaje: str, max_tokens: int = 500, telefono: str = "") -> str | None:
    """
    Envía un mensaje con system prompt separado.
    Útil para tareas que necesitan instrucciones de sistema explícitas.
    Gateada como llamada AUXILIAR del presupuesto (ver completar_texto).
    """
    if not _reservar_aux(telefono):
        return None
    return await _completar(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": mensaje},
        ],
        system, max_tokens, telefono,
    )
