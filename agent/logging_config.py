# agent/logging_config.py — Logging estructurado y enmascaramiento de datos sensibles

"""
En producción (ENVIRONMENT=production):
  - Logs en formato JSON (una línea por entrada) para parseo automático en Render/Datadog
  - Teléfonos enmascarados: 521234567890 → 5212****7890
  - Texto de mensajes truncado a 40 chars en logs

En desarrollo:
  - Formato legible (texto plano con colores si el terminal lo soporta)
  - Sin enmascaramiento (para debugging)
"""

import os
import re
import json
import logging
from datetime import datetime, timezone


# ── Enmascaramiento de datos sensibles ───────────────────────────────────────

_PATRON_TELEFONO = re.compile(r"\b(\d{2,4})\d{4,8}(\d{4})\b")


def enmascarar_telefono(texto: str) -> str:
    """Enmascara números de teléfono: 521234567890 → 5212****7890"""
    return _PATRON_TELEFONO.sub(r"\1****\2", texto)


def truncar_mensaje(texto: str, max_len: int = 40) -> str:
    """Trunca texto largo para logs."""
    if len(texto) <= max_len:
        return texto
    return texto[:max_len] + "..."


# ── JSON Formatter para producción ───────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """Formatea logs como JSON de una línea para parsing en servicios de monitoreo."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": enmascarar_telefono(record.getMessage()),
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        # Campos extra si existen
        for key in ("request_id", "telefono", "ruta", "duracion_ms", "status_code"):
            val = getattr(record, key, None)
            if val is not None:
                if key == "telefono":
                    val = enmascarar_telefono(str(val))
                entry[key] = val
        return json.dumps(entry, ensure_ascii=False)


# ── Configuración ────────────────────────────────────────────────────────────

def configurar_logging():
    """
    Configura el logging según el entorno.
    Llamar UNA vez al inicio de la aplicación (antes de cualquier logger).
    """
    environment = os.getenv("ENVIRONMENT", "development")
    es_produccion = environment == "production"
    nivel = logging.INFO if es_produccion else logging.DEBUG

    root = logging.getLogger()
    root.setLevel(nivel)

    # Limpiar handlers existentes
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(nivel)

    if es_produccion:
        handler.setFormatter(JsonFormatter())
    else:
        # Formato legible para desarrollo
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        ))

    root.addHandler(handler)

    # Silenciar loggers ruidosos en producción
    if es_produccion:
        for noisy in ("httpx", "httpcore", "uvicorn.access", "sqlalchemy.engine"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
