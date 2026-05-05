# agent/welcome.py — Bienvenida automática post-checkout Premium/Pro (T2.0.B)

"""
Welcome canónico tras una nueva suscripción (`accion="created"` en
T1.3.C). Reemplaza el welcome genérico que hoy envía el landing webhook
y agrega información clave que el usuario necesita para empezar:

  - Saludo personalizado (nombre del Stripe customer si está).
  - Plan activado (Premium / Pro) y créditos mensuales asignados.
  - URL del dashboard.
  - Password derivado para login (HMAC-SHA256 de customer_id).
  - Invitación a responder "hola" para arrancar el onboarding
    conversacional existente (3 fases en agent/onboarding.py).

Idempotencia: el caller (T1.3.C) verifica el flag
`SuscripcionStripe.bienvenida_enviada` antes de invocar; este módulo
también lo marca al final del send. Doble defensa.

Modos:
  - WELCOME_DRY_RUN=true → loguea pero no llama al proveedor real.
    Usado en tests + dev local sin tokens de WhatsApp configurados.
  - DASHBOARD_PASSWORD_SECRET ausente → no envía y loguea ERROR
    (el password no se puede derivar; el welcome sería incompleto).
  - Whapi falla → catch + log + retorna False; no rompe el webhook.

Nada en este módulo escribe en DB excepto setear el flag
`bienvenida_enviada` al final del send.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime
from typing import Literal

logger = logging.getLogger("dona")


_PASSWORD_PREFIX = "dona-"
_PASSWORD_SUFFIX_LEN = 12
_DEFAULT_DASHBOARD_URL = "https://www.usadona.com/dashboard"


def _derivar_password(customer_id: str) -> str | None:
    """Compute "dona-" + hex(HMAC-SHA256(customer_id, secret))[:12].

    Misma fórmula que `landing/lib/dashboard-auth.ts:deriveDashboardPassword`
    (T1.4.B). Si DASHBOARD_PASSWORD_SECRET no está configurado o
    customer_id está vacío, retorna None.
    """
    secret = os.getenv("DASHBOARD_PASSWORD_SECRET", "").strip()
    if not secret or not customer_id:
        return None
    digest = hmac.new(
        secret.encode("utf-8"), customer_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return _PASSWORD_PREFIX + digest[:_PASSWORD_SUFFIX_LEN]


def _short_id(id_: str) -> str:
    """Trunca un identificador para logs sin filtrar el valor completo.
    Mismo patrón que landing/lib/internal-bridge.ts:shortId (T1.4.D)."""
    if not id_:
        return "***"
    if len(id_) <= 12:
        return "***"
    return f"{id_[:8]}...{id_[-4:]}"


def _short_telefono(telefono: str) -> str:
    """Trunca teléfono: deja últimos 4 + prefijo. Solo para logs server-side
    fuera del JsonFormatter (que ya redacta por su cuenta)."""
    if not telefono:
        return "***"
    if len(telefono) <= 6:
        return "***"
    return f"{telefono[:2]}****{telefono[-4:]}"


def _dashboard_url() -> str:
    """Resuelve la URL del dashboard server-side. Misma cadena de fallbacks
    que la del Customer Portal (T1.5 follow-up)."""
    override = os.getenv("STRIPE_PORTAL_RETURN_URL", "").strip()
    if override and override.startswith(("http://", "https://")):
        return override
    nextauth = os.getenv("NEXTAUTH_URL", "").strip()
    if nextauth and nextauth.startswith(("http://", "https://")):
        return f"{nextauth.rstrip('/')}/dashboard"
    site = os.getenv("NEXT_PUBLIC_SITE_URL", "").strip()
    if site and site.startswith(("http://", "https://")):
        return f"{site.rstrip('/')}/dashboard"
    return _DEFAULT_DASHBOARD_URL


def _nombre_plan(plan_codigo: str) -> str:
    """Traduce 'premium' / 'pro' a etiqueta UI. Otros se devuelven crudos."""
    if plan_codigo == "premium":
        return "Premium"
    if plan_codigo == "pro":
        return "Pro"
    return plan_codigo or "—"


def _saludo(nombre_customer: str | None) -> str:
    """Devuelve 'Hola {nombre}' si hay nombre, 'Hola!' si no."""
    if not nombre_customer:
        return "Hola!"
    nombre = nombre_customer.strip().split()[0] if nombre_customer.strip() else ""
    if not nombre:
        return "Hola!"
    return f"Hola {nombre}!"


def _componer_mensaje(
    *,
    nombre: str | None,
    plan_codigo: str,
    creditos_mensuales: int,
    password: str,
    dashboard_url: str,
) -> str:
    """Mensaje WhatsApp único, ~400 chars, con todo lo necesario para
    el primer login + arranque del onboarding."""
    plan_label = _nombre_plan(plan_codigo)
    return (
        f"{_saludo(nombre)} Soy *Dona*, tu asistente.\n"
        f"\n"
        f"Tu plan *{plan_label}* está activo "
        f"(*{creditos_mensuales} créditos* este mes).\n"
        f"\n"
        f"📊 *Dashboard*: {dashboard_url}\n"
        f"🔑 *Contraseña*: {password}\n"
        f"\n"
        f"Para empezar, respóndeme *hola* aquí en WhatsApp y "
        f"te hago algunas preguntas para conocerte y serte útil. "
        f"También puedo ayudarte sin esperar — solo escribime."
    )


# ── API pública del módulo ────────────────────────────────────────────────


WelcomeResultado = Literal[
    "enviado",
    "dry_run",
    "ya_enviado",
    "secret_faltante",
    "telefono_faltante",
    "envio_fallo",
]


async def enviar_bienvenida_premium(
    *,
    subscription_id: str,
    customer_id: str,
    telefono: str,
    plan_codigo: str,
    creditos_mensuales: int,
    nombre_customer: str | None = None,
) -> WelcomeResultado:
    """
    Envía el WhatsApp de bienvenida y marca el flag `bienvenida_enviada`.

    Args (todos vienen del SuscripcionStripe recién creado):
      subscription_id: PK de la sub. Usado para idempotencia.
      customer_id: cus_xxx. Usado para derivar el password.
      telefono: E.164 sin `+` (formato del backend).
      plan_codigo: "premium" | "pro".
      creditos_mensuales: del plan según creditos_de_plan().
      nombre_customer: opcional, para personalizar el saludo.

    Returns:
      "enviado" | "dry_run" | "ya_enviado" | "secret_faltante"
      | "telefono_faltante" | "envio_fallo"

    El flag `bienvenida_enviada` se marca a True solo si el resultado
    es "enviado" o "dry_run" (el dry_run cuenta para que en dev/test
    el flag avance y permita testar la idempotencia).
    """
    from agent.memory import async_session, SuscripcionStripe
    from sqlalchemy import select

    # Idempotencia: relectura desde DB. El caller también verificó
    # antes de invocar, pero defensa en profundidad.
    async with async_session() as session:
        sub = (await session.execute(
            select(SuscripcionStripe).where(
                SuscripcionStripe.subscription_id == subscription_id
            )
        )).scalar_one_or_none()
        if sub is not None and sub.bienvenida_enviada:
            logger.info(
                f"[WELCOME] sub={_short_id(subscription_id)} "
                f"ya_enviado · skip"
            )
            return "ya_enviado"

    if not telefono:
        logger.warning(
            f"[WELCOME] sub={_short_id(subscription_id)} sin telefono · "
            f"no se envía welcome"
        )
        return "telefono_faltante"

    password = _derivar_password(customer_id)
    if not password:
        logger.error(
            f"[WELCOME] sub={_short_id(subscription_id)} "
            f"DASHBOARD_PASSWORD_SECRET no configurada o customer_id vacío "
            f"· no se envía welcome (el password sería incompleto)"
        )
        return "secret_faltante"

    mensaje = _componer_mensaje(
        nombre=nombre_customer,
        plan_codigo=plan_codigo,
        creditos_mensuales=creditos_mensuales,
        password=password,
        dashboard_url=_dashboard_url(),
    )

    dry_run = os.getenv("WELCOME_DRY_RUN", "").lower() in ("true", "1", "yes")
    if dry_run:
        # Loguear que se hubiese enviado (sin password — el JsonFormatter
        # lo redacta, pero por defensa también truncamos manualmente acá).
        logger.info(
            f"[WELCOME] DRY_RUN sub={_short_id(subscription_id)} "
            f"tel={_short_telefono(telefono)} plan={plan_codigo} "
            f"creditos={creditos_mensuales} mensaje_len={len(mensaje)}"
        )
        await _marcar_enviado(subscription_id)
        return "dry_run"

    # Envío real vía proveedor (Whapi en prod).
    try:
        from agent.providers import obtener_proveedor
        proveedor = obtener_proveedor()
        ok = await proveedor.enviar_mensaje(telefono, mensaje)
    except Exception as e:
        # No fallar el webhook por un error en el proveedor. El owner
        # puede regenerar manualmente con el CLI helper de T1.4.B.
        logger.exception(
            f"[WELCOME] sub={_short_id(subscription_id)} "
            f"excepción enviando: {type(e).__name__}"
        )
        return "envio_fallo"

    if not ok:
        logger.warning(
            f"[WELCOME] sub={_short_id(subscription_id)} "
            f"proveedor.enviar_mensaje retornó False · "
            f"el flag NO se marca · owner puede reintentar manualmente"
        )
        return "envio_fallo"

    await _marcar_enviado(subscription_id)
    logger.info(
        f"[WELCOME] sub={_short_id(subscription_id)} "
        f"enviado tel={_short_telefono(telefono)} plan={plan_codigo}"
    )
    return "enviado"


async def _marcar_enviado(subscription_id: str) -> None:
    """Marca SuscripcionStripe.bienvenida_enviada = True.

    Solo se llama tras éxito real ("enviado") o en DRY_RUN.
    Si la fila no existe (raro), no hace nada.
    """
    from agent.memory import async_session, SuscripcionStripe
    from sqlalchemy import select

    async with async_session() as session:
        sub = (await session.execute(
            select(SuscripcionStripe).where(
                SuscripcionStripe.subscription_id == subscription_id
            )
        )).scalar_one_or_none()
        if sub is None:
            return
        sub.bienvenida_enviada = True
        sub.actualizado = datetime.utcnow()
        await session.commit()
