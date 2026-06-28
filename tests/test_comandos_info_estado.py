# tests/test_comandos_info_estado.py — Cobertura de ramas no cubiertas de
# `dona estado` y `dona ayuda`.

"""
El test_comandos_info.py original cubre la detección y el render de texto, pero
deja sin ejercer varias ramas de `agent/comandos_info.py`:

  - el conteo REAL de mensajes recientes (`_contar_mensajes_recientes`), que en
    aquellos tests siempre está mockeado;
  - los `except` best-effort de Google (ayuda y estado) cuando `obtener_google_auth`
    lanza;
  - el recorte "…y N más" cuando el scheduler tiene más de 12 jobs;
  - la rama de error del scheduler;
  - la línea de créditos cuando billing responde.

Estos tests fijan el COMPORTAMIENTO ACTUAL — no cambian producción. Para el conteo
de mensajes se usa una SQLite temporal con el patrón de recarga de módulos de
CLAUDE.md §5 (importlib.reload tras setear DATABASE_URL).
"""

import importlib
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agent.comandos_info as ci


# ── _contar_mensajes_recientes — camino real contra DB ──────────────────────

@pytest.fixture
async def memoria_temporal(tmp_path, monkeypatch):
    """Recarga agent.memory contra una SQLite temporal y crea el esquema.

    `_contar_mensajes_recientes` importa `Mensaje`/`async_session` en tiempo de
    llamada, así que tras recargar memory apunta a esta base.
    """
    db_path = tmp_path / "estado.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.memory
    import agent.business.models as _bm
    import agent.automation.models as _am
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    await agent.memory.inicializar_db()
    return agent.memory


@pytest.mark.asyncio
async def test_contar_mensajes_recientes_cuenta_solo_ventana_y_telefono(memoria_temporal):
    """Cuenta solo los mensajes del teléfono dado dentro de la ventana horaria."""
    memory = memoria_temporal
    tel = "5551234567"
    ahora = datetime.utcnow()
    reciente = ahora - timedelta(hours=1)
    viejo = ahora - timedelta(hours=48)

    async with memory.async_session() as session:
        session.add(memory.Mensaje(telefono=tel, role="user", content="hola", timestamp=reciente))
        session.add(memory.Mensaje(telefono=tel, role="assistant", content="hey", timestamp=reciente))
        # Fuera de la ventana de 24h → no cuenta.
        session.add(memory.Mensaje(telefono=tel, role="user", content="viejo", timestamp=viejo))
        # Otro teléfono → no cuenta.
        session.add(memory.Mensaje(telefono="5559999999", role="user", content="x", timestamp=reciente))
        await session.commit()

    n = await ci._contar_mensajes_recientes(tel, horas=24)
    assert n == 2


@pytest.mark.asyncio
async def test_contar_mensajes_recientes_sin_datos_devuelve_cero(memoria_temporal):
    """Sin mensajes para el teléfono, el conteo es 0 (no None)."""
    n = await ci._contar_mensajes_recientes("5550000000", horas=24)
    assert n == 0


@pytest.mark.asyncio
async def test_contar_mensajes_recientes_best_effort_ante_error(monkeypatch):
    """Si la consulta falla (p. ej. tabla ausente), devuelve 0 sin propagar."""
    import agent.memory

    def _session_rota(*args, **kwargs):
        raise RuntimeError("DB caída")

    monkeypatch.setattr(agent.memory, "async_session", _session_rota)
    n = await ci._contar_mensajes_recientes("5551234567", horas=24)
    assert n == 0


# ── Ayuda — best-effort si Google falla ─────────────────────────────────────

@pytest.mark.asyncio
async def test_ayuda_resiliente_si_google_lanza():
    """Si `obtener_google_auth` lanza, ayuda degrada a 'sin Google' sin romper."""
    with patch("agent.memory.obtener_google_auth", new=AsyncMock(side_effect=RuntimeError("boom"))):
        texto = await ci.generar_texto_ayuda("5551")
    assert "Conectar Google" in texto
    assert "Calendario (Google)" not in texto


# ── Estado — ramas best-effort y de presentación ────────────────────────────

@pytest.mark.asyncio
async def test_estado_resiliente_si_google_lanza():
    """Si Google lanza, estado lo trata como no conectado sin propagar."""
    with patch("agent.memory.obtener_google_auth", new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)):
        texto = await ci.generar_texto_estado("5551")
    assert "no conectado" in texto


@pytest.mark.asyncio
async def test_estado_scheduler_recorta_a_doce_jobs():
    """Con más de 12 jobs, lista 12 y agrega el resumen '…y N más'."""
    jobs = []
    for i in range(15):
        j = MagicMock()
        j.id = f"job_{i}"
        j.trigger = "interval[0:05:00]"
        jobs.append(j)

    fake_scheduler = MagicMock()
    fake_scheduler.running = True
    fake_scheduler.get_jobs = MagicMock(return_value=jobs)

    fake_mod = types.ModuleType("agent.scheduler")
    fake_mod.scheduler = fake_scheduler
    orig = sys.modules.get("agent.scheduler")
    sys.modules["agent.scheduler"] = fake_mod
    try:
        with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
             patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)):
            texto = await ci.generar_texto_estado("5551")
    finally:
        if orig is not None:
            sys.modules["agent.scheduler"] = orig
        else:
            sys.modules.pop("agent.scheduler", None)

    assert "15 jobs activos" in texto
    assert "…y 3 más" in texto


@pytest.mark.asyncio
async def test_estado_scheduler_error_no_rompe():
    """Si obtener jobs del scheduler lanza, estado sigue y reporta actividad."""
    fake_scheduler = MagicMock()
    fake_scheduler.running = True
    fake_scheduler.get_jobs = MagicMock(side_effect=RuntimeError("scheduler roto"))

    fake_mod = types.ModuleType("agent.scheduler")
    fake_mod.scheduler = fake_scheduler
    orig = sys.modules.get("agent.scheduler")
    sys.modules["agent.scheduler"] = fake_mod
    try:
        with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
             patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)):
            texto = await ci.generar_texto_estado("5551")
    finally:
        if orig is not None:
            sys.modules["agent.scheduler"] = orig
        else:
            sys.modules.pop("agent.scheduler", None)

    # No se rompió: el render continúa hasta la actividad reciente.
    assert "Actividad 24h" in texto


@pytest.mark.asyncio
async def test_estado_muestra_creditos_si_billing_responde():
    """Si billing responde, estado agrega la línea de créditos disponibles."""
    with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
         patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)), \
         patch("agent.billing.obtener_saldo", new=AsyncMock(return_value=42)):
        texto = await ci.generar_texto_estado("5551")
    assert "Créditos" in texto
    assert "42" in texto
