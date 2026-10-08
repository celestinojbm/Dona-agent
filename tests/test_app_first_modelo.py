# tests/test_app_first_modelo.py — J7.1 · modelo de datos app-first
#
# Aislamiento entre workspaces (lo crítico), permisos por rol, conjuntos
# cerrados, transiciones de tarea, contraseñas y actividad sanitizada.
# SQLite en archivo temporal, mismo patrón de recarga que el resto del repo.

import importlib
import json
import sys

import pytest


@pytest.fixture
async def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'app_first.db'}")
    import agent.memory

    importlib.reload(agent.memory)
    # Registrar las tablas app_* en el Base recién recargado: recargar si el
    # módulo ya estaba importado (Base anterior), importar si es la primera vez.
    for nombre in ("agent.app_first.models", "agent.app_first.repositorio"):
        if nombre in sys.modules:
            importlib.reload(sys.modules[nombre])
        else:
            importlib.import_module(nombre)
    await agent.memory.inicializar_db()
    return sys.modules["agent.app_first.repositorio"]


async def _escenario(repo):
    """Dos usuarios, cada uno con su workspace, área, proyecto, agente y tarea."""
    datos = {}
    for nombre in ("ana", "beto"):
        uid = await repo.crear_usuario(f"{nombre}@example.com", "contraseña-larga-1")
        ws = await repo.crear_workspace(uid, f"Empresa de {nombre}")
        ctx = await repo.resolver_contexto(uid, ws)
        area = await repo.crear_area(ctx, "Ventas")
        proyecto = await repo.crear_proyecto(
            ctx, area, "Lanzamiento", "Vender el producto nuevo", ["Propuesta enviada"]
        )
        agente = await repo.crear_agente(ctx, "Ejecutor", "ejecutor", herramientas_permitidas=["redactar"])
        tarea = await repo.crear_tarea(ctx, proyecto, "Redactar propuesta", agente_id=agente)
        datos[nombre] = dict(uid=uid, ws=ws, ctx=ctx, area=area, proyecto=proyecto,
                             agente=agente, tarea=tarea)
    return datos


class TestAislamiento:
    async def test_un_usuario_no_resuelve_un_workspace_ajeno(self, repo):
        d = await _escenario(repo)
        with pytest.raises(repo.NoEncontrado):
            await repo.resolver_contexto(d["ana"]["uid"], d["beto"]["ws"])

    async def test_ids_de_otro_workspace_son_inexistentes(self, repo):
        d = await _escenario(repo)
        ctx_ana, beto = d["ana"]["ctx"], d["beto"]
        lecturas = [
            repo.obtener_proyecto(ctx_ana, beto["proyecto"]),
            repo.obtener_tarea(ctx_ana, beto["tarea"]),
            repo.obtener_agente(ctx_ana, beto["agente"]),
            repo.listar_tareas(ctx_ana, beto["proyecto"]),
            repo.listar_mensajes(ctx_ana, beto["proyecto"]),
        ]
        for corrutina in lecturas:
            with pytest.raises(repo.NoEncontrado):
                await corrutina

    async def test_no_se_escribe_en_objetos_ajenos(self, repo):
        d = await _escenario(repo)
        ctx_ana, beto = d["ana"]["ctx"], d["beto"]
        with pytest.raises(repo.NoEncontrado):
            await repo.crear_tarea(ctx_ana, beto["proyecto"], "Intrusa")
        with pytest.raises(repo.NoEncontrado):  # agente ajeno en proyecto propio
            await repo.crear_tarea(ctx_ana, d["ana"]["proyecto"], "Mezcla", agente_id=beto["agente"])
        with pytest.raises(repo.NoEncontrado):
            await repo.crear_proyecto(ctx_ana, beto["area"], "P", "O", ["c"])
        with pytest.raises(repo.NoEncontrado):
            await repo.cambiar_estado_tarea(ctx_ana, beto["tarea"], "en_ejecucion")
        with pytest.raises(repo.NoEncontrado):
            await repo.agregar_mensaje(ctx_ana, beto["proyecto"], "hola")
        # La tarea de Beto no cambió.
        assert (await repo.obtener_tarea(beto["ctx"], beto["tarea"]))["estado"] == "pendiente"

    async def test_listados_solo_devuelven_lo_propio(self, repo):
        d = await _escenario(repo)
        for nombre in ("ana", "beto"):
            ctx = d[nombre]["ctx"]
            assert [p["id"] for p in await repo.listar_proyectos(ctx)] == [d[nombre]["proyecto"]]
            assert [a["id"] for a in await repo.listar_agentes(ctx)] == [d[nombre]["agente"]]
            assert {a["objeto_id"] for a in await repo.listar_actividad(ctx) if a["objeto_tipo"] == "tarea"} == {
                d[nombre]["tarea"]
            }

    async def test_mensaje_con_tarea_de_otro_proyecto_se_rechaza(self, repo):
        d = await _escenario(repo)
        ctx = d["ana"]["ctx"]
        otro = await repo.crear_proyecto(ctx, d["ana"]["area"], "Otro", "Objetivo", ["c"])
        with pytest.raises(repo.NoEncontrado):
            await repo.agregar_mensaje(ctx, otro, "hola", tarea_id=d["ana"]["tarea"])


