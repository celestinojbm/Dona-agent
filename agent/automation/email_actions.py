# agent/automation/email_actions.py — Dominio persistente del correo (PR 1)

"""
Primera escritura controlada de Dona: la acción `enviar_correo_gmail`
persistida en `acciones_automatizacion`, en reemplazo del dict en
memoria `_borradores_pendientes` de brain.py.

Este módulo contiene ÚNICAMENTE:
  - preparación persistente e idempotente (preparation_request_key);
  - preview owner-scoped con token de confirmación;
  - confirmación VALIDADA sin aprobación (PR 1 · fail-closed);
  - cancelación, reemplazo y expiración (TTL 24 h);
  - cifrado/descifrado vía email_crypto y audit vía email_audit.

PROHIBIDO aquí (regla absoluta del PR 1): importar Gmail o un executor,
llamar ejecutar_accion, crear reservas o delivery attempts, marcar
approved/running, o cualquier I/O externo. Aunque EMAIL_SEND_ENABLED
aparezca en el entorno, la confirmación válida mantiene needs_approval
y NO materializa nada.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from agent.automation import email_crypto
from agent.automation.audit import registrar_evento
from agent.automation.email_audit import metadata_audit_email
from agent.automation.email_crypto import (
    ENVELOPE_PURGADO,
    EmailCryptoError,
    EmailCryptoNoDisponibleError,
)

logger = logging.getLogger("dona")

TIPO_ACCION_EMAIL = "enviar_correo_gmail"
TTL_HORAS = 24

# Estados que mantienen viva la vía de confirmación. PR 1 solo produce
# needs_approval; approved queda contemplado por compatibilidad con el
# índice parcial y la transición transaccional futura (PR 2).
_ESTADOS_CONFIRMABLES = ("needs_approval", "approved")

# ── Token de confirmación (Crockford Base32, 10 chars) ──────────────────────

_ALFABETO_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_LONGITUD_TOKEN = 10
# Normalización Crockford: caracteres visualmente ambiguos mapean a su dígito.
_MAPA_CROCKFORD = str.maketrans({"O": "0", "I": "1", "L": "1"})

# Respuesta ÚNICA para toda referencia inválida: owner incorrecto, token
# inexistente, expirado, consumido o ajeno. Indistinguibles a propósito.
MENSAJE_REFERENCIA_INVALIDA = (
    "No encontré un borrador de correo vigente con ese código. "
    "Puede haber expirado o ya no estar activo. "
    "Si quieres enviar un correo, pídeme preparar uno nuevo."
)


def generar_token() -> str:
    """Token aleatorio de 10 caracteres Crockford Base32 (secrets, no random)."""
    return "".join(secrets.choice(_ALFABETO_CROCKFORD) for _ in range(_LONGITUD_TOKEN))


def formatear_token(token: str) -> str:
    """Presentación visible: dos grupos de 5 ('AB2K7 9XM4T')."""
    return f"{token[:5]} {token[5:]}"


def normalizar_token(referencia: str) -> str | None:
    """Normaliza una referencia de usuario a token canónico.

    Mayúsculas, sin espacios ni guiones, mapa Crockford (O→0, I→1, L→1) y
    validación de longitud EXACTA y alfabeto. Cualquier desvío → None.
    """
    if not referencia or not isinstance(referencia, str):
        return None
    limpio = re.sub(r"[\s\-]+", "", referencia).upper().translate(_MAPA_CROCKFORD)
    if len(limpio) != _LONGITUD_TOKEN:
        return None
    if any(c not in _ALFABETO_CROCKFORD for c in limpio):
        return None
    return limpio


def hash_token(token: str) -> str:
    """SHA-256 hex del token normalizado — lo único que se persiste."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _hash_prep_key(preparation_request_key: str) -> str:
    """Hash de la clave de preparación para audit (nunca la clave cruda)."""
    return hashlib.sha256(preparation_request_key.encode("utf-8")).hexdigest()


