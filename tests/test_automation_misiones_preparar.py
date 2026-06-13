# tests/test_automation_misiones_preparar.py — M0-2 · preparar + preview

"""
Tests de `preparar_recuperar_lead` (M0-2, spec Hermes): genera el draft del
mensaje de recuperación con el LLM gateado por el BudgetGuard y devuelve el
preview owner-scoped. NO envía, NO crea acción HIGH, NO aprueba.

Cubre la lista de Hermes para M0-2:
  - sin destino válido bloquea (missing/invalid)
  - el draft no envía (ningún provider de WhatsApp se toca)
  - wrong owner no ve el preview
  - preview/audit sanitizado (destino/teléfono nunca crudos)
  - presupuesto agotado bloquea SIN llamar al provider del draft
  - el mensaje no inventa descuentos/promesas (el prompt lo prohíbe explícito)

El LLM se mockea (sin llamadas reales). SQLite en archivo temporal.
"""

from __future__ import annotations

import importlib

import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "misiones_prep.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("AUTOMATION_SCHEDULER_ENABLED", raising=False)
    for v in ("DONA_LLM_COST_KILL_SWITCH", "BUDGET_MAX_LLM_AUX_CALLS_MENSAJE"):
        monkeypatch.delenv(v, raising=False)

    import agent.automation.models as _models
    import agent.automation.audit as _audit
    import agent.automation.missions as _missions
    import agent.presupuesto_runtime as _pr
    importlib.reload(agent.memory)
    importlib.reload(_models)
    importlib.reload(_audit)
    importlib.reload(_missions)
    _pr._contadores_eventos.clear()
    _pr._owners_suspendidos.clear()
    _pr._costo_diario_owner.clear()
    await agent.memory.inicializar_db()
    return _missions


OWNER = "5215500001111"
OTRO = "5215599998888"
DESTINO = "+5215512345678"


class _FakeDeepSeek:
    """Cliente estilo OpenAI con contador y captura del prompt enviado."""

    def __init__(self, texto="¡Hola Ana! Quedé pendiente de tu consulta, ¿te ayudo a retomarla?"):
        self.llamadas = 0
        self.prompts: list[str] = []
        cliente = self

        class _Completions:
            async def create(self, **kwargs):
                cliente.llamadas += 1
                cliente.prompts.append(kwargs["messages"][-1]["content"])

                class _R:
                    class usage:
                        total_tokens = 60
                    choices = [type("C", (), {"message": type("M", (), {"content": texto})()})()]
                return _R()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


@pytest.fixture
def llm_mock(monkeypatch):
    """Mockea el LLM auxiliar (DeepSeek) y desactiva el fallback Haiku."""
    import agent.llm as llm
    ds = _FakeDeepSeek()
    monkeypatch.setattr(llm, "_deepseek", ds)
    monkeypatch.setattr(llm, "_anthropic", None)
    return ds


async def _audit_rows():
    from sqlalchemy import select
    from agent.memory import async_session
    from agent.automation.models import AuditLogAutomatizacion
    async with async_session() as session:
        rows = (await session.execute(select(AuditLogAutomatizacion))).scalars().all()
        return [(r.evento, r.telefono_short, r.payload_summary) for r in rows]


# ── 1. Validación de destino ─────────────────────────────────────────────


class TestValidacionDestino:
    async def test_sin_destino_bloquea_sin_crear_mision(self, db, llm_mock):
        r = await db.preparar_recuperar_lead(telefono=OWNER, destino="")
        assert r["ok"] is False
        assert r["reason_code"] == "missing_lead_destination"
        assert r["mision_id"] is None
        assert llm_mock.llamadas == 0          # no se generó draft
        assert len(await db.listar_misiones(OWNER)) == 0  # no se creó misión

    async def test_destino_invalido_bloquea(self, db, llm_mock):
        r = await db.preparar_recuperar_lead(telefono=OWNER, destino="abc-no-num")
        assert r["ok"] is False
        assert r["reason_code"] == "invalid_destination"
        assert llm_mock.llamadas == 0

    def test_validar_destino_reason_codes(self, db):
        assert db.validar_destino("") == "missing_lead_destination"
        assert db.validar_destino("123") == "invalid_destination"
        assert db.validar_destino("abcdefgh") == "invalid_destination"
        assert db.validar_destino(DESTINO) == ""


# ── 2. Happy path: draft + preview ───────────────────────────────────────


