# agent/automation/credits.py — Reservas de créditos · T2.1.D

"""
Patrón "cobrar al crear, reembolsar si falla".

Pipeline:
    reservar(accion_id, telefono, creditos)
      → cobra atómicamente (saldo - creditos) usando agent.billing.cobrar
      → registra ReservaCreditoAutomation con estado='pending'
      → audit log 'credits_reserved'
    confirmar(accion_id)
      → estado='confirmed' · NO toca saldo (el descuento ya quedó firme)
      → audit log 'credits_confirmed'
    liberar(accion_id, razon)
      → acredita de vuelta vía agent.billing.acreditar
      → estado='released'
      → audit log 'credits_released'

Idempotencia:
    Cada acción tiene UNIQUE(accion_id) en la tabla. Re-llamar reservar()
    para la misma acción retorna la reserva existente sin volver a cobrar.
    confirmar() / liberar() son no-ops si ya están en estado terminal.

Saldo insuficiente:
    reservar() relanza SaldoInsuficienteError de agent.billing y
    registra una fila estado='failed' (sin descuento) para audit.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

logger = logging.getLogger("dona")


class CreditosInsuficientesError(Exception):
    """Wrapper de billing.SaldoInsuficienteError con campos públicos."""

    def __init__(self, *, saldo: int, requerido: int):
        self.saldo = saldo
        self.requerido = requerido
        super().__init__(
            f"Saldo insuficiente: tienes {saldo} créditos · necesitas {requerido}"
        )


async def reservar(
    *,
    accion_id: int,
    telefono: str,
    creditos: int,
    razon: str = "",
) -> dict[str, Any]:
    """Crea (o devuelve si ya existe) una reserva de créditos para una acción.

    Comportamiento:
      - Si ya hay reserva en estado 'pending'|'confirmed' para esta
        accion_id → la devuelve sin cobrar de nuevo (idempotente).
      - Si la reserva existente está en 'released'|'failed' →
        intentamos cobrar otra vez (re-ejecución legítima tras fallo).
      - Si el cobro funciona → fila nueva (o actualizada) con estado
        'pending' + audit log 'credits_reserved'.
      - Si el cobro falla por saldo insuficiente → fila con estado
        'failed' + audit log 'credits_reservation_failed' + raise
        CreditosInsuficientesError.
      - Si creditos == 0 → no se cobra · se crea reserva 'pending'
        de 0 créditos · útil para acciones LOW gratuitas.

    Returns:
        dict con la reserva (id, accion_id, telefono, creditos,
        estado, transaccion_credito_id, creado, actualizado).
    """
    from agent.memory import async_session, SaldoCreditos
    from agent.automation.models import ReservaCreditoAutomation
    from agent.automation.audit import registrar_evento
    from agent.billing import cobrar, SaldoInsuficienteError, obtener_saldo

    if creditos < 0:
        raise ValueError("creditos debe ser >= 0")

    # 1. Buscar reserva existente
    async with async_session() as session:
        existing = (await session.execute(
            select(ReservaCreditoAutomation).where(
                ReservaCreditoAutomation.accion_id == accion_id
            )
        )).scalar_one_or_none()

        if existing is not None and existing.estado in ("pending", "confirmed"):
            logger.info(
                f"[CREDITS] reserva existente accion_id={accion_id} "
                f"estado={existing.estado} · no se cobra de nuevo"
            )
            return _to_dict(existing)

    # 2. Cobro real (si creditos > 0). Si falla, registramos failed.
    if creditos == 0:
        # Caso LOW gratuita · solo registrar reserva sin cobrar
        return await _persistir_reserva_nueva(
            accion_id=accion_id, telefono=telefono, creditos=0,
            razon=razon, estado="pending", transaccion_credito_id=None,
        )

    try:
        await cobrar(
            telefono,
            creditos,
            razon=f"reserva acción #{accion_id}: {razon[:80]}",
            asset_id=None,
            job_id=accion_id,
        )
    except SaldoInsuficienteError as e:
        # Registrar fila 'failed' + audit · no descontar.
        saldo_actual = e.saldo
        await _persistir_reserva_nueva(
            accion_id=accion_id, telefono=telefono, creditos=creditos,
            razon=razon, estado="failed", transaccion_credito_id=None,
            sustituir_si_existe=True,
        )
        await registrar_evento(
            evento="credits_reservation_failed",
            telefono=telefono,
            accion_id=accion_id,
            payload={
                "creditos_requeridos": creditos,
                "saldo_actual": saldo_actual,
                "motivo": "saldo_insuficiente",
            },
        )
        await registrar_evento(
            evento="action_blocked_insufficient_credits",
            telefono=telefono,
            accion_id=accion_id,
            payload={
                "creditos_requeridos": creditos,
                "saldo_actual": saldo_actual,
            },
        )
        raise CreditosInsuficientesError(
            saldo=saldo_actual, requerido=creditos
        ) from None

    # 3. Cobro OK · crear/actualizar reserva en pending
    saldo_actual = await obtener_saldo(telefono)
    reserva_dict = await _persistir_reserva_nueva(
        accion_id=accion_id, telefono=telefono, creditos=creditos,
        razon=razon, estado="pending", transaccion_credito_id=None,
        sustituir_si_existe=True,
    )
    await registrar_evento(
        evento="credits_reserved",
        telefono=telefono,
        accion_id=accion_id,
        payload={
            "creditos": creditos,
            "saldo_post_reserva": saldo_actual,
        },
    )
    return reserva_dict


async def confirmar(accion_id: int) -> dict[str, Any] | None:
    """Confirma una reserva 'pending' · estado→'confirmed'.

    No-op si la reserva ya está confirmed/released/failed o no existe.
    Los créditos ya se descontaron al reservar · esto solo marca que
    el descuento queda firme.
    """
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
        # Releer datos antes del update porque ORM auto-refresca
        creditos = int(row.creditos)
        telefono = row.telefono
        razon_db = row.razon

    # Acreditar fuera de la sesión actual · acreditar() abre la suya
    if creditos > 0:
        await acreditar(
            telefono,
            creditos,
            razon=f"reembolso reserva acción #{accion_id}: {razon[:60]}",
        )

    # Marcar como liberada
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


# ── Helpers internos ──────────────────────────────────────────────────────


async def _persistir_reserva_nueva(
    *,
    accion_id: int,
    telefono: str,
    creditos: int,
    razon: str,
    estado: str,
    transaccion_credito_id: int | None,
    sustituir_si_existe: bool = False,
) -> dict[str, Any]:
    """Crea o actualiza la fila de reserva · respeta UNIQUE(accion_id)."""
    from agent.memory import async_session
    from agent.automation.models import ReservaCreditoAutomation

    async with async_session() as session:
        existing = (await session.execute(
            select(ReservaCreditoAutomation).where(
                ReservaCreditoAutomation.accion_id == accion_id
            )
        )).scalar_one_or_none()
        if existing is not None and sustituir_si_existe:
            existing.creditos = creditos
            existing.estado = estado
            existing.razon = razon[:1000]
            existing.transaccion_credito_id = transaccion_credito_id
            existing.actualizado = datetime.utcnow()
            await session.commit()
            await session.refresh(existing)
            return _to_dict(existing)
        if existing is not None:
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
