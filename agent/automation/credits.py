# agent/automation/credits.py — Reservas de créditos · T2.1.D + T2.1.D.1

"""
Patrón "write-ahead + cobro + reconciliación":

Pipeline normal:
    reservar(accion_id, telefono, creditos)
      1. INSERT fila estado='preparing' (write-ahead · sin tocar saldo)
      2. agent.billing.cobrar(..., job_id=accion_id) → atómico en su sesión
      3. UPDATE fila → estado='pending' + link a TransaccionCredito.id
      4. audit log 'credits_reserved'
    confirmar(accion_id)
      → estado='confirmed' · NO toca saldo
      → audit 'credits_confirmed'
    liberar(accion_id, razon)
      → agent.billing.acreditar → estado='released'
      → audit 'credits_released'

Saldo insuficiente:
    reservar() detecta SaldoInsuficienteError de billing.cobrar:
      → fila ya existe como 'preparing' · la marca 'failed'
      → audit 'credits_reservation_failed' + 'action_blocked_insufficient_credits'
      → relanza CreditosInsuficientesError.

Riesgo residual mitigado (T2.1.D.1):
    Si la app crashea ENTRE billing.cobrar (paso 2 ya commitado en DB) y
    el UPDATE final (paso 3), la fila queda en 'preparing' y la
    TransaccionCredito de cobro ya está persistida con job_id=accion_id.
    `reconciliar_accion(accion_id)` detecta esta situación: si existe la
    transacción de cobro la AVANZA a 'pending' (sin doble cobrar); si no
    existe y la fila es lo bastante vieja, la marca 'failed' (saldo no se
    movió, libre para reintento del worker).
    `reconciliar_reservas()` hace el barrido en batch.
    Además, `reservar()` invoca reconciliación inline cuando encuentra
    una fila pre-existente en 'preparing' (autoreparación del happy path
    del reintento del worker).

Idempotencia:
    UNIQUE(accion_id) garantiza una fila por acción. Re-llamar
    reservar() para una acción con reserva 'pending'/'confirmed' la
    devuelve sin volver a cobrar. confirmar()/liberar() son no-op en
    estados terminales.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("dona")

# Ventana de gracia antes de considerar una fila 'preparing' como
# huérfana cuando el cobro nunca ocurrió.
RECONCILE_EDAD_MIN_SEGUNDOS = 120


class CreditosInsuficientesError(Exception):
    """Wrapper de billing.SaldoInsuficienteError con campos públicos."""

    def __init__(self, *, saldo: int, requerido: int):
        self.saldo = saldo
        self.requerido = requerido
        super().__init__(
            f"Saldo insuficiente: tienes {saldo} créditos · necesitas {requerido}"
        )


# ── API pública ──────────────────────────────────────────────────────────


async def reservar(
    *,
    accion_id: int,
    telefono: str,
    creditos: int,
    razon: str = "",
) -> dict[str, Any]:
    """Reserva créditos para una acción con write-ahead.

    Returns:
        dict con la reserva en estado terminal de éxito: 'pending'
        (cobro completo). Si los créditos son 0 también retorna
        'pending' (sin cobro). Si la reserva ya estaba 'pending' o
        'confirmed' la devuelve idempotente.

    Raises:
        CreditosInsuficientesError si el cobro falla por saldo.
        ValueError si creditos < 0.
    """
    if creditos < 0:
        raise ValueError("creditos debe ser >= 0")

    # 1. Reserva pre-existente · idempotencia o reconciliación inline
    existing = await obtener_reserva(accion_id)
    if existing is not None:
        if existing["estado"] == "preparing":
            # Posible crash anterior · reconciliar antes de decidir
            existing = await reconciliar_accion(
                accion_id, max_edad_segundos=0,
            ) or existing
        if existing["estado"] in ("pending", "confirmed"):
            logger.info(
                f"[CREDITS] reserva idempotente accion_id={accion_id} "
                f"estado={existing['estado']} · no se cobra"
            )
            return existing
        # released/failed → permitir nuevo intento de cobro

    # 2. Caso gratuito · sin cobro
    if creditos == 0:
        return await _persistir_reserva(
            accion_id=accion_id, telefono=telefono, creditos=0,
            razon=razon, estado="pending",
            transaccion_credito_id=None, sustituir_si_existe=True,
        )

    # 3. Write-ahead · fila 'preparing' antes de tocar saldo
    try:
        await _persistir_reserva(
            accion_id=accion_id, telefono=telefono, creditos=creditos,
            razon=razon, estado="preparing",
            transaccion_credito_id=None, sustituir_si_existe=True,
        )
    except IntegrityError:
        # Race · otra task escribió antes. Re-leer y reciclar lógica.
        await asyncio.sleep(0)
        return await reservar(
            accion_id=accion_id, telefono=telefono,
            creditos=creditos, razon=razon,
        )

    # 4. Cobro real · billing.cobrar es atómico en su propia sesión
    from agent.billing import cobrar, SaldoInsuficienteError

    try:
        await cobrar(
            telefono,
            creditos,
            razon=f"reserva acción #{accion_id}: {razon[:80]}",
            asset_id=None,
            job_id=accion_id,
        )
    except SaldoInsuficienteError as e:
        # El cobro NO movió saldo · marcar fila como failed
        await _actualizar_estado_y_tx(
            accion_id, estado="failed", transaccion_credito_id=None,
        )
        from agent.automation.audit import registrar_evento
        await registrar_evento(
            evento="credits_reservation_failed",
            telefono=telefono,
            accion_id=accion_id,
            payload={
                "creditos_requeridos": creditos,
                "saldo_actual": e.saldo,
                "motivo": "saldo_insuficiente",
            },
        )
        await registrar_evento(
            evento="action_blocked_insufficient_credits",
            telefono=telefono,
            accion_id=accion_id,
            payload={
                "creditos_requeridos": creditos,
                "saldo_actual": e.saldo,
            },
        )
        raise CreditosInsuficientesError(
            saldo=e.saldo, requerido=creditos,
        ) from None

    # 5. Cobro OK · localizar la TransaccionCredito y completar reserva
    tx_id = await _ultima_tx_id_para_accion(accion_id, telefono, creditos)
    reserva_final = await _actualizar_estado_y_tx(
        accion_id, estado="pending", transaccion_credito_id=tx_id,
    )

    from agent.automation.audit import registrar_evento
    from agent.billing import obtener_saldo
    saldo_actual = await obtener_saldo(telefono)
    await registrar_evento(
        evento="credits_reserved",
        telefono=telefono,
        accion_id=accion_id,
        payload={
            "creditos": creditos,
            "saldo_post_reserva": saldo_actual,
            "transaccion_credito_id": tx_id,
        },
    )
    return reserva_final


async def confirmar(accion_id: int) -> dict[str, Any] | None:
    """Confirma una reserva 'pending' · estado→'confirmed'. No-op si la
    reserva ya está confirmed/released/failed o no existe."""
    from agent.memory import async_session
    from agent.automation.models import ReservaCreditoAutomation
    from agent.automation.audit import registrar_evento

    async with async_session() as session:
        row = (await session.execute(
            select(ReservaCreditoAutomation).where(
                ReservaCreditoAutomation.accion_id == accion_id
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        if row.estado != "pending":
            return _to_dict(row)
        row.estado = "confirmed"
        row.actualizado = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        result = _to_dict(row)

    await registrar_evento(
        evento="credits_confirmed",
        telefono=result["telefono"],
        accion_id=accion_id,
        payload={"creditos": result["creditos"]},
    )
    return result


async def liberar(
    accion_id: int, *, razon: str = "ejecución fallida",
) -> dict[str, Any] | None:
    """Libera una reserva 'pending' · acredita de vuelta los créditos
    al usuario · estado→'released'.

    No-op si la reserva ya está confirmed/released/failed o no existe.
    """
    from agent.memory import async_session
    from agent.automation.models import ReservaCreditoAutomation
    from agent.automation.audit import registrar_evento
    from agent.billing import acreditar

    async with async_session() as session:
        row = (await session.execute(
            select(ReservaCreditoAutomation).where(
                ReservaCreditoAutomation.accion_id == accion_id
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        if row.estado != "pending":
            return _to_dict(row)
        creditos = int(row.creditos)
        telefono = row.telefono

    if creditos > 0:
        await acreditar(
            telefono,
            creditos,
            razon=f"reembolso reserva acción #{accion_id}: {razon[:60]}",
        )

    async with async_session() as session:
        row = (await session.execute(
            select(ReservaCreditoAutomation).where(
                ReservaCreditoAutomation.accion_id == accion_id
            )
        )).scalar_one()
        row.estado = "released"
        row.actualizado = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        result = _to_dict(row)

    await registrar_evento(
        evento="credits_released",
        telefono=telefono,
        accion_id=accion_id,
        payload={
            "creditos_reembolsados": creditos,
            "razon": razon[:100],
        },
    )
    return result


async def obtener_reserva(accion_id: int) -> dict[str, Any] | None:
    """Lee la reserva asociada · útil para tests y diagnóstico."""
    from agent.memory import async_session
    from agent.automation.models import ReservaCreditoAutomation
    async with async_session() as session:
        row = (await session.execute(
            select(ReservaCreditoAutomation).where(
                ReservaCreditoAutomation.accion_id == accion_id
            )
        )).scalar_one_or_none()
    return _to_dict(row) if row else None


# ── Reconciliación · T2.1.D.1 ────────────────────────────────────────────


async def reconciliar_accion(
    accion_id: int,
    *,
    max_edad_segundos: int = RECONCILE_EDAD_MIN_SEGUNDOS,
) -> dict[str, Any] | None:
    """Repara una reserva que quedó en 'preparing'.

    Pasos:
      1. Lee la fila. Si no es 'preparing' devuelve tal cual.
      2. Busca TransaccionCredito con job_id=accion_id, delta<0 y monto
         que coincida con creditos. Si existe → AVANZA a 'pending'
         + transaccion_credito_id + audit 'credits_reservation_reconciled'
         con resultado 'promoted_to_pending'.
      3. Si no existe Y la fila tiene edad ≥ max_edad_segundos → marca
         'failed' (saldo nunca se movió) + audit con resultado
         'marked_failed'.
      4. Si no existe pero la fila es reciente → no toca (puede estar
         legítimamente en vuelo en otro worker).

    Returns: dict de la reserva final, o None si no había reserva.
    """
    from agent.automation.audit import registrar_evento

    reserva = await obtener_reserva(accion_id)
    if reserva is None or reserva["estado"] != "preparing":
        return reserva

    telefono = reserva["telefono"]
    creditos = int(reserva["creditos"])

    tx_id = await _ultima_tx_id_para_accion(
        accion_id, telefono, creditos,
    )
    if tx_id is not None:
        actualizada = await _actualizar_estado_y_tx(
            accion_id, estado="pending", transaccion_credito_id=tx_id,
        )
        await registrar_evento(
            evento="credits_reservation_reconciled",
            telefono=telefono,
            accion_id=accion_id,
            payload={
                "resultado": "promoted_to_pending",
                "transaccion_credito_id": tx_id,
                "creditos": creditos,
            },
        )
        return actualizada

    # No hay transacción asociada · evaluar edad
    creado = _parse_iso(reserva["creado"])
    edad = (datetime.utcnow() - creado).total_seconds() if creado else 0
    if edad < max_edad_segundos:
        return reserva

    actualizada = await _actualizar_estado_y_tx(
        accion_id, estado="failed", transaccion_credito_id=None,
    )
    await registrar_evento(
        evento="credits_reservation_reconciled",
        telefono=telefono,
        accion_id=accion_id,
        payload={
            "resultado": "marked_failed",
            "creditos": creditos,
            "edad_segundos": int(edad),
        },
    )
    return actualizada


async def reconciliar_reservas(
    *,
    max_edad_segundos: int = RECONCILE_EDAD_MIN_SEGUNDOS,
    limit: int = 500,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Barrido batch · reconcilia todas las reservas 'preparing'.

    En dry_run sólo cuenta cuántas filas serían tocadas (promoted vs
    marked_failed vs intactas).
    """
    from agent.memory import async_session
    from agent.automation.models import ReservaCreditoAutomation

    if limit < 1 or limit > 5000:
        raise ValueError("limit debe estar entre 1 y 5000")

    async with async_session() as session:
        rows = (await session.execute(
            select(ReservaCreditoAutomation)
            .where(ReservaCreditoAutomation.estado == "preparing")
            .order_by(ReservaCreditoAutomation.creado.asc())
            .limit(limit)
        )).scalars().all()

    pendientes = []
    for r in rows:
        pendientes.append({
            "accion_id": r.accion_id,
            "telefono": r.telefono,
            "creditos": int(r.creditos),
            "creado": r.creado.isoformat() if r.creado else None,
        })

    if dry_run:
        promoted_estimado = 0
        marked_failed_estimado = 0
        intactas_estimado = 0
        for p in pendientes:
            tx_id = await _ultima_tx_id_para_accion(
                p["accion_id"], p["telefono"], p["creditos"],
            )
            if tx_id is not None:
                promoted_estimado += 1
            else:
                creado = _parse_iso(p["creado"])
                edad = (datetime.utcnow() - creado).total_seconds() if creado else 0
                if edad >= max_edad_segundos:
                    marked_failed_estimado += 1
                else:
                    intactas_estimado += 1
        return {
            "dry_run": True,
            "total_preparing": len(pendientes),
            "promoted_estimado": promoted_estimado,
            "marked_failed_estimado": marked_failed_estimado,
            "intactas_estimado": intactas_estimado,
        }

    promoted = 0
    marked_failed = 0
    intactas = 0
    for p in pendientes:
        r = await reconciliar_accion(
            p["accion_id"], max_edad_segundos=max_edad_segundos,
        )
        if r is None:
            continue
        if r["estado"] == "pending":
            promoted += 1
        elif r["estado"] == "failed":
            marked_failed += 1
        else:
            intactas += 1
    return {
        "dry_run": False,
        "total_preparing_inicial": len(pendientes),
        "promoted": promoted,
        "marked_failed": marked_failed,
        "intactas": intactas,
    }


