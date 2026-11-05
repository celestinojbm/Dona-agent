# agent/rate_limiter.py — Rate limiting persistente con Redis

"""
Sliding window rate limiting que sobrevive restarts.

Si REDIS_URL está configurada, usa Redis (persistente, compartido entre workers).
Si no, cae a in-memory dict (comportamiento legacy para desarrollo local).
El fallback en memoria NO se comparte entre workers y se pierde al reiniciar.

Límites del gate de mensajes:
  - Por usuario: 10 mensajes por 60 segundos
  - Global: 1000 mensajes por 60 segundos (todos los usuarios)

Cupos aparte (`consumir_cupo`): misma ventana, máximo y duración propios,
clave opaca (no guarda teléfono ni IP en claro) y segundos de Retry-After.
  - privacy_export / privacy_delete: solicitudes CCPA
  - login_engineering: login del panel, compartido entre instancias de Next
    vía POST /internal/panel/login-cupo. Si Redis no está, el cupo queda
    en memoria de este proceso.
"""

import hashlib
import logging
import math
import os
from time import time as _time
from uuid import uuid4

logger = logging.getLogger("dona")

# ── Configuración ────────────────────────────────────────────────────────────
_RATE_LIMIT_MAX = 10  # máximo por usuario por ventana
_RATE_LIMIT_VENTANA = 60.0  # ventana en segundos
_RATE_LIMIT_GLOBAL = 1000  # máximo global por ventana
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
    logger.info(
        "[RATE] REDIS_URL no configurada — rate limiting in-memory (no persiste tras restart)"
    )


# ── Fallback in-memory ───────────────────────────────────────────────────────
_rate_limit_mem: dict[str, list[float]] = {}
_rate_limit_global_mem: list[float] = []
_RATE_LIMIT_MAX_KEYS = 500

# Cupos genéricos (privacidad, etc.). Dict aparte: no comparten tope ni
# ventana con el gate de mensajes de WhatsApp.
_cupos_mem: dict[str, list[float]] = {}
_CUPOS_MAX_CLAVES = 2000

# ambito → (env máximo, default, env ventana en segundos, default)
_CUPOS: dict[str, tuple[str, int, str, int]] = {
    "privacy_export": (
        "RATE_LIMIT_PRIVACY_EXPORT_MAX",
        3,
        "RATE_LIMIT_PRIVACY_EXPORT_WINDOW_SECONDS",
        3600,
    ),
    "privacy_delete": (
        "RATE_LIMIT_PRIVACY_DELETE_MAX",
        3,
        "RATE_LIMIT_PRIVACY_DELETE_WINDOW_SECONDS",
        86400,
    ),
    # Login del panel de ingeniería. Lo consulta la landing por el bridge
    # HMAC; el usuario es el principal fijo, no un campo del cliente.
    "login_engineering": (
        "RATE_LIMIT_LOGIN_MAX",
        5,
        "RATE_LIMIT_LOGIN_WINDOW_SECONDS",
        15 * 60,
    ),
}

# Principal único del panel. Un usuario vacío no abre otro balde.
USUARIO_LOGIN_PANEL = "engineering"

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
    timestamps = [t for t in _rate_limit_mem.get(telefono, []) if ahora - t < _RATE_LIMIT_VENTANA]
    if len(timestamps) >= _RATE_LIMIT_MAX:
        _rate_limit_mem[telefono] = timestamps
        return False

    # ── Global después ──
    global _rate_limit_global_mem
    _rate_limit_global_mem = [t for t in _rate_limit_global_mem if ahora - t < _RATE_LIMIT_VENTANA]
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


def _entero_env(nombre: str, default: int) -> int:
    """Entero >= 1 desde el entorno. Vacío o inválido conserva el default."""
    raw = os.getenv(nombre, "").strip()
    if not raw:
        return default
    try:
        valor = int(raw)
    except ValueError:
        logger.warning(f"[RATE] {nombre}={raw!r} inválido; uso {default}")
        return default
    if valor < 1:
        logger.warning(f"[RATE] {nombre}={valor} < 1; uso {default}")
        return default
    return valor


def config_cupo(ambito: str) -> tuple[int, float]:
    """(máximo, ventana en segundos) del ámbito. Se lee en cada llamada."""
    max_var, max_def, win_var, win_def = _CUPOS[ambito]
    return _entero_env(max_var, max_def), float(_entero_env(win_var, win_def))


def _clave_cupo(ambito: str, sujeto: str) -> str:
    """Clave opaca: el sujeto (teléfono u otro id) no queda en claro en Redis."""
    material = f"{ambito}\n{(sujeto or '').strip()}".encode()
    return "rate:cupo:" + hashlib.sha256(material).hexdigest()


