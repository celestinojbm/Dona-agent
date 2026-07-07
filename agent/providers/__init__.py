# agent/providers/__init__.py — Factory de proveedores
# Dona

"""
Selecciona el proveedor de WhatsApp según la variable WHATSAPP_PROVIDER en .env.

Twilio está DECLARADO (documentado en CLAUDE.md/README/.env.example y con
manejo de su formato de teléfono en envio_gate.py) pero su módulo
`agent/providers/twilio.py` AÚN NO está implementado. El factory no debe
delatar eso con un ModuleNotFoundError críptico en el primer webhook: si
alguien configura un proveedor válido cuyo módulo no existe, fallamos
EXPLÍCITO y temprano con un mensaje accionable (Fase 0 · TEMA 2).
"""

import importlib
import importlib.util
import os

from agent.providers.base import ProveedorWhatsApp

# Proveedores válidos → (módulo, clase). El módulo puede no existir todavía
# (Twilio): en ese caso el factory falla con mensaje claro, no con
# ModuleNotFoundError críptico. Mantener sincronizado con
# agent/readiness.py:_SECRET_POR_PROVEEDOR.
_PROVEEDORES = {
    "whapi": ("agent.providers.whapi", "ProveedorWhapi"),
    "meta": ("agent.providers.meta", "ProveedorMeta"),
    "twilio": ("agent.providers.twilio", "ProveedorTwilio"),
}


def proveedores_soportados() -> list[str]:
    """Nombres de proveedores aceptados por WHATSAPP_PROVIDER (declarados)."""
    return list(_PROVEEDORES)


def modulo_de_proveedor_falta(proveedor: str) -> bool:
    """True si el proveedor es válido pero su módulo no se puede importar.

    Detecta el caso Twilio (declarado pero sin implementar) sin instanciar
    nada, para que readiness pueda alarmar en el arranque.
    """
    entrada = _PROVEEDORES.get(proveedor.lower())
    if entrada is None:
        return False  # no soportado es otro problema (lo maneja el caller)
    nombre_modulo, _ = entrada
    return importlib.util.find_spec(nombre_modulo) is None


def obtener_proveedor() -> ProveedorWhatsApp:
    """Retorna el proveedor de WhatsApp configurado en .env.

    Falla EXPLÍCITO si el valor no está soportado o si su módulo no existe
    (p. ej. WHATSAPP_PROVIDER=twilio sin agent/providers/twilio.py).
    """
    proveedor = os.getenv("WHATSAPP_PROVIDER", "whapi").lower()

    entrada = _PROVEEDORES.get(proveedor)
    if entrada is None:
        soportados = ", ".join(proveedores_soportados())
        raise ValueError(
            f"Proveedor no soportado: {proveedor}. Usa: {soportados}"
        )

    nombre_modulo, nombre_clase = entrada
    if importlib.util.find_spec(nombre_modulo) is None:
        raise RuntimeError(
            f"WHATSAPP_PROVIDER={proveedor} pero {nombre_modulo.replace('.', '/')}.py "
            "no existe (proveedor declarado pero sin implementar). "
            "Implementa el módulo o cambia WHATSAPP_PROVIDER a whapi/meta."
        )

    modulo = importlib.import_module(nombre_modulo)
    clase = getattr(modulo, nombre_clase)
    return clase()
