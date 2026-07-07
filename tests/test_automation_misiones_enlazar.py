# tests/test_automation_misiones_enlazar.py — M0-3 · enlazar acción HIGH

"""
Tests de `enlazar_accion_high_recuperar_lead` (M0-3, contrato Hermes): compone
la acción HIGH `enviar_mensaje_whatsapp` con el draft de la misión y la enlaza,
en estado `needs_approval`. NO envía, NO aprueba.

Cubre la lista de Hermes para M0-3:
  - la acción enlazada es riesgo HIGH y la misión guarda accion_id
  - el generic execute sigue bloqueado (dedicated_confirmation_required)
  - la política de terceros que niega por límite duro bloquea la misión
  - el payload de la acción no filtra PII en audit
  - bloqueo explícito y testeado: wrong-owner, misión inexistente, draft ausente
  - idempotencia: re-enlazar devuelve la misma acción
  - idempotency_key única por misión (dos misiones ≠ acción)

El LLM del draft se mockea (vía M0-2); ningún provider de WhatsApp se toca.
"""

from __future__ import annotations

import importlib

import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "misiones_link.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("AUTOMATION_SCHEDULER_ENABLED", raising=False)
    for v in ("DONA_LLM_COST_KILL_SWITCH", "BUDGET_MAX_LLM_AUX_CALLS_MENSAJE"):
        monkeypatch.delenv(v, raising=False)

    import agent.automation.models as _models
    import agent.automation.audit as _audit
    import agent.automation.action_center as _ac
    import agent.automation.missions as _missions
    import agent.automation.executors.send_message as _sm
    import agent.presupuesto_runtime as _pr
    importlib.reload(agent.memory)
    importlib.reload(_models)
    importlib.reload(_audit)
    importlib.reload(_ac)
    importlib.reload(_sm)
    importlib.reload(_missions)
    _pr._contadores_eventos.clear()
    await agent.memory.inicializar_db()
    return _missions


OWNER = "5215500001111"
OTRO = "5215599998888"
DESTINO = "+5215512345678"


class _FakeHaikuLLM:
    def __init__(self, texto="Hola, quedé pendiente de tu consulta, ¿la retomamos?"):
        self.llamadas = 0
        cliente = self

        class _Messages:
            async def create(self, **kwargs):
                cliente.llamadas += 1

                class _R:
                    class usage:
                        input_tokens = 30
                        output_tokens = 30
                    content = [type("B", (), {"text": texto})()]
                return _R()

        self.messages = _Messages()


@pytest.fixture
def llm_mock(monkeypatch):
    import agent.llm as llm
    fake = _FakeHaikuLLM()
    monkeypatch.setattr(llm, "_anthropic", fake)
    return fake


async def _preparar(db, telefono=OWNER, destino=DESTINO):
    """Crea una misión con draft listo (M0-2) y devuelve su id."""
    r = await db.preparar_recuperar_lead(
        telefono=telefono, destino=destino, lead_nombre="Ana",
        contexto="pidió precio", objetivo="retomar",
    )
    assert r["ok"] is True
    return r["mision_id"]


async def _audit_rows():
    from sqlalchemy import select
    from agent.memory import async_session
    from agent.automation.models import AuditLogAutomatizacion
    async with async_session() as session:
        rows = (await session.execute(select(AuditLogAutomatizacion))).scalars().all()
        return [(r.evento, r.telefono_short, r.payload_summary) for r in rows]


# ── 1. Happy path: enlaza acción HIGH needs_approval ─────────────────────


class TestEnlaceOk:
    async def test_enlaza_accion_high_needs_approval(self, db, llm_mock):
        mid = await _preparar(db)
        r = await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        assert r["ok"] is True
        assert r["estado"] == "needs_approval"
        assert r["accion_id"] > 0
        assert r["next_required_action"] == "aprobar_y_confirmar_envio_dedicado"

    async def test_mision_guarda_accion_id_y_estado(self, db, llm_mock):
        mid = await _preparar(db)
        r = await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        m = await db.obtener_mision(mid, OWNER)
        assert m["accion_id"] == r["accion_id"]
        assert m["estado"] == "needs_approval"

    async def test_accion_enlazada_es_high(self, db, llm_mock):
        from sqlalchemy import select
        from agent.memory import async_session
        from agent.automation.models import AccionAutomatizacion
        mid = await _preparar(db)
        r = await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        async with async_session() as s:
            acc = (await s.execute(
                select(AccionAutomatizacion).where(AccionAutomatizacion.id == r["accion_id"])
            )).scalar_one()
        assert acc.tipo_accion == "enviar_mensaje_whatsapp"
        assert acc.riesgo == "high"
        assert acc.estado == "needs_approval"


# ── 2. Generic HIGH sigue bloqueado ──────────────────────────────────────


class TestGenericHighBloqueado:
    async def test_accion_aprobada_requiere_confirmacion_dedicada(self, db, llm_mock):
        """Aun aprobada, la acción HIGH no se ejecuta por el control genérico:
        queda en dedicated_confirmation_required (no hay bypass)."""
        from agent.automation.permissions import calcular_next_required_action
        mid = await _preparar(db)
        r = await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        # needs_approval → approval_required; approved → dedicated_confirmation_required
        nra, _ = calcular_next_required_action("approved", "high")
        assert nra == "dedicated_confirmation_required"
        # y en needs_approval el control genérico solo pide aprobación
        nra2, _ = calcular_next_required_action("needs_approval", "high")
        assert nra2 == "approval_required"


# ── 3. Política de terceros (límite duro) bloquea ────────────────────────


