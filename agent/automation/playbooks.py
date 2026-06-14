# agent/automation/playbooks.py — Playbook Engine (T2.1.A)

"""
Catálogo estático de playbooks. Cada playbook es una estructura
estandarizada que combina varias acciones para alcanzar un objetivo
de negocio.

Estructura:
    {
        "id": str,
        "nombre": str,
        "objetivo": str,
        "pasos": [{"tipo_accion": str, "titulo": str, ...}],
        "herramientas_requeridas": list[str],
        "riesgo": NivelRiesgo (el riesgo MAXIMO de los pasos),
        "costo_creditos_estimado": int,
        "requires_approval": bool,
        "outputs_esperados": list[str],
    }

T2.1.A entrega los 6 playbooks fundacionales sugeridos. Cada uno tiene
solo pasos LOW/MEDIUM en T2.1.A · los pasos HIGH/CRITICAL existen en
las definiciones para que futuros PRs (T2.1.C) puedan ejecutar el
playbook completo cuando se desbloquee la ejecución externa.
"""

from __future__ import annotations

from typing import Any

from agent.automation.costos import estimar_costo_playbook
from agent.automation.permissions import (
    NivelRiesgo,
    clasificar_riesgo,
    requiere_aprobacion,
)

# ── Pasos por playbook ──────────────────────────────────────────────────────

# Cada paso es un dict mínimo: tipo_accion + titulo + descripcion.
# El motor calcula el riesgo y el costo a partir de tipo_accion.

_PASOS_DIAGNOSTICO_A_PLAN_SEMANAL = [
    {
        "tipo_accion": "analizar_diagnostico",
        "titulo": "Analizar diagnóstico del negocio",
        "descripcion": (
            "Revisar campos del perfil (oferta, cliente ideal, objetivo, "
            "canales, bloqueo, tareas a delegar) y extraer foco de la semana."
        ),
    },
    {
        "tipo_accion": "generar_plan_semanal",
        "titulo": "Generar plan semanal",
        "descripcion": (
            "Producir un plan de 5-7 acciones priorizadas para la semana, "
            "alineadas al objetivo del mes."
        ),
    },
]

_PASOS_CALENDARIO_CONTENIDO_7D = [
    {
        "tipo_accion": "analizar_diagnostico",
        "titulo": "Analizar canales y oferta",
        "descripcion": "Identificar formato de contenido por canal del usuario.",
    },
    {
        "tipo_accion": "generar_calendario_contenido",
        "titulo": "Generar calendario de 7 días",
        "descripcion": (
            "Producir 7 ideas de publicación (1 por día) con copy sugerido "
            "y hashtags por canal."
        ),
    },
    {
        "tipo_accion": "preparar_publicacion_redes",
        "titulo": "Preparar borradores de publicaciones",
        "descripcion": "Convertir cada idea en borrador listo para revisión.",
    },
]

_PASOS_REACTIVACION_CLIENTES = [
    {
        "tipo_accion": "analizar_diagnostico",
        "titulo": "Identificar cliente ideal y oferta",
        "descripcion": "Tomar oferta y cliente ideal del perfil.",
    },
    {
        "tipo_accion": "borrador_copy_oferta",
        "titulo": "Borrador de mensaje de reactivación",
        "descripcion": "Texto cálido para clientes que dejaron de comprar.",
    },
    {
        "tipo_accion": "preparar_mensaje_whatsapp",
        "titulo": "Preparar mensaje WhatsApp listo para revisar",
        "descripcion": (
            "Convertir el borrador en mensaje listo para que el usuario lo "
            "revise antes de enviarlo."
        ),
    },
    # HIGH · solo se ejecuta tras aprobación explícita en futuro PR
    {
        "tipo_accion": "enviar_mensaje_whatsapp",
        "titulo": "Enviar mensaje a clientes seleccionados",
        "descripcion": (
            "Envío real al subset de clientes seleccionados por el usuario. "
            "Bloqueado en T2.1.A · requiere aprobación + ejecutor externo."
        ),
    },
]

_PASOS_MEJORA_OFERTA = [
    {
        "tipo_accion": "analizar_diagnostico",
        "titulo": "Auditar oferta actual y bloqueo",
        "descripcion": "Revisar campo oferta_principal y bloqueo_actual.",
    },
    {
        "tipo_accion": "generar_idea_oferta",
        "titulo": "Sugerir 3 mejoras de oferta",
        "descripcion": (
            "Tres alternativas concretas de oferta basadas en cliente ideal "
            "y objetivo del mes."
        ),
    },
    {
        "tipo_accion": "borrador_copy_oferta",
        "titulo": "Borradores de copy para cada alternativa",
        "descripcion": "Copy listo para que el usuario elija y publique.",
    },
]

_PASOS_CAMPANA_WHATSAPP_SIMPLE = [
    {
        "tipo_accion": "analizar_diagnostico",
        "titulo": "Validar oferta y cliente ideal",
        "descripcion": "Revisar perfil para validar que la campaña tiene sentido.",
    },
    {
        "tipo_accion": "preparar_campana_whatsapp",
        "titulo": "Preparar campaña de 3 mensajes",
        "descripcion": (
            "Secuencia de 3 mensajes (anuncio, recordatorio, último día) "
            "lista para revisar."
        ),
    },
    # HIGH · futuro PR
    {
        "tipo_accion": "enviar_campana_masiva",
        "titulo": "Lanzar campaña a clientes opt-in",
        "descripcion": (
            "Envío real al subset opt-in (TCPA cumplido). Bloqueado en "
            "T2.1.A · requiere aprobación + ejecutor externo + verificación "
            "TCPA."
        ),
    },
]

