# tests/test_automation_misiones_dossier.py — M0-5 · dossier de evidencia + métricas

"""
Tests de `dossier_mision` y `metricas_misiones` (M0-5, contrato Hermes): la
superficie mínima de Control Room. Read-only, owner-scoped, sin PII cruda.

Cubre la lista de Hermes para M0-5:
  - mission detail: estado, destino masked, acción enlazada, evidence status
  - completed_with_evidence True SOLO si están todos los eventos requeridos
  - no full phone/message en la salida
  - métricas: contadores por estado + completadas-con-evidencia (métrica norte)
    + reason_codes de bloqueadas
"""

from __future__ import annotations

import importlib

import pytest

import agent.memory


class FakeProveedor:
    def __init__(self, resultado=True):
        self.resultado = resultado
        self.invocaciones = []

    async def enviar_mensaje(self, telefono, mensaje):
        self.invocaciones.append((telefono, mensaje))
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
    db_path = tmp_path / "m05.db"
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

    import agent.llm as llm
    monkeypatch.setattr(llm, "_deepseek", _FakeDeepSeek())
    monkeypatch.setattr(llm, "_anthropic", None)
    return _ac, _sm, _bi, _missions


OWNER = "5215500001111"
OTRO = "5215599998888"
DESTINO = "+5215512345678"


def _mock_prov(monkeypatch, sm, fake):
    monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)


async def _mision_completada(env, monkeypatch, destino=DESTINO):
    """Happy path completo → misión completed con evidencia."""
    ac, sm, bi, missions = env
    fake = FakeProveedor(resultado=True)
    _mock_prov(monkeypatch, sm, fake)
    await bi.acreditar(OWNER, 50, "seed")
    r = await missions.preparar_recuperar_lead(
        telefono=OWNER, destino=destino, lead_nombre="Ana", contexto="pidió precio",
    )
    link = await missions.enlazar_accion_high_recuperar_lead(r["mision_id"], OWNER)
    await ac.aprobar_accion(link["accion_id"])
    await missions.confirmar_recuperar_lead(r["mision_id"], OWNER, "ENVIAR")
    return r["mision_id"]


# ── 1. Dossier owner-scoped ──────────────────────────────────────────────


class TestDossierOwnerScope:
    async def test_wrong_owner_none(self, env, monkeypatch):
        _, _, _, missions = env
        r = await missions.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        assert await missions.dossier_mision(r["mision_id"], OTRO) is None

    async def test_owner_ve_detalle(self, env, monkeypatch):
        _, _, _, missions = env
        r = await missions.preparar_recuperar_lead(
            telefono=OWNER, destino=DESTINO, lead_nombre="Ana",
        )
        d = await missions.dossier_mision(r["mision_id"], OWNER)
        assert d["mision_id"] == r["mision_id"]
        assert d["estado"] == "draft"
        assert d["tiene_draft"] is True


# ── 2. completed_with_evidence ───────────────────────────────────────────


class TestEvidencia:
    async def test_draft_no_tiene_evidencia_completa(self, env, monkeypatch):
        _, _, _, missions = env
        r = await missions.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        d = await missions.dossier_mision(r["mision_id"], OWNER)
        assert d["evidencia"]["completed_with_evidence"] is False
        assert "mission_recover_lead_completed" in d["evidencia"]["faltantes"]
        # los eventos ya ocurridos sí aparecen como presentes
        assert "mission_recover_lead_created" in d["evidencia"]["presentes"]
        assert "mission_recover_lead_draft_created" in d["evidencia"]["presentes"]

    async def test_completada_tiene_evidencia_completa(self, env, monkeypatch):
        _, _, _, missions = env
        mid = await _mision_completada(env, monkeypatch)
        d = await missions.dossier_mision(mid, OWNER)
        assert d["estado"] == "completed"
        assert d["evidencia"]["completed_with_evidence"] is True
        assert d["evidencia"]["faltantes"] == []
        # incluye la prueba del envío real
        assert "high_execution_succeeded" in d["evidencia"]["presentes"]
        assert "mission_recover_lead_completed" in d["evidencia"]["presentes"]


# ── 3. Sin PII cruda en el dossier ───────────────────────────────────────


class TestSinPII:
    async def test_dossier_no_expone_destino_crudo(self, env, monkeypatch):
        _, _, _, missions = env
        mid = await _mision_completada(env, monkeypatch)
        d = await missions.dossier_mision(mid, OWNER)
        import json
        blob = json.dumps(d, ensure_ascii=False)
        assert DESTINO not in blob              # nunca el número completo
        assert d["destino_masked"]              # sí el enmascarado
        assert "destino" not in d               # sin clave de destino crudo


# ── 4. Métricas ──────────────────────────────────────────────────────────


class TestMetricas:
    async def test_contadores_por_estado_y_evidencia(self, env, monkeypatch):
        _, _, _, missions = env
        # 1 completada con evidencia
        await _mision_completada(env, monkeypatch)
        # 1 en draft (sin completar)
        await missions.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        # 1 bloqueada por destino inválido (no crea misión) → usar marcar_bloqueada
        rb = await missions.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        await missions.marcar_bloqueada(rb["mision_id"], OWNER, "third_party_consent_required")

        m = await missions.metricas_misiones(OWNER)
        assert m["completadas"] == 1
        assert m["completadas_con_evidencia"] == 1     # métrica norte
        assert m["bloqueadas"] == 1
        assert m["por_estado"].get("draft", 0) == 1
        assert m["reason_codes"].get("third_party_consent_required") == 1
        assert m["total"] == 3

    async def test_metricas_owner_scoped(self, env, monkeypatch):
        _, _, _, missions = env
        await _mision_completada(env, monkeypatch)         # OWNER
        await missions.preparar_recuperar_lead(telefono=OTRO, destino=DESTINO)  # OTRO
        m_owner = await missions.metricas_misiones(OWNER)
        m_otro = await missions.metricas_misiones(OTRO)
        assert m_owner["total"] == 1 and m_owner["completadas"] == 1
        assert m_otro["total"] == 1 and m_otro["completadas"] == 0

    async def test_completada_sin_eventos_no_cuenta_como_con_evidencia(self, env, monkeypatch):
        """Una misión forzada a 'completed' SIN el rastro de eventos NO cuenta
        como completada-con-evidencia (la métrica norte exige evidencia real,
        no solo el estado)."""
        from sqlalchemy import update
        from agent.memory import async_session
        from agent.automation.models import MisionAutomation
        _, _, _, missions = env
        r = await missions.preparar_recuperar_lead(telefono=OWNER, destino=DESTINO)
        async with async_session() as s:
            await s.execute(update(MisionAutomation).where(MisionAutomation.id == r["mision_id"])
                            .values(estado="completed"))
            await s.commit()
        m = await missions.metricas_misiones(OWNER)
        assert m["completadas"] == 1
        assert m["completadas_con_evidencia"] == 0     # falta high_execution_succeeded etc.