class TestPreparaDraftYPreview:
    async def test_preparar_devuelve_preview_con_draft(self, db, llm_mock):
        r = await db.preparar_recuperar_lead(
            telefono=OWNER, destino=DESTINO, lead_nombre="Ana",
            contexto="pidió precio y no compró", objetivo="retomar compra",
        )
        assert r["ok"] is True
        assert r["estado"] == "draft"
        assert r["mensaje_preview"]            # hay draft
        assert r["riesgo"] == "high"
        assert r["next_required_action"] == "enlazar_accion_high_y_confirmar_envio"
        assert r["requiere_consentimiento_tercero"] is True
        assert r["costo_creditos_estimado_envio"] >= 1
        assert llm_mock.llamadas == 1          # un solo draft

    async def test_draft_no_envia_ni_crea_accion_high(self, db, llm_mock):
        """El draft NO toca ningún provider de WhatsApp ni crea acciones."""
        from sqlalchemy import select
        from agent.memory import async_session
        from agent.automation.models import AccionAutomatizacion

        await db.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        async with async_session() as session:
            acciones = (await session.execute(select(AccionAutomatizacion))).scalars().all()
        assert acciones == []                  # ninguna acción HIGH creada

    async def test_draft_persiste_en_la_mision(self, db, llm_mock):
        r = await db.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        m = await db.obtener_mision(r["mision_id"], OWNER)
        assert m["evidencia"]["draft"]["mensaje"]


# ── 3. Owner scope del preview ───────────────────────────────────────────


class TestOwnerScopePreview:
    async def test_wrong_owner_no_ve_preview(self, db, llm_mock):
        r = await db.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        assert await db.preview_recuperar_lead(r["mision_id"], OTRO) is None

    async def test_owner_re_renderiza_preview(self, db, llm_mock):
        r = await db.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        p = await db.preview_recuperar_lead(r["mision_id"], OWNER)
        assert p is not None
        assert p["mensaje_preview"] == r["mensaje_preview"]


# ── 4. Audit sin PII ─────────────────────────────────────────────────────


class TestAuditSinPII:
    async def test_audit_no_filtra_destino_ni_draft(self, db, llm_mock):
        draft_texto = "Hola Ana, te escribo a tu WhatsApp +5215512345678 personal"
        llm_mock_texto = _FakeDeepSeek(draft_texto)
        import agent.llm as llm
        llm._deepseek = llm_mock_texto

        await db.preparar_recuperar_lead(
            telefono=OWNER, destino=DESTINO, lead_nombre="Ana",
        )
        for evento, tel_short, summary in await _audit_rows():
            assert DESTINO not in summary       # destino enmascarado
            assert OWNER not in summary
            assert OWNER not in tel_short
            # el cuerpo del draft no se vuelca al audit
            assert "te escribo a tu WhatsApp" not in summary

    async def test_eventos_draft_y_preview_emitidos(self, db, llm_mock):
        await db.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        eventos = [e for (e, _, _) in await _audit_rows()]
        assert "mission_recover_lead_draft_created" in eventos
        assert "mission_recover_lead_preview_rendered" in eventos


# ── 5. Presupuesto agotado bloquea SIN provider ──────────────────────────


class TestPresupuestoAgotado:
    async def test_aux_cero_bloquea_sin_provider(self, db, llm_mock, monkeypatch):
        """REGRESIÓN/INVARIANTE: con cupo auxiliar 0, el draft se bloquea por
        el BudgetGuard SIN llamar al provider, y la misión queda blocked."""
        import agent.presupuesto_runtime as pr
        monkeypatch.setenv("BUDGET_MAX_LLM_AUX_CALLS_MENSAJE", "0")

        with pr.presupuesto_de_mensaje(OWNER):
            r = await db.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)

        assert r["ok"] is False
        assert r["reason_code"] == "budget_exhausted"
        assert llm_mock.llamadas == 0          # provider NUNCA llamado
        # La misión quedó registrada y bloqueada (no draft colgado)
        m = await db.obtener_mision(r["mision_id"], OWNER)
        assert m["estado"] == "blocked"
        assert m["reason_code"] == "budget_exhausted"

    async def test_kill_switch_bloquea_como_policy(self, db, llm_mock, monkeypatch):
        import agent.presupuesto_runtime as pr
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")

        with pr.presupuesto_de_mensaje(OWNER):
            r = await db.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)

        assert r["ok"] is False
        assert r["reason_code"] == "policy_blocked"
        assert llm_mock.llamadas == 0


# ── 6. El draft no inventa descuentos (prompt lo prohíbe) ────────────────


class TestNoInventaDescuentos:
    async def test_prompt_prohibe_inventar_ofertas(self, db, llm_mock):
        """El prompt enviado al LLM instruye explícitamente NO inventar
        descuentos/precios/promesas si no vienen en el contexto."""
        await db.preparar_recuperar_lead(
            telefono=OWNER, destino=DESTINO, lead_nombre="Ana",
            contexto="preguntó por horarios",   # sin oferta en el contexto
        )
        prompt = llm_mock.prompts[0].lower()
        assert "descuento" in prompt
        assert "no" in prompt and "invent" in prompt
        assert "promes" in prompt or "promoc" in prompt

    def test_prompt_incluye_contexto_del_owner(self, db):
        p = db._prompt_draft_recuperacion("Ana", "pidió precio", "retomar")
        assert "Ana" in p
        assert "pidió precio" in p
        assert "retomar" in p
