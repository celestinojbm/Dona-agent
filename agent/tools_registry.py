# agent/tools_registry.py — Registry canónico de definición de tools (Fase 2 · Bloque 1)

"""
Fuente ÚNICA de definición para las tools migradas. En el Bloque 1 contiene
SOLO `listar_tareas_google`. Provee a `brain` el schema (para el LLM) y una
ruta de dispatch **read-only** con resolución LAZY del handler.

Límites deliberados de este bloque (no relajar sin decisión explícita):

  - NO es un motor de acciones. Las ESCRITURAS pertenecen a `agent/automation/`
    (Action Center: aprobación, idempotencia, créditos, audit). Este módulo
    SOLO despacha handlers cuya `capability == "read"`. Cualquier otra queda
    fail-closed (`ToolNoEjecutableDirecto`) y reservada para el routing futuro.

  - `risk_tier` es METADATA canónica. En el Bloque 1 NO hay enforcement nuevo:
    `agent/automation/permissions.py` no se toca y el runtime todavía NO
    consulta este campo. Solo unifica la definición en un único lugar.

  - Import liviano: este módulo NO importa providers ni `brain` al construirse;
    el handler se resuelve de forma perezosa en el primer dispatch. Importarlo
    no toca red ni requiere secretos.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Literal

# Dos taxonomías SEPARADAS (corrección del plan):
#   capability → qué hace la tool (leer vs escribir)
#   risk_tier  → cuánto riesgo tiene (mapea conceptualmente a permissions)
Capability = Literal["read", "write"]
RiskTier = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass(frozen=True)
class ToolDefinition:
    """Definición canónica de una tool. Fuente única de su schema, categoría,
    provider, capacidad, riesgo (metadata) y handler."""

    name: str
    description: str
    input_schema: dict
    category: str
    provider: str
    capability: Capability
    risk_tier: RiskTier
    handler_ref: str  # "modulo:funcion" — resuelto lazy en el primer dispatch


class ToolNoEjecutableDirecto(RuntimeError):
    """La ruta directa del registry SOLO ejecuta tools read-only. Una tool con
    `capability != 'read'` NO puede ejecutarse por aquí: debe enrutarse por
    `agent/automation/` (aprobación, idempotencia, créditos, audit). Fail-closed."""


# ── Definiciones canónicas ─────────────────────────────────────────────────
_LISTAR_TAREAS_GOOGLE = ToolDefinition(
    name="listar_tareas_google",
    description=(
        "Lista las tareas pendientes del usuario en Google Tasks. Úsala cuando diga: "
        "'qué tengo pendiente', 'mis tareas', 'muéstrame mi lista de tareas'. "
        "Por defecto usa la lista principal; no incluye tareas ya completadas."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "incluir_completadas": {
                "type": "boolean",
                "description": "Si es true, incluye también las ya marcadas como hechas.",
                "default": False,
            },
            "limite": {
                "type": "integer",
                "description": "Máximo de tareas a retornar (1-100).",
                "default": 20,
            },
        },
        "required": [],
    },
    category="tareas",
    provider="google_tasks",
    capability="read",
    risk_tier="LOW",
    handler_ref="agent.tool_handlers.google_tasks:handle_listar_tareas",
)


REGISTRY: dict[str, ToolDefinition] = {
    _LISTAR_TAREAS_GOOGLE.name: _LISTAR_TAREAS_GOOGLE,
}

# Cache de handlers ya resueltos: el import lazy ocurre una sola vez por ref.
_HANDLER_CACHE: dict[str, object] = {}


def get(name: str) -> ToolDefinition | None:
    """Definición canónica de una tool, o None si no está registrada."""
    return REGISTRY.get(name)


def all_defs() -> tuple[ToolDefinition, ...]:
    """Todas las definiciones canónicas registradas."""
    return tuple(REGISTRY.values())


def schema_for(name: str) -> dict:
    """Schema en el formato que consume el LLM (name/description/input_schema).
    Es la ÚNICA fuente del schema de la tool migrada; `brain` lo inyecta en
    su lista `TOOLS` en vez de mantener un dict inline duplicado."""
    d = REGISTRY[name]
    return {
        "name": d.name,
        "description": d.description,
        "input_schema": d.input_schema,
    }


def es_read_only(name: str) -> bool:
    """True si la tool está registrada y su capability es 'read'. La usa el
    seam de `brain` como primer gate antes de la ruta directa."""
    d = REGISTRY.get(name)
    return d is not None and d.capability == "read"


def _resolver_handler(handler_ref: str):
    """Resuelve `"modulo:funcion"` importando el módulo del handler de forma
    perezosa (recién en el primer dispatch, no al construir el registry) y
    cachea el callable."""
    cached = _HANDLER_CACHE.get(handler_ref)
    if cached is not None:
        return cached
    modulo, _, funcion = handler_ref.partition(":")
    mod = importlib.import_module(modulo)
    fn = getattr(mod, funcion)
    _HANDLER_CACHE[handler_ref] = fn
    return fn


async def dispatch_read(name: str, telefono: str, args: dict) -> str:
    """Ejecuta el handler read-only de una tool migrada y devuelve el contenido
    del `tool_result`.

    FAIL-CLOSED: si la tool no está registrada, o su `capability` no es 'read',
    lanza `ToolNoEjecutableDirecto` — esta ruta NUNCA ejecuta una escritura.
    Las escrituras futuras se enrutan por `agent/automation/`.
    """
    d = REGISTRY.get(name)
    if d is None:
        raise ToolNoEjecutableDirecto(f"tool no registrada: {name!r}")
    if d.capability != "read":
        raise ToolNoEjecutableDirecto(
            f"tool {name!r} capability={d.capability!r}: la ruta directa del "
            f"registry es solo para 'read'; enrutar por agent/automation/"
        )
    handler = _resolver_handler(d.handler_ref)
    return await handler(telefono, args)
