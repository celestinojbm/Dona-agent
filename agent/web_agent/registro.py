# agent/web_agent/registro.py — Registro global de tareas web

"""
Registro simple de tareas de automatización web. Las tareas se registran
con `registrar(tarea)` y se invocan por nombre vía `obtener(nombre)`.

Ejemplo de uso:

    from agent.web_agent.registro import registrar, obtener
    from agent.web_agent.base import WebAgentTarea

    class MiTarea(WebAgentTarea):
        nombre = "mi_tarea"
        async def ejecutar(self, ctx, params): ...

    registrar(MiTarea())
    tarea = obtener("mi_tarea")
"""

from agent.web_agent.base import WebAgentTarea

_TAREAS: dict[str, WebAgentTarea] = {}


def registrar(tarea: WebAgentTarea) -> None:
    """Registra una instancia de tarea. Sobrescribe si ya existe el nombre."""
    if not tarea.nombre:
        raise ValueError("WebAgentTarea.nombre no puede estar vacío")
    _TAREAS[tarea.nombre] = tarea


def obtener(nombre: str) -> WebAgentTarea | None:
    """Retorna la tarea registrada con ese nombre o None si no existe."""
    return _TAREAS.get(nombre)


def nombres_registrados() -> list[str]:
    """Lista los nombres de todas las tareas registradas."""
    return sorted(_TAREAS.keys())
