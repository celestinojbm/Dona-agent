# agent/logging_config.py — Logging estructurado y enmascaramiento de datos sensibles

"""
En producción (ENVIRONMENT=production):
  - Logs en formato JSON (una línea por entrada) para parseo automático en Render/Datadog.
  - Redaction de PII (teléfono, email, tokens) en cualquier registro con nivel INFO o superior.
  - Texto de mensajes truncado a 40 chars en logs.

En desarrollo:
  - Formato legible (texto plano).
  - Sin redaction (debugging).

Reglas de redaction (solo aplica a nivel INFO o superior, no a DEBUG):
  - Teléfono E.164 (con o sin '+'): 521234567890 → 5212****7890
  - Email: foo@bar.com → fo***@bar.com
  - Bearer / claves API obvias (sk-..., whsec_..., cs_(live|test)_..., xoxb-..., re_...)
  - Stripe identifiers de objeto (cus_, sub_, pi_, in_, seti_, ch_)

DEBUG nunca redacta: si necesitás ver PII real para diagnosticar, subí el nivel a DEBUG
con LOG_LEVEL=DEBUG (o ejecutás con ENVIRONMENT distinto de production).
"""

import os
import re
import json
import logging
from datetime import datetime, timezone


# ── Patrones de redaction ────────────────────────────────────────────────────

# Teléfono: 10–15 dígitos con + opcional.
# Lookbehind/forward evitan romper números más largos en los que esto está embebido.
# Cabeza captura el '+' y 2–4 dígitos para preservar el código de país.
_PATRON_TELEFONO = re.compile(r"(?<!\d)(\+?\d{2,4})\d{3,8}(\d{4})(?!\d)")

# Email RFC simplificado.
_PATRON_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]{1,2})[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")

# Bearer + token (HTTP Authorization).
_PATRON_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]+")

# Claves API frecuentes: OpenAI/Anthropic (sk-...), Stripe webhook (whsec_...),
# Stripe session/customer/sub/payment-intent/invoice/setup-intent/charge ids,
# Slack (xoxb-...), Resend (re_...), generic xkeysib (Brevo).
# T2.0.B: password de dashboard (dona-<12 hex>) derivado de
# DASHBOARD_PASSWORD_SECRET — debe redactarse de cualquier log.
_PATRON_API_KEY = re.compile(
    r"\b("
    r"sk-[A-Za-z0-9_\-]{16,}"
    r"|sk-ant-[A-Za-z0-9_\-]{16,}"
    r"|whsec_[A-Za-z0-9]{16,}"
    r"|cs_(?:live|test)_[A-Za-z0-9]{16,}"
    r"|(?:cus|sub|pi|in|seti|ch|prod|price|evt)_[A-Za-z0-9]{14,}"
    r"|xox[abps]-[A-Za-z0-9-]{10,}"
    r"|re_[A-Za-z0-9_\-]{16,}"
    r"|xkeysib-[A-Za-z0-9]{16,}"
    r"|dona-[a-f0-9]{12}"
    r")\b"
)


def enmascarar_telefono(texto: str) -> str:
    """Enmascara números de teléfono: 521234567890 → 5212****7890."""
    return _PATRON_TELEFONO.sub(r"\1****\2", texto)


def _enmascarar_email(match: re.Match) -> str:
    cabeza, dominio = match.group(1), match.group(2)
    return f"{cabeza}***@{dominio}"


def redactar_pii(texto: str) -> str:
    """
    Aplica todos los patrones de redaction sobre `texto` y retorna el resultado.
    Idempotente: aplicarla dos veces no rompe nada.
    """
    if not texto:
        return texto
    # Orden importa: primero los tokens (que contienen dígitos largos, podrían
    # ser confundidos con teléfonos), después email, después teléfono.
    texto = _PATRON_API_KEY.sub("[REDACTED_KEY]", texto)
    texto = _PATRON_BEARER.sub("Bearer [REDACTED]", texto)
    texto = _PATRON_EMAIL.sub(_enmascarar_email, texto)
    texto = enmascarar_telefono(texto)
    return texto


def truncar_mensaje(texto: str, max_len: int = 40) -> str:
    """Trunca texto largo para logs."""
    if len(texto) <= max_len:
        return texto
    return texto[:max_len] + "..."


# ── JSON Formatter para producción ───────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """Formatea logs como JSON de una línea para parsing en servicios de monitoreo.

    Aplica redaction de PII solo a niveles INFO o superior. DEBUG queda
    intacto para que sea posible diagnosticar problemas con datos reales
    bajándolo el nivel.
    """

    def format(self, record: logging.LogRecord) -> str:
        debe_redactar = record.levelno >= logging.INFO
        mensaje_raw = record.getMessage()
        mensaje = redactar_pii(mensaje_raw) if debe_redactar else mensaje_raw

        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": mensaje,
        }
        if record.exc_info and record.exc_info[0]:
            # Stacktrace queda completo (no se redacta dentro del traceback,
            # pero los frames usualmente no contienen PII; los argumentos sí
            # podrían — si hace falta, subí el nivel a DEBUG).
            entry["exception"] = self.formatException(record.exc_info)

        # Campos extra estándar usados por el middleware de main.py.
        for key in ("request_id", "telefono", "ruta", "duracion_ms", "status_code"):
            val = getattr(record, key, None)
            if val is not None:
                if debe_redactar and key == "telefono":
                    val = enmascarar_telefono(str(val))
                entry[key] = val
        return json.dumps(entry, ensure_ascii=False)


# ── Configuración ────────────────────────────────────────────────────────────

def configurar_logging():
    """
    Configura el logging según el entorno.
    Llamar UNA vez al inicio de la aplicación (antes de cualquier logger).

    Variables de entorno:
      - ENVIRONMENT=production → JsonFormatter + redaction en INFO+.
      - LOG_LEVEL=DEBUG → fuerza nivel DEBUG (sin redaction, útil para diagnóstico).
    """
    # Fail-closed (C8): JSON + redaction de PII salvo dev/test EXPLÍCITOS.
    # Antes, un typo en ENVIRONMENT apagaba la redacción en silencio.
    from agent.entorno import es_entorno_estricto
    es_produccion = es_entorno_estricto()

    # LOG_LEVEL puede sobrescribir el nivel default. Útil para activar DEBUG
    # temporal en producción sin redeploy si se hace via env var.
    nivel_override = os.getenv("LOG_LEVEL", "").upper().strip()
    if nivel_override in ("DEBUG", "INFO", "WARNING", "ERROR"):
        nivel = getattr(logging, nivel_override)
    else:
        nivel = logging.INFO if es_produccion else logging.DEBUG

    root = logging.getLogger()
    root.setLevel(nivel)

    # Limpiar handlers existentes.
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(nivel)

    if es_produccion:
        handler.setFormatter(JsonFormatter())
    else:
        # Formato legible para desarrollo.
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        ))

    root.addHandler(handler)

    # Silenciar loggers ruidosos en producción.
    if es_produccion:
        for noisy in ("httpx", "httpcore", "uvicorn.access", "sqlalchemy.engine"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
