# tests/test_app_first_ejecucion.py — J7.2/J7.3 · runner de agentes
#
# Tarea completa, encolado idempotente, reclamo único, aprobación y rechazo,
# herramienta no permitida, presupuesto ANTES de llamar, fallo del proveedor
# y reintento sin duplicar efectos, recuperación tras reinicio del worker,
# cancelación y aislamiento. Proveedores simulados: sin red.

import asyncio
import importlib
import sys
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'runner.db'}")
    import agent.memory

    importlib.reload(agent.memory)
    for nombre in (
        "agent.app_first.models",
        "agent.app_first.repositorio",
        "agent.app_first.proveedores",
        "agent.app_first.ejecucion",
    ):
        if nombre in sys.modules:
            importlib.reload(sys.modules[nombre])
        else:
            importlib.import_module(nombre)
    await agent.memory.inicializar_db()

    class App:
        repo = sys.modules["agent.app_first.repositorio"]
        run = sys.modules["agent.app_first.ejecucion"]
        prov = sys.modules["agent.app_first.proveedores"]
        m = sys.modules["agent.app_first.models"]
        memoria = agent.memory

        @staticmethod
        async def contar(modelo, *condiciones):
            async with agent.memory.async_session() as s:
                return await s.scalar(select(func.count()).select_from(modelo).where(*condiciones))

    return App


async def _workspace(app, email="ana@example.com", herramientas=(), presupuesto=10, modelo="simulado"):
    repo = app.repo
    uid = await repo.crear_usuario(email, "contraseña-larga-1")
    ws = await repo.crear_workspace(uid, "Empresa")
    ctx = await repo.resolver_contexto(uid, ws)
    area = await repo.crear_area(ctx, "Ventas")
    proyecto = await repo.crear_proyecto(ctx, area, "Lanzamiento", "Vender más", ["Propuesta lista"])
    ejecutor = await repo.crear_agente(ctx, "Ejecutor", "ejecutor", herramientas_permitidas=list(herramientas),
                                       presupuesto_max_unidades=presupuesto, modelo=modelo)
    responsable = await repo.crear_agente(ctx, "Responsable", "responsable", presupuesto_max_unidades=10)
    return dict(uid=uid, ws=ws, ctx=ctx, proyecto=proyecto, ejecutor=ejecutor, responsable=responsable)


async def _tarea(app, w, titulo="Redactar propuesta", descripcion=""):
    return await app.repo.crear_tarea(w["ctx"], w["proyecto"], titulo, descripcion, agente_id=w["ejecutor"])


class _Contador:
    """Proveedor que delega en el simulado y cuenta llamadas."""

    def __init__(self, base, fallar=False):
        self.nombre = "contador"
        self.base = base
        self.fallar = fallar
        self.llamadas = 0

    def costo_estimado(self, titulo, descripcion):
        return 1

    async def generar(self, **kw):
        self.llamadas += 1
        if self.fallar:
            raise self.base_error("caído")
        return await self.base.generar(**kw)

    async def revisar(self, **kw):
        return await self.base.revisar(**kw)


def _contador(app, fallar=False):
    c = _Contador(app.prov.ProveedorSimulado(), fallar)
    c.base_error = app.prov.ProveedorNoDisponible
    app.prov.registrar_proveedor("contador", c)
    return c