# ── Ruta determinística (parseo exacto de ENVIAR/CANCELAR <token>) ──────────

# Acepta prefijo opcional "dona", el verbo exacto y SOLO el token (con
# espacios/guiones internos). Sin substrings ni frases adicionales: cualquier
# otra palabra rompe el fullmatch y el mensaje sigue su flujo normal.
_RE_COMANDO_CONFIRMACION = re.compile(
    r"^\s*(?:dona\s+)?(enviar|cancelar)\s+([0-9A-Za-z][0-9A-Za-z\s\-]{0,30})\s*$",
    re.IGNORECASE,
)


def parsear_comando_confirmacion(texto: str) -> tuple[str, str] | None:
    """Parsea 'ENVIAR <token>' / 'CANCELAR <token>' de forma exacta.

    Devuelve (verbo_en_minúsculas, token_normalizado) o None. NO matchea:
    'no envíes AB2K79XM4T', 'sí, envíalo', 'ENVIAR mañana AB2K79XM4T',
    'creo que ENVIAR AB2K79XM4T'.
    """
    if not texto:
        return None
    m = _RE_COMANDO_CONFIRMACION.fullmatch(texto)
    if not m:
        return None
    token = normalizar_token(m.group(2))
    if token is None:
        return None
    return m.group(1).lower(), token


# ── Helpers internos ────────────────────────────────────────────────────────


def _ahora() -> datetime:
    """UTC naive, consistente con el resto del repo (datetime.utcnow)."""
    return datetime.utcnow()


def _result_json(reason_code: str) -> str:
    return json.dumps({"reason_code": reason_code}, ensure_ascii=False)


def _payload_dict(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    thread_id: str,
    reply_message_id: str,
) -> dict:
    return {
        "destinatario": destinatario,
        "asunto": asunto,
        "cuerpo": cuerpo,
        "thread_id": thread_id,
        "reply_message_id": reply_message_id,
    }


async def _emitir_auditoria(eventos: list[dict]) -> None:
    """Emite eventos acumulados FUERA de la sesión de la mutación (evita
    contención de SQLite y garantiza que el audit refleja estado commiteado)."""
    for ev in eventos:
        try:
            await registrar_evento(**ev)
        except Exception as e:
            logger.error(f"[EMAIL-ACTIONS] Audit falló ({ev.get('evento')}): {e}")


def _evento(
    evento: str,
    telefono: str,
    accion_id: int | None = None,
    **campos,
) -> dict:
    """Arma un registrar_evento del dominio email: la metadata SIEMPRE pasa
    por la whitelist cerrada de metadata_audit_email."""
    return {
        "evento": evento,
        "telefono": telefono,
        "accion_id": accion_id,
        "riesgo": "high",
        "payload": metadata_audit_email(tipo_accion=TIPO_ACCION_EMAIL, **campos),
    }


async def _expirar_vencidas(session, telefono: str, ahora: datetime) -> list[int]:
    """Expira (cancelled + purga + hash borrado) las acciones vencidas del
    owner mediante UPDATE condicional — nunca check-then-act inseguro: el
    WHERE re-verifica owner/tipo/estado/TTL en el mismo statement."""
    from agent.automation.models import AccionAutomatizacion

    res = await session.execute(
        select(AccionAutomatizacion.id).where(
            AccionAutomatizacion.telefono == telefono,
            AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
            AccionAutomatizacion.estado == "needs_approval",
            AccionAutomatizacion.expires_at.is_not(None),
            AccionAutomatizacion.expires_at <= ahora,
        )
    )
    ids = [r[0] for r in res.all()]
    expirados: list[int] = []
    for accion_id in ids:
        upd = await session.execute(
            update(AccionAutomatizacion)
            .where(
                AccionAutomatizacion.id == accion_id,
                AccionAutomatizacion.telefono == telefono,
                AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
                AccionAutomatizacion.estado == "needs_approval",
                AccionAutomatizacion.expires_at.is_not(None),
                AccionAutomatizacion.expires_at <= ahora,
            )
            .values(
                estado="cancelled",
                payload_json=ENVELOPE_PURGADO,
                confirmation_reference_hash="",
                result_json=_result_json("expired"),
                updated_at=ahora,
            )
        )
        if upd.rowcount:
            expirados.append(accion_id)
    return expirados


