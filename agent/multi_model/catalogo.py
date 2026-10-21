"""Catálogo de modelos y precios (F23).

Precios **configurables por modelo**: hay una tabla base (grounded en los modelos
que el repo ya usa) y un override por variable de entorno del backend
(`DONA_MODEL_PRICES`, JSON `{"<id>": {"in": <usd_mtok>, "out": <usd_mtok>}}`).
Los precios son USD por millón de tokens; son estimaciones para cotización, no
facturación. Nunca se hace una llamada real desde aquí.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger("dona")


@dataclass(frozen=True)
class ModeloInfo:
    id: str
    nombre: str
    proveedor: str  # anthropic | openai | google
    precio_in_usd_mtok: Decimal
    precio_out_usd_mtok: Decimal
    # Clases de tarea para las que el modelo es buena opción (Auto las usa).
    clases: tuple[str, ...]
    # Nivel de coste relativo (para desempatar por coste en Auto): 1=barato.
    nivel_coste: int


# Clases de tarea reconocidas por el modo Auto y las sugerencias.
CLASES_TAREA = (
    "conversacion",
    "planificacion",
    "razonamiento",
    "borrador",
    "clasificacion",
    "resumen",
    "imagen",
)


# Tabla base (IDs reales ya presentes en el repo + GPT/Gemini). Los precios son
# defaults configurables; no pretenden ser exactos.
_BASE: tuple[ModeloInfo, ...] = (
    ModeloInfo(
        id="claude-sonnet-4-5",
        nombre="Claude Sonnet 4.5",
        proveedor="anthropic",
        precio_in_usd_mtok=Decimal("3.0"),
        precio_out_usd_mtok=Decimal("15.0"),
        clases=("conversacion", "planificacion", "razonamiento", "resumen"),
        nivel_coste=3,
    ),
    ModeloInfo(
        id="claude-haiku-4-5-20251001",
        nombre="Claude Haiku 4.5",
        proveedor="anthropic",
        precio_in_usd_mtok=Decimal("1.0"),
        precio_out_usd_mtok=Decimal("5.0"),
        clases=("clasificacion", "resumen", "borrador", "conversacion"),
        nivel_coste=1,
    ),
    ModeloInfo(
        id="gpt-4o",
        nombre="GPT-4o",
        proveedor="openai",
        precio_in_usd_mtok=Decimal("2.5"),
        precio_out_usd_mtok=Decimal("10.0"),
        clases=("conversacion", "planificacion", "razonamiento"),
        nivel_coste=2,
    ),
    ModeloInfo(
        id="gemini-2.5-flash",
        nombre="Gemini 2.5 Flash",
        proveedor="google",
        precio_in_usd_mtok=Decimal("0.3"),
        precio_out_usd_mtok=Decimal("2.5"),
        clases=("imagen", "borrador", "clasificacion", "resumen"),
        nivel_coste=1,
    ),
)

_POR_ID = {m.id: m for m in _BASE}


def _override_precios() -> dict:
    raw = os.getenv("DONA_MODEL_PRICES", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.warning("[MULTI_MODEL] DONA_MODEL_PRICES no es JSON válido; se ignora")
        return {}


def modelos_disponibles() -> list[ModeloInfo]:
    return list(_BASE)


def info_modelo(modelo_id: str) -> ModeloInfo | None:
    return _POR_ID.get(modelo_id)


def existe(modelo_id: str) -> bool:
    return modelo_id in _POR_ID


def precio_modelo(modelo_id: str) -> tuple[Decimal, Decimal] | None:
    """(precio_in, precio_out) USD/Mtok, con override por env si existe."""
    base = _POR_ID.get(modelo_id)
    if base is None:
        return None
    ov = _override_precios().get(modelo_id, {})
    pin = Decimal(str(ov["in"])) if "in" in ov else base.precio_in_usd_mtok
    pout = Decimal(str(ov["out"])) if "out" in ov else base.precio_out_usd_mtok
    return pin, pout


def costo_estimado_usd(modelo_id: str, tokens_in: int, tokens_out: int) -> Decimal | None:
    """Coste estimado en USD (Decimal, nunca float) para una llamada."""
    precios = precio_modelo(modelo_id)
    if precios is None:
        return None
    pin, pout = precios
    return (Decimal(tokens_in) * pin + Decimal(tokens_out) * pout) / Decimal(1_000_000)
