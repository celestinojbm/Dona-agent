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


# ── M0-4 · completitud tras confirmación dedicada + reconciliación ───────


async def marcar_completada(
    mision_id: int, telefono_owner: str,
) -> dict[str, Any] | None:
    """Marca la misión como `completed` (owner-scoped, idempotente sobre
    terminales). Sin reason_code: completed no es un cierre por razón."""
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
            return _mision_a_dict(row)   # idempotente
        row.estado = "completed"
        row.reason_code = ""
        row.completed_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        result = _mision_a_dict(row)

    await registrar_evento(
        evento="mission_recover_lead_completed",
        telefono=telefono_owner,
        accion_id=result.get("accion_id"),
        riesgo="high",
        payload={"mision_id": mision_id, "estado": "completed"},
    )
    return result


# Errores del confirmador dedicado que NO son fallas de envío: el owner aún
# puede reintentar (la misión NO se cierra; queda en needs_approval).
_ERRORES_REINTENTABLES = {"confirmacion_invalida", "accion_no_aprobada"}


async def confirmar_recuperar_lead(
    mision_id: int, telefono_owner: str, confirmacion: str,
) -> dict[str, Any]:
    """Wrapper ESTRECHO de confirmación de la misión (M0-4): revalida owner,
    tipo y acción enlazada, DELEGA al confirmador HIGH dedicado existente
    (`confirmar_high_whatsapp_dedicado`) y SINCRONIZA el estado de la misión
    con el resultado. NO implementa provider propio, NO auto-aprueba, NO
    relaja la confirmación literal `ENVIAR` (criterio Hermes).

    Mapeo de resultado → misión:
      - completed → misión `completed`.
      - falla de envío real (provider/policy) → misión `failed`/`blocked` con
        razón cerrada.
      - error reintentable (confirmación inválida / acción no aprobada) → la
        misión NO se toca (sigue `needs_approval`); el owner puede reintentar.

    Idempotente: misión ya `completed` → devuelve idempotente sin re-enviar.
    Antes de delegar corre la reconciliación de ESTA misión (preflight) para
    sanar el residual de crash de M0-3 (needs_approval sin accion_id).
    """
    mision = await obtener_mision(mision_id, telefono_owner)
    if mision is None:
        return {"ok": False, "error": "mision_no_existe_o_ajena", "mision_id": mision_id}
    if mision.get("tipo") != TIPO_RECUPERAR_LEAD:
        return {"ok": False, "error": "tipo_no_soportado", "mision_id": mision_id}

    # Guard TERMINAL completo: una misión ya cerrada NO se re-confirma ni se
    # delega (delegar podría re-enviar si la acción quedó `approved`). Solo
    # `completed` responde idempotente; el resto de terminales es un error
    # explícito SIN tocar al provider.
    if mision["estado"] in _ESTADOS_TERMINALES:
        if mision["estado"] == "completed":
            return {
                "ok": True, "mision_id": mision_id, "estado": "completed",
                "accion_id": mision.get("accion_id"), "idempotent": True,
            }
        return {
            "ok": False, "error": "mision_terminal",
            "estado": mision["estado"], "mision_id": mision_id,
        }

    # Preflight de reconciliación de ESTA misión (sana el residual de crash).
    mision = await _reconciliar_una_mision(mision, telefono_owner)

    accion_id = mision.get("accion_id")
    if not accion_id:
        # Sin acción enlazada (ni siquiera tras reconciliar) → no se puede
        # confirmar; el owner debe re-preparar/enlazar.
        return {"ok": False, "error": "sin_accion_enlazada",
                "estado": mision.get("estado"), "mision_id": mision_id}

    # Delegar al confirmador HIGH dedicado existente (claim atómico + 2.5 +
    # ejecución idempotente viven ahí; aquí NO se duplica nada).
    from agent.automation.executors.send_message import confirmar_high_whatsapp_dedicado
    res = await confirmar_high_whatsapp_dedicado(accion_id, confirmacion, telefono_owner)
    estado_final = res.get("estado_final", "")
    error = str(res.get("error") or "")
    estado_accion = str(res.get("estado") or "")

    # La acción YA está completada (este envío o uno previo: un crash pudo
    # dejar la acción `completed` sin completar la misión, y el confirmador
    # entonces responde estado_final=failed/error=accion_no_aprobada con
    # estado=completed). En todos esos casos el mensaje SÍ salió → la misión
    # se sincroniza a completed, no se deja colgada en needs_approval.
    if estado_final == "completed" or estado_accion == "completed":
        await marcar_completada(mision_id, telefono_owner)
        return {
            "ok": True, "mision_id": mision_id, "estado": "completed",
            "accion_id": accion_id,
            "idempotent": bool((res.get("result") or {}).get("idempotent"))
                or estado_final != "completed",
        }

    # No completó. ¿Reintentable (no tocar la misión) o falla real (cerrar)?
    if error in _ERRORES_REINTENTABLES:
        return {
            "ok": False, "error": error, "mision_id": mision_id,
            "estado": mision.get("estado"), "reintentable": True,
        }

    # Duplicado / claim perdido: NO es una falla — otra confirmación
    # concurrente está (o terminó de) enviar. NUNCA cerrar la misión como
    # failed por esto: sincronizar desde el estado real. (Cierra el bug de
    # que el perdedor del claim marcaba failed pisando el completed del
    # ganador.)
    if any(k in error for k in ("claim_lost", "ya_en_ejecucion", "duplicate")):
        actual = await obtener_mision(mision_id, telefono_owner)
        if actual and actual["estado"] == "completed":
            return {
                "ok": True, "mision_id": mision_id, "estado": "completed",
                "accion_id": accion_id, "idempotent": True,
            }
        return {
            "ok": True, "mision_id": mision_id, "accion_id": accion_id,
            "estado": (actual or {}).get("estado", "needs_approval"),
            "en_proceso": True,
        }

    # Falla real de envío/política → cerrar la misión con razón cerrada.
    reason = _reason_code_por_fallo_envio(error)
    if reason == "policy_blocked" or reason == "third_party_consent_required":
        await marcar_bloqueada(mision_id, telefono_owner, reason)
        estado_mision = "blocked"
    else:
        await marcar_fallida(mision_id, telefono_owner, reason)
        estado_mision = "failed"
    return {
        "ok": False, "error": error, "reason_code": reason,
        "estado": estado_mision, "mision_id": mision_id, "accion_id": accion_id,
    }


