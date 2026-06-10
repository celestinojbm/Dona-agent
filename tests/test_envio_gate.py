# tests/test_envio_gate.py — Fase 0 · 2.1: gate central de envíos salientes

"""
Regresiones que PINEAN el lado de ENVÍO de C3 (audit Fable 5): antes de este
gate, los paths automáticos (recordatorios, GCal, onboarding, ejecutor HIGH)
enviaban WhatsApp sin consultar el opt-out TCPA. Los tests marcados como
REGRESIÓN fallan contra el código viejo.

Cubre:
  - Recordatorio programado NO se envía a usuario con STOP (REGRESIÓN).
  - Fail-closed: error de DB leyendo opt-out → envío bloqueado + CRITICAL.
  - Respuesta DIRECTA sigue viva tras STOP (confirmación, comandos).
  - DIRECTO va atado al teléfono: no exime envíos a otros números.
  - PROACTIVO (default): opt-out, límite diario (contado en el gate) y
    quiet hours solo con timezone conocida.
  - AUTOMATICO: opt-out sí, sin quiet hours ni límite diario.
  - Supresión de emergencia: STOP suprime in-memory aunque la persistencia
    falle; START / "dona actívate" la levantan.
  - Ejecutor HIGH respeta el opt-out del tercero destinatario.
"""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timedelta

import pytest


TEL = "15550001111"
TEL_OTRO = "15550002222"


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
async def memoria(tmp_path, monkeypatch):
    """DB SQLite aislada + módulos recargados sobre ella."""
    db_path = tmp_path / "gate.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    import agent.memory
    importlib.reload(agent.memory)
    await agent.memory.inicializar_db()

    # scheduler importa funciones de memory a nivel de módulo — re-bindear.
    import agent.scheduler
    importlib.reload(agent.scheduler)

    return agent.memory


@pytest.fixture(autouse=True)
def _gate_limpio():
    """La supresión de emergencia es estado in-memory del módulo — aislarla."""
    from agent.envio_gate import _supresion_emergencia
    _supresion_emergencia.clear()
    yield
    _supresion_emergencia.clear()


def _proveedor_fake():
    """Proveedor real (subclase de ProveedorWhatsApp) que registra envíos."""
    from agent.providers.base import ProveedorWhatsApp

    class FakeProveedor(ProveedorWhatsApp):
        def __init__(self):
            self.enviados: list[tuple[str, str]] = []

        async def parsear_webhook(self, request):
            return []

        async def _enviar_mensaje_impl(self, telefono, mensaje):
            self.enviados.append((telefono, mensaje))
            return True

    return FakeProveedor()


async def _seed_recordatorio_vencido(memoria, telefono: str) -> None:
    async with memoria.async_session() as session:
        session.add(memoria.Recordatorio(
            telefono=telefono,
            mensaje="llamar al banco",
            fecha_hora=datetime.utcnow() - timedelta(minutes=5),
        ))
        await session.commit()


def _offset_para_hora_local(hora_objetivo: int) -> int:
    """Offset (min) tal que la hora local del usuario sea hora_objetivo:30."""
    ahora = datetime.utcnow()
    minutos_utc = ahora.hour * 60 + ahora.minute
    return (hora_objetivo * 60 + 30 - minutos_utc) % 1440


# ── 1. Recordatorios respetan el opt-out (REGRESIÓN — pinea C3-envío) ────


class TestRecordatoriosRespetanOptOut:
    async def test_recordatorio_no_se_envia_tras_stop(self, memoria):
        """REGRESIÓN: contra el código viejo este test FALLA (el scheduler
        enviaba recordatorios sin consultar el opt-out, violando el copy de
        STOP: 'No te enviaré recordatorios ni resúmenes automáticos')."""
        import agent.scheduler as sch

        await memoria.guardar_proactividad(TEL, proactive_enabled=False)
        await _seed_recordatorio_vencido(memoria, TEL)

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert fake.enviados == []

    async def test_recordatorio_se_envia_con_optin(self, memoria):
        """Control: sin opt-out el recordatorio sale normal (no sobre-bloquear)."""
        import agent.scheduler as sch

        await memoria.guardar_proactividad(TEL, proactive_enabled=True)
        await _seed_recordatorio_vencido(memoria, TEL)

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert len(fake.enviados) == 1
        assert fake.enviados[0][0] == TEL
        assert "llamar al banco" in fake.enviados[0][1]

    async def test_recordatorio_sin_fila_proactividad_se_envia(self, memoria):
        """Usuario que nunca tocó su proactividad → habilitado por default."""
        import agent.scheduler as sch

        await _seed_recordatorio_vencido(memoria, TEL)

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert len(fake.enviados) == 1


# ── 2. Fail-closed ───────────────────────────────────────────────────────


