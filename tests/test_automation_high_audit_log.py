# tests/test_automation_high_audit_log.py — audit log HIGH dedicado
#
# Cubre la trazabilidad persistente del flujo dedicated HIGH para
# enviar_mensaje_whatsapp:
#   - preview emite high_preview_requested y high_preview_rendered.
#   - confirmación inválida (string distinto a 'ENVIAR') no toca al
#     provider y deja huella de rechazo.
#   - confirmación con tipo no-string tampoco toca al provider y deja
#     huella de rechazo.
#   - confirmación válida sobre acción aprobada: claimed + succeeded
#     con metadata sanitizada.
#   - segundo intento sobre acción ya completada: duplicate_blocked,
#     un solo provider call total.
#   - confirmaciones concurrentes: un solo provider call, ganador
#     succeeded, perdedor duplicate_blocked.
#   - los payload_summary nunca contienen el teléfono del dueño, el
#     número destino, el cuerpo del mensaje ni secrets.

from __future__ import annotations

import asyncio
import importlib
import json

import pytest

import agent.memory


class FakeProveedor:
    """Stand-in del proveedor WhatsApp · no toca red · cuenta envíos."""

    def __init__(self, resultado: bool = True, lento_segs: float = 0.0):
        self.resultado = resultado
        self.lento_segs = lento_segs
        self.invocaciones: list[tuple[str, str]] = []

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        if self.lento_segs:
            await asyncio.sleep(self.lento_segs)
        self.invocaciones.append((telefono, mensaje))
        return self.resultado


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "high-audit.db"
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
    return _ac, _cr, _ex, _bi, _sm, _au


async def _eventos_audit() -> list[tuple[str, str, str]]:
    """Devuelve [(evento, telefono_short, payload_summary), ...]."""
    from agent.automation.models import AuditLogAutomatizacion
    from sqlalchemy import select

    async with agent.memory.async_session() as s:
        rows = (await s.execute(select(AuditLogAutomatizacion))).scalars().all()
    return [(r.evento, r.telefono_short, r.payload_summary) for r in rows]


def _contar(eventos: list[tuple[str, str, str]], nombre: str) -> int:
    return sum(1 for e in eventos if e[0] == nombre)


class TestPreviewAuditTrail:
    @pytest.mark.asyncio
    async def test_preview_emite_requested_y_rendered_cuando_aprobada(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm, au = db
        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5215559900001",
            numero_destino="+5215511122233",
            mensaje="Confirmación del pedido del cliente.",
        )
        await ac.aprobar_accion(a["id"])

        preview = await sm.preview_confirmacion_high_whatsapp(a["id"], "5215559900001")
        assert preview["ok"] is True

        eventos = await _eventos_audit()
        nombres = [e[0] for e in eventos]
        assert "high_preview_requested" in nombres
        assert "high_preview_rendered" in nombres

        # El rendered debe llevar metadata sanitizada (destino_short,
        # longitud_mensaje, costo) y NO el destino crudo ni el cuerpo.
        rendered = next(e for e in eventos if e[0] == "high_preview_rendered")
        summary = rendered[2]
        assert "+5****2233" in summary
        assert "+5215511122233" not in summary
        assert "Confirmación del pedido" not in summary
        assert "longitud_mensaje" in summary

    @pytest.mark.asyncio
    async def test_preview_sin_aprobar_emite_requested_pero_no_rendered(self, db):
        ac, cr, ex, bi, sm, au = db
        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5215559900002",
            numero_destino="+5215511122234",
            mensaje="hola",
        )
        bloqueado = await sm.preview_confirmacion_high_whatsapp(a["id"], "5215559900002")
        assert bloqueado["ok"] is False
        assert bloqueado["error"] == "accion_no_aprobada"

        eventos = await _eventos_audit()
        assert _contar(eventos, "high_preview_requested") == 1
        assert _contar(eventos, "high_preview_rendered") == 0


