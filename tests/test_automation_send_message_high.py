# tests/test_automation_send_message_high.py — T2.2

"""
Tests del primer ejecutor HIGH real: enviar mensaje de WhatsApp.

Cubre:
  - preparar_enviar_mensaje_whatsapp crea acción HIGH en
    estado 'needs_approval'
  - validaciones de payload (numero_destino y mensaje)
  - ejecutar SIN aprobación falla (estado_invalido) · saldo intacto
  - aprobar + ejecutar → completed · provider llamado una sola vez
  - reintento de ejecutar tras éxito NO duplica envío ni cobro
  - provider.enviar_mensaje devuelve False → reserva liberada
  - provider.enviar_mensaje lanza excepción → reserva liberada
  - audit NO incluye el número destino completo ni el cuerpo del
    mensaje completo
  - confirmar_enviar_mensaje_whatsapp atajo: idempotente si ya
    completed · aprueba+ejecuta si needs_approval
  - tipo CRITICAL (envio_masivo_clientes) sigue bloqueado · no
    confunde con HIGH
"""

from __future__ import annotations

import asyncio
import importlib
import json
import pytest

import agent.memory


# ── Fixtures ─────────────────────────────────────────────────────────


class FakeProveedor:
    """Stand-in del ProveedorWhatsApp · cuenta invocaciones · no toca
    red. Tests configuran el resultado de enviar_mensaje."""

    def __init__(self, resultado: bool = True, lanzar_exc: bool = False):
        self.resultado = resultado
        self.lanzar_exc = lanzar_exc
        self.invocaciones: list[tuple[str, str]] = []

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        self.invocaciones.append((telefono, mensaje))
        if self.lanzar_exc:
            raise RuntimeError("simulated provider exception")
        return self.resultado


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """SQLite aislada · módulos automation recargados · sin LLM real
    (los tests no lo necesitan)."""
    db_path = tmp_path / "high.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("AUTOMATION_SCHEDULER_ENABLED", raising=False)

    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    import agent.automation.credits as _cr
    import agent.automation.execution as _ex
    import agent.automation.executors.send_message as _sm
    import agent.billing as _bi
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_ac)
    importlib.reload(_cr)
    importlib.reload(_bi)
    importlib.reload(_sm)
    importlib.reload(_ex)
    await agent.memory.inicializar_db()
    return _ac, _cr, _ex, _bi, _sm


def _mock_proveedor(monkeypatch, sm_module, fake: FakeProveedor):
    """Monkeypatchea _obtener_proveedor en el módulo send_message."""
    monkeypatch.setattr(sm_module, "_obtener_proveedor", lambda: fake)


# ── 1. Preparar · validaciones y creación ────────────────────────────


class TestPreparar:
    @pytest.mark.asyncio
    async def test_preparar_crea_accion_high_needs_approval(self, db):
        ac, cr, ex, bi, sm = db
        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5550",
            numero_destino="+5215512345678",
            mensaje="Hola, te confirmo el envío.",
        )
        assert a["tipo_accion"] == "enviar_mensaje_whatsapp"
        assert a["riesgo"] == "high"
        assert a["estado"] == "needs_approval"
        assert a["requires_approval"] is True
        # Payload guardado en payload_json
        payload = json.loads(a["payload_json"])
        assert payload["numero_destino"] == "+5215512345678"
        assert payload["mensaje"] == "Hola, te confirmo el envío."

    @pytest.mark.asyncio
    async def test_preparar_rechaza_numero_vacio(self, db):
        ac, cr, ex, bi, sm = db
        with pytest.raises(ValueError):
            await sm.preparar_enviar_mensaje_whatsapp(
                telefono="5550", numero_destino="", mensaje="hola",
            )

    @pytest.mark.asyncio
    async def test_preparar_rechaza_numero_no_numerico(self, db):
        ac, cr, ex, bi, sm = db
        with pytest.raises(ValueError):
            await sm.preparar_enviar_mensaje_whatsapp(
                telefono="5550", numero_destino="abc1234",
                mensaje="hola",
            )

    @pytest.mark.asyncio
    async def test_preparar_rechaza_mensaje_vacio(self, db):
        ac, cr, ex, bi, sm = db
        with pytest.raises(ValueError):
            await sm.preparar_enviar_mensaje_whatsapp(
                telefono="5550", numero_destino="+5215512345678",
                mensaje="   ",
            )

    @pytest.mark.asyncio
    async def test_preparar_rechaza_mensaje_demasiado_largo(self, db):
        ac, cr, ex, bi, sm = db
        msg = "x" * 5000
        with pytest.raises(ValueError):
            await sm.preparar_enviar_mensaje_whatsapp(
                telefono="5550", numero_destino="+5215512345678",
                mensaje=msg,
            )

    @pytest.mark.asyncio
    async def test_preparar_no_invoca_provider(self, db, monkeypatch):
        ac, cr, ex, bi, sm = db
        fake = FakeProveedor()
        _mock_proveedor(monkeypatch, sm, fake)
        await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5550", numero_destino="+5215512345678",
            mensaje="hola",
        )
        assert fake.invocaciones == []


