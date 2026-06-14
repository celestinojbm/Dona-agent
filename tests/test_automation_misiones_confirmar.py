# tests/test_automation_misiones_confirmar.py — M0-4 · completion sync + reconciliación

"""
Tests de `confirmar_recuperar_lead` (M0-4, contrato Hermes): wrapper estrecho
que DELEGA al confirmador HIGH dedicado existente y SINCRONIZA el estado de la
misión con el resultado. NO implementa provider propio, NO auto-aprueba.

Cubre la lista de Hermes para M0-4:
  - confirmación válida → provider fake llamado 1 vez → misión completed
  - provider lanza excepción → misión failed (provider_failed)
  - confirmación inválida → no llama provider → misión sigue needs_approval
  - doble confirmación secuencial → no duplica envío
  - doble confirmación concurrente → no duplica + créditos coherentes
  - reconciliación post-crash: needs_approval sin accion_id → relink/revert;
    acción mision-* huérfana → cancelar

LLM del draft y provider de WhatsApp mockeados; SQLite en archivo temporal.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest

import agent.memory


class FakeProveedor:
    def __init__(self, resultado=True, lanzar_exc=False):
        self.resultado = resultado
        self.lanzar_exc = lanzar_exc
        self.invocaciones = []

    async def enviar_mensaje(self, telefono, mensaje):
        self.invocaciones.append((telefono, mensaje))
        if self.lanzar_exc:
            raise RuntimeError("simulated provider exception")
        return self.resultado


class _FakeDeepSeek:
    def __init__(self, texto="Hola, ¿retomamos tu consulta?"):
        cliente = self

        class _Completions:
            async def create(self, **kwargs):
                class _R:
                    class usage:
                        total_tokens = 60
                    choices = [type("C", (), {"message": type("M", (), {"content": texto})()})()]
                return _R()

        class _Chat:
            completions = _Completions()
        self.chat = _Chat()


@pytest.fixture
async def env(tmp_path, monkeypatch):
    db_path = tmp_path / "m04.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("AUTOMATION_SCHEDULER_ENABLED", raising=False)
    for v in ("DONA_LLM_COST_KILL_SWITCH", "BUDGET_MAX_LLM_AUX_CALLS_MENSAJE"):
        monkeypatch.delenv(v, raising=False)

    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    import agent.automation.credits as _cr
    import agent.automation.execution as _ex
    import agent.automation.executors.send_message as _sm
    import agent.automation.missions as _missions
    import agent.billing as _bi
    importlib.reload(agent.memory)
    for m in (_bm, _am, _au, _ac, _cr, _bi, _sm, _ex, _missions):
        importlib.reload(m)
    await agent.memory.inicializar_db()

    # LLM del draft
    import agent.llm as llm
    monkeypatch.setattr(llm, "_deepseek", _FakeDeepSeek())
    monkeypatch.setattr(llm, "_anthropic", None)

    return _ac, _sm, _bi, _missions


OWNER = "5215500001111"
OTRO = "5215599998888"
DESTINO = "+5215512345678"


def _mock_prov(monkeypatch, sm, fake):
    monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)


async def _preparar_enlazar_aprobar(env, monkeypatch, fake=None):
    """Misión lista para confirmar: draft + acción HIGH enlazada + aprobada
    + créditos sembrados + provider mockeado."""
    ac, sm, bi, missions = env
    fake = fake or FakeProveedor(resultado=True)
    _mock_prov(monkeypatch, sm, fake)
    await bi.acreditar(OWNER, 50, "seed")
    r = await missions.preparar_recuperar_lead(
        telefono=OWNER, destino=DESTINO, lead_nombre="Ana", contexto="pidió precio",
    )
    link = await missions.enlazar_accion_high_recuperar_lead(r["mision_id"], OWNER)
    await ac.aprobar_accion(link["accion_id"])
    return r["mision_id"], link["accion_id"], fake


# ── 1. Confirmación válida → completed ───────────────────────────────────


class TestConfirmacionOk:
    async def test_envia_una_vez_y_mision_completed(self, env, monkeypatch):
        _, _, _, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        r = await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        assert r["ok"] is True
        assert r["estado"] == "completed"
        assert len(fake.invocaciones) == 1
        m = await missions.obtener_mision(mid, OWNER)
        assert m["estado"] == "completed"
        assert m["completed_at"] is not None


# ── 2. Provider falla → failed ───────────────────────────────────────────


class TestProviderFalla:
    async def test_excepcion_provider_mision_failed(self, env, monkeypatch):
        _, _, _, missions = env
        fake = FakeProveedor(lanzar_exc=True)
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch, fake)
        r = await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        assert r["ok"] is False
        assert r["estado"] == "failed"
        assert r["reason_code"] == "provider_failed"
        m = await missions.obtener_mision(mid, OWNER)
        assert m["estado"] == "failed"


# ── 3. Confirmación inválida → no envía, misión intacta ──────────────────


class TestConfirmacionInvalida:
    async def test_string_invalido_no_envia_ni_cierra(self, env, monkeypatch):
        _, _, _, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        r = await missions.confirmar_recuperar_lead(mid, OWNER, " enviar ")
        assert r["ok"] is False
        assert r.get("reintentable") is True
        assert fake.invocaciones == []
        m = await missions.obtener_mision(mid, OWNER)
        assert m["estado"] == "needs_approval"   # NO se cerró

    async def test_wrong_owner_no_confirma(self, env, monkeypatch):
        _, _, _, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        r = await missions.confirmar_recuperar_lead(mid, OTRO, "ENVIAR")
        assert r["ok"] is False
        assert r["error"] == "mision_no_existe_o_ajena"
        assert fake.invocaciones == []


# ── 4. Idempotencia / doble confirmación ─────────────────────────────────


class TestDobleConfirmacion:
    async def test_secuencial_no_duplica(self, env, monkeypatch):
        _, _, bi, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        r1 = await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        saldo1 = await bi.obtener_saldo(OWNER)
        r2 = await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        saldo2 = await bi.obtener_saldo(OWNER)
        assert r1["estado"] == "completed" and r2["estado"] == "completed"
        assert r2.get("idempotent") is True
        assert len(fake.invocaciones) == 1       # un solo envío
        assert saldo1 == saldo2                   # sin doble cobro

    async def test_concurrente_no_duplica_y_creditos_coherentes(self, env, monkeypatch):
        _, _, bi, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        r1, r2 = await asyncio.gather(
            missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR"),
            missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR"),
        )
        assert len(fake.invocaciones) == 1       # un solo envío real
        m = await missions.obtener_mision(mid, OWNER)
        assert m["estado"] == "completed"
        # Créditos: exactamente un cobro (50 - costo del envío)
        from agent.automation.costos import estimar_costo_accion
        costo = estimar_costo_accion("enviar_mensaje_whatsapp")
        assert await bi.obtener_saldo(OWNER) == 50 - costo


# ── 5. Reconciliación post-crash ─────────────────────────────────────────


class TestReconciliacion:
    async def test_needs_approval_sin_accion_relinkea(self, env, monkeypatch):
        """Simula el residual de crash: misión needs_approval sin accion_id
        pero CON una acción mision-* válida → la reconciliación relinkea."""
        from sqlalchemy import update
        from agent.memory import async_session
        from agent.automation.models import MisionAutomation
        _, _, _, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        # Romper el enlace (deja la acción huérfana, misión sin accion_id)
        async with async_session() as s:
            await s.execute(update(MisionAutomation).where(MisionAutomation.id == mid)
                            .values(accion_id=None, estado="needs_approval"))
            await s.commit()

        out = await missions.reconciliar_misiones_recuperar_lead(OWNER)
        assert out["relinkeadas"] == 1
        m = await missions.obtener_mision(mid, OWNER)
        assert m["accion_id"] == aid

    async def test_needs_approval_sin_accion_ni_candidata_revierte_a_draft(self, env, monkeypatch):
        from sqlalchemy import update
        from agent.memory import async_session
        from agent.automation.models import MisionAutomation, AccionAutomatizacion
        _, _, _, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        # Romper enlace Y cancelar la acción (no hay candidata confirmable)
        async with async_session() as s:
            await s.execute(update(MisionAutomation).where(MisionAutomation.id == mid)
                            .values(accion_id=None, estado="needs_approval"))
            await s.execute(update(AccionAutomatizacion).where(AccionAutomatizacion.id == aid)
                            .values(estado="cancelled"))
            await s.commit()

        out = await missions.reconciliar_misiones_recuperar_lead(OWNER)
        assert out["revertidas"] == 1
        m = await missions.obtener_mision(mid, OWNER)
        assert m["estado"] == "draft"

    async def test_accion_huerfana_se_cancela(self, env, monkeypatch):
        """Acción mision-* confirmable cuya misión NO la apunta → cancelada."""
        from sqlalchemy import select, update
        from agent.memory import async_session
        from agent.automation.models import MisionAutomation, AccionAutomatizacion
        _, _, _, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        # La misión apunta a OTRA cosa (None) → la acción aid queda huérfana
        async with async_session() as s:
            await s.execute(update(MisionAutomation).where(MisionAutomation.id == mid)
                            .values(accion_id=None, estado="draft"))
            await s.commit()

        out = await missions.reconciliar_misiones_recuperar_lead(OWNER)
        assert out["canceladas"] == 1
        async with async_session() as s:
            acc = (await s.execute(
                select(AccionAutomatizacion).where(AccionAutomatizacion.id == aid)
            )).scalar_one()
        assert acc.estado == "cancelled"

    async def test_mision_terminal_no_reenvia(self, env, monkeypatch):
        """REGRESIÓN (Codex alta): una misión terminal blocked/failed con
        acción aún approved NO debe re-delegar ni enviar."""
        from sqlalchemy import update
        from agent.memory import async_session
        from agent.automation.models import MisionAutomation
        ac, sm, bi, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        # Forzar misión a 'failed' dejando la acción 'approved'
        async with async_session() as s:
            await s.execute(update(MisionAutomation).where(MisionAutomation.id == mid)
                            .values(estado="failed", reason_code="provider_failed"))
            await s.commit()
        r = await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        assert r["ok"] is False
        assert r["error"] == "mision_terminal"
        assert fake.invocaciones == []           # NO envió

    async def test_accion_ya_completed_sincroniza_mision(self, env, monkeypatch):
        """REGRESIÓN (Codex media): crash post-envío deja la acción completed
        y la misión needs_approval; confirmar debe SINCRONIZAR a completed
        (el confirmador devuelve accion_no_aprobada con estado=completed)."""
        ac, sm, bi, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        # Primer envío real → acción completed; luego forzamos la misión de
        # vuelta a needs_approval (simula crash antes de completar la misión).
        await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        from sqlalchemy import update
        from agent.memory import async_session
        from agent.automation.models import MisionAutomation
        async with async_session() as s:
            await s.execute(update(MisionAutomation).where(MisionAutomation.id == mid)
                            .values(estado="needs_approval", completed_at=None))
            await s.commit()

        r = await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        assert r["ok"] is True
        assert r["estado"] == "completed"
        assert len(fake.invocaciones) == 1       # NO re-envió
        m = await missions.obtener_mision(mid, OWNER)
        assert m["estado"] == "completed"

    async def test_reconciliacion_completa_mision_con_accion_completed(self, env, monkeypatch):
        ac, sm, bi, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        from sqlalchemy import update
        from agent.memory import async_session
        from agent.automation.models import MisionAutomation
        async with async_session() as s:
            await s.execute(update(MisionAutomation).where(MisionAutomation.id == mid)
                            .values(estado="needs_approval", completed_at=None))
            await s.commit()
        out = await missions.reconciliar_misiones_recuperar_lead(OWNER)
        assert out["completadas"] == 1
        assert (await missions.obtener_mision(mid, OWNER))["estado"] == "completed"

    async def test_reconciliacion_no_cancela_accion_de_otro_owner_enlazada(self, env, monkeypatch):
        """REGRESIÓN (Codex media owner-scope): la acción enlazada del OWNER
        no se cancela; correr la reconciliación de OTRO owner no la toca."""
        from sqlalchemy import select
        from agent.memory import async_session
        from agent.automation.models import AccionAutomatizacion
        ac, sm, bi, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        # La acción aid pertenece a OWNER y está correctamente enlazada.
        out_otro = await missions.reconciliar_misiones_recuperar_lead(OTRO)
        out_owner = await missions.reconciliar_misiones_recuperar_lead(OWNER)
        async with async_session() as s:
            acc = (await s.execute(
                select(AccionAutomatizacion).where(AccionAutomatizacion.id == aid)
            )).scalar_one()
        # Sigue confirmable (approved, la aprobó el helper) — NO cancelada.
        assert acc.estado == "approved"
        assert out_otro["canceladas"] == 0 and out_owner["canceladas"] == 0

    async def test_confirmar_corre_reconciliacion_preflight(self, env, monkeypatch):
        """confirmar_recuperar_lead sana needs_approval-sin-accion antes de
        delegar (relinkea y confirma en el mismo flujo)."""
        from sqlalchemy import update
        from agent.memory import async_session
        from agent.automation.models import MisionAutomation
        ac, sm, bi, missions = env
        mid, aid, fake = await _preparar_enlazar_aprobar(env, monkeypatch)
        async with async_session() as s:
            await s.execute(update(MisionAutomation).where(MisionAutomation.id == mid)
                            .values(accion_id=None, estado="needs_approval"))
            await s.commit()

        r = await missions.confirmar_recuperar_lead(mid, OWNER, "ENVIAR")
        assert r["ok"] is True
        assert r["estado"] == "completed"
        assert len(fake.invocaciones) == 1
