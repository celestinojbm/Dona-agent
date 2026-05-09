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


# Tipos de acción y su nivel de riesgo. Cualquier tipo no listado
# se considera medium por defecto (requiere aprobación simple).
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
    """Clasifica un tipo de acción. Si no está en la tabla, retorna MEDIUM
    (default seguro · requiere aprobación)."""
    return RIESGO_POR_TIPO_ACCION.get(tipo_accion, NivelRiesgo.MEDIUM)


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

# Transiciones permitidas: estado_actual → set de estados destino válidos
TRANSICIONES: dict[str, set[str]] = {
    "pending": {"running", "cancelled", "rejected"},
    "needs_approval": {"approved", "rejected", "cancelled"},
    "approved": {"running", "cancelled"},
    "running": {"completed", "failed"},
    "completed": set(),
    "rejected": set(),
    "failed": set(),
    "cancelled": set(),
}


def transicion_valida(actual: str, destino: str) -> bool:
    """True si la transición de estado es válida según TRANSICIONES."""
    if actual not in ESTADOS_VALIDOS or destino not in ESTADOS_VALIDOS:
        return False
    return destino in TRANSICIONES.get(actual, set())


EstadoAccion = Literal[
    "pending", "needs_approval", "approved", "running",
    "completed", "rejected", "failed", "cancelled",
]
