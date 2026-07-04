# tests/test_automation_audit.py — T2.1.A · Audit Log

import importlib
import json
import logging
import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    await agent.memory.inicializar_db()
    return _au


class TestSanitizar:
    def test_descarta_claves_pii(self, db):
        d = {
            "telefono": "5215551234567",
            "email": "celes@test.com",
            "password": "dona-secret123",
            "stripe_secret_key": "sk_live_xxx",
            "tipo_accion": "generar_plan_semanal",  # esta SÍ debe quedar
        }
        out = db.sanitizar_payload(d)
        assert "telefono" not in out
        assert "email" not in out
        assert "password" not in out
        assert "stripe_secret_key" not in out
        assert out["tipo_accion"] == "generar_plan_semanal"

    def test_descarta_campos_onboarding_extendido(self, db):
        d = {
            "oferta_principal": "Pasteles para eventos",
            "cliente_ideal": "Familias en CDMX",
            "objetivo_mes": "10 ventas",
            "canales_actuales": "WhatsApp",
            "bloqueo_actual": "tiempo",
            "tareas_delegar": "seguimiento",
            "modo": "dry_run",
        }
        out = db.sanitizar_payload(d)
        assert "oferta_principal" not in out
        assert "cliente_ideal" not in out
        assert "objetivo_mes" not in out
        assert "canales_actuales" not in out
        assert "bloqueo_actual" not in out
        assert "tareas_delegar" not in out
        assert out["modo"] == "dry_run"

    def test_trunca_strings_largos(self, db):
        d = {"campo_x": "a" * 500}
        out = db.sanitizar_payload(d)
        assert len(out["campo_x"]) <= 203  # 200 + '...'

    def test_recursivo_dicts_anidados(self, db):
        d = {"outer": {"telefono": "5215551234567", "ok": "value"}}
        out = db.sanitizar_payload(d)
        assert "telefono" not in out["outer"]
        assert out["outer"]["ok"] == "value"

    def test_listas_de_dicts(self, db):
        d = {"items": [{"telefono": "5215551234567", "tipo": "x"},
                       {"email": "c@t.com", "tipo": "y"}]}
        out = db.sanitizar_payload(d)
        for item in out["items"]:
            assert "telefono" not in item
            assert "email" not in item

    def test_payload_none_retorna_dict_vacio(self, db):
        assert db.sanitizar_payload(None) == {}
        assert db.sanitizar_payload({}) == {}


class TestRegistrarEvento:
    @pytest.mark.asyncio
    async def test_registra_evento_valido(self, db):
        log_id = await db.registrar_evento(
            evento="action_created",
            telefono="5215551234567",
            accion_id=42,
            riesgo="low",
            payload={"tipo_accion": "generar_plan_semanal"},
        )
        assert log_id > 0

    @pytest.mark.asyncio
    async def test_evento_invalido_retorna_0(self, db):
        log_id = await db.registrar_evento(
            evento="evento_inexistente",
            telefono="5551",
        )
        assert log_id == 0

    @pytest.mark.asyncio
    async def test_telefono_se_trunca_en_db(self, db):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        await db.registrar_evento(
            evento="action_created",
            telefono="5215551234567",
        )
        async with agent.memory.async_session() as session:
            r = await session.execute(select(AuditLogAutomatizacion))
            log = r.scalars().first()
        assert log.telefono_short != "5215551234567"
        assert "5215551234567" not in log.telefono_short
        assert "*" in log.telefono_short

    @pytest.mark.asyncio
    async def test_payload_summary_es_json_sanitizado(self, db):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        await db.registrar_evento(
            evento="action_created",
            telefono="5551",
            payload={
                "tipo_accion": "preparar_mensaje_whatsapp",
                "telefono": "5215551234567",  # debe descartarse
                "oferta_principal": "Pasteles para eventos",  # descartar
            },
        )
        async with agent.memory.async_session() as session:
            r = await session.execute(select(AuditLogAutomatizacion))
            log = r.scalars().first()
        summary = json.loads(log.payload_summary)
        assert summary["tipo_accion"] == "preparar_mensaje_whatsapp"
        assert "telefono" not in summary
        assert "oferta_principal" not in summary

    @pytest.mark.asyncio
    async def test_payload_con_tipos_no_serializables_no_rompe_audit(self, db):
        """8.1 · el audit trail es promesa de producto ("audit HIGH
        incondicional"): un valor no JSON-serializable en el payload
        (datetime, Decimal, set) NUNCA debe romper la escritura del audit.
        `default=str` los estringiza en lugar de lanzar TypeError y perder
        el evento — crítico en flujos de dinero/HIGH donde el summary suele
        arrastrar montos (Decimal desde columnas Numeric) y timestamps."""
        from datetime import datetime as _dt
        from decimal import Decimal

        from sqlalchemy import select

        from agent.automation.models import AuditLogAutomatizacion

        log_id = await db.registrar_evento(
            evento="credits_reserved",
            telefono="5215551234567",
            riesgo="high",
            payload={
                "cuando": _dt(2026, 7, 4, 12, 0, 0),
                "monto": Decimal("10.5"),
                "tags": {"solo_un_elemento"},
                "creditos": 10,
            },
        )
        # Sin `default=str` esto lanzaba TypeError y el evento se perdía.
        assert log_id > 0
        async with agent.memory.async_session() as session:
            r = await session.execute(select(AuditLogAutomatizacion))
            log = r.scalars().first()
        summary = json.loads(log.payload_summary)  # debe ser JSON válido
        assert summary["creditos"] == 10
        assert "2026-07-04" in summary["cuando"]
        assert summary["monto"] == "10.5"

    @pytest.mark.asyncio
    async def test_no_loguea_pii_en_stdout(self, db, caplog):
        with caplog.at_level(logging.INFO, logger="dona"):
            caplog.clear()
            await db.registrar_evento(
                evento="action_created",
                telefono="5215551234567",
                accion_id=99,
                riesgo="medium",
                payload={
                    "telefono_completo": "5215551234567",
                    "oferta_principal": "secreto",
                },
            )
        for record in caplog.records:
            msg = record.getMessage()
            assert "5215551234567" not in msg
            assert "secreto" not in msg
