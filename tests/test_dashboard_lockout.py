# tests/test_dashboard_lockout.py — rank 4 · lockout persistente de login del dashboard

"""
Regresión del rank 4 del audit: el login del dashboard no tenía lockout, así que
admitía intentos de brute-force ilimitados (cada intento, además, pegaba a
Stripe). Estos tests fijan el comportamiento del lockout persistente:
bloqueo tras N fallos, reset al éxito, expiración del cooldown, aislamiento por
email y normalización del email.
"""

import importlib
from datetime import datetime, timedelta

import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "lockout.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", "test-bridge-secret")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.dashboard_lockout as _dl

    # Recargar tras setear DATABASE_URL · re-bindea los modelos al nuevo Base
    # (patrón del repo · ver CLAUDE.md sobre importlib.reload).
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_dl)
    await agent.memory.inicializar_db()
    return _dl


EMAIL = "user@test.com"


@pytest.mark.asyncio
async def test_email_limpio_no_esta_bloqueado(db):
    estado = await db.verificar_lockout(EMAIL)
    assert estado["bloqueado"] is False
    assert estado["retry_after_segundos"] == 0


@pytest.mark.asyncio
async def test_bloquea_tras_max_intentos(db):
    """Tras MAX_INTENTOS fallos el email queda bloqueado; antes, no."""
    for _ in range(db.MAX_INTENTOS - 1):
        r = await db.registrar_resultado(EMAIL, exito=False)
        assert r["bloqueado"] is False
    assert (await db.verificar_lockout(EMAIL))["bloqueado"] is False

    # El fallo número MAX_INTENTOS dispara el bloqueo.
    r = await db.registrar_resultado(EMAIL, exito=False)
    assert r["bloqueado"] is True
    assert r["retry_after_segundos"] == db.COOLDOWN_SEGUNDOS

    estado = await db.verificar_lockout(EMAIL)
    assert estado["bloqueado"] is True
    assert estado["retry_after_segundos"] > 0


@pytest.mark.asyncio
async def test_exito_resetea_contador(db):
    """Un login exitoso resetea el contador de fallos."""
    for _ in range(db.MAX_INTENTOS - 1):
        await db.registrar_resultado(EMAIL, exito=False)
    await db.registrar_resultado(EMAIL, exito=True)  # reset

    # Tras el reset, un fallo más NO debe bloquear (contador parte de cero).
    r = await db.registrar_resultado(EMAIL, exito=False)
    assert r["bloqueado"] is False
    assert (await db.verificar_lockout(EMAIL))["bloqueado"] is False


@pytest.mark.asyncio
async def test_bloqueo_expira_tras_cooldown(db):
    """Pasado el cooldown, el email deja de estar bloqueado."""
    for _ in range(db.MAX_INTENTOS):
        await db.registrar_resultado(EMAIL, exito=False)
    assert (await db.verificar_lockout(EMAIL))["bloqueado"] is True

    # Simular que el cooldown ya pasó moviendo bloqueado_hasta al pasado.
    eh = db._hash_email(EMAIL)
    async with agent.memory.async_session() as s:
        row = await s.get(db.DashboardLoginIntento, eh)
        row.bloqueado_hasta = datetime.utcnow() - timedelta(seconds=1)
        await s.commit()

    assert (await db.verificar_lockout(EMAIL))["bloqueado"] is False


@pytest.mark.asyncio
async def test_emails_independientes(db):
    """El lockout de un email no afecta a otro."""
    for _ in range(db.MAX_INTENTOS):
        await db.registrar_resultado("a@test.com", exito=False)
    assert (await db.verificar_lockout("a@test.com"))["bloqueado"] is True
    assert (await db.verificar_lockout("b@test.com"))["bloqueado"] is False


@pytest.mark.asyncio
async def test_email_se_normaliza(db):
    """Casing y espacios no generan filas distintas (misma cuenta)."""
    for _ in range(db.MAX_INTENTOS):
        await db.registrar_resultado("User@Test.com", exito=False)
    # Mismo email con otro casing/espacios → mismo bloqueo.
    assert (await db.verificar_lockout("  user@test.com "))["bloqueado"] is True
