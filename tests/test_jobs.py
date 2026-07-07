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


class TestReaperRamasDeError:
    """Resiliencia del reaper (ARQ-01): un fallo del reembolso o del marcado de
    error no puede perder crédito ni tumbar el arranque. El orden (reembolsar
    ANTES de marcar error) hace que cada rama sea segura de reintentar en el
    próximo arranque."""

    @pytest.mark.asyncio
    async def test_reembolso_falla_no_marca_error_ni_cuenta(self, db, monkeypatch):
        """Si `_reembolsar` revienta, el reaper NO marca error y NO cuenta el job:
        lo deja 'running' para reintentar el reembolso en el próximo arranque en
        vez de perder el crédito."""
        from datetime import datetime, timedelta

        import agent.jobs.queue as q
        from agent.jobs.queue import obtener_estado, reaper_jobs_huerfanos

        async def _reembolsar_boom(*a, **k):
            raise RuntimeError("acreditar caído")

        # El reaper importa _reembolsar de handlers_creativos con `from ... import`
        # DENTRO de la función, así que hay que parchear el símbolo en el módulo
        # de origen para que el import diferido tome el mock.
        import agent.jobs.handlers_creativos as hc
        monkeypatch.setattr(hc, "_reembolsar", _reembolsar_boom)

        viejo = datetime.utcnow() - timedelta(hours=1)
        job_id = await _insertar_job("running", actualizado=viejo, costo_creditos=3)

        recuperados = await reaper_jobs_huerfanos(corte=datetime.utcnow())

        # No se cuenta como recuperado y el job sigue 'running' (reintentable).
        assert recuperados == []
        estado = await obtener_estado(job_id)
        assert estado["estado"] == "running"
        # Nada acreditado: el reembolso reventó antes de tocar el saldo.
        saldo, txs = await _saldo_y_txs("5551")
        assert saldo == 0
        assert txs == []
        # sanity: el símbolo del módulo de queue no se ensució entre corridas.
        assert q.reaper_jobs_huerfanos is reaper_jobs_huerfanos

    @pytest.mark.asyncio
    async def test_marcar_error_falla_igual_cuenta_y_reembolsa(self, db, monkeypatch):
        """Si el reembolso ok pero `marcar_error` revienta, el crédito YA se
        aplicó (idempotente) y el job igual se cuenta como recuperado: el estado
        se corrige en el próximo arranque, el dinero no se pierde."""
        from datetime import datetime, timedelta

        import agent.jobs.queue as q
        from agent.jobs.queue import reaper_jobs_huerfanos

        async def _marcar_error_boom(*a, **k):
            raise RuntimeError("DB caída al marcar error")

        # marcar_error se llama sin cualificar dentro del reaper → se resuelve en
        # los globals del módulo queue en tiempo de ejecución.
        monkeypatch.setattr(q, "marcar_error", _marcar_error_boom)

        viejo = datetime.utcnow() - timedelta(hours=1)
        job_id = await _insertar_job("running", actualizado=viejo, costo_creditos=4)

        recuperados = await reaper_jobs_huerfanos(corte=datetime.utcnow())

        # Se cuenta como recuperado pese al fallo de marcar_error.
        assert recuperados == [job_id]
        # El reembolso SÍ se aplicó (va antes de marcar error).
        saldo, txs = await _saldo_y_txs("5551")
        assert saldo == 4
        assert any(t.delta == 4 and "Refund" in t.razon for t in txs)