def _reason_code_por_fallo_envio(error: str) -> str:
    """Mapea el error del confirmador dedicado a un reason_code cerrado."""
    if error in ("politica_terceros_error",):
        return "policy_blocked"
    if error.startswith("limite_"):
        return "policy_blocked"
    if "consent" in error:
        return "third_party_consent_required"
    if "claim" in error or "ya_en_ejecucion" in error:
        return "claim_lost"
    return "provider_failed"


async def _reconciliar_una_mision(
    mision: dict[str, Any], telefono_owner: str,
) -> dict[str, Any]:
    """Sana el residual de crash de M0-3 para UNA misión (preflight de la
    confirmación): si está `needs_approval` sin `accion_id`, busca una acción
    `enviar_mensaje_whatsapp` con opportunity_id `mision-<id>` del owner y la
    relinkea; si no hay, revierte a `draft`. Devuelve la misión actualizada.
    No toca misiones sanas."""
    if mision.get("estado") != "needs_approval" or mision.get("accion_id"):
        return mision

    mision_id = mision["id"]
    from sqlalchemy import select as _select, update as _update
    from agent.memory import async_session
    from agent.automation.models import MisionAutomation, AccionAutomatizacion

    async with async_session() as session:
        acc = (await session.execute(
            _select(AccionAutomatizacion).where(
                AccionAutomatizacion.telefono == telefono_owner,
                AccionAutomatizacion.opportunity_id == f"mision-{mision_id}",
                AccionAutomatizacion.tipo_accion == "enviar_mensaje_whatsapp",
                AccionAutomatizacion.estado.in_(("needs_approval", "approved")),
            ).order_by(AccionAutomatizacion.id.asc())
        )).scalars().first()

        if acc is not None:
            # Relinkear (guard accion_id IS NULL — no pisa un relink concurrente)
            await session.execute(
                _update(MisionAutomation)
                .where(
                    MisionAutomation.id == mision_id,
                    MisionAutomation.telefono == telefono_owner,
                    MisionAutomation.accion_id.is_(None),
                )
                .values(accion_id=acc.id, updated_at=datetime.utcnow())
            )
            await session.commit()
            nueva_accion, nuevo_estado = acc.id, "needs_approval"
        else:
            # Sin acción que relinkear → revertir a draft para re-preparar.
            await session.execute(
                _update(MisionAutomation)
                .where(
                    MisionAutomation.id == mision_id,
                    MisionAutomation.telefono == telefono_owner,
                    MisionAutomation.estado == "needs_approval",
                    MisionAutomation.accion_id.is_(None),
                )
                .values(estado="draft", updated_at=datetime.utcnow())
            )
            await session.commit()
            nueva_accion, nuevo_estado = None, "draft"

    await registrar_evento(
        evento="mission_recover_lead_reconciled",
        telefono=telefono_owner,
        accion_id=nueva_accion,
        riesgo="high",
        payload={
            "mision_id": mision_id,
            "accion_recuperada": nueva_accion is not None,
            "estado_resultante": nuevo_estado,
        },
    )
    return await obtener_mision(mision_id, telefono_owner) or mision


