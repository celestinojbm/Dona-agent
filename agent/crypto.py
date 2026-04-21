# agent/crypto.py — Cifrado de datos sensibles (tokens OAuth, etc.)

"""
Cifra/descifra strings usando Fernet (AES-128-CBC con HMAC-SHA256).

Requiere la variable de entorno ENCRYPTION_KEY con una clave Fernet válida.
Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Si ENCRYPTION_KEY no está configurada, opera en modo transparente (sin cifrado)
para no romper deploys existentes. Loguea un warning en cada arranque.
"""

import os
import logging

logger = logging.getLogger("dona")

_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
_fernet = None

if _ENCRYPTION_KEY:
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_ENCRYPTION_KEY.encode())
        logger.info("[CRYPTO] Cifrado de tokens activado")
    except Exception as e:
        if _ENVIRONMENT == "production":
            raise RuntimeError(
                f"[CRYPTO] ENCRYPTION_KEY inválida en producción: {e}. "
                "Deploy abortado — genera una clave válida con "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        logger.error(f"[CRYPTO] ENCRYPTION_KEY inválida: {e}. Tokens NO se cifrarán.")
else:
    if _ENVIRONMENT == "production":
        raise RuntimeError(
            "[CRYPTO] ENCRYPTION_KEY no configurada en producción — "
            "almacenar tokens OAuth en texto plano es inaceptable. "
            "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "y configúrala como variable de entorno antes de reintentar el deploy."
        )
    logger.warning(
        "[CRYPTO] ENCRYPTION_KEY no configurada — tokens se almacenan en texto plano. "
        "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )


def cifrar(valor: str) -> str:
    """Cifra un string. Si no hay clave configurada, retorna el valor original."""
    if not _fernet or not valor:
        return valor
    try:
        return _fernet.encrypt(valor.encode()).decode()
    except Exception as e:
        logger.error(f"[CRYPTO] Error cifrando: {e}")
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
