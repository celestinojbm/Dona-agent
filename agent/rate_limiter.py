# agent/rate_limiter.py — Rate limiting persistente con Redis

"""
Sliding window rate limiting que sobrevive restarts.

Si REDIS_URL está configurada, usa Redis (persistente, compartido entre workers).
Si no, cae a in-memory dict (comportamiento legacy para desarrollo local).

Límites:
  - Por usuario: 10 mensajes por 60 segundos
  - Global: 1000 mensajes por 60 segundos (todos los usuarios)
"""

import logging
import os
from time import time as _time
from uuid import uuid4

logger = logging.getLogger("dona")

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

# ── Métricas in-memory del gate (8.2) ─────────────────────────────────────────
# Contadores observables vía snapshot_metricas_rate(). El más importante:
# cuántas veces Redis falló y el gate cayó al fallback degradado per-worker.
_contadores_rate: dict[str, int] = {}


def snapshot_metricas_rate() -> dict[str, int]:
    """Foto inmutable de los contadores del rate limiter (para /admin/metrics)."""
    return dict(_contadores_rate)


def _registrar_fallback_degradado(exc: Exception) -> None:
    """Marca un fallo de Redis con métrica + WARNING. El fallback a memoria es
    per-worker (no compartido entre workers) → más permisivo que Redis; dejar
    rastro observable para detectar degradación silenciosa (auditoría A9)."""
    _contadores_rate["redis_fallback_a_memoria"] = (
        _contadores_rate.get("redis_fallback_a_memoria", 0) + 1
    )
    logger.warning(
        f"[RATE] Redis error → fallback DEGRADADO a memoria (per-worker): "
        f"{type(exc).__name__}: {exc}"
    )


def _dentro_de_limite_memoria(telefono: str) -> bool:
    """Rate limiting in-memory (fallback).

    El límite POR USUARIO se verifica ANTES que el cupo global (8.2): un número
    que excede su tope personal se rechaza sin tocar el presupuesto compartido,
    así un solo abusador no puede agotar el cupo global y tirar a todos (DoS).
    """
    ahora = _time()

    # ── Per-user PRIMERO (no registra todavía: check-then-act conservador) ──
    timestamps = [
        t for t in _rate_limit_mem.get(telefono, []) if ahora - t < _RATE_LIMIT_VENTANA
    ]
    if len(timestamps) >= _RATE_LIMIT_MAX:
        _rate_limit_mem[telefono] = timestamps
        return False

    # ── Global después ──
    global _rate_limit_global_mem
    _rate_limit_global_mem = [
        t for t in _rate_limit_global_mem if ahora - t < _RATE_LIMIT_VENTANA
    ]
    if len(_rate_limit_global_mem) >= _RATE_LIMIT_GLOBAL:
        # Rechazado por el cupo global: NO contamos el envío del usuario.
        _rate_limit_mem[telefono] = timestamps
        return False

    # ── Pasó ambos: registrar en ambas ventanas ──
    _rate_limit_global_mem.append(ahora)
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
    """Rate limiting con Redis sliding window.

    Igual que el path en memoria: per-usuario ANTES que el cupo global (8.2), y
    check-then-add (cuenta primero, registra solo si pasa) en vez del viejo
    add-then-undo. El member del sorted set es ÚNICO por request (uuid): si
    fuera el timestamp crudo, dos requests en el mismo float colapsarían en una
    sola entrada (ZADD actualiza el score, no añade) → subconteo y bypass del
    límite bajo concurrencia.
    """
    try:
        ahora = _time()
        ventana_inicio = ahora - _RATE_LIMIT_VENTANA
        clave_user = f"rate:user:{telefono}"
        clave_global = "rate:global"

        # ── Per-user PRIMERO: contar sin registrar ──
        pipe = _redis.pipeline()
        pipe.zremrangebyscore(clave_user, "-inf", ventana_inicio)
        pipe.zcard(clave_user)
        if pipe.execute()[1] >= _RATE_LIMIT_MAX:
            return False

        # ── Global después: contar sin registrar ──
        pipe = _redis.pipeline()
        pipe.zremrangebyscore(clave_global, "-inf", ventana_inicio)
        pipe.zcard(clave_global)
        if pipe.execute()[1] >= _RATE_LIMIT_GLOBAL:
            return False

        # ── Pasó ambos: registrar con member ÚNICO (uuid) en ambas ventanas ──
        member = f"{ahora}:{uuid4().hex}"
        pipe = _redis.pipeline()
        pipe.zadd(clave_user, {member: ahora})
        pipe.expire(clave_user, int(_RATE_LIMIT_VENTANA) + 5)
        pipe.zadd(clave_global, {member: ahora})
        pipe.expire(clave_global, int(_RATE_LIMIT_VENTANA) + 5)
        pipe.execute()
        return True

    except Exception as e:
        _registrar_fallback_degradado(e)
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
