# agent/web_agent/__init__.py — Scaffolding para automatización web (patrón Twin.so)

"""
Módulo de automatización web: fallback tipo "web agent" para servicios sin API
(portales bancarios, POS legacy, intranets, etc.).

Estado: SCAFFOLD. No está cableado al flujo principal. Para activar una
automatización concreta, implementá una subclase de `WebAgentTarea` y
registrála en `registro.py`.

Filosofía (inspirada en Twin.so):
  1. Preferir APIs oficiales siempre que existan.
  2. Sólo caer acá cuando no hay alternativa.
  3. Persistir sesiones con cookies cifradas por usuario.
  4. Human-in-the-loop para MFA/captcha (se reenvía al usuario por WhatsApp).
"""

from agent.web_agent.base import WebAgentTarea, ResultadoTarea, ContextoTarea
from agent.web_agent.registro import registrar, obtener, nombres_registrados
from agent.web_agent.runner import ejecutar_tarea

# Importar las tareas concretas dispara su auto-registro. Best-effort: si algún
# módulo falla al importarse no tumbamos el arranque del servidor.
try:
    from agent.web_agent import tareas as _tareas  # noqa: F401
except Exception as _e:  # pragma: no cover
    import logging
    logging.getLogger("dona").warning(f"[WEB_AGENT] No se pudieron cargar tareas: {_e}")

__all__ = [
    "WebAgentTarea",
    "ResultadoTarea",
    "ContextoTarea",
    "registrar",
    "obtener",
    "nombres_registrados",
    "ejecutar_tarea",
]
