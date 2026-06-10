# agent/dashboard_lockout.py — Lockout persistente de login del dashboard (rank 4)

"""
Lockout anti fuerza-bruta para el login del dashboard.

El password del dashboard es derivado (``dona-`` + 12 hex = 48 bits) y el login
corre en la landing (Vercel serverless), que no mantiene estado entre instancias
ni cold starts. Por eso el contador de intentos fallidos y el bloqueo viven aquí,
en Postgres, y la landing los consulta vía el bridge HMAC interno
(``/internal/auth/login-check`` y ``/internal/auth/login-record``).

Política:
  - Se cuenta por email (hasheado · sin PII en DB).
  - Tras ``MAX_INTENTOS`` fallos → bloqueo de ``COOLDOWN_SEGUNDOS``.
  - El éxito resetea el contador (borra la fila).
  - La landing solo registra intentos con password de formato válido; los
    malformados se rechazan allá y no llegan acá.

Con lockout, 48 bits es seguro contra brute-force online: un atacante obtiene
~``MAX_INTENTOS`` intentos por ventana de cooldown.

Privacidad: NUNCA se guarda el email en claro. La clave de fila es
``HMAC-SHA256(INTERNAL_BRIDGE_SECRET, email_normalizado)`` — opaca y no
enumerable sin el secret. Coherente con cómo el repo trata PII.
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from agent.memory import Base, async_session

# ── Política de lockout ──────────────────────────────────────────────────────
MAX_INTENTOS = 10              # fallos antes de bloquear
COOLDOWN_SEGUNDOS = 15 * 60    # 15 minutos de bloqueo


class DashboardLoginIntento(Base):
    """Contador de intentos fallidos + bloqueo por identificador (email hash).

    Una fila por email. Aditiva · no toca tablas existentes. La crea
    ``create_all`` en ``inicializar_db`` (registrada vía import lazy allí).
    """

    __tablename__ = "dashboard_login_intentos"

    # HMAC-SHA256 hex del email normalizado (64 chars). Sin PII.
    email_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def _hash_email(email: str) -> str:
    """Clave opaca y estable para un email.

    Hash con ``INTERNAL_BRIDGE_SECRET`` para que no sea reversible ni enumerable
    sin el secret. Email normalizado (trim + lower) para que el casing no genere
    filas distintas.

    Fail-closed por defecto (ver agent/entorno.py): en entorno estricto un
    secret ausente aborta en vez de producir hashes computables por cualquiera
    (enumeración de PII). Solo dev/test explícitos degradan a un literal local.
    """
    from agent.entorno import es_entorno_estricto

    raw = os.getenv("INTERNAL_BRIDGE_SECRET", "").strip()
    if not raw:
        if es_entorno_estricto():
            raise RuntimeError(
                "[LOCKOUT] INTERNAL_BRIDGE_SECRET no configurado en entorno "
                "estricto — el hash de email sería computable por cualquiera "
                "(enumeración de PII). Configura la variable."
            )
        raw = "dona-lockout-dev-secret-do-not-use-in-prod"
    norm = (email or "").strip().lower().encode("utf-8")
    return hmac.new(raw.encode("utf-8"), norm, hashlib.sha256).hexdigest()


async def verificar_lockout(email: str) -> dict:
    """¿Está bloqueado este email? No muta estado.

    Devuelve ``{"bloqueado": bool, "retry_after_segundos": int}``.
    """
    eh = _hash_email(email)
    async with async_session() as session:
        row = await session.get(DashboardLoginIntento, eh)
        if not row or not row.bloqueado_hasta:
            return {"bloqueado": False, "retry_after_segundos": 0}
        ahora = datetime.utcnow()
        if row.bloqueado_hasta > ahora:
            restante = int((row.bloqueado_hasta - ahora).total_seconds())
            return {"bloqueado": True, "retry_after_segundos": max(restante, 1)}
        return {"bloqueado": False, "retry_after_segundos": 0}


async def registrar_resultado(email: str, exito: bool) -> dict:
    """Registra el resultado de un intento de login.

    - ``exito=True``  → resetea (borra la fila).
    - ``exito=False`` → incrementa; si alcanza ``MAX_INTENTOS``, bloquea.

    Devuelve ``{"bloqueado": bool, "intentos": int, "retry_after_segundos": int}``.
    """
    eh = _hash_email(email)
    ahora = datetime.utcnow()
    async with async_session() as session:
        row = await session.get(DashboardLoginIntento, eh)

        if exito:
            if row is not None:
                await session.delete(row)
                await session.commit()
            return {"bloqueado": False, "intentos": 0, "retry_after_segundos": 0}

        if row is None:
            row = DashboardLoginIntento(email_hash=eh, intentos_fallidos=0)
            session.add(row)

        # Ya bloqueado y vigente: no incrementar (idempotente ante reentregas).
        if row.bloqueado_hasta and row.bloqueado_hasta > ahora:
            restante = int((row.bloqueado_hasta - ahora).total_seconds())
            return {
                "bloqueado": True,
                "intentos": row.intentos_fallidos,
                "retry_after_segundos": max(restante, 1),
            }

        row.intentos_fallidos = (row.intentos_fallidos or 0) + 1
        row.actualizado_en = ahora

        bloqueado = False
        retry = 0
        if row.intentos_fallidos >= MAX_INTENTOS:
            row.bloqueado_hasta = ahora + timedelta(seconds=COOLDOWN_SEGUNDOS)
            row.intentos_fallidos = 0  # el bloqueo es la barrera; reset del contador
            bloqueado = True
            retry = COOLDOWN_SEGUNDOS

        await session.commit()
        return {
            "bloqueado": bloqueado,
            "intentos": row.intentos_fallidos,
            "retry_after_segundos": retry,
        }
