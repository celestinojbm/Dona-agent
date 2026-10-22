"""Prompt caching de Anthropic para el camino conversacional (F16).

Objetivo: estabilizar el prefijo del prompt (tools en orden determinista +
instrucciones estables versionadas) y marcar un breakpoint de caché, de modo que
cada turno y cada iteración del tool-loop reutilicen el prefijo en vez de
re-tokenizarlo. Baja costo y latencia sin tocar la UX.

Reglas (del plan):
- El prefijo estable NO lleva timestamp, saldo ni IDs: sólo las instrucciones
  base versionadas. Todo lo volátil (hora, memoria, emoción, mensaje nuevo) va
  DESPUÉS del breakpoint.
- Historial append-only: este módulo no modifica turnos; sólo cómo se arma el
  parámetro `system`.
- Sin caché propia de respuestas; esto es exclusivamente el prompt caching
  nativo de Anthropic.

Camino header-free (GA): se usa `cache_control: {"type": "ephemeral"}` con el
TTL por defecto (5 min). NO se usan cabeceras beta ni el TTL extendido de 1h
(eso exigiría una cabecera beta; el plan dice "no inventar cabeceras"). Antes de
encender el flag en producción conviene re-verificar la doc oficial vigente
(longitud mínima cacheable, compatibilidad con tools/imágenes/thinking/streaming).

Prueba real de caché (decisión de Celestino, 2026-10-21): el presupuesto de
pruebas de pago quedó CANCELADO (0 USD). NO se hace ningún "hit real" contra
Anthropic desde aquí; la verificación de este módulo es 100% con mocks. Si en el
futuro se autoriza un hit real, debe correrse SÓLO en un entorno/base de datos
AISLADO (nunca `main` ni producción) y con presupuesto explícito.

Flag: DONA_PROMPT_CACHE_ENABLED=false por defecto → comportamiento byte-idéntico
al actual (system como string plano).
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("dona")

# Versión de la plantilla estable. Súbela cuando cambien las instrucciones base
# (invalida el prefijo cacheado a propósito). Sólo para telemetría/diagnóstico.
VERSION_PLANTILLA = "2026-10-20.1"


def cache_habilitado() -> bool:
    """True si el prompt caching está activado por env (apagado por defecto)."""
    return os.getenv("DONA_PROMPT_CACHE_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def unir_system(estable: str, volatil: str = "") -> str:
    """Une estable + volátil en el string clásico (fallback/compatibilidad).
    Debe coincidir byte a byte con el ensamblado histórico."""
    return estable + ("\n\n" + volatil if volatil else "")


def construir_system(estable: str, volatil: str = "") -> str | list[dict[str, Any]]:
    """Construye el parámetro `system` para Anthropic.

    - Flag OFF → string plano (idéntico a unir_system): comportamiento actual.
    - Flag ON  → lista de bloques de texto; el bloque estable lleva
      `cache_control` ephemeral (breakpoint). El bloque volátil va después del
      breakpoint, así que NO se cachea. Como en el orden de caché los `tools`
      preceden al `system`, el breakpoint sobre el bloque estable cachea
      además el toolset (estable en el tool-loop, que usa TOOLS completo).
    """
    if not cache_habilitado():
        return unir_system(estable, volatil)
    bloques: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": estable,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if volatil:
        bloques.append({"type": "text", "text": volatil})
    return bloques


def metricas_cache(response: Any) -> dict[str, Any]:
    """Extrae métricas de caché del usage de la respuesta, de forma defensiva.

    Devuelve tokens no-cacheados/creación/lectura/salida y la fracción de caché
    = cache_read / (input_no_cache + cache_creation + cache_read). Nunca incluye
    prompts ni teléfonos. Si falta `usage`, devuelve ceros (no rompe)."""
    usage = getattr(response, "usage", None)

    def _g(nombre: str) -> int:
        try:
            v = getattr(usage, nombre, 0) or 0
            return int(v)
        except Exception:
            return 0

    input_no_cache = _g("input_tokens")
    cache_creation = _g("cache_creation_input_tokens")
    cache_read = _g("cache_read_input_tokens")
    salida = _g("output_tokens")
    base = input_no_cache + cache_creation + cache_read
    fraccion = (cache_read / base) if base > 0 else 0.0
    return {
        "input_no_cache": input_no_cache,
        "cache_creation": cache_creation,
        "cache_read": cache_read,
        "output": salida,
        "fraccion_cache": round(fraccion, 4),
    }


def registrar_metricas_cache(
    response: Any,
    modelo: str = "",
    duracion_ms: int | None = None,
    resultado: str = "ok",
    id_opaco: str = "",
) -> dict[str, Any]:
    """Loggea métricas de caché sin PII. Devuelve el dict para testeo."""
    m = metricas_cache(response)
    m.update(
        {
            "modelo": modelo,
            "version_plantilla": VERSION_PLANTILLA,
            "cache_habilitado": cache_habilitado(),
            "duracion_ms": duracion_ms,
            "resultado": resultado,
            "id": id_opaco,
        }
    )
    logger.info(
        "[PROMPT_CACHE] modelo=%s v=%s hab=%s no_cache=%d creacion=%d lectura=%d "
        "salida=%d frac=%.4f dur_ms=%s res=%s",
        modelo,
        VERSION_PLANTILLA,
        m["cache_habilitado"],
        m["input_no_cache"],
        m["cache_creation"],
        m["cache_read"],
        m["output"],
        m["fraccion_cache"],
        duracion_ms,
        resultado,
    )
    return m
