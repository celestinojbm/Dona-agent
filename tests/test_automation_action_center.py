# tests/test_automation_action_center.py — T2.1.A · Action Center CRUD

import importlib
import json
import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """SQLite aislada · recarga modelos automation para que la metadata
    se aplique a la DB nueva."""
    db_path = tmp_path / "act.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_ac)
    await agent.memory.inicializar_db()
    return _ac


class TestCrearAccionLow:
    @pytest.mark.asyncio
    async def test_low_estado_inicial_pending(self, db):
        a = await db.crear_accion(
            telefono="5551",
            tipo_accion="generar_plan_semanal",
            titulo="Plan semanal de prueba",
        )
        assert a["created"] is True
        assert a["riesgo"] == "low"
        assert a["estado"] == "pending"
        assert a["requires_approval"] is False
        assert a["costo_creditos_estimado"] > 0
        assert a["id"] > 0


class TestCrearAccionMedium:
    @pytest.mark.asyncio
    async def test_medium_inicial_needs_approval(self, db):
        a = await db.crear_accion(
            telefono="5552",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Borrador para X",
        )
        assert a["riesgo"] == "medium"
        assert a["estado"] == "needs_approval"
        assert a["requires_approval"] is True


class TestCrearAccionHighCritical:
    @pytest.mark.asyncio
    async def test_high_inicial_needs_approval(self, db):
        a = await db.crear_accion(
            telefono="5553",
            tipo_accion="enviar_mensaje_whatsapp",
            titulo="Envío real",
        )
        assert a["riesgo"] == "high"
        assert a["estado"] == "needs_approval"

    @pytest.mark.asyncio
    async def test_critical_inicial_needs_approval(self, db):
        a = await db.crear_accion(
            telefono="5554",
            tipo_accion="envio_masivo_clientes",
            titulo="Envío masivo",
        )
        assert a["riesgo"] == "critical"
        # Inicial es needs_approval; el bloqueo sucede en execution.
        assert a["estado"] == "needs_approval"


class TestIdempotencia:
    @pytest.mark.asyncio
    async def test_misma_accion_no_se_duplica(self, db):
        a1 = await db.crear_accion(
            telefono="5560",
            tipo_accion="generar_plan_semanal",
            titulo="Plan", playbook_id="diagnostico_a_plan_semanal",
            opportunity_id="opp_xxx",
        )
        a2 = await db.crear_accion(
            telefono="5560",
            tipo_accion="generar_plan_semanal",
            titulo="Plan", playbook_id="diagnostico_a_plan_semanal",
            opportunity_id="opp_xxx",
        )
        assert a1["created"] is True
        assert a2["created"] is False
        assert a1["id"] == a2["id"]

    @pytest.mark.asyncio
    async def test_diferente_tipo_genera_otra(self, db):
        a1 = await db.crear_accion(
            telefono="5561",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        a2 = await db.crear_accion(
            telefono="5561",
            tipo_accion="analizar_diagnostico",
            titulo="Análisis",
        )
        assert a1["id"] != a2["id"]


class TestListar:
    @pytest.mark.asyncio
    async def test_listar_filtra_por_telefono(self, db):
        await db.crear_accion(
            telefono="5570",
            tipo_accion="generar_plan_semanal",
            titulo="P1",
        )
        await db.crear_accion(
            telefono="5571",
            tipo_accion="generar_plan_semanal",
            titulo="P2",
        )
        l1 = await db.listar_acciones("5570")
        l2 = await db.listar_acciones("5571")
        assert len(l1) == 1 and l1[0]["telefono"] == "5570"
        assert len(l2) == 1 and l2[0]["telefono"] == "5571"

    @pytest.mark.asyncio
    async def test_listar_filtra_por_estado(self, db):
        await db.crear_accion(
            telefono="5580",
            tipo_accion="generar_plan_semanal",  # LOW → pending
            titulo="A",
        )
        await db.crear_accion(
            telefono="5580",
            tipo_accion="preparar_mensaje_whatsapp",  # MEDIUM → needs_approval
            titulo="B",
        )
        pending = await db.listar_acciones("5580", estado="pending")
        needs = await db.listar_acciones("5580", estado="needs_approval")
        assert len(pending) == 1 and pending[0]["tipo_accion"] == "generar_plan_semanal"
        assert len(needs) == 1 and needs[0]["tipo_accion"] == "preparar_mensaje_whatsapp"


class TestTransicionesEstado:
    @pytest.mark.asyncio
    async def test_aprobar_cambia_a_approved(self, db):
        a = await db.crear_accion(
            telefono="5590",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Brd",
        )
        u = await db.aprobar_accion(a["id"])
        assert u["estado"] == "approved"
        assert u["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_rechazar_cambia_a_rejected(self, db):
        a = await db.crear_accion(
            telefono="5591",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Brd",
        )
        u = await db.rechazar_accion(a["id"])
        assert u["estado"] == "rejected"
        assert u["rejected_at"] is not None

    @pytest.mark.asyncio
    async def test_aprobar_invalida_si_ya_completada(self, db):
        a = await db.crear_accion(
            telefono="5592",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Brd",
        )
        await db.aprobar_accion(a["id"])
        await db.marcar_running(a["id"])
        await db.marcar_completada(a["id"], result={"ok": True})
        # Ya completada · no se puede re-aprobar
        u = await db.aprobar_accion(a["id"])
        assert u["estado"] == "completed"  # quedó en completed

    @pytest.mark.asyncio
    async def test_marcar_completada_persiste_result(self, db):
        a = await db.crear_accion(
            telefono="5593",
            tipo_accion="generar_plan_semanal",
            titulo="P",
        )
        await db.marcar_running(a["id"])
        u = await db.marcar_completada(a["id"], result={"plan_md": "# Hola"})
        assert u["estado"] == "completed"
        result_dict = json.loads(u["result_json"])
        assert result_dict.get("plan_md") == "# Hola"

    @pytest.mark.asyncio
    async def test_marcar_fallida_persiste_error(self, db):
        a = await db.crear_accion(
            telefono="5594",
            tipo_accion="generar_plan_semanal",
            titulo="P",
        )
        await db.marcar_running(a["id"])
        u = await db.marcar_fallida(a["id"], error_message="timeout LLM")
        assert u["estado"] == "failed"
        assert "timeout" in u["error_message"]


class TestAccionInexistente:
    @pytest.mark.asyncio
    async def test_aprobar_no_existe_retorna_none(self, db):
        u = await db.aprobar_accion(999999)
        assert u is None
