# agent/crypto.py — Cifrado de datos sensibles (tokens OAuth, etc.)

"""
Cifra/descifra strings usando Fernet (AES-128-CBC con HMAC-SHA256).

Requiere la variable de entorno ENCRYPTION_KEY con una clave Fernet válida.
Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Si ENCRYPTION_KEY no está configurada, opera en modo transparente (sin cifrado)
para no romper deploys existentes. Loguea un warning en cada arranque.
"""

import logging
import os

from agent.entorno import es_entorno_estricto

logger = logging.getLogger("dona")


def _inicializar_fernet():
    """Construye el Fernet desde ENCRYPTION_KEY. Fail-closed por defecto:
    en entorno estricto (producción o ENVIRONMENT desconocido/ausente — ver
    agent/entorno.py) una clave ausente o inválida aborta el arranque. Solo
    dev/test explícitos degradan a modo texto plano (con warning)."""
    key = os.getenv("ENCRYPTION_KEY", "")
    if key:
        try:
            from cryptography.fernet import Fernet
            fernet = Fernet(key.encode())
            logger.info("[CRYPTO] Cifrado de tokens activado")
            return fernet
        except Exception as e:
            if es_entorno_estricto():
                raise RuntimeError(
                    f"[CRYPTO] ENCRYPTION_KEY inválida en entorno estricto: {e}. "
                    "Deploy abortado — genera una clave válida con "
                    "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            logger.error(f"[CRYPTO] ENCRYPTION_KEY inválida: {e}. Tokens NO se cifrarán.")
            return None
    if es_entorno_estricto():
        raise RuntimeError(
            "[CRYPTO] ENCRYPTION_KEY no configurada en entorno estricto "
            "(producción o ENVIRONMENT desconocido/ausente) — almacenar tokens "
            "OAuth en texto plano es inaceptable. "
            "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "y configúrala antes de reintentar el deploy."
        )
    logger.warning(
        "[CRYPTO] ENCRYPTION_KEY no configurada — tokens se almacenan en texto plano. "
        "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )
    return None


_fernet = _inicializar_fernet()


def cifrar(valor: str) -> str:
    """Cifra un string. Si no hay clave configurada, retorna el valor original.

    Fail-closed (0.4): si el cifrado ESTÁ activo pero `encrypt` falla, NO degrada
    a texto plano. En entorno estricto relanza para no persistir un secreto sin
    cifrar (un token OAuth en claro es inaceptable); en dev/test loguea y
    devuelve el original. `descifrar` sí queda fail-open a propósito (compat con
    valores legacy/migración en texto plano)."""
    if not _fernet or not valor:
        return valor
    try:
        return _fernet.encrypt(valor.encode()).decode()
    except Exception as e:
        logger.error(f"[CRYPTO] Error cifrando: {e}")
        if es_entorno_estricto():
            raise RuntimeError(
                f"[CRYPTO] Error cifrando un valor sensible en entorno estricto: "
                f"{e}. Se aborta para no almacenarlo en texto plano."
            ) from e
        return valor


def descifrar(valor: str) -> str:
    """Descifra un string. Si no hay clave o el valor no está cifrado, retorna original."""
    if not _fernet or not valor:
        return valor
    try:
        return _fernet.decrypt(valor.encode()).decode()
    except Exception:
        # El valor probablemente no está cifrado (migración pendiente o texto plano legacy)
        return valor


def esta_activo() -> bool:
    """Retorna True si el cifrado está configurado y activo."""
    return _fernet is not None