# ── Preparación persistente e idempotente ───────────────────────────────────


async def preparar_envio_correo(
    telefono: str,
    *,
    destinatario: str,
    asunto: str,
    cuerpo: str,
    thread_id: str = "",
    reply_message_id: str = "",
    preparation_request_key: str,
) -> dict:
    """Prepara (o re-renderiza) la acción persistente de envío de correo.

    Reglas de idempotencia:
      - misma key + mismo fingerprint → misma acción (needs_approval:
        re-render + token nuevo; terminal: respuesta honesta sin recrear);
      - misma key + fingerprint distinto → conflicto cerrado;
      - key nueva → cancela atómicamente la confirmable anterior
        (superseded, payload purgado) y crea la nueva.

    Devuelve dict con `estado` y `mensaje`; en éxito incluye `action_id`,
    `token` (en claro, NUNCA persistido) y `payload` para el preview.
    """
    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session

    if not telefono or not preparation_request_key:
        return {
            "estado": "error",
            "mensaje": "No pude preparar el borrador (solicitud incompleta).",
        }
    prep_key = preparation_request_key[:80]
    payload = _payload_dict(destinatario, asunto, cuerpo, thread_id, reply_message_id)
    fingerprint = email_crypto.calcular_fingerprint(payload)

    try:
        envelope = email_crypto.cifrar_payload_email(payload)
    except EmailCryptoNoDisponibleError:
        logger.error("[EMAIL-ACTIONS] Cifrado no disponible — preparación rechazada")
        return {
            "estado": "cifrado_no_disponible",
            "mensaje": (
                "No puedo guardar borradores de correo de forma segura en este "
                "momento. Intenta de nuevo más tarde."
            ),
        }

    ahora = _ahora()
    eventos: list[dict] = []
    resultado: dict | None = None

    for _intento in (1, 2):
        eventos.clear()
        try:
            async with async_session() as session:
                await _registrar_expiraciones(
                    eventos, telefono,
                    await _expirar_vencidas(session, telefono, ahora),
                )
                res = await session.execute(
                    select(AccionAutomatizacion)
                    .where(
                        AccionAutomatizacion.telefono == telefono,
                        AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
                        AccionAutomatizacion.preparation_request_key == prep_key,
                    )
                    .limit(1)
                )
                existente = res.scalar_one_or_none()
                if existente is not None:
                    resultado = await _resolver_existente(
                        session, eventos, existente, telefono,
                        fingerprint, prep_key, ahora,
                    )
                else:
                    resultado = await _crear_nueva(
                        session, eventos, telefono, envelope, fingerprint,
                        prep_key, payload, ahora,
                    )
                await session.commit()
            break
        except IntegrityError:
            # Concurrencia real: otro request ganó uno de los índices
            # parciales. Reintentar UNA vez re-leyendo; sin filtrar internos.
            logger.warning(
                "[EMAIL-ACTIONS] IntegrityError preparando correo — reintento"
            )
            resultado = None
            continue

    await _emitir_auditoria(eventos)
    if resultado is None:
        return {
            "estado": "conflicto_concurrencia",
            "mensaje": (
                "Hubo dos solicitudes de correo al mismo tiempo. "
                "Ya quedó un solo borrador activo: pídeme verlo o prepara uno nuevo."
            ),
        }
    return resultado