class TestFlujoCompleto:
    async def test_tarea_completa_con_evidencia_y_revision(self, app):
        w = await _workspace(app)
        t = await _tarea(app, w)
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        assert await app.run.ejecutar(ej) == "completada"

        tarea = await app.repo.obtener_tarea(w["ctx"], t)
        assert tarea["estado"] == "completada"
        ejecuciones = await app.run.listar_ejecuciones(w["ctx"], t)
        assert [(e["estado"], e["intento"], e["unidades_consumidas"]) for e in ejecuciones] == [("terminada", 1, 1)]
        evidencias = await app.run.listar_evidencias(w["ctx"], t)
        assert [e["tipo"] for e in evidencias] == ["texto", "registro"]
        assert evidencias[0]["contenido"].startswith("[Simulado]")
        assert await app.contar(app.m.AppConsumo, app.m.AppConsumo.simulado.is_(True)) == 1
        eventos = [a["evento"] for a in await app.repo.listar_actividad(w["ctx"], 100)]
        assert "ejecucion_encolada" in eventos and "ejecucion_terminada" in eventos

    async def test_encolar_es_idempotente(self, app):
        w = await _workspace(app)
        t = await _tarea(app, w)
        a = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        b = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        assert a == b
        assert await app.contar(app.m.AppEjecucion) == 1

    async def test_dos_workers_no_procesan_la_misma_ejecucion(self, app):
        w = await _workspace(app)
        contador = _contador(app)
        async with app.memoria.async_session() as s:
            agente = await s.get(app.m.AppAgente, w["ejecutor"])
            agente.modelo = "contador"
            await s.commit()
        t = await _tarea(app, w)
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        resultados = await asyncio.gather(app.run.ejecutar(ej), app.run.ejecutar(ej))
        assert sorted(resultados, key=lambda r: r is None) == ["completada", None]
        assert contador.llamadas == 1
        assert await app.contar(app.m.AppConsumo) == 1

    async def test_tarea_sin_agente_no_se_encola(self, app):
        w = await _workspace(app)
        t = await app.repo.crear_tarea(w["ctx"], w["proyecto"], "Sin agente")
        with pytest.raises(app.repo.ValorInvalido):
            await app.run.encolar_tarea(w["ctx"], t, despachar=False)


class TestAprobaciones:
    async def test_operacion_reservada_espera_aprobacion_y_luego_completa(self, app):
        w = await _workspace(app, herramientas=["publicar_resultado"])
        t = await _tarea(app, w, "Publicar la propuesta")
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        assert await app.run.ejecutar(ej) == "necesita_aprobacion"
        assert (await app.repo.obtener_tarea(w["ctx"], t))["estado"] == "necesita_aprobacion"
        pendientes = await app.run.listar_aprobaciones(w["ctx"])
        assert [(p["operacion"], p["riesgo"]) for p in pendientes] == [("publicar_resultado", "HIGH")]
        assert await app.contar(app.m.AppEfecto) == 0  # nada sin decisión humana

        assert await app.run.decidir_aprobacion(w["ctx"], pendientes[0]["id"], True, despachar=False) == "aprobada"
        assert await app.run.ejecutar(ej) == "completada"
        assert await app.contar(app.m.AppEfecto) == 1
        with pytest.raises(app.repo.Conflicto):  # no se decide dos veces
            await app.run.decidir_aprobacion(w["ctx"], pendientes[0]["id"], True, despachar=False)

    async def test_rechazo_bloquea_sin_efecto(self, app):
        w = await _workspace(app, herramientas=["publicar_resultado"])
        t = await _tarea(app, w, "Publicar la propuesta")
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        await app.run.ejecutar(ej)
        ap = (await app.run.listar_aprobaciones(w["ctx"]))[0]
        await app.run.decidir_aprobacion(w["ctx"], ap["id"], False, despachar=False)
        tarea = await app.repo.obtener_tarea(w["ctx"], t)
        assert (tarea["estado"], tarea["motivo_bloqueo"]) == ("bloqueada", "aprobacion_rechazada")
        assert await app.contar(app.m.AppEfecto) == 0
        assert await app.run.ejecutar(ej) is None  # cancelada: no se puede reclamar

    async def test_herramienta_no_permitida_bloquea_sin_pedir_aprobacion(self, app):
        w = await _workspace(app, herramientas=[])
        t = await _tarea(app, w, "Publicar la propuesta")
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        assert await app.run.ejecutar(ej) == "bloqueada"
        tarea = await app.repo.obtener_tarea(w["ctx"], t)
        assert tarea["motivo_bloqueo"] == "herramienta_no_permitida"
        assert await app.run.listar_aprobaciones(w["ctx"]) == []

    async def test_miembro_no_responsable_no_decide(self, app):
        w = await _workspace(app, herramientas=["publicar_resultado"])
        t = await _tarea(app, w, "Publicar la propuesta")
        await app.run.ejecutar(await app.run.encolar_tarea(w["ctx"], t, despachar=False))
        ap = (await app.run.listar_aprobaciones(w["ctx"]))[0]
        otro = await app.repo.crear_usuario("miembro@example.com", "contraseña-larga-2")
        await app.repo.agregar_miembro(w["ctx"], otro, "miembro")
        ctx_otro = await app.repo.resolver_contexto(otro, w["ws"])
        with pytest.raises(app.repo.SinPermiso):
            await app.run.decidir_aprobacion(ctx_otro, ap["id"], True, despachar=False)


