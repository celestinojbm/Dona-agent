# tests/test_automation_misiones.py — M0-1 · Mission Runtime recuperar-lead

"""
Tests del modelo/estado de misión (M0-1, spec Hermes). Cubre:
  - crear misión recuperar_lead owner-scoped → estado inicial seguro (draft)
  - lectura OWNER-SCOPED: wrong owner recibe None (no revela existencia)
  - audit SIN PII: el destino/teléfono completo nunca aparece en el audit
    log; solo el enmascarado
  - estados y reason codes CERRADOS (razón inválida → AssertionError)
  - cierre seguro blocked/failed + idempotencia sobre terminales
  - NO envío / NO provider en esta capa

Todos los tests usan SQLite en archivo temporal con módulos recargados, el
patrón estándar del repo. No hay provider ni LLM real involucrado.
"""

from __future__ import annotations

import importlib

import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """SQLite aislada + módulos de misión recargados. Sin provider/LLM."""
    db_path = tmp_path / "misiones.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("AUTOMATION_SCHEDULER_ENABLED", raising=False)

    import agent.automation.models as _models
    import agent.automation.audit as _audit
    import agent.automation.missions as _missions
    importlib.reload(agent.memory)
    importlib.reload(_models)
    importlib.reload(_audit)
    importlib.reload(_missions)
    await agent.memory.inicializar_db()
    return _missions


OWNER = "5215500001111"
OTRO = "5215599998888"
DESTINO = "+5215512345678"


async def _audit_rows():
    """Lee el audit log completo (para verificar que no filtra PII)."""
    from sqlalchemy import select
    from agent.memory import async_session
    from agent.automation.models import AuditLogAutomatizacion

    async with async_session() as session:
        rows = (await session.execute(
            select(AuditLogAutomatizacion)
        )).scalars().all()
        return [(r.evento, r.telefono_short, r.payload_summary) for r in rows]


# ── 1. Creación + estado inicial seguro ──────────────────────────────────


class TestCreacion:
    async def test_crea_mision_draft_owner_correcto(self, db):
        m = await db.crear_mision_recuperar_lead(
            telefono=OWNER, destino=DESTINO, lead_nombre="Ana",
            contexto="pidió precio y no compró", objetivo="retomar compra",
        )
        assert m["created"] is True
        assert m["tipo"] == "recuperar_lead"
        assert m["estado"] == "draft"          # estado inicial seguro
        assert m["telefono"] == OWNER
        assert m["accion_id"] is None          # sin acción HIGH todavía
        assert m["reason_code"] == ""
        assert m["id"] > 0

    async def test_estado_inicial_nunca_es_ejecutable(self, db):
        """El draft jamás arranca en un estado que habilite envío."""
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        assert m["estado"] not in ("approved", "sending", "completed")

    async def test_emite_evento_created(self, db):
        await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        eventos = [e for (e, _, _) in await _audit_rows()]
        assert "mission_recover_lead_created" in eventos


# ── 2. Lectura owner-scoped (wrong-owner no revela nada) ─────────────────


class TestOwnerScope:
    async def test_owner_correcto_lee(self, db):
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        leida = await db.obtener_mision(m["id"], OWNER)
        assert leida is not None
        assert leida["id"] == m["id"]

    async def test_wrong_owner_recibe_none(self, db):
        """REGRESIÓN (modo de fallo wrong-owner): otro dueño NO ve la misión
        ni su existencia."""
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        assert await db.obtener_mision(m["id"], OTRO) is None

    async def test_listar_es_owner_scoped(self, db):
        await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        await db.crear_mision_recuperar_lead(telefono=OTRO, destino=DESTINO)
        assert len(await db.listar_misiones(OWNER)) == 2
        assert len(await db.listar_misiones(OTRO)) == 1


# ── 3. Audit sin PII (destino/teléfono nunca crudos) ─────────────────────


class TestAuditSinPII:
    async def test_audit_no_contiene_destino_completo(self, db):
        await db.crear_mision_recuperar_lead(
            telefono=OWNER, destino=DESTINO, lead_nombre="Ana Pérez",
        )
        for evento, tel_short, summary in await _audit_rows():
            assert DESTINO not in summary
            assert OWNER not in summary
            assert OWNER not in tel_short        # truncado
            assert "Ana Pérez" not in summary    # nombre del lead tampoco

    async def test_audit_usa_destino_enmascarado(self, db):
        await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        summaries = " ".join(s for (_, _, s) in await _audit_rows())
        assert db.destino_masked(DESTINO) in summaries

    def test_destino_masked_no_revela_numero(self, db):
        masked = db.destino_masked(DESTINO)
        assert DESTINO not in masked
        assert masked.count("*") >= 1
        # cortos → completamente ocultos
        assert db.destino_masked("123") == "***"


# ── 4. Estados y reason codes cerrados ───────────────────────────────────


class TestSetsCerrados:
    async def test_bloquear_con_razon_cerrada(self, db):
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        r = await db.marcar_bloqueada(m["id"], OWNER, "third_party_consent_required")
        assert r["estado"] == "blocked"
        assert r["reason_code"] == "third_party_consent_required"

    async def test_fallar_con_razon_cerrada(self, db):
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        r = await db.marcar_fallida(m["id"], OWNER, "provider_failed")
        assert r["estado"] == "failed"
        assert r["reason_code"] == "provider_failed"

    async def test_razon_no_cerrada_es_rechazada(self, db):
        """Una razón fuera del set cerrado revienta con ValueError (NO
        AssertionError: un assert se borra bajo `python -O` y el set cerrado
        se volvería fail-open en prod optimizada — hallazgo de Codex)."""
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        with pytest.raises(ValueError):
            await db.marcar_bloqueada(m["id"], OWNER, "razon_inventada_xyz")

    def test_sets_cerrados_declarados(self, db):
        assert "blocked" in db.ESTADOS_MISION and "failed" in db.ESTADOS_MISION
        assert "third_party_consent_required" in db.REASON_CODES_MISION
        assert "wrong_owner" in db.REASON_CODES_MISION


# ── 5. Cierre seguro: owner-scope + idempotencia ─────────────────────────


class TestCierreSeguro:
    async def test_cerrar_mision_ajena_no_hace_nada(self, db):
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        assert await db.marcar_bloqueada(m["id"], OTRO, "policy_blocked") is None
        # La misión del owner sigue en draft (no fue tocada)
        assert (await db.obtener_mision(m["id"], OWNER))["estado"] == "draft"

    async def test_terminal_no_se_recierra(self, db):
        """Una misión ya terminal es idempotente: no cambia de razón ni
        re-emite evento."""
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        await db.marcar_fallida(m["id"], OWNER, "provider_failed")
        # Segundo intento con otra razón: no la pisa
        r2 = await db.marcar_bloqueada(m["id"], OWNER, "policy_blocked")
        assert r2["estado"] == "failed"
        assert r2["reason_code"] == "provider_failed"
        # Un solo evento de cierre (failed), no dos
        eventos = [e for (e, _, _) in await _audit_rows()]
        assert eventos.count("mission_recover_lead_failed") == 1
        assert "mission_recover_lead_blocked" not in eventos