# ── Helpers internos ──────────────────────────────────────────────────────


async def _persistir_reserva(
    *,
    accion_id: int,
    telefono: str,
    creditos: int,
    razon: str,
    estado: str,
    transaccion_credito_id: int | None,
    sustituir_si_existe: bool,
) -> dict[str, Any]:
    """UPSERT · respeta UNIQUE(accion_id)."""
    from agent.memory import async_session
    from agent.automation.models import ReservaCreditoAutomation

    async with async_session() as session:
        existing = (await session.execute(
            select(ReservaCreditoAutomation).where(
                ReservaCreditoAutomation.accion_id == accion_id
            )
        )).scalar_one_or_none()
        if existing is not None:
            if not sustituir_si_existe:
                return _to_dict(existing)
            existing.creditos = creditos
            existing.estado = estado
            existing.razon = razon[:1000]
            existing.transaccion_credito_id = transaccion_credito_id
            existing.actualizado = datetime.utcnow()
            await session.commit()
            await session.refresh(existing)
            return _to_dict(existing)
        nueva = ReservaCreditoAutomation(
            accion_id=accion_id,
            telefono=telefono,
            creditos=creditos,
            estado=estado,
            razon=razon[:1000],
            transaccion_credito_id=transaccion_credito_id,
            creado=datetime.utcnow(),
            actualizado=datetime.utcnow(),
        )
        session.add(nueva)
        await session.commit()
        await session.refresh(nueva)
        return _to_dict(nueva)


