# agent/automation/missions.py — Mission Runtime (M0 · recuperar-lead)

"""
Capa de orquestación VISIBLE sobre las acciones existentes (spec Hermes
M0): una misión "recuperar-lead" convierte la intención del dueño en un
flujo verificable — identificar → preparar → aprobar → contactar →
registrar evidencia.

M0-1 (este módulo) entrega SOLO el modelo de estado y su CRUD seguro:
  - `crear_mision_recuperar_lead(...)` — crea una misión `draft`,
    owner-scoped, sin enviar nada.
  - `obtener_mision(mision_id, telefono_owner)` — lectura OWNER-SCOPED:
    un dueño distinto recibe None (no se revela existencia ni metadata).
  - `marcar_bloqueada / marcar_fallida` — cierre seguro con razón cerrada.

NO envía, NO llama al provider, NO crea acciones HIGH (eso es M0-2/M0-3).

Invariantes de seguridad:
  - Toda lectura filtra por `telefono` del owner (wrong-owner → None).
  - El destino del lead vive en la fila (estado operativo owner-scoped,
    como acciones/consentimientos) pero NUNCA se filtra a audit logs: ahí
    va enmascarado (`destino_masked`). El sanitizador de audit ya descarta
    las claves `destino`/`numero_destino`; aquí solo pasamos el enmascarado.
  - Estados y razones son SETS CERRADOS (no strings arbitrarios).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from agent.automation.audit import registrar_evento

logger = logging.getLogger("dona")

# ── Constantes cerradas ──────────────────────────────────────────────────

TIPO_RECUPERAR_LEAD = "recuperar_lead"

# Estados del lifecycle de una misión (set CERRADO).
ESTADOS_MISION = {
    "draft",            # creada, datos mínimos, sin preparar
    "needs_approval",   # draft + acción HIGH enlazada, esperando al dueño
    "approved",         # dueño aprobó (consentimiento + acción)
    "sending",          # materializando el envío HIGH
    "completed",        # lead contactado con evidencia
    "failed",           # falló (razón cerrada)
    "blocked",          # bloqueada por política/gate (razón cerrada)
    "cancelled",        # cancelada antes de ejecutar
}

# Razones cerradas de bloqueo/fallo (spec Hermes M0). No inventar strings.
REASON_CODES_MISION = {
    "missing_lead_destination",
    "invalid_destination",
    "third_party_consent_required",
    "high_confirmation_required",
    "budget_exhausted",
    "insufficient_credits",
    "claim_lost",
    "provider_failed",
    "duplicate_blocked",
    "wrong_owner",
    "policy_blocked",
}

_ESTADOS_TERMINALES = {"completed", "failed", "blocked", "cancelled"}


# ── Helpers ──────────────────────────────────────────────────────────────


def destino_masked(destino: str) -> str:
    """Enmascara el destino para audit/preview-a-logs: nunca el número
    completo. Mismo estilo que el resto del pipeline (prefijo+sufijo)."""
    d = (destino or "").strip()
    if len(d) <= 6:
        return "***"
    return f"{d[:2]}****{d[-4:]}"


def _mision_a_dict(m) -> dict[str, Any]:
    try:
        evidencia = json.loads(m.evidencia_json or "{}")
    except Exception:
        evidencia = {}
    return {
        "id": m.id,
        "telefono": m.telefono,
        "subscription_id": m.subscription_id,
        "tipo": m.tipo,
        "estado": m.estado,
        "canal": m.canal,
        "lead_nombre": m.lead_nombre,
        "destino": m.destino,                      # completo · solo owner-scoped
        "destino_masked": destino_masked(m.destino),
        "contexto": m.contexto,
        "objetivo": m.objetivo,
        "accion_id": m.accion_id,
        "reason_code": m.reason_code,
        "evidencia": evidencia,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        "completed_at": m.completed_at.isoformat() if m.completed_at else None,
    }


# ── API ──────────────────────────────────────────────────────────────────


async def crear_mision_recuperar_lead(
    *,
    telefono: str,
    destino: str = "",
    lead_nombre: str = "",
    contexto: str = "",
    objetivo: str = "",
    subscription_id: str = "",
    canal: str = "whatsapp",
) -> dict[str, Any]:
    """Crea una misión `recuperar_lead` en estado `draft` (owner-triggered).

    NO envía, NO crea acción HIGH, NO aprueba. Solo registra la intención
    del dueño como estado operativo visible. Devuelve el dict de la misión
    con `created`: True.

    El destino se guarda completo (operativo, owner-scoped) pero el evento
    de audit usa solo el enmascarado.
    """
    from agent.memory import async_session
    from agent.automation.models import MisionAutomation

    mision = MisionAutomation(
        telefono=telefono,
        subscription_id=subscription_id[:120],
        tipo=TIPO_RECUPERAR_LEAD,
        estado="draft",
        canal=canal,
        lead_nombre=lead_nombre[:120],
        destino=(destino or "").strip(),
        contexto=contexto,
        objetivo=objetivo[:200],
        evidencia_json="{}",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    async with async_session() as session:
        session.add(mision)
        await session.commit()
        await session.refresh(mision)
        mision_id = mision.id
        result = _mision_a_dict(mision)

    await registrar_evento(
        evento="mission_recover_lead_created",
        telefono=telefono,
        riesgo="high",   # el objetivo final es un envío a tercero (HIGH)
        payload={
            "mision_id": mision_id,
            "tipo": TIPO_RECUPERAR_LEAD,
            "estado": "draft",
            "canal": canal,
            "tiene_destino": bool(result["destino"]),
            "destino_masked": result["destino_masked"],
        },
    )
    return {**result, "created": True}


async def obtener_mision(mision_id: int, telefono_owner: str) -> dict[str, Any] | None:
    """Lectura OWNER-SCOPED de una misión. Un dueño distinto del que la
    creó recibe None — no se revela ni la existencia ni la metadata (cierra
    el modo de fallo wrong-owner de la spec)."""
    from agent.memory import async_session
    from agent.automation.models import MisionAutomation

    async with async_session() as session:
        row = (await session.execute(
            select(MisionAutomation).where(
                MisionAutomation.id == mision_id,
                MisionAutomation.telefono == telefono_owner,
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        return _mision_a_dict(row)


async def listar_misiones(telefono_owner: str, limite: int = 20) -> list[dict[str, Any]]:
    """Lista las misiones del owner, más recientes primero. Owner-scoped."""
    from agent.memory import async_session
    from agent.automation.models import MisionAutomation

    async with async_session() as session:
        rows = (await session.execute(
            select(MisionAutomation)
            .where(MisionAutomation.telefono == telefono_owner)
            .order_by(MisionAutomation.created_at.desc())
            .limit(limite)
        )).scalars().all()
        return [_mision_a_dict(r) for r in rows]


async def _cerrar_mision(
    mision_id: int,
    telefono_owner: str,
    estado_final: str,
    reason_code: str,
    evento: str,
) -> dict[str, Any] | None:
    """Cierre seguro común para blocked/failed. Owner-scoped, razón cerrada,
    idempotente sobre estados terminales (no re-cierra).

    La validación del set cerrado usa `raise`, NO `assert`: un `assert`
    desaparece bajo `python -O` y el "set cerrado" se volvería fail-open en
    producción optimizada (hallazgo de Codex). Misma lección que el guard de
    presupuesto y C4: los invariantes de seguridad no dependen de aserciones.
    El estado_final lo fijan las funciones públicas (siempre válido); se
    valida igual por defensa en profundidad."""
    if estado_final not in ESTADOS_MISION:
        raise ValueError(f"estado no cerrado: {estado_final}")
    if reason_code not in REASON_CODES_MISION:
        raise ValueError(f"razón no cerrada: {reason_code}")

    from agent.memory import async_session
    from agent.automation.models import MisionAutomation

    async with async_session() as session:
        row = (await session.execute(
            select(MisionAutomation).where(
                MisionAutomation.id == mision_id,
                MisionAutomation.telefono == telefono_owner,
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        if row.estado in _ESTADOS_TERMINALES:
            # Ya cerrada: no re-cerrar ni re-emitir evento (idempotente).
            return _mision_a_dict(row)
        row.estado = estado_final
        row.reason_code = reason_code
        row.updated_at = datetime.utcnow()
        if estado_final == "completed":
            row.completed_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        result = _mision_a_dict(row)

    await registrar_evento(
        evento=evento,
        telefono=telefono_owner,
        accion_id=result.get("accion_id"),
        riesgo="high",
        payload={
            "mision_id": mision_id,
            "estado": estado_final,
            "reason_code": reason_code,
        },
    )
    return result


async def marcar_bloqueada(
    mision_id: int, telefono_owner: str, reason_code: str,
) -> dict[str, Any] | None:
    """Marca una misión como `blocked` con razón cerrada (gate/política)."""
    return await _cerrar_mision(
        mision_id, telefono_owner, "blocked", reason_code,
        "mission_recover_lead_blocked",
    )


async def marcar_fallida(
    mision_id: int, telefono_owner: str, reason_code: str,
) -> dict[str, Any] | None:
    """Marca una misión como `failed` con razón cerrada."""
    return await _cerrar_mision(
        mision_id, telefono_owner, "failed", reason_code,
        "mission_recover_lead_failed",
    )
