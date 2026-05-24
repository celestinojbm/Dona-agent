# tests/test_automation_next_required_action.py
#
# Contrato explícito de "siguiente acción requerida" para el Action Center.
# Cada acción serializada debe exponer:
#   - next_required_action: qué control debe operar la acción ahora
#   - execution_block_reason: motivo (texto corto) cuando la acción no se
#     puede ejecutar por el control genérico
#
# Valores esperados:
#   low/pending           → execute_available, sin razón de bloqueo
#   medium/approved       → execute_available, sin razón de bloqueo
#   medium/needs_approval → approval_required
#   medium/pending        → none (defensivo · combinación legacy/bug)
#   high/needs_approval   → approval_required
#   high/pending          → none (defensivo · combinación legacy/bug)
#   high/approved         → dedicated_confirmation_required + razón explicando
#                           que requiere confirmación dedicada con preview,
#                           costo y riesgo antes de efecto externo real.
#   critical/needs_approval → reinforced_approval_required + razón de bloqueo
#   completed/failed/rejected/cancelled → none
#
# Estos tests fijan el contrato a nivel:
#   1. Helper puro en agent.automation.permissions
#   2. Serializador interno _a_dict (action_center)
#   3. Sanitizador para dashboard _filtrar_accion_para_dashboard (main)

import importlib
import pytest
import pytest_asyncio

import agent.memory


@pytest_asyncio.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "next_required.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.permissions as _perm
    import agent.automation.action_center as _ac
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_perm)
    importlib.reload(_ac)
    await agent.memory.inicializar_db()
    return _ac


# ───────────────────────── Helper puro ─────────────────────────


class TestHelperPuro:
    """El helper central calcula (next_required_action, execution_block_reason)
    a partir de (estado, riesgo). No toca DB."""

    def test_low_pending_execute_available(self):
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("pending", "low")
        assert nxt == "execute_available"
        assert motivo == ""

    def test_medium_approved_execute_available(self):
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("approved", "medium")
        assert nxt == "execute_available"
        assert motivo == ""

    def test_medium_needs_approval(self):
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("needs_approval", "medium")
        assert nxt == "approval_required"
        assert motivo == ""

    def test_medium_pending_no_es_execute_available(self):
        """Defensivo · medium/pending NO debe abrir ningún control desde
        el Action Center genérico.

        Una acción medium recién creada arranca en needs_approval, así que
        pending/medium solo aparece por datos legacy o un bug. Tampoco se
        puede aprobar: TRANSICIONES en permissions.py solo permite
        pending → running/cancelled/rejected, no pending → approved. Si
        ofreciéramos Aprobar terminaría en transición inválida y la UI
        engañaría al usuario.

        Por eso el contrato devuelve 'none' y motivo vacío · ningún botón
        del control genérico tiene sentido sobre esta combinación."""
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("pending", "medium")
        assert nxt == "none"
        assert motivo == ""

    def test_high_needs_approval(self):
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("needs_approval", "high")
        assert nxt == "approval_required"
        assert motivo == ""

    def test_high_pending_no_es_aprobable(self):
        """Defensivo · igual que medium/pending, high/pending no es una
        transición válida hacia approved (TRANSICIONES sólo permite
        pending → running/cancelled/rejected). Una HIGH se crea siempre en
        needs_approval, así que pending/high sólo aparece por datos legacy
        o por un bug.

        Aprobar desde pending sería transición inválida y la UI engañaría
        al usuario · el contrato devuelve 'none' y motivo vacío. Ningún
        botón del control genérico (Aprobar/Rechazar/Ejecutar) debe
        ofrecerse sobre esta combinación."""
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("pending", "high")
        assert nxt == "none"
        assert motivo == ""

    def test_high_approved_dedicated_confirmation_required(self):
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("approved", "high")
        assert nxt == "dedicated_confirmation_required"
        # Razón breve · debe mencionar la confirmación dedicada para que la
        # UI pueda renderizarla literal si quiere.
        assert motivo, "execution_block_reason debe ser no vacío para high/approved"
        assert "confirmaci" in motivo.lower()

    def test_critical_needs_approval_reinforced(self):
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("needs_approval", "critical")
        assert nxt == "reinforced_approval_required"
        assert motivo, "execution_block_reason debe ser no vacío para critical"

    def test_critical_approved_sigue_bloqueado(self):
        """Aun aprobada, una CRITICAL queda bloqueada: el control genérico
        no debe creer que está lista para ejecutar."""
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action("approved", "critical")
        assert nxt == "reinforced_approval_required"
        assert motivo

    @pytest.mark.parametrize("estado", ["completed", "failed", "rejected", "cancelled"])
    def test_estados_terminales_devuelven_none(self, estado):
        from agent.automation.permissions import calcular_next_required_action
        nxt, motivo = calcular_next_required_action(estado, "high")
        assert nxt == "none"
        assert motivo == ""

    def test_running_no_es_ejecutable_por_control_generico(self):
        """running ya está siendo ejecutada · no se debe ofrecer otro
        control sobre ella. La UI debe mostrar estado, no botones."""
        from agent.automation.permissions import calcular_next_required_action
        nxt, _motivo = calcular_next_required_action("running", "low")
        assert nxt == "none"


