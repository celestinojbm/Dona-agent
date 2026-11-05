"""Combinación de modelos (F23).

Dos formas:
- `planificar_y_ejecutar`: un modelo planifica y otro ejecuta cada paso.
- `comparar_lado_a_lado`: varios modelos responden lo mismo para compararlos.

Ambas registran qué modelo se usó en cada paso/respuesta, en una forma lista para
alimentar el recibo (F3): `pasos_para_recibo(...)` devuelve líneas con el modelo
por paso. No hace llamadas reales: usa la capa de proveedores (en pruebas,
simulada).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from agent.multi_model.presupuesto import PresupuestoAgenteAgotadoError
from agent.multi_model.seleccion import generar

logger = logging.getLogger("dona")

# Topes de coste (defensa contra gasto descontrolado):
# - a lo sumo N modelos en una comparación lado a lado;
# - a lo sumo N pasos de ejecución en un plan.
TOPE_MODELOS_COMPARAR = 3
TOPE_PASOS = 5


def _dec(costo_usd: str | None) -> Decimal:
    if not costo_usd:
        return Decimal(0)
    try:
        return Decimal(str(costo_usd))
    except Exception:
        return Decimal(0)


def _presupuesto_agotado(gastado: Decimal, tope_coste_usd) -> bool:
    """True si ya se alcanzó/superó el tope de coste → no hacer más llamadas
    (reserva/verificación de presupuesto ANTES de la siguiente llamada)."""
    if tope_coste_usd is None:
        return False
    try:
        tope = Decimal(str(tope_coste_usd))
    except Exception:
        return False
    return gastado >= tope


@dataclass
class PasoEjecutado:
    nombre: str
    modelo: str
    proveedor: str
    texto: str
    costo_usd: str | None = None


@dataclass
class ResultadoCombinacion:
    modo: str  # "plan_y_ejecucion" | "comparacion"
    pasos: list[PasoEjecutado] = field(default_factory=list)
    # Para comparación lado a lado: una entrada por modelo.
    respuestas: list[PasoEjecutado] = field(default_factory=list)


def _lineas_plan(texto_plan: str) -> list[str]:
    """Extrae pasos del texto del planificador (una línea por paso no vacía)."""
    lineas = [l.strip(" -*\t") for l in (texto_plan or "").splitlines()]
    pasos = [l for l in lineas if l]
    return pasos or ["ejecutar la tarea"]


async def planificar_y_ejecutar(
    *,
    modelo_plan: str,
    modelo_exec: str,
    mensajes: list[dict],
    system: str = "",
    max_pasos: int = 5,
    tope_coste_usd=None,
    agente: str = "",
) -> ResultadoCombinacion:
    """El modelo `modelo_plan` produce un plan; `modelo_exec` ejecuta cada paso.
    Registra el modelo usado en cada paso (incluido el de planificación).

    Topes de coste: `max_pasos` se acota a TOPE_PASOS; si se pasa
    `tope_coste_usd`, se deja de ejecutar pasos cuando el coste estimado
    acumulado alcanza el tope (se verifica ANTES de cada llamada). Si se pasa
    `agente`, además se respeta su presupuesto DIARIO (riesgo 3 de PR #306 /
    issue #310): al agotarse, se detiene el plan igual que con `tope_coste_usd`
    en vez de propagar la excepción. Respeta el flag vía generar() (simulado si
    DONA_MULTI_MODEL_ENABLED está apagado)."""
    pasos_max = max(0, min(int(max_pasos), TOPE_PASOS))
    res = ResultadoCombinacion(modo="plan_y_ejecucion")
    gastado = Decimal(0)

    try:
        plan = await generar(
            modelo=modelo_plan,
            mensajes=mensajes + [{"role": "user", "content": "Haz un plan en pasos."}],
            system=system,
            agente=agente,
        )
    except PresupuestoAgenteAgotadoError:
        logger.warning("[MULTI_MODEL] presupuesto de agente agotado; no se planificó")
        res.pasos.append(PasoEjecutado(
            nombre="planificación", modelo=modelo_plan, proveedor="",
            texto="[plan no iniciado: presupuesto de agente agotado]",
        ))
        return res
    gastado += _dec(plan.costo_usd)
    res.pasos.append(PasoEjecutado(
        nombre="planificación", modelo=plan.modelo, proveedor=plan.proveedor,
        texto=plan.texto, costo_usd=plan.costo_usd,
    ))

    for i, paso in enumerate(_lineas_plan(plan.texto)[:pasos_max], 1):
        if _presupuesto_agotado(gastado, tope_coste_usd):
            logger.warning("[MULTI_MODEL] tope de coste alcanzado; se detiene el plan")
            if res.pasos:
                res.pasos[-1].texto += " [plan detenido: tope de coste]"
            break
        try:
            ej = await generar(
                modelo=modelo_exec,
                mensajes=mensajes + [{"role": "user", "content": f"Ejecuta el paso: {paso}"}],
                system=system,
                agente=agente,
            )
        except PresupuestoAgenteAgotadoError:
            logger.warning(
                "[MULTI_MODEL] presupuesto de agente agotado; se detiene el plan"
            )
            if res.pasos:
                res.pasos[-1].texto += " [plan detenido: presupuesto de agente agotado]"
            break
        gastado += _dec(ej.costo_usd)
        res.pasos.append(PasoEjecutado(
            nombre=f"paso {i}: {paso[:60]}", modelo=ej.modelo,
            proveedor=ej.proveedor, texto=ej.texto, costo_usd=ej.costo_usd,
        ))
    return res


async def comparar_lado_a_lado(
    *,
    modelos: list[str],
    mensajes: list[dict],
    system: str = "",
    tope_coste_usd=None,
    agente: str = "",
) -> ResultadoCombinacion:
    """Cada modelo responde lo mismo; se devuelven las respuestas para mostrarlas
    lado a lado. Registra el modelo de cada respuesta.

    Topes de coste: se comparan a lo sumo TOPE_MODELOS_COMPARAR modelos (el resto
    se descarta con warning); si se pasa `tope_coste_usd`, se deja de consultar
    cuando el coste estimado acumulado alcanza el tope. Si se pasa `agente`, se
    respeta además su presupuesto DIARIO (riesgo 3 de PR #306 / issue #310): al
    agotarse, se detiene la comparación. Respeta el flag vía generar()."""
    if len(modelos) > TOPE_MODELOS_COMPARAR:
        logger.warning(
            "[MULTI_MODEL] comparar_lado_a_lado limitado a %d modelos (%d pedidos)",
            TOPE_MODELOS_COMPARAR, len(modelos),
        )
    seleccionados = list(modelos)[:TOPE_MODELOS_COMPARAR]
    res = ResultadoCombinacion(modo="comparacion")
    gastado = Decimal(0)
    for modelo in seleccionados:
        if _presupuesto_agotado(gastado, tope_coste_usd):
            logger.warning("[MULTI_MODEL] tope de coste alcanzado; se detiene la comparación")
            break
        try:
            r = await generar(modelo=modelo, mensajes=mensajes, system=system, agente=agente)
        except PresupuestoAgenteAgotadoError:
            logger.warning(
                "[MULTI_MODEL] presupuesto de agente agotado; se detiene la comparación"
            )
            break
        gastado += _dec(r.costo_usd)
        res.respuestas.append(PasoEjecutado(
            nombre=f"respuesta {r.modelo}", modelo=r.modelo, proveedor=r.proveedor,
            texto=r.texto, costo_usd=r.costo_usd,
        ))
    return res


def pasos_para_recibo(resultado: ResultadoCombinacion) -> list[dict]:
    """Convierte la combinación en líneas por paso para el recibo (F3): cada
    línea muestra el modelo usado. Integra con agent.recibos.linea_paso /
    construir_desglose (que viven en la rama F3)."""
    fuente = resultado.pasos or resultado.respuestas
    return [
        {
            "nombre": p.nombre,
            "modelo": p.modelo,
            "proveedor": p.proveedor,
            "estado": "completado",
            "detalle": f"modelo {p.modelo}",
        }
        for p in fuente
    ]
