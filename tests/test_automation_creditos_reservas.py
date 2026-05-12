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
        # T2.2 conectó executor para enviar_mensaje_whatsapp · los
        # demás HIGH (contactar_lead, publicar_red_social,
        # enviar_campana_masiva) siguen sin ejecutor y deben liberar.
        a = await ac.crear_accion(
            telefono="5604",
            tipo_accion="contactar_lead",  # HIGH · cuesta 8
            titulo="Contact",
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


# ─── T2.1.D.1 · Reconciliación post-crash ─────────────────────────────────


async def _crear_reserva_preparing_huerfana(
    *, accion_id: int, telefono: str, creditos: int,
    edad_segundos: int = 0,
):
    """Inyecta una fila 'preparing' como si el proceso hubiera muerto
    entre _persistir_reserva(preparing) y el cobro/UPDATE final.
    edad_segundos controla la antigüedad de la fila.
    """
    from datetime import datetime, timedelta
    from agent.memory import async_session
    from agent.automation.models import ReservaCreditoAutomation
    creado = datetime.utcnow() - timedelta(seconds=edad_segundos)
    async with async_session() as s:
        r = ReservaCreditoAutomation(
            accion_id=accion_id,
            telefono=telefono,
            creditos=creditos,
            estado="preparing",
            razon="crash sim",
            transaccion_credito_id=None,
            creado=creado,
            actualizado=creado,
        )
        s.add(r)
        await s.commit()


async def _simular_cobro_sin_reserva(
    *, accion_id: int, telefono: str, creditos: int,
):
    """Simula que billing.cobrar ya commitó (saldo descontado + fila en
    transacciones_credito con job_id=accion_id) pero la reserva quedó
    huérfana en 'preparing' por un crash post-cobro.
    """
    from agent.billing import cobrar
    await cobrar(
        telefono, creditos,
        razon=f"reserva acción #{accion_id}: crash sim",
        asset_id=None, job_id=accion_id,
    )


class TestReconciliacionCrashEntreCobroYReserva:
    """Mitigación del riesgo residual: crash entre billing.cobrar() y
    el UPDATE final que avanza a 'pending'."""

    @pytest.mark.asyncio
    async def test_reconcilia_promueve_preparing_a_pending(self, db):
        """Caso A · cobro OK pero crash antes del UPDATE.
        reconciliar_accion encuentra la TransaccionCredito y avanza la
        reserva a 'pending' SIN volver a cobrar."""
        ac, cr, ex, bi = db
        await bi.acreditar("5800", 50, "seed")
        a = await ac.crear_accion(
            telefono="5800", tipo_accion="generar_plan_semanal",
            titulo="Crash A",
        )
        # 1. Simular write-ahead: fila preparing
        await _crear_reserva_preparing_huerfana(
            accion_id=a["id"], telefono="5800", creditos=8,
        )
        # 2. Simular que el cobro YA commitó (saldo -8, tx con job_id)
        await _simular_cobro_sin_reserva(
            accion_id=a["id"], telefono="5800", creditos=8,
        )
        assert await bi.obtener_saldo("5800") == 42

        # 3. Reconciliar
        r = await cr.reconciliar_accion(a["id"], max_edad_segundos=0)
        assert r is not None
        assert r["estado"] == "pending"
        assert r["transaccion_credito_id"] is not None
        # Saldo NO se vuelve a tocar (sin doble cobro)
        assert await bi.obtener_saldo("5800") == 42

    @pytest.mark.asyncio
    async def test_reconcilia_marca_failed_si_no_hay_tx_y_es_vieja(self, db):
        """Caso B · crash antes del cobro (no hay TransaccionCredito).
        Si la fila es vieja la marca 'failed' (saldo nunca se movió)."""
        ac, cr, ex, bi = db
        await bi.acreditar("5801", 50, "seed")
        a = await ac.crear_accion(
            telefono="5801", tipo_accion="generar_plan_semanal",
            titulo="Crash B",
        )
        await _crear_reserva_preparing_huerfana(
            accion_id=a["id"], telefono="5801", creditos=8,
            edad_segundos=300,
        )
        # NO se simula cobro · saldo intacto
        assert await bi.obtener_saldo("5801") == 50

        r = await cr.reconciliar_accion(a["id"], max_edad_segundos=120)
        assert r["estado"] == "failed"
        # Saldo intacto · no se descontó nada
        assert await bi.obtener_saldo("5801") == 50

    @pytest.mark.asyncio
    async def test_reconcilia_no_toca_preparing_reciente(self, db):
        """Una fila preparing reciente puede estar legítimamente en
        vuelo en otro worker · NO la toca."""
        ac, cr, ex, bi = db
        await bi.acreditar("5802", 50, "seed")
        a = await ac.crear_accion(
            telefono="5802", tipo_accion="generar_plan_semanal",
            titulo="Joven",
        )
        await _crear_reserva_preparing_huerfana(
            accion_id=a["id"], telefono="5802", creditos=8,
            edad_segundos=5,
        )

        r = await cr.reconciliar_accion(a["id"], max_edad_segundos=120)
        assert r["estado"] == "preparing"  # sin tocar

    @pytest.mark.asyncio
    async def test_reservar_post_crash_auto_reconcilia(self, db):
        """El worker reintenta ejecutar_accion · reservar() encuentra
        una reserva 'preparing' con cobro huérfano y la auto-promueve
        a 'pending' SIN re-cobrar."""
        ac, cr, ex, bi = db
        await bi.acreditar("5803", 50, "seed")
        a = await ac.crear_accion(
            telefono="5803", tipo_accion="generar_plan_semanal",
            titulo="Reintento",
        )
        await _crear_reserva_preparing_huerfana(
            accion_id=a["id"], telefono="5803", creditos=8,
        )
        await _simular_cobro_sin_reserva(
            accion_id=a["id"], telefono="5803", creditos=8,
        )
        assert await bi.obtener_saldo("5803") == 42

        # El worker reintenta · reservar() auto-reconcilia
        r = await cr.reservar(
            accion_id=a["id"], telefono="5803", creditos=8,
            razon="reintento",
        )
        assert r["estado"] == "pending"
        # Saldo NO cambia · sin doble cobro
        assert await bi.obtener_saldo("5803") == 42

    @pytest.mark.asyncio
    async def test_reconciliar_emite_audit(self, db):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ac, cr, ex, bi = db
        await bi.acreditar("5804", 50, "seed")
        a = await ac.crear_accion(
            telefono="5804", tipo_accion="generar_plan_semanal",
            titulo="Audit",
        )
        await _crear_reserva_preparing_huerfana(
            accion_id=a["id"], telefono="5804", creditos=8,
        )
        await _simular_cobro_sin_reserva(
            accion_id=a["id"], telefono="5804", creditos=8,
        )
        await cr.reconciliar_accion(a["id"], max_edad_segundos=0)

        async with agent.memory.async_session() as s:
            res = await s.execute(
                select(AuditLogAutomatizacion).where(
                    AuditLogAutomatizacion.evento
                    == "credits_reservation_reconciled"
                )
            )
            logs = list(res.scalars().all())
        assert len(logs) == 1
        assert "promoted_to_pending" in logs[0].payload_summary

    @pytest.mark.asyncio
    async def test_reconciliar_reservas_batch_promueve_y_falla(self, db):
        """Barrido batch · mezcla de filas con y sin tx, con distinta
        edad. Debe contar correctamente."""
        ac, cr, ex, bi = db
        await bi.acreditar("5805", 50, "seed_A")
        await bi.acreditar("5806", 50, "seed_B")
        await bi.acreditar("5807", 50, "seed_C")

        # A · preparing + cobro huérfano → promoted
        a1 = await ac.crear_accion(
            telefono="5805", tipo_accion="generar_plan_semanal",
            titulo="A",
        )
        await _crear_reserva_preparing_huerfana(
            accion_id=a1["id"], telefono="5805", creditos=8,
        )
        await _simular_cobro_sin_reserva(
            accion_id=a1["id"], telefono="5805", creditos=8,
        )

        # B · preparing viejo sin cobro → marked_failed
        a2 = await ac.crear_accion(
            telefono="5806", tipo_accion="generar_plan_semanal",
            titulo="B",
        )
        await _crear_reserva_preparing_huerfana(
            accion_id=a2["id"], telefono="5806", creditos=8,
            edad_segundos=300,
        )

        # C · preparing joven sin cobro → intacta
        a3 = await ac.crear_accion(
            telefono="5807", tipo_accion="generar_plan_semanal",
            titulo="C",
        )
        await _crear_reserva_preparing_huerfana(
            accion_id=a3["id"], telefono="5807", creditos=8,
            edad_segundos=5,
        )

        # Dry-run primero
        preview = await cr.reconciliar_reservas(
            max_edad_segundos=120, dry_run=True,
        )
        assert preview["dry_run"] is True
        assert preview["total_preparing"] == 3
        assert preview["promoted_estimado"] == 1
        assert preview["marked_failed_estimado"] == 1
        assert preview["intactas_estimado"] == 1

        # Ejecutar
        out = await cr.reconciliar_reservas(
            max_edad_segundos=120, dry_run=False,
        )
        assert out["dry_run"] is False
        assert out["promoted"] == 1
        assert out["marked_failed"] == 1
        assert out["intactas"] == 1

        # Estado final · A pending, B failed, C preparing
        rA = await cr.obtener_reserva(a1["id"])
        rB = await cr.obtener_reserva(a2["id"])
        rC = await cr.obtener_reserva(a3["id"])
        assert rA["estado"] == "pending"
        assert rB["estado"] == "failed"
        assert rC["estado"] == "preparing"


class TestWriteAheadOrden:
    """El nuevo flujo de reservar() debe persistir la fila ANTES del
    cobro · invariante crítico del fix T2.1.D.1."""

    @pytest.mark.asyncio
    async def test_si_cobro_falla_la_fila_existe_como_failed(self, db):
        """Si cobrar lanza SaldoInsuficienteError, la fila preparing
        debió persistir y debe quedar marcada 'failed' (no inexistente)."""
        ac, cr, ex, bi = db
        # Sin saldo · cobro fallará
        a = await ac.crear_accion(
            telefono="5810", tipo_accion="generar_plan_semanal",
            titulo="Sin saldo",
        )
        with pytest.raises(cr.CreditosInsuficientesError):
            await cr.reservar(
                accion_id=a["id"], telefono="5810", creditos=8,
                razon="test",
            )
        # La fila debe existir como failed
        r = await cr.obtener_reserva(a["id"])
        assert r is not None
        assert r["estado"] == "failed"

    @pytest.mark.asyncio
    async def test_reserva_exitosa_link_transaccion_credito_id(self, db):
        """Cuando reservar() completa OK, la fila pending debe estar
        linkeada a la TransaccionCredito del cobro."""
        ac, cr, ex, bi = db
        await bi.acreditar("5811", 50, "seed")
        a = await ac.crear_accion(
            telefono="5811", tipo_accion="generar_plan_semanal",
            titulo="Link",
        )
        r = await cr.reservar(
            accion_id=a["id"], telefono="5811", creditos=8, razon="test",
        )
        assert r["estado"] == "pending"
        assert r["transaccion_credito_id"] is not None
        # Y la tx existe con el id correcto
        from agent.memory import async_session, TransaccionCredito
        from sqlalchemy import select
        async with async_session() as s:
            tx = (await s.execute(
                select(TransaccionCredito).where(
                    TransaccionCredito.id == r["transaccion_credito_id"]
                )
            )).scalar_one()
        assert int(tx.delta) == -8
        assert tx.job_id == a["id"]
