"""Lógica del primer valor (F12).

- Seed de créditos de bienvenida idempotente (una sola vez por teléfono), vía
  `acreditar` con idempotency_key durable → dobles webhooks/recargas no duplican.
- TTFV = first_result_at − started_at.
- Camino por defecto: borrador de seguimiento (sin proveedor facturable), que se
  prefiere antes que un envío real a terceros.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from sqlalchemy import select, update

from agent.memory import async_session
from agent.primer_valor.models import (
    ETAPAS,
    RESULTADOS,
    EventoOnboarding,
    OnboardingPrimerValor,
)

logger = logging.getLogger("dona")

# Chips de acción del home (SÓLO lo implementado hoy). Decisión de Celestino #11:
# un BORRADOR útil del negocio primero (p. ej. "Armar seguimiento"), y la imagen
# se ofrece DESPUÉS → "Generar imagen" va al final.
CHIPS = (
    "Armar seguimiento",
    "Redactar correo",
    "Programar recordatorio",
    "Ver saldo",
    "Generar imagen",
)


def primer_valor_habilitado() -> bool:
    return os.getenv("DONA_FIRST_VALUE_ONBOARDING_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# Decisión de Celestino #12: créditos de bienvenida = 0 (desactivado por defecto).
# Decisión de Celestino #13: retención de telemetría de onboarding = 90 días.
RETENCION_EVENTOS_ONBOARDING_DIAS = 90


def creditos_bienvenida() -> int:
    """Cantidad de créditos de bienvenida (0 = desactivado; Celestino fijó 0)."""
    try:
        n = int(os.getenv("DONA_FIRST_VALUE_WELCOME_CREDITS", "0"))
    except ValueError:
        n = 0
    return max(n, 0)  # nunca negativo


async def purgar_eventos_onboarding(
    dias: int = RETENCION_EVENTOS_ONBOARDING_DIAS,
) -> int:
    """Borra eventos_onboarding más antiguos que `dias` (retención 90 días por
    defecto, decisión #13). Devuelve cuántas filas se borraron. No toca las
    métricas de primer valor (onboarding_primer_valor)."""
    from datetime import timedelta

    from sqlalchemy import delete

    corte = datetime.utcnow() - timedelta(days=max(int(dias), 1))
    async with async_session() as s:
        res = await s.execute(
            delete(EventoOnboarding).where(EventoOnboarding.creado < corte)
        )
        await s.commit()
        return int(res.rowcount or 0)


async def _fila(telefono: str) -> OnboardingPrimerValor | None:
    async with async_session() as s:
        return (await s.execute(
            select(OnboardingPrimerValor).where(
                OnboardingPrimerValor.telefono == telefono
            )
        )).scalar_one_or_none()


async def iniciar(telefono: str) -> None:
    """Marca started_at una sola vez (idempotente: no lo pisa si ya existe)."""
    async with async_session() as s:
        fila = (await s.execute(
            select(OnboardingPrimerValor).where(
                OnboardingPrimerValor.telefono == telefono
            )
        )).scalar_one_or_none()
        if fila is None:
            s.add(OnboardingPrimerValor(
                telefono=telefono,
                started_at=datetime.utcnow(),
                actualizado=datetime.utcnow(),
            ))
            await s.commit()


async def registrar_evento(telefono: str, etapa: str) -> None:
    if etapa not in ETAPAS:
        return
    async with async_session() as s:
        s.add(EventoOnboarding(telefono=telefono, etapa=etapa, creado=datetime.utcnow()))
        await s.commit()


async def registrar_primer_resultado(
    telefono: str, accion_ref: str, kind: str
) -> bool:
    """Fija el primer resultado una sola vez. Devuelve True si fue el primero
    (idempotente: un segundo resultado no lo pisa → no re-mide ni duplica)."""
    if kind not in RESULTADOS:
        kind = RESULTADOS[0]
    await iniciar(telefono)  # asegura started_at
    async with async_session() as s:
        # UPDATE condicional: sólo si aún no hay primer resultado.
        res = await s.execute(
            update(OnboardingPrimerValor)
            .where(
                OnboardingPrimerValor.telefono == telefono,
                OnboardingPrimerValor.first_result_at.is_(None),
            )
            .values(
                first_result_at=datetime.utcnow(),
                first_action_ref=accion_ref[:120],
                first_result_kind=kind,
                actualizado=datetime.utcnow(),
            )
        )
        await s.commit()
        return res.rowcount > 0


async def ttfv_segundos(telefono: str) -> float | None:
    """Time-to-first-value en segundos, o None si falta algún extremo."""
    fila = await _fila(telefono)
    if fila is None or fila.started_at is None or fila.first_result_at is None:
        return None
    return (fila.first_result_at - fila.started_at).total_seconds()


async def sembrar_creditos_bienvenida(telefono: str) -> int | None:
    """Siembra créditos de bienvenida UNA sola vez (idempotente por teléfono).
    Devuelve el saldo tras la siembra, o None si está desactivado (0)."""
    n = creditos_bienvenida()
    if n <= 0:
        return None
    from agent.billing import acreditar

    # idempotency_key durable → doble webhook/recarga no duplica el seed.
    return await acreditar(
        telefono, n, "bienvenida", idempotency_key=f"bienvenida:{telefono}"
    )


def generar_borrador_seguimiento(nombre: str = "", contexto: str = "") -> str:
    """Primer resultado por defecto: un borrador de seguimiento determinístico.
    NO llama a ningún proveedor facturable; es texto local, listo para editar.
    Prefiere el borrador antes que un envío real a terceros."""
    saludo = f"Hola {nombre}," if nombre else "Hola,"
    tema = contexto.strip() or "lo que conversamos"
    return (
        f"{saludo}\n\n"
        f"Te escribo para dar seguimiento a {tema}. "
        f"¿Te queda bien que avancemos esta semana? "
        f"Quedo atento a tu respuesta.\n\n"
        f"Un saludo."
    )
