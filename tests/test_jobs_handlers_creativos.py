# tests/test_jobs_handlers_creativos.py — Idempotencia del reembolso de jobs

"""
Cubre BILL-01 (Fase 0): `_reembolsar` en agent/jobs/handlers_creativos.py
debe pasar una `idempotency_key` determinística basada en el job a
`acreditar()`, así un doble reembolso del MISMO job (ej. arq reintentando un
job tras un shutdown que ya alcanzó a reembolsar) no duplica créditos.

Escenario real: el worker es matado (SIGTERM/redeploy) DESPUÉS de que
`_reembolsar` ya corrió una vez pero ANTES de que el job se marque
'error'/'done' — arq reintenta (retry_jobs=True, max_tries=5 default) y el
handler vuelve a fallar, llamando `_reembolsar` de nuevo con el mismo job_id.
Sin idempotency_key, el segundo reembolso duplicaría los créditos.
"""

import importlib

import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """DB SQLite aislada por test."""
    db_path = tmp_path / "handlers_creativos.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    import agent.billing as billing
    importlib.reload(billing)
    import agent.jobs.handlers_creativos as handlers
    importlib.reload(handlers)
    await agent.memory.inicializar_db()
    return billing, handlers


class TestReembolsoIdempotentePorJob:
    @pytest.mark.asyncio
    async def test_doble_reembolso_mismo_job_acredita_una_sola_vez(self, db):
        billing, handlers = db
        telefono = "5559990001"
        await billing.acreditar(telefono, 100, "seed", stripe_session_id="seed_1")
        saldo_pre = await billing.obtener_saldo(telefono)  # 100

        # Simula: el worker reembolsa por un fallo del provider (job_id=42).
        saldo_1 = await handlers._reembolsar(
            telefono, 10, "provider falló", scope="gen_imagen", job_id=42,
        )
        assert saldo_1 == saldo_pre + 10

        # Simula el escenario BILL-01: arq reintenta el MISMO job (mismo
        # job_id=42) tras un shutdown que ya había reembolsado — el handler
        # vuelve a fallar y llama _reembolsar de nuevo.
        saldo_2 = await handlers._reembolsar(
            telefono, 10, "provider falló", scope="gen_imagen", job_id=42,
        )

        # Sólo se acreditó UNA vez: el segundo reembolso es no-op idempotente.
        assert saldo_2 == saldo_1
        assert await billing.obtener_saldo(telefono) == saldo_pre + 10

    @pytest.mark.asyncio
    async def test_reembolsos_de_jobs_distintos_acreditan_ambos(self, db):
        billing, handlers = db
        telefono = "5559990002"
        await billing.acreditar(telefono, 100, "seed", stripe_session_id="seed_2")
        saldo_pre = await billing.obtener_saldo(telefono)

        await handlers._reembolsar(telefono, 10, "provider falló", job_id=1)
        await handlers._reembolsar(telefono, 15, "fallo al guardar", job_id=2)

        # Jobs distintos → idempotency_key distinta → ambos reembolsos aplican.
        assert await billing.obtener_saldo(telefono) == saldo_pre + 25

    @pytest.mark.asyncio
    async def test_sin_job_id_no_hay_dedup_compat_legacy(self, db):
        """Compat: llamadas sin job_id (legacy/tests) no ganan dedup — mismo
        comportamiento que antes de BILL-01. No debe romper nada existente."""
        billing, handlers = db
        telefono = "5559990003"
        await billing.acreditar(telefono, 100, "seed", stripe_session_id="seed_3")
        saldo_pre = await billing.obtener_saldo(telefono)

        await handlers._reembolsar(telefono, 10, "provider falló")
        await handlers._reembolsar(telefono, 10, "provider falló")

        # Sin idempotency_key, cada llamada es un acreditar() independiente.
        assert await billing.obtener_saldo(telefono) == saldo_pre + 20

    @pytest.mark.asyncio
    async def test_creditos_cero_no_reembolsa(self, db):
        billing, handlers = db
        telefono = "5559990004"
        resultado = await handlers._reembolsar(telefono, 0, "sin costo", job_id=99)
        assert resultado is None
