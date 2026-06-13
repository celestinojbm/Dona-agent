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


# ── M0-2 · preparar (draft + preview owner-scoped) ───────────────────────

# Límite del cuerpo del draft (consistente con el tope del ejecutor HIGH; el
# draft NUNCA debe exceder lo que el envío real aceptará).
MAX_LEN_DRAFT = 4000


def validar_destino(destino: str) -> str:
    """Valida el destino del lead. Retorna "" si es válido, o el reason_code
    cerrado del problema (missing_lead_destination / invalid_destination).
    Misma regla que el ejecutor HIGH (solo dígitos, '+' opcional, 6..32)."""
    s = (destino or "").strip()
    if not s:
        return "missing_lead_destination"
    if len(s) < 6 or len(s) > 32:
        return "invalid_destination"
    cuerpo = s[1:] if s.startswith("+") else s
    if not cuerpo.isdigit():
        return "invalid_destination"
    return ""


def _prompt_draft_recuperacion(
    lead_nombre: str, contexto: str, objetivo: str,
) -> str:
    """Construye el prompt del mensaje de recuperación. REGLA CLAVE (spec
    Hermes): el mensaje NO debe inventar descuentos, precios ni promesas que
    no vengan en el contexto del dueño — instrucción explícita al modelo."""
    nombre = (lead_nombre or "").strip() or "el cliente"
    ctx = (contexto or "").strip() or "(sin contexto adicional)"
    obj = (objetivo or "").strip() or "retomar la conversación"
    return (
        "Eres Dona, asistente de un dueño de negocio. Redacta UN mensaje "
        "breve de WhatsApp para recontactar a un lead que no convirtió.\n\n"
        f"Lead: {nombre}\n"
        f"Contexto que dio el dueño: {ctx}\n"
        f"Objetivo del mensaje: {obj}\n\n"
        "Reglas estrictas:\n"
        "- Tono humano, cálido y directo. NO agresivo, NO insistente.\n"
        "- Máximo 2 frases cortas + un cierre con pregunta suave (CTA).\n"
        "- Español. Sin markdown, sin emojis excesivos (máximo 1).\n"
        "- PROHIBIDO inventar descuentos, precios, promociones, plazos u "
        "ofertas que NO estén explícitos en el contexto del dueño. Si no hay "
        "oferta en el contexto, NO la menciones ni la inventes.\n"
        "- No hagas promesas en nombre del negocio que no puedas respaldar.\n"
        "- Devuelve SOLO el texto del mensaje, sin comillas ni explicación."
    )


def _reason_code_por_presupuesto(razon_budget: str) -> str:
    """Mapea una razón de bloqueo del BudgetGuard al reason_code cerrado de
    la misión. Kill-switch/suspensión = policy_blocked; el resto (cupo,
    costo, tiempo, contador) = budget_exhausted."""
    if razon_budget in ("kill_switch_global", "owner_suspendido"):
        return "policy_blocked"
    return "budget_exhausted"


async def _generar_draft(telefono: str, prompt: str) -> tuple[str | None, str]:
    """Genera el draft con la vía LLM gateada por el BudgetGuard. Reserva el
    cupo AUXILIAR explícitamente (para obtener la razón exacta si bloquea) y
    reutiliza el núcleo de provider+timeout+consumo de agent.llm SIN volver a
    reservar. Retorna (texto, "") si OK, o (None, reason_code) si bloqueó/falló.

    Distingue: presupuesto bloqueado → reason del guard (sin tocar provider);
    provider sin respuesta → "provider_failed".

    El draft NO cobra créditos (billing); solo consume presupuesto de runtime.
    Los créditos del ENVÍO se reservan en la ejecución HIGH (M0-4)."""
    from agent.presupuesto_runtime import reservar_llm_aux
    import agent.llm as _llm

    decision = reservar_llm_aux(telefono)
    if not decision.permitido:
        # Bloqueado ANTES de tocar al provider (BudgetGuard).
        return None, _reason_code_por_presupuesto(decision.razon)

    texto = await _llm._completar(
        [{"role": "user", "content": prompt}], None, 400, telefono,
    )
    if not texto:
        return None, "provider_failed"
    return texto.strip()[:MAX_LEN_DRAFT], ""