class TestPermisos:
    async def test_miembro_no_define_agentes_ni_areas(self, repo):
        d = await _escenario(repo)
        uid = await repo.crear_usuario("carla@example.com", "contraseña-larga-2")
        await repo.agregar_miembro(d["ana"]["ctx"], uid, "miembro")
        ctx_carla = await repo.resolver_contexto(uid, d["ana"]["ws"])
        assert ctx_carla.rol == "miembro"
        with pytest.raises(repo.SinPermiso):
            await repo.crear_agente(ctx_carla, "X", "ejecutor")
        with pytest.raises(repo.SinPermiso):
            await repo.crear_area(ctx_carla, "Marketing")
        with pytest.raises(repo.SinPermiso):
            await repo.agregar_miembro(ctx_carla, d["beto"]["uid"])
        # Pero sí crea tareas y escribe en el chat del proyecto.
        await repo.crear_tarea(ctx_carla, d["ana"]["proyecto"], "Tarea de Carla")
        await repo.agregar_mensaje(ctx_carla, d["ana"]["proyecto"], "Listo")

    async def test_no_se_puede_agregar_owner_ni_duplicar_miembro(self, repo):
        d = await _escenario(repo)
        uid = await repo.crear_usuario("dani@example.com", "contraseña-larga-3")
        with pytest.raises(repo.ValorInvalido):
            await repo.agregar_miembro(d["ana"]["ctx"], uid, "owner")
        await repo.agregar_miembro(d["ana"]["ctx"], uid, "admin")
        with pytest.raises(repo.Conflicto):
            await repo.agregar_miembro(d["ana"]["ctx"], uid, "miembro")

    async def test_responsable_debe_ser_miembro(self, repo):
        d = await _escenario(repo)
        with pytest.raises(repo.ValorInvalido):
            await repo.crear_proyecto(
                d["ana"]["ctx"], d["ana"]["area"], "P", "O", ["c"], responsable_usuario_id=d["beto"]["uid"]
            )


