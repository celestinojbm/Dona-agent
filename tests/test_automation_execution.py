# tests/test_automation_execution.py — T2.1.A · Execution System

import importlib
import json
import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "exec.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    import agent.automation.execution as _ex
    import agent.automation.costos as _co
    # T2.1.D · Estos tests legacy NO simulan saldo de créditos. Para que
    # la lógica de reservas no los rompa, forzamos costo=0 a todas las
    # acciones · reservar(creditos=0) no cobra y crea fila pending OK.
    monkeypatch.setattr(_co, "estimar_costo_accion", lambda tipo: 0)
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_ac)
    importlib.reload(_ex)
    monkeypatch.setattr(_co, "estimar_costo_accion", lambda tipo: 0)
    await agent.memory.inicializar_db()
    return _ex, _ac


class TestEjecutarLowAuto:
    @pytest.mark.asyncio
    async def test_low_pending_se_ejecuta(self, db):
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5550",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "completed"
        assert "result" in r
        # T2.1.C: modo='llm' si LLM responde · 'fallback' si no.
        # En tests sin DEEPSEEK_API_KEY/ANTHROPIC_API_KEY el LLM
        # retorna None y se usa fallback determinístico.
        assert r["result"]["modo"] in ("llm", "fallback")

    @pytest.mark.asyncio
    async def test_low_genera_output_md(self, db):
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5551",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        r = await ex.ejecutar_accion(a)
        assert "Plan semanal" in r["result"]["output_md"]

    @pytest.mark.asyncio
    async def test_calendario_devuelve_7_dias(self, db):
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5552",
            tipo_accion="generar_calendario_contenido",
            titulo="Cal",
        )
        r = await ex.ejecutar_accion(a)
        assert len(r["result"]["calendario"]) == 7

    @pytest.mark.asyncio
    async def test_checklist_devuelve_lista(self, db):
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5553",
            tipo_accion="generar_checklist_ventas",
            titulo="Ch",
        )
        r = await ex.ejecutar_accion(a)
        assert isinstance(r["result"]["checklist"], list)
        assert len(r["result"]["checklist"]) >= 5


class TestEjecutarMedium:
    @pytest.mark.asyncio
    async def test_medium_sin_aprobacion_falla(self, db):
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5560",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Borrador",
        )
        # Estado inicial = needs_approval
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "failed"
        assert "aprob" in r["error"].lower() or "estado" in r["error"].lower()

    @pytest.mark.asyncio
    async def test_medium_con_aprobacion_ejecuta(self, db):
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5561",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Borrador",
        )
        await ac.aprobar_accion(a["id"])
        # Recargar la acción tras la aprobación
        listed = await ac.listar_acciones("5561")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "completed"
        assert r["result"]["estado_envio"] == "pending_user_review"
        # Confirma que NO se envía nada · solo prepara
        assert "borrador" in r["result"]


class TestEjecutarHighSinEjecutorReal:
    @pytest.mark.asyncio
    async def test_high_aprobado_pero_sin_ejecutor_t21a_falla(self, db):
        """T2.2 conectó ejecutor para enviar_mensaje_whatsapp · el
        resto de HIGH (publicar_red_social, contactar_lead,
        enviar_campana_masiva) sigue sin ejecutor y debe fallar."""
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5570",
            tipo_accion="contactar_lead",
            titulo="Contact",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5570")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "failed"
        assert "T2.1" in r["error"] or "ejecutor" in r["error"].lower()


class TestEjecutarCriticalBloqueado:
    @pytest.mark.asyncio
    async def test_critical_aprobado_queda_bloqueado(self, db):
        """Critical NUNCA se ejecuta en T2.1.A · ni siquiera con
        aprobación. Genera audit log evento 'action_blocked_critical'."""
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5580",
            tipo_accion="envio_masivo_clientes",
            titulo="Mass send",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5580")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "failed"
        assert "critical" in r["error"].lower() or "bloque" in r["error"].lower()

    @pytest.mark.asyncio
    async def test_critical_emite_audit_block(self, db):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5581",
            tipo_accion="borrar_datos_negocio",
            titulo="X",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5581")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        await ex.ejecutar_accion(approved)
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(AuditLogAutomatizacion).where(
                    AuditLogAutomatizacion.evento == "action_blocked_critical"
                )
            )
            logs = list(r.scalars().all())
        assert len(logs) >= 1
        assert logs[0].riesgo == "critical"


class TestEjecutoresInternosNoTienenEfectoExterno:
    """Validación crítica: los ejecutores T2.1.A jamás llaman a
    proveedores reales (Whapi, Stripe, etc). Solo retornan dicts."""

    @pytest.mark.asyncio
    async def test_preparar_mensaje_no_invoca_whapi(self, db, monkeypatch):
        from agent.automation import execution as _ex
        # Si se intentara llamar a algún módulo de provider, fallaría.
        # Pero los ejecutores T2.1.A son funciones puras · no importan
        # nada de providers. Verificamos que la función NO tiene
        # referencias a 'enviar_mensaje', 'whapi', 'twilio'.
        import inspect
        for name, fn in [
            ("preparar_mensaje", _ex._ejecutor_preparar_mensaje_whatsapp),
            ("preparar_campana", _ex._ejecutor_preparar_campana_whatsapp),
            ("publicar_redes", _ex._ejecutor_preparar_publicacion_redes),
            ("preparar_email", _ex._ejecutor_preparar_email_seguimiento),
        ]:
            src = inspect.getsource(fn).lower()
            for forbidden in ("whapi", "twilio", "providers", "stripe.",
                              "send_message", "enviar_mensaje", "publish_"):
                assert forbidden not in src, \
                    f"Ejecutor {name} contiene referencia prohibida: {forbidden}"


class TestEstadoActionCenterPostEjecucion:
    @pytest.mark.asyncio
    async def test_low_termina_completed_en_db(self, db):
        ex, ac = db
        a = await ac.crear_accion(
            telefono="5590",
            tipo_accion="analizar_diagnostico",
            titulo="An",
        )
        await ex.ejecutar_accion(a)
        listed = await ac.listar_acciones("5590")
        assert listed[0]["estado"] == "completed"
        assert listed[0]["completed_at"] is not None
        # Result_json contiene la métrica completitud
        result = json.loads(listed[0]["result_json"])
        assert "campos_llenos" in result