async def _registrar_expiraciones(
    eventos: list[dict], telefono: str, ids_expirados: list[int]
) -> None:
    for accion_id in ids_expirados:
        eventos.append(
            _evento(
                "email_action_expired", telefono, accion_id,
                estado="cancelled", reason_code="expired",
            )
        )


async def _resolver_existente(
    session,
    eventos: list[dict],
    accion,
    telefono: str,
    fingerprint: str,
    prep_key: str,
    ahora: datetime,
) -> dict:
    """Resuelve una preparación cuya key ya existe (idempotencia)."""
    from agent.automation.models import AccionAutomatizacion

    prep_hash = _hash_prep_key(prep_key)

    # Estado terminal (incluye la recién expirada por _expirar_vencidas):
    # respuesta honesta, sin recrear acción ni contenido purgado.
    if accion.estado not in _ESTADOS_CONFIRMABLES:
        mensajes = {
            "cancelled": (
                "Ese borrador ya no está activo (fue cancelado o expiró). "
                "Si quieres enviar el correo, pídeme preparar uno nuevo."
            ),
            "completed": "Esa solicitud de correo ya fue procesada.",
            "failed": (
                "Esa solicitud de correo falló antes. "
                "Pídeme preparar un correo nuevo."
            ),
        }
        return {
            "estado": "terminal",
            "estado_accion": accion.estado,
            "action_id": accion.id,
            "mensaje": mensajes.get(
                accion.estado,
                "Esa solicitud de correo ya no está activa.",
            ),
        }

    # Misma key + fingerprint DIFERENTE → conflicto cerrado. No reemplaza,
    # no crea otra acción.
    if accion.payload_fingerprint != fingerprint:
        eventos.append(
            _evento(
                "email_prep_key_conflict", telefono, accion.id,
                estado=accion.estado,
                reason_code="prep_key_conflict",
                payload_fingerprint=fingerprint,
                preparation_request_hash=prep_hash,
            )
        )
        return {
            "estado": "conflicto",
            "action_id": accion.id,
            "mensaje": (
                "Ya hay un borrador distinto asociado a esta misma solicitud. "
                "Para cambiar el contenido, inicia una nueva solicitud de correo."
            ),
        }

    # Misma key + mismo fingerprint en needs_approval → re-render: token
    # nuevo, hash sustituido, MISMO action_id. Primero verificar que el
    # payload almacenado sigue íntegro.
    try:
        payload_almacenado = email_crypto.descifrar_payload_email(accion.payload_json)
    except EmailCryptoError:
        # Ciphertext corrupto/purgado inconsistente → cancelar y purgar.
        await session.execute(
            update(AccionAutomatizacion)
            .where(
                AccionAutomatizacion.id == accion.id,
                AccionAutomatizacion.telefono == telefono,
                AccionAutomatizacion.estado == accion.estado,
            )
            .values(
                estado="cancelled",
                payload_json=ENVELOPE_PURGADO,
                confirmation_reference_hash="",
                result_json=_result_json("payload_corrupto"),
                updated_at=ahora,
            )
        )
        eventos.append(
            _evento(
                "email_payload_corrupted", telefono, accion.id,
                estado="cancelled", error_code="payload_corrupto",
            )
        )
        return {
            "estado": "corrupta",
            "mensaje": (
                "El borrador guardado no se pudo recuperar y lo cancelé por "
                "seguridad. Pídeme preparar el correo de nuevo."
            ),
        }

    token = generar_token()
    upd = await session.execute(
        update(AccionAutomatizacion)
        .where(
            AccionAutomatizacion.id == accion.id,
            AccionAutomatizacion.telefono == telefono,
            AccionAutomatizacion.estado == "needs_approval",
        )
        .values(confirmation_reference_hash=hash_token(token), updated_at=ahora)
    )
    if not upd.rowcount:
        return {
            "estado": "no_disponible",
            "mensaje": (
                "Ese borrador cambió de estado mientras lo procesaba. "
                "Pídeme verlo de nuevo o prepara un correo nuevo."
            ),
        }
    eventos.append(
        _evento(
            "email_action_rerendered", telefono, accion.id,
            estado="needs_approval",
            payload_fingerprint=fingerprint,
            preparation_request_hash=prep_hash,
            expires_at=accion.expires_at,
        )
    )
    return {
        "estado": "rerender",
        "action_id": accion.id,
        "token": token,
        "payload": payload_almacenado,
        "expires_at": accion.expires_at,
        "mensaje": "Este borrador ya estaba preparado; te lo muestro de nuevo.",
    }


