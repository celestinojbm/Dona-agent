# tests/test_automation_scheduler.py — T2.1.E

"""
Tests del scheduler de mantenimiento de automation:
  - Default OFF: AUTOMATION_SCHEDULER_ENABLED no fijado → deshabilitado
  - Intervalo configurable + clamps
  - tick_reconciliacion_reservas llama a reconciliar_reservas con los
    parámetros de env vars
  - Excepción del tick no propaga · el siguiente tick puede correr
  - Lock anti-concurrencia: si un tick está corriendo, el siguiente se
    salta y se contabiliza
  - registrar_automation_jobs: no-op si deshabilitado · registra job si
    habilitado · nunca propaga excepción
"""

from __future__ import annotations

import asyncio
import importlib
import pytest

import agent.memory


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """SQLite aislada · módulos de automation recargados con env limpio."""
    db_path = tmp_path / "sched.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    # Asegurarse de que cada test arranque sin env del scheduler heredado.
    monkeypatch.delenv("AUTOMATION_SCHEDULER_ENABLED", raising=False)
    monkeypatch.delenv("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("AUTOMATION_SCHEDULER_RECONCILE_EDAD_SEGUNDOS", raising=False)
    monkeypatch.delenv("AUTOMATION_SCHEDULER_RECONCILE_LIMIT", raising=False)

    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.credits as _cr
    import agent.automation.scheduler as _sched
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_cr)
    importlib.reload(_sched)
    await agent.memory.inicializar_db()
    # Resetear contadores del singleton in-memory
    _sched._estado.update({
        "habilitado": False,
        "intervalo_segundos": 0,
        "max_edad_segundos": 0,
        "limit": 0,
        "ultima_corrida_inicio": None,
        "ultima_corrida_fin": None,
        "ultimo_resultado": None,
        "corridas_totales": 0,
        "corridas_saltadas_por_lock": 0,
        "corridas_fallidas": 0,
    })
    return _sched, _cr


# ── 1. Configuración por env vars ────────────────────────────────────


class TestEnvConfig:
    @pytest.mark.asyncio
    async def test_default_deshabilitado(self, db):
        sched, _ = db
        assert sched.scheduler_habilitado() is False

    @pytest.mark.asyncio
    async def test_habilitado_si_env_truthy(self, db, monkeypatch):
        sched, _ = db
        for v in ("true", "1", "yes", "on", "TRUE", "On"):
            monkeypatch.setenv("AUTOMATION_SCHEDULER_ENABLED", v)
            assert sched.scheduler_habilitado() is True

    @pytest.mark.asyncio
    async def test_deshabilitado_si_env_falsy(self, db, monkeypatch):
        sched, _ = db
        for v in ("false", "0", "no", "off", ""):
            monkeypatch.setenv("AUTOMATION_SCHEDULER_ENABLED", v)
            assert sched.scheduler_habilitado() is False

    @pytest.mark.asyncio
    async def test_intervalo_default_y_clamp(self, db, monkeypatch):
        sched, _ = db
        # Default
        assert sched.intervalo_segundos() == 300
        # Clamp inferior
        monkeypatch.setenv("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", "5")
        assert sched.intervalo_segundos() == 30
        # Clamp superior
        monkeypatch.setenv("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", "999999")
        assert sched.intervalo_segundos() == 3600
        # Valor válido
        monkeypatch.setenv("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", "600")
        assert sched.intervalo_segundos() == 600
        # Valor inválido → fallback default
        monkeypatch.setenv("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", "abc")
        assert sched.intervalo_segundos() == 300

    @pytest.mark.asyncio
    async def test_edad_y_limit_clamps(self, db, monkeypatch):
        sched, _ = db
        assert sched.edad_min_segundos() == 120
        assert sched.limit_corrida() == 500
        monkeypatch.setenv("AUTOMATION_SCHEDULER_RECONCILE_EDAD_SEGUNDOS", "5")
        assert sched.edad_min_segundos() == 30  # min 30
        monkeypatch.setenv("AUTOMATION_SCHEDULER_RECONCILE_LIMIT", "0")
        assert sched.limit_corrida() == 1  # min 1
        monkeypatch.setenv("AUTOMATION_SCHEDULER_RECONCILE_LIMIT", "99999")
        assert sched.limit_corrida() == 5000