class TestReaperArranqueMainWiring:
    """Wiring del reaper en el arranque de FastAPI (agent/main.py · lifespan):
    al levantar el proceso se registra el callback de observabilidad inproc y se
    corre el reaper, cuyo resultado se refleja en las métricas in-memory
    expuestas en /admin/metrics. Se ejerce el `lifespan` real neutralizando los
    colaboradores pesados (tablas enhanced, catálogo, scheduler) que no hacen al
    caso ARQ-01."""

    @pytest.mark.asyncio
    async def test_lifespan_corre_reaper_y_actualiza_metricas(self, db, monkeypatch):
        from datetime import datetime, timedelta

        import agent.main as main_mod

        # Neutralizar lo que no toca ARQ-01: la DB ya la inicializó el fixture
        # `db` (memoria recargada apunta al SQLite temporal), y no queremos
        # levantar tablas enhanced, catálogo ni el scheduler real.
        async def _noop_async(*a, **k):
            return None

        def _noop(*a, **k):
            return None

        monkeypatch.setattr(main_mod, "inicializar_db", _noop_async)
        monkeypatch.setattr(main_mod, "iniciar_scheduler", _noop)
        monkeypatch.setattr(main_mod, "detener_scheduler", _noop)
        import enhanced.catalog as _cat
        import enhanced.models as _mdl
        monkeypatch.setattr(_mdl, "inicializar_tablas_enhanced", _noop_async)
        monkeypatch.setattr(_cat, "sembrar_catalogo", _noop_async)

        # Partir de métricas limpias para aislar el conteo de este test.
        base_huerfanos = main_mod.metricas.jobs_huerfanos_recuperados
        base_inproc = main_mod.metricas.jobs_inproc_fallback

        # Sembrar un huérfano viejo: 'running' de un proceso muerto, con costo.
        viejo = datetime.utcnow() - timedelta(hours=1)
        job_id = await _insertar_job("running", actualizado=viejo, costo_creditos=5)

        # Ejercer el lifespan real (entrar = arranque, salir = shutdown).
        async with main_mod.lifespan(main_mod.app):
            # Dentro del contexto ya corrió el bloque ARQ-01.
            # 1) El reaper recuperó el huérfano y lo contabilizó en métricas.
            assert main_mod.metricas.jobs_huerfanos_recuperados == base_huerfanos + 1
            estado = await db.obtener_estado(job_id)
            assert estado["estado"] == "error"
            saldo, _ = await _saldo_y_txs("5551")
            assert saldo == 5  # reembolsado

            # 2) El callback de observabilidad inproc quedó registrado y apunta a
            #    la métrica: dispararlo desde la cola incrementa el contador.
            import agent.jobs.queue as q
            q._on_inproc_fallback()  # simula una activación del fallback inproc
            assert main_mod.metricas.jobs_inproc_fallback == base_inproc + 1

            # 3) Ambos contadores se exponen en el snapshot de /admin/metrics.
            snap = main_mod.metricas.snapshot()
            assert snap["jobs_huerfanos_recuperados"] == base_huerfanos + 1
            assert snap["jobs_inproc_fallback"] == base_inproc + 1

    @pytest.mark.asyncio
    async def test_registrar_jobs_huerfanos_ignora_cero_y_negativos(self, db):
        """`registrar_jobs_huerfanos` es un no-op si el reaper no recuperó nada
        (arranque limpio: n=0). Blinda la métrica de sumas espurias."""
        import agent.main as main_mod

        base = main_mod.metricas.jobs_huerfanos_recuperados
        main_mod.metricas.registrar_jobs_huerfanos(0)
        main_mod.metricas.registrar_jobs_huerfanos(-3)
        assert main_mod.metricas.jobs_huerfanos_recuperados == base
        main_mod.metricas.registrar_jobs_huerfanos(2)
        assert main_mod.metricas.jobs_huerfanos_recuperados == base + 2

    @pytest.mark.asyncio
    async def test_lifespan_no_aborta_si_el_reaper_revienta(self, db, monkeypatch):
        """El reaper es recuperación best-effort: si revienta al arrancar (DB no
        lista, etc.) NO debe tumbar el arranque de FastAPI. El bloque ARQ-01 lo
        traga y loguea, y el resto del lifespan sigue."""
        import agent.jobs.queue as q
        import agent.main as main_mod

        async def _noop_async(*a, **k):
            return None

        def _noop(*a, **k):
            return None

        monkeypatch.setattr(main_mod, "inicializar_db", _noop_async)
        monkeypatch.setattr(main_mod, "iniciar_scheduler", _noop)
        monkeypatch.setattr(main_mod, "detener_scheduler", _noop)
        import enhanced.catalog as _cat
        import enhanced.models as _mdl
        monkeypatch.setattr(_mdl, "inicializar_tablas_enhanced", _noop_async)
        monkeypatch.setattr(_cat, "sembrar_catalogo", _noop_async)

        async def _reaper_boom(*a, **k):
            raise RuntimeError("DB no lista al arrancar")

        # El lifespan importa reaper_jobs_huerfanos de queue con `from ... import`
        # dentro del try → parchear el símbolo en el módulo de origen.
        monkeypatch.setattr(q, "reaper_jobs_huerfanos", _reaper_boom)

        entro = False
        async with main_mod.lifespan(main_mod.app):
            # Si llegamos acá, el arranque NO abortó pese al reaper reventado.
            entro = True
        assert entro is True