# ─────────────── _a_dict (serializador interno) ───────────────


class TestSerializadorInterno:
    @pytest.mark.asyncio
    async def test_low_pending_expone_execute_available(self, db):
        a = await db.crear_accion(
            telefono="5710",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        assert a["next_required_action"] == "execute_available"
        assert a["execution_block_reason"] == ""

    @pytest.mark.asyncio
    async def test_medium_needs_approval_expone_approval_required(self, db):
        a = await db.crear_accion(
            telefono="5711",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Borrador",
        )
        assert a["next_required_action"] == "approval_required"
        assert a["execution_block_reason"] == ""

    @pytest.mark.asyncio
    async def test_high_approved_expone_dedicated_confirmation(self, db):
        a = await db.crear_accion(
            telefono="5712",
            tipo_accion="enviar_mensaje_whatsapp",
            titulo="Envío real",
        )
        aprobada = await db.aprobar_accion(a["id"])
        assert aprobada["riesgo"] == "high"
        assert aprobada["estado"] == "approved"
        assert aprobada["next_required_action"] == "dedicated_confirmation_required"
        assert aprobada["execution_block_reason"]
        assert "confirmaci" in aprobada["execution_block_reason"].lower()

    @pytest.mark.asyncio
    async def test_critical_expone_reinforced(self, db):
        a = await db.crear_accion(
            telefono="5713",
            tipo_accion="envio_masivo_clientes",
            titulo="Mass",
        )
        assert a["riesgo"] == "critical"
        assert a["next_required_action"] == "reinforced_approval_required"
        assert a["execution_block_reason"]

    @pytest.mark.asyncio
    async def test_medium_aprobada_expone_execute_available(self, db):
        a = await db.crear_accion(
            telefono="5714",
            tipo_accion="preparar_mensaje_whatsapp",
            titulo="Brd",
        )
        aprobada = await db.aprobar_accion(a["id"])
        assert aprobada["riesgo"] == "medium"
        assert aprobada["estado"] == "approved"
        assert aprobada["next_required_action"] == "execute_available"


# ─────────────── Sanitizador dashboard ───────────────


class TestSanitizadorDashboard:
    """El sanitizador del dashboard debe pasar next_required_action y
    execution_block_reason · son campos no sensibles que la UI necesita
    para no confundir HIGH approved con LOW pending."""

    def test_sanitizador_propaga_campos_contrato(self):
        from agent.main import _filtrar_accion_para_dashboard
        accion = {
            "id": 99,
            "opportunity_id": "opp",
            "playbook_id": "pb",
            "tipo_accion": "enviar_mensaje_whatsapp",
            "titulo": "T",
            "descripcion": "D",
            "razon_recomendacion": "R",
            "estado": "approved",
            "riesgo": "high",
            "costo_creditos_estimado": 5,
            "requires_approval": True,
            "payload_json": "{}",
            "result_json": "{}",
            "error_message": "",
            "idempotency_key": "secreto",
            "created_at": None,
            "updated_at": None,
            "approved_at": None,
            "rejected_at": None,
            "completed_at": None,
            "next_required_action": "dedicated_confirmation_required",
            "execution_block_reason": "Requiere confirmación dedicada",
        }
        out = _filtrar_accion_para_dashboard(accion)
        assert out["next_required_action"] == "dedicated_confirmation_required"
        assert out["execution_block_reason"] == "Requiere confirmación dedicada"
        # Sigue sin filtrar lo sensible
        assert "idempotency_key" not in out
        assert "payload_json" not in out
