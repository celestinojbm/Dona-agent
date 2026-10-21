"""Evaluador determinístico de la política de autonomía (F1).

El modelo sólo propone; esta función decide. Nunca fabrica autorización a partir
de texto del usuario o de contenido externo: evalúa sobre la configuración
persistida (`AutonomiaPorAccion`) y la cotización calculada por el backend.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

# Tipos de acción SIEMPRE reservados a aprobación humana explícita,
# independientemente del nivel configurado (permisos, autonomía, credenciales,
# acciones destructivas, envíos a terceros).
TIPOS_SIEMPRE_HUMANOS: frozenset[str] = frozenset(
    {
        "permisos",
        "autonomia",
        "credenciales",
        "destructiva",
        "envio_tercero",
    }
)


def autonomia_habilitada() -> bool:
    """Si está apagado (default), TODO exige confirmación humana."""
    return os.getenv("DONA_AUTONOMY_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def hash_argumentos(args: dict | None) -> str:
    """sha256 de los argumentos canónicos (claves ordenadas). Un cambio de
    argumentos cambia el hash → invalida una autorización preexistente."""
    canon = json.dumps(args or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DecisionPolitica:
    requiere_humano: bool
    origen: str  # "humana" | "politica"
    razon: str
    notificar: bool = False  # L3 ejecuta y notifica


def evaluar_politica(
    *,
    tipo_accion: str,
    cotizacion_creditos: int,
    config,  # AutonomiaPorAccion | None
    consumo_periodo_creditos: int = 0,
    destinatario_autorizado: bool = True,
) -> DecisionPolitica:
    """Decide si la acción requiere confirmación humana o puede autoautorizarse.

    Reglas:
    - Flag apagado → siempre humano.
    - Tipos siempre-humanos → humano.
    - Envío a tercero sin destinatario/alcance autorizado → humano.
    - Sin config o nivel 1 → humano.
    - Nivel 2 → auto si hay umbral y cotización <= umbral.
    - Nivel 3 → auto (y notifica) si la acción está permitida (hay config).
    - Nivel 4 → auto si hay tope de periodo y consumo+cotización <= tope.
    - Un tope_por_accion presente se respeta en L2/L3/L4.
    - NULL en un tope NUNCA significa ilimitado: sin tope no autoriza.
    """
    if not autonomia_habilitada():
        return DecisionPolitica(True, "humana", "autonomia_desactivada")

    if tipo_accion in TIPOS_SIEMPRE_HUMANOS:
        return DecisionPolitica(True, "humana", "tipo_siempre_humano")

    if tipo_accion == "envio_tercero" and not destinatario_autorizado:
        return DecisionPolitica(True, "humana", "destinatario_no_autorizado")

    if config is None or int(getattr(config, "nivel", 1)) <= 1:
        return DecisionPolitica(True, "humana", "nivel_1_o_sin_config")

    nivel = int(config.nivel)

    # Tope por acción (si está definido) aplica a cualquier nivel auto.
    tope_accion = getattr(config, "tope_por_accion", None)
    if tope_accion is not None and cotizacion_creditos > int(tope_accion):
        return DecisionPolitica(True, "humana", "supera_tope_por_accion")

    if nivel == 2:
        umbral = getattr(config, "umbral_creditos", None)
        if umbral is None:
            return DecisionPolitica(True, "humana", "l2_sin_umbral")
        if cotizacion_creditos <= int(umbral):
            return DecisionPolitica(False, "politica", "l2_bajo_umbral")
        return DecisionPolitica(True, "humana", "l2_sobre_umbral")

    if nivel == 3:
        # Ejecuta tipos permitidos (existe config para este tipo) y notifica.
        return DecisionPolitica(False, "politica", "l3_permitido", notificar=True)

    if nivel == 4:
        tope_periodo = getattr(config, "tope_periodo", None)
        if tope_periodo is None:
            # Sin tope de periodo NO es ilimitado: requiere humano.
            return DecisionPolitica(True, "humana", "l4_sin_tope")
        if consumo_periodo_creditos + cotizacion_creditos <= int(tope_periodo):
            return DecisionPolitica(False, "politica", "l4_dentro_presupuesto")
        return DecisionPolitica(True, "humana", "l4_supera_presupuesto")

    return DecisionPolitica(True, "humana", "nivel_desconocido")