async def reconciliar_misiones_recuperar_lead(
    telefono_owner: str,
) -> dict[str, Any]:
    """Reconciliación post-crash del owner (residual M0-3, aprobado por Hermes
    para M0-4). Tres saneos, todos OWNER-SCOPED:
      (a) misión `needs_approval` sin `accion_id` → relinkear acción
          `mision-*` válida o revertir a `draft`;
      (b) misión no-terminal CON acción enlazada YA `completed` → marcar la
          misión `completed` (un crash post-envío pudo dejarla colgada);
      (c) acción `enviar_mensaje_whatsapp` con opportunity_id `mision-*`,
          confirmable (needs_approval/approved), cuya misión del MISMO owner
          NO la apunta → cancelarla (huérfana no enviable).
    Devuelve contadores. Idempotente.

    SINGLE-FLIGHT POR OWNER (asunción operativa): dentro de UNA corrida, (a)
    relink precede a (c) cancel, y (c) revalida `m.accion_id == aid` justo
    antes de cancelar — así una acción que (a) acaba de relinkear NO se
    cancela. El único residual (Codex, acotado) es correr DOS reconciliaciones
    del mismo owner EN PARALELO: la otra podría relinkear entre la revalidación
    y el cancel de ésta. Impacto acotado: NO hay doble envío ni doble cobro (la
    garantía vive en el claim atómico del ejecutor + límites 2.5); el peor caso
    es cancelar una acción recién relinkeada → el confirmar de esa misión falla
    y el owner re-prepara. Mitigación: no disparar reconciliación concurrente
    para el mismo owner (es tarea de mantenimiento/preflight, naturalmente
    serializada)."""
    from sqlalchemy import select as _select
    from agent.memory import async_session
    from agent.automation.models import MisionAutomation, AccionAutomatizacion

    relinkeadas = revertidas = completadas = canceladas = 0

    # (a) Misiones needs_approval sin accion_id
    async with async_session() as session:
        pendientes = (await session.execute(
            _select(MisionAutomation).where(
                MisionAutomation.telefono == telefono_owner,
                MisionAutomation.estado == "needs_approval",
                MisionAutomation.accion_id.is_(None),
            )
        )).scalars().all()
        ids_pendientes = [m.id for m in pendientes]

    for mid in ids_pendientes:
        m = await obtener_mision(mid, telefono_owner)
        if not m:
            continue
        antes = m.get("accion_id")
        m2 = await _reconciliar_una_mision(m, telefono_owner)
        if m2.get("accion_id") and not antes:
            relinkeadas += 1
        elif m2.get("estado") == "draft":
            revertidas += 1

    # (b) Misiones no-terminales cuya acción enlazada ya está `completed`
    async with async_session() as session:
        filas = (await session.execute(
            _select(MisionAutomation.id, AccionAutomatizacion.estado)
            .join(AccionAutomatizacion, AccionAutomatizacion.id == MisionAutomation.accion_id)
            .where(
                MisionAutomation.telefono == telefono_owner,
                MisionAutomation.estado.notin_(tuple(_ESTADOS_TERMINALES)),
                AccionAutomatizacion.estado == "completed",
            )
        )).all()
        ids_a_completar = [row[0] for row in filas]
    for mid in ids_a_completar:
        if await marcar_completada(mid, telefono_owner):
            completadas += 1

    # (c) Acciones mision-* confirmables huérfanas (la misión del MISMO owner
    # no las apunta). Se revalida justo antes de cancelar (evita un TOCTOU
    # donde un enlace concurrente las vuelva legítimas entre listar y cancelar).
    async with async_session() as session:
        candidatas_ids = (await session.execute(
            _select(AccionAutomatizacion.id, AccionAutomatizacion.opportunity_id).where(
                AccionAutomatizacion.telefono == telefono_owner,
                AccionAutomatizacion.tipo_accion == "enviar_mensaje_whatsapp",
                AccionAutomatizacion.opportunity_id.like("mision-%"),
                AccionAutomatizacion.estado.in_(("needs_approval", "approved")),
            )
        )).all()

    from agent.automation.action_center import cancelar_accion
    for aid, opp in candidatas_ids:
        try:
            mid = int(str(opp).split("-", 1)[1])
        except (ValueError, IndexError):
            continue
        # Revalidación owner-scoped JUSTO antes de cancelar.
        async with async_session() as session:
            m = (await session.execute(
                _select(MisionAutomation).where(
                    MisionAutomation.id == mid,
                    MisionAutomation.telefono == telefono_owner,
                )
            )).scalar_one_or_none()
            acc = (await session.execute(
                _select(AccionAutomatizacion).where(AccionAutomatizacion.id == aid)
            )).scalar_one_or_none()
        # Sigue huérfana si: la acción aún es confirmable Y ninguna misión del
        # owner la apunta (misión inexistente/ajena, o apunta a otra acción).
        if acc is None or acc.estado not in ("needs_approval", "approved"):
            continue
        if m is not None and m.accion_id == aid:
            continue   # se enlazó entre listar y ahora → ya NO es huérfana
        try:
            await cancelar_accion(aid)
            canceladas += 1
        except Exception as e:
            logger.error(f"[M0-4] no se pudo cancelar acción huérfana {aid} ({type(e).__name__}: {e})")

    return {
        "relinkeadas": relinkeadas, "revertidas": revertidas,
        "completadas": completadas, "canceladas": canceladas,
    }


