"""Tarifa de Dona (F3 · decisión de Celestino 2026-10-21).

Regla de precio: **coste base + 30% de margen, redondeo hacia arriba**.

- Créditos: enteros (lo que ve el usuario). El redondeo hacia arriba garantiza
  que nunca se cobra de menos.
- Dinero: `Decimal` internamente (decimales internos permitidos); nunca `float`.

El valor de 1 crédito en USD es configurable por env (`DONA_VALOR_CREDITO_USD`)
porque Celestino aún no fijó la equivalencia crédito↔USD; mientras no esté, las
funciones que convierten a créditos exigen pasar `valor_credito_usd`
explícitamente (no se inventa un precio).
"""

from __future__ import annotations

import math
import os
from decimal import Decimal

VERSION_TARIFA = "2026-10-21.1"

# Margen sobre el coste base (30%).
MARGEN = Decimal("0.30")


def _a_decimal(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


def aplicar_margen(coste_base_usd) -> Decimal:
    """Coste con margen = coste_base * 1.30 (Decimal, sin float)."""
    return _a_decimal(coste_base_usd) * (Decimal("1") + MARGEN)


def valor_credito_usd_env() -> Decimal | None:
    """Valor de 1 crédito en USD desde env, o None si no está configurado."""
    raw = os.getenv("DONA_VALOR_CREDITO_USD", "").strip()
    if not raw:
        return None
    try:
        v = Decimal(raw)
        return v if v > 0 else None
    except Exception:
        return None


def creditos_por_costo(coste_base_usd, valor_credito_usd=None) -> int:
    """Convierte un coste base (USD) a créditos enteros aplicando margen 30% y
    **redondeo hacia arriba**.

    `valor_credito_usd`: USD por crédito. Si es None, se toma de
    `DONA_VALOR_CREDITO_USD`; si tampoco está, se lanza ValueError (no se inventa
    un precio).
    """
    valor = _a_decimal(valor_credito_usd) if valor_credito_usd is not None else valor_credito_usd_env()
    if valor is None or valor <= 0:
        raise ValueError(
            "valor_credito_usd no configurado (DONA_VALOR_CREDITO_USD); "
            "Celestino aún no fijó la equivalencia crédito↔USD."
        )
    con_margen = aplicar_margen(coste_base_usd)
    # Redondeo hacia arriba al entero de créditos.
    return int(math.ceil(con_margen / valor))


def margen_str() -> str:
    """El margen como string para el desglose (p. ej. '0.30')."""
    return str(MARGEN)