class TestConfirmacionInvalidaAuditTrail:
    @pytest.mark.asyncio
    async def test_string_invalido_no_toca_provider_y_emite_rejected(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm, au = db
        await bi.acreditar("5215559900010", 50, "seed")
        fake = FakeProveedor(resultado=True)
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5215559900010",
            numero_destino="+5215511122244",
            mensaje="hola",
        )
        await ac.aprobar_accion(a["id"])

        r = await sm.confirmar_high_whatsapp_dedicado(a["id"], " ENVIAR ", "5215559900010")

        assert r["estado_final"] == "failed"
        assert r["error"] == "confirmacion_invalida"
        assert fake.invocaciones == []

        eventos = await _eventos_audit()
        assert _contar(eventos, "high_confirmation_submitted") == 1
        assert _contar(eventos, "high_confirmation_rejected") == 1
        # El payload nunca debe loguear el string de confirmación crudo
        # (puede ser PII en otros flujos · disciplina general).
        rejected = next(e for e in eventos if e[0] == "high_confirmation_rejected")
        assert " ENVIAR " not in rejected[2]

    @pytest.mark.asyncio
    async def test_confirmacion_no_string_no_toca_provider_y_emite_rejected(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm, au = db
        await bi.acreditar("5215559900011", 50, "seed")
        fake = FakeProveedor(resultado=True)
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5215559900011",
            numero_destino="+5215511122245",
            mensaje="hola",
        )
        await ac.aprobar_accion(a["id"])

        # Pasar None (no-string) directamente al helper · simula caller
        # interno desprolijo. El endpoint público ya valida tipo, pero
        # la defensa en profundidad debe sostenerse aquí también.
        r = await sm.confirmar_high_whatsapp_dedicado(a["id"], None, "5215559900011")  # type: ignore[arg-type]

        assert r["estado_final"] == "failed"
        assert r["error"] == "confirmacion_invalida"
        assert fake.invocaciones == []

        eventos = await _eventos_audit()
        assert _contar(eventos, "high_confirmation_submitted") == 1
        rejected = [e for e in eventos if e[0] == "high_confirmation_rejected"]
        assert len(rejected) == 1
        assert '"confirmacion_es_str": false' in rejected[0][2]


class TestExitoYDuplicadosAuditTrail:
    @pytest.mark.asyncio
    async def test_confirmacion_valida_emite_claimed_y_succeeded(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm, au = db
        await bi.acreditar("5215559900020", 50, "seed")
        fake = FakeProveedor(resultado=True)
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5215559900020",
            numero_destino="+5215511122255",
            mensaje="Confirmo tu pedido para mañana.",
        )
        await ac.aprobar_accion(a["id"])

        r = await sm.confirmar_high_whatsapp_dedicado(a["id"], "ENVIAR", "5215559900020")
        assert r["estado_final"] == "completed"
        assert len(fake.invocaciones) == 1

        eventos = await _eventos_audit()
        assert _contar(eventos, "high_confirmation_submitted") == 1
        assert _contar(eventos, "high_execution_claimed") == 1
        assert _contar(eventos, "high_execution_succeeded") == 1
        assert _contar(eventos, "high_execution_failed") == 0
        assert _contar(eventos, "high_execution_duplicate_blocked") == 0

        ok = next(e for e in eventos if e[0] == "high_execution_succeeded")
        summary = ok[2]
        # destino_short debe estar; destino crudo y cuerpo nunca.
        assert "+5****2255" in summary
        assert "+5215511122255" not in summary
        assert "Confirmo tu pedido" not in summary

    @pytest.mark.asyncio
    async def test_doble_confirmacion_secuencial_emite_duplicate_blocked(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm, au = db
        await bi.acreditar("5215559900021", 50, "seed")
        fake = FakeProveedor(resultado=True)
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5215559900021",
            numero_destino="+5215511122256",
            mensaje="hola",
        )
        await ac.aprobar_accion(a["id"])

        r1 = await sm.confirmar_high_whatsapp_dedicado(a["id"], "ENVIAR", "5215559900021")
        r2 = await sm.confirmar_high_whatsapp_dedicado(a["id"], "ENVIAR", "5215559900021")

        assert r1["estado_final"] == "completed"
        assert r2["estado_final"] == "failed"
        assert r2["error"] == "accion_no_aprobada"
        assert len(fake.invocaciones) == 1

        eventos = await _eventos_audit()
        assert _contar(eventos, "high_execution_succeeded") == 1
        assert _contar(eventos, "high_execution_duplicate_blocked") == 1

    @pytest.mark.asyncio
    async def test_concurrencia_emite_un_succeeded_y_un_duplicate_blocked(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm, au = db
        await bi.acreditar("5215559900022", 50, "seed")
        fake = FakeProveedor(resultado=True, lento_segs=0.05)
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5215559900022",
            numero_destino="+5215511122257",
            mensaje="hola",
        )
        await ac.aprobar_accion(a["id"])

        r1, r2 = await asyncio.gather(
            sm.confirmar_high_whatsapp_dedicado(a["id"], "ENVIAR", "5215559900022"),
            sm.confirmar_high_whatsapp_dedicado(a["id"], "ENVIAR", "5215559900022"),
        )

        estados = sorted([r1["estado_final"], r2["estado_final"]])
        assert estados == ["completed", "failed"]
        assert len(fake.invocaciones) == 1

        eventos = await _eventos_audit()
        assert _contar(eventos, "high_confirmation_submitted") == 2
        assert _contar(eventos, "high_execution_succeeded") == 1
        assert _contar(eventos, "high_execution_duplicate_blocked") == 1

    @pytest.mark.asyncio
    async def test_owner_distinto_no_previsualiza_ni_confirma(self, db, monkeypatch):
        ac, cr, ex, bi, sm, au = db
        await bi.acreditar("5215559900023", 50, "seed")
        fake = FakeProveedor(resultado=True)
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono="5215559900023",
            numero_destino="+521555992258",
            mensaje="mensaje privado",
        )
        await ac.aprobar_accion(a["id"])

        preview = await sm.preview_confirmacion_high_whatsapp(
            a["id"], "5215559909999",
        )
        assert preview["ok"] is False
        assert preview["error"] == "accion_no_existe"
        assert "numero_destino" not in preview
        assert "mensaje_preview" not in preview

        r = await sm.confirmar_high_whatsapp_dedicado(
            a["id"], "ENVIAR", "5215559909999",
        )
        assert r["estado_final"] == "failed"
        assert r["error"] == "accion_no_existe"
        assert fake.invocaciones == []

        eventos = await _eventos_audit()
        assert _contar(eventos, "high_preview_requested") == 0
        assert _contar(eventos, "high_confirmation_submitted") == 0
        assert _contar(eventos, "high_confirmation_rejected") == 0
        assert _contar(eventos, "high_execution_claimed") == 0
        assert _contar(eventos, "high_execution_succeeded") == 0
        for nombre, telefono_short, summary in eventos:
            if nombre.startswith("high_"):
                assert "0023" not in telefono_short
                assert "5215559900023" not in summary





