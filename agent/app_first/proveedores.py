# agent/app_first/proveedores.py — Proveedores de modelo para los agentes (J7.2)

"""
Interfaz mínima que usa el runner (``agent/app_first/ejecucion.py``):

  - ``costo_estimado(tarea)`` → unidades que se RESERVAN antes de llamar.
  - ``generar(...)`` → ``ResultadoModelo`` del agente ejecutor.
  - ``revisar(criterios, evidencias)`` → ``Revision`` del agente responsable.

En el piloto solo existe el proveedor ``simulado``: determinista, sin red,
sin costo real. Es el que usan CI y la demo, y todo lo que produce va
marcado ``simulado=True`` (la UI lo muestra). Cualquier otro modelo lanza
``ProveedorNoDisponible`` hasta que se conecte uno real con OK explícito
(llamadas facturables, presupuesto y DONA_LLM_ENABLED).

Los tests pueden registrar un proveedor propio con ``registrar_proveedor``
(p. ej. uno que falle) sin tocar el runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

# Operaciones reservadas que un ejecutor puede SOLICITAR. Nunca se ejecutan
# sin una aprobación humana (app_aprobaciones). Riesgo según la taxonomía
# de agent/automation/permissions.py.
OPERACIONES_RESERVADAS: dict[str, str] = {
    "publicar_resultado": "HIGH",
}


class ProveedorNoDisponible(RuntimeError):
    """El proveedor no está disponible (caído, sin configurar o no permitido)."""


@dataclass(frozen=True)
class ResultadoModelo:
    texto: str
    unidades: int
    simulado: bool
    operaciones_solicitadas: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Revision:
    cumple: bool
    comentario: str
    simulado: bool


class ProveedorModelo(Protocol):
    nombre: str

    def costo_estimado(self, titulo: str, descripcion: str) -> int: ...

    async def generar(
        self, *, instrucciones: str, titulo: str, descripcion: str, objetivo: str,
        herramientas: tuple[str, ...],
    ) -> ResultadoModelo: ...

    async def revisar(self, *, criterios: list[str], evidencias: list[str]) -> Revision: ...


class ProveedorSimulado:
    """Determinista y sin red. Solicita la operación reservada
    ``publicar_resultado`` solo si la tarea lo pide explícitamente ("publicar")
    y el agente tiene esa herramienta."""

    nombre = "simulado"

    def costo_estimado(self, titulo: str, descripcion: str) -> int:
        return 1

    async def generar(
        self, *, instrucciones: str, titulo: str, descripcion: str, objetivo: str,
        herramientas: tuple[str, ...],
    ) -> ResultadoModelo:
        texto = (
            f"[Simulado] Borrador para «{titulo}».\n"
            f"Objetivo del proyecto: {objetivo}\n"
            f"Encargo: {descripcion or '(sin descripción)'}\n"
            "Este texto lo generó el proveedor simulado; no es trabajo de un modelo real."
        )
        pide_publicar = "publicar" in f"{titulo} {descripcion}".lower()
        ops = ("publicar_resultado",) if pide_publicar else ()
        return ResultadoModelo(texto=texto, unidades=1, simulado=True, operaciones_solicitadas=ops)

    async def revisar(self, *, criterios: list[str], evidencias: list[str]) -> Revision:
        if not any(e.strip() for e in evidencias):
            return Revision(False, "[Simulado] No hay evidencia que revisar.", True)
        return Revision(
            True,
            "[Simulado] Evidencia presente; criterios marcados como revisados: "
            + "; ".join(criterios),
            True,
        )


_PROVEEDORES: dict[str, ProveedorModelo] = {"simulado": ProveedorSimulado()}


def registrar_proveedor(nombre: str, proveedor: ProveedorModelo) -> None:
    _PROVEEDORES[nombre] = proveedor


def obtener_proveedor(modelo: str) -> ProveedorModelo:
    proveedor = _PROVEEDORES.get(modelo)
    if proveedor is None:
        raise ProveedorNoDisponible(f"modelo no disponible en el piloto: {modelo}")
    return proveedor
