# tests/test_jobs.py — Tests del sistema de jobs asíncronos

"""
Cubre:
  - encolar + transición pending → running → done
  - handler desconocido registra error
  - listar_jobs_usuario ordenado por fecha desc
  - backend_activo según env
"""

import importlib
import asyncio
import pytest

import agent.memory
import agent.jobs


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("JOBS_BACKEND", "inproc")
    import agent.memory as _memory
    import agent.jobs.queue as _queue
    import agent.jobs.worker as _worker
    import agent.jobs as _jobs
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
        from agent.jobs.worker import registrar_handler, _dispatch

        @registrar_handler("test_handler_temp")
        async def _h(tel, params):
            return 42

        assert await _dispatch("test_handler_temp", "x", {}) == 42
