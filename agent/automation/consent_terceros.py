# agent/automation/consent_terceros.py — Política de contacto a terceros (Fase 0 · 2.5)
# Dona

"""
Política Hermes (2026-06-10): "block until owner affirmative consent per
destination". Dona NO inicia contacto con un tercero frío sin que el owner
confirme explícitamente que tiene permiso para contactarlo.

Cómo encaja en el flujo HIGH dedicado (preparar → aprobar → preview →
confirmar ENVIAR):

  - El PREVIEW evalúa esta política. Si los límites bloquean, el preview lo
    dice y la confirmación se rechaza. Si el destino es frío, el preview
    muestra el TEXTO_CONSENTIMIENTO_OWNER y el mensaje FINAL compuesto (con
    identificación + PARAR si es primer contacto).
  - El CONFIRMAR (literal ENVIAR tras ese preview) constituye el
    consentimiento afirmativo: se registra en
    automation_consentimientos_tercero (texto mostrado + accion_id) ANTES
    de ejecutar.
  - El EJECUTOR exige consentimiento fresco para destinos fríos
    (defensa en profundidad): cualquier camino que llegue al ejecutor sin
    pasar por la confirmación dedicada se bloquea fail-closed.
  - Best-effort (solo opt-out vía gate de envíos) queda ÚNICAMENTE para
    destinos que YA hablaron con Dona (tienen mensajes inbound).

Límites (política Hermes, conservadores para la etapa actual):
  - Por destino sin respuesta: máx 2 mensajes/día, máx 3 mensajes/7 días.
  - Por destino que respondió (o ya conocido): máx 8 mensajes/día.
  - Por owner: máx 10 terceros NUEVOS/día, máx 30/7 días.
El opt-out duro del destino (STOP/PARAR al número de Dona) lo aplica el
gate de envíos (agent/envio_gate.py) ANTES de cualquier envío — esta
política se evalúa además de, no en lugar de, ese gate.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger("dona")

# Texto de permiso que ve el owner en el preview. Escribir ENVIAR después
# de verlo ES el consentimiento afirmativo que se registra.
TEXTO_CONSENTIMIENTO_OWNER = (
    "Al escribir ENVIAR confirmas que tienes permiso para contactar a este "
    "número por WhatsApp en este contexto."
)

# Ventana de frescura del consentimiento que exige el ejecutor: cubre el
# lapso preview→confirmar→ejecutar, sin dejar consentimientos viejos
# habilitando envíos futuros por caminos no dedicados.
MINUTOS_CONSENTIMIENTO_FRESCO = 15

# Límites por destino (mensajes iniciados por Dona)
MAX_MENSAJES_DESTINO_DIA_SIN_RESPUESTA = 2
MAX_MENSAJES_DESTINO_7D_SIN_RESPUESTA = 3
MAX_MENSAJES_DESTINO_DIA_CON_RESPUESTA = 8

# Límites por owner (terceros nuevos = primer envío de la historia)
MAX_TERCEROS_NUEVOS_DIA_OWNER = 10
MAX_TERCEROS_NUEVOS_7D_OWNER = 30


def normalizar_destino(numero: str) -> str:
    """Solo dígitos — misma forma en consentimientos, log de envíos y
    lookups contra la tabla de mensajes (formato webhook, sin '+')."""
    return "".join(c for c in str(numero or "") if c.isdigit())


def componer_mensaje_primer_contacto(
    nombre_owner: str, mensaje: str, max_total: int = 4000
) -> str:
    """Copy obligatorio de primer contacto (política Hermes): identificar
    quién escribe / en nombre de quién, y ofrecer opt-out con PARAR.

    Si encabezado+cuerpo+pie exceden el tope del proveedor, se trunca el
    CUERPO — la identificación y el opt-out nunca se recortan."""
    en_nombre_de = f" a pedido de {nombre_owner}" if nombre_owner else ""
    encabezado = f"Hola, soy Dona, escribiendo{en_nombre_de}:\n\n"
    pie = "\n\n_Si no quieres recibir más mensajes, responde *PARAR*._"
    disponible = max_total - len(encabezado) - len(pie)
    cuerpo = mensaje if len(mensaje) <= disponible else mensaje[: disponible - 1] + "…"
    return f"{encabezado}{cuerpo}{pie}"


async def destino_hablo_con_dona(destino: str) -> bool:
    """True si el destino tiene mensajes INBOUND (role='user') — es decir,
    ya conversó con Dona alguna vez y no es un contacto frío."""
    from sqlalchemy import exists, select

    from agent.memory import Mensaje, async_session

    destino_norm = normalizar_destino(destino)
    if not destino_norm:
        return False
    async with async_session() as session:
        result = await session.execute(
            select(
                exists().where(
                    Mensaje.telefono == destino_norm,
                    Mensaje.role == "user",
                )
            )
        )
        return bool(result.scalar())


async def _destino_respondio_desde(destino: str, desde: datetime) -> bool:
    """True si el destino escribió a Dona DESPUÉS de `desde` (respondió)."""
    from sqlalchemy import exists, select

    from agent.memory import Mensaje, async_session

    # Normalizar igual que destino_hablo_con_dona: Mensaje.telefono se guarda en
    # forma de webhook y el caller pasa el destino del owner — comparar por la
    # misma clave canónica o el lookup devuelve False de más (2.5).
    destino_norm = normalizar_destino(destino)
    if not destino_norm:
        return False
    async with async_session() as session:
        result = await session.execute(
            select(
                exists().where(
                    Mensaje.telefono == destino_norm,
                    Mensaje.role == "user",
                    Mensaje.timestamp > desde,
                )
            )
        )
        return bool(result.scalar())


async def evaluar_politica_envio_tercero(
    telefono_owner: str, numero_destino: str
) -> dict:
    """Evalúa la política ANTES de un envío HIGH a un tercero.

    Retorna dict con:
      permitido: bool
      motivo: '' | 'limite_destino_dia' | 'limite_destino_7d' |
              'limite_owner_terceros_dia' | 'limite_owner_terceros_7d'
      es_primer_contacto: bool (cero envíos históricos al destino)
      requiere_consentimiento: bool (destino frío → registrar consent)
      destino_conocido: bool (ya habló con Dona → best-effort, solo gate)

    Fail-closed la aplica el caller: si esta función LANZA, no se envía.
    """
    from sqlalchemy import func, select

    from agent.automation.models import EnvioTerceroAutomation
    from agent.memory import async_session

    destino = normalizar_destino(numero_destino)
    ahora = datetime.utcnow()
    hace_1d = ahora - timedelta(days=1)
    hace_7d = ahora - timedelta(days=7)

    conocido = await destino_hablo_con_dona(destino)

    async with async_session() as session:
        # Historial de envíos de Dona a este destino (de CUALQUIER owner:
        # los LÍMITES protegen al destinatario, no a la relación owner-destino)
        envios_destino = (await session.execute(
            select(
                func.count().label("total"),
                func.min(EnvioTerceroAutomation.enviado_en).label("primero"),
            ).where(EnvioTerceroAutomation.destino == destino)
        )).one()
        primer_envio = envios_destino.primero

        envios_destino_1d = (await session.execute(
            select(func.count()).where(
                EnvioTerceroAutomation.destino == destino,
                EnvioTerceroAutomation.enviado_en >= hace_1d,
            )
        )).scalar() or 0
        envios_destino_7d = (await session.execute(
            select(func.count()).where(
                EnvioTerceroAutomation.destino == destino,
                EnvioTerceroAutomation.enviado_en >= hace_7d,
            )
        )).scalar() or 0

        # La IDENTIFICACIÓN ("a pedido de X" + PARAR) es por par owner-destino:
        # si otro owner ya contactó al destino, ESTE owner igual debe
        # identificarse en su primer mensaje.
        envios_owner_destino = (await session.execute(
            select(func.count()).where(
                EnvioTerceroAutomation.telefono_owner == telefono_owner,
                EnvioTerceroAutomation.destino == destino,
            )
        )).scalar() or 0

    es_primer_contacto = (envios_owner_destino == 0) and not conocido

    resultado = {
        "permitido": True,
        "motivo": "",
        "es_primer_contacto": es_primer_contacto,
        "requiere_consentimiento": not conocido,
        "destino_conocido": conocido,
    }

    # ── Tier del destino: ¿respondió alguna vez a los envíos? ───────────
    if conocido or (
        primer_envio is not None
        and await _destino_respondio_desde(destino, primer_envio)
    ):
        if envios_destino_1d >= MAX_MENSAJES_DESTINO_DIA_CON_RESPUESTA:
            resultado.update(permitido=False, motivo="limite_destino_dia")
            return resultado
    else:
        # Frío y sin respuesta: límites estrictos
        if envios_destino_1d >= MAX_MENSAJES_DESTINO_DIA_SIN_RESPUESTA:
            resultado.update(permitido=False, motivo="limite_destino_dia")
            return resultado
        if envios_destino_7d >= MAX_MENSAJES_DESTINO_7D_SIN_RESPUESTA:
            resultado.update(permitido=False, motivo="limite_destino_7d")
            return resultado

    # ── Límite de terceros NUEVOS por owner ──────────────────────────────
    if es_primer_contacto:
        nuevos_1d = await _terceros_nuevos_owner_desde(telefono_owner, hace_1d)
        if nuevos_1d >= MAX_TERCEROS_NUEVOS_DIA_OWNER:
            resultado.update(permitido=False, motivo="limite_owner_terceros_dia")
            return resultado
        nuevos_7d = await _terceros_nuevos_owner_desde(telefono_owner, hace_7d)
        if nuevos_7d >= MAX_TERCEROS_NUEVOS_7D_OWNER:
            resultado.update(permitido=False, motivo="limite_owner_terceros_7d")
            return resultado

    return resultado


async def _terceros_nuevos_owner_desde(telefono_owner: str, desde: datetime) -> int:
    """Cuántos destinos DISTINTOS recibieron su PRIMER envío histórico de
    este owner a partir de `desde`."""
    from sqlalchemy import func, select

    from agent.automation.models import EnvioTerceroAutomation
    from agent.memory import async_session

    async with async_session() as session:
        sub = (
            select(
                EnvioTerceroAutomation.destino.label("destino"),
                func.min(EnvioTerceroAutomation.enviado_en).label("primero"),
            )
            .where(EnvioTerceroAutomation.telefono_owner == telefono_owner)
            .group_by(EnvioTerceroAutomation.destino)
            .subquery()
        )
        result = await session.execute(
            select(func.count()).select_from(sub).where(sub.c.primero >= desde)
        )
        return int(result.scalar() or 0)


async def registrar_consentimiento(
    telefono_owner: str,
    numero_destino: str,
    accion_id: int | None,
    texto_confirmacion: str = TEXTO_CONSENTIMIENTO_OWNER,
    scope: str = "este_mensaje",
) -> None:
    """Registra el consentimiento afirmativo del owner (append-only)."""
    from agent.automation.models import ConsentimientoTerceroAutomation
    from agent.memory import async_session

    async with async_session() as session:
        session.add(ConsentimientoTerceroAutomation(
            telefono_owner=telefono_owner,
            destino=normalizar_destino(numero_destino),
            scope=scope,
            texto_confirmacion=texto_confirmacion,
            source_accion_id=accion_id,
        ))
        await session.commit()
    logger.info(
        f"[CONSENT-2.5] Consentimiento registrado owner_short="
        f"{telefono_owner[-4:] if telefono_owner else '?'} "
        f"destino_short=...{normalizar_destino(numero_destino)[-4:]} "
        f"accion_id={accion_id} scope={scope}"
    )


async def tiene_consentimiento_fresco(
    telefono_owner: str,
    numero_destino: str,
    accion_id: int,
    max_minutos: int = MINUTOS_CONSENTIMIENTO_FRESCO,
) -> bool:
    """True si el owner registró consentimiento para este destino, PARA ESTA
    ACCIÓN, dentro de la ventana de frescura. Lo exige el ejecutor para
    destinos fríos.

    Invariante Hermes (visto bueno 2.5, condición #6): el consentimiento
    scope=este_mensaje NO se reutiliza entre mensajes — atarlo al accion_id
    impide que el consent de una acción habilite otra acción al mismo
    destino dentro de la ventana por un camino no dedicado."""
    from sqlalchemy import exists, select

    from agent.automation.models import ConsentimientoTerceroAutomation
    from agent.memory import async_session

    corte = datetime.utcnow() - timedelta(minutes=max_minutos)
    async with async_session() as session:
        result = await session.execute(
            select(
                exists().where(
                    ConsentimientoTerceroAutomation.telefono_owner == telefono_owner,
                    ConsentimientoTerceroAutomation.destino == normalizar_destino(numero_destino),
                    ConsentimientoTerceroAutomation.source_accion_id == accion_id,
                    ConsentimientoTerceroAutomation.creado >= corte,
                )
            )
        )
        return bool(result.scalar())


async def registrar_envio_tercero(
    telefono_owner: str, numero_destino: str, accion_id: int | None
) -> None:
    """Loguea un envío exitoso a un tercero (base de los límites)."""
    from agent.automation.models import EnvioTerceroAutomation
    from agent.memory import async_session

    async with async_session() as session:
        session.add(EnvioTerceroAutomation(
            telefono_owner=telefono_owner,
            destino=normalizar_destino(numero_destino),
            accion_id=accion_id,
        ))
        await session.commit()


async def obtener_nombre_owner(telefono_owner: str) -> str:
    """Nombre del owner para el copy de identificación (best-effort)."""
    try:
        from agent.memory import obtener_onboarding

        estado = await obtener_onboarding(telefono_owner)
        return (estado or {}).get("nombre", "") or ""
    except Exception:
        return ""
