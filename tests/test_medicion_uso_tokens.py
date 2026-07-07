# tests/test_medicion_uso_tokens.py — TEMA 4 · 4.4
#
# "registrar_uso_tokens no-fire-and-forget con alerta": la MEDICIÓN del loop
# (tokens usados por llamada LLM) no puede perderse en silencio. Antes se
# disparaba con asyncio.create_task SIN referencia (una task así puede ni
# ejecutarse: el GC la puede recolectar) y los fallos se tragaban en
# logger.debug (invisible en prod). Estos tests fijan el contrato nuevo:
#   - un fallo de persistencia se CUENTA (snapshot_metricas_uso_tokens) y se
#     ALERTA en WARNING —nunca DEBUG—, sin relanzar (la medición no rompe la
#     respuesta, pero tampoco desaparece);
#   - el teléfono se enmascara en el log (no PII completa, TEMA 7.4);
#   - brain.py ya NO tiene el wrapper fire-and-forget (_registrar_tokens_bg).

import importlib
import logging

import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "medicion.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    await agent.memory.inicializar_db()
    return agent.memory


class TestContratoAlerta:
    def test_snapshot_expone_registrados_y_fallos(self):
        snap = agent.memory.snapshot_metricas_uso_tokens()
        assert "registrados" in snap
        assert "fallos" in snap
        # Copia inmutable: mutarla no toca el estado interno.
        snap["fallos"] = 999
        assert agent.memory.snapshot_metricas_uso_tokens()["fallos"] != 999

    @pytest.mark.asyncio
    async def test_fallo_de_db_se_contabiliza_y_alerta_sin_relanzar(
        self, monkeypatch, caplog
    ):
        base = agent.memory.snapshot_metricas_uso_tokens()["fallos"]

        # async_session() revienta al invocarse → simula DB caída.
        def _sesion_rota(*_a, **_k):
            raise RuntimeError("DB caída simulada")

        monkeypatch.setattr(agent.memory, "async_session", _sesion_rota)

        telefono = "5215512345678"
        with caplog.at_level(logging.WARNING, logger="dona"):
            # NO debe relanzar: la medición nunca rompe la respuesta.
            await agent.memory.registrar_uso_tokens(telefono, 100, 50)

        # Contabilizado como fallo (la "alerta" observable en /admin/metrics).
        assert agent.memory.snapshot_metricas_uso_tokens()["fallos"] == base + 1

        # Alertado en WARNING (o superior), no tragado en DEBUG.
        registros = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert registros, "el fallo de medición debe loguear en WARNING+"
        assert any("token" in r.getMessage().lower() for r in registros)

        # PII: el teléfono completo NO aparece en ningún log (TEMA 7.4).
        assert not any(telefono in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_exito_incrementa_registrados_y_persiste(self, db):
        base = db.snapshot_metricas_uso_tokens()["registrados"]

        await db.registrar_uso_tokens("5215500000001", 120, 30)

        assert db.snapshot_metricas_uso_tokens()["registrados"] == base + 1
        filas = await db.obtener_uso_tokens("5215500000001", dias=1)
        assert filas
        assert filas[0]["tokens_in"] == 120
        assert filas[0]["tokens_out"] == 30
        assert filas[0]["requests"] == 1

    @pytest.mark.asyncio
    async def test_acumula_en_mismo_dia_sin_perder_medicion(self, db):
        await db.registrar_uso_tokens("5215500000002", 10, 5)
        await db.registrar_uso_tokens("5215500000002", 7, 3)
        filas = await db.obtener_uso_tokens("5215500000002", dias=1)
        assert filas[0]["tokens_in"] == 17
        assert filas[0]["tokens_out"] == 8
        assert filas[0]["requests"] == 2


class TestSinFireAndForget:
    def test_brain_no_reintroduce_wrapper_fire_and_forget(self):
        import agent.brain as brain

        # El wrapper _registrar_tokens_bg encarnaba el anti-patrón (create_task
        # sin referencia + swallow en debug). No debe volver: la medición se
        # espera (await) en el path principal.
        assert not hasattr(brain, "_registrar_tokens_bg"), (
            "la medición de tokens no debe volver a ser fire-and-forget"
        )