class TestPresupuestoYFallos:
    async def test_sin_presupuesto_bloquea_antes_de_llamar(self, app):
        w = await _workspace(app, presupuesto=0)
        contador = _contador(app)
        async with app.memoria.async_session() as s:
            (await s.get(app.m.AppAgente, w["ejecutor"])).modelo = "contador"
            await s.commit()
        t = await _tarea(app, w)
        assert await app.run.ejecutar(await app.run.encolar_tarea(w["ctx"], t, despachar=False)) == "bloqueada"
        assert contador.llamadas == 0
        assert (await app.repo.obtener_tarea(w["ctx"], t))["motivo_bloqueo"] == "presupuesto_agotado"

    async def test_fallo_de_proveedor_y_reintento_sin_duplicar(self, app):
        w = await _workspace(app, herramientas=["publicar_resultado"])
        contador = _contador(app, fallar=True)
        async with app.memoria.async_session() as s:
            (await s.get(app.m.AppAgente, w["ejecutor"])).modelo = "contador"
            await s.commit()
        t = await _tarea(app, w, "Publicar la propuesta")
        ej1 = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        assert await app.run.ejecutar(ej1) == "fallida"
        assert (await app.run.listar_ejecuciones(w["ctx"], t))[0]["error_codigo"] == "proveedor_no_disponible"
        assert await app.run.listar_evidencias(w["ctx"], t) == []

        contador.fallar = False  # el proveedor vuelve
        ej2 = await app.run.reintentar_tarea(w["ctx"], t, despachar=False)
        assert ej2 != ej1
        assert await app.run.ejecutar(ej2) == "necesita_aprobacion"
        ap = (await app.run.listar_aprobaciones(w["ctx"]))[0]
        await app.run.decidir_aprobacion(w["ctx"], ap["id"], True, despachar=False)
        assert await app.run.ejecutar(ej2) == "completada"
        assert await app.contar(app.m.AppEfecto) == 1
        intentos = [e["intento"] for e in await app.run.listar_ejecuciones(w["ctx"], t)]
        assert intentos == [1, 2]

    async def test_modelo_no_disponible_falla_sin_red(self, app):
        w = await _workspace(app, modelo="claude-real")
        t = await _tarea(app, w)
        assert await app.run.ejecutar(await app.run.encolar_tarea(w["ctx"], t, despachar=False)) == "fallida"


class TestRecuperacion:
    async def test_reinicio_del_worker_con_ejecucion_a_medias(self, app):
        w = await _workspace(app)
        t = await _tarea(app, w)
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        assert await app.run._reclamar(ej)  # el worker la tomó… y murió
        futuro = datetime.utcnow() + timedelta(minutes=10)
        assert await app.run.reaper(ahora=futuro, despachar=False) == [ej]
        ejecuciones = await app.run.listar_ejecuciones(w["ctx"], t)
        assert [(e["intento"], e["estado"]) for e in ejecuciones] == [(1, "abandonada"), (2, "encolada")]
        assert await app.run.reaper(ahora=futuro, despachar=False) == []  # idempotente
        assert await app.run.ejecutar(ejecuciones[1]["id"]) == "completada"

    async def test_lease_vigente_no_se_toca(self, app):
        w = await _workspace(app)
        t = await _tarea(app, w)
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        await app.run._reclamar(ej)
        assert await app.run.reaper(despachar=False) == []

    async def test_tras_max_intentos_la_tarea_falla(self, app):
        w = await _workspace(app)
        t = await _tarea(app, w)
        await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        futuro = datetime.utcnow() + timedelta(minutes=10)
        for _ in range(app.run.MAX_INTENTOS):
            pendiente = [e for e in await app.run.listar_ejecuciones(w["ctx"], t) if e["estado"] == "encolada"]
            await app.run._reclamar(pendiente[0]["id"])
            await app.run.reaper(ahora=futuro, despachar=False)
        assert (await app.repo.obtener_tarea(w["ctx"], t))["estado"] == "fallida"


