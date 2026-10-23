"""Reserva write-ahead de créditos (F1 · decisión de Celestino #6).

Flujo: RESERVAR al iniciar → COBRAR al completar (consumir) → LIBERAR si falla.
Reglas:
- `reservar` es idempotente por `accion_ref` (uso único): un retry no reserva dos
  veces.
- `consumir` y `liberar` son transiciones atómicas por estado (UPDATE
  condicional) → ni concurrencia ni retries ejecutan la transición dos veces.
- "No liberar si el proveedor pudo ejecutar": es responsabilidad del caller
  decidir entre consumir (sí ejecutó / cobro al completar) y liberar (falló sin
  posibilidad de haber ejecutado). Esta capa sólo garantiza que la transición
  ocurra una sola vez.

El débito real del saldo lo hace billing al completar (integración F1+F3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from agent.autonomia.models import ReservaCredito
from agent.memory import async_session

logger = logging.getLogger("dona")


@dataclass(frozen=True)
class ResultadoReserva:
    ok: bool
    estado: str
    razon: str = ""


async def reservar(
    *, telefono: str, accion_ref: str, creditos: int, idempotency_key: str = ""
) -> ResultadoReserva:
    """Crea una reserva (estado 'reservada'). Idempotente por accion_ref: si ya
    existe, devuelve su estado actual sin crear otra."""
    if creditos <= 0:
        return ResultadoReserva(False, "", "creditos_invalidos")
    r = ReservaCredito(
        telefono=telefono,
        accion_ref=accion_ref[:120],
        creditos=int(creditos),
        estado="reservada",
        idempotency_key=(idempotency_key or None),
        creado=datetime.utcnow(),
        actualizado=datetime.utcnow(),
    )
    async with async_session() as s:
        s.add(r)
        try:
            await s.commit()
            return ResultadoReserva(True, "reservada")
        except IntegrityError:
            await s.rollback()
            ya = (await s.execute(
                select(ReservaCredito).where(
                    ReservaCredito.accion_ref == accion_ref[:120]
                )
            )).scalar_one()
            return ResultadoReserva(True, ya.estado, "ya_reservada")


async def _transicion(
    accion_ref: str, telefono: str, destino: str
) -> ResultadoReserva:
    """Transición atómica desde 'reservada' → destino (consumida|liberada)."""
    async with async_session() as s:
        r = (await s.execute(
            select(ReservaCredito).where(
                ReservaCredito.accion_ref == accion_ref[:120]
            )
        )).scalar_one_or_none()
        if r is None:
            return ResultadoReserva(False, "", "inexistente")
        if r.telefono != telefono:
            return ResultadoReserva(False, r.estado, "ajena")
        if r.estado == destino:
            # Idempotente: ya estaba en el destino.
            return ResultadoReserva(True, destino, "ya_en_destino")
        res = await s.execute(
            update(ReservaCredito)
            .where(
                ReservaCredito.id == r.id,
                ReservaCredito.estado == "reservada",
            )
            .values(estado=destino, actualizado=datetime.utcnow())
        )
        await s.commit()
        if res.rowcount == 0:
            # Ya no estaba 'reservada' (otra transición ganó): no se repite.
            return ResultadoReserva(False, r.estado, f"no_reservada_estado_{r.estado}")
        return ResultadoReserva(True, destino)


async def consumir(*, telefono: str, accion_ref: str) -> ResultadoReserva:
    """Cobro al completar: marca la reserva como consumida (uso único)."""
    return await _transicion(accion_ref, telefono, "consumida")


async def liberar(*, telefono: str, accion_ref: str) -> ResultadoReserva:
    """Liberar si falló (sin posibilidad de ejecución): marca liberada."""
    return await _transicion(accion_ref, telefono, "liberada")
