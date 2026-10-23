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

# Clases de acción. Decisión de Celestino #8: sólo LECTURA y BORRADOR pueden
# auto-ejecutarse sin confirmar (no gastan ni envían). GASTO sigue los niveles
# L1–L4 con umbrales; ENVIO (a terceros) siempre es humano.
CLASES_SEGURAS_AUTO: frozenset[str] = frozenset({"lectura", "borrador"})

# Defaults de autonomía (decisión de Celestino #9). Zona para la ventana del
# "día" del tope diario.
UMBRAL_L2_DEFECTO = 10        # créditos por acción (L2)
TOPE_DIARIO_DEFECTO = 100     # créditos por día (tope global de auto-gasto)
ZONA_PERIODO_DEFECTO = "America/New_York"


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
    clase_accion: str = "gasto",
) -> DecisionPolitica:
    """Decide si la acción requiere confirmación humana o puede autoautorizarse.

    Reglas (con las decisiones de Celestino #8 y #9):
    - Flag apagado → siempre humano (interruptor maestro).
    - Tipos siempre-humanos → humano.
    - Envío a tercero sin destinatario/alcance autorizado → humano.
    - Clase LECTURA o BORRADOR → auto (no gastan ni envían): #8.
    - Clase ENVIO → humano (los envíos son siempre explícitos).
    - Clase GASTO → niveles L1–L4:
        * L1 o sin config → humano.
        * Tope por acción (si está) se respeta.
        * Tope diario SIEMPRE aplica: consumo_periodo + cotización <= tope_día.
          tope_día = config.tope_periodo si está, si no TOPE_DIARIO_DEFECTO (100).
        * L2 → auto si cotización <= umbral (config.umbral_creditos o
          UMBRAL_L2_DEFECTO=10) y dentro del tope diario.
        * L3 → auto+notifica dentro del tope diario.
        * L4 → auto dentro del tope diario.
    """
    if not autonomia_habilitada():
        return DecisionPolitica(True, "humana", "autonomia_desactivada")

    if tipo_accion in TIPOS_SIEMPRE_HUMANOS:
        return DecisionPolitica(True, "humana", "tipo_siempre_humano")

    if tipo_accion == "envio_tercero" and not destinatario_autorizado:
        return DecisionPolitica(True, "humana", "destinatario_no_autorizado")

    # #8: lectura y borrador no gastan ni envían → auto seguro.
    if clase_accion in CLASES_SEGURAS_AUTO:
        return DecisionPolitica(False, "politica", "clase_lectura_o_borrador")

    # Envíos: siempre humanos (además de envio_tercero en siempre-humanos).
    if clase_accion == "envio":
        return DecisionPolitica(True, "humana", "envio_siempre_humano")

    # Clase gasto (default): niveles.
    if config is None or int(getattr(config, "nivel", 1)) <= 1:
        return DecisionPolitica(True, "humana", "nivel_1_o_sin_config")

    nivel = int(config.nivel)

    # Tope por acción (si está definido) aplica a cualquier nivel auto.
    tope_accion = getattr(config, "tope_por_accion", None)
    if tope_accion is not None and cotizacion_creditos > int(tope_accion):
        return DecisionPolitica(True, "humana", "supera_tope_por_accion")

    # Tope diario (default 100) SIEMPRE aplica al auto-gasto.
    tope_periodo = getattr(config, "tope_periodo", None)
    tope_dia = int(tope_periodo) if tope_periodo is not None else TOPE_DIARIO_DEFECTO
    if consumo_periodo_creditos + cotizacion_creditos > tope_dia:
        return DecisionPolitica(True, "humana", "supera_tope_diario")

    if nivel == 2:
        umbral = getattr(config, "umbral_creditos", None)
        umbral_ef = int(umbral) if umbral is not None else UMBRAL_L2_DEFECTO
        if cotizacion_creditos <= umbral_ef:
            return DecisionPolitica(False, "politica", "l2_bajo_umbral")
        return DecisionPolitica(True, "humana", "l2_sobre_umbral")

    if nivel == 3:
        return DecisionPolitica(False, "politica", "l3_permitido", notificar=True)

    if nivel == 4:
        return DecisionPolitica(False, "politica", "l4_dentro_presupuesto")

    return DecisionPolitica(True, "humana", "nivel_desconocido")