class TestCancelacion:
    async def test_cancelar_antes_de_ejecutar(self, app):
        w = await _workspace(app)
        t = await _tarea(app, w)
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        await app.run.cancelar_tarea(w["ctx"], t)
        assert await app.run.ejecutar(ej) is None
        assert (await app.run.listar_ejecuciones(w["ctx"], t))[0]["estado"] == "cancelada"

    async def test_cancelar_mientras_el_proveedor_trabaja_descarta_el_resultado(self, app):
        w = await _workspace(app)
        run, repo = app.run, app.repo
        ctx = w["ctx"]
        estado = {}

        class _QueCancela:
            nombre = "que_cancela"

            def costo_estimado(self, titulo, descripcion):
                return 1

            async def generar(self, **kw):
                await run.cancelar_tarea(ctx, estado["tarea"])  # el usuario cancela a mitad
                return await app.prov.ProveedorSimulado().generar(**kw)

            async def revisar(self, **kw):  # pragma: no cover
                raise AssertionError

        app.prov.registrar_proveedor("que_cancela", _QueCancela())
        async with app.memoria.async_session() as s:
            (await s.get(app.m.AppAgente, w["ejecutor"])).modelo = "que_cancela"
            await s.commit()
        estado["tarea"] = await _tarea(app, w)
        ej = await run.encolar_tarea(ctx, estado["tarea"], despachar=False)
        assert await run.ejecutar(ej) == "cancelada"
        assert (await repo.obtener_tarea(ctx, estado["tarea"]))["estado"] == "cancelada"
        assert await run.listar_evidencias(ctx, estado["tarea"]) == []


class TestAislamientoYWorker:
    async def test_otro_workspace_no_ve_ni_decide(self, app):
        a = await _workspace(app, "ana@example.com", herramientas=["publicar_resultado"])
        b = await _workspace(app, "beto@example.com")
        t = await _tarea(app, a, "Publicar la propuesta")
        await app.run.ejecutar(await app.run.encolar_tarea(a["ctx"], t, despachar=False))
        ap = (await app.run.listar_aprobaciones(a["ctx"]))[0]
        assert await app.run.listar_aprobaciones(b["ctx"]) == []
        for corrutina in (
            app.run.decidir_aprobacion(b["ctx"], ap["id"], True, despachar=False),
            app.run.listar_ejecuciones(b["ctx"], t),
            app.run.listar_evidencias(b["ctx"], t),
            app.run.encolar_tarea(b["ctx"], t, despachar=False),
            app.run.cancelar_tarea(b["ctx"], t),
        ):
            with pytest.raises(app.repo.NoEncontrado):
                await corrutina

    async def test_con_worker_apagado_queda_encolada(self, app, monkeypatch):
        monkeypatch.delenv("DONA_WORKER_ENABLED", raising=False)
        w = await _workspace(app)
        t = await _tarea(app, w)
        ej = await app.run.encolar_tarea(w["ctx"], t, despachar=False)
        assert await app.run.despachar_ejecucion(ej) == "ninguno"
        from agent.jobs.worker import app_ejecutar

        assert await app_ejecutar({}, ej) is None
        assert (await app.run.listar_ejecuciones(w["ctx"], t))[0]["estado"] == "encolada"

    async def test_inproc_procesa_en_segundo_plano(self, app, monkeypatch):
        monkeypatch.setenv("DONA_WORKER_ENABLED", "true")
        monkeypatch.setenv("JOBS_BACKEND", "inproc")
        w = await _workspace(app)
        t = await _tarea(app, w)
        await app.run.encolar_tarea(w["ctx"], t)  # despacha inproc
        for _ in range(50):
            if (await app.repo.obtener_tarea(w["ctx"], t))["estado"] == "completada":
                break
            await asyncio.sleep(0.05)
        assert (await app.repo.obtener_tarea(w["ctx"], t))["estado"] == "completada"