class TestErroresNoFiltranSecretsNiTelefono:
    @pytest.mark.asyncio
    async def test_provider_excepcion_emite_failed_sin_destino_ni_secret(
        self, db, monkeypatch,
    ):
        ac, cr, ex, bi, sm, au = db
        telefono_dueno = "5215559900030"
        numero_destino = "+5215511188899"
        cuerpo = "Mensaje con SECRET_SENTINEL_DO_NOT_LOG"

        await bi.acreditar(telefono_dueno, 50, "seed")

        class ProveedorQueRevienta:
            invocaciones: list[tuple[str, str]] = []

            async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
                self.invocaciones.append((telefono, mensaje))
                # Mensaje del error incluye token + número destino · si
                # algo filtra esto al audit log, el test lo detecta.
                raise RuntimeError(
                    f"upstream 500: leak {numero_destino} {cuerpo}"
                )

        fake = ProveedorQueRevienta()
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        a = await sm.preparar_enviar_mensaje_whatsapp(
            telefono=telefono_dueno,
            numero_destino=numero_destino,
            mensaje=cuerpo,
        )
        await ac.aprobar_accion(a["id"])

        r = await sm.confirmar_high_whatsapp_dedicado(a["id"], "ENVIAR", telefono_dueno)
        assert r["estado_final"] == "failed"
        assert len(fake.invocaciones) == 1
        # Saldo intacto (reserva liberada por excepción).
        assert await bi.obtener_saldo(telefono_dueno) == 50

        eventos = await _eventos_audit()
        for nombre, telefono_short, summary in eventos:
            assert telefono_dueno not in summary, (
                f"evento {nombre} filtró teléfono del dueño"
            )
            assert telefono_dueno not in telefono_short, (
                f"evento {nombre} guardó teléfono dueño en telefono_short"
            )
            assert numero_destino not in summary, (
                f"evento {nombre} filtró número destino crudo"
            )
            assert "SECRET_SENTINEL_DO_NOT_LOG" not in summary, (
                f"evento {nombre} filtró el secret del cuerpo"
            )
            assert cuerpo not in summary, (
                f"evento {nombre} filtró el cuerpo del mensaje crudo"
            )

        # Debió emitirse el evento high_execution_failed específico.
        nombres = [e[0] for e in eventos]
        assert "high_execution_failed" in nombres
        assert "high_execution_succeeded" not in nombres
