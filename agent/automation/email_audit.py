# agent/automation/email_audit.py — Audit whitelist del flujo email (PR 1)

"""
Constructor cerrado de metadata para eventos de audit del dominio email
persistente. Es el CONTROL PRINCIPAL de privacidad del flujo: la firma
keyword-only enumera exhaustivamente los campos permitidos, así que un
campo nuevo (o un typo que intente colar destinatario/asunto/cuerpo)
produce TypeError en el punto de emisión, no una fila contaminada.

`sanitizar_payload` de agent/automation/audit.py sigue corriendo después
como defensa adicional — no como control principal.

Regla dura: este módulo NUNCA recibe payload descifrado, destinatario,
asunto, cuerpo, preview ni tokens en claro. Solo hashes, conteos,
estados y códigos cerrados.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# Sentinel: distingue "no provisto" de valores falsy legítimos (0, False, "").
_NO_PROVISTO = object()


def metadata_audit_email(
    *,
    action_id: int | None | object = _NO_PROVISTO,
    tipo_accion: str | object = _NO_PROVISTO,
    estado: str | object = _NO_PROVISTO,
    reason_code: str | object = _NO_PROVISTO,
    error_code: str | object = _NO_PROVISTO,
    payload_fingerprint: str | object = _NO_PROVISTO,
    longitud_cuerpo: int | object = _NO_PROVISTO,
    tiene_thread: bool | object = _NO_PROVISTO,
    preparation_request_hash: str | object = _NO_PROVISTO,
    created_at: datetime | str | object = _NO_PROVISTO,
    expires_at: datetime | str | object = _NO_PROVISTO,
    es_reemplazo: bool | object = _NO_PROVISTO,
) -> dict[str, Any]:
    """Construye la metadata de un evento email con campos cerrados.

    No todos los eventos incluyen todos los campos: solo se emiten los
    provistos. Un kwarg fuera de la firma → TypeError (whitelist dura).
    Los datetimes se serializan a ISO para que el payload sea estable.
    """
    valores = {
        "action_id": action_id,
        "tipo_accion": tipo_accion,
        "estado": estado,
        "reason_code": reason_code,
        "error_code": error_code,
        "payload_fingerprint": payload_fingerprint,
        "longitud_cuerpo": longitud_cuerpo,
        "tiene_thread": tiene_thread,
        "preparation_request_hash": preparation_request_hash,
        "created_at": created_at,
        "expires_at": expires_at,
        "es_reemplazo": es_reemplazo,
    }
    metadata: dict[str, Any] = {}
    for clave, valor in valores.items():
        if valor is _NO_PROVISTO:
            continue
        if isinstance(valor, datetime):
            valor = valor.isoformat()
        metadata[clave] = valor
    return metadata
