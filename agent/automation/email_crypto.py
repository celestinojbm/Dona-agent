# agent/automation/email_crypto.py — Cifrado estricto del payload de correo (PR 1)

"""
Cifrado fail-closed para el payload de la acción persistente
`enviar_correo_gmail` (destinatario, asunto, cuerpo, thread_id,
reply_message_id).

NO reutiliza `agent.crypto.descifrar()` a propósito: esa función es
fail-open (un ciphertext inválido se devuelve como si fuera plaintext
legacy), aceptable para tokens OAuth en migración pero inaceptable para
contenido de correo que gobierna una acción externa futura. Aquí todo
error de descifrado es un error tipado — nunca se reinterpreta
ciphertext inválido como plaintext.

Envelope persistido (JSON en payload_json):
    {"v": 1, "alg": "fernet", "ct": "...", "fingerprint": "...",
     "longitud_cuerpo": 0, "tiene_thread": false}

Modo plaintext ({"alg": "plaintext"}) SOLO cuando
EMAIL_CRYPTO_PERMITIR_PLAINTEXT == "true" Y el entorno no es estricto
(fixture de tests sin cryptography). Nunca en producción.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os

from agent.entorno import es_entorno_estricto

logger = logging.getLogger("dona")

# Campos que viajan cifrados CONJUNTAMENTE. El orden no importa: el JSON
# canónico se serializa con sort_keys.
CAMPOS_PAYLOAD = ("destinatario", "asunto", "cuerpo", "thread_id", "reply_message_id")

# Marca de payload purgado (cancelación/expiración/reemplazo). Reemplaza el
# envelope completo — el ciphertext original deja de existir.
ENVELOPE_PURGADO = '{"purged": true}'


class EmailCryptoError(Exception):
    """Base de errores del cifrado de correo."""


class EmailCryptoNoDisponibleError(EmailCryptoError):
    """No hay ENCRYPTION_KEY válida y el modo plaintext no está autorizado."""


class EmailEnvelopeInvalidoError(EmailCryptoError):
    """El envelope persistido no tiene la forma/versión/algoritmo esperados."""


class EmailPayloadIndescifrableError(EmailCryptoError):
    """El ciphertext no se pudo descifrar o no corresponde al fingerprint."""


class EmailPayloadPurgadoError(EmailCryptoError):
    """El payload fue purgado (cancelación/expiración/reemplazo)."""


def _payload_canonico(payload: dict) -> str:
    """JSON canónico y determinístico del payload (base del fingerprint)."""
    datos = {campo: str(payload.get(campo, "") or "") for campo in CAMPOS_PAYLOAD}
    return json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def calcular_fingerprint(payload: dict) -> str:
    """SHA-256 hex del payload canónico. Determinístico por contenido."""
    return hashlib.sha256(_payload_canonico(payload).encode("utf-8")).hexdigest()


def _obtener_fernet():
    """Fernet desde ENCRYPTION_KEY, leída en cada llamada (patrón test-friendly
    del repo: los tests setean env vars y recargan módulos). Clave ausente o
    inválida → None; el llamador decide fail-closed."""
    key = os.getenv("ENCRYPTION_KEY", "")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
    except Exception as e:
        logger.error(f"[EMAIL-CRYPTO] ENCRYPTION_KEY inválida: {type(e).__name__}")
        return None


def _plaintext_permitido() -> bool:
    """Plaintext SOLO con flag explícita Y entorno no estricto. La flag no
    vive en ningún .env: es exclusiva de fixtures de test."""
    return (
        os.getenv("EMAIL_CRYPTO_PERMITIR_PLAINTEXT", "") == "true"
        and not es_entorno_estricto()
    )


def crypto_email_disponible() -> bool:
    """True si hay clave Fernet válida para cifrar payloads de correo."""
    return _obtener_fernet() is not None


def es_envelope_purgado(envelope_json: str) -> bool:
    """True si el valor persistido es la marca de payload purgado."""
    try:
        datos = json.loads(envelope_json or "")
    except (ValueError, TypeError):
        return False
    return isinstance(datos, dict) and datos.get("purged") is True


def cifrar_payload_email(payload: dict) -> str:
    """Cifra el payload completo y devuelve el envelope JSON a persistir.

    Fail-closed: sin clave válida y sin autorización de plaintext, levanta
    EmailCryptoNoDisponibleError — la acción NO se crea con contenido en claro.
    """
    canonico = _payload_canonico(payload)
    fingerprint = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
    metadatos = {
        "v": 1,
        "fingerprint": fingerprint,
        "longitud_cuerpo": len(str(payload.get("cuerpo", "") or "")),
        "tiene_thread": bool(payload.get("thread_id")),
    }

    fernet = _obtener_fernet()
    if fernet is not None:
        try:
            ct = fernet.encrypt(canonico.encode("utf-8")).decode("ascii")
        except Exception as e:
            raise EmailCryptoError(
                f"Error cifrando payload de correo: {type(e).__name__}"
            ) from e
        return json.dumps({**metadatos, "alg": "fernet", "ct": ct}, ensure_ascii=False)

    if _plaintext_permitido():
        datos = {campo: str(payload.get(campo, "") or "") for campo in CAMPOS_PAYLOAD}
        return json.dumps(
            {**metadatos, "alg": "plaintext", "payload": datos}, ensure_ascii=False
        )

    raise EmailCryptoNoDisponibleError(
        "ENCRYPTION_KEY no disponible y plaintext no autorizado — "
        "no se persiste contenido de correo en claro."
    )


def descifrar_payload_email(envelope_json: str) -> dict:
    """Descifra un envelope persistido y devuelve el payload como dict.

    Errores tipados, nunca fail-open:
      - EmailPayloadPurgadoError    · envelope es la marca de purga
      - EmailEnvelopeInvalidoError  · forma/versión/algoritmo desconocidos, o
                                      envelope plano sin autorización
      - EmailCryptoNoDisponibleError· ciphertext Fernet sin clave para leerlo
      - EmailPayloadIndescifrableError · ciphertext corrupto o fingerprint
                                      que no corresponde al contenido
    """
    try:
        envelope = json.loads(envelope_json or "")
    except (ValueError, TypeError) as e:
        raise EmailEnvelopeInvalidoError("Envelope no es JSON válido") from e
    if not isinstance(envelope, dict):
        raise EmailEnvelopeInvalidoError("Envelope no es un objeto JSON")

    if envelope.get("purged") is True:
        raise EmailPayloadPurgadoError("El payload fue purgado")

    if envelope.get("v") != 1:
        raise EmailEnvelopeInvalidoError(
            f"Versión de envelope desconocida: {envelope.get('v')!r}"
        )

    alg = envelope.get("alg")
    if alg == "fernet":
        fernet = _obtener_fernet()
        if fernet is None:
            raise EmailCryptoNoDisponibleError(
                "Ciphertext Fernet persistido pero no hay ENCRYPTION_KEY válida"
            )
        ct = envelope.get("ct", "")
        try:
            canonico = fernet.decrypt(str(ct).encode("ascii")).decode("utf-8")
        except Exception as e:
            # NUNCA degradar a plaintext: ciphertext inválido es error tipado.
            raise EmailPayloadIndescifrableError(
                "Ciphertext de correo indescifrable"
            ) from e
        try:
            datos = json.loads(canonico)
        except ValueError as e:
            raise EmailPayloadIndescifrableError(
                "Plaintext descifrado no es JSON válido"
            ) from e
        if not isinstance(datos, dict):
            raise EmailPayloadIndescifrableError("Plaintext descifrado no es un objeto")
        payload = {campo: str(datos.get(campo, "") or "") for campo in CAMPOS_PAYLOAD}
    elif alg == "plaintext":
        # Un envelope plano solo es legible bajo la misma autorización
        # explícita con la que se pudo escribir.
        if not _plaintext_permitido():
            raise EmailEnvelopeInvalidoError(
                "Envelope plaintext sin autorización en este entorno"
            )
        datos = envelope.get("payload")
        if not isinstance(datos, dict):
            raise EmailEnvelopeInvalidoError("Envelope plaintext sin payload")
        payload = {campo: str(datos.get(campo, "") or "") for campo in CAMPOS_PAYLOAD}
    else:
        raise EmailEnvelopeInvalidoError(f"Algoritmo desconocido: {alg!r}")

    # El fingerprint del envelope debe corresponder al contenido descifrado —
    # detecta corrupción lógica aunque el ciphertext autentique.
    if calcular_fingerprint(payload) != envelope.get("fingerprint"):
        raise EmailPayloadIndescifrableError(
            "Fingerprint del envelope no corresponde al contenido"
        )
    return payload
