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

from dataclasses import dataclass, field

from agent.multi_model.seleccion import generar


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
) -> ResultadoCombinacion:
    """El modelo `modelo_plan` produce un plan; `modelo_exec` ejecuta cada paso.
    Registra el modelo usado en cada paso (incluido el de planificación)."""
    res = ResultadoCombinacion(modo="plan_y_ejecucion")

    plan = await generar(
        modelo=modelo_plan,
        mensajes=mensajes + [{"role": "user", "content": "Haz un plan en pasos."}],
        system=system,
    )
    res.pasos.append(PasoEjecutado(
        nombre="planificación", modelo=plan.modelo, proveedor=plan.proveedor,
        texto=plan.texto, costo_usd=plan.costo_usd,
    ))

    for i, paso in enumerate(_lineas_plan(plan.texto)[:max_pasos], 1):
        ej = await generar(
            modelo=modelo_exec,
            mensajes=mensajes + [{"role": "user", "content": f"Ejecuta el paso: {paso}"}],
            system=system,
        )
        res.pasos.append(PasoEjecutado(
            nombre=f"paso {i}: {paso[:60]}", modelo=ej.modelo,
            proveedor=ej.proveedor, texto=ej.texto, costo_usd=ej.costo_usd,
        ))
    return res


async def comparar_lado_a_lado(
    *, modelos: list[str], mensajes: list[dict], system: str = ""
) -> ResultadoCombinacion:
    """Cada modelo responde lo mismo; se devuelven las respuestas para mostrarlas
    lado a lado. Registra el modelo de cada respuesta."""
    res = ResultadoCombinacion(modo="comparacion")
    for modelo in modelos:
        r = await generar(modelo=modelo, mensajes=mensajes, system=system)
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