async def _crear_nueva(
    session,
    eventos: list[dict],
    telefono: str,
    envelope: str,
    fingerprint: str,
    prep_key: str,
    payload: dict,
    ahora: datetime,
) -> dict:
    """Crea la nueva acción confirmable, cancelando (superseded) la anterior."""
    from agent.automation.models import AccionAutomatizacion

    # Reemplazo atómico: la confirmable previa (de cualquier key) se cancela
    # y purga en el MISMO statement condicional; el índice parcial único
    # respalda que nunca queden dos confirmables aunque haya carrera.
    res_prev = await session.execute(
        select(AccionAutomatizacion.id).where(
            AccionAutomatizacion.telefono == telefono,
            AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
            AccionAutomatizacion.estado.in_(_ESTADOS_CONFIRMABLES),
        )
    )
    ids_previas = [r[0] for r in res_prev.all()]
    es_reemplazo = False
    for accion_id in ids_previas:
        upd = await session.execute(
            update(AccionAutomatizacion)
            .where(
                AccionAutomatizacion.id == accion_id,
                AccionAutomatizacion.telefono == telefono,
                AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
                AccionAutomatizacion.estado.in_(_ESTADOS_CONFIRMABLES),
            )
            .values(
                estado="cancelled",
                payload_json=ENVELOPE_PURGADO,
                confirmation_reference_hash="",
                result_json=_result_json("superseded"),
                updated_at=ahora,
            )
        )
        if upd.rowcount:
            es_reemplazo = True
            eventos.append(
                _evento(
                    "email_action_superseded", telefono, accion_id,
                    estado="cancelled", reason_code="superseded",
                )
            )

    token = generar_token()
    expires_at = ahora + timedelta(hours=TTL_HORAS)
    nueva = AccionAutomatizacion(
        telefono=telefono,
        tipo_accion=TIPO_ACCION_EMAIL,
        # Título/descripción SIN contenido del correo (van a listados/audit).
        titulo="Enviar correo (pendiente de confirmación)",
        descripcion="",
        razon_recomendacion="",
        estado="needs_approval",
        riesgo="high",
        costo_creditos_estimado=0,
        requires_approval=True,
        payload_json=envelope,
        payload_fingerprint=fingerprint,
        preparation_request_key=prep_key,
        confirmation_reference_hash=hash_token(token),
        expires_at=expires_at,
        created_at=ahora,
        updated_at=ahora,
    )
    session.add(nueva)
    await session.flush()  # IntegrityError de índices parciales emerge aquí
    eventos.append(
        _evento(
            "email_action_prepared", telefono, nueva.id,
            estado="needs_approval",
            payload_fingerprint=fingerprint,
            longitud_cuerpo=len(payload.get("cuerpo", "")),
            tiene_thread=bool(payload.get("thread_id")),
            preparation_request_hash=_hash_prep_key(prep_key),
            created_at=ahora,
            expires_at=expires_at,
            es_reemplazo=es_reemplazo,
        )
    )
    return {
        "estado": "ok",
        "action_id": nueva.id,
        "token": token,
        "payload": payload,
        "expires_at": expires_at,
        "es_reemplazo": es_reemplazo,
        "mensaje": "Borrador guardado, pendiente de confirmación.",
    }


# ── Confirmación (PR 1 · fail-closed) y cancelación ─────────────────────────


