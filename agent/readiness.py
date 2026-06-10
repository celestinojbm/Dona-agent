# agent/readiness.py — Readiness check de secrets críticos al startup (Fase 0 · 0.2)

"""
Valida en el arranque que TODOS los secrets críticos estén configurados.

Complementa los checks per-módulo existentes (billing, inbound, bridge,
crypto, providers): aquellos abortan al PRIMER faltante; este check corre
ANTES y reporta la lista COMPLETA de faltantes en un solo error, para que
un deploy mal configurado se arregle en una sola iteración y nunca arranque
"vivo pero degradado".

Comportamiento (fail-closed, ver agent/entorno.py):
  - Entorno estricto (producción o ENVIRONMENT desconocido/ausente):
    cualquier faltante → RuntimeError con la lista de NOMBRES (nunca valores)
    → el deploy aborta antes de servir tráfico.
  - dev/test explícitos: warning con la lista; no aborta.

Qué se exige y por qué:
  - STRIPE_WEBHOOK_SECRET   verificación de firma de webhooks de pago
  - ENCRYPTION_KEY          cifrado de tokens OAuth + secret del state OAuth
  - INTERNAL_BRIDGE_SECRET  firma del bridge landing→backend + hash de lockout
  - INBOUND_WEBHOOK_SECRET  firma de tokens de webhooks externos
  - ADMIN_TOKEN             sin él los endpoints /admin quedan inoperables
  - DATABASE_URL            sin ella se cae a SQLite en disco efímero
                            (pérdida de datos silenciosa en prod)
  - Según WHATSAPP_PROVIDER (misma resolución que agent/providers):
      whapi → WHAPI_TOKEN (enviar) + WHAPI_WEBHOOK_TOKEN (verificar webhook)
      meta  → META_ACCESS_TOKEN + META_APP_SECRET + META_WEBHOOK_VERIFY_TOKEN

No se exige ANTHROPIC_API_KEY: el brain tiene fallbacks multi-proveedor y
su ausencia no abre ningún agujero de seguridad (degrada, no expone).
"""

import logging
import os

from agent.entorno import es_entorno_estricto

logger = logging.getLogger("dona")

# Secrets exigidos siempre (en entorno estricto).
_SECRETS_BASE = (
    "STRIPE_WEBHOOK_SECRET",
    "ENCRYPTION_KEY",
    "INTERNAL_BRIDGE_SECRET",
    "INBOUND_WEBHOOK_SECRET",
    "ADMIN_TOKEN",
    "DATABASE_URL",
)

# Secrets exigidos según el proveedor de WhatsApp activo.
_SECRETS_POR_PROVIDER = {
    "whapi": ("WHAPI_TOKEN", "WHAPI_WEBHOOK_TOKEN"),
    "meta": ("META_ACCESS_TOKEN", "META_APP_SECRET", "META_WEBHOOK_VERIFY_TOKEN"),
    # twilio: el adaptador valida sus propias credenciales; no se duplica aquí.
}


def _provider_activo() -> str:
    """Misma resolución que agent/providers/__init__.py:obtener_proveedor."""
    return os.getenv("WHATSAPP_PROVIDER", "whapi").lower()


def secrets_faltantes() -> list[str]:
    """Lista de nombres de secrets críticos ausentes o vacíos (sin valores)."""
    requeridos = list(_SECRETS_BASE)
    requeridos += list(_SECRETS_POR_PROVIDER.get(_provider_activo(), ()))
    return [n for n in requeridos if not os.getenv(n, "").strip()]


def verificar_secrets_criticos() -> list[str]:
    """Readiness check de startup. Retorna la lista de faltantes.

    En entorno estricto, cualquier faltante aborta con RuntimeError listando
    TODOS los nombres (sin valores). En dev/test solo loguea warning.
    """
    faltantes = secrets_faltantes()
    if not faltantes:
        return []
    if es_entorno_estricto():
        raise RuntimeError(
            "[READINESS] Secrets críticos faltantes en entorno estricto — el "
            "deploy aborta para no arrancar degradado. Configura: "
            + ", ".join(faltantes)
            + f" (provider activo: {_provider_activo()})."
        )
    logger.warning(
        f"[READINESS] Secrets faltantes (tolerado solo en dev/test): "
        f"{', '.join(faltantes)}"
    )
    return faltantes