# ── 2. Tick · llama reconciliar_reservas ─────────────────────────────


class TestTickLlamaReconciliar:
    @pytest.mark.asyncio
    async def test_tick_pasa_parametros_de_env(self, db, monkeypatch):
        sched, cr = db
        monkeypatch.setenv("AUTOMATION_SCHEDULER_RECONCILE_EDAD_SEGUNDOS", "240")
        monkeypatch.setenv("AUTOMATION_SCHEDULER_RECONCILE_LIMIT", "33")

        capturado: dict = {}

        async def fake_reconciliar(**kwargs):
            capturado.update(kwargs)
            return {"dry_run": False, "promoted": 0, "marked_failed": 0,
                    "intactas": 0, "total_preparing_inicial": 0}

        monkeypatch.setattr(cr, "reconciliar_reservas", fake_reconciliar)

        r = await sched.tick_reconciliacion_reservas()
        assert r["status"] == "ok"
        assert capturado["max_edad_segundos"] == 240
        assert capturado["limit"] == 33
        assert capturado["dry_run"] is False

    @pytest.mark.asyncio
    async def test_tick_actualiza_estado(self, db, monkeypatch):
        sched, cr = db

        async def fake(**kwargs):
            return {"dry_run": False, "promoted": 2, "marked_failed": 1,
                    "intactas": 3, "total_preparing_inicial": 6}

        monkeypatch.setattr(cr, "reconciliar_reservas", fake)
        await sched.tick_reconciliacion_reservas()
        estado = sched.obtener_estado()
        assert estado["corridas_totales"] == 1
        assert estado["ultimo_resultado"]["promoted"] == 2
        assert estado["ultima_corrida_inicio"] is not None
        assert estado["ultima_corrida_fin"] is not None


# ── 3. Excepción del tick no propaga ─────────────────────────────────


class TestTickManejoDeExcepcion:
    @pytest.mark.asyncio
    async def test_excepcion_no_propaga_y_cuenta_fallidas(self, db, monkeypatch):
        sched, cr = db

        async def explota(**kwargs):
            raise RuntimeError("DB caída")

        monkeypatch.setattr(cr, "reconciliar_reservas", explota)

        # No debe propagar
        r = await sched.tick_reconciliacion_reservas()
        assert r["status"] == "error"
        assert r["error"] == "RuntimeError"
        estado = sched.obtener_estado()
        assert estado["corridas_fallidas"] == 1

    @pytest.mark.asyncio
    async def test_tick_siguiente_corre_tras_fallo(self, db, monkeypatch):
        sched, cr = db

        contador = {"n": 0}

        async def alternante(**kwargs):
            contador["n"] += 1
            if contador["n"] == 1:
                raise RuntimeError("primer intento falla")
            return {"dry_run": False, "promoted": 0, "marked_failed": 0,
                    "intactas": 0, "total_preparing_inicial": 0}

        monkeypatch.setattr(cr, "reconciliar_reservas", alternante)

        r1 = await sched.tick_reconciliacion_reservas()
        r2 = await sched.tick_reconciliacion_reservas()
        assert r1["status"] == "error"
        assert r2["status"] == "ok"
        estado = sched.obtener_estado()
        assert estado["corridas_totales"] == 1
        assert estado["corridas_fallidas"] == 1


# ── 4. Lock anti-concurrencia ────────────────────────────────────────


