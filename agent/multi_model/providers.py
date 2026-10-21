"""Capa común de proveedores de modelos (F23).

Interfaz única `ProveedorModelo.generar(...)` para Anthropic, OpenAI y Google.
Las claves se leen SÓLO de variables de entorno del backend (nunca en código ni
expuestas al front). Los adaptadores reales construyen su cliente de forma
perezosa; en pruebas se usa `ProveedorSimulado`, que NUNCA hace red (presupuesto
0 USD).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from agent.multi_model.catalogo import costo_estimado_usd, info_modelo

logger = logging.getLogger("dona")


@dataclass
class RespuestaModelo:
    modelo: str
    proveedor: str
    texto: str
    tokens_in: int = 0
    tokens_out: int = 0
    costo_usd: str | None = None  # Decimal como string, nunca float
    simulado: bool = False
    meta: dict = field(default_factory=dict)


class ProveedorModelo:
    """Interfaz común. Los adaptadores reales la implementan; el simulado también."""

    proveedor: str = "base"

    async def generar(
        self,
        *,
        modelo: str,
        mensajes: list[dict],
        system: str = "",
        max_tokens: int = 1024,
        **kw,
    ) -> RespuestaModelo:  # pragma: no cover - interfaz
        raise NotImplementedError


def _costo(modelo: str, tin: int, tout: int) -> str | None:
    c = costo_estimado_usd(modelo, tin, tout)
    return str(c) if c is not None else None


class ProveedorSimulado(ProveedorModelo):
    """Proveedor determinístico sin red (para pruebas y para el modo demo).

    Produce una respuesta reproducible a partir del último mensaje; estima tokens
    por longitud. No consume créditos reales ni llama a ninguna API de pago.
    """

    proveedor = "simulado"

    def __init__(self, etiqueta: str = "sim"):
        self.etiqueta = etiqueta

    async def generar(
        self, *, modelo, mensajes, system="", max_tokens=1024, **kw
    ) -> RespuestaModelo:
        ultimo = mensajes[-1]["content"] if mensajes else ""
        texto = f"[{self.etiqueta}:{modelo}] respuesta simulada a: {str(ultimo)[:80]}"
        tin = (len(system) + sum(len(str(m.get('content', ''))) for m in mensajes)) // 4
        tout = len(texto) // 4
        info = info_modelo(modelo)
        return RespuestaModelo(
            modelo=modelo,
            proveedor=(info.proveedor if info else "desconocido"),
            texto=texto,
            tokens_in=tin,
            tokens_out=tout,
            costo_usd=_costo(modelo, tin, tout),
            simulado=True,
        )


# ── Adaptadores reales (lazy; claves sólo de env; NO se llaman en pruebas) ──

class ProveedorAnthropic(ProveedorModelo):
    proveedor = "anthropic"
    _env_key = "ANTHROPIC_API_KEY"

    def _cliente(self):
        key = os.getenv(self._env_key, "")
        if not key:
            raise RuntimeError(f"{self._env_key} no configurada (clave sólo por env)")
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=key)

    async def generar(
        self, *, modelo, mensajes, system="", max_tokens=1024, **kw
    ) -> RespuestaModelo:  # pragma: no cover - requiere API real (no se prueba)
        cliente = self._cliente()
        kwargs = dict(model=modelo, max_tokens=max_tokens, messages=mensajes)
        if system:
            kwargs["system"] = system
        resp = await cliente.messages.create(**kwargs)
        tin = int(getattr(resp.usage, "input_tokens", 0) or 0)
        tout = int(getattr(resp.usage, "output_tokens", 0) or 0)
        return RespuestaModelo(
            modelo=modelo, proveedor=self.proveedor,
            texto=(resp.content[0].text if resp.content else ""),
            tokens_in=tin, tokens_out=tout, costo_usd=_costo(modelo, tin, tout),
        )


class ProveedorOpenAI(ProveedorModelo):
    proveedor = "openai"
    _env_key = "OPENAI_API_KEY"

    def _cliente(self):
        key = os.getenv(self._env_key, "")
        if not key:
            raise RuntimeError(f"{self._env_key} no configurada (clave sólo por env)")
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=key)

    async def generar(
        self, *, modelo, mensajes, system="", max_tokens=1024, **kw
    ) -> RespuestaModelo:  # pragma: no cover - requiere API real (no se prueba)
        cliente = self._cliente()
        msgs = ([{"role": "system", "content": system}] if system else []) + mensajes
        resp = await cliente.chat.completions.create(
            model=modelo, max_tokens=max_tokens, messages=msgs
        )
        usage = getattr(resp, "usage", None)
        tin = int(getattr(usage, "prompt_tokens", 0) or 0)
        tout = int(getattr(usage, "completion_tokens", 0) or 0)
        return RespuestaModelo(
            modelo=modelo, proveedor=self.proveedor,
            texto=resp.choices[0].message.content or "",
            tokens_in=tin, tokens_out=tout, costo_usd=_costo(modelo, tin, tout),
        )


class ProveedorGoogle(ProveedorModelo):
    proveedor = "google"
    _env_key = "GEMINI_API_KEY"  # o GOOGLE_API_KEY

    def _api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

    async def generar(
        self, *, modelo, mensajes, system="", max_tokens=1024, **kw
    ) -> RespuestaModelo:  # pragma: no cover - requiere API real (no se prueba)
        if not self._api_key():
            raise RuntimeError("GEMINI_API_KEY/GOOGLE_API_KEY no configurada (sólo env)")
        # La integración concreta de texto con Gemini se añade al activar el flag;
        # hoy Gemini se usa para imagen en agent/creativos. Placeholder explícito.
        raise NotImplementedError("Adaptador de texto Gemini pendiente de activar")


# Proveedores reales por nombre.
_PROVEEDORES_REALES: dict[str, ProveedorModelo] = {
    "anthropic": ProveedorAnthropic(),
    "openai": ProveedorOpenAI(),
    "google": ProveedorGoogle(),
}

# Override inyectable para pruebas: si está set, se usa en vez de los reales.
_proveedor_forzado: ProveedorModelo | None = None


def forzar_proveedor(proveedor: ProveedorModelo | None) -> None:
    """Inyecta un proveedor (p. ej. ProveedorSimulado) para pruebas/demo."""
    global _proveedor_forzado
    _proveedor_forzado = proveedor


def proveedor_para(modelo_id: str) -> ProveedorModelo:
    """Devuelve el proveedor para un modelo. Si hay uno forzado (pruebas/demo),
    lo usa. Si no, el real según el catálogo."""
    if _proveedor_forzado is not None:
        return _proveedor_forzado
    info = info_modelo(modelo_id)
    if info is None:
        raise ValueError(f"modelo desconocido: {modelo_id}")
    prov = _PROVEEDORES_REALES.get(info.proveedor)
    if prov is None:
        raise ValueError(f"proveedor desconocido: {info.proveedor}")
    return prov
