# tests/test_automation_creditos_reservas.py — T2.1.D

"""
Tests del sistema de reservas de créditos:
  - reserva exitosa descuenta y registra
  - saldo insuficiente bloquea con error claro
  - idempotencia: re-llamar reservar() no duplica ni cobra de nuevo
  - liberar() acredita de vuelta
  - confirmar() no toca saldo (ya estaba descontado)
  - integración con execution.ejecutar_accion:
      * éxito: descuenta y confirma
      * fallo: descuenta inicialmente y libera (acredita de vuelta)
      * insuficiente: bloquea sin descontar
      * CRITICAL: bloquea + libera reserva
      * HIGH sin ejecutor: bloquea + libera reserva
  - audit log emitido para cada evento
"""

import importlib
import json
import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "creds.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    import agent.automation.credits as _cr
    import agent.automation.execution as _ex
    import agent.billing as _bi
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_ac)
    importlib.reload(_cr)
    importlib.reload(_bi)
    importlib.reload(_ex)
    await agent.memory.inicializar_db()
    return _ac, _cr, _ex, _bi


def _patch_llm_returns(monkeypatch, value):
    async def fake(*args, **kwargs):
        return value
    import agent.llm
    monkeypatch.setattr(agent.llm, "completar_con_sistema", fake)


# ─── Reserva directa ──────────────────────────────────────────────────────


