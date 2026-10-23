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


# Tabla base (IDs reales ya presentes en el repo). Los precios son defaults
# configurables; no pretenden ser exactos.
#
# Gemini: QUITADO del catálogo hasta tener un adaptador de texto real
# (agent.multi_model.providers.ProveedorGoogle.generar aún no está implementado).
# No se expone un modelo que no se puede ejecutar. Reañadir cuando exista el
# adaptador + sus pruebas con mock.
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
)

_POR_ID = {m.id: m for m in _BASE}


def _precio_valido(v) -> Decimal | None:
    """Coacciona un valor de precio a Decimal >= 0, o None si es inválido."""
    if isinstance(v, bool):  # bool es subclase de int; no lo aceptamos
        return None
    try:
        d = Decimal(str(v))
    except Exception:
        return None
    return d if d >= 0 else None


def _override_precios() -> dict[str, dict[str, Decimal]]:
    """Lee y VALIDA DONA_MODEL_PRICES. Forma esperada:
    {"<id>": {"in": num>=0, "out": num>=0}}. Entradas o campos inválidos se
    ignoran con warning (no rompen el arranque). Devuelve sólo lo válido."""
    raw = os.getenv("DONA_MODEL_PRICES", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        logger.warning("[MULTI_MODEL] DONA_MODEL_PRICES no es JSON válido; se ignora")
        return {}
    if not isinstance(data, dict):
        logger.warning("[MULTI_MODEL] DONA_MODEL_PRICES debe ser un objeto; se ignora")
        return {}

    validos: dict[str, dict[str, Decimal]] = {}
    for mid, cfg in data.items():
        if not isinstance(cfg, dict):
            logger.warning("[MULTI_MODEL] precio inválido para %s (no es objeto); se ignora", mid)
            continue
        entrada: dict[str, Decimal] = {}
        for campo in ("in", "out"):
            if campo in cfg:
                d = _precio_valido(cfg[campo])
                if d is None:
                    logger.warning(
                        "[MULTI_MODEL] precio %s.%s inválido; se ignora ese campo", mid, campo
                    )
                else:
                    entrada[campo] = d
        if entrada:
            validos[mid] = entrada
    return validos


def modelos_disponibles() -> list[ModeloInfo]:
    return list(_BASE)


def info_modelo(modelo_id: str) -> ModeloInfo | None:
    return _POR_ID.get(modelo_id)


def existe(modelo_id: str) -> bool:
    return modelo_id in _POR_ID


def precio_modelo(modelo_id: str) -> tuple[Decimal, Decimal] | None:
    """(precio_in, precio_out) USD/Mtok, con override por env VALIDADO si existe."""
    base = _POR_ID.get(modelo_id)
    if base is None:
        return None
    ov = _override_precios().get(modelo_id, {})
    pin = ov.get("in", base.precio_in_usd_mtok)
    pout = ov.get("out", base.precio_out_usd_mtok)
    return pin, pout


def costo_estimado_usd(modelo_id: str, tokens_in: int, tokens_out: int) -> Decimal | None:
    """Coste estimado en USD (Decimal, nunca float) para una llamada."""
    precios = precio_modelo(modelo_id)
    if precios is None:
        return None
    pin, pout = precios
    return (Decimal(tokens_in) * pin + Decimal(tokens_out) * pout) / Decimal(1_000_000)