# ── M0-5 · dossier de evidencia + métricas (Control Room mínimo) ─────────

# Eventos de audit que deben existir para considerar una misión COMPLETADA
# CON EVIDENCIA (no solo "estado=completed", sino el rastro reconstruible del
# flujo). high_execution_succeeded es la prueba de que el envío salió.
EVENTOS_EVIDENCIA_REQUERIDOS = (
    "mission_recover_lead_created",
    "mission_recover_lead_draft_created",
    "mission_recover_lead_preview_rendered",
    "mission_recover_lead_action_linked",
    "high_execution_succeeded",
    "mission_recover_lead_completed",
)


async def _eventos_de_mision(mision_id: int, accion_id, telefono_owner: str) -> set[str]:
    """Conjunto de tipos de evento de audit asociados a la misión. Los eventos
    de misión llevan `mision_id` en payload_summary; los `high_*` llevan
    accion_id. Owner-scoped por telefono_short. NUNCA lee destino/cuerpo
    (solo nombres de evento)."""
    from sqlalchemy import select as _select, or_
    from agent.memory import async_session
    from agent.automation.models import AuditLogAutomatizacion
    from agent.automation.audit import _short_telefono

    tel_short = _short_telefono(telefono_owner)
    # payload_summary va con sort_keys → "mision_id": <id> seguido de , o }
    patron_coma = f'%"mision_id": {mision_id},%'
    patron_llave = f'%"mision_id": {mision_id}}}%'
    condiciones = [
        AuditLogAutomatizacion.payload_summary.like(patron_coma),
        AuditLogAutomatizacion.payload_summary.like(patron_llave),
    ]
    if accion_id:
        condiciones.append(AuditLogAutomatizacion.accion_id == accion_id)

    async with async_session() as session:
        rows = (await session.execute(
            _select(AuditLogAutomatizacion.evento).where(
                AuditLogAutomatizacion.telefono_short == tel_short,
                or_(*condiciones),
            )
        )).all()
    return {r[0] for r in rows}


