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


# ── M0-3 · enlazar la acción HIGH WhatsApp existente ─────────────────────


async def enlazar_accion_high_recuperar_lead(
    mision_id: int, telefono_owner: str,
) -> dict[str, Any]:
    """Compone la acción HIGH `enviar_mensaje_whatsapp` con el draft de la
    misión y la enlaza (contrato Hermes M0-3). NO envía, NO aprueba.

    REUTILIZA el camino HIGH dedicado existente (preparar_enviar_mensaje_whatsapp
    → crear_accion); NO crea un ejecutor nuevo ni relaja la seguridad. La
    acción nace `needs_approval` y como es riesgo HIGH, el control genérico la
    deja en `dedicated_confirmation_required`: el generic execute sigue
    bloqueado; solo el camino dedicado (confirmar_high_whatsapp_dedicado, M0-4)
    la materializa.

    Bloquea de forma explícita (y testeada) si:
      - misión inexistente o de otro owner → {ok: False} (no revela cuál);
      - draft ausente → {ok: False, error};
      - destino inválido (defensa en profundidad) → misión `blocked`;
      - la política de terceros (2.5) niega por límite duro → misión `blocked`.
    Idempotente: si ya está enlazada, devuelve la acción existente.

    La política `requiere_consentimiento` (primer contacto) NO bloquea aquí:
    el consentimiento se registra al confirmar ENVIAR (M0-4). Aquí solo se
    bloquea por límite duro (permitido=False).

    RESIDUAL DECLARADO (a cerrar en M0-4 por reconciliación, no por duplicar
    la creación HIGH ni tocar el ejecutor): el claim atómico cierra los
    duplicados concurrentes, pero crear la acción y setear `accion_id` son dos
    commits. Un crash en esa ventana deja la acción HIGH en `needs_approval`
    no enlazada y la misión `needs_approval` sin `accion_id`. No hay envío sin
    aprobación+confirmación dedicada (y los límites 2.5 acotan el daño), pero
    el camino dedicado existente no exige enlace a misión. M0-4 debe
    reconciliar: misión `needs_approval` sin `accion_id` → revertir a draft o
    relinkear; acción con opportunity_id `mision-*` cuya misión no la apunta →
    cancelar.
    """
    mision = await obtener_mision(mision_id, telefono_owner)  # owner-scoped
    if mision is None:
        # wrong-owner e inexistente son indistinguibles (no se revela cuál).
        return {"ok": False, "error": "mision_no_existe_o_ajena", "mision_id": mision_id}

    # Idempotencia: ya enlazada → devolver la acción existente.
    if mision.get("accion_id"):
        return {
            "ok": True, "mision_id": mision_id, "accion_id": mision["accion_id"],
            "estado": mision["estado"], "idempotent": True,
        }

    # Solo se enlaza desde `draft` (no terminal/needs_approval/etc.).
    if mision["estado"] != "draft":
        return {
            "ok": False, "error": "estado_no_enlazable",
            "estado": mision["estado"], "mision_id": mision_id,
        }

    draft = (mision.get("evidencia") or {}).get("draft") or {}
    mensaje = draft.get("mensaje", "")
    if not mensaje:
        return {"ok": False, "error": "draft_ausente", "mision_id": mision_id}

    destino = mision.get("destino", "")
    rd = validar_destino(destino)
    if rd:
        await marcar_bloqueada(mision_id, telefono_owner, rd)
        return {"ok": False, "reason_code": rd, "mision_id": mision_id}

    # Política de terceros (2.5): límite duro → bloquea SIN crear acción.
    # Fail-closed: si la evaluación lanza, se bloquea.
    from agent.automation.consent_terceros import evaluar_politica_envio_tercero
    try:
        politica = await evaluar_politica_envio_tercero(telefono_owner, destino)
    except Exception as e:
        logger.critical(
            f"[M0-3] FAIL-CLOSED evaluando política mision={mision_id} "
            f"({type(e).__name__}: {e})"
        )
        await marcar_bloqueada(mision_id, telefono_owner, "policy_blocked")
        return {"ok": False, "reason_code": "policy_blocked", "mision_id": mision_id}

    if not politica["permitido"]:
        await marcar_bloqueada(mision_id, telefono_owner, "policy_blocked")
        await registrar_evento(
            evento="high_send_blocked_policy",
            telefono=telefono_owner,
            riesgo="high",
            payload={
                "fase": "mission_link", "mision_id": mision_id,
                "motivo": politica["motivo"],
            },
        )
        return {
            "ok": False, "reason_code": "policy_blocked",
            "motivo": politica["motivo"], "mision_id": mision_id,
        }

    # Claim ATÓMICO ANTES de crear la acción (cierra el race concurrente Y la
    # ventana de crash, hallazgo Codex): se reclama la misión draft→needs_approval
    # con guard `accion_id IS NULL`. SOLO el ganador (rowcount==1) crea la
    # acción HIGH → cero acciones huérfanas confirmables. Si el ganador cae
    # entre el claim y el set de accion_id, la misión queda needs_approval SIN
    # acción: estado recuperable y NO enviable (no hay acción que confirmar).
    from sqlalchemy import update
    from agent.memory import async_session
    from agent.automation.models import MisionAutomation

    async with async_session() as session:
        res = await session.execute(
            update(MisionAutomation)
            .where(
                MisionAutomation.id == mision_id,
                MisionAutomation.telefono == telefono_owner,
                MisionAutomation.estado == "draft",
                MisionAutomation.accion_id.is_(None),
            )
            .values(estado="needs_approval", updated_at=datetime.utcnow())
        )
        gano_claim = (res.rowcount == 1)
        await session.commit()

    if not gano_claim:
        # Perdimos el claim: otra llamada concurrente ya lo tomó. NO creamos
        # acción (cero huérfanas). Devolvemos la acción ya enlazada si existe.
        actual = await obtener_mision(mision_id, telefono_owner)
        linked_aid = (actual or {}).get("accion_id")
        if linked_aid:
            return {
                "ok": True, "mision_id": mision_id,
                "accion_id": linked_aid, "estado": actual["estado"],
                "idempotent": True,
            }
        estado_actual = (actual or {}).get("estado")
        if estado_actual == "needs_approval":
            # El ganador está creando la acción justo ahora (ventana corta);
            # no es un error — el enlace está en proceso.
            return {
                "ok": True, "mision_id": mision_id, "accion_id": None,
                "estado": "needs_approval", "idempotent": True,
                "enlace_en_proceso": True,
            }
        return {
            "ok": False, "error": "estado_no_enlazable",
            "estado": estado_actual, "mision_id": mision_id,
        }

    # Ganamos el claim: crear la acción HIGH con el draft, reutilizando el
    # camino dedicado. opportunity_id único por misión.
    from agent.automation.executors.send_message import preparar_enviar_mensaje_whatsapp
    accion = await preparar_enviar_mensaje_whatsapp(
        telefono=telefono_owner,
        numero_destino=destino,
        mensaje=mensaje,
        titulo="Recuperar lead",
        descripcion=f"Misión recuperar-lead #{mision_id}",
        opportunity_id=f"mision-{mision_id}",
    )
    accion_id = accion["id"]

    # Setear accion_id en la misión ya reclamada (guard accion_id IS NULL).
    async with async_session() as session:
        await session.execute(
            update(MisionAutomation)
            .where(
                MisionAutomation.id == mision_id,
                MisionAutomation.telefono == telefono_owner,
                MisionAutomation.accion_id.is_(None),
            )
            .values(accion_id=accion_id, updated_at=datetime.utcnow())
        )
        await session.commit()

    result = await obtener_mision(mision_id, telefono_owner) or {}
    await registrar_evento(
        evento="mission_recover_lead_action_linked",
        telefono=telefono_owner,
        accion_id=accion_id,
        riesgo="high",
        payload={
            "mision_id": mision_id,
            "estado": result.get("estado", "needs_approval"),
            "destino_masked": result.get("destino_masked", ""),
            "es_primer_contacto": politica["es_primer_contacto"],
            "requiere_consentimiento": politica["requiere_consentimiento"],
        },
    )
    return {
        "ok": True,
        "mision_id": mision_id,
        "accion_id": accion_id,
        "estado": "needs_approval",
        "es_primer_contacto": politica["es_primer_contacto"],
        "requiere_consentimiento": politica["requiere_consentimiento"],
        # El siguiente paso (M0-4) es aprobar + confirmar literal ENVIAR por
        # el camino dedicado; el generic execute sigue bloqueado.
        "next_required_action": "aprobar_y_confirmar_envio_dedicado",
    }
