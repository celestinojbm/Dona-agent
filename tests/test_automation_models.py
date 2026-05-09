# tests/test_automation_models.py — T2.1.A · Migración runtime + modelos

import importlib
import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "models.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _bm
    import agent.automation.models as _am
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    await agent.memory.inicializar_db()
    return agent.memory


class TestMigracionRuntime:
    @pytest.mark.asyncio
    async def test_tabla_acciones_existe(self, db):
        from sqlalchemy import text
        async with db.engine.begin() as conn:
            r = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' "
                     "AND name='acciones_automatizacion'")
            )
            rows = r.fetchall()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_tabla_audit_log_existe(self, db):
        from sqlalchemy import text
        async with db.engine.begin() as conn:
            r = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' "
                     "AND name='audit_log_automatizacion'")
            )
            rows = r.fetchall()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_columnas_acciones_completas(self, db):
        from sqlalchemy import text
        async with db.engine.begin() as conn:
            r = await conn.execute(text("PRAGMA table_info(acciones_automatizacion)"))
            cols = {row[1] for row in r.fetchall()}
        esperadas = {
            "id", "telefono", "opportunity_id", "playbook_id", "tipo_accion",
            "titulo", "descripcion", "razon_recomendacion", "estado",
            "riesgo", "costo_creditos_estimado", "requires_approval",
            "payload_json", "result_json", "error_message",
            "idempotency_key", "created_at", "updated_at",
            "approved_at", "rejected_at", "completed_at",
        }
        faltantes = esperadas - cols
        assert not faltantes, f"Faltan columnas: {faltantes}"

    @pytest.mark.asyncio
    async def test_columnas_audit_completas(self, db):
        from sqlalchemy import text
        async with db.engine.begin() as conn:
            r = await conn.execute(text("PRAGMA table_info(audit_log_automatizacion)"))
            cols = {row[1] for row in r.fetchall()}
        esperadas = {
            "id", "telefono_short", "evento", "accion_id", "riesgo",
            "payload_summary", "created_at",
        }
        faltantes = esperadas - cols
        assert not faltantes, f"Faltan columnas: {faltantes}"


class TestMigracionesAutomationEnLista:
    def test_migraciones_automation_se_pueden_importar(self):
        from agent.automation.models import MIGRACIONES_AUTOMATION
        assert isinstance(MIGRACIONES_AUTOMATION, list)
        assert len(MIGRACIONES_AUTOMATION) >= 2

    def test_memory_concatena_automation(self):
        # Verifica que agent/memory.py tiene el import
        import agent.memory as _m
        import inspect
        src = inspect.getsource(_m._migrar_columnas)
        assert "MIGRACIONES_AUTOMATION" in src
