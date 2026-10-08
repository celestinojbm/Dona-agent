# agent/efectos.py — Interruptores de efectos externos (J4 · arranque sin efectos)

"""
Punto único que decide qué efectos externos puede producir este proceso.

Dona está retirada de circulación (pausa). El backend tiene que poder
arrancar —en staging, en la MSI o por un redeploy accidental de `main`—
SIN enviar mensajes, sin procesar cobros y sin llamadas facturables a
modelos. Por eso **todos los interruptores están apagados por defecto**:
solo un `true` explícito los enciende.

Interruptores (``1``/``true``/``yes``/``on``, sin distinguir mayúsculas):

  DONA_SCHEDULER_ENABLED   APScheduler (recordatorios, proactividad,
                           resúmenes, monitoreo, simulaciones, limpieza).
  DONA_WORKER_ENABLED      ejecución de jobs en segundo plano (arq o inproc).
  DONA_WHATSAPP_ENABLED    canal WhatsApp: webhooks entrantes y envíos.
  DONA_STRIPE_ENABLED      procesamiento de eventos de Stripe.
  DONA_LLM_ENABLED         llamadas a modelos (vía el guard de presupuesto).
  DONA_INBOUND_ENABLED     webhooks entrantes firmados (Zapier/Make/n8n).

Dónde se aplican (choke points existentes, no call sites sueltos):

  - whatsapp → ``envio_gate.puede_enviar`` (todos los ``enviar_*`` del
    proveedor pasan por ahí) + rutas ``/webhook*`` en ``main.py``.
  - llm      → ``presupuesto_runtime.kill_switch_global_activo``: con LLM
    apagado toda reserva LLM se deniega como con el kill-switch global.
  - scheduler → ``scheduler.iniciar_scheduler``.
  - worker   → ``jobs.worker`` (arranque del worker arq y ejecución de jobs).
  - stripe / inbound → sus rutas en ``main.py``.

Las variables se leen en cada llamada (no se cachean), como en
``agent/entorno.py``, para que los tests puedan usar ``monkeypatch``.
"""

from __future__ import annotations

import os

# nombre corto → variable de entorno
INTERRUPTORES: dict[str, str] = {
    "scheduler": "DONA_SCHEDULER_ENABLED",
    "worker": "DONA_WORKER_ENABLED",
    "whatsapp": "DONA_WHATSAPP_ENABLED",
    "stripe": "DONA_STRIPE_ENABLED",
    "llm": "DONA_LLM_ENABLED",
    "inbound": "DONA_INBOUND_ENABLED",
}

_VERDADEROS = ("1", "true", "yes", "on")

# Requisitos entre interruptores: encender el de la izquierda sin los de la
# derecha es una configuración incoherente (el arranque la rechaza).
#   - El scheduler existe para enviar recordatorios/resúmenes por WhatsApp y
#     sus jobs llaman a modelos: sin esos efectos solo haría trabajo a medias.
_REQUISITOS: dict[str, tuple[str, ...]] = {
    "scheduler": ("whatsapp", "llm"),
}


def efecto_habilitado(nombre: str) -> bool:
    """True solo si el interruptor del efecto está explícitamente encendido."""
    var = INTERRUPTORES[nombre]  # KeyError si el nombre no existe: a propósito
    return os.getenv(var, "").strip().lower() in _VERDADEROS


def resumen_efectos() -> dict[str, bool]:
    """Estado de todos los interruptores (solo booleanos, sin secretos)."""
    return {nombre: efecto_habilitado(nombre) for nombre in INTERRUPTORES}


def problemas_de_efectos() -> list[str]:
    """Incoherencias entre interruptores encendidos y sus requisitos.

    Vacía si la combinación es válida. No mira secretos (eso es
    ``agent/readiness.py``), solo dependencias entre efectos.
    """
    problemas: list[str] = []
    for efecto, requisitos in _REQUISITOS.items():
        if not efecto_habilitado(efecto):
            continue
        faltan = [r for r in requisitos if not efecto_habilitado(r)]
        if faltan:
            problemas.append(
                f"{INTERRUPTORES[efecto]}=true requiere "
                + ", ".join(f"{INTERRUPTORES[r]}=true" for r in faltan)
            )
    return problemas


class ConfiguracionEfectosError(RuntimeError):
    """Combinación de interruptores incoherente: el proceso no debe arrancar."""


def verificar_efectos() -> None:
    """Aborta el arranque si la combinación de interruptores es incoherente.

    Aplica en TODOS los entornos (también dev/test): no se trata de secretos
    sino de no arrancar tareas habilitadas sin sus requisitos.
    """
    problemas = problemas_de_efectos()
    if problemas:
        raise ConfiguracionEfectosError(
            "[EFECTOS] Configuración incoherente:\n  - " + "\n  - ".join(problemas)
        )
