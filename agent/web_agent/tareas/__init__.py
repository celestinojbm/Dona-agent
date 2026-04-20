# agent/web_agent/tareas/__init__.py — Catálogo de tareas concretas

"""
Importa este paquete para registrar todas las tareas disponibles.
Cada módulo se auto-registra al importarse (llama a `registrar(...)` al cargar).
"""

from agent.web_agent.tareas import consultar_pagina_publica  # noqa: F401

__all__ = ["consultar_pagina_publica"]