async def _actualizar_estado_y_tx(
    accion_id: int,
    *,
    estado: str,
    transaccion_credito_id: int | None,
) -> dict[str, Any] | None:
    """UPDATE estado y opcionalmente la FK a TransaccionCredito."""
    from agent.memory import async_session
    from agent.automation.models import ReservaCreditoAutomation

    async with async_session() as session:
        row = (await session.execute(
            select(ReservaCreditoAutomation).where(
                ReservaCreditoAutomation.accion_id == accion_id
            )
        )).scalar_one_or_none()
        if row is None:
            return None
        row.estado = estado
        if transaccion_credito_id is not None:
            row.transaccion_credito_id = transaccion_credito_id
        row.actualizado = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        return _to_dict(row)


async def _ultima_tx_id_para_accion(
    accion_id: int, telefono: str, creditos: int,
) -> int | None:
    """Busca la TransaccionCredito que corresponde al cobro de esta
    acción. Match por (job_id=accion_id, telefono, delta=-creditos),
    elige la más reciente. Retorna su id o None.
    """
    from agent.memory import async_session, TransaccionCredito
    async with async_session() as session:
        rows = (await session.execute(
            select(TransaccionCredito)
            .where(
                TransaccionCredito.job_id == accion_id,
                TransaccionCredito.telefono == telefono,
                TransaccionCredito.delta == -creditos,
            )
            .order_by(TransaccionCredito.id.desc())
            .limit(1)
        )).scalars().all()
    return int(rows[0].id) if rows else None


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _to_dict(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "accion_id": row.accion_id,
        "telefono": row.telefono,
        "creditos": row.creditos,
        "estado": row.estado,
        "razon": row.razon,
        "transaccion_credito_id": row.transaccion_credito_id,
        "creado": row.creado.isoformat() if row.creado else None,
        "actualizado": row.actualizado.isoformat() if row.actualizado else None,
    }
