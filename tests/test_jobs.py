# tests/test_jobs.py — Tests del sistema de jobs asíncronos

"""
Cubre:
  - encolar + transición pending → running → done
  - handler desconocido registra error
  - listar_jobs_usuario ordenado por fecha desc
  - backend_activo según env
"""

import asyncio
import importlib

import pytest


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("JOBS_BACKEND", "inproc")
    import agent.jobs as _jobs
    import agent.jobs.queue as _queue
    import agent.jobs.worker as _worker
    import agent.memory as _memory
    importlib.reload(_memory)
    importlib.reload(_queue)
    importlib.reload(_worker)
    importlib.reload(_jobs)
    await _memory.inicializar_db()
    yield _jobs
    # Drenar las tasks inproc en vuelo ANTES de que el loop del test cierre:
    # una task viva al cierre revienta el teardown con "Event loop is closed"
    # (el flake histórico de test_listar_jobs_usuario).
    await _queue.esperar_tareas_inproc()


class TestBackendActivo:
    def test_inproc_cuando_no_hay_redis(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("JOBS_BACKEND", raising=False)
        from agent.jobs.queue import backend_activo
        assert backend_activo() == "inproc"

    def test_arq_cuando_hay_redis(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.delenv("JOBS_BACKEND", raising=False)
        from agent.jobs.queue import backend_activo
        assert backend_activo() == "arq"

    def test_override_explicito(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://x")
        monkeypatch.setenv("JOBS_BACKEND", "inproc")
        from agent.jobs.queue import backend_activo
        assert backend_activo() == "inproc"


class TestEncolarInproc:
    @pytest.mark.asyncio
    async def test_encolar_crea_fila_pending(self, db):
        job_id = await db.encolar("echo", "5551", {"msg": "hola"})
        # Dar chance al task en background de arrancar
        await asyncio.sleep(0.05)
        estado = await db.obtener_estado(job_id)
        assert estado is not None
        assert estado["tipo"] == "echo"
        assert estado["telefono"] == "5551"
        assert estado["params"] == {"msg": "hola"}

    @pytest.mark.asyncio
    async def test_job_llega_a_done(self, db):
        job_id = await db.encolar("echo", "5551", {})
        # esperar a que el handler inproc termine
        for _ in range(50):
            await asyncio.sleep(0.02)
            estado = await db.obtener_estado(job_id)
            if estado["estado"] == "done":
                break
        assert estado["estado"] == "done"
        assert estado["intentos"] == 1

    @pytest.mark.asyncio
    async def test_tipo_desconocido_marca_error(self, db):
        job_id = await db.encolar("tipo_inventado", "5551", {})
        for _ in range(50):
            await asyncio.sleep(0.02)
            estado = await db.obtener_estado(job_id)
            if estado["estado"] in ("done", "error"):
                break
        assert estado["estado"] == "error"
        assert "tipo_inventado" in estado["error_msg"]

    @pytest.mark.asyncio
    async def test_obtener_estado_inexistente(self, db):
        assert await db.obtener_estado(999_999) is None

    @pytest.mark.asyncio
    async def test_listar_jobs_usuario(self, db):
        import agent.jobs.queue as q
        j1 = await db.encolar("echo", "5551", {"i": 1})
        j2 = await db.encolar("echo", "5551", {"i": 2})
        await db.encolar("echo", "otro", {"i": 3})
        # Determinista: drenar las tasks en vez de dormir un tiempo arbitrario
        await q.esperar_tareas_inproc()
        mios = await db.listar_jobs_usuario("5551", limite=10)
        assert len(mios) == 2
        # orden desc por creado
        assert mios[0]["id"] == j2
        assert mios[1]["id"] == j1


class TestTareasInprocFuertes:
    """REGRESIÓN (flake "Event loop is closed" + bug real de producción):
    _encolar_inproc creaba la task SIN referencia fuerte — asyncio solo
    guarda referencias débiles, así que el GC podía recolectar un job a
    media ejecución (desaparecía sin done ni error). Además no había forma
    de drenar las tasks en vuelo, y una task viva al cerrar el loop del
    test reventaba el teardown."""

    @pytest.mark.asyncio
    async def test_tasks_trackeadas_y_drenables(self, db):
        import agent.jobs.queue as q
        ids = [await db.encolar("echo", "5551", {"i": i}) for i in range(3)]

        await q.esperar_tareas_inproc()

        # Tras drenar: todo terminal y el set limpio (done_callback descarta)
        for jid in ids:
            estado = await db.obtener_estado(jid)
            assert estado["estado"] in ("done", "error")
        assert all(t.done() for t in q._tareas_inproc)


class TestRegistroHandlers:
    def test_echo_esta_registrado(self):
        from agent.jobs.worker import handlers_registrados
        assert "echo" in handlers_registrados()

    @pytest.mark.asyncio
    async def test_decorator_registra(self, db):
        from agent.jobs.worker import _dispatch, registrar_handler

        @registrar_handler("test_handler_temp")
        async def _h(tel, params):
            return 42

        assert await _dispatch("test_handler_temp", "x", {}) == 42


# ── ARQ-01: reaper de jobs huérfanos + observabilidad del fallback inproc ────

async def _insertar_job(estado: str, actualizado, telefono="5551",
                        tipo="gen_imagen", costo_creditos=3):
    """Inserta una fila JobCreativo con estado y `actualizado` explícitos, para
    simular un job dejado por un proceso muerto (running viejo) o uno reciente."""
    import json as _json
    from datetime import datetime as _dt

    from agent.memory import JobCreativo, async_session
    async with async_session() as session:
        row = JobCreativo(
            telefono=telefono,
            tipo=tipo,
            estado=estado,
            params_json=_json.dumps({"costo_creditos": costo_creditos, "prompt": "x"}),
            backend="inproc",
            creado=_dt.utcnow(),
            actualizado=actualizado,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


async def _saldo_y_txs(telefono="5551"):
    """Retorna (saldo, filas_transacciones) del usuario."""
    from sqlalchemy import select

    from agent.memory import SaldoCreditos, TransaccionCredito, async_session
    async with async_session() as session:
        bal = (await session.execute(
            select(SaldoCreditos).where(SaldoCreditos.telefono == telefono)
        )).scalar_one_or_none()
        txs = (await session.execute(
            select(TransaccionCredito).where(TransaccionCredito.telefono == telefono)
        )).scalars().all()
        return (int(bal.saldo) if bal else 0, list(txs))


class TestReaperJobsHuerfanos:
    """El defecto ARQ-01: con backend inproc, un redeploy a media ejecución deja
    el job 'running' para siempre, sin reembolso. El reaper de arranque lo cierra
    como error y reembolsa. Detección: estado=='running' AND actualizado < corte
    (corte ≈ arranque del proceso). Un job del proceso actual NO se toca."""

    @pytest.mark.asyncio
    async def test_job_huerfano_se_marca_error_y_reembolsa(self, db):
        from datetime import datetime, timedelta

        from agent.jobs.queue import obtener_estado, reaper_jobs_huerfanos

        # Saldo inicial 0. Simulamos que confirmar_imagen cobró 3 créditos y
        # encoló; el proceso murió con el job en 'running' hace 1 hora.
        viejo = datetime.utcnow() - timedelta(hours=1)
        job_id = await _insertar_job("running", actualizado=viejo, costo_creditos=3)

        # corte = "ahora": el job viejo es huérfano.
        recuperados = await reaper_jobs_huerfanos(corte=datetime.utcnow())

        assert recuperados == [job_id]
        estado = await obtener_estado(job_id)
        assert estado["estado"] == "error"
        assert "huérfano" in estado["error_msg"]

        # Se acreditó el reembolso: saldo=3 y hay una TransaccionCredito +3.
        saldo, txs = await _saldo_y_txs("5551")
        assert saldo == 3
        assert any(t.delta == 3 and "Refund" in t.razon for t in txs)

    @pytest.mark.asyncio
    async def test_job_reciente_del_proceso_actual_no_se_toca(self, db):
        from datetime import datetime, timedelta

        from agent.jobs.queue import obtener_estado, reaper_jobs_huerfanos

        # Job legítimamente en curso: lo marcó ESTE proceso hace un instante
        # (actualizado > corte). El reaper NO debe tocarlo.
        corte = datetime.utcnow() - timedelta(minutes=5)
        reciente = datetime.utcnow()
        job_id = await _insertar_job("running", actualizado=reciente, costo_creditos=3)

        recuperados = await reaper_jobs_huerfanos(corte=corte)

        assert recuperados == []
        estado = await obtener_estado(job_id)
        assert estado["estado"] == "running"  # intacto
        saldo, txs = await _saldo_y_txs("5551")
        assert saldo == 0  # no reembolsó
        assert txs == []

    @pytest.mark.asyncio
    async def test_jobs_terminales_no_se_tocan(self, db):
        from datetime import datetime, timedelta

        from agent.jobs.queue import reaper_jobs_huerfanos

        viejo = datetime.utcnow() - timedelta(hours=2)
        # done y error viejos NO son huérfanos (ya terminaron).
        await _insertar_job("done", actualizado=viejo, costo_creditos=3)
        await _insertar_job("error", actualizado=viejo, costo_creditos=3)

        recuperados = await reaper_jobs_huerfanos(corte=datetime.utcnow())

        assert recuperados == []
        saldo, _ = await _saldo_y_txs("5551")
        assert saldo == 0

    @pytest.mark.asyncio
    async def test_reaper_es_idempotente_no_doble_reembolsa(self, db):
        """Dos instancias web arrancando a la vez (o un restart a media faena)
        corren el reaper dos veces. El reembolso idempotente por job evita
        doble-acreditar: el saldo debe ser 3, no 6."""
        from datetime import datetime, timedelta

        from agent.jobs.queue import reaper_jobs_huerfanos

        viejo = datetime.utcnow() - timedelta(hours=1)
        job_id = await _insertar_job("running", actualizado=viejo, costo_creditos=3)

        r1 = await reaper_jobs_huerfanos(corte=datetime.utcnow())
        # Segunda corrida: el job ya está en 'error', así que ni siquiera es
        # candidato. Aun forzando el mismo job, la clave idempotente lo cubre.
        r2 = await reaper_jobs_huerfanos(corte=datetime.utcnow())

        assert r1 == [job_id]
        assert r2 == []  # ya no está 'running'
        saldo, txs = await _saldo_y_txs("5551")
        assert saldo == 3  # un solo reembolso
        assert sum(1 for t in txs if t.delta == 3) == 1

    @pytest.mark.asyncio
    async def test_job_sin_costo_se_marca_error_sin_reembolso(self, db):
        from datetime import datetime, timedelta

        from agent.jobs.queue import obtener_estado, reaper_jobs_huerfanos

        viejo = datetime.utcnow() - timedelta(hours=1)
        job_id = await _insertar_job("running", actualizado=viejo, costo_creditos=0)

        recuperados = await reaper_jobs_huerfanos(corte=datetime.utcnow())

        assert recuperados == [job_id]
        estado = await obtener_estado(job_id)
        assert estado["estado"] == "error"
        saldo, txs = await _saldo_y_txs("5551")
        assert saldo == 0
        assert txs == []  # nada que reembolsar

    @pytest.mark.asyncio
    async def test_default_corte_es_ahora(self, db):
        """Sin `corte` explícito usa utcnow() — el caso real del arranque de
        FastAPI: cualquier 'running' preexistente es de un proceso muerto."""
        from datetime import datetime, timedelta

        from agent.jobs.queue import reaper_jobs_huerfanos

        viejo = datetime.utcnow() - timedelta(minutes=30)
        job_id = await _insertar_job("running", actualizado=viejo, costo_creditos=2)

        recuperados = await reaper_jobs_huerfanos()  # sin corte

        assert recuperados == [job_id]
        saldo, _ = await _saldo_y_txs("5551")
        assert saldo == 2


class TestObservabilidadInproc:
    """El fallback inproc era SILENCIOSO (ARQ-01). Ahora cuenta y notifica."""

    @pytest.mark.asyncio
    async def test_encolar_inproc_incrementa_contador_y_dispara_callback(self, db):
        import agent.jobs.queue as q

        base = q.inproc_fallback_total()
        disparos = {"n": 0}
        q.registrar_callback_inproc_fallback(lambda: disparos.__setitem__("n", disparos["n"] + 1))
        try:
            await db.encolar("echo", "5551", {})
            await q.esperar_tareas_inproc()
            assert q.inproc_fallback_total() == base + 1
            assert disparos["n"] == 1
        finally:
            q.registrar_callback_inproc_fallback(None)

    @pytest.mark.asyncio
    async def test_callback_que_revienta_no_rompe_encolar(self, db):
        import agent.jobs.queue as q

        def _boom():
            raise RuntimeError("métrica caída")

        q.registrar_callback_inproc_fallback(_boom)
        try:
            # No debe propagar: el fallo de la métrica no puede tumbar el encolado.
            job_id = await db.encolar("echo", "5551", {})
            await q.esperar_tareas_inproc()
            assert job_id > 0
        finally:
            q.registrar_callback_inproc_fallback(None)
