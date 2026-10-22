"""Recibo por acción (F3) — desglose de crédito, formato y comandos.

Materializa la "trazabilidad" de la regla de oro: cada cobro puede explicar qué
acción fue, qué proveedores/modelos intervinieron, coste base vs. observado,
créditos cobrados y saldo resultante. No es factura fiscal.

Reglas:
- Créditos: enteros. Dinero: NUMERIC como string (Decimal→str), nunca float.
- El flag DONA_CREDIT_RECEIPTS_ENABLED controla SÓLO la exposición (comandos/UI);
  la idempotencia del cobro y el guardado del desglose están SIEMPRE activos.
- Un recibo ajeno no se revela: el lookup filtra por teléfono y responde igual
  que "no existe".
"""

from __future__ import annotations

import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any

VERSION_DESGLOSE = "1"


def recibos_habilitado() -> bool:
    """True si la EXPOSICIÓN de recibos está encendida (apagada por defecto)."""
    return os.getenv("DONA_CREDIT_RECEIPTS_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _dinero(v: Any) -> str | None:
    """Normaliza un monto a string NUMERIC (nunca float). None → None."""
    if v is None or v == "":
        return None
    try:
        return str(Decimal(str(v)))
    except (InvalidOperation, ValueError):
        return None


def linea_proveedor(
    *,
    proveedor: str,
    modelo: str = "",
    tokens: dict[str, int] | None = None,
    unidades: dict[str, Any] | None = None,
    coste_base: Any = None,
    moneda: str = "USD",
    estado: str = "estimado",
) -> dict[str, Any]:
    """Una línea del recibo por proveedor. `estado` ∈ estimado|observado|
    no_disponible. Dinero como string."""
    if estado not in ("estimado", "observado", "no_disponible"):
        estado = "estimado"
    return {
        "proveedor": proveedor,
        "modelo": modelo,
        "tokens": tokens or None,
        "unidades": unidades or None,
        "coste_base": _dinero(coste_base),
        "moneda": moneda,
        "estado": estado,
    }


def linea_paso(
    *,
    nombre: str,
    creditos: int | None = None,
    estado: str = "completado",
    detalle: str = "",
) -> dict[str, Any]:
    """Una línea del desglose POR PASO (decisión de Celestino #7). `creditos` es
    entero (lo que ve el usuario); None si el paso no cobró por sí mismo."""
    return {
        "nombre": nombre,
        "creditos": int(creditos) if creditos is not None else None,
        "estado": estado,
        "detalle": detalle,
    }


def construir_desglose(
    *,
    accion: str,
    proveedores: list[dict[str, Any]],
    creditos_cobrados: int,
    saldo_posterior: int,
    estado: str,
    version_tarifa: str | None = None,
    pasos: list[dict[str, Any]] | None = None,
    margen: Any = None,
    coste_base_total: Any = None,
    moneda: str = "USD",
    unidades_no_token: dict[str, Any] | None = None,
    ajuste_ref: str | None = None,
) -> dict[str, Any]:
    """Construye el desglose versionado (dict serializable a JSON).

    Decisiones de Celestino aplicadas:
    - #4 Créditos ENTEROS (visibles); dinero como string Decimal (interno), nunca
      float.
    - #5 Margen por defecto = 30% (de agent.tarifa) si no se pasa explícito;
      `version_tarifa` por defecto = tarifa.VERSION_TARIFA.
    - #7 Recibo con desglose POR PASO (`pasos`), además de proveedores usados.

    `estado` del recibo ∈ estimado|observado|no_disponible.
    """
    from agent import tarifa

    if estado not in ("estimado", "observado", "no_disponible"):
        estado = "estimado"
    if margen is None:
        margen = tarifa.margen_str()  # 30% por defecto
    if version_tarifa is None:
        version_tarifa = tarifa.VERSION_TARIFA
    return {
        "version": VERSION_DESGLOSE,
        "accion": accion,
        "version_tarifa": version_tarifa,
        "proveedores": list(proveedores),
        "pasos": list(pasos) if pasos else None,
        "unidades_no_token": unidades_no_token or None,
        "coste_base_total": _dinero(coste_base_total),
        "moneda": moneda,
        "margen": _dinero(margen),
        "estado": estado,
        "creditos_cobrados": int(creditos_cobrados),
        "saldo_posterior": int(saldo_posterior),
        "ajuste_ref": ajuste_ref,
    }


# ── Comandos determinísticos (gratis, antes del LLM) ────────────────────────

_RE_RECIBO_ID = re.compile(r"^(?:dona\s+)?recibo\s+#?(\d+)\s*$", re.IGNORECASE)
_RE_ULTIMO = re.compile(
    r"^(?:dona\s+)?(?:[úu]ltimo\s+recibo|recibo)\s*$", re.IGNORECASE
)


def es_comando_recibo(texto: str) -> tuple[str, int | None] | None:
    """Detecta "recibo <id>" o "último recibo"/"recibo".

    Devuelve ("id", <n>), ("ultimo", None) o None si no es comando de recibo.
    """
    t = (texto or "").strip()
    m = _RE_RECIBO_ID.match(t)
    if m:
        return ("id", int(m.group(1)))
    if _RE_ULTIMO.match(t):
        return ("ultimo", None)
    return None


# ── Formato para WhatsApp (no es factura fiscal) ────────────────────────────

_NOMBRE_ESTADO = {
    "estimado": "estimado",
    "observado": "observado",
    "no_disponible": "no disponible",
}


def formatear_recibo(tx: dict[str, Any]) -> str:
    """Formatea un recibo para WhatsApp. `tx` trae id, creado, razon, delta,
    saldo_resultante, accion_ref y desglose (dict ya parseado) o None."""
    desg = tx.get("desglose") or {}
    lineas = [
        f"🧾 *Recibo #{tx.get('id')}*",
    ]
    accion = desg.get("accion") or tx.get("razon") or "(acción)"
    lineas.append(f"Acción: {accion}")
    creditos = desg.get("creditos_cobrados")
    if creditos is None:
        # delta es negativo en un cobro
        creditos = abs(int(tx.get("delta", 0)))
    lineas.append(f"Créditos: *{creditos}*")

    # Desglose POR PASO (decisión de Celestino #7).
    pasos = desg.get("pasos") or []
    if pasos:
        lineas.append("")
        lineas.append("*Por paso:*")
        for p in pasos:
            est = _NOMBRE_ESTADO.get(p.get("estado", ""), p.get("estado", ""))
            cr = p.get("creditos")
            cr_txt = f" — {cr} cr" if cr is not None else ""
            det = f" ({p['detalle']})" if p.get("detalle") else ""
            lineas.append(f"• {p.get('nombre', '?')}: {est}{cr_txt}{det}")

    # Proveedores usados.
    provs = desg.get("proveedores") or []
    if provs:
        lineas.append("")
        lineas.append("*Proveedores:*")
        for p in provs:
            etiqueta = p.get("proveedor", "?")
            if p.get("modelo"):
                etiqueta += f" ({p['modelo']})"
            estado = _NOMBRE_ESTADO.get(p.get("estado", ""), p.get("estado", ""))
            coste = p.get("coste_base")
            det = f" · {coste} {p.get('moneda', '')}".rstrip() if coste else ""
            lineas.append(f"• {etiqueta} — {estado}{det}")

    saldo = desg.get("saldo_posterior")
    if saldo is None:
        saldo = tx.get("saldo_resultante")
    lineas.append("")
    lineas.append(f"Saldo posterior: *{saldo}* créditos")
    lineas.append("")
    lineas.append("_No es una factura fiscal. ID copiable para soporte._")
    return "\n".join(lineas)