async def confirmar_envio_correo(telefono: str, referencia: str) -> dict:
    """Valida ENVIAR <token>: owner, token, tipo, estado, fingerprint y TTL.

    REGLA ABSOLUTA DEL PR 1: una confirmación válida NO cambia el estado,
    NO consume el token, NO crea reserva ni attempt, NO aprueba, NO
    reclama, NO llama executor ni Gmail — bajo CUALQUIER valor de
    EMAIL_SEND_ENABLED. Solo informa que el envío no está habilitado.
    """
    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session

    token = normalizar_token(referencia)
    eventos: list[dict] = []
    ahora = _ahora()

    if token is None or not telefono:
        eventos.append(
            _evento(
                "email_confirmation_rejected", telefono or "",
                reason_code="referencia_invalida",
            )
        )
        await _emitir_auditoria(eventos)
        return {"estado": "invalida", "mensaje": MENSAJE_REFERENCIA_INVALIDA}

    resultado: dict
    async with async_session() as session:
        await _registrar_expiraciones(
            eventos, telefono, await _expirar_vencidas(session, telefono, ahora)
        )
        res = await session.execute(
            select(AccionAutomatizacion)
            .where(
                AccionAutomatizacion.telefono == telefono,
                AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
                AccionAutomatizacion.confirmation_reference_hash == hash_token(token),
                AccionAutomatizacion.estado == "needs_approval",
                AccionAutomatizacion.expires_at.is_not(None),
                AccionAutomatizacion.expires_at > ahora,
            )
            .limit(1)
        )
        accion = res.scalar_one_or_none()

        if accion is None:
            # Respuesta uniforme: inexistente/expirado/ajeno/consumido son
            # indistinguibles para quien pregunta.
            eventos.append(
                _evento(
                    "email_confirmation_rejected", telefono,
                    reason_code="referencia_invalida",
                )
            )
            resultado = {"estado": "invalida", "mensaje": MENSAJE_REFERENCIA_INVALIDA}
        else:
            resultado = await _validar_payload_confirmacion(
                session, eventos, accion, telefono, token, ahora
            )
        await session.commit()

    await _emitir_auditoria(eventos)
    return resultado


async def _validar_payload_confirmacion(
    session, eventos: list[dict], accion, telefono: str, token: str, ahora: datetime
) -> dict:
    """Verifica integridad del payload y devuelve la respuesta fail-closed."""
    from agent.automation.models import AccionAutomatizacion

    try:
        payload = email_crypto.descifrar_payload_email(accion.payload_json)
    except EmailCryptoError:
        payload = None
    if (
        payload is None
        or email_crypto.calcular_fingerprint(payload) != accion.payload_fingerprint
    ):
        await session.execute(
            update(AccionAutomatizacion)
            .where(
                AccionAutomatizacion.id == accion.id,
                AccionAutomatizacion.telefono == telefono,
                AccionAutomatizacion.estado == "needs_approval",
            )
            .values(
                estado="cancelled",
                payload_json=ENVELOPE_PURGADO,
                confirmation_reference_hash="",
                result_json=_result_json("payload_corrupto"),
                updated_at=ahora,
            )
        )
        eventos.append(
            _evento(
                "email_payload_corrupted", telefono, accion.id,
                estado="cancelled", error_code="payload_corrupto",
            )
        )
        return {
            "estado": "corrupta",
            "mensaje": (
                "El borrador guardado no se pudo verificar y lo cancelé por "
                "seguridad. Pídeme preparar el correo de nuevo."
            ),
        }

    # Confirmación VÁLIDA · PR 1: needs_approval se mantiene, el token sigue
    # vigente (no se consume porque nada cambió), cero materialización.
    eventos.append(
        _evento(
            "email_confirmation_hold", telefono, accion.id,
            estado="needs_approval",
            reason_code="envio_no_habilitado",
            payload_fingerprint=accion.payload_fingerprint,
            expires_at=accion.expires_at,
        )
    )
    return {
        "estado": "pendiente_habilitacion",
        "action_id": accion.id,
        "mensaje": (
            "El borrador está guardado, pero el envío todavía no está habilitado.\n"
            f"Cuando se habilite, confirma nuevamente con ENVIAR {formatear_token(token)}."
        ),
    }


