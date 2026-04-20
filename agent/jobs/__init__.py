# agent/jobs/__init__.py — Sistema de jobs asíncronos

"""
Package para ejecutar trabajos largos (generación de video, publicación web,
etc.) sin bloquear el webhook de WhatsApp.

Exporta el API público:
  - encolar(tipo, telefono, params) → job_id
  - obtener_estado(job_id) → dict
  - listar_jobs_usuario(telefono) → list[dict]
  - marcar_done / marcar_error (para workers)

El backend se elige por env `JOBS_BACKEND`:
  - "arq" → cola distribuida sobre Redis (prod)
  - "inproc" → asyncio.create_task local (dev / sin Redis)
"""

from agent.jobs.queue import (  # noqa: F401
    encolar,
    obtener_estado,
    listar_jobs_usuario,
    marcar_running,
    marcar_done,
    marcar_error,
    backend_activo,
)

# Importar los módulos de handlers para que los decorators se ejecuten y
# queden registrados en `_HANDLERS`. NO remover — sin esto los handlers no
# están disponibles en runtime.
from agent.jobs import worker  # noqa: F401,E402
from agent.jobs import handlers_creativos  # noqa: F401,E402