class TestReservaDirecta:
    @pytest.mark.asyncio
    async def test_reserva_descuenta_y_registra(self, db):
        ac, cr, ex, bi = db
        await bi.acreditar("5551", 50, "seed")
        a = await ac.crear_accion(
            telefono="5551",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        # generar_plan_semanal cuesta 8 según costos.py
        r = await cr.reservar(
            accion_id=a["id"], telefono="5551", creditos=8,
            razon="test",
        )
        assert r["estado"] == "pending"
        assert r["creditos"] == 8
        # Saldo bajó
        assert await bi.obtener_saldo("5551") == 42

    @pytest.mark.asyncio
    async def test_reservar_creditos_cero_no_descuenta(self, db):
        ac, cr, ex, bi = db
        await bi.acreditar("5552", 10, "seed")
        a = await ac.crear_accion(
            telefono="5552",
            tipo_accion="generar_plan_semanal",
            titulo="X",
        )
        r = await cr.reservar(
            accion_id=a["id"], telefono="5552", creditos=0, razon="gratis",
        )
        assert r["estado"] == "pending"
        assert r["creditos"] == 0
        # Saldo intacto
        assert await bi.obtener_saldo("5552") == 10


class TestSaldoInsuficiente:
    @pytest.mark.asyncio
    async def test_sin_saldo_lanza_error(self, db):
        ac, cr, ex, bi = db
        a = await ac.crear_accion(
            telefono="5560",
            tipo_accion="generar_plan_semanal",
            titulo="X",
        )
        with pytest.raises(cr.CreditosInsuficientesError) as exc:
            await cr.reservar(
                accion_id=a["id"], telefono="5560", creditos=10,
                razon="test",
            )
        assert exc.value.requerido == 10
        assert exc.value.saldo == 0
        # No descontó
        assert await bi.obtener_saldo("5560") == 0
        # Pero registró fila 'failed' para audit
        rsv = await cr.obtener_reserva(a["id"])
        assert rsv is not None
        assert rsv["estado"] == "failed"

    @pytest.mark.asyncio
    async def test_saldo_parcial_lanza_error_sin_descontar(self, db):
        ac, cr, ex, bi = db
        await bi.acreditar("5561", 5, "seed")
        a = await ac.crear_accion(
            telefono="5561",
            tipo_accion="generar_plan_semanal",
            titulo="X",
        )
        with pytest.raises(cr.CreditosInsuficientesError):
            await cr.reservar(
                accion_id=a["id"], telefono="5561", creditos=10,
                razon="test",
            )
        # Saldo intacto
        assert await bi.obtener_saldo("5561") == 5


class TestIdempotencia:
    @pytest.mark.asyncio
    async def test_re_reservar_misma_accion_no_duplica_cobro(self, db):
        ac, cr, ex, bi = db
        await bi.acreditar("5570", 30, "seed")
        a = await ac.crear_accion(
            telefono="5570",
            tipo_accion="generar_plan_semanal",
            titulo="X",
        )
        r1 = await cr.reservar(
            accion_id=a["id"], telefono="5570", creditos=8, razon="t",
        )
        r2 = await cr.reservar(
            accion_id=a["id"], telefono="5570", creditos=8, razon="t",
        )
        assert r1["id"] == r2["id"]
        # Saldo bajó SOLO una vez (30 - 8 = 22)
        assert await bi.obtener_saldo("5570") == 22

    @pytest.mark.asyncio
    async def test_idempotencia_tras_confirmar(self, db):
        ac, cr, ex, bi = db
        await bi.acreditar("5571", 30, "seed")
        a = await ac.crear_accion(
            telefono="5571",
            tipo_accion="generar_plan_semanal",
            titulo="X",
        )
        await cr.reservar(
            accion_id=a["id"], telefono="5571", creditos=8, razon="t",
        )
        await cr.confirmar(a["id"])
        # Re-reservar tras confirmar: idempotente · no vuelve a cobrar
        r = await cr.reservar(
            accion_id=a["id"], telefono="5571", creditos=8, razon="t",
        )
        assert r["estado"] == "confirmed"
        assert await bi.obtener_saldo("5571") == 22


class TestConfirmarLiberar:
    @pytest.mark.asyncio
    async def test_confirmar_no_toca_saldo(self, db):
        ac, cr, ex, bi = db
        await bi.acreditar("5580", 30, "seed")
        a = await ac.crear_accion(
            telefono="5580",
            tipo_accion="generar_plan_semanal",
            titulo="X",
        )
        await cr.reservar(
            accion_id=a["id"], telefono="5580", creditos=8, razon="t",
        )
        saldo_pre = await bi.obtener_saldo("5580")
        await cr.confirmar(a["id"])
        saldo_post = await bi.obtener_saldo("5580")
        assert saldo_pre == saldo_post == 22

    @pytest.mark.asyncio
    async def test_liberar_acredita_de_vuelta(self, db):
        ac, cr, ex, bi = db
        await bi.acreditar("5581", 30, "seed")
        a = await ac.crear_accion(
            telefono="5581",
            tipo_accion="generar_plan_semanal",
            titulo="X",
        )
        await cr.reservar(
            accion_id=a["id"], telefono="5581", creditos=8, razon="t",
        )
        assert await bi.obtener_saldo("5581") == 22
        await cr.liberar(a["id"], razon="ejecutor falló")
        # Reembolso completo
        assert await bi.obtener_saldo("5581") == 30
        rsv = await cr.obtener_reserva(a["id"])
        assert rsv["estado"] == "released"

    @pytest.mark.asyncio
    async def test_liberar_idempotente(self, db):
        ac, cr, ex, bi = db
        await bi.acreditar("5582", 30, "seed")
        a = await ac.crear_accion(
            telefono="5582",
            tipo_accion="generar_plan_semanal",
            titulo="X",
        )
        await cr.reservar(
            accion_id=a["id"], telefono="5582", creditos=8, razon="t",
        )
        await cr.liberar(a["id"], razon="x")
        saldo_pre = await bi.obtener_saldo("5582")
        # Segundo liberar: no acredita de nuevo
        await cr.liberar(a["id"], razon="x")
        assert await bi.obtener_saldo("5582") == saldo_pre


# ─── Integración con execution.ejecutar_accion ───────────────────────────


class TestEjecucionIntegrada:
    @pytest.mark.asyncio
    async def test_low_pending_exito_descuenta_y_confirma(self, db, monkeypatch):
        ac, cr, ex, bi = db
        _patch_llm_returns(monkeypatch, "# Plan\n## Lunes\n- A")
        await bi.acreditar("5600", 50, "seed")
        a = await ac.crear_accion(
            telefono="5600",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "completed"
        # Saldo bajó (50 - 8 = 42)
        assert await bi.obtener_saldo("5600") == 42
        # Reserva confirmada
        rsv = await cr.obtener_reserva(a["id"])
        assert rsv["estado"] == "confirmed"

    @pytest.mark.asyncio
    async def test_saldo_insuficiente_bloquea_sin_descontar(self, db, monkeypatch):
        ac, cr, ex, bi = db
        _patch_llm_returns(monkeypatch, None)
        # Sin acreditar · saldo = 0
        a = await ac.crear_accion(
            telefono="5601",
            tipo_accion="generar_plan_semanal",  # cuesta 8
            titulo="Plan",
        )
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "failed"
        assert r["error"] == "insufficient_credits"
        assert r["requerido"] == 8
        assert r["saldo"] == 0
        # Saldo intacto
        assert await bi.obtener_saldo("5601") == 0
        # Reserva quedó como failed
        rsv = await cr.obtener_reserva(a["id"])
        assert rsv["estado"] == "failed"

    @pytest.mark.asyncio
    async def test_excepcion_ejecutor_libera_reserva(self, db, monkeypatch):
        """Si el ejecutor lanza excepción · libera créditos."""
        ac, cr, ex, bi = db
        # Patch del ejecutor para que lance
        async def boom(*args, **kwargs):
            raise RuntimeError("boom interno")
        monkeypatch.setitem(
            ex.EJECUTORES_T21A, "generar_plan_semanal", boom,
        )
        await bi.acreditar("5602", 50, "seed")
        a = await ac.crear_accion(
            telefono="5602",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "failed"
        # Reembolso completo
        assert await bi.obtener_saldo("5602") == 50
        rsv = await cr.obtener_reserva(a["id"])
        assert rsv["estado"] == "released"

    @pytest.mark.asyncio
    async def test_critical_bloqueado_libera_reserva(self, db, monkeypatch):
        ac, cr, ex, bi = db
        _patch_llm_returns(monkeypatch, "x")
        await bi.acreditar("5603", 200, "seed")
        a = await ac.crear_accion(
            telefono="5603",
            tipo_accion="envio_masivo_clientes",  # CRITICAL · cuesta 100
            titulo="Mass",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5603")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "failed"
        # Reembolso completo: Critical bloqueado · liberada
        assert await bi.obtener_saldo("5603") == 200
        rsv = await cr.obtener_reserva(a["id"])
        assert rsv["estado"] == "released"

    @pytest.mark.asyncio
    async def test_high_sin_ejecutor_libera_reserva(self, db, monkeypatch):
        ac, cr, ex, bi = db
        await bi.acreditar("5604", 50, "seed")
        a = await ac.crear_accion(
            telefono="5604",
            tipo_accion="enviar_mensaje_whatsapp",  # HIGH · cuesta 6
            titulo="Send",
        )
        await ac.aprobar_accion(a["id"])
        listed = await ac.listar_acciones("5604")
        approved = [x for x in listed if x["id"] == a["id"]][0]
        r = await ex.ejecutar_accion(approved)
        assert r["estado_final"] == "failed"
        # Reembolso · sin ejecutor disponible · NO se cobra
        assert await bi.obtener_saldo("5604") == 50
        rsv = await cr.obtener_reserva(a["id"])
        assert rsv["estado"] == "released"

    @pytest.mark.asyncio
    async def test_re_ejecutar_misma_accion_no_doble_cobra(self, db, monkeypatch):
        """Idempotencia end-to-end: ejecutar dos veces la misma acción
        descuenta créditos solo una vez."""
        ac, cr, ex, bi = db
        _patch_llm_returns(monkeypatch, "# Plan\n## Lunes\n- A")
        await bi.acreditar("5605", 50, "seed")
        a = await ac.crear_accion(
            telefono="5605",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        await ex.ejecutar_accion(a)
        # Segunda invocación: la acción ya está completed · falla por
        # estado pero NO debería cobrar de nuevo
        listed = await ac.listar_acciones("5605")
        completed = [x for x in listed if x["id"] == a["id"]][0]
        r2 = await ex.ejecutar_accion(completed)
        assert r2["estado_final"] == "failed"
        # Saldo todavía 42 (un solo descuento)
        assert await bi.obtener_saldo("5605") == 42


# ─── Audit log ────────────────────────────────────────────────────────────


class TestAuditExtendido:
    @pytest.mark.asyncio
    async def test_eventos_de_reserva_se_registran(self, db, monkeypatch):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ac, cr, ex, bi = db
        _patch_llm_returns(monkeypatch, "# Plan")
        await bi.acreditar("5610", 50, "seed")
        a = await ac.crear_accion(
            telefono="5610",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        await ex.ejecutar_accion(a)
        async with agent.memory.async_session() as s:
            r = await s.execute(select(AuditLogAutomatizacion))
            eventos = {row.evento for row in r.scalars().all()}
        # Reserva creada y confirmada
        assert "credits_reserved" in eventos
        assert "credits_confirmed" in eventos

    @pytest.mark.asyncio
    async def test_evento_insuficiente_se_registra(self, db, monkeypatch):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ac, cr, ex, bi = db
        a = await ac.crear_accion(
            telefono="5611",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        await ex.ejecutar_accion(a)
        async with agent.memory.async_session() as s:
            r = await s.execute(select(AuditLogAutomatizacion))
            eventos = {row.evento for row in r.scalars().all()}
        assert "action_blocked_insufficient_credits" in eventos
        assert "credits_reservation_failed" in eventos

    @pytest.mark.asyncio
    async def test_evento_released_al_fallar_ejecutor(self, db, monkeypatch):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ac, cr, ex, bi = db

        async def boom(*args, **kwargs):
            raise RuntimeError("boom")
        monkeypatch.setitem(
            ex.EJECUTORES_T21A, "generar_plan_semanal", boom,
        )
        await bi.acreditar("5612", 50, "seed")
        a = await ac.crear_accion(
            telefono="5612",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        await ex.ejecutar_accion(a)
        async with agent.memory.async_session() as s:
            r = await s.execute(select(AuditLogAutomatizacion))
            eventos = {row.evento for row in r.scalars().all()}
        assert "credits_released" in eventos

    @pytest.mark.asyncio
    async def test_audit_no_incluye_pii_ni_secretos(self, db, monkeypatch):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ac, cr, ex, bi = db
        _patch_llm_returns(monkeypatch, "# Plan")
        await bi.acreditar("5215559999999", 50, "seed")
        a = await ac.crear_accion(
            telefono="5215559999999",
            tipo_accion="generar_plan_semanal",
            titulo="Plan",
        )
        await ex.ejecutar_accion(a)
        async with agent.memory.async_session() as s:
            r = await s.execute(select(AuditLogAutomatizacion))
            logs = list(r.scalars().all())
        for log in logs:
            assert "5215559999999" not in log.payload_summary
            assert "5215559999999" not in log.telefono_short
