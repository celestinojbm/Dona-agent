# agent/observability.py — request_id correlation + métricas extendidas (T1.6)

"""
Observabilidad mínima de Dona (T1.6 + M0.3).

Aporta correlation por request_id sobre el logging que ya existe:

  - Cada request HTTP genera un id corto al entrar al middleware
    (`asignar_nuevo_request_id`).
  - El id vive en un contextvar (asyncio-safe: no se pisan entre
    requests concurrentes).
  - Un filtro de logging lo lee y lo deja en `record.request_id` para
    que `JsonFormatter` (logging_config.py) lo emita como campo extra
    del JSON.
  - El middleware lo expone como header `X-Request-ID` en la respuesta
    para que el caller (landing) pueda correlacionar logs cliente
    ↔ servidor.

NO depende de DB ni red externa. NO persiste nada. Si el contextvar
no fue seteado (ej. log fuera de un request), el campo simplemente
no aparece en el JSON.

Convención del id: prefijo 'req_' + 12 chars hex. Suficiente entropía
para que dos requests no choquen en una ventana razonable, y corto
como para leerlo en logs.
"""

from __future__ import annotations

import logging
import secrets
from contextvars import ContextVar


_REQUEST_ID_PREFIX = "req_"
_REQUEST_ID_HEX_LEN = 12

# Variable de contexto. None mientras no haya request activo.
_request_id_var: ContextVar[str | None] = ContextVar(
    "dona_request_id", default=None
)


def asignar_nuevo_request_id() -> str:
    """Genera un id corto y lo deja activo para todo el request.

    Devuelve el id para que el middleware pueda devolverlo como header.
    """
    rid = _REQUEST_ID_PREFIX + secrets.token_hex(_REQUEST_ID_HEX_LEN // 2)
    _request_id_var.set(rid)
    return rid


def obtener_request_id() -> str | None:
    """Retorna el request_id actual o None si no hay request activo."""
    return _request_id_var.get()


def fijar_request_id(rid: str) -> None:
    """Setea un id provisto desde fuera (ej. propagado desde el caller).

    Útil cuando el landing nos manda un X-Request-ID y queremos
    seguirlo en lugar de generar uno nuevo. Validamos formato laxo:
    solo letras/números/_-, máximo 80 chars, no vacío.
    """
    if not rid:
        return
    rid = rid.strip()
    if not rid or len(rid) > 80:
        return
    # Solo aceptar caracteres seguros para logs JSON.
    if not all(c.isalnum() or c in "_-" for c in rid):
        return
    _request_id_var.set(rid)


class RequestIdFilter(logging.Filter):
    """Filtro de logging que inyecta `record.request_id` desde el contextvar.

    Si no hay request activo, no agrega el atributo (el formatter lo
    omite del JSON).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        rid = _request_id_var.get()
        if rid:
            record.request_id = rid
        return True


def instalar_filtro_request_id() -> None:
    """Agrega el filtro al root logger para que TODO log lleve request_id.

    Idempotente: detecta si el filtro ya está instalado y no duplica.
    Llamar UNA vez en startup, después de configurar_logging().
    """
    root = logging.getLogger()
    for f in root.filters:
        if isinstance(f, RequestIdFilter):
            return
    root.addFilter(RequestIdFilter())
    # También en cada handler para que el filtro corra antes del format.
    for h in root.handlers:
        ya = any(isinstance(f, RequestIdFilter) for f in h.filters)
        if not ya:
            h.addFilter(RequestIdFilter())
