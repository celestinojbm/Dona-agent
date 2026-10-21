"""Tests de F14 — plan vivo (backend).

Cubre con SQLite aislado: checklist = versión autorizada; estados desde eventos
reales (durables); retry no regresa pasos; revisión vieja no pisa nueva;
recuperable tras "caída" (releer refleja el estado); outbox idempotente (un fallo
de notificación no toca el plan); usuario ajeno no ve. Formato WhatsApp.

Concurrencia real → PostgreSQL aislado; aquí la concurrencia optimista se valida
con el UPDATE condicional por `revision`.
"""

import importlib
import sys

import pytest

import agent.memory


def _recargar_plan_vivo():
    for mod in (
        "agent.plan_vivo.formato",
        "agent.plan_vivo.notificaciones",
        "agent.plan_vivo.planes",
        "agent.plan_vivo.models",
    ):
        sys.modules.pop(mod, None)
    import agent.plan_vivo.models  # noqa: F401
    import agent.plan_vivo.planes as planes
    import agent.plan_vivo.notificaciones as notif
    return planes, notif


@pytest.fixture
async def pv(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'pv.db'}")
    monkeypatch.setenv("DONA_LIVE_PLAN_ENABLED", "true")
    importlib.reload(agent.memory)
    planes, notif = _recargar_plan_vivo()
    await agent.memory.inicializar_db()
    return planes, notif


class TestPlan:
    async def test_crear_plan_preparado(self, pv):
        planes, _ = pv
        plan = await planes.crear_plan(
            telefono="5551", accion_ref="r1",
            titulos_pasos=["Buscar", "Redactar", "Enviar"],
            coste_maximo=10,
        )
        d = await planes.obtener_plan("5551", plan.id)
        assert d["estado"] == "preparado"
        assert d["revision"] == 0
        assert len(d["pasos"]) == 3
        assert all(p["estado"] == "pendiente" for p in d["pasos"])
        assert d["hash_plan"]

    async def test_coincide_version(self, pv):
        planes, _ = pv
        plan = await planes.crear_plan(
            telefono="5551", accion_ref="r2", titulos_pasos=["A"], coste_maximo=1,
        )
        d = await planes.obtener_plan("5551", plan.id)
        assert planes.coincide_version(d, d["version"], d["hash_plan"])
        assert not planes.coincide_version(d, d["version"], "hash_falso")
        assert not planes.coincide_version(d, 999, d["hash_plan"])

    async def test_ajeno_no_ve(self, pv):
        planes, _ = pv
        plan = await planes.crear_plan(
            telefono="5551", accion_ref="r3", titulos_pasos=["A"], coste_maximo=1,
        )
        assert await planes.obtener_plan("9999", plan.id) is None
        assert await planes.obtener_plan("5551", plan.id) is not None

    async def test_marcar_paso_sube_revision_y_es_durable(self, pv):
        planes, _ = pv
        plan = await planes.crear_plan(
            telefono="5551", accion_ref="r4", titulos_pasos=["A", "B"], coste_maximo=1,
        )
        r = await planes.marcar_paso(
            plan_id=plan.id, paso_id="p1", estado="completado",
            resultado="ok", intento=1, revision_esperada=0,
        )
        assert r.ok and r.revision == 1
        # Durable: releer (simula recuperación tras caída) refleja el estado.
        d = await planes.obtener_plan("5551", plan.id)
        assert d["pasos"][0]["estado"] == "completado"
        assert d["revision"] == 1

    async def test_revision_vieja_no_pisa(self, pv):
        planes, _ = pv
        plan = await planes.crear_plan(
            telefono="5551", accion_ref="r5", titulos_pasos=["A"], coste_maximo=1,
        )
        ok = await planes.marcar_paso(
            plan_id=plan.id, paso_id="p1", estado="en_curso", revision_esperada=0,
        )
        assert ok.ok
        # Otro escritor con la revisión vieja (0) no puede pisar (ahora es 1).
        viejo = await planes.marcar_paso(
            plan_id=plan.id, paso_id="p1", estado="fallido", revision_esperada=0,
        )
        assert not viejo.ok and viejo.razon == "revision_desactualizada"

    async def test_retry_no_regresa_paso_terminal(self, pv):
        planes, _ = pv
        plan = await planes.crear_plan(
            telefono="5551", accion_ref="r6", titulos_pasos=["A"], coste_maximo=1,
        )
        await planes.marcar_paso(
            plan_id=plan.id, paso_id="p1", estado="completado", revision_esperada=0,
        )
        # Un retry intenta volver a 'pendiente' → rechazado (no regresa).
        r = await planes.marcar_paso(
            plan_id=plan.id, paso_id="p1", estado="pendiente", revision_esperada=1,
        )
        assert not r.ok and r.razon == "no_regresa"

    async def test_avanzar_estado(self, pv):
        planes, _ = pv
        plan = await planes.crear_plan(
            telefono="5551", accion_ref="r7", titulos_pasos=["A"], coste_maximo=1,
        )
        mal = await planes.avanzar_estado(plan_id=plan.id, estado="inventado", revision_esperada=0)
        assert not mal.ok and mal.razon == "estado_invalido"
        ok = await planes.avanzar_estado(plan_id=plan.id, estado="en_curso", revision_esperada=0)
        assert ok.ok
        d = await planes.obtener_plan("5551", plan.id)
        assert d["estado"] == "en_curso"


class TestNotificaciones:
    async def test_outbox_idempotente(self, pv):
        _, notif = pv
        a = await notif.encolar(plan_id=1, telefono="5551", dedupe_key="plan1:v1")
        b = await notif.encolar(plan_id=1, telefono="5551", dedupe_key="plan1:v1")
        assert a is True and b is False  # no duplica

    async def test_fallida_no_rompe(self, pv):
        _, notif = pv
        await notif.encolar(plan_id=1, telefono="5551", dedupe_key="k1")
        # Un fallo de notificación (p. ej. 429 de Whapi) sólo marca la fila.
        await notif.marcar_fallida("k1")
        from sqlalchemy import select
        from agent.plan_vivo.models import NotificacionPlan
        from agent.memory import async_session
        async with async_session() as s:
            n = (await s.execute(
                select(NotificacionPlan).where(NotificacionPlan.dedupe_key == "k1")
            )).scalar_one()
        assert n.estado == "fallida" and n.intentos == 1


class TestNotificacionWhatsApp:
    """Decisión de Celestino #10: plan vivo SÓLO en la app; nada de checklist en
    vivo en WhatsApp. Durante la ejecución no se notifica; sólo aviso terminal."""

    def test_sin_plan_vivo_en_whatsapp(self):
        # Ya no existe un render de checklist en vivo para WhatsApp.
        import agent.plan_vivo.formato as fmt
        assert not hasattr(fmt, "render_whatsapp")

    def test_en_curso_no_notifica(self):
        from agent.plan_vivo.formato import notificacion_terminal
        assert notificacion_terminal({"estado": "en_curso"}) is None
        assert notificacion_terminal({"estado": "preparado"}) is None

    def test_aviso_terminal_breve(self):
        from agent.plan_vivo.formato import notificacion_terminal
        assert notificacion_terminal({"estado": "completado"}) == "Listo."
        assert "app" in notificacion_terminal({"estado": "fallido"})


def test_flag_apagado_por_defecto(monkeypatch):
    monkeypatch.delenv("DONA_LIVE_PLAN_ENABLED", raising=False)
    from agent.plan_vivo.planes import plan_vivo_habilitado
    assert plan_vivo_habilitado() is False
