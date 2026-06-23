# tests/test_dinero_atomico.py — Fase 1 · 3.x · atomicidad de dinero

"""
3.1 — acreditar() deduplicaba por SELECT-then-INSERT sobre stripe_session_id
(racy, sin UNIQUE): dos entregas concurrentes del mismo evento Stripe
doble-acreditaban. Ahora el cerrojo es un INSERT en idempotencia_credito (PK) en
la MISMA transacción → exactamente-una-vez, incluso concurrente.

3.3 — liberar() leía 'pending' y reembolsaba sin atomicidad → doble reembolso
concurrente. Ahora el reembolso usa idempotency_key=refund:{accion_id} (una sola
acreditación) y el flip de estado es condicional.

Verificado adversarialmente (workflow verify-money-atomicity): se descartó el
retrofit de UNIQUE sobre transacciones_credito (campo minado: duplicados previos
hacían fallar el índice y _migrar_columnas se tragaba el error) a favor de la
tabla de idempotencia nueva.
"""

import asyncio
import importlib
from datetime import datetime

import pytest

TEL = "15551230000"


@pytest.fixture
async def mem(tmp_path, monkeypatch):
    db = tmp_path / "dinero.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db}")

    import agent.memory
    import agent.business.models as _bm
    import agent.automation.models as _am
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    await agent.memory.inicializar_db()
    return agent.memory


# ── 3.1 · acreditar idempotente y atómico ──────────────────────────────────


async def test_acreditar_secuencial_idempotente(mem):
    import agent.billing as billing

    s1 = await billing.acreditar(TEL, 100, "compra", stripe_session_id="cs_1")
    s2 = await billing.acreditar(TEL, 100, "compra", stripe_session_id="cs_1")  # reentrega
    assert s1 == 100
    assert s2 == 100  # NO re-acredita
    assert await billing.obtener_saldo(TEL) == 100


async def test_acreditar_concurrente_no_duplica(mem):
    """5 entregas concurrentes del mismo stripe_session_id → una sola acreditación."""
    import agent.billing as billing

    await asyncio.gather(*[
        billing.acreditar(TEL, 50, "compra", stripe_session_id="cs_race")
        for _ in range(5)
    ])
    assert await billing.obtener_saldo(TEL) == 50


async def test_acreditar_claves_distintas_suman(mem):
    import agent.billing as billing

    await billing.acreditar(TEL, 30, "a", stripe_session_id="cs_a")
    await billing.acreditar(TEL, 30, "b", stripe_session_id="cs_b")
    assert await billing.obtener_saldo(TEL) == 60


async def test_acreditar_compat_idempotencia_legacy(mem):
    """Migración segura: un evento acreditado con la idempotencia VIEJA (existe
    en transacciones_credito.stripe_session_id pero NO en idempotencia_credito,
    p.ej. procesado antes del deploy) NO se re-acredita al reentregarse."""
    import agent.billing as billing
    from agent.memory import SaldoCreditos, TransaccionCredito

    async with mem.async_session() as s:
        s.add(SaldoCreditos(
            telefono=TEL, saldo=200, total_comprado=200,
            total_consumido=0, actualizado=datetime.utcnow(),
        ))
        s.add(TransaccionCredito(
            telefono=TEL, delta=200, razon="compra pre-deploy",
            stripe_session_id="cs_old", saldo_resultante=200,
            creado=datetime.utcnow(),
        ))
        await s.commit()

    saldo = await billing.acreditar(TEL, 200, "compra", stripe_session_id="cs_old")
    assert saldo == 200  # no re-acredita (fallback a la idempotencia legacy)
    assert await billing.obtener_saldo(TEL) == 200


async def test_acreditar_sin_clave_no_dedupe(mem):
    """Sin clave (regalo/bonus), cada llamada es un crédito legítimo distinto."""
    import agent.billing as billing

    await billing.acreditar(TEL, 10, "bonus")
    await billing.acreditar(TEL, 10, "bonus")
    assert await billing.obtener_saldo(TEL) == 20


async def test_acreditar_idempotency_key_explicito(mem):
    """El idempotency_key explícito (sin stripe_session_id) también deduplica,
    y NO infla total_comprado (no es una compra)."""
    import agent.billing as billing

    await billing.acreditar(TEL, 25, "reembolso", idempotency_key="refund:9")
    await billing.acreditar(TEL, 25, "reembolso", idempotency_key="refund:9")
    assert await billing.obtener_saldo(TEL) == 25


# ── 3.3 · liberar reembolsa exactamente una vez ────────────────────────────


async def _crear_reserva_pending(mem, *, accion_id: int, creditos: int):
    from agent.automation.models import ReservaCreditoAutomation

    async with mem.async_session() as s:
        s.add(ReservaCreditoAutomation(
            accion_id=accion_id,
            telefono=TEL,
            creditos=creditos,
            estado="pending",
            razon="test",
            transaccion_credito_id=None,
            creado=datetime.utcnow(),
            actualizado=datetime.utcnow(),
        ))
        await s.commit()


async def test_liberar_concurrente_un_solo_reembolso(mem):
    import agent.automation.credits as credits
    import agent.billing as billing

    await _crear_reserva_pending(mem, accion_id=777, creditos=40)
    saldo_antes = await billing.obtener_saldo(TEL)

    await asyncio.gather(
        credits.liberar(777, razon="ejecución fallida"),
        credits.liberar(777, razon="ejecución fallida"),
    )

    assert await billing.obtener_saldo(TEL) == saldo_antes + 40  # UNA sola vez
    r = await credits.obtener_reserva(777)
    assert r["estado"] == "released"


async def test_liberar_repetido_no_re_reembolsa(mem):
    import agent.automation.credits as credits
    import agent.billing as billing

    await _crear_reserva_pending(mem, accion_id=888, creditos=15)
    await credits.liberar(888)
    saldo = await billing.obtener_saldo(TEL)
    await credits.liberar(888)  # ya 'released' → no-op
    assert await billing.obtener_saldo(TEL) == saldo


async def test_liberar_inexistente_es_noop(mem):
    import agent.automation.credits as credits

    assert await credits.liberar(999999) is None
