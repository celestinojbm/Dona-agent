"""Sugerencias (F23): respuestas sugeridas, siguientes acciones y modelo
recomendado, como chips.

Determinístico (0 USD, sin llamadas): las sugerencias se derivan de la clase de
tarea y de señales simples del contexto. Una versión futura podría pedirlas a un
modelo, pero el default no gasta.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.multi_model.seleccion import elegir_auto

# Respuestas sugeridas por clase de tarea (chips cortos).
_RESPUESTAS = {
    "borrador": ("Confirmar", "Ajustar el tono", "Acortar"),
    "conversacion": ("Sí, dale", "Cuéntame más", "Ahora no"),
    "planificacion": ("Confirmar el plan", "Ajustar pasos", "Cancelar"),
    "razonamiento": ("Explícalo simple", "Dame ejemplos", "Siguiente"),
    "resumen": ("Más detalle", "Más corto", "Acciones clave"),
    "clasificacion": ("Correcto", "Reclasificar", "Ver criterios"),
    "imagen": ("Generar", "Cambiar estilo", "Otra idea"),
}

# Siguientes acciones sugeridas por clase (chips de acción).
_ACCIONES = {
    "borrador": ("Enviar borrador", "Programar envío", "Ver recibo"),
    "conversacion": ("Armar seguimiento", "Programar recordatorio", "Ver saldo"),
    "planificacion": ("Ejecutar plan", "Ver recibo", "Guardar plan"),
    "razonamiento": ("Armar seguimiento", "Redactar correo", "Ver recibo"),
    "resumen": ("Redactar correo", "Programar recordatorio", "Compartir"),
    "clasificacion": ("Armar seguimiento", "Exportar", "Ver detalle"),
    "imagen": ("Descargar", "Variaciones", "Ver recibo"),
}

_RESPUESTAS_DEFECTO = ("Sí", "No", "Dame opciones")
_ACCIONES_DEFECTO = ("Armar seguimiento", "Ver saldo", "Ayuda")


@dataclass(frozen=True)
class Sugerencias:
    respuestas_sugeridas: tuple[str, ...]
    siguientes_acciones: tuple[str, ...]
    modelo_recomendado: str
    razon_modelo: str
    extras: dict = field(default_factory=dict)


def sugerencias_para(
    *, clase_tarea: str = "conversacion", presupuesto_creditos: int | None = None
) -> Sugerencias:
    """Devuelve chips de respuestas, siguientes acciones y modelo recomendado."""
    eleccion = elegir_auto(clase_tarea, presupuesto_creditos)
    return Sugerencias(
        respuestas_sugeridas=_RESPUESTAS.get(clase_tarea, _RESPUESTAS_DEFECTO),
        siguientes_acciones=_ACCIONES.get(clase_tarea, _ACCIONES_DEFECTO),
        modelo_recomendado=eleccion.modelo,
        razon_modelo=eleccion.razon,
    )