class TestValoresCerrados:
    async def test_rol_de_agente_cerrado(self, repo):
        d = await _escenario(repo)
        with pytest.raises(repo.ValorInvalido):
            await repo.crear_agente(d["ana"]["ctx"], "X", "director")

    async def test_proyecto_exige_criterios(self, repo):
        d = await _escenario(repo)
        with pytest.raises(repo.ValorInvalido):
            await repo.crear_proyecto(d["ana"]["ctx"], d["ana"]["area"], "P", "O", ["  "])

    async def test_transiciones_de_tarea(self, repo):
        d = await _escenario(repo)
        ctx, tarea = d["ana"]["ctx"], d["ana"]["tarea"]
        with pytest.raises(repo.ValorInvalido):  # no se salta a completada
            await repo.cambiar_estado_tarea(ctx, tarea, "completada")
        await repo.cambiar_estado_tarea(ctx, tarea, "en_ejecucion")
        with pytest.raises(repo.ValorInvalido):  # bloqueada exige motivo cerrado
            await repo.cambiar_estado_tarea(ctx, tarea, "bloqueada", "porque sí")
        t = await repo.cambiar_estado_tarea(ctx, tarea, "bloqueada", "presupuesto_agotado")
        assert t["motivo_bloqueo"] == "presupuesto_agotado"
        await repo.cambiar_estado_tarea(ctx, tarea, "pendiente")
        await repo.cambiar_estado_tarea(ctx, tarea, "cancelada")
        with pytest.raises(repo.ValorInvalido):  # terminal
            await repo.cambiar_estado_tarea(ctx, tarea, "pendiente")

    async def test_estado_inexistente(self, repo):
        d = await _escenario(repo)
        with pytest.raises(repo.ValorInvalido):
            await repo.cambiar_estado_tarea(d["ana"]["ctx"], d["ana"]["tarea"], "en_pausa")


class TestCuentas:
    async def test_password_se_guarda_con_hash_y_verifica(self, repo):
        uid = await repo.crear_usuario("  Eva@Example.com ", "una-contraseña-segura")
        assert await repo.verificar_credenciales("eva@example.com", "una-contraseña-segura") == uid
        assert await repo.verificar_credenciales("eva@example.com", "otra-contraseña-x") is None
        assert await repo.verificar_credenciales("nadie@example.com", "una-contraseña-segura") is None
        from sqlalchemy import select

        import agent.memory
        from agent.app_first import models as m

        async with agent.memory.async_session() as s:
            guardado = await s.scalar(select(m.AppUsuario.password_hash).where(m.AppUsuario.id == uid))
        assert guardado.startswith("scrypt$") and "una-contraseña-segura" not in guardado

    async def test_email_duplicado_y_password_corta(self, repo):
        await repo.crear_usuario("fer@example.com", "contraseña-larga-4")
        with pytest.raises(repo.Conflicto):
            await repo.crear_usuario("FER@example.com", "contraseña-larga-5")
        with pytest.raises(repo.ValorInvalido):
            await repo.crear_usuario("gil@example.com", "corta")

    def test_hash_mal_formado_no_verifica(self, repo):
        assert repo.verificar_password("x", "no-es-un-hash") is False
        assert repo.verificar_password("x", "md5$1$2$3$a$b") is False


class TestActividad:
    async def test_actividad_registra_cambios_sin_pii(self, repo):
        d = await _escenario(repo)
        ctx = d["ana"]["ctx"]
        await repo.cambiar_estado_tarea(ctx, d["ana"]["tarea"], "en_ejecucion")
        eventos = await repo.listar_actividad(ctx)
        estado = next(e for e in eventos if e["evento"] == "tarea_estado")
        assert estado["datos"] == {"de": "pendiente", "a": "en_ejecucion", "motivo_bloqueo": ""}
        assert all("email" not in json.dumps(e["datos"]) for e in eventos)
        assert {"workspace_creado", "area_creada", "proyecto_creado", "agente_creado", "tarea_creada"} <= {
            e["evento"] for e in eventos
        }


class TestEsquemaAditivo:
    async def test_tablas_app_conviven_con_las_existentes(self, repo):
        from sqlalchemy import inspect

        import agent.memory

        async with agent.memory.engine.connect() as conn:
            tablas = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        nuevas = {t for t in tablas if t.startswith("app_")}
        assert nuevas == {
            "app_usuarios", "app_workspaces", "app_membresias", "app_areas", "app_proyectos",
            "app_agentes", "app_tareas", "app_ejecuciones", "app_aprobaciones", "app_evidencias",
            "app_actividad", "app_consumo", "app_mensajes_proyecto",
        }
        # Las tablas del producto anterior siguen ahí, intactas.
        assert {"usuarios", "mensajes", "saldo_creditos", "suscripcion_stripe"} <= tablas
