"""Política de canal secundario: WhatsApp solo para avisos y aprobaciones (F35).

Qué decide: si un mensaje con cierto *propósito* puede salir por WhatsApp o
debe quedarse en la app. No decide si se puede enviar (eso es de
`agent/envio_gate.py`: TCPA, quiet hours, opt-out, límite diario) y no envía
nada. Este módulo no importa el gate de envío ni los proveedores.

Taxonomía de propósitos (mapeo con lo que ya existe en el repo):

| Origen                                                        | Propósito          | WhatsApp con flag on |
|---------------------------------------------------------------|--------------------|----------------------|
| Aviso terminal de F14 (`plan_vivo.formato.notificacion_terminal`) | `aviso`        | sí                   |
| Tope de uso al 80 % / 100 % (`multi_model/presupuesto.py`, F32)   | `aviso`        | sí                   |
| L3 «ejecuta y notifica», recordatorio puntual, alerta de plazo    | `aviso`        | sí                   |
| Firma pendiente, plan cambiado (F14), confirmar acción HIGH       | `aprobacion`   | sí                   |
| Confirmación de STOP/START u otro acuse TCPA                      | `cumplimiento_tcpa` | sí              |
| Respuesta conversacional DIRECTO                                  | `conversacion` | no → app             |
| Morning brief, weekly review, consejo estratégico                 | `proactividad` | no → app             |
| Push de onboarding                                                | `onboarding`   | no → app             |
| Entrega de jobs creativos                                         | `creativo`     | no → app             |

Flag `DONA_WHATSAPP_SOLO_AVISOS_ENABLED` (apagado por defecto). Se lee en cada
llamada, sin cachear, para que `monkeypatch.setenv` funcione en tests.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_ENV_FLAG = "DONA_WHATSAPP_SOLO_AVISOS_ENABLED"
# Mismo criterio que agent/efectos.py: solo un valor explícito enciende.
_VERDADEROS = frozenset({"true", "1", "yes", "on"})

PROPOSITOS_WHATSAPP = frozenset({"aviso", "aprobacion", "cumplimiento_tcpa"})

# Propósitos conocidos que, con el flag encendido, se quedan en la app. Sirven
# solo para distinguir la razón (`proposito_no_permitido` frente a
# `proposito_desconocido`); la denegación no depende de esta lista: todo lo que
# no esté en PROPOSITOS_WHATSAPP se niega (fail-closed, sin lista gris).
PROPOSITOS_SOLO_APP = frozenset({"conversacion", "proactividad", "onboarding", "creativo"})

DESTINO_WHATSAPP = "whatsapp"
DESTINO_APP = "app"

RAZON_FLAG_APAGADO = "flag_apagado"
RAZON_PERMITIDO = "proposito_permitido"
RAZON_NO_PERMITIDO = "proposito_no_permitido"
RAZON_DESCONOCIDO = "proposito_desconocido"

# Copy breve para WhatsApp (app-first): una o dos frases, sin markdown pesado.
LARGO_MAXIMO_COPY = 200
_ELIPSIS = "…"
_SUFIJO_DETALLE_APP = "Revisa el detalle en la app."
_PREFIJO_APROBACION = "Necesito tu aprobación: "
_SUFIJO_APROBACION = "Revísalo y autorízalo en la app."
_AVISO_SIN_TITULO = "Tienes un aviso nuevo"
_APROBACION_SIN_TITULO = "una acción pendiente"
# Marcadores de formato de WhatsApp que convertirían el aviso en markdown.
_MARCADORES_FORMATO = re.compile(r"[*~`]")
_ESPACIOS = re.compile(r"\s+")


@dataclass(frozen=True)
class DecisionCanal:
    """Resultado de la política. `razon` es un código estable, no frase libre."""

    permitido_whatsapp: bool
    proposito: str
    razon: str
    destino: str


def flag_solo_avisos_activo() -> bool:
    """True solo si DONA_WHATSAPP_SOLO_AVISOS_ENABLED es `true`/`1`/`yes`/`on`
    (minúsculas tras strip). Ausente, vacío u otro valor → False."""
    return os.getenv(_ENV_FLAG, "").strip() in _VERDADEROS


def _normalizar_proposito(proposito: object) -> str:
    if not isinstance(proposito, str):
        return ""
    return proposito.strip().lower()


def decidir_canal(proposito: str, *, flag: bool | None = None) -> DecisionCanal:
    """Decide si un mensaje con `proposito` puede ir por WhatsApp o va a la app.

    - `flag=None` lee `DONA_WHATSAPP_SOLO_AVISOS_ENABLED`; `True`/`False`
      explícito ignora el entorno (inyección para tests y llamadores).
    - Flag apagado: todo permitido (`razon="flag_apagado"`), *incluido* un
      propósito vacío o desconocido. Trade-off deliberado: hoy el gate de envío
      no conoce esta taxonomía, así que con el flag apagado la política no
      puede cambiar lo que ya sale por WhatsApp.
    - Flag encendido: solo `PROPOSITOS_WHATSAPP` sale por WhatsApp. Cualquier
      otro propósito (conocido, typo, vacío o no string) va a la app.
      Fail-closed: no hay lista gris.

    No envía, no consulta `envio_gate` y no relaja TCPA: `cumplimiento_tcpa`
    permitido aquí solo significa que el canal es admisible; el gate decide.
    """
    normalizado = _normalizar_proposito(proposito)
    activo = flag_solo_avisos_activo() if flag is None else bool(flag)

    if not activo:
        return DecisionCanal(True, normalizado, RAZON_FLAG_APAGADO, DESTINO_WHATSAPP)
    if normalizado in PROPOSITOS_WHATSAPP:
        return DecisionCanal(True, normalizado, RAZON_PERMITIDO, DESTINO_WHATSAPP)
    razon = RAZON_NO_PERMITIDO if normalizado in PROPOSITOS_SOLO_APP else RAZON_DESCONOCIDO
    return DecisionCanal(False, normalizado, razon, DESTINO_APP)


def _limpiar_titulo(titulo: object) -> str:
    """Una sola línea, sin marcadores de formato ni punto final."""
    if not isinstance(titulo, str):
        return ""
    texto = _MARCADORES_FORMATO.sub("", titulo)
    texto = _ESPACIOS.sub(" ", texto).strip()
    return texto.rstrip(" .")


def _recortar(texto: str, maximo: int) -> str:
    if maximo <= 0:
        return ""
    if len(texto) <= maximo:
        return texto
    return texto[: maximo - len(_ELIPSIS)].rstrip() + _ELIPSIS


def _cerrar(texto: str) -> str:
    """Añade punto final salvo que ya cierre con signo o elipsis."""
    return texto if texto.endswith(("!", "?", _ELIPSIS)) else f"{texto}."


def redactar_aviso(titulo: str, *, detalle_en_app: bool = True) -> str:
    """Aviso breve para WhatsApp (no se envía aquí; no consulta el flag).

    Con `detalle_en_app` añade «Revisa el detalle en la app.», el mismo tono
    que `plan_vivo.formato.notificacion_terminal`. Máximo
    `LARGO_MAXIMO_COPY` caracteres; un título largo se recorta con elipsis.
    """
    sufijo = f" {_SUFIJO_DETALLE_APP}" if detalle_en_app else ""
    cuerpo = _limpiar_titulo(titulo) or _AVISO_SIN_TITULO
    cuerpo = _recortar(cuerpo, LARGO_MAXIMO_COPY - len(sufijo) - 1)
    return f"{_cerrar(cuerpo)}{sufijo}"


def redactar_aprobacion(titulo: str) -> str:
    """Pedido breve de aprobación: deja claro que se autoriza en la app.

    Sin enlaces, tokens ni teléfonos. No consulta el flag: quien envíe debe
    haber pasado antes por `decidir_canal`. Máximo `LARGO_MAXIMO_COPY`.
    """
    sufijo = f" {_SUFIJO_APROBACION}"
    cuerpo = _limpiar_titulo(titulo) or _APROBACION_SIN_TITULO
    disponible = LARGO_MAXIMO_COPY - len(_PREFIJO_APROBACION) - len(sufijo) - 1
    cuerpo = _cerrar(_recortar(cuerpo, disponible))
    return f"{_PREFIJO_APROBACION}{cuerpo}{sufijo}"