class TestPoliticaBloquea:
    async def test_limite_destino_bloquea_mision_sin_crear_accion(self, db, llm_mock):
        """Con el límite por destino frío agotado (2/día), enlazar bloquea la
        misión y NO crea acción."""
        from agent.memory import async_session
        from agent.automation.models import EnvioTerceroAutomation, AccionAutomatizacion
        from agent.automation.consent_terceros import normalizar_destino
        from datetime import datetime
        from sqlalchemy import select

        mid = await _preparar(db)
        # Sembrar 2 envíos hoy a este destino (frío) → límite diario agotado
        dest_norm = normalizar_destino(DESTINO)
        async with async_session() as s:
            for _ in range(2):
                s.add(EnvioTerceroAutomation(
                    telefono_owner="otro_owner", destino=dest_norm,
                    accion_id=None, enviado_en=datetime.utcnow(),
                ))
            await s.commit()

        r = await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        assert r["ok"] is False
        assert r["reason_code"] == "policy_blocked"
        m = await db.obtener_mision(mid, OWNER)
        assert m["estado"] == "blocked"
        async with async_session() as s:
            acciones = (await s.execute(select(AccionAutomatizacion))).scalars().all()
        assert acciones == []   # no se creó acción


# ── 4. Bloqueos explícitos: owner, inexistente, draft ausente ────────────


class TestBloqueosExplicitos:
    async def test_wrong_owner_no_enlaza(self, db, llm_mock):
        mid = await _preparar(db)
        r = await db.enlazar_accion_high_recuperar_lead(mid, OTRO)
        assert r["ok"] is False
        assert r["error"] == "mision_no_existe_o_ajena"
        # La misión del owner sigue en draft (no fue tocada)
        assert (await db.obtener_mision(mid, OWNER))["estado"] == "draft"

    async def test_mision_inexistente(self, db, llm_mock):
        r = await db.enlazar_accion_high_recuperar_lead(999999, OWNER)
        assert r["ok"] is False
        assert r["error"] == "mision_no_existe_o_ajena"

    async def test_draft_ausente_no_enlaza(self, db, llm_mock):
        """Una misión creada sin preparar (M0-1, sin draft) no se puede
        enlazar."""
        m = await db.crear_mision_recuperar_lead(telefono=OWNER, destino=DESTINO)
        r = await db.enlazar_accion_high_recuperar_lead(m["id"], OWNER)
        assert r["ok"] is False
        assert r["error"] == "draft_ausente"


# ── 5. Idempotencia ──────────────────────────────────────────────────────


class TestIdempotencia:
    async def test_re_enlazar_devuelve_misma_accion(self, db, llm_mock):
        mid = await _preparar(db)
        r1 = await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        r2 = await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        assert r2["accion_id"] == r1["accion_id"]
        assert r2.get("idempotent") is True

    async def test_dos_misiones_acciones_distintas(self, db, llm_mock):
        """Dos misiones del mismo owner el mismo día → acciones DISTINTAS
        (opportunity_id único evita la colisión de idempotency_key)."""
        mid1 = await _preparar(db)
        mid2 = await _preparar(db)
        r1 = await db.enlazar_accion_high_recuperar_lead(mid1, OWNER)
        r2 = await db.enlazar_accion_high_recuperar_lead(mid2, OWNER)
        assert r1["accion_id"] != r2["accion_id"]

    async def test_enlace_concurrente_no_deja_accion_high_confirmable(self, db, llm_mock):
        """REGRESIÓN (hallazgo Codex): dos enlaces CONCURRENTES de la misma
        misión no deben dejar dos acciones HIGH confirmables. El claim atómico
        deja UNA enlazada; la otra queda cancelada (no enviable)."""
        import asyncio
        from sqlalchemy import select
        from agent.memory import async_session
        from agent.automation.models import AccionAutomatizacion

        mid = await _preparar(db)
        r1, r2 = await asyncio.gather(
            db.enlazar_accion_high_recuperar_lead(mid, OWNER),
            db.enlazar_accion_high_recuperar_lead(mid, OWNER),
        )
        # Ninguna llamada falla: una enlaza, la otra es idempotente o queda
        # "enlace_en_proceso" (el ganador estaba creando la acción).
        assert r1["ok"] is True and r2["ok"] is True

        # Tras completar ambas, la misión tiene EXACTAMENTE una acción y está
        # enlazada; cualquier accion_id devuelto coincide con ella.
        m = await db.obtener_mision(mid, OWNER)
        assert m["accion_id"] is not None
        for r in (r1, r2):
            if r.get("accion_id") is not None:
                assert r["accion_id"] == m["accion_id"]

        # Invariante núcleo (claim-first: el perdedor NO crea acción): existe
        # UNA sola acción confirmable y es la enlazada — cero huérfanas.
        async with async_session() as s:
            acciones = (await s.execute(select(AccionAutomatizacion))).scalars().all()
        confirmables = [a for a in acciones if a.estado in ("needs_approval", "approved")]
        assert len(confirmables) == 1
        assert confirmables[0].id == m["accion_id"]


# ── 6. Audit sin PII ─────────────────────────────────────────────────────


class TestAuditSinPII:
    async def test_audit_no_filtra_destino_ni_mensaje(self, db, llm_mock):
        mid = await _preparar(db)
        await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        for evento, tel_short, summary in await _audit_rows():
            assert DESTINO not in summary
            assert OWNER not in summary
            assert OWNER not in tel_short

    async def test_evento_action_linked_emitido(self, db, llm_mock):
        mid = await _preparar(db)
        await db.enlazar_accion_high_recuperar_lead(mid, OWNER)
        eventos = [e for (e, _, _) in await _audit_rows()]
        assert "mission_recover_lead_action_linked" in eventos