_PASOS_CHECKLIST_VENTAS = [
    {
        "tipo_accion": "analizar_diagnostico",
        "titulo": "Identificar bloqueo de ventas",
        "descripcion": "Tomar campo bloqueo_actual y tareas_delegar.",
    },
    {
        "tipo_accion": "generar_checklist_ventas",
        "titulo": "Generar checklist comercial",
        "descripcion": (
            "Lista práctica de 8-12 puntos para destrabar ventas esta semana."
        ),
    },
]


# ── Catálogo de playbooks ───────────────────────────────────────────────────

_DEFINICIONES_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "diagnostico_a_plan_semanal": {
        "nombre": "Diagnóstico a plan semanal",
        "objetivo": "Convertir el diagnóstico del negocio en un plan accionable de la semana.",
        "pasos": _PASOS_DIAGNOSTICO_A_PLAN_SEMANAL,
        "herramientas_requeridas": ["llm"],
        "outputs_esperados": ["plan_semanal_md"],
    },
    "calendario_contenido_7d": {
        "nombre": "Calendario de contenido 7 días",
        "objetivo": "Producir un plan de contenido de 7 días alineado al cliente ideal.",
        "pasos": _PASOS_CALENDARIO_CONTENIDO_7D,
        "herramientas_requeridas": ["llm"],
        "outputs_esperados": ["calendario_md", "borradores_publicaciones"],
    },
    "reactivacion_clientes": {
        "nombre": "Reactivación de clientes",
        "objetivo": "Recuperar clientes que dejaron de comprar.",
        "pasos": _PASOS_REACTIVACION_CLIENTES,
        "herramientas_requeridas": ["llm", "whatsapp_provider"],
        "outputs_esperados": ["mensaje_reactivacion_md", "lista_envio_pendiente"],
    },
    "mejora_oferta": {
        "nombre": "Mejora de oferta",
        "objetivo": "Iterar la oferta principal del negocio.",
        "pasos": _PASOS_MEJORA_OFERTA,
        "herramientas_requeridas": ["llm"],
        "outputs_esperados": ["alternativas_oferta_md", "copy_oferta_md"],
    },
    "campana_whatsapp_simple": {
        "nombre": "Campaña simple de WhatsApp",
        "objetivo": "Lanzar una campaña corta (3 mensajes) sobre la oferta principal.",
        "pasos": _PASOS_CAMPANA_WHATSAPP_SIMPLE,
        "herramientas_requeridas": ["llm", "whatsapp_provider"],
        "outputs_esperados": ["campana_3_mensajes_md", "lista_opt_in_pendiente"],
    },
    "checklist_ventas": {
        "nombre": "Checklist de ventas",
        "objetivo": "Generar lista comercial práctica para destrabar ventas.",
        "pasos": _PASOS_CHECKLIST_VENTAS,
        "herramientas_requeridas": ["llm"],
        "outputs_esperados": ["checklist_md"],
    },
}


# ── API pública ─────────────────────────────────────────────────────────────


def listar_playbooks() -> list[dict[str, Any]]:
    """Retorna todos los playbooks disponibles ya enriquecidos con riesgo,
    costo, requires_approval. Útil para el dashboard / admin."""
    return [
        obtener_playbook(playbook_id)
        for playbook_id in _DEFINICIONES_PLAYBOOKS
    ]


def existe_playbook(playbook_id: str) -> bool:
    return playbook_id in _DEFINICIONES_PLAYBOOKS


def obtener_playbook(playbook_id: str) -> dict[str, Any]:
    """Obtiene un playbook con campos derivados (riesgo, costo, approval).

    Raises:
        KeyError si playbook_id no existe.
    """
    if playbook_id not in _DEFINICIONES_PLAYBOOKS:
        raise KeyError(f"Playbook desconocido: {playbook_id}")
    base = _DEFINICIONES_PLAYBOOKS[playbook_id]
    pasos = base["pasos"]
    riesgo_max = _riesgo_maximo(pasos)
    costo = estimar_costo_playbook(pasos)
    return {
        "id": playbook_id,
        "nombre": base["nombre"],
        "objetivo": base["objetivo"],
        "pasos": pasos,
        "herramientas_requeridas": base["herramientas_requeridas"],
        "riesgo": riesgo_max.value,
        "costo_creditos_estimado": costo,
        "requires_approval": requiere_aprobacion(riesgo_max),
        "outputs_esperados": base["outputs_esperados"],
    }


def _riesgo_maximo(pasos: list[dict]) -> NivelRiesgo:
    """Riesgo maximo entre los pasos · ordering low<medium<high<critical."""
    ORDEN = {
        NivelRiesgo.LOW: 0,
        NivelRiesgo.MEDIUM: 1,
        NivelRiesgo.HIGH: 2,
        NivelRiesgo.CRITICAL: 3,
    }
    nivel_max = NivelRiesgo.LOW
    for paso in pasos:
        r = clasificar_riesgo(paso.get("tipo_accion", ""))
        if ORDEN[r] > ORDEN[nivel_max]:
            nivel_max = r
    return nivel_max
