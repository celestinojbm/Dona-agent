# agent/rate_limiter.py — Rate limiting persistente con Redis

"""
Sliding window rate limiting que sobrevive restarts.

Si REDIS_URL está configurada, usa Redis (persistente, compartido entre workers).
Si no, cae a in-memory dict (comportamiento legacy para desarrollo local).

Límites:
  - Por usuario: 10 mensajes por 60 segundos
  - Global: 1000 mensajes por 60 segundos (todos los usuarios)
"""

import os
import logging
from time import time as _time

logger = logging.getLogger("agentkit")

# ── Configuración ────────────────────────────────────────────────────────────
_RATE_LIMIT_MAX = 10         # máximo por usuario por ventana
_RATE_LIMIT_VENTANA = 60.0   # ventana en segundos
_RATE_LIMIT_GLOBAL = 1000    # máximo global por ventana
_REDIS_URL = os.getenv("REDIS_URL", "")

# ── Redis (si disponible) ────────────────────────────────────────────────────
_redis = None

if _REDIS_URL:
    try:
        import redis
        _redis = redis.from_url(_REDIS_URL, decode_responses=True, socket_timeout=2)
        _redis.ping()
        logger.info("[RATE] Rate limiting con Redis activado")
    except Exception as e:
        logger.warning(f"[RATE] Redis no disponible ({e}), usando rate limiting in-memory")
        _redis = None
else:
    logger.info("[RATE] REDIS_URL no configurada — rate limiting in-memory (no persiste tras restart)")


# ── Fallback in-memory ───────────────────────────────────────────────────────
_rate_limit_mem: dict[str, list[float]] = {}
_rate_limit_global_mem: list[float] = []
_RATE_LIMIT_MAX_KEYS = 500


def _dentro_de_limite_memoria(telefono: str) -> bool:
    """Rate limiting in-memory (fallback)."""
    ahora = _time()

    # Global check
    global _rate_limit_global_mem
    _rate_limit_global_mem = [t for t in _rate_limit_global_mem if ahora - t < _RATE_LIMIT_VENTANA]
    if len(_rate_limit_global_mem) >= _RATE_LIMIT_GLOBAL:
        return False
    _rate_limit_global_mem.append(ahora)

    # Per-user check
    timestamps = _rate_limit_mem.get(telefono, [])
    timestamps = [t for t in timestamps if ahora - t < _RATE_LIMIT_VENTANA]
    if len(timestamps) >= _RATE_LIMIT_MAX:
        _rate_limit_mem[telefono] = timestamps
        return False
    timestamps.append(ahora)
    _rate_limit_mem[telefono] = timestamps

    # Limpieza periódica
    if len(_rate_limit_mem) > _RATE_LIMIT_MAX_KEYS:
        numeros_ordenados = sorted(
            _rate_limit_mem,
            key=lambda t: _rate_limit_mem[t][-1] if _rate_limit_mem[t] else 0,
        )
        for n in numeros_ordenados[: len(_rate_limit_mem) - _RATE_LIMIT_MAX_KEYS]:
            del _rate_limit_mem[n]

    return True


def _dentro_de_limite_redis(telefono: str) -> bool:
    """Rate limiting con Redis sliding window."""
    try:
        ahora = _time()
        ventana_inicio = ahora - _RATE_LIMIT_VENTANA

        pipe = _redis.pipeline()

        # Global check
        clave_global = "rate:global"
        pipe.zremrangebyscore(clave_global, "-inf", ventana_inicio)
        pipe.zcard(clave_global)
        pipe.zadd(clave_global, {f"{ahora}": ahora})
        pipe.expire(clave_global, int(_RATE_LIMIT_VENTANA) + 5)

        # Per-user check
        clave_user = f"rate:user:{telefono}"
        pipe.zremrangebyscore(clave_user, "-inf", ventana_inicio)
        pipe.zcard(clave_user)
        pipe.zadd(clave_user, {f"{ahora}": ahora})
        pipe.expire(clave_user, int(_RATE_LIMIT_VENTANA) + 5)

        results = pipe.execute()

        # results[1] = global count after cleanup (before add)
        # results[5] = user count after cleanup (before add)
        global_count = results[1]
        user_count = results[5]

        if global_count >= _RATE_LIMIT_GLOBAL:
            # Undo the add
            _redis.zrem(clave_global, f"{ahora}")
            _redis.zrem(clave_user, f"{ahora}")
            return False

        if user_count >= _RATE_LIMIT_MAX:
            # Undo the add
            _redis.zrem(clave_global, f"{ahora}")
            _redis.zrem(clave_user, f"{ahora}")
            return False

        return True

    except Exception as e:
        logger.warning(f"[RATE] Redis error, fallback a memoria: {e}")
        return _dentro_de_limite_memoria(telefono)


def dentro_de_limite(telefono: str) -> bool:
    """
    Verifica si el número está dentro del límite de rate limiting.
    Usa Redis si disponible, sino fallback a in-memory.
    """
    if _redis:
        return _dentro_de_limite_redis(telefono)
    return _dentro_de_limite_memoria(telefono)


def limpiar_rate_limit():
    """Limpia todo el rate limiting (para !exec limpiar_rate_limit)."""
    global _rate_limit_global_mem
    cantidad = 0

    if _redis:
        try:
            keys = _redis.keys("rate:*")
            cantidad = len(keys)
            if keys:
                _redis.delete(*keys)
        except Exception as e:
            logger.warning(f"[RATE] Error limpiando Redis: {e}")

    cantidad += len(_rate_limit_mem)
    _rate_limit_mem.clear()
    _rate_limit_global_mem = []
    return cantidad