class TestFailClosed:
    async def test_error_db_bloquea_envio_automatico(self, memoria, monkeypatch, caplog):
        """Si la lectura del opt-out FALLA, el envío se BLOQUEA (no se asume
        consentimiento) y se loguea CRITICAL."""
        from agent.envio_gate import contexto_envio_automatico

        async def _explota(telefono):
            raise RuntimeError("db caída")

        monkeypatch.setattr(memoria, "obtener_proactividad", _explota)

        fake = _proveedor_fake()
        with caplog.at_level(logging.CRITICAL, logger="dona"):
            with contexto_envio_automatico():
                ok = await fake.enviar_mensaje(TEL, "hola")

        assert ok is False
        assert fake.enviados == []
        assert any("FAIL-CLOSED" in r.message for r in caplog.records)

    async def test_error_db_no_bloquea_respuesta_directa(self, memoria, monkeypatch):
        """La conversación reactiva no depende de la DB de proactividad."""
        from agent.envio_gate import contexto_envio_directo

        async def _explota(telefono):
            raise RuntimeError("db caída")

        monkeypatch.setattr(memoria, "obtener_proactividad", _explota)

        fake = _proveedor_fake()
        with contexto_envio_directo(TEL):
            ok = await fake.enviar_mensaje(TEL, "tu saldo es 10")

        assert ok is True
        assert len(fake.enviados) == 1


# ── 3. Contexto DIRECTO ──────────────────────────────────────────────────


class TestContextoDirecto:
    async def test_respuesta_directa_permitida_con_optout(self, memoria):
        """Tras STOP, el usuario 'sigue pudiendo escribir' — las respuestas
        a sus mensajes (incluida la confirmación del STOP) salen."""
        from agent.envio_gate import contexto_envio_directo

        await memoria.guardar_proactividad(TEL, proactive_enabled=False)

        fake = _proveedor_fake()
        with contexto_envio_directo(TEL):
            ok = await fake.enviar_mensaje(TEL, "✅ Has sido dado de baja…")

        assert ok is True

    async def test_directo_no_exime_a_otros_numeros(self, memoria):
        """El contexto DIRECTO va atado al teléfono del usuario que escribió:
        un envío a OTRO número dentro del mismo contexto cae a PROACTIVO."""
        from agent.envio_gate import contexto_envio_directo

        await memoria.guardar_proactividad(TEL_OTRO, proactive_enabled=False)

        fake = _proveedor_fake()
        with contexto_envio_directo(TEL):
            ok = await fake.enviar_mensaje(TEL_OTRO, "spam lateral")

        assert ok is False
        assert fake.enviados == []


# ── 4. PROACTIVO (default) ───────────────────────────────────────────────


class TestProactivoDefault:
    async def test_sin_contexto_bloquea_optout(self, memoria):
        await memoria.guardar_proactividad(TEL, proactive_enabled=False)

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "resumen de tu semana")

        assert ok is False
        assert fake.enviados == []

    async def test_limite_diario_contado_en_el_gate(self, memoria):
        """El gate cuenta e impone MAX_MENSAJES_DIARIOS para TODO envío
        proactivo (no solo los del motor de proactividad)."""
        from agent.proactivity import MAX_MENSAJES_DIARIOS

        fake = _proveedor_fake()
        for i in range(MAX_MENSAJES_DIARIOS):
            assert await fake.enviar_mensaje(TEL, f"proactivo {i}") is True

        # El siguiente excede el límite → bloqueado
        assert await fake.enviar_mensaje(TEL, "uno de más") is False
        assert len(fake.enviados) == MAX_MENSAJES_DIARIOS

        config = await memoria.obtener_proactividad(TEL)
        assert config["mensajes_hoy"] == MAX_MENSAJES_DIARIOS

    async def test_limite_diario_no_aplica_a_automatico(self, memoria):
        """Recordatorios y alertas operativas no compiten con el presupuesto
        proactivo diario."""
        from agent.envio_gate import contexto_envio_automatico
        from agent.proactivity import MAX_MENSAJES_DIARIOS

        await memoria.guardar_proactividad(
            TEL,
            proactive_enabled=True,
            mensajes_hoy=MAX_MENSAJES_DIARIOS,
            ultimo_reset=datetime.utcnow(),
        )

        fake = _proveedor_fake()
        with contexto_envio_automatico():
            ok = await fake.enviar_mensaje(TEL, "🔔 Recordatorio: pagar renta")

        assert ok is True

    async def test_quiet_hours_con_timezone_conocida(self, memoria):
        """Proactivo a las 3:30 am locales → bloqueado."""
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(3))

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "buenos días…?")

        assert ok is False

    async def test_quiet_hours_no_aplica_de_dia(self, memoria):
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(10))

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "buenos días")

        assert ok is True

    async def test_quiet_hours_automatico_exento(self, memoria):
        """Un recordatorio que el usuario programó a las 6 am debe sonar a
        las 6 am."""
        from agent.envio_gate import contexto_envio_automatico

        await memoria.guardar_timezone(TEL, _offset_para_hora_local(3))

        fake = _proveedor_fake()
        with contexto_envio_automatico():
            ok = await fake.enviar_mensaje(TEL, "🔔 Recordatorio madrugador")

        assert ok is True

    async def test_sin_timezone_no_hay_quiet_hours(self, memoria):
        """Sin timezone conocida NO se aplica quiet hours: usar la hora UTC
        bloquearía tardes de EEUU, no madrugadas."""
        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "proactivo sin tz")

        assert ok is True


