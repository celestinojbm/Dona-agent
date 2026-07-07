# agent/readiness.py — Readiness check de secrets críticos al arranque (Fase 0 · 0.2)

"""
Un solo punto que valida, en entorno estricto, que TODOS los secrets críticos
estén presentes ANTES de servir tráfico — y reporta TODO lo que falta de una
sola vez (en vez de abortar de a un secret por módulo, lo que obliga a un
redeploy iterativo para descubrir el siguiente faltante).

Complementa el fail-closed de C8 (#70): aquel hace que producción RECHACE
requests cuando falta verificación; éste hace que producción **ni siquiera
arranque** si le faltan precondiciones. Juntos convierten "seguridad por
intención" en "seguridad por garantía" (recomendación del audit + Hermes).

Delta-cero por diseño: la lista de requeridos son secrets que el deploy actual
ya tiene (verificado contra Render) y/o que los checks per-módulo ya exigían;
esto solo los consolida y los reporta juntos y antes. ``ENVIRONMENT`` se lee en
cada llamada (no se cachea) para facilitar tests.
"""

import os

from agent.entorno import entorno_actual, es_entorno_estricto
from agent.providers import modulo_de_proveedor_falta


class ReadinessError(RuntimeError):
    """Falta una precondición crítica para arrancar en entorno estricto."""


# Secrets/precondiciones siempre requeridos en entorno estricto. (nombre, para qué)
# Todos verificados SET en el deploy de producción actual → no rompe el boot.
# Nota (OAuth state): NO se exige OAUTH_STATE_SECRET por separado — el firmado
# del state cae a ENCRYPTION_KEY (ya requerido) o GOOGLE_CLIENT_SECRET; exigirlo
# rompería prod (está ausente). Ver agent/google_calendar.py:_resolver_state_secret.
# Nota (Stripe): se exige STRIPE_WEBHOOK_SECRET (verificación de webhooks) pero NO
# STRIPE_SECRET_KEY — el backend no inicia checkout server-side (ausente en prod;
# billing.py degrada con "checkout no disponible", no aborta).
_SECRETS_REQUERIDOS = [
    ("DATABASE_URL", "persistencia (sin DB confiable, dedup/créditos/auditoría/permisos no son seguros)"),
    ("ENCRYPTION_KEY", "cifrado de tokens OAuth y firma del state OAuth"),
    ("INTERNAL_BRIDGE_SECRET", "bridge landing→backend + hash de lockout del dashboard"),
    ("STRIPE_WEBHOOK_SECRET", "verificación de webhooks de Stripe (billing)"),
    ("INBOUND_WEBHOOK_SECRET", "firma de tokens de webhooks inbound"),
    ("ADMIN_TOKEN", "autenticación de endpoints admin"),
    ("DASHBOARD_PASSWORD_SECRET", "derivación del password del dashboard del usuario"),
    ("ANTHROPIC_API_KEY", "LLM principal (Claude)"),
]

# Secret del proveedor de WhatsApp activo (solo se exige el del provider en uso).
_SECRET_POR_PROVEEDOR = {
    "whapi": ("WHAPI_WEBHOOK_TOKEN", "verificación del webhook de Whapi"),
    "meta": ("META_APP_SECRET", "verificación HMAC del webhook de Meta"),
    "twilio": ("TWILIO_AUTH_TOKEN", "verificación de firma de Twilio"),
}


def _falta(var: str) -> bool:
    return not os.getenv(var, "").strip()


def evaluar_readiness() -> list[str]:
    """Lista de precondiciones faltantes (vacía si todo OK). NO lanza."""
    problemas: list[str] = []

    for var, desc in _SECRETS_REQUERIDOS:
        if _falta(var):
            problemas.append(f"{var} — {desc}")

    # Proveedor de WhatsApp: no se adivina en entorno estricto. Ausente o no
    # soportado es un problema; si es válido, se exige SOLO el secret del activo.
    proveedor = os.getenv("WHATSAPP_PROVIDER", "").strip().lower()
    if not proveedor:
        problemas.append(
            "WHATSAPP_PROVIDER — no configurado (no se debe adivinar el proveedor)"
        )
    elif proveedor not in _SECRET_POR_PROVEEDOR:
        problemas.append(
            f"WHATSAPP_PROVIDER — valor no soportado: {proveedor} (usa whapi/meta/twilio)"
        )
    elif modulo_de_proveedor_falta(proveedor):
        # Proveedor DECLARADO pero sin módulo (caso Twilio): antes esto pasaba
        # el readiness en verde y reventaba con ModuleNotFoundError en el primer
        # webhook. Ahora es una alarma temprana en el arranque (Fase 0 · TEMA 2).
        problemas.append(
            f"WHATSAPP_PROVIDER={proveedor} — proveedor declarado pero su módulo "
            f"agent/providers/{proveedor}.py no existe (implementa el módulo o "
            "usa whapi/meta)"
        )
    else:
        var, desc = _SECRET_POR_PROVEEDOR[proveedor]
        if _falta(var):
            problemas.append(f"{var} — {desc} (WHATSAPP_PROVIDER={proveedor})")

    return problemas


def verificar_readiness() -> None:
    """En entorno estricto, aborta el arranque si falta algún secret crítico,
    reportando TODOS los faltantes de una vez. En dev/test explícitos no hace
    nada (se permite arrancar sin secrets para pruebas locales)."""
    if not es_entorno_estricto():
        return

    problemas = evaluar_readiness()
    if not problemas:
        return

    lista = "\n  - ".join(problemas)
    raise ReadinessError(
        f"[READINESS] Arranque abortado en entorno estricto "
        f"(ENVIRONMENT={entorno_actual() or '<ausente>'}): faltan "
        f"{len(problemas)} precondición(es) crítica(s):\n  - {lista}\n"
        "Configura TODAS antes de reintentar el deploy (o usa "
        "ENVIRONMENT=development/test explícito en entornos no productivos)."
    )
