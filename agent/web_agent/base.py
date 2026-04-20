# agent/web_agent/base.py — Interfaz base para tareas de automatización web

"""
Contrato mínimo para cualquier tarea de automatización web (browser-based).

Ejemplo de implementación concreta:

    class LoginPortalX(WebAgentTarea):
        nombre = "portal_x_login"

        async def ejecutar(self, contexto, parametros):
            # usar contexto.page (Playwright Page) para navegar
            ...
            return ResultadoTarea(exito=True, datos={"balance": 1234.56})

El runner (a implementar cuando se necesite el primer caso real) se encarga de:
  - Lanzar el browser (Playwright headless).
  - Cargar cookies cifradas del usuario (session.py).
  - Inyectar MFA si el usuario lo reenvía por WhatsApp.
  - Persistir cookies actualizadas al terminar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextoTarea:
    """Contexto pasado a cada tarea por el runner."""
    telefono: str                              # usuario dueño de la sesión
    page: Any = None                           # Playwright Page (inyectada por el runner)
    cookies: list[dict] = field(default_factory=list)
    # Hook para pedir un MFA al usuario via WhatsApp; retorna str con el código
    # (o None si el usuario no respondió dentro del timeout). El runner lo inyecta.
    solicitar_mfa: Any = None


@dataclass
class ResultadoTarea:
    """Resultado estructurado de una tarea."""
    exito: bool
    datos: dict = field(default_factory=dict)     # payload útil (balance, items, etc.)
    mensaje: str = ""                              # texto amigable para el usuario
    cookies_actualizadas: list[dict] = field(default_factory=list)
    requiere_mfa: bool = False                     # el runner debería reintentar con MFA


class WebAgentTarea(ABC):
    """
    Base para cualquier tarea automatizada en el navegador.

    `nombre` debe ser único dentro del registro — es la clave con la que la
    tarea se invoca desde el resto de Dona.
    """

    nombre: str = ""

    @abstractmethod
    async def ejecutar(self, contexto: ContextoTarea, parametros: dict) -> ResultadoTarea:
        """Ejecuta la tarea. El runner se encarga del scaffolding del browser."""
        ...