# ── 2. Ejecutar sin aprobación · falla ───────────────────────────────


class TestEjecutarSinAprobacion:
    @pytest.mark.asyncio
    async def test_ejecutar_needs_approval_no_envia(self, db, monkeypatch):
        ac, cr, ex, bi, sm = db
        await bi.acreditar("5560", 50, "seed")
        fake = FakeProveedor()
        _mock_proveedor(monkeypatch, sm, fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5560", numero_destino="+5215512345678",
            mensaje="hola",
        )
        # ejecutar_accion directamente sobre la acción needs_approval
        r = await ex.ejecutar_accion(a)
        assert r["estado_final"] == "failed"
        assert "estado" in r["error"].lower() or "aprob" in r["error"].lower()
        # Provider nunca llamado
        assert fake.invocaciones == []
        # Saldo intacto (la reserva NO se creó porque ejecutar_accion
        # devuelve en el branch estado_invalido antes de reservar)
        assert await bi.obtener_saldo("5560") == 50


# ── 3. Ejecutar con aprobación · éxito ───────────────────────────────


class TestEjecutarConAprobacion:
    @pytest.mark.asyncio
    async def test_aprobar_y_ejecutar_envia_una_sola_vez(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm = db
        await bi.acreditar("5570", 50, "seed")
        fake = FakeProveedor(resultado=True)
        _mock_proveedor(monkeypatch, sm, fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5570", numero_destino="+5215512345678",
            mensaje="Te confirmo tu pedido.",
        )
        await ac.aprobar_accion(a["id"])
        fresh = (await ac.listar_acciones("5570"))[0]
        r = await ex.ejecutar_accion(fresh)

        assert r["estado_final"] == "completed"
        assert r["result"]["estado_envio"] == "sent"
        assert r["result"]["mensaje_id"]
        assert r["result"]["destino_short"] == "+5****5678"
        assert r["result"]["longitud_mensaje"] == len("Te confirmo tu pedido.")
        # Provider llamado exactamente una vez
        assert len(fake.invocaciones) == 1
        assert fake.invocaciones[0] == (
            "+5215512345678", "Te confirmo tu pedido.",
        )
        # Saldo bajó por el costo de enviar_mensaje_whatsapp (6 créditos)
        assert await bi.obtener_saldo("5570") == 44
        # Reserva en estado confirmed
        reserva = await cr.obtener_reserva(a["id"])
        assert reserva["estado"] == "confirmed"


# ── 4. Idempotencia · retry NO duplica envío ─────────────────────────


class TestIdempotenciaEnRetry:
    @pytest.mark.asyncio
    async def test_segunda_ejecucion_no_invoca_provider(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm = db
        await bi.acreditar("5580", 50, "seed")
        fake = FakeProveedor(resultado=True)
        _mock_proveedor(monkeypatch, sm, fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5580", numero_destino="+5215512345678",
            mensaje="hola",
        )
        await ac.aprobar_accion(a["id"])
        fresh = (await ac.listar_acciones("5580"))[0]
        r1 = await ex.ejecutar_accion(fresh)
        assert r1["estado_final"] == "completed"
        assert len(fake.invocaciones) == 1

        # Re-ejecutar con un dict stale que aún dice 'approved'
        stale = dict(fresh)
        stale["estado"] = "approved"  # finge que no se enteró del completed
        r2 = await ex.ejecutar_accion(stale)
        # El estado real en DB es 'completed' · marcar_running no lo
        # cambia (transición inválida) y el executor detecta result_json
        # previo via _leer_result_actual → idempotent
        # No hay un assert directo sobre el flag idempotent porque
        # ejecutar_accion wrappea con su propio result; el assert clave:
        assert len(fake.invocaciones) == 1, (
            "Segundo intento NO debe invocar provider de nuevo"
        )
        # Saldo igual (no doble cobro)
        assert await bi.obtener_saldo("5580") == 44

    @pytest.mark.asyncio
    async def test_executor_directo_con_result_previo_es_idempotente(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm = db
        fake = FakeProveedor(resultado=True)
        _mock_proveedor(monkeypatch, sm, fake)

        # Construir manualmente una acción ya enviada (simula post-send)
        await bi.acreditar("5581", 50, "seed")
        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5581", numero_destino="+5215512345678",
            mensaje="hola",
        )
        # Poblamos result_json como si ya hubiera sido enviada
        from agent.automation.models import AccionAutomatizacion
        from sqlalchemy import select
        async with agent.memory.async_session() as s:
            row = (await s.execute(
                select(AccionAutomatizacion).where(
                    AccionAutomatizacion.id == a["id"]
                )
            )).scalar_one()
            row.result_json = json.dumps({
                "estado_envio": "sent", "mensaje_id": "acc1-9999",
                "destino_short": "+5****5678", "longitud_mensaje": 4,
            })
            await s.commit()
        accion_dict = await ac.listar_acciones("5581")
        # Llamar al executor real directamente
        r = await sm.ejecutor_enviar_mensaje_whatsapp(
            accion_dict[0], perfil=None,
        )
        assert r["idempotent"] is True
        assert r["estado_envio"] == "sent"
        # Provider NUNCA invocado
        assert fake.invocaciones == []


# ── 5. Fallos del provider · reserva liberada ────────────────────────


class TestFallosDelProvider:
    @pytest.mark.asyncio
    async def test_provider_devuelve_false_libera_reserva(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm = db
        await bi.acreditar("5590", 50, "seed")
        fake = FakeProveedor(resultado=False)
        _mock_proveedor(monkeypatch, sm, fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5590", numero_destino="+5215512345678",
            mensaje="hola",
        )
        await ac.aprobar_accion(a["id"])
        fresh = (await ac.listar_acciones("5590"))[0]
        r = await ex.ejecutar_accion(fresh)
        assert r["estado_final"] == "failed"
        # Provider llamado una vez (luego falló)
        assert len(fake.invocaciones) == 1
        # Reserva liberada · saldo intacto (50)
        assert await bi.obtener_saldo("5590") == 50
        reserva = await cr.obtener_reserva(a["id"])
        assert reserva["estado"] == "released"

    @pytest.mark.asyncio
    async def test_provider_lanza_excepcion_libera_reserva(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm = db
        await bi.acreditar("5591", 50, "seed")
        fake = FakeProveedor(lanzar_exc=True)
        _mock_proveedor(monkeypatch, sm, fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5591", numero_destino="+5215512345678",
            mensaje="hola",
        )
        await ac.aprobar_accion(a["id"])
        fresh = (await ac.listar_acciones("5591"))[0]
        r = await ex.ejecutar_accion(fresh)
        assert r["estado_final"] == "failed"
        assert await bi.obtener_saldo("5591") == 50
        reserva = await cr.obtener_reserva(a["id"])
        assert reserva["estado"] == "released"


# ── 6. Audit no filtra PII ───────────────────────────────────────────


class TestAuditSinPII:
    @pytest.mark.asyncio
    async def test_audit_no_incluye_numero_destino_ni_cuerpo(
        self, db, monkeypatch,
    ):
        from agent.automation.models import AuditLogAutomatizacion
        from sqlalchemy import select
        ac, cr, ex, bi, sm = db
        telefono_dueno = "5215559999999"
        numero_destino = "+5215511122233"
        cuerpo = "Mensaje confidencial con info de cliente Juan Pérez."
        await bi.acreditar(telefono_dueno, 50, "seed")
        fake = FakeProveedor(resultado=True)
        _mock_proveedor(monkeypatch, sm, fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono=telefono_dueno,
            numero_destino=numero_destino,
            mensaje=cuerpo,
        )
        await ac.aprobar_accion(a["id"])
        fresh = (await ac.listar_acciones(telefono_dueno))[0]
        await ex.ejecutar_accion(fresh)

        async with agent.memory.async_session() as s:
            res = await s.execute(select(AuditLogAutomatizacion))
            logs = list(res.scalars().all())
        for log in logs:
            # Ni el teléfono del dueño ni el destinatario ni el cuerpo
            # del mensaje deben aparecer crudos en payload_summary o
            # telefono_short.
            assert telefono_dueno not in log.payload_summary
            assert telefono_dueno not in log.telefono_short
            assert numero_destino not in log.payload_summary
            assert "Juan Pérez" not in log.payload_summary
            assert cuerpo not in log.payload_summary


# ── 7. confirmar_enviar_mensaje_whatsapp · atajo end-to-end ──────────


class TestConfirmarShortcut:
    @pytest.mark.asyncio
    async def test_confirmar_aprueba_y_ejecuta(self, db, monkeypatch):
        ac, cr, ex, bi, sm = db
        await bi.acreditar("5600", 50, "seed")
        fake = FakeProveedor(resultado=True)
        _mock_proveedor(monkeypatch, sm, fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5600", numero_destino="+5215512345678",
            mensaje="hola",
        )
        r = await sm.confirmar_enviar_mensaje_whatsapp(a["id"])
        assert r["estado_final"] == "completed"
        assert len(fake.invocaciones) == 1

    @pytest.mark.asyncio
    async def test_confirmar_idempotente_si_ya_completada(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm = db
        await bi.acreditar("5601", 50, "seed")
        fake = FakeProveedor(resultado=True)
        _mock_proveedor(monkeypatch, sm, fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5601", numero_destino="+5215512345678",
            mensaje="hola",
        )
        r1 = await sm.confirmar_enviar_mensaje_whatsapp(a["id"])
        assert r1["estado_final"] == "completed"
        # Segunda llamada · ya completada
        r2 = await sm.confirmar_enviar_mensaje_whatsapp(a["id"])
        assert r2["estado_final"] == "completed"
        assert r2.get("idempotent") is True
        # Provider invocado solo una vez
        assert len(fake.invocaciones) == 1

    @pytest.mark.asyncio
    async def test_confirmar_rechazada_no_ejecuta(self, db, monkeypatch):
        ac, cr, ex, bi, sm = db
        fake = FakeProveedor(resultado=True)
        _mock_proveedor(monkeypatch, sm, fake)
        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5602", numero_destino="+5215512345678",
            mensaje="hola",
        )
        await ac.rechazar_accion(a["id"])
        r = await sm.confirmar_enviar_mensaje_whatsapp(a["id"])
        assert r["estado_final"] == "rejected"
        assert fake.invocaciones == []

    @pytest.mark.asyncio
    async def test_confirmar_accion_inexistente(self, db):
        ac, cr, ex, bi, sm = db
        r = await sm.confirmar_enviar_mensaje_whatsapp(99999)
        assert r["estado_final"] == "failed"
        assert r["error"] == "accion_no_existe"


# ── 8. CRITICAL no se confunde con HIGH ──────────────────────────────


class TestCriticalNoMezcla:
    @pytest.mark.asyncio
    async def test_envio_masivo_clientes_sigue_bloqueado(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm = db
        await bi.acreditar("5610", 200, "seed")
        fake = FakeProveedor(resultado=True)
        _mock_proveedor(monkeypatch, sm, fake)
        # CRITICAL · existe en costos.py con 100 créditos
        a = await ac.crear_accion(
            telefono="5610",
            tipo_accion="envio_masivo_clientes",
            titulo="Envío masivo (CRITICAL)",
        )
        assert a["riesgo"] == "critical"
        await ac.aprobar_accion(a["id"])
        fresh = (await ac.listar_acciones("5610"))[0]
        r = await ex.ejecutar_accion(fresh)
        assert r["estado_final"] == "failed"
        assert "critical" in r["error"].lower() or "bloque" in r["error"].lower()
        # Provider NUNCA invocado
        assert fake.invocaciones == []
        # Reserva liberada · saldo intacto
        assert await bi.obtener_saldo("5610") == 200
