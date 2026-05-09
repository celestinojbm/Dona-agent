# agent/automation/opportunities.py — Opportunity Engine (T2.1.A)

"""
Detecta oportunidades de negocio a partir del perfil del usuario
(tabla perfil_negocio post T2.0.E.1).

Diseño determinístico (sin LLM en T2.1.A · futuro PR puede agregar
LLM-as-judge para refinar/priorizar). Cada regla mira ciertos campos
del perfil y emite oportunidades con un playbook sugerido + razón.

Estructura de salida (lista de Oportunidad):
    {
        "id": str,            # único por (telefono, tipo)
        "tipo": str,          # ej. "mejorar_oferta", "calendario_contenido"
        "titulo": str,
        "descripcion": str,
        "razon": str,         # explica POR QUÉ se detectó
        "prioridad": int,     # 1 (alta) → 5 (baja)
        "impacto_estimado": str,  # texto · "alto" | "medio" | "bajo"
        "riesgo": str,        # del playbook sugerido
        "fuente_datos": list[str],  # campos de perfil_negocio usados
        "playbook_sugerido": str,
    }

Idempotencia: el campo `id` se construye a partir de (telefono, tipo)
para que regenerar oportunidades del mismo perfil no duplique entradas
en el Action Center (ver action_center.py:crear_accion).
"""

from __future__ import annotations

import hashlib
from typing import Any

from agent.automation.playbooks import obtener_playbook


def _id_oportunidad(telefono: str, tipo: str) -> str:
    """ID determinístico para idempotencia. Hash truncado del par
    (telefono, tipo) · evita PII en el ID."""
    h = hashlib.sha256(f"{telefono}:{tipo}".encode("utf-8")).hexdigest()
    return f"opp_{h[:16]}"


def _construir(
    *,
    telefono: str,
    tipo: str,
    titulo: str,
    descripcion: str,
    razon: str,
    prioridad: int,
    impacto: str,
    fuente: list[str],
    playbook_id: str,
) -> dict[str, Any]:
    """Helper que arma la dict completa de oportunidad enriquecida con
    riesgo del playbook sugerido."""
    pb = obtener_playbook(playbook_id)
    return {
        "id": _id_oportunidad(telefono, tipo),
        "tipo": tipo,
        "titulo": titulo,
        "descripcion": descripcion,
        "razon": razon,
        "prioridad": prioridad,
        "impacto_estimado": impacto,
        "riesgo": pb["riesgo"],
        "fuente_datos": fuente,
        "playbook_sugerido": playbook_id,
    }


# ── Reglas individuales · cada una mira el perfil y decide ─────────────────


def _detectar_mejorar_oferta(perfil: dict, telefono: str) -> list[dict]:
    """Si oferta_principal está vacía o el usuario reportó bloqueo, sugerir
    iterar la oferta."""
    tiene_oferta = bool(perfil.get("oferta_principal", "").strip())
    bloqueo = perfil.get("bloqueo_actual", "").strip()
    if tiene_oferta and not bloqueo:
        return []
    razon = (
        "Tu oferta principal aún no está definida con claridad."
        if not tiene_oferta
        else "Reportaste un bloqueo; iterar la oferta puede ayudar a destrabarlo."
    )
    return [
        _construir(
            telefono=telefono,
            tipo="mejorar_oferta",
            titulo="Iterar tu oferta principal",
            descripcion=(
                "Genera 3 alternativas de oferta apuntando a tu cliente "
                "ideal y al objetivo del mes."
            ),
            razon=razon,
            prioridad=1 if not tiene_oferta else 2,
            impacto="alto",
            fuente=["oferta_principal", "cliente_ideal", "bloqueo_actual"],
            playbook_id="mejora_oferta",
        )
    ]


def _detectar_calendario_contenido(perfil: dict, telefono: str) -> list[dict]:
    """Si el usuario tiene canales pero objetivo del mes es ambicioso,
    sugerir calendario."""
    canales = perfil.get("canales_actuales", "").strip()
    objetivo = perfil.get("objetivo_mes", "").strip()
    if not canales:
        return []
    razon = (
        "Tienes canales activos y un objetivo del mes — un calendario "
        "constante de 7 días te ayuda a ejecutarlo."
        if objetivo
        else "Tienes canales activos pero falta consistencia · un calendario "
             "te ayuda a publicar con ritmo."
    )
    return [
        _construir(
            telefono=telefono,
            tipo="calendario_contenido",
            titulo="Calendario de contenido para 7 días",
            descripcion=(
                "Plan de 7 publicaciones (1 por día) por canal, listas "
                "para revisar y publicar."
            ),
            razon=razon,
            prioridad=2,
            impacto="medio",
            fuente=["canales_actuales", "objetivo_mes", "oferta_principal"],
            playbook_id="calendario_contenido_7d",
        )
    ]


def _detectar_reactivacion(perfil: dict, telefono: str) -> list[dict]:
    """Si las tareas a delegar mencionan seguimiento/recuperar/reactivar,
    sugerir reactivación de clientes."""
    tareas = perfil.get("tareas_delegar", "").lower()
    triggers = ("seguimiento", "recuperar", "reactivar", "follow", "perdido")
    matched = [t for t in triggers if t in tareas]
    if not matched:
        return []
    return [
        _construir(
            telefono=telefono,
            tipo="reactivacion_clientes",
            titulo="Reactivar clientes que dejaron de comprar",
            descripcion=(
                "Borrador de mensaje cálido + lista lista para revisar "
                "antes de enviar."
            ),
            razon=(
                f"Mencionaste querer delegar tareas relacionadas con "
                f"'{matched[0]}'. Esto encaja con un playbook de "
                f"reactivación."
            ),
            prioridad=2,
            impacto="alto",
            fuente=["tareas_delegar", "cliente_ideal"],
            playbook_id="reactivacion_clientes",
        )
    ]