async def cancelar_envio_correo(telefono: str, referencia: str) -> dict:
    """CANCELAR <token>: cancela, consume el hash y purga el payload.

    Mismo lookup scoped que la confirmación; referencia inválida produce la
    MISMA respuesta uniforme.
    """
    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session

    token = normalizar_token(referencia)
    eventos: list[dict] = []
    ahora = _ahora()

    if token is None or not telefono:
        return {"estado": "invalida", "mensaje": MENSAJE_REFERENCIA_INVALIDA}

    async with async_session() as session:
        await _registrar_expiraciones(
            eventos, telefono, await _expirar_vencidas(session, telefono, ahora)
        )
        res = await session.execute(
            select(AccionAutomatizacion.id)
            .where(
                AccionAutomatizacion.telefono == telefono,
                AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
                AccionAutomatizacion.confirmation_reference_hash == hash_token(token),
                AccionAutomatizacion.estado == "needs_approval",
                AccionAutomatizacion.expires_at.is_not(None),
                AccionAutomatizacion.expires_at > ahora,
            )
            .limit(1)
        )
        accion_id = res.scalar_one_or_none()
        cancelada = False
        if accion_id is not None:
            # UPDATE condicional: owner + tipo + hash + estado + TTL en el
            # WHERE — re-verifica todo, nunca check-then-act inseguro.
            upd = await session.execute(
                update(AccionAutomatizacion)
                .where(
                    AccionAutomatizacion.id == accion_id,
                    AccionAutomatizacion.telefono == telefono,
                    AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
                    AccionAutomatizacion.confirmation_reference_hash
                    == hash_token(token),
                    AccionAutomatizacion.estado == "needs_approval",
                    AccionAutomatizacion.expires_at.is_not(None),
                    AccionAutomatizacion.expires_at > ahora,
                )
                .values(
                    estado="cancelled",
                    payload_json=ENVELOPE_PURGADO,
                    confirmation_reference_hash="",
                    result_json=_result_json("cancelled_by_user"),
                    updated_at=ahora,
                )
            )
            cancelada = bool(upd.rowcount)
        await session.commit()

    if cancelada:
        eventos.append(
            _evento(
                "email_action_cancelled", telefono, accion_id,
                estado="cancelled", reason_code="cancelled_by_user",
            )
        )
        await _emitir_auditoria(eventos)
        return {
            "estado": "cancelada",
            "mensaje": "Listo, cancelé ese borrador. No se envió nada.",
        }
    await _emitir_auditoria(eventos)
    return {"estado": "invalida", "mensaje": MENSAJE_REFERENCIA_INVALIDA}


# ── Consultas owner-scoped ──────────────────────────────────────────────────


async def tiene_accion_confirmable(telefono: str) -> bool:
    """True si el owner tiene una acción de correo confirmable vigente.
    Consulta focalizada para selección de tools (reemplaza el dict en
    memoria de brain.py). No devuelve contenido."""
    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session

    if not telefono:
        return False
    ahora = _ahora()
    async with async_session() as session:
        res = await session.execute(
            select(AccionAutomatizacion.id)
            .where(
                AccionAutomatizacion.telefono == telefono,
                AccionAutomatizacion.tipo_accion == TIPO_ACCION_EMAIL,
                AccionAutomatizacion.estado.in_(_ESTADOS_CONFIRMABLES),
                AccionAutomatizacion.expires_at.is_not(None),
                AccionAutomatizacion.expires_at > ahora,
            )
            .limit(1)
        )
        return res.scalar_one_or_none() is not None
