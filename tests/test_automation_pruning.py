# tests/test_automation_pruning.py — T2.1.D · Pruning seguro

"""
Tests del módulo agent.automation.pruning:
  - dry_run default · cuenta sin borrar
  - ejecutar_borrado=True borra hasta max_delete
  - dias muy bajo lanza ValueError (anti-borrado-corto)
  - audit log se conserva más tiempo (>= 90 días)
  - sólo borra estados terminales (no in-flight)
  - emite audit log 'pruning_executed' al borrar
"""

import importlib
from datetime import datetime, timedelta
import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "prun.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    import agent.automation.pruning as _pr
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_ac)
    importlib.reload(_pr)
    await agent.memory.inicializar_db()
    return _ac, _pr


async def _crear_accion_vieja(
    telefono: str, tipo: str, estado: str, dias_atras: int,
):
    """Crea acción terminal directamente con created_at viejo."""
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion
    fecha = datetime.utcnow() - timedelta(days=dias_atras)
    async with async_session() as session:
        a = AccionAutomatizacion(
            telefono=telefono,
            tipo_accion=tipo,
            titulo="Vieja",
            estado=estado,
            riesgo="low",
            created_at=fecha,
            updated_at=fecha,
        )
        session.add(a)
        await session.commit()
        await session.refresh(a)
        return a.id


async def _crear_audit_viejo(evento: str, dias_atras: int):
    from agent.memory import async_session
    from agent.automation.models import AuditLogAutomatizacion
    fecha = datetime.utcnow() - timedelta(days=dias_atras)
    async with async_session() as session:
        log = AuditLogAutomatizacion(
            telefono_short="*****",
            evento=evento,
            payload_summary="{}",
            created_at=fecha,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log.id


# ─── pruning_acciones ────────────────────────────────────────────────────


class TestPruningAcciones:
    @pytest.mark.asyncio
    async def test_dry_run_default_no_borra(self, db):
        ac, pr = db
        await _crear_accion_vieja("5550", "x", "completed", 200)
        await _crear_accion_vieja("5550", "y", "failed", 200)
        # default dry_run
        r = await pr.pruning_acciones(dias=180)
        assert r["dry_run"] is True
        assert r["candidatas"] == 2
        assert r["borradas"] == 0
        # filas siguen ahí
        accs = await ac.listar_acciones("5550")
        assert len(accs) == 2

    @pytest.mark.asyncio
    async def test_ejecutar_borrado_borra(self, db):
        ac, pr = db
        await _crear_accion_vieja("5551", "x", "completed", 200)
        await _crear_accion_vieja("5551", "y", "failed", 200)
        r = await pr.pruning_acciones(dias=180, ejecutar_borrado=True)
        assert r["dry_run"] is False
        assert r["borradas"] == 2
        accs = await ac.listar_acciones("5551")
        assert len(accs) == 0

    @pytest.mark.asyncio
    async def test_no_borra_acciones_recientes(self, db):
        ac, pr = db
        await _crear_accion_vieja("5552", "x", "completed", 30)
        # threshold 180 días · 30 días no califica
        r = await pr.pruning_acciones(dias=180, ejecutar_borrado=True)
        assert r["candidatas"] == 0
        accs = await ac.listar_acciones("5552")
        assert len(accs) == 1

    @pytest.mark.asyncio
    async def test_no_borra_acciones_no_terminales(self, db):
        ac, pr = db
        # pending y running son IN-FLIGHT · no se borran aunque sean viejas
        await _crear_accion_vieja("5553", "x", "pending", 200)
        await _crear_accion_vieja("5553", "y", "running", 200)
        await _crear_accion_vieja("5553", "z", "needs_approval", 200)
        r = await pr.pruning_acciones(dias=180, ejecutar_borrado=True)
        assert r["candidatas"] == 0
        accs = await ac.listar_acciones("5553")
        assert len(accs) == 3

    @pytest.mark.asyncio
    async def test_max_delete_limita_por_invocacion(self, db):
        ac, pr = db
        for i in range(10):
            await _crear_accion_vieja(f"556{i}", "x", "completed", 200)
        r = await pr.pruning_acciones(
            dias=180, max_delete=3, ejecutar_borrado=True,
        )
        assert r["borradas"] == 3
        assert r["candidatas"] == 10
        assert r["restantes"] == 7

    @pytest.mark.asyncio
    async def test_dias_muy_bajo_es_error(self, db):
        ac, pr = db
        with pytest.raises(ValueError):
            await pr.pruning_acciones(dias=15)

    @pytest.mark.asyncio
    async def test_max_delete_fuera_de_rango_error(self, db):
        ac, pr = db
        with pytest.raises(ValueError):
            await pr.pruning_acciones(dias=180, max_delete=0)
        with pytest.raises(ValueError):
            await pr.pruning_acciones(dias=180, max_delete=99999)


# ─── pruning_audit_log ───────────────────────────────────────────────────


class TestPruningAuditLog:
    @pytest.mark.asyncio
    async def test_dry_run_default(self, db):
        ac, pr = db
        await _crear_audit_viejo("action_completed", 400)
        r = await pr.pruning_audit_log(dias=365)
        assert r["dry_run"] is True
        assert r["candidatas"] == 1
        assert r["borradas"] == 0

    @pytest.mark.asyncio
    async def test_borra_audit_viejo(self, db):
        ac, pr = db
        await _crear_audit_viejo("action_completed", 400)
        await _crear_audit_viejo("action_failed", 400)
        r = await pr.pruning_audit_log(dias=365, ejecutar_borrado=True)
        # borra 2 + emite 1 audit propio (pruning_executed)
        assert r["borradas"] == 2

    @pytest.mark.asyncio
    async def test_dias_menor_a_90_es_error(self, db):
        ac, pr = db
        with pytest.raises(ValueError):
            await pr.pruning_audit_log(dias=30)
        with pytest.raises(ValueError):
            await pr.pruning_audit_log(dias=89)

    @pytest.mark.asyncio
    async def test_no_borra_audit_reciente(self, db):
        ac, pr = db
        await _crear_audit_viejo("action_completed", 30)
        r = await pr.pruning_audit_log(dias=365, ejecutar_borrado=True)
        assert r["borradas"] == 0


# ─── Audit log de pruning ────────────────────────────────────────────────


class TestAuditDePruning:
    @pytest.mark.asyncio
    async def test_pruning_emite_audit(self, db):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ac, pr = db
        await _crear_accion_vieja("5570", "x", "completed", 200)
        await pr.pruning_acciones(dias=180, ejecutar_borrado=True)
        async with agent.memory.async_session() as s:
            r = await s.execute(
                select(AuditLogAutomatizacion).where(
                    AuditLogAutomatizacion.evento == "pruning_executed"
                )
            )
            logs = list(r.scalars().all())
        assert len(logs) == 1
        assert "tabla" in logs[0].payload_summary
        assert "borradas" in logs[0].payload_summary

    @pytest.mark.asyncio
    async def test_dry_run_no_emite_audit(self, db):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ac, pr = db
        await _crear_accion_vieja("5571", "x", "completed", 200)
        await pr.pruning_acciones(dias=180)  # dry_run default
        async with agent.memory.async_session() as s:
            r = await s.execute(
                select(AuditLogAutomatizacion).where(
                    AuditLogAutomatizacion.evento == "pruning_executed"
                )
            )
            logs = list(r.scalars().all())
        assert len(logs) == 0
