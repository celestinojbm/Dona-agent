# agent/automation/execution.py — Execution System (T2.1.A)

"""
Interfaz de ejecutores para acciones del Automation Core.

T2.1.A entrega ejecutores INTERNOS / DRY-RUN:
  - generan plan, copy, checklist, calendario, mensaje preparado
  - producen output texto que el usuario ve y aprueba
  - NO envían mensajes reales · NO publican en redes · NO gastan
    créditos reales · NO tocan Stripe · NO tocan WhatsApp

Reglas estrictas:
  1. ejecutar() solo procede si la acción está en estado 'approved' o
     'pending' (esta última solo para riesgo LOW que auto-ejecuta).
  2. Acciones CRITICAL están bloqueadas en T2.1.A · ejecutar() las
     rechaza explícitamente con audit log evento 'action_blocked_critical'.
  3. HIGH solo se ejecuta si está 'approved'. Si el ejecutor mapeado
     es de tipo dry-run (T2.1.A), pasa; si fuera de tipo real (T2.1.C),
     ese ejecutor decide si está habilitado.
  4. Todo lo demás (MEDIUM/HIGH 'approved', LOW 'pending') pasa por
     el ejecutor mapeado al tipo_accion.

Ejecutores T2.1.A son funciones puras que reciben el payload de la
acción + perfil_negocio y retornan dict · sin side effects externos.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from agent.automation.permissions import (
    NivelRiesgo,
    clasificar_riesgo,
    esta_bloqueado_t21,
)
from agent.automation.audit import registrar_evento
from agent.automation.action_center import (
    marcar_running,
    marcar_completada,
    marcar_fallida,
)

logger = logging.getLogger("dona")


# ── Ejecutores internos · todos dry-run / generación de texto ───────────────


async def _ejecutor_plan_semanal(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    """Genera un plan semanal en texto (markdown). T2.1.A no llama LLM ·
    devuelve un esqueleto basado en los campos del perfil."""
    nombre = (perfil or {}).get("nombre_negocio", "tu negocio")
    objetivo = (perfil or {}).get("objetivo_mes", "(sin objetivo definido)")
    plan = (
        f"# Plan semanal · {nombre}\n\n"
        f"**Objetivo del mes:** {objetivo}\n\n"
        "## Lunes\n- (pendiente · placeholder T2.1.A)\n\n"
        "## Martes\n- (placeholder)\n\n"
        "## Miércoles\n- (placeholder)\n\n"
        "## Jueves\n- (placeholder)\n\n"
        "## Viernes\n- (placeholder)\n"
    )
    return {"output_md": plan, "modo": "dry_run", "fuente": "esqueleto_t21a"}


async def _ejecutor_calendario_contenido(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    canales = (perfil or {}).get("canales_actuales", "WhatsApp")
    calendario = [
        {"dia": i + 1, "canal": canales.split(",")[0].strip() or "WhatsApp",
         "idea": f"(placeholder día {i+1})"}
        for i in range(7)
    ]
    return {"calendario": calendario, "modo": "dry_run"}


async def _ejecutor_checklist_ventas(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    items = [
        "Revisar últimos 5 leads sin respuesta.",
        "Confirmar pedidos pendientes del día.",
        "Cobrar facturas vencidas.",
        "Subir 1 publicación de oferta principal.",
        "Hacer 3 seguimientos a clientes recurrentes.",
        "Actualizar precio si cambió costo.",
        "Agendar 2 reuniones de cierre esta semana.",
        "Pedir 1 testimonio nuevo.",
    ]
    return {"checklist": items, "modo": "dry_run"}


async def _ejecutor_analizar_diagnostico(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    p = perfil or {}
    llenos = sum(1 for k in (
        "oferta_principal", "cliente_ideal", "objetivo_mes",
        "canales_actuales", "bloqueo_actual", "tareas_delegar",
    ) if p.get(k, "").strip())
    return {
        "campos_llenos": llenos,
        "campos_totales": 6,
        "completitud_pct": int(llenos / 6 * 100),
        "modo": "dry_run",
    }


async def _ejecutor_generar_idea_oferta(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    return {
        "alternativas": [
            "(placeholder T2.1.A — alternativa 1)",
            "(placeholder T2.1.A — alternativa 2)",
            "(placeholder T2.1.A — alternativa 3)",
        ],
        "modo": "dry_run",
    }


async def _ejecutor_preparar_mensaje_whatsapp(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    """Prepara un borrador · NO envía. Listo para que el usuario apruebe."""
    return {
        "borrador": "(placeholder T2.1.A · borrador WhatsApp · sin enviar)",
        "modo": "dry_run",
        "estado_envio": "pending_user_review",
    }


async def _ejecutor_preparar_publicacion_redes(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    return {
        "borrador": "(placeholder T2.1.A · borrador post · sin publicar)",
        "modo": "dry_run",
        "estado_publicacion": "pending_user_review",
    }


async def _ejecutor_preparar_email_seguimiento(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    return {
        "asunto": "(placeholder asunto)",
        "cuerpo": "(placeholder cuerpo email)",
        "modo": "dry_run",
        "estado_envio": "pending_user_review",
    }


async def _ejecutor_preparar_campana_whatsapp(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    return {
        "mensajes": [
            "(M1 anuncio · placeholder)",
            "(M2 recordatorio · placeholder)",
            "(M3 último día · placeholder)",
        ],
        "modo": "dry_run",
        "estado_envio": "pending_user_review",
    }


async def _ejecutor_borrador_copy_oferta(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    return {
        "copy": "(placeholder T2.1.A · copy de oferta)",
        "modo": "dry_run",
    }


async def _ejecutor_generar_checklist_ventas(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    # Alias del checklist · alguien podría llamar tipo distinto
    return await _ejecutor_checklist_ventas(accion, perfil)


# Mapping tipo_accion → ejecutor (todos dry-run en T2.1.A)
EJECUTORES_T21A: dict[str, Callable[..., Awaitable[dict]]] = {
    # LOW
    "generar_plan_semanal": _ejecutor_plan_semanal,
    "generar_calendario_contenido": _ejecutor_calendario_contenido,
    "generar_checklist_ventas": _ejecutor_checklist_ventas,
    "analizar_diagnostico": _ejecutor_analizar_diagnostico,
    "generar_idea_oferta": _ejecutor_generar_idea_oferta,
    # MEDIUM (preparan · no envían)
    "preparar_mensaje_whatsapp": _ejecutor_preparar_mensaje_whatsapp,
    "preparar_campana_whatsapp": _ejecutor_preparar_campana_whatsapp,
    "preparar_publicacion_redes": _ejecutor_preparar_publicacion_redes,
    "preparar_email_seguimiento": _ejecutor_preparar_email_seguimiento,
    "borrador_copy_oferta": _ejecutor_borrador_copy_oferta,
}


# ── API pública ─────────────────────────────────────────────────────────────


async def ejecutar_accion(accion: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una acción del Action Center.

    Reglas:
      - Si estado == 'pending' y riesgo == LOW: ejecuta (auto).
      - Si estado == 'approved': ejecuta.
      - Si estado != esos dos: rechaza con error_message claro.
      - Si riesgo == CRITICAL: bloquea SIEMPRE en T2.1.A.
      - Si tipo_accion no tiene ejecutor mapeado (HIGH típicamente):
        en T2.1.A se rechaza con error_message · futuro PR los conecta
        a ejecutores reales con guardrails extra.

    Returns:
        Dict con 'estado_final' · 'result' · 'error' (si aplica).
    """
    accion_id = accion["id"]
    tipo = accion["tipo_accion"]
    estado = accion["estado"]
    riesgo_str = accion["riesgo"]
    riesgo = NivelRiesgo(riesgo_str)
    telefono = accion["telefono"]

    # Bloqueo crítico
    if esta_bloqueado_t21(riesgo):
        await registrar_evento(
            evento="action_blocked_critical",
            telefono=telefono,
            accion_id=accion_id,
            riesgo=riesgo_str,
            payload={"tipo_accion": tipo, "razon": "critical_blocked_t21a"},
        )
        await marcar_fallida(
            accion_id,
            error_message=(
                "Acción CRITICAL bloqueada en T2.1.A · requiere "
                "confirmación fuerte (futuro PR)."
            ),
        )
        return {
            "estado_final": "failed",
            "error": "critical_blocked_t21a",
        }

    # Estado válido para ejecutar
    estado_ok = (
        (estado == "pending" and riesgo == NivelRiesgo.LOW)
        or estado == "approved"
    )
    if not estado_ok:
        msg = (
            f"Estado '{estado}' no permite ejecutar; riesgo={riesgo_str}. "
            f"MEDIUM/HIGH requieren aprobación."
        )
        await marcar_fallida(accion_id, error_message=msg)
        return {"estado_final": "failed", "error": msg}

    # Ejecutor mapeado
    ejecutor = EJECUTORES_T21A.get(tipo)
    if ejecutor is None:
        # Típicamente HIGH (enviar_*, contactar_lead) que NO tienen
        # ejecutor en T2.1.A. Rechazamos hasta T2.1.C.
        msg = (
            f"Tipo de acción '{tipo}' no tiene ejecutor disponible en "
            f"T2.1.A · futuro PR (T2.1.C) lo habilita con guardrails."
        )
        await marcar_fallida(accion_id, error_message=msg)
        return {"estado_final": "failed", "error": msg}

    # Ejecución
    await marcar_running(accion_id)
    try:
        # Cargar perfil (best-effort) · si no existe, ejecutor recibe None
        perfil_dict = await _cargar_perfil(telefono)
        result = await ejecutor(accion, perfil_dict)
    except Exception as e:
        # Sanitizar el mensaje · sin stack trace ni datos crudos
        msg = f"{type(e).__name__}: error interno durante ejecución"
        logger.exception(f"[EXEC] accion_id={accion_id} tipo={tipo}")
        await marcar_fallida(accion_id, error_message=msg)
        return {"estado_final": "failed", "error": msg}

    await marcar_completada(accion_id, result=result)
    return {"estado_final": "completed", "result": result}


async def _cargar_perfil(telefono: str) -> dict[str, Any] | None:
    """Lee perfil_negocio · retorna dict o None si no existe."""
    from agent.memory import async_session
    from agent.business.models import PerfilNegocio
    from sqlalchemy import select

    async with async_session() as session:
        row = (await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )).scalar_one_or_none()
    if row is None:
        return None
    return {
        "nombre_negocio": row.nombre_negocio,
        "industria": row.industria,
        "moneda": row.moneda,
        "meta_mensual": row.meta_mensual,
        "oferta_principal": row.oferta_principal,
        "cliente_ideal": row.cliente_ideal,
        "objetivo_mes": row.objetivo_mes,
        "canales_actuales": row.canales_actuales,
        "bloqueo_actual": row.bloqueo_actual,
        "tareas_delegar": row.tareas_delegar,
    }