async def dossier_mision(mision_id: int, telefono_owner: str) -> dict[str, Any] | None:
    """Vista de detalle OWNER-SCOPED de una misión para el Control Room
    (M0-5). Wrong-owner → None. Muestra estado, destino ENMASCARADO, acción
    enlazada, reason_code, timestamps y el ESTADO DE EVIDENCIA: qué eventos
    requeridos están presentes y `completed_with_evidence` (True solo si la
    misión está `completed` Y todos los eventos requeridos existen). No expone
    destino/cuerpo crudos."""
    mision = await obtener_mision(mision_id, telefono_owner)
    if mision is None:
        return None

    presentes = await _eventos_de_mision(
        mision_id, mision.get("accion_id"), telefono_owner,
    )
    faltantes = [e for e in EVENTOS_EVIDENCIA_REQUERIDOS if e not in presentes]
    completed_with_evidence = (
        mision["estado"] == "completed" and not faltantes
    )

    return {
        "mision_id": mision["id"],
        "tipo": mision["tipo"],
        "estado": mision["estado"],
        "canal": mision["canal"],
        "lead_nombre": mision["lead_nombre"],
        "destino_masked": mision["destino_masked"],   # nunca crudo
        "accion_id": mision["accion_id"],
        "reason_code": mision["reason_code"],
        "tiene_draft": bool((mision.get("evidencia") or {}).get("draft")),
        "created_at": mision["created_at"],
        "updated_at": mision["updated_at"],
        "completed_at": mision["completed_at"],
        "evidencia": {
            "requeridos": list(EVENTOS_EVIDENCIA_REQUERIDOS),
            "presentes": sorted(presentes & set(EVENTOS_EVIDENCIA_REQUERIDOS)),
            "faltantes": faltantes,
            "completed_with_evidence": completed_with_evidence,
        },
    }


async def metricas_misiones(telefono_owner: str) -> dict[str, Any]:
    """Contadores OWNER-SCOPED de misiones recuperar-lead para el Control Room
    (M0-5): totales por estado, completadas-con-evidencia, y desglose de
    reason_codes de las bloqueadas/fallidas. Métrica norte = completadas con
    evidencia."""
    from sqlalchemy import select as _select, func
    from agent.memory import async_session
    from agent.automation.models import MisionAutomation

    async with async_session() as session:
        por_estado = dict((await session.execute(
            _select(MisionAutomation.estado, func.count())
            .where(
                MisionAutomation.telefono == telefono_owner,
                MisionAutomation.tipo == TIPO_RECUPERAR_LEAD,
            )
            .group_by(MisionAutomation.estado)
        )).all())

        por_razon = dict((await session.execute(
            _select(MisionAutomation.reason_code, func.count())
            .where(
                MisionAutomation.telefono == telefono_owner,
                MisionAutomation.tipo == TIPO_RECUPERAR_LEAD,
                MisionAutomation.estado.in_(("blocked", "failed")),
            )
            .group_by(MisionAutomation.reason_code)
        )).all())

        completadas_ids = (await session.execute(
            _select(MisionAutomation.id, MisionAutomation.accion_id).where(
                MisionAutomation.telefono == telefono_owner,
                MisionAutomation.tipo == TIPO_RECUPERAR_LEAD,
                MisionAutomation.estado == "completed",
            )
        )).all()

    # Métrica norte: completadas CON evidencia completa (no solo estado).
    con_evidencia = 0
    for mid, aid in completadas_ids:
        presentes = await _eventos_de_mision(mid, aid, telefono_owner)
        if all(e in presentes for e in EVENTOS_EVIDENCIA_REQUERIDOS):
            con_evidencia += 1

    total = sum(por_estado.values())
    return {
        "total": total,
        "por_estado": por_estado,
        "completadas": por_estado.get("completed", 0),
        "completadas_con_evidencia": con_evidencia,   # ← métrica norte
        "bloqueadas": por_estado.get("blocked", 0),
        "fallidas": por_estado.get("failed", 0),
        "reason_codes": {k: v for k, v in por_razon.items() if k},
    }
