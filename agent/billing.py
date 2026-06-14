# agent/billing.py — Sistema de créditos prepagos + Stripe Checkout

"""
Billing de Dona. Modelo simple: **créditos prepagos**.

El usuario compra paquetes por Stripe Checkout; cada tool creativa declara
su `costo_creditos`; `cobrar_o_rechazar` es el gate que cualquier tool debe
pasar antes de ejecutar trabajo caro.

Diseño:
  - Saldo es un entero (créditos). No usamos decimales para evitar drift.
  - Todas las operaciones de balance son atómicas dentro de una transacción DB.
  - Cada cobro/acreditación deja fila en `transacciones_credito` (audit trail).
  - Stripe webhook es **idempotente** via `stripe_session_id` — reentregar
    un evento no duplica créditos.

Paquetes definidos por env (ver `PAQUETES` abajo). Los `price_id` deben
coincidir con los price objects en el dashboard de Stripe.
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("dona")


# ── Fail-fast: STRIPE_WEBHOOK_SECRET obligatorio en producción ───────────────
# El endpoint /webhook/stripe está públicamente expuesto. Sin secret de
# verificación, un atacante puede forjar payloads de checkout.session.completed
# y acreditar créditos arbitrarios. En entorno estricto (producción o
# desconocido — ver agent/entorno.py) exigimos la variable al import del
# módulo: si falta, el deploy aborta antes de empezar a servir. Solo dev/test
# explícitos mantienen el path permisivo (con warning) para pruebas locales
# sin configurar Stripe. Fail-closed por defecto (C8 del audit 2026-06-09).
from agent.entorno import es_entorno_estricto


def _check_stripe_webhook_secret() -> None:
    """Aborta el arranque si el entorno es estricto y falta STRIPE_WEBHOOK_SECRET."""
    if es_entorno_estricto() and not os.getenv("STRIPE_WEBHOOK_SECRET", "").strip():
        raise RuntimeError(
            "[BILLING] STRIPE_WEBHOOK_SECRET no configurada en entorno estricto "
            "(producción o ENVIRONMENT desconocido/ausente) — los webhooks de "
            "Stripe podrían aceptar payloads forjados, lo que permitiría a un "
            "atacante acreditar créditos arbitrarios. Configura la variable "
            "(o ENVIRONMENT=development/test explícito) antes de reintentar."
        )


_check_stripe_webhook_secret()


# ── Configuración de paquetes ───────────────────────────────────────────────
# Los paquetes pueden ajustarse por env sin redeploy. Si un price_id no está
# configurado el paquete queda deshabilitado (no aparece en "dona recargar").

@dataclass(frozen=True)
class Paquete:
    codigo: str          # identificador interno (100, 500, 2000)
    creditos: int
    precio_usd: float    # sólo para mostrar al usuario; Stripe mantiene el precio real
    stripe_price_id: str


def _paquetes_desde_env() -> list[Paquete]:
    """Lee los 3 paquetes estándar desde env. Placeholder si faltan."""
    packs = [
        Paquete("100",  100,  10.0, os.getenv("STRIPE_PRICE_PAQUETE_100",  "")),
        Paquete("500",  500,  40.0, os.getenv("STRIPE_PRICE_PAQUETE_500",  "")),
        Paquete("2000", 2000, 120.0, os.getenv("STRIPE_PRICE_PAQUETE_2000", "")),
    ]
    return packs


def paquetes_disponibles() -> list[Paquete]:
    """Paquetes con `stripe_price_id` configurado (los que realmente se pueden comprar)."""
    return [p for p in _paquetes_desde_env() if p.stripe_price_id]


def paquete_por_codigo(codigo: str) -> Paquete | None:
    for p in _paquetes_desde_env():
        if p.codigo == codigo:
            return p
    return None


# ── Costos por tool (declarativo) ───────────────────────────────────────────
# Fuente de verdad de cuánto cuesta cada operación creativa. Tools reales
# en sprints 2-5 importan estas constantes.

COSTO_IMAGEN_STANDARD = 2      # nanobanana / Gemini Flash Image
COSTO_IMAGEN_PREMIUM = 4       # Ideogram v2 / Flux Pro Ultra / Recraft
COSTO_BG_REMOVE = 1            # Photoroom / remove.bg
COSTO_VOZ_CORTA = 3            # ElevenLabs < 500 chars
COSTO_VOZ_LARGA = 10           # ElevenLabs > 500 chars
COSTO_MUSICA = 15              # Suno / Udio
COSTO_VIDEO_5S = 80            # Seedance-1-pro 5s (~$0.15/video proveedor)
COSTO_VIDEO_CORTO = 150        # Seedance-1-pro 10s (~$0.30/video proveedor)
COSTO_VIDEO_LARGO = 250        # Veo 3 8s con audio
COSTO_VIDEO_AVATAR = 80        # HeyGen 1 min
COSTO_WEB_DEPLOY = 100         # Generación Next.js + deploy Vercel
COSTO_CAMPAÑA_ADS = 30         # Creación Meta/Google Ads campaign
COSTO_DOCUMENTO = 3            # Factura / presupuesto / recibo en PDF (LLM + reportlab)


# ── Mapping plan Stripe → créditos mensuales (T1.3.B) ──────────────────────
# El landing crea Stripe Checkout Sessions con `metadata.plan` valores
# "premium" ($20/mes) o "pro" ($40/mes). Cuando llegue el webhook al backend
# (T1.3.C-E), `creditos_de_plan(metadata.plan)` resuelve cuántos créditos
# acreditar al usuario en cada periodo.
#
# Política de configuración (decisión owner):
#   - En producción exigimos las env vars STRIPE_CREDITOS_PREMIUM y
#     STRIPE_CREDITOS_PRO setadas en Render. Si faltan, retornamos None y
#     loguemos ERROR (no acreditar > acreditar mal).
#   - En dev/test aceptamos defaults conservadores (premium=100, pro=500)
#     con warning, para permitir tests locales sin configurar Stripe.
#
# Defaults para dev/test — tentativos, NO se usan en producción.
_CREDITOS_DEFAULT_DEV = {
    "premium": 100,
    "pro": 500,
}

# Mapping plan_codigo → nombre de la env var.
_ENV_VAR_POR_PLAN = {
    "premium": "STRIPE_CREDITOS_PREMIUM",
    "pro": "STRIPE_CREDITOS_PRO",
}


def creditos_de_plan(plan_codigo: str) -> int | None:
    """
    Mapea un ``plan_codigo`` Stripe ("premium" | "pro") a créditos mensuales.

    Comportamiento:
      - Plan conocido + env var seteada → ``int(env_var)``.
      - Plan conocido + env var faltante en **producción** → loguea ERROR y
        retorna ``None`` (no acreditar nada > acreditar mal).
      - Plan conocido + env var faltante en **dev/test** → fallback default
        (premium=100, pro=500) con warning.
      - Plan desconocido → loguea warning y retorna ``None``.
      - env var con valor no entero → loguea ERROR y retorna ``None``.

    El llamador (T1.3.C+) debe verificar el resultado con ``is None`` antes de
    invocar ``acreditar()`` — un None significa "no se acredita esta vez".

    Las variables de entorno se leen en cada llamada para facilitar tests con
    ``monkeypatch.setenv``.
    """
    plan = (plan_codigo or "").strip().lower()
    if plan not in _ENV_VAR_POR_PLAN:
        logger.warning(
            f"[BILLING] Plan desconocido en creditos_de_plan: {plan_codigo!r} — "
            f"no se acredita. Planes soportados: {list(_ENV_VAR_POR_PLAN)}."
        )
        return None

    env_var = _ENV_VAR_POR_PLAN[plan]
    raw = os.getenv(env_var, "").strip()

    if not raw:
        if es_entorno_estricto():
            logger.error(
                f"[BILLING] {env_var} no configurada en entorno estricto — "
                f"NO se acreditan créditos para plan '{plan}'. Configura la "
                f"variable en Render o suspende ventas del plan."
            )
            return None
        # Dev/test: fallback default + warning explícito.
        default = _CREDITOS_DEFAULT_DEV[plan]
        logger.warning(
            f"[BILLING] {env_var} no configurada — usando default {default} "
            f"(SOLO dev/test, configurar antes de producción)."
        )
        return default

    try:
        creditos = int(raw)
    except ValueError:
        logger.error(
            f"[BILLING] {env_var} no es un entero válido: {raw!r} — "
            f"NO se acreditan créditos para plan '{plan}'."
        )
        return None

    if creditos <= 0:
        logger.error(
            f"[BILLING] {env_var}={creditos} debe ser > 0 — "
            f"NO se acreditan créditos para plan '{plan}'."
        )
        return None

    return creditos


# ── Errores ─────────────────────────────────────────────────────────────────

class SaldoInsuficienteError(Exception):
    """El usuario no tiene créditos suficientes para la operación pedida."""
    def __init__(self, saldo: int, requerido: int):
        self.saldo = saldo
        self.requerido = requerido
        super().__init__(f"Saldo insuficiente: tiene {saldo}, necesita {requerido}")


# ── API: Saldo ──────────────────────────────────────────────────────────────

async def obtener_saldo(telefono: str) -> int:
    """Retorna el saldo actual. 0 si no hay fila."""
    from agent.memory import async_session, SaldoCreditos
    from sqlalchemy import select

    async with async_session() as session:
        row = (await session.execute(
            select(SaldoCreditos).where(SaldoCreditos.telefono == telefono)
        )).scalar_one_or_none()
        return int(row.saldo) if row else 0


async def obtener_resumen(telefono: str) -> dict:
    """Saldo + totales + últimas transacciones (para `dona saldo`)."""
    from agent.memory import async_session, SaldoCreditos, TransaccionCredito
    from sqlalchemy import select

    async with async_session() as session:
        bal = (await session.execute(
            select(SaldoCreditos).where(SaldoCreditos.telefono == telefono)
        )).scalar_one_or_none()
        saldo = int(bal.saldo) if bal else 0
        comprado = int(bal.total_comprado) if bal else 0
        consumido = int(bal.total_consumido) if bal else 0

        txs = (await session.execute(
            select(TransaccionCredito)
            .where(TransaccionCredito.telefono == telefono)
            .order_by(TransaccionCredito.creado.desc(), TransaccionCredito.id.desc())
            .limit(5)
        )).scalars().all()
        ultimos = [
            {
                "delta": t.delta, "razon": t.razon,
                "saldo_resultante": t.saldo_resultante,
                "creado": t.creado.isoformat() if t.creado else None,
            }
            for t in txs
        ]

    return {
        "saldo": saldo,
        "total_comprado": comprado,
        "total_consumido": consumido,
        "ultimos": ultimos,
    }


# ── API: Cobro / Acreditación ──────────────────────────────────────────────

async def cobrar(
    telefono: str,
    creditos: int,
    razon: str,
    asset_id: int | None = None,
    job_id: int | None = None,
) -> int:
    """
    Descuenta `creditos` del saldo del usuario de forma atómica.
    Retorna el saldo resultante. Si no alcanza, lanza `SaldoInsuficienteError`
    (sin tocar DB).

    Implementación: SELECT FOR UPDATE no es portable entre sqlite/postgres,
    así que usamos un UPDATE condicional (`WHERE saldo >= creditos`) y
    verificamos rowcount — patrón "compare-and-swap".
    """
    if creditos <= 0:
        raise ValueError("creditos debe ser > 0 en cobrar()")

    from agent.memory import async_session, SaldoCreditos, TransaccionCredito
    from sqlalchemy import select, update

    async with async_session() as session:
        # Asegurar que exista la fila
        row = (await session.execute(
            select(SaldoCreditos).where(SaldoCreditos.telefono == telefono)
        )).scalar_one_or_none()
        if row is None:
            raise SaldoInsuficienteError(saldo=0, requerido=creditos)

        # Capturar saldo previo como int puro — ORM "auto-refresca" atributos
        # del objeto luego del UPDATE, y `row.saldo` mutaría a su valor nuevo.
        saldo_prev = int(row.saldo)
        if saldo_prev < creditos:
            raise SaldoInsuficienteError(saldo=saldo_prev, requerido=creditos)

        # Update condicional — si otra request cobró simultáneamente, rowcount=0
        res = await session.execute(
            update(SaldoCreditos)
            .where(
                SaldoCreditos.telefono == telefono,
                SaldoCreditos.saldo >= creditos,
            )
            .values(
                saldo=SaldoCreditos.saldo - creditos,
                total_consumido=SaldoCreditos.total_consumido + creditos,
                actualizado=datetime.utcnow(),
            )
        )
        if res.rowcount == 0:
            # Race con otra request, reintenta una vez
            await session.rollback()
            raise SaldoInsuficienteError(saldo=saldo_prev, requerido=creditos)

        nuevo = saldo_prev - creditos
        session.add(TransaccionCredito(
            telefono=telefono,
            delta=-creditos,
            razon=razon[:120],
            asset_id=asset_id,
            job_id=job_id,
            saldo_resultante=nuevo,
            creado=datetime.utcnow(),
        ))
        await session.commit()
        return nuevo


async def acreditar(
    telefono: str,
    creditos: int,
    razon: str,
    stripe_session_id: str = "",
) -> int:
    """
    Suma `creditos` al saldo (ej: compra por Stripe, regalo, bonus).
    Idempotente por `stripe_session_id` — si ya hay una tx con ese id,
    no hace nada y retorna el saldo actual.
    """
    if creditos <= 0:
        raise ValueError("creditos debe ser > 0 en acreditar()")

    from agent.memory import async_session, SaldoCreditos, TransaccionCredito
    from sqlalchemy import select, update

    async with async_session() as session:
        # Idempotencia
        if stripe_session_id:
            ya = (await session.execute(
                select(TransaccionCredito).where(
                    TransaccionCredito.stripe_session_id == stripe_session_id
                )
            )).scalar_one_or_none()
            if ya is not None:
                logger.info(f"[BILLING] Idempotent skip: stripe_session_id={stripe_session_id} ya acreditado")
                bal = (await session.execute(
                    select(SaldoCreditos).where(SaldoCreditos.telefono == telefono)
                )).scalar_one_or_none()
                return int(bal.saldo) if bal else 0

        bal = (await session.execute(
            select(SaldoCreditos).where(SaldoCreditos.telefono == telefono)
        )).scalar_one_or_none()

        if bal is None:
            session.add(SaldoCreditos(
                telefono=telefono,
                saldo=creditos,
                total_comprado=creditos if stripe_session_id else 0,
                total_consumido=0,
                actualizado=datetime.utcnow(),
            ))
            nuevo = creditos
        else:
            # Capturar saldo previo como int puro — ORM "auto-refresca" atributos
            # del objeto luego del UPDATE, y `bal.saldo` mutaría a su valor nuevo.
            saldo_prev = int(bal.saldo)
            await session.execute(
                update(SaldoCreditos)
                .where(SaldoCreditos.telefono == telefono)
                .values(
                    saldo=SaldoCreditos.saldo + creditos,
                    total_comprado=SaldoCreditos.total_comprado + (creditos if stripe_session_id else 0),
                    actualizado=datetime.utcnow(),
                )
            )
            nuevo = saldo_prev + creditos

        session.add(TransaccionCredito(
            telefono=telefono,
            delta=creditos,
            razon=razon[:120],
            stripe_session_id=stripe_session_id[:200],
            saldo_resultante=nuevo,
            creado=datetime.utcnow(),
        ))
        await session.commit()
        return nuevo


async def cobrar_o_rechazar(
    telefono: str,
    creditos: int,
    razon: str,
) -> tuple[bool, str | None]:
    """
    Helper para tools: intenta cobrar; si no alcanza, retorna mensaje
    listo para enviar al usuario (con link a recargar).

    Uso:
        ok, err = await cobrar_o_rechazar(tel, COSTO_IMAGEN_STANDARD, "generar_imagen")
        if not ok:
            await proveedor.enviar_mensaje(tel, err)
            return
        # ...ejecutar trabajo caro...
    """
    try:
        await cobrar(telefono, creditos, razon)
        return True, None
    except SaldoInsuficienteError as e:
        msj = (
            f"⚠️ No alcanzan los créditos.\n"
            f"Necesitas *{e.requerido}*, tienes *{e.saldo}*.\n\n"
            f"Escribe *\"dona recargar\"* para comprar más."
        )
        return False, msj


# ── API: Stripe Checkout ────────────────────────────────────────────────────

async def crear_checkout(telefono: str, codigo_paquete: str, success_url: str = "", cancel_url: str = "") -> str | None:
    """
    Crea una Stripe Checkout Session y retorna la URL para compartir con el
    usuario. `telefono` viaja en `client_reference_id` para que el webhook
    sepa a quién acreditar.

    Retorna None si Stripe no está configurado o el paquete es desconocido.
    """
    paquete = paquete_por_codigo(codigo_paquete)
    if paquete is None or not paquete.stripe_price_id:
        logger.warning(f"[BILLING] Paquete inválido o sin price_id: {codigo_paquete}")
        return None

    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        logger.warning("[BILLING] STRIPE_SECRET_KEY no configurada — checkout no disponible")
        return None

    try:
        import stripe  # type: ignore
        stripe.api_key = stripe_key

        base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        default_success = f"{base}/billing/success" if base else "https://dona.app/billing/success"
        default_cancel = f"{base}/billing/cancel" if base else "https://dona.app/billing/cancel"

        # Stripe Python SDK es sync; lo corremos en thread pool para no bloquear.
        import asyncio
        def _crear():
            return stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[{"price": paquete.stripe_price_id, "quantity": 1}],
                client_reference_id=telefono,
                metadata={"telefono": telefono, "paquete": paquete.codigo, "creditos": str(paquete.creditos)},
                success_url=success_url or default_success,
                cancel_url=cancel_url or default_cancel,
            )
        session = await asyncio.to_thread(_crear)
        return session.url
    except Exception as e:
        logger.error(f"[BILLING] Error creando Stripe Checkout: {e}")
        return None


# ── API: Webhook de Stripe ──────────────────────────────────────────────────

def verificar_firma_stripe(payload: bytes, sig_header: str, webhook_secret: str | None = None) -> dict | None:
    """
    Verifica la firma de un evento de Stripe. Retorna el evento dict o None.

    Comportamiento:
      - En entorno estricto (producción o ENVIRONMENT desconocido/ausente —
        ver agent/entorno.py): si no hay secret (ni argumento ni env var),
        retorna ``None`` y loguea ERROR. Defensa en profundidad: el check
        de import-time ya debería haber abortado el deploy, pero esto cubre
        el caso de que el módulo se haya cargado por algún path alternativo
        sin el secret.
      - En dev/test explícitos: si no hay secret, parsea el JSON sin verificar
        (con warning). Permite probar el flujo localmente sin Stripe.
      - Con secret configurado: valida con ``stripe.Webhook.construct_event``.
        Si la firma es inválida, retorna ``None``.

    Las variables de entorno se leen en cada llamada (no se cachean) para
    facilitar tests con ``monkeypatch.setenv``.
    """
    secret = (
        webhook_secret if webhook_secret is not None
        else os.getenv("STRIPE_WEBHOOK_SECRET", "")
    ).strip()

    if not secret:
        if es_entorno_estricto():
            logger.error(
                "[BILLING] STRIPE_WEBHOOK_SECRET no configurada en entorno "
                "estricto — rechazando webhook (no se acreditan créditos)."
            )
            return None
        logger.warning(
            "[BILLING] STRIPE_WEBHOOK_SECRET no configurada — "
            "aceptando sin verificar (INSEGURO, solo dev/test)."
        )
        try:
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return None

    try:
        import stripe  # type: ignore
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as e:
        logger.warning(f"[BILLING] Firma Stripe inválida: {e}")
        return None


async def procesar_evento_stripe(evento: dict) -> dict:
    """
    Procesa un evento verificado de Stripe. Actualmente sólo actuamos sobre
    `checkout.session.completed`: acredita los créditos comprados.

    Retorna dict con `handled: bool` y contexto para logs/tests.
    """
    tipo = evento.get("type") or evento.get("event")
    data = (evento.get("data") or {}).get("object") or {}

    if tipo != "checkout.session.completed":
        return {"handled": False, "reason": f"evento ignorado: {tipo}"}

    telefono = data.get("client_reference_id") or (data.get("metadata") or {}).get("telefono", "")
    creditos_raw = (data.get("metadata") or {}).get("creditos", "")
    session_id = data.get("id", "")

    try:
        creditos = int(creditos_raw)
    except (TypeError, ValueError):
        creditos = 0

    if not telefono or creditos <= 0:
        logger.warning(f"[BILLING] Evento sin telefono/creditos: id={session_id}")
        return {"handled": False, "reason": "metadata faltante"}

    saldo = await acreditar(
        telefono=telefono,
        creditos=creditos,
        razon=f"Compra paquete ({creditos} créditos)",
        stripe_session_id=session_id,
    )
    logger.info(f"[BILLING] Acreditado {creditos} cr → {telefono} (saldo={saldo})")
    return {"handled": True, "telefono": telefono, "creditos": creditos, "saldo": saldo}


# ── API: Webhook de Stripe — eventos de suscripción (T1.3.C) ───────────────
#
# Esta función es el dispatcher de los 4 tipos de evento que componen el ciclo
# de vida de una suscripción Stripe en Dona:
#
#   1. checkout.session.completed (mode=subscription)
#        El cliente terminó el checkout de la landing. Crea/actualiza la fila
#        en `suscripcion_stripe` con telefono + plan + creditos_mensuales.
#        NO acredita créditos todavía — eso lo hace invoice.payment_succeeded
#        cuando Stripe cobra el primer mes (típicamente segundos después).
#        Si el evento de invoice llega ANTES (race), `_procesar_invoice_*`
#        rechaza por "subscription_no_persistida" y Stripe reintenta.
#
#   2. invoice.payment_succeeded
#        Stripe cobró un periodo (el primero o una renovación). Acredita
#        `creditos_mensuales` al teléfono de la suscripción. Idempotente por
#        `invoice.id` (`ultimo_invoice_acreditado` en SuscripcionStripe) y
#        adicionalmente por `acreditar(stripe_session_id=invoice_id)` que
#        revisa TransaccionCredito. Decisión owner: créditos son ACUMULABLES
#        (no resetean saldo).
#
#   3. customer.subscription.updated
#        Cambio de plan, status (past_due, active, etc.) o price. Actualiza
#        la fila pero NO toca saldo. Si cambia el plan_codigo, recalcula
#        `creditos_mensuales` para la próxima renovación.
#
#   4. customer.subscription.deleted
#        Cancelación. Marca status="canceled" pero PRESERVA el saldo de
#        créditos del usuario (decisión owner: lo que ya pagaron es suyo).
#
# Idempotencia a tres niveles para defender contra reentregas de Stripe:
#   - `EventoStripeProcesado.event_id` (cualquier evento, primer filtro).
#   - `SuscripcionStripe.ultimo_invoice_acreditado` (solo invoices, segundo).
#   - `TransaccionCredito.stripe_session_id` (último filtro dentro de acreditar).
#
# El llamador (T1.3.D, endpoint /internal/stripe-event) decide qué hacer con
# el resultado: 200 si handled o si fue duplicado conocido, 500 si hubo error
# inesperado para forzar el retry de Stripe.


async def procesar_evento_suscripcion(evento: dict) -> dict:
    """
    Procesa un evento Stripe de suscripción (4 tipos soportados).

    Maneja la idempotencia por ``event.id`` antes de despachar al handler.
    Retorna dict con ``handled: bool`` y contexto. Nunca propaga excepciones
    de DB hacia arriba (el llamador decide el status HTTP).
    """
    from agent.memory import async_session, EventoStripeProcesado
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    tipo = evento.get("type", "") or ""
    event_id = evento.get("id", "") or ""

    if not event_id:
        logger.warning("[BILLING] Evento de suscripción sin event_id — no procesable")
        return {"handled": False, "reason": "missing_event_id"}

    # Filtro 1 (idempotencia general): event_id ya procesado.
    async with async_session() as session:
        ya = (await session.execute(
            select(EventoStripeProcesado).where(
                EventoStripeProcesado.event_id == event_id
            )
        )).scalar_one_or_none()
        if ya is not None:
            logger.info(f"[BILLING] Evento ya procesado, skip: {event_id} ({tipo})")
            return {"handled": False, "reason": "duplicate_event", "event_id": event_id}

    data = (evento.get("data") or {}).get("object") or {}

    if tipo == "checkout.session.completed":
        # Solo procesamos checkouts mode=subscription. Los mode=payment los
        # maneja `procesar_evento_stripe` (legacy paquetes one-time).
        if data.get("mode") != "subscription":
            return {
                "handled": False,
                "reason": f"checkout no es subscription (mode={data.get('mode')})",
            }
        resultado = await _procesar_checkout_subscription(data)
    elif tipo == "invoice.payment_succeeded":
        resultado = await _procesar_invoice_payment_succeeded(data)
    elif tipo == "customer.subscription.updated":
        resultado = await _procesar_subscription_updated(data)
    elif tipo == "customer.subscription.deleted":
        resultado = await _procesar_subscription_deleted(data)
    else:
        return {"handled": False, "reason": f"tipo no soportado: {tipo}"}

    # Solo marcamos como procesado si el handler confirmó éxito. Eventos
    # rechazados (plan inválido, telefono faltante, etc.) NO se marcan: si
    # Stripe reentrega después de que el owner arregle la config, se vuelven
    # a procesar. Decisión consciente — preferimos reintentos sobre eventos
    # huérfanos que requieren intervención manual.
    if resultado.get("handled"):
        async with async_session() as session:
            session.add(EventoStripeProcesado(event_id=event_id, tipo=tipo))
            try:
                await session.commit()
            except IntegrityError:
                # Race: otro hilo lo marcó al mismo tiempo. El estado en DB
                # ya es consistente; el resultado del handler es válido.
                await session.rollback()
                logger.info(
                    f"[BILLING] Evento {event_id} marcado por otro hilo (race benigno)"
                )

    return resultado


async def _procesar_checkout_subscription(data: dict) -> dict:
    """
    checkout.session.completed con mode=subscription.

    Crea o actualiza la fila SuscripcionStripe. NO acredita créditos.
    Los créditos se acreditan en invoice.payment_succeeded para que un
    checkout sin pago concretado (raro pero posible) no regale créditos.
    """
    from agent.memory import async_session, SuscripcionStripe
    from sqlalchemy import select

    subscription_id = (data.get("subscription") or "").strip()
    customer_id = (data.get("customer") or "").strip()
    metadata = data.get("metadata") or {}
    plan_codigo = (metadata.get("plan") or "").strip().lower()

    # Telefono: prioridad metadata.phone (lo que setea el landing al crear la
    # session), fallback customer_details.phone (lo que llena el cliente en
    # el checkout). Quitamos el "+" inicial para alinear con el formato que
    # usa el resto del backend (e164 sin signo).
    telefono = (
        metadata.get("phone")
        or (data.get("customer_details") or {}).get("phone")
        or ""
    ).strip().lstrip("+")

    # Nombre del customer · best-effort para personalizar el welcome (T2.0.B).
    # checkout.session.completed trae customer_details.name si Stripe lo
    # capturó en el form. Si falta, el welcome usa "Hola!" sin nombre.
    nombre_customer = (
        (data.get("customer_details") or {}).get("name") or ""
    ).strip() or None

    if not subscription_id:
        logger.warning("[BILLING] checkout subscription sin subscription_id")
        return {"handled": False, "reason": "missing_subscription_id"}

    if not telefono:
        logger.warning(
            f"[BILLING] checkout subscription sin telefono: sub={subscription_id}"
        )
        return {"handled": False, "reason": "missing_telefono"}

    creditos = creditos_de_plan(plan_codigo)
    if creditos is None:
        # creditos_de_plan ya logueó el motivo (plan desconocido o env faltante).
        return {"handled": False, "reason": f"plan_invalido: {plan_codigo!r}"}

    async with async_session() as session:
        existing = (await session.execute(
            select(SuscripcionStripe).where(
                SuscripcionStripe.subscription_id == subscription_id
            )
        )).scalar_one_or_none()

        if existing is not None:
            # Re-checkout para la misma subscription (raro pero posible si el
            # cliente reabre el link). Actualizamos plan/telefono en lugar de
            # crear duplicado.
            existing.telefono = telefono
            existing.customer_id = customer_id
            existing.plan_codigo = plan_codigo
            existing.creditos_mensuales = creditos
            existing.status = "active"
            existing.actualizado = datetime.utcnow()
            accion = "updated"
        else:
            session.add(SuscripcionStripe(
                subscription_id=subscription_id,
                telefono=telefono,
                customer_id=customer_id,
                plan_codigo=plan_codigo,
                price_id="",  # se completa en customer.subscription.updated
                status="active",
                creditos_mensuales=creditos,
            ))
            accion = "created"
        await session.commit()

    logger.info(
        f"[BILLING] Checkout {accion}: sub={subscription_id} "
        f"plan={plan_codigo} creditos_mensuales={creditos}"
    )

    # T2.0.B — Welcome automático con password derivado SOLO en accion=created.
    # Idempotencia adicional vía SuscripcionStripe.bienvenida_enviada (la función
    # vuelve a chequear el flag). Si falla, no rompemos el procesamiento del
    # evento — el owner puede regenerar manualmente con el CLI helper de T1.4.B.
    welcome_resultado: str | None = None
    if accion == "created":
        try:
            from agent.welcome import enviar_bienvenida_premium
            welcome_resultado = await enviar_bienvenida_premium(
                subscription_id=subscription_id,
                customer_id=customer_id,
                telefono=telefono,
                plan_codigo=plan_codigo,
                creditos_mensuales=creditos,
                nombre_customer=nombre_customer,
            )
        except Exception as e:
            # Defensa adicional: enviar_bienvenida_premium ya tiene su propio
            # try/except, pero por si algo más arriba (import, DB) explota.
            logger.exception(
                f"[BILLING] welcome falló sub={subscription_id}: {type(e).__name__}"
            )
            welcome_resultado = "envio_fallo"

    return {
        "handled": True,
        "tipo": "checkout.session.completed",
        "accion": accion,
        "subscription_id": subscription_id,
        "telefono": telefono,
        "plan_codigo": plan_codigo,
        "creditos_mensuales": creditos,
        # Solo aparece cuando accion=created. None en updated.
        "welcome": welcome_resultado,
    }


async def _procesar_invoice_payment_succeeded(data: dict) -> dict:
    """
    invoice.payment_succeeded — acredita créditos del periodo (acumulables).

    Doble idempotencia:
      - ``SuscripcionStripe.ultimo_invoice_acreditado``: si ya acreditamos este
        invoice, no acreditamos de nuevo.
      - ``acreditar(stripe_session_id=invoice_id)``: revisa TransaccionCredito.

    Si la suscripción no existe en DB (race con checkout.session.completed),
    rechazamos. Stripe reintenta y debería llegar después.
    """
    from agent.memory import async_session, SuscripcionStripe
    from sqlalchemy import select

    invoice_id = (data.get("id") or "").strip()
    subscription_id = (data.get("subscription") or "").strip()

    if not invoice_id:
        logger.warning("[BILLING] invoice sin id")
        return {"handled": False, "reason": "missing_invoice_id"}

    if not subscription_id:
        logger.warning(f"[BILLING] invoice {invoice_id} sin subscription")
        return {"handled": False, "reason": "missing_subscription_id"}

    # Cargar SuscripcionStripe; capturar campos que necesitamos antes de salir
    # del session scope (telefono, creditos_mensuales, plan_codigo).
    async with async_session() as session:
        sub = (await session.execute(
            select(SuscripcionStripe).where(
                SuscripcionStripe.subscription_id == subscription_id
            )
        )).scalar_one_or_none()

        if sub is None:
            logger.warning(
                f"[BILLING] invoice {invoice_id} para sub desconocida {subscription_id} "
                f"— posible race con checkout.session.completed; Stripe reintentará"
            )
            return {"handled": False, "reason": "subscription_no_persistida"}

        # Filtro 2: invoice ya acreditado para esta suscripción.
        if sub.ultimo_invoice_acreditado == invoice_id:
            logger.info(
                f"[BILLING] invoice {invoice_id} ya acreditado para sub {subscription_id}"
            )
            return {"handled": False, "reason": "invoice_ya_acreditado"}

        creditos = int(sub.creditos_mensuales)
        telefono = sub.telefono
        plan_codigo = sub.plan_codigo
        status_actual = sub.status

    # Acreditar fuera del session scope anterior; `acreditar` abre el suyo.
    # El stripe_session_id lleva el invoice_id como tercer nivel de idempotencia.
    saldo = await acreditar(
        telefono=telefono,
        creditos=creditos,
        razon=f"Renovación {plan_codigo} ({creditos} créditos)",
        stripe_session_id=invoice_id,
    )

    # Marcar invoice como procesado y reactivar status si venía de past_due.
    async with async_session() as session:
        sub = (await session.execute(
            select(SuscripcionStripe).where(
                SuscripcionStripe.subscription_id == subscription_id
            )
        )).scalar_one_or_none()
        if sub is not None:
            sub.ultimo_invoice_acreditado = invoice_id
            sub.actualizado = datetime.utcnow()
            # Solo reactivamos a "active" si el status anterior NO era una
            # cancelación firme. Si la suscripción fue cancelada y por alguna
            # razón llega un invoice tardío, no la resucitamos.
            if status_actual not in ("canceled",):
                sub.status = "active"
            await session.commit()

    logger.info(
        f"[BILLING] Acreditado {creditos} cr (invoice={invoice_id} sub={subscription_id} saldo={saldo})"
    )
    return {
        "handled": True,
        "tipo": "invoice.payment_succeeded",
        "subscription_id": subscription_id,
        "invoice_id": invoice_id,
        "telefono": telefono,
        "creditos": creditos,
        "saldo": saldo,
    }


async def _procesar_subscription_updated(data: dict) -> dict:
    """
    customer.subscription.updated — actualiza plan/status/price/creditos_mensuales.

    NO toca saldo: el cambio aplica a la próxima renovación. Si el cliente sube
    de Premium a Pro a mitad de periodo, los 100 créditos de este mes ya están
    acreditados; la próxima invoice traerá los 500 nuevos.
    """
    from agent.memory import async_session, SuscripcionStripe
    from sqlalchemy import select

    subscription_id = (data.get("id") or "").strip()
    if not subscription_id:
        logger.warning("[BILLING] subscription_updated sin id")
        return {"handled": False, "reason": "missing_subscription_id"}

    nuevo_status = (data.get("status") or "").strip()
    items = (data.get("items") or {}).get("data") or []
    nuevo_price_id = ""
    if items:
        nuevo_price_id = ((items[0].get("price") or {}).get("id") or "").strip()

    metadata = data.get("metadata") or {}
    nuevo_plan = (metadata.get("plan") or "").strip().lower()

    async with async_session() as session:
        sub = (await session.execute(
            select(SuscripcionStripe).where(
                SuscripcionStripe.subscription_id == subscription_id
            )
        )).scalar_one_or_none()

        if sub is None:
            logger.warning(
                f"[BILLING] subscription_updated para sub desconocida {subscription_id}"
            )
            return {"handled": False, "reason": "subscription_no_persistida"}

        cambios = []
        if nuevo_status and nuevo_status != sub.status:
            cambios.append(f"status:{sub.status}->{nuevo_status}")
            sub.status = nuevo_status
        if nuevo_price_id and nuevo_price_id != sub.price_id:
            cambios.append(f"price_id:{sub.price_id}->{nuevo_price_id}")
            sub.price_id = nuevo_price_id
        if nuevo_plan and nuevo_plan != sub.plan_codigo:
            nuevos_creditos = creditos_de_plan(nuevo_plan)
            if nuevos_creditos is not None:
                cambios.append(f"plan:{sub.plan_codigo}->{nuevo_plan}")
                cambios.append(
                    f"creditos_mensuales:{sub.creditos_mensuales}->{nuevos_creditos}"
                )
                sub.plan_codigo = nuevo_plan
                sub.creditos_mensuales = nuevos_creditos
            else:
                # creditos_de_plan ya logueó. Mantenemos el plan anterior.
                cambios.append(f"plan:{nuevo_plan}_rechazado")

        sub.actualizado = datetime.utcnow()
        await session.commit()

    logger.info(
        f"[BILLING] subscription_updated {subscription_id}: "
        f"{('; '.join(cambios)) if cambios else 'sin cambios relevantes'}"
    )
    return {
        "handled": True,
        "tipo": "customer.subscription.updated",
        "subscription_id": subscription_id,
        "cambios": cambios,
    }


async def _procesar_subscription_deleted(data: dict) -> dict:
    """
    customer.subscription.deleted — marca status="canceled".

    NO toca el saldo de créditos del usuario. Decisión owner: lo que el cliente
    ya pagó es suyo aunque haya cancelado. La próxima renovación simplemente
    no llegará (Stripe deja de generar invoices).
    """
    from agent.memory import async_session, SuscripcionStripe
    from sqlalchemy import select

    subscription_id = (data.get("id") or "").strip()
    if not subscription_id:
        logger.warning("[BILLING] subscription_deleted sin id")
        return {"handled": False, "reason": "missing_subscription_id"}

    async with async_session() as session:
        sub = (await session.execute(
            select(SuscripcionStripe).where(
                SuscripcionStripe.subscription_id == subscription_id
            )
        )).scalar_one_or_none()

        if sub is None:
            logger.warning(
                f"[BILLING] subscription_deleted para sub desconocida {subscription_id}"
            )
            return {"handled": False, "reason": "subscription_no_persistida"}

        sub.status = "canceled"
        sub.actualizado = datetime.utcnow()
        await session.commit()

    logger.info(f"[BILLING] subscription canceled: {subscription_id}")
    return {
        "handled": True,
        "tipo": "customer.subscription.deleted",
        "subscription_id": subscription_id,
    }
