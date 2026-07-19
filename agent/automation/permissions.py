# agent/automation/permissions.py — Permission & Risk System (T2.1.A)

"""
Clasificación de riesgo y reglas de auto-ejecución.

Cuatro niveles:
    low      — borradores, planes, ideas, análisis. Sin efecto externo.
               Auto-ejecutable.
    medium   — preparar mensajes, campañas, publicaciones.
               Requiere aprobación simple del usuario.
    high     — enviar mensajes, publicar, contactar leads,
               consumir muchos créditos. Requiere aprobación explícita.
    critical — gastar dinero, borrar datos, cambios de configuración,
               envíos masivos. Bloqueado en T2.1.A. Requiere
               confirmación fuerte (futuro PR).

Diseño puro · sin DB · función-only para máxima testabilidad.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal


class NivelRiesgo(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Tipos de acción y su nivel de riesgo. Cualquier tipo NO listado se
# considera CRITICAL (fail-closed): un tipo que nadie clasificó no tiene
# base para asumirse inocuo — queda bloqueado hasta agregarse aquí.
RIESGO_POR_TIPO_ACCION: dict[str, NivelRiesgo] = {
    # LOW · solo generación interna · cero efecto externo
    "generar_plan_semanal": NivelRiesgo.LOW,
    "generar_calendario_contenido": NivelRiesgo.LOW,
    "generar_checklist_ventas": NivelRiesgo.LOW,
    "analizar_diagnostico": NivelRiesgo.LOW,
    "generar_idea_oferta": NivelRiesgo.LOW,
    # MEDIUM · prepara contenido externo pero no lo envía
    "preparar_mensaje_whatsapp": NivelRiesgo.MEDIUM,
    "preparar_campana_whatsapp": NivelRiesgo.MEDIUM,
    "preparar_publicacion_redes": NivelRiesgo.MEDIUM,
    "preparar_email_seguimiento": NivelRiesgo.MEDIUM,
    "borrador_copy_oferta": NivelRiesgo.MEDIUM,
    # HIGH · efecto externo real (no se ejecuta en T2.1.A)
    # enviar_correo_gmail: acción persistente del PR 1 de correo. Metadata y
    # contrato solamente — NO está registrada en EJECUTORES_T21A y en PR 1 la
    # confirmación mantiene needs_approval (fail-closed, sin materialización).
    "enviar_correo_gmail": NivelRiesgo.HIGH,
    "enviar_mensaje_whatsapp": NivelRiesgo.HIGH,
    "enviar_campana_masiva": NivelRiesgo.HIGH,
    "publicar_red_social": NivelRiesgo.HIGH,
    "contactar_lead": NivelRiesgo.HIGH,
    # CRITICAL · efecto irreversible · bloqueado
    "gastar_creditos_masivo": NivelRiesgo.CRITICAL,
    "borrar_datos_negocio": NivelRiesgo.CRITICAL,
    "cambiar_config_cuenta": NivelRiesgo.CRITICAL,
    "envio_masivo_clientes": NivelRiesgo.CRITICAL,
}


def clasificar_riesgo(tipo_accion: str) -> NivelRiesgo:
    """Clasifica un tipo de acción. Si no está en la tabla, retorna CRITICAL
    (fail-closed, C4 del audit): el default MEDIUM anterior era fail-open —
    un tipo inventado/spoofeado (p.ej. alucinado por el LLM) obtenía
    aprobación simple en vez de bloqueo. Lo no clasificado se bloquea."""
    return RIESGO_POR_TIPO_ACCION.get(tipo_accion, NivelRiesgo.CRITICAL)


def requiere_aprobacion(riesgo: NivelRiesgo | str) -> bool:
    """True si la acción requiere aprobación humana antes de ejecutar.
    LOW puede auto-ejecutar. MEDIUM/HIGH/CRITICAL requieren aprobación."""
    r = NivelRiesgo(riesgo) if isinstance(riesgo, str) else riesgo
    return r != NivelRiesgo.LOW


def puede_auto_ejecutar(riesgo: NivelRiesgo | str) -> bool:
    """True si puede ejecutarse automáticamente sin aprobación humana.
    Solo LOW. Las demás necesitan paso explícito."""
    r = NivelRiesgo(riesgo) if isinstance(riesgo, str) else riesgo
    return r == NivelRiesgo.LOW


def esta_bloqueado_t21(riesgo: NivelRiesgo | str) -> bool:
    """True si la acción está bloqueada en T2.1.A · CRITICAL nunca se
    ejecuta (ni siquiera con aprobación). Se desbloquea en futuro PR
    cuando agreguemos confirmación fuerte de doble factor."""
    r = NivelRiesgo(riesgo) if isinstance(riesgo, str) else riesgo
    return r == NivelRiesgo.CRITICAL


def estado_inicial_para_riesgo(riesgo: NivelRiesgo | str) -> str:
    """Estado inicial de una acción recién creada según su riesgo.
    LOW → 'pending' (puede pasar a 'running' automáticamente).
    MEDIUM/HIGH → 'needs_approval'.
    CRITICAL → 'needs_approval' (pero queda bloqueada en T2.1.A).
    """
    r = NivelRiesgo(riesgo) if isinstance(riesgo, str) else riesgo
    if r == NivelRiesgo.LOW:
        return "pending"
    return "needs_approval"


# Estados válidos del lifecycle de una acción
ESTADOS_VALIDOS = {
    "pending",          # creada, esperando ejecución (LOW)
    "needs_approval",   # esperando aprobación (MEDIUM/HIGH/CRITICAL)
    "approved",         # aprobada, lista para ejecutar
    "running",          # en ejecución
    "completed",        # ejecutada con éxito
    "rejected",         # rechazada por el usuario
    "failed",           # error durante ejecución
    "cancelled",        # cancelada antes de ejecutar
}

# Transiciones permitidas: estado_actual → set de estados destino válidos.
# `approved → failed` (5.2): una acción aprobada puede fallar ANTES de
# transicionar a running — p.ej. una CRITICAL bloqueada por el gate de riesgo
# que ya no necesita pasar por running solo para poder marcarse failed.
TRANSICIONES: dict[str, set[str]] = {
    "pending": {"running", "cancelled", "rejected"},
    "needs_approval": {"approved", "rejected", "cancelled"},
    "approved": {"running", "cancelled", "failed"},
    "running": {"completed", "failed"},
    "completed": set(),
    "rejected": set(),
    "failed": set(),
    "cancelled": set(),
}


def transicion_valida(
    actual: str,
    destino: str,
    riesgo: NivelRiesgo | str | None = None,
) -> bool:
    """True si la transición de estado es válida.

    Validación base: ``destino`` debe estar en ``TRANSICIONES[actual]``.

    Si se pasa ``riesgo`` (5.2 · C4/A13), aplica además el gate fail-closed del
    eslabón "permiso→ejecución" del core loop sobre el destino ``running``:

      - CRITICAL nunca alcanza ``running`` (bloqueada hasta tener confirmación
        reforzada · futuro PR). Aplica desde cualquier estado origen.
      - Sólo LOW puede auto-ejecutarse desde ``pending``. MEDIUM/HIGH deben
        pasar por ``approved`` (aprobación humana) antes de ``running``.

    Las transiciones que NO son a ``running`` (rechazar, cancelar, aprobar,
    completar, fallar) no se ven afectadas por el riesgo: una CRITICAL puede
    rechazarse o cancelarse con normalidad.

    ``riesgo=None`` mantiene el comportamiento legacy de 2 argumentos.
    """
    if actual not in ESTADOS_VALIDOS or destino not in ESTADOS_VALIDOS:
        return False
    if destino not in TRANSICIONES.get(actual, set()):
        return False
    if riesgo is None:
        return True
    r = NivelRiesgo(riesgo) if isinstance(riesgo, str) else riesgo
    if destino == "running":
        if r == NivelRiesgo.CRITICAL:
            return False
        if actual == "pending" and r != NivelRiesgo.LOW:
            return False
    return True


# ── Contrato explícito "siguiente acción requerida" ─────────────────────
#
# Valores estables que la API expone para que cualquier cliente (dashboard,
# admin, bridge interno) sepa qué control debe operar la acción ahora sin
# tener que reimplementar la matriz (estado × riesgo).
#
#   execute_available               · listo para ejecutarse por el control
#                                     genérico del Action Center
#   approval_required               · espera aprobación humana simple
#   dedicated_confirmation_required · aprobado, pero requiere UX dedicada
#                                     con preview/costo/riesgo antes de
#                                     efecto externo real (HIGH approved)
#   reinforced_approval_required    · CRITICAL · bloqueado · necesita
#                                     confirmación reforzada (futura)
#   none                            · terminal o en ejecución · no ofrecer
#                                     siguiente control sobre la acción
NextRequiredAction = Literal[
    "execute_available",
    "approval_required",
    "dedicated_confirmation_required",
    "reinforced_approval_required",
    "none",
]


# Razones cortas de bloqueo · texto plano en español. Se usan tanto para
# que la API explique el motivo como para que la UI pueda renderizarlas
# directamente si no quiere construir su propia copia.
_MOTIVO_HIGH_APROBADA = (
    "Requiere confirmación dedicada con preview, costo y riesgo antes "
    "de cualquier efecto externo real."
)
_MOTIVO_CRITICAL = (
    "Acción crítica · bloqueada por defecto · requiere confirmación "
    "reforzada futura."
)


def calcular_next_required_action(
    estado: str, riesgo: str,
) -> tuple[str, str]:
    """Devuelve (next_required_action, execution_block_reason) para una
    combinación (estado, riesgo).

    Es función pura · no toca DB ni red. La usa _a_dict para hacer el
    contrato explícito en cada acción serializada del Action Center.
    """
    estado_terminal = {"completed", "rejected", "failed", "cancelled"}
    if estado in estado_terminal:
        return "none", ""
    # running ya está en ejecución · ningún control adicional aplica
    if estado == "running":
        return "none", ""

    if riesgo == "critical":
        # CRITICAL bloqueado por defecto · aun aprobado no se ejecuta por
        # el control genérico hasta tener UX de confirmación reforzada.
        return "reinforced_approval_required", _MOTIVO_CRITICAL

    if riesgo == "high":
        if estado == "approved":
            return "dedicated_confirmation_required", _MOTIVO_HIGH_APROBADA
        if estado == "needs_approval":
            return "approval_required", ""
        # high/pending legacy o bug: pending → approved no es transición
        # válida; no ofrecer ningún control genérico.
        return "none", ""

    # low / medium · cada riesgo abre ejecución solo si su estado lo
    # justifica. LOW puede auto-ejecutar desde pending. MEDIUM exige
    # aprobación humana primero · pending/medium aquí solo ocurre por
    # datos legacy o por un bug, y NO se debe ofrecer ningún control
    # genérico: TRANSICIONES sólo permite pending → running/cancelled/
    # rejected, así que aprobar desde pending sería transición inválida
    # y la UI estaría engañando al usuario.
    if estado == "needs_approval":
        return "approval_required", ""
    if riesgo == "low" and estado in {"pending", "approved"}:
        return "execute_available", ""
    if riesgo == "medium" and estado == "approved":
        return "execute_available", ""
    # Fallback defensivo · cualquier otra combinación (incluido
    # medium/pending legacy) se trata como none: ningún botón del control
    # genérico aplica.
    return "none", ""


EstadoAccion = Literal[
    "pending", "needs_approval", "approved", "running",
    "completed", "rejected", "failed", "cancelled",
]
