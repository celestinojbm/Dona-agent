# agent/automation/audit.py — Audit log fundacional (T2.1.A)

"""
Trazabilidad del pipeline de automatización · sin PII / sin secretos.

Helpers:
    registrar_evento(evento, telefono, ...) → AuditLogAutomatizacion
    sanitizar_payload(d) → dict seguro para persistir/loguear

Cada paso significativo del pipeline (oportunidad detectada, acción
creada, aprobada, rechazada, ejecutada, completada, fallida, bloqueada)
debe generar una entrada aquí. Los tests verifican que ningún campo
sensible queda en payload_summary.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("dona")


# Eventos del pipeline · whitelist estricta para evitar typos.
EVENTOS_VALIDOS = {
    "opportunity_detected",
    "action_created",
    "action_approved",
    "action_rejected",
    "action_cancelled",
    "action_started",
    "action_completed",
    "action_failed",
    "action_blocked_critical",
    "playbook_invoked",
    # T2.1.D · ciclo de reservas de créditos
    "credits_reserved",
    "credits_confirmed",
    "credits_released",
    "credits_reservation_failed",
    "action_blocked_insufficient_credits",
    # T2.1.D · pruning
    "pruning_executed",
}


# Claves que NUNCA deben aparecer en payload_summary · si las recibimos,
# las descartamos silenciosamente.
_CLAVES_PROHIBIDAS = {
    "telefono",                # debe ir en telefono_short separado
    "telefono_completo",
    "email",
    "password",
    "secret",
    "api_key",
    "token",
    "stripe_secret_key",
    "dashboard_password_secret",
    "internal_bridge_secret",
    "auth_secret",
    "customer_id",             # use customer_id_short
    "subscription_id",         # use subscription_id_short
    "stripe_session_id",
    "raw_message",              # cuerpo de mensajes WhatsApp del usuario
    "raw_response",
    # Campos de texto libre del onboarding extendido (T2.0.E.1) ·
    # pueden contener PII de clientes del usuario
    "oferta_principal",
    "cliente_ideal",
    "objetivo_mes",
    "canales_actuales",
    "bloqueo_actual",
    "tareas_delegar",
}

# Claves cuyo VALOR debe ser truncado a primeros N chars para evitar
# filtrar IDs largos (Stripe, sub_, etc).
_CLAVES_TRUNCAR = {
    "stripe_customer_id_short",
    "subscription_id_short",
    "customer_id_short",
}

_TRUNCATE_LEN = 12  # 'cus_xxxxx...' suficiente para correlacionar


def _short_telefono(telefono: str) -> str:
    """Trunca telefono igual que agent/welcome.py."""
    if not telefono:
        return "***"
    if len(telefono) <= 6:
        return "***"
    return f"{telefono[:2]}****{telefono[-4:]}"


def sanitizar_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Filtra el payload removiendo claves prohibidas y truncando IDs.

    - Claves en _CLAVES_PROHIBIDAS se descartan completamente.
    - Claves en _CLAVES_TRUNCAR se mantienen pero su valor se trunca.
    - Strings con length > 200 se truncan a 200 chars + sufijo '...'.
    - dicts anidados se procesan recursivamente.
    """
    if not payload:
        return {}
    out: dict[str, Any] = {}
    for k, v in payload.items():
        kl = str(k).lower()
        if kl in _CLAVES_PROHIBIDAS:
            continue
        if isinstance(v, dict):
            out[k] = sanitizar_payload(v)
        elif isinstance(v, list):
            # Listas pequeñas se mantienen; cada elemento dict se sanitiza
            new_list: list[Any] = []
            for item in v[:20]:  # cap de 20 items
                if isinstance(item, dict):
                    new_list.append(sanitizar_payload(item))
                elif isinstance(item, str):
                    new_list.append(item[:200])
                else:
                    new_list.append(item)
            out[k] = new_list
        elif isinstance(v, str):
            if kl in _CLAVES_TRUNCAR:
                out[k] = v[:_TRUNCATE_LEN] + "..." if len(v) > _TRUNCATE_LEN else v
            elif len(v) > 200:
                out[k] = v[:200] + "..."
            else:
                out[k] = v
        else:
            out[k] = v
    return out


async def registrar_evento(
    *,
    evento: str,
    telefono: str,
    accion_id: int | None = None,
    riesgo: str = "",
    payload: dict[str, Any] | None = None,
) -> int:
    """Registra un evento del pipeline en audit_log_automatizacion.

    Args:
        evento: uno de EVENTOS_VALIDOS.
        telefono: completo · se trunca antes de persistir.
        accion_id: id de la acción relacionada (opcional).
        riesgo: low/medium/high/critical o '' si no aplica.
        payload: dict que pasa por sanitizar_payload.

    Returns:
        id del registro creado (int) · 0 si el evento es inválido.
    """
    if evento not in EVENTOS_VALIDOS:
        logger.warning(f"[AUDIT-AUT] evento inválido descartado: {evento!r}")
        return 0

    from agent.memory import async_session
    from agent.automation.models import AuditLogAutomatizacion

    safe = sanitizar_payload(payload or {})
    summary = json.dumps(safe, ensure_ascii=False, sort_keys=True)
    telefono_short = _short_telefono(telefono)

    async with async_session() as session:
        log = AuditLogAutomatizacion(
            telefono_short=telefono_short,
            evento=evento,
            accion_id=accion_id,
            riesgo=riesgo,
            payload_summary=summary,
            created_at=datetime.utcnow(),
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        log_id = log.id

    # Log a stdout solo metadata · NO el contenido sanitizado (que ya
    # está en DB) para mantener logs cortos.
    logger.info(
        f"[AUDIT-AUT] tel={telefono_short} evento={evento} "
        f"accion={accion_id} riesgo={riesgo} log_id={log_id}"
    )
    return log_id
