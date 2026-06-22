# agent/envio_gate.py — Gate central de envíos salientes de WhatsApp (Fase 0 · 2.1)
# Dona

"""
TODO envío saliente de WhatsApp pasa por `puede_enviar()` ANTES de tocar la
API del proveedor. El choke point vive en `ProveedorWhatsApp`
(providers/base.py): los métodos públicos `enviar_*` consultan este gate y
solo entonces delegan en `_enviar_*_impl`. Los ~150 call sites del repo no
llaman al gate directamente — heredan la clasificación vía ContextVar.

Clasificación del envío (de menos a más restrictivo):

  DIRECTO     Respuesta a un mensaje inbound del usuario (incluye la
              confirmación de STOP y el aviso de sobrecarga), entrega de un
              trabajo que él mismo pidió (jobs creativos) o mensaje
              transaccional (post-pago Stripe, post-OAuth). Sin checks: el
              usuario inició el contacto, y la conversación reactiva sigue
              viva tras STOP ("Sigues pudiendo escribirme cuando necesites
              algo"). El contexto va atado al teléfono del usuario: un envío
              a OTRO número dentro de un contexto DIRECTO no hereda la
              exención (cae a PROACTIVO).

  AUTOMATICO  Contenido programado o configurado por el propio usuario
              (recordatorios, eventos de Google Calendar, seguimientos CRM,
              webhook inbound de Zapier/Make), alertas operativas al admin,
              y el ejecutor HIGH de automation (donde el teléfono evaluado es
              el del TERCERO destinatario). Respeta opt-out fail-closed —
              el copy de STOP promete "no te enviaré recordatorios ni
              resúmenes automáticos" — pero sin quiet hours ni límite diario:
              la hora la eligió el usuario al programar el contenido.

  PROACTIVO   (default) Todo lo no etiquetado: motor de proactividad,
              onboarding push, resumen semanal, y cualquier path futuro que
              olvide declararse. Opt-out fail-closed + quiet hours (solo con
              timezone conocida) + límite diario compartido
              (MAX_MENSAJES_DIARIOS), contado AQUÍ en el gate.

Fail-closed: si la lectura del opt-out / timezone / contador FALLA, el envío
se BLOQUEA y se loguea CRITICAL. Un error de DB nunca puede convertirse en
un mensaje no consentido (riesgo TCPA: $500–1500 por mensaje).

Supresión de emergencia: registro in-memory (per-worker) de teléfonos que
enviaron STOP, poblado ANTES de intentar persistir el opt-out. Si la
persistencia falla, el gate igual bloquea AUTOMATICO/PROACTIVO en este
worker hasta el próximo deploy/restart. Es un cinturón best-effort, NO un
reemplazo de la persistencia durable (PR #74).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime

logger = logging.getLogger("dona")

# Tipos de envío — ver docstring del módulo.
TIPO_DIRECTO = "directo"
TIPO_AUTOMATICO = "automatico"
TIPO_PROACTIVO = "proactivo"

# Hora local (0-23) antes de la cual NO se envían mensajes PROACTIVOS.
# Mismo umbral que la guardia nocturna del motor de proactividad.
HORA_INICIO_ENVIOS_PROACTIVOS = 7

# Contexto del envío en curso: (tipo, telefono | None).
# DIRECTO va atado a un teléfono; AUTOMATICO aplica a cualquier destino.
_ctx_envio: ContextVar[tuple[str, str | None] | None] = ContextVar(
    "ctx_envio", default=None
)

# Supresión de emergencia in-memory (per-worker). Ver docstring del módulo.
_supresion_emergencia: set[str] = set()


# ── Normalización de teléfono · clave canónica del opt-out (2.5) ───────────
# Cada proveedor entrega el teléfono distinto: whapi '<dígitos>@s.whatsapp.net',
# meta '<dígitos>' (campo from), twilio 'whatsapp:+<dígitos>'; y el owner tipea
# numero_destino con '+' opcional. El opt-out y la supresión deben comparar por
# IDENTIDAD del número, no por el formato crudo: si no, un STOP de un tercero
# (guardado bajo su chat_id) no matchea cuando el gate llega con el
# numero_destino del owner, y el mensaje sale pese al opt-out (riesgo TCPA).


def normalizar_telefono(telefono: str) -> str:
    """Solo dígitos — colapsa los formatos de los 3 proveedores al mismo
    número. Misma forma canónica que consent_terceros.normalizar_destino."""
    return "".join(c for c in str(telefono or "") if c.isdigit())


def clave_canonica(telefono: str) -> str:
    """Clave canónica del opt-out: los dígitos del teléfono, o —si no hay
    dígitos (id de grupo/alfanumérico)— el valor crudo. El fallback al crudo
    evita que entradas sin dígitos colapsen todas a '' y compartan una fila."""
    return normalizar_telefono(telefono) or str(telefono or "")


@contextmanager
def contexto_envio_directo(telefono: str):
    """Marca los envíos a `telefono` dentro del bloque como DIRECTO."""
    token = _ctx_envio.set((TIPO_DIRECTO, telefono))
    try:
        yield
    finally:
        _ctx_envio.reset(token)


@contextmanager
def contexto_envio_automatico():
    """Marca los envíos dentro del bloque como AUTOMATICO."""
    token = _ctx_envio.set((TIPO_AUTOMATICO, None))
    try:
        yield
    finally:
        _ctx_envio.reset(token)


@contextmanager
def contexto_envio_proactivo():
    """Fuerza PROACTIVO dentro del bloque, ANULANDO un contexto heredado.

    Necesario para envíos conceptualmente proactivos que nacen dentro del
    procesamiento de un mensaje inbound (p. ej. el aviso de sobrecarga,
    lanzado con create_task desde el webhook): sin esto heredarían DIRECTO
    y evadirían opt-out, quiet hours y límite diario."""
    token = _ctx_envio.set((TIPO_PROACTIVO, None))
    try:
        yield
    finally:
        _ctx_envio.reset(token)


def activar_contexto_directo(telefono: str):
    """Variante imperativa de `contexto_envio_directo` para bloques donde un
    `with` obligaría a re-indentar cientos de líneas (loop del webhook).
    Devuelve el token; restaurar con `restaurar_contexto(token)`."""
    return _ctx_envio.set((TIPO_DIRECTO, telefono))


def restaurar_contexto(token) -> None:
    _ctx_envio.reset(token)


def _tipo_efectivo(telefono_destino: str) -> str:
    """Resuelve el tipo de envío para `telefono_destino` según el contexto.
    Sin contexto → PROACTIVO (lo más restrictivo). DIRECTO solo aplica si el
    destino coincide con el teléfono del contexto."""
    ctx = _ctx_envio.get()
    if ctx is None:
        return TIPO_PROACTIVO
    tipo, telefono_ctx = ctx
    if tipo == TIPO_DIRECTO:
        return TIPO_DIRECTO if telefono_ctx == telefono_destino else TIPO_PROACTIVO
    return tipo


# ── Supresión de emergencia ──────────────────────────────────────────────


def registrar_supresion_emergencia(telefono: str) -> None:
    """Suprime envíos AUTOMATICO/PROACTIVO a `telefono` en este worker,
    independientemente de lo que diga (o no pueda decir) la DB. Se indexa por
    la clave canónica (dígitos) para que un STOP entrante y un envío saliente
    con formatos distintos del mismo número coincidan (2.5)."""
    _supresion_emergencia.add(clave_canonica(telefono))
    logger.warning(f"[GATE] Supresión de emergencia registrada para {telefono}")


def limpiar_supresion_emergencia(telefono: str) -> None:
    """Levanta la supresión de emergencia (re-opt-in vía START)."""
    _supresion_emergencia.discard(clave_canonica(telefono))


def esta_suprimido_emergencia(telefono: str) -> bool:
    return clave_canonica(telefono) in _supresion_emergencia


# ── Gate principal ───────────────────────────────────────────────────────


async def puede_enviar(telefono: str) -> bool:
    """Decide si un envío saliente a `telefono` está permitido.

    Llamado por ProveedorWhatsApp antes de cada envío. Fail-closed: ante
    cualquier error leyendo el estado del usuario, retorna False.
    """
    tipo = _tipo_efectivo(telefono)

    if tipo == TIPO_DIRECTO:
        return True

    # ── Supresión de emergencia (STOP que pudo no persistir) ────────────
    if esta_suprimido_emergencia(telefono):
        logger.warning(
            f"[GATE] Envío bloqueado tipo={tipo} motivo=supresion_emergencia "
            f"tel={telefono}"
        )
        return False

    # ── Opt-out TCPA (proactive_enabled) — fail-closed ──────────────────
    # Se evalúa por IDENTIDAD del número (clave canónica en dígitos) ADEMÁS del
    # teléfono crudo: un STOP de un tercero se persiste bajo sus dígitos, pero
    # el gate llega con el numero_destino que tipeó el owner (con '+' u otro
    # formato del proveedor). Leer ambas representaciones evita perder el
    # opt-out de un tercero por mismatch de formato (2.5).
    from agent.memory import obtener_proactividad

    clave = clave_canonica(telefono)
    try:
        config_canon = (
            await obtener_proactividad(clave) if clave != telefono else None
        )
        config_exact = await obtener_proactividad(telefono)
    except Exception as e:
        logger.critical(
            f"[GATE] FAIL-CLOSED: error leyendo opt-out de {telefono} "
            f"({type(e).__name__}: {e}) — envío {tipo} BLOQUEADO"
        )
        return False

    # La fila CANÓNICA (en dígitos) es autoritativa si existe: los STOP/START
    # nuevos la escriben bajo la identidad del número, así un opt-out de un
    # tercero (canónica disabled) se respeta aunque el gate llegue con otro
    # formato, y un re-opt-in posterior (canónica enabled) deja pasar sin que
    # una representación cruda vieja lo trabe. Si NO hay fila canónica, se cae a
    # la cruda (filas pre-existentes del owner — sin migración). Sin fila →
    # nunca tocó su proactividad → habilitado.
    config = config_canon if config_canon is not None else config_exact

    if config is not None and not config.get("proactive_enabled", True):
        logger.info(
            f"[GATE] Envío bloqueado tipo={tipo} motivo=optout tel={telefono}"
        )
        return False

    if tipo == TIPO_AUTOMATICO:
        return True

    # ── Solo PROACTIVO: quiet hours + límite diario ──────────────────────

    # Quiet hours: solo con timezone conocida. Aplicar la hora UTC a un
    # usuario de EEUU (UTC-5..-8) bloquearía las tardes, no las madrugadas.
    from agent.memory import obtener_timezone

    try:
        offset_min = await obtener_timezone(telefono)
    except Exception as e:
        logger.critical(
            f"[GATE] FAIL-CLOSED: error leyendo timezone de {telefono} "
            f"({type(e).__name__}: {e}) — envío proactivo BLOQUEADO"
        )
        return False

    if offset_min is not None:
        from datetime import timedelta

        hora_local = (datetime.utcnow() + timedelta(minutes=offset_min)).hour
        if hora_local < HORA_INICIO_ENVIOS_PROACTIVOS:
            logger.info(
                f"[GATE] Envío bloqueado tipo=proactivo motivo=quiet_hours "
                f"hora_local={hora_local} tel={telefono}"
            )
            return False

    # Límite diario compartido (reset por fecha UTC, igual que
    # incrementar_mensajes_proactivos).
    from agent.proactivity import MAX_MENSAJES_DIARIOS

    mensajes_hoy = 0
    if config is not None:
        ultimo_reset = config.get("ultimo_reset")
        if ultimo_reset is not None and ultimo_reset.date() >= datetime.utcnow().date():
            mensajes_hoy = config.get("mensajes_hoy") or 0
    if mensajes_hoy >= MAX_MENSAJES_DIARIOS:
        logger.info(
            f"[GATE] Envío bloqueado tipo=proactivo motivo=limite_diario "
            f"({mensajes_hoy}/{MAX_MENSAJES_DIARIOS}) tel={telefono}"
        )
        return False

    return True


async def registrar_envio_realizado(telefono: str) -> None:
    """Bookkeeping post-envío exitoso. Para envíos PROACTIVOS incrementa el
    contador diario compartido (el motor de proactividad ya NO incrementa por
    su cuenta — el conteo vive aquí, en el choke point). Best-effort: un
    fallo del contador no debe romper el envío ya hecho."""
    if _tipo_efectivo(telefono) != TIPO_PROACTIVO:
        return
    try:
        from agent.memory import incrementar_mensajes_proactivos

        await incrementar_mensajes_proactivos(telefono)
    except Exception as e:
        logger.error(
            f"[GATE] No se pudo incrementar contador proactivo de {telefono}: "
            f"{type(e).__name__}: {e}"
        )