# ── 5. Supresión de emergencia ───────────────────────────────────────────


class TestSupresionEmergencia:
    async def test_stop_suprime_aunque_persistencia_falle(self, memoria, monkeypatch):
        """Si el write del opt-out a DB falla, el gate igual bloquea envíos
        automáticos/proactivos en este worker (cinturón in-memory)."""
        from agent.proactivity import manejar_stop_tcpa
        from agent.envio_gate import (
            contexto_envio_automatico,
            esta_suprimido_emergencia,
        )

        async def _explota(telefono, **kwargs):
            raise RuntimeError("db caída")

        monkeypatch.setattr(memoria, "guardar_proactividad", _explota)

        with pytest.raises(RuntimeError):
            await manejar_stop_tcpa(TEL)

        assert esta_suprimido_emergencia(TEL)

        fake = _proveedor_fake()
        with contexto_envio_automatico():
            ok = await fake.enviar_mensaje(TEL, "recordatorio")
        assert ok is False

    async def test_start_levanta_supresion(self, memoria):
        from agent.proactivity import manejar_stop_tcpa, manejar_start_tcpa
        from agent.envio_gate import esta_suprimido_emergencia

        await manejar_stop_tcpa(TEL)
        assert esta_suprimido_emergencia(TEL)

        await manejar_start_tcpa(TEL)
        assert not esta_suprimido_emergencia(TEL)

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "proactivo de vuelta")
        assert ok is True

    async def test_dona_activate_levanta_supresion(self, memoria):
        from agent.proactivity import manejar_stop_tcpa, manejar_comando_proactividad
        from agent.envio_gate import esta_suprimido_emergencia

        await manejar_stop_tcpa(TEL)
        await manejar_comando_proactividad(TEL, "dona activa")
        assert not esta_suprimido_emergencia(TEL)

    async def test_supresion_no_afecta_respuesta_directa(self, memoria):
        from agent.proactivity import manejar_stop_tcpa
        from agent.envio_gate import contexto_envio_directo

        await manejar_stop_tcpa(TEL)

        fake = _proveedor_fake()
        with contexto_envio_directo(TEL):
            ok = await fake.enviar_mensaje(TEL, "confirmación de baja")
        assert ok is True


# ── 6. Ejecutor HIGH respeta el opt-out del tercero ──────────────────────


class TestEjecutorHighOptOutTercero:
    async def test_destino_con_stop_no_recibe(self, memoria, monkeypatch):
        """REGRESIÓN: el ejecutor HIGH enviaba al tercero sin consultar si
        ese número había hecho opt-out de Dona."""
        import json
        import agent.automation.executors.send_message as sm

        await memoria.guardar_proactividad(TEL_OTRO, proactive_enabled=False)

        fake = _proveedor_fake()
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        async def _sin_resultado(accion_id):
            return None

        monkeypatch.setattr(sm, "_leer_result_actual", _sin_resultado)

        accion = {
            "id": 1,
            "payload_json": json.dumps(
                {"numero_destino": TEL_OTRO, "mensaje": "hola de parte de tu cliente"}
            ),
        }

        with pytest.raises(RuntimeError, match="provider_enviar_mensaje_failed"):
            await sm.ejecutor_enviar_mensaje_whatsapp(accion, None)

        assert fake.enviados == []

    async def test_destino_sin_optout_recibe(self, memoria, monkeypatch):
        """Control: tercero sin registro de opt-out → el envío HIGH procede."""
        import json
        import agent.automation.executors.send_message as sm

        fake = _proveedor_fake()
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        async def _sin_resultado(accion_id):
            return None

        async def _persistir_ok(accion_id, resultado):
            return None

        monkeypatch.setattr(sm, "_leer_result_actual", _sin_resultado)
        # No persistir result_json contra la DB del test (fuera de scope aquí)
        monkeypatch.setattr(sm, "_persistir_result_inline", _persistir_ok)

        accion = {
            "id": 2,
            "payload_json": json.dumps(
                {"numero_destino": TEL_OTRO, "mensaje": "mensaje aprobado"}
            ),
        }

        resultado = await sm.ejecutor_enviar_mensaje_whatsapp(accion, None)

        assert resultado["estado_envio"] == "sent"
        assert len(fake.enviados) == 1