def _retry_tras(mas_viejo, ahora: float, ventana: float) -> int:
    """Segundos hasta que el intento más viejo de la ventana salga del cupo."""
    score = None
    if mas_viejo:
        primero = mas_viejo[0]
        if isinstance(primero, (list, tuple)) and len(primero) >= 2:
            score = float(primero[1])
        elif isinstance(primero, (int, float)):
            score = float(primero)
    if score is None:
        return max(1, math.ceil(ventana))
    return max(1, math.ceil(score + ventana - ahora))


def _podar_cupos_memoria() -> None:
    if len(_cupos_mem) <= _CUPOS_MAX_CLAVES:
        return
    ordenadas = sorted(
        _cupos_mem,
        key=lambda k: _cupos_mem[k][-1] if _cupos_mem[k] else 0,
    )
    sobran = len(_cupos_mem) - _CUPOS_MAX_CLAVES
    for clave in ordenadas[:sobran]:
        del _cupos_mem[clave]


def _consumir_cupo_memoria(clave: str, maximo: int, ventana: float) -> tuple[bool, int]:
    """Ventana deslizante en el proceso. Check-then-add: el rechazo no cuenta."""
    ahora = _time()
    marcas = [t for t in _cupos_mem.get(clave, []) if ahora - t < ventana]
    if len(marcas) >= maximo:
        _cupos_mem[clave] = marcas
        return False, _retry_tras([(None, min(marcas))], ahora, ventana)
    marcas.append(ahora)
    _cupos_mem[clave] = marcas
    _podar_cupos_memoria()
    return True, 0


def _consumir_cupo_redis(clave: str, maximo: int, ventana: float) -> tuple[bool, int]:
    """Misma ventana en un sorted set. El member es único (uuid): el timestamp
    crudo colapsaría dos requests del mismo instante en una sola entrada.
    """
    try:
        ahora = _time()
        pipe = _redis.pipeline()
        pipe.zremrangebyscore(clave, "-inf", ahora - ventana)
        pipe.zcard(clave)
        pipe.zrange(clave, 0, 0, withscores=True)
        _borrados, cuenta, mas_viejo = pipe.execute()
        if cuenta >= maximo:
            return False, _retry_tras(mas_viejo, ahora, ventana)
        member = f"{ahora}:{uuid4().hex}"
        pipe = _redis.pipeline()
        pipe.zadd(clave, {member: ahora})
        pipe.expire(clave, max(int(ventana) + 5, 1))
        pipe.execute()
        return True, 0
    except Exception as e:
        _registrar_fallback_degradado(e)
        return _consumir_cupo_memoria(clave, maximo, ventana)


def sujeto_login(ip: str | None, usuario: str | None) -> str:
    """Clave IP+usuario del login. No consulta si el principal existe.

    IP vacía comparte el balde ``desconocida``. Usuario vacío es el principal
    del panel: no se acepta un identificador en blanco como sujeto nuevo.
    """
    ip_n = (ip or "").strip().lower()[:80] or "desconocida"
    usuario_n = (usuario or "").strip().lower() or USUARIO_LOGIN_PANEL
    return f"{ip_n}|{usuario_n}"


def consumir_login(ip: str | None, usuario: str | None = None) -> tuple[bool, int]:
    """Cupo del login de ingeniería. Redis si hay cliente; si no, memoria."""
    maximo, ventana = config_cupo("login_engineering")
    return consumir_cupo("login_engineering", sujeto_login(ip, usuario), maximo, ventana)


def consumir_cupo(
    ambito: str, sujeto: str, maximo: int, ventana_segundos: float
) -> tuple[bool, int]:
    """Consume un intento de `ambito` para `sujeto`.

    Devuelve ``(permitido, retry_after_segundos)``. ``retry_after`` es 0 si
    pasó, o los segundos a esperar si el cupo está lleno.

    Redis si hay cliente; si no, memoria de este proceso (no persiste ni se
    comparte entre workers). El sujeto se hashea: no se guarda en claro.
    """
    if maximo < 1 or ventana_segundos <= 0:
        return True, 0
    clave = _clave_cupo(ambito, sujeto)
    if _redis:
        return _consumir_cupo_redis(clave, maximo, ventana_segundos)
    return _consumir_cupo_memoria(clave, maximo, ventana_segundos)


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

    cantidad += len(_rate_limit_mem) + len(_cupos_mem)
    _rate_limit_mem.clear()
    _cupos_mem.clear()
    _rate_limit_global_mem = []
    return cantidad