class TestLockNoConcurrencia:
    @pytest.mark.asyncio
    async def test_segundo_tick_concurrente_se_salta(self, db, monkeypatch):
        sched, cr = db

        evento_inicio = asyncio.Event()
        evento_finalizar = asyncio.Event()

        async def lento(**kwargs):
            evento_inicio.set()
            await evento_finalizar.wait()
            return {"dry_run": False, "promoted": 0, "marked_failed": 0,
                    "intactas": 0, "total_preparing_inicial": 0}

        monkeypatch.setattr(cr, "reconciliar_reservas", lento)

        # Lanzamos el primero en background
        task1 = asyncio.create_task(sched.tick_reconciliacion_reservas())
        await evento_inicio.wait()  # garantizamos que tomó el lock

        # Mientras el primero sigue corriendo, lanzamos el segundo
        r2 = await sched.tick_reconciliacion_reservas()
        assert r2["status"] == "skipped_lock"

        # Liberamos el primero
        evento_finalizar.set()
        r1 = await task1
        assert r1["status"] == "ok"

        estado = sched.obtener_estado()
        assert estado["corridas_totales"] == 1
        assert estado["corridas_saltadas_por_lock"] == 1


# ── 5. registrar_automation_jobs ─────────────────────────────────────


class _FakeScheduler:
    """Stand-in mínimo del AsyncIOScheduler · solo capta add_job."""

    def __init__(self):
        self.jobs: list[dict] = []

    def add_job(self, func, **kwargs):
        self.jobs.append({"func": func, **kwargs})


class TestRegistrarAutomationJobs:
    @pytest.mark.asyncio
    async def test_deshabilitado_no_agrega_job(self, db, monkeypatch):
        sched, _ = db
        monkeypatch.delenv("AUTOMATION_SCHEDULER_ENABLED", raising=False)
        fake = _FakeScheduler()
        ok = sched.registrar_automation_jobs(fake)
        assert ok is False
        assert fake.jobs == []
        assert sched.obtener_estado()["habilitado"] is False

    @pytest.mark.asyncio
    async def test_habilitado_agrega_job_con_max_instances_1(
        self, db, monkeypatch,
    ):
        sched, _ = db
        monkeypatch.setenv("AUTOMATION_SCHEDULER_ENABLED", "true")
        monkeypatch.setenv("AUTOMATION_SCHEDULER_INTERVAL_SECONDS", "600")
        fake = _FakeScheduler()
        ok = sched.registrar_automation_jobs(fake)
        assert ok is True
        assert len(fake.jobs) == 1
        job = fake.jobs[0]
        assert job["id"] == "automation_reconcile_reservas"
        assert job["trigger"] == "interval"
        assert job["seconds"] == 600
        assert job["max_instances"] == 1
        assert job["coalesce"] is True
        assert job["replace_existing"] is True
        # La función registrada es el tick · verifica que es callable
        assert callable(job["func"])
        estado = sched.obtener_estado()
        assert estado["habilitado"] is True
        assert estado["intervalo_segundos"] == 600

    @pytest.mark.asyncio
    async def test_no_propaga_excepcion_si_add_job_falla(
        self, db, monkeypatch,
    ):
        sched, _ = db
        monkeypatch.setenv("AUTOMATION_SCHEDULER_ENABLED", "true")

        class _Roto:
            def add_job(self, *a, **kw):
                raise RuntimeError("APS down")

        # No debe propagar
        ok = sched.registrar_automation_jobs(_Roto())
        assert ok is False
        # Estado refleja que NO quedó habilitado tras la falla
        assert sched.obtener_estado()["habilitado"] is False


# ── 6. Integración: reconciliar real desde el tick ───────────────────


class TestIntegracionTickRealReconciliar:
    """Caso end-to-end · el tick invoca reconciliar_reservas real
    contra SQLite. Confirma que el cableado entero funciona sin
    monkeypatch."""

    @pytest.mark.asyncio
    async def test_tick_con_db_vacia_retorna_ok(self, db):
        sched, _ = db
        r = await sched.tick_reconciliacion_reservas()
        assert r["status"] == "ok"
        # No hay reservas preparing · resultado vacío pero válido
        assert r["resultado"]["total_preparing_inicial"] == 0
        assert r["resultado"]["promoted"] == 0
        assert r["resultado"]["marked_failed"] == 0
