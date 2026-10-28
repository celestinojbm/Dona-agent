"""Selección de modelo y modo Auto (F23).

- Flag DONA_MULTI_MODEL_ENABLED apagado por defecto. Apagado → se usa el modelo
  por defecto (comportamiento actual), sin selector.
- Elección explícita por chat o por agente (persistida en preferencia_modelo).
- Cambio de modelo a mitad de conversación SIN perder contexto: el historial es
  model-agnostic (lista de {role, content}); cambiar de modelo sólo cambia qué
  proveedor atiende el próximo turno, el historial se pasa intacto.
- Modo Auto: elige modelo por clase de tarea y coste (determinístico).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from agent.multi_model.catalogo import existe, info_modelo, modelos_disponibles
from agent.multi_model.presupuesto import (
    PresupuestoAgenteAgotadoError,
    registrar_gasto,
    verificar_presupuesto,
)
from agent.multi_model.providers import (
    RespuestaModelo,
    multi_model_habilitado,
    proveedor_para,
)

logger = logging.getLogger("dona")

MODELO_POR_DEFECTO = "claude-sonnet-4-5"

# Tareas que premian capacidad sobre coste cuando hay presupuesto.
_TAREAS_POTENTES = frozenset({"planificacion", "razonamiento"})
# Por debajo de este presupuesto (créditos) Auto fuerza el modelo más barato.
UMBRAL_BARATO_CREDITOS = 5

# multi_model_habilitado() ahora vive en providers.py (la usa también como
# defensa en profundidad en proveedor_para); se reexporta vía el import de
# arriba — es la API pública histórica de este módulo.


@dataclass(frozen=True)
class EleccionModelo:
    modelo: str
    razon: str
    auto: bool = False


def elegir_auto(clase_tarea: str, presupuesto_creditos: int | None = None) -> EleccionModelo:
    """Elige modelo por tarea y coste (determinístico).

    - Candidatos = modelos cuyo catálogo declara la clase de tarea.
    - Presupuesto ajustado (<= UMBRAL_BARATO_CREDITOS) → el más barato.
    - Tareas potentes con presupuesto holgado → el más capaz (mayor nivel_coste).
    - Resto → el más barato que sirve.
    """
    candidatos = [m for m in modelos_disponibles() if clase_tarea in m.clases]
    if not candidatos:
        return EleccionModelo(MODELO_POR_DEFECTO, "sin_candidatos_default", auto=True)

    ajustado = presupuesto_creditos is not None and presupuesto_creditos <= UMBRAL_BARATO_CREDITOS
    if clase_tarea in _TAREAS_POTENTES and not ajustado:
        elegido = max(candidatos, key=lambda m: (m.nivel_coste, m.id))
        return EleccionModelo(elegido.id, "tarea_potente_mas_capaz", auto=True)

    elegido = min(candidatos, key=lambda m: (m.nivel_coste, m.id))
    razon = "presupuesto_ajustado_mas_barato" if ajustado else "mas_barato_que_sirve"
    return EleccionModelo(elegido.id, razon, auto=True)


def elegir(
    *,
    preferencia: str | None = None,
    clase_tarea: str = "conversacion",
    presupuesto_creditos: int | None = None,
    modo_auto: bool = False,
) -> EleccionModelo:
    """Resuelve qué modelo usar.

    - Flag apagado → siempre el modelo por defecto.
    - preferencia explícita y válida → ese modelo.
    - modo_auto → elegir_auto por tarea/coste.
    - Si no, modelo por defecto.
    """
    if not multi_model_habilitado():
        return EleccionModelo(MODELO_POR_DEFECTO, "flag_apagado")
    if preferencia and existe(preferencia):
        return EleccionModelo(preferencia, "preferencia_explicita")
    if preferencia and not existe(preferencia):
        return EleccionModelo(MODELO_POR_DEFECTO, "preferencia_invalida_default")
    if modo_auto:
        return elegir_auto(clase_tarea, presupuesto_creditos)
    return EleccionModelo(MODELO_POR_DEFECTO, "default")


def cambiar_modelo(historial: list[dict], nuevo_modelo: str) -> tuple[list[dict], str]:
    """Cambia de modelo a mitad de conversación sin perder contexto.

    Devuelve (historial_intacto, nuevo_modelo). El historial NO se modifica: es
    model-agnostic, así que el próximo turno lo atiende el nuevo proveedor con el
    mismo contexto. Lanza si el modelo no existe (no se cambia a algo inválido).
    """
    if not existe(nuevo_modelo):
        raise ValueError(f"modelo desconocido: {nuevo_modelo}")
    # Se devuelve el MISMO historial (sin copiar/mutar) → contexto preservado.
    return historial, nuevo_modelo


def _modelo_respaldo(modelo: str) -> str | None:
    """Modelo de RESPALDO del catálogo para `modelo` (riesgo 2 de PR #306 /
    issue #310). Si el catálogo no declara uno válido (inexistente o igual al
    que falló), cae a MODELO_POR_DEFECTO; si `modelo` YA es el por defecto y
    no tiene respaldo propio, retorna None (no hay a dónde caer)."""
    info = info_modelo(modelo)
    respaldo = info.respaldo if info else None
    if not respaldo or respaldo == modelo or not existe(respaldo):
        respaldo = MODELO_POR_DEFECTO if MODELO_POR_DEFECTO != modelo else None
    return respaldo


async def generar(
    *,
    modelo: str,
    mensajes: list[dict],
    system: str = "",
    max_tokens: int = 1024,
    permitir_fallback: bool = True,
    agente: str = "",
) -> RespuestaModelo:
    """Genera con el proveedor del modelo elegido (capa común).

    - Respeta DONA_MULTI_MODEL_ENABLED: si está APAGADO, se usa el proveedor
      simulado (NUNCA se llama a un proveedor real / API de pago).
    - Timeout + reintentos acotados: los adaptadores reales (providers.py)
      envuelven la llamada con `invocar_con_timeout_retry` (configurable por
      env `DONA_MODEL_TIMEOUT_S` / `DONA_MODEL_MAX_RETRIES`).
    - Fallback: si el proveedor del modelo falla (incluido timeout agotado),
      reintenta UNA sola vez contra el modelo de RESPALDO del catálogo
      (`ModeloInfo.respaldo`, preferentemente de otro proveedor) — no contra
      el mismo proveedor caído.
    - Presupuesto por agente (riesgo 3): si se pasa `agente`, cada intento se
      verifica ANTES de llamar a cualquier proveedor; al 100% del tope diario
      lanza `PresupuestoAgenteAgotadoError` sin llamar a nadie (ni siquiera al
      respaldo). Al 80% sólo avisa (logger.warning) y la llamada continúa.
    """
    permitir_real = multi_model_habilitado()

    verificar_presupuesto(agente)
    prov = proveedor_para(modelo, permitir_real=permitir_real)
    try:
        resp = await prov.generar(
            modelo=modelo, mensajes=mensajes, system=system, max_tokens=max_tokens
        )
    except PresupuestoAgenteAgotadoError:
        raise
    except Exception as e:  # noqa: BLE001
        respaldo = _modelo_respaldo(modelo) if permitir_fallback else None
        if respaldo is None:
            raise
        logger.warning(
            "[MULTI_MODEL] %s falló (%s); fallback a %s (respaldo del catálogo)",
            modelo, type(e).__name__, respaldo,
        )
        verificar_presupuesto(agente)  # el intento de respaldo también reserva
        provf = proveedor_para(respaldo, permitir_real=permitir_real)
        resp = await provf.generar(
            modelo=respaldo, mensajes=mensajes, system=system, max_tokens=max_tokens,
        )
    registrar_gasto(agente, resp.costo_usd)
    return resp