def _detectar_campana_whatsapp(perfil: dict, telefono: str) -> list[dict]:
    """Si los canales incluyen WhatsApp y hay una oferta clara, sugerir
    una campaña corta."""
    canales = perfil.get("canales_actuales", "").lower()
    oferta = perfil.get("oferta_principal", "").strip()
    if "whatsapp" not in canales:
        return []
    if not oferta:
        return []
    return [
        _construir(
            telefono=telefono,
            tipo="campana_whatsapp_simple",
            titulo="Campaña simple de WhatsApp",
            descripcion=(
                "Secuencia de 3 mensajes (anuncio · recordatorio · "
                "último día) sobre tu oferta. Lista para revisar."
            ),
            razon=(
                "Mencionaste WhatsApp como canal y tienes una oferta "
                "definida; una campaña corta es de bajo costo."
            ),
            prioridad=3,
            impacto="medio",
            fuente=["canales_actuales", "oferta_principal", "cliente_ideal"],
            playbook_id="campana_whatsapp_simple",
        )
    ]


def _detectar_checklist_ventas(perfil: dict, telefono: str) -> list[dict]:
    """Si hay bloqueo reportado, sugerir checklist comercial."""
    bloqueo = perfil.get("bloqueo_actual", "").strip()
    if not bloqueo:
        return []
    return [
        _construir(
            telefono=telefono,
            tipo="checklist_ventas",
            titulo="Checklist comercial para destrabar ventas",
            descripcion=(
                "Lista práctica de 8-12 puntos accionables esta semana."
            ),
            razon=(
                "Reportaste un bloqueo. Un checklist corto evita parálisis "
                "y da próximas acciones concretas."
            ),
            prioridad=2,
            impacto="medio",
            fuente=["bloqueo_actual", "tareas_delegar"],
            playbook_id="checklist_ventas",
        )
    ]


def _detectar_plan_semanal(perfil: dict, telefono: str) -> list[dict]:
    """Si el perfil está completo (todos los campos T2.0.E.1 llenos),
    sugerir plan semanal · es la oportunidad 'cierre' del onboarding."""
    requeridos = (
        "oferta_principal", "cliente_ideal", "objetivo_mes",
        "canales_actuales", "bloqueo_actual", "tareas_delegar",
    )
    llenos = sum(1 for k in requeridos if perfil.get(k, "").strip())
    if llenos < 4:  # exigimos al menos 4 de 6
        return []
    return [
        _construir(
            telefono=telefono,
            tipo="plan_semanal",
            titulo="Convertir tu diagnóstico en un plan semanal",
            descripcion=(
                "Plan de 5-7 acciones priorizadas para la semana, "
                "alineadas a tu objetivo del mes."
            ),
            razon=(
                f"Tu diagnóstico tiene {llenos}/6 campos llenos. Suficiente "
                f"para que Dona te genere un plan focalizado."
            ),
            prioridad=1,
            impacto="alto",
            fuente=list(requeridos),
            playbook_id="diagnostico_a_plan_semanal",
        )
    ]


# ── API pública ─────────────────────────────────────────────────────────────


REGLAS = (
    _detectar_plan_semanal,
    _detectar_mejorar_oferta,
    _detectar_calendario_contenido,
    _detectar_reactivacion,
    _detectar_campana_whatsapp,
    _detectar_checklist_ventas,
)


def detectar_oportunidades(perfil: dict, telefono: str) -> list[dict[str, Any]]:
    """Aplica todas las reglas y retorna oportunidades ordenadas por prioridad.

    Args:
        perfil: dict con los campos del perfil_negocio (puede ser un
                ORM .__dict__ o un dict crudo).
        telefono: para construir el ID idempotente sin filtrarlo.

    Returns:
        Lista de oportunidades con todos los campos · ordenadas por
        prioridad ascendente (1 = más alta).
    """
    todas: list[dict] = []
    for regla in REGLAS:
        todas.extend(regla(perfil, telefono))
    todas.sort(key=lambda o: (o["prioridad"], o["tipo"]))
    return todas


async def detectar_oportunidades_para_telefono(
    telefono: str,
) -> list[dict[str, Any]]:
    """Lee el perfil_negocio de DB y detecta oportunidades.

    Returns lista vacía si el perfil no existe o no tiene nombre_negocio
    (onboarding incompleto).
    """
    from agent.memory import async_session
    from agent.business.models import PerfilNegocio
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
    if not perfil or not perfil.nombre_negocio:
        return []
    perfil_dict = {
        "nombre_negocio": perfil.nombre_negocio,
        "industria": perfil.industria,
        "moneda": perfil.moneda,
        "meta_mensual": perfil.meta_mensual,
        "oferta_principal": perfil.oferta_principal,
        "cliente_ideal": perfil.cliente_ideal,
        "objetivo_mes": perfil.objetivo_mes,
        "canales_actuales": perfil.canales_actuales,
        "bloqueo_actual": perfil.bloqueo_actual,
        "tareas_delegar": perfil.tareas_delegar,
    }
    return detectar_oportunidades(perfil_dict, telefono)
