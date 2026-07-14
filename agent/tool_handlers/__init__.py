# agent/tool_handlers/ — Handlers de tools desacoplados de brain (Fase 2 · Bloque 1)
#
# Cada handler es `async def handler(telefono: str, args: dict) -> str` y
# devuelve el contenido del tool_result. Los handlers NO importan `brain`;
# importan sus providers de forma perezosa dentro de la función. El registry
# (agent/tools_registry.py) los resuelve vía handler_ref.