def _preview_de(mision: dict[str, Any]) -> dict[str, Any]:
    """Arma el preview owner-scoped a partir del dict de misión. El mensaje
    completo (draft) solo se expone aquí, a un caller ya owner-validado; el
    costo mostrado es el del ENVÍO eventual, no el del draft."""
    from agent.automation.costos import estimar_costo_accion
    draft = (mision.get("evidencia") or {}).get("draft") or {}
    mensaje = draft.get("mensaje", "")
    return {
        "ok": True,
        "mision_id": mision["id"],
        "tipo": mision["tipo"],
        "estado": mision["estado"],
        "canal": mision["canal"],
        "lead_nombre": mision["lead_nombre"],
        "destino_masked": mision["destino_masked"],
        "destino": mision["destino"],            # operativo · owner-scoped
        "objetivo": mision["objetivo"],
        "mensaje_preview": mensaje,
        "longitud_mensaje": len(mensaje),
        "riesgo": "high",                        # el envío a tercero es HIGH
        "costo_creditos_estimado_envio": estimar_costo_accion("enviar_mensaje_whatsapp"),
        # En M0-2 todavía NO hay acción HIGH ni consentimiento: el siguiente
        # paso (M0-3) enlaza la acción y pide aprobación + confirmación ENVIAR.
        "next_required_action": "enlazar_accion_high_y_confirmar_envio",
        "requiere_consentimiento_tercero": True,
        "requiere_confirmacion_high": True,
    }


async def preparar_recuperar_lead(
    *,
    telefono: str,
    destino: str,
    lead_nombre: str = "",
    contexto: str = "",
    objetivo: str = "",
    subscription_id: str = "",
    canal: str = "whatsapp",
) -> dict[str, Any]:
    """Owner-triggered: crea la misión, redacta el draft (LLM gateado) y
    devuelve el preview owner-scoped. NO envía, NO crea acción HIGH, NO
    aprueba (eso es M0-3/M0-4).

    - Destino inválido/ausente → {ok: False, reason_code} SIN crear misión.
    - Draft bloqueado por presupuesto → misión `blocked` (reason_code) y
      {ok: False, ...}; el provider NO se llama si el BudgetGuard deniega.
    - OK → misión `draft` con el mensaje guardado + preview.
    """
    razon_destino = validar_destino(destino)
    if razon_destino:
        return {"ok": False, "reason_code": razon_destino, "mision_id": None}

    mision = await crear_mision_recuperar_lead(
        telefono=telefono, destino=destino, lead_nombre=lead_nombre,
        contexto=contexto, objetivo=objetivo, subscription_id=subscription_id,
        canal=canal,
    )
    mision_id = mision["id"]

    prompt = _prompt_draft_recuperacion(lead_nombre, contexto, objetivo)
    texto, razon = await _generar_draft(telefono, prompt)
    if texto is None:
        await marcar_bloqueada(mision_id, telefono, razon)
        return {"ok": False, "reason_code": razon, "mision_id": mision_id}

    # Guardar el draft en el estado operativo (owner-scoped) de la misión.
    from agent.memory import async_session
    from agent.automation.models import MisionAutomation

    async with async_session() as session:
        row = (await session.execute(
            select(MisionAutomation).where(
                MisionAutomation.id == mision_id,
                MisionAutomation.telefono == telefono,
            )
        )).scalar_one_or_none()
        if row is None:
            return {"ok": False, "reason_code": "wrong_owner", "mision_id": mision_id}
        try:
            evidencia = json.loads(row.evidencia_json or "{}")
        except Exception:
            evidencia = {}
        evidencia["draft"] = {
            "mensaje": texto,
            "generado_en": datetime.utcnow().isoformat(),
        }
        row.evidencia_json = json.dumps(evidencia, ensure_ascii=False)
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        result = _mision_a_dict(row)

    await registrar_evento(
        evento="mission_recover_lead_draft_created",
        telefono=telefono,
        riesgo="high",
        payload={
            "mision_id": mision_id,
            "longitud_draft": len(texto),
            "destino_masked": result["destino_masked"],
        },
    )
    await registrar_evento(
        evento="mission_recover_lead_preview_rendered",
        telefono=telefono,
        riesgo="high",
        payload={
            "mision_id": mision_id,
            "estado": result["estado"],
            "destino_masked": result["destino_masked"],
            "longitud_mensaje": len(texto),
        },
    )
    return _preview_de(result)


async def preview_recuperar_lead(
    mision_id: int, telefono_owner: str,
) -> dict[str, Any] | None:
    """Re-renderiza el preview owner-scoped de una misión ya preparada.
    Wrong-owner → None. No re-genera el draft ni toca el provider."""
    mision = await obtener_mision(mision_id, telefono_owner)
    if mision is None:
        return None
    return _preview_de(mision)
