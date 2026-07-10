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
    import agent.business.models as _bm
    import agent.automation.models as _am
    importlib.reload(agent.memory)
    # Re-bindear los modelos al Base recargado: los tests del ejecutor HIGH
    # tocan las tablas de automation (consentimiento 2.5) y deben existir
    # en esta DB temporal.
    importlib.reload(_bm)
    importlib.reload(_am)
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

        # tz diurna: el foco es el límite diario, no las quiet hours (que sin
        # timezone bloquearían antes de llegar al contador — Fase 1B).
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(12))
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

    async def test_sin_timezone_bloquea_proactivo_conservador(self, memoria):
        """Fase 1B (decisión del owner): sin timezone confiable, un PROACTIVO
        se BLOQUEA. No se puede probar que el destinatario está dentro de la
        ventana 8am–9pm, así que el default conservador es no enviar."""
        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "proactivo sin tz")

        assert ok is False
        assert fake.enviados == []

    async def test_quiet_hours_permite_borde_20h(self, memoria):
        """Control del borde interno superior: las 20:xx locales (8:59 PM)
        siguen DENTRO de la ventana [8, 21) → permitido."""
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(20))

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "casi las nueve")

        assert ok is True

    async def test_quiet_hours_bloquea_a_las_22h(self, memoria):
        """TCPA-01: antes el gate solo chequeaba el piso de 7am — un proactivo
        a las 22:00 local salía sin problema. Ahora el límite superior (9pm)
        debe bloquearlo."""
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(22))

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "buenas noches…?")

        assert ok is False
        assert fake.enviados == []

    async def test_quiet_hours_bloquea_a_las_7_30am(self, memoria):
        """TCPA-01: el piso se sube de 7am a 8am (estándar FCC 8am-9pm) — un
        proactivo a las 7:30 local ahora también queda bloqueado."""
        from agent.envio_gate import HORA_INICIO_ENVIOS_PROACTIVOS

        assert HORA_INICIO_ENVIOS_PROACTIVOS == 8
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(7))

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "buenos días temprano")

        assert ok is False
        assert fake.enviados == []

    async def test_quiet_hours_permite_borde_inferior_8am(self, memoria):
        """Control: las 8:xx locales SÍ están dentro de la ventana [8, 21)."""
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(8))

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "buenos días")

        assert ok is True

    async def test_quiet_hours_bloquea_borde_superior_21h(self, memoria):
        """Control: las 21:xx locales YA están fuera de la ventana [8, 21)."""
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(21))

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "buenas noches")

        assert ok is False


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

        # tz diurna: el foco es que START levante la supresión, no las quiet
        # hours (sin timezone bloquearían el proactivo — Fase 1B).
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(12))
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
        ese número había hecho opt-out de Dona. (El destino se siembra como
        "conocido" para aislar el GATE de la política de consentimiento 2.5,
        que tiene tests propios en test_consent_terceros.py.)"""
        import json
        import agent.automation.executors.send_message as sm

        await memoria.guardar_mensaje(TEL_OTRO, "user", "hola dona")
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
        """Control: tercero CONOCIDO sin registro de opt-out → el envío HIGH
        procede (best-effort). El caso de destino frío sin consentimiento se
        pina en test_consent_terceros.py."""
        import json
        import agent.automation.executors.send_message as sm

        await memoria.guardar_mensaje(TEL_OTRO, "user", "hola dona")
        # tz diurna del tercero: el foco es el opt-out, no las quiet hours
        # (sin timezone el envío a un tercero se bloquea — Fase 1B).
        await memoria.guardar_timezone(TEL_OTRO, _offset_para_hora_local(12))

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


# ── 6b. Ejecutor HIGH respeta quiet hours del TERCERO (TCPA-04) ──────────


class TestEjecutorHighQuietHoursTercero:
    """El destinatario de un enviar_mensaje_whatsapp HIGH es un TERCERO que
    nunca eligió la hora en que el owner decide aprobar la acción — a
    diferencia de un recordatorio al propio owner, donde la hora la fijó él
    mismo al programar el contenido. El ejecutor pasa
    contexto_envio_automatico(es_tercero=True) para que el gate SÍ aplique
    quiet hours sobre la hora local del tercero (Fase 0 · TEMA 2)."""

    TEL_OWNER = "15550009999"

    async def test_tercero_de_madrugada_bloqueado(self, memoria, monkeypatch):
        """Owner aprueba a cualquier hora, pero el tercero está a las 2am
        locales → el gate debe bloquear el envío."""
        import json
        import agent.automation.executors.send_message as sm

        await memoria.guardar_mensaje(TEL_OTRO, "user", "hola dona")
        await memoria.guardar_timezone(TEL_OTRO, _offset_para_hora_local(2))

        fake = _proveedor_fake()
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        async def _sin_resultado(accion_id):
            return None

        monkeypatch.setattr(sm, "_leer_result_actual", _sin_resultado)

        accion = {
            "id": 3,
            "telefono": self.TEL_OWNER,
            "payload_json": json.dumps(
                {"numero_destino": TEL_OTRO, "mensaje": "hola de madrugada"}
            ),
        }

        with pytest.raises(RuntimeError, match="provider_enviar_mensaje_failed"):
            await sm.ejecutor_enviar_mensaje_whatsapp(accion, None)

        assert fake.enviados == []

    async def test_tercero_en_horario_permitido_recibe(self, memoria, monkeypatch):
        """Control: mismo escenario pero el tercero está en horario diurno →
        el envío procede con normalidad."""
        import json
        import agent.automation.executors.send_message as sm

        await memoria.guardar_mensaje(TEL_OTRO, "user", "hola dona")
        await memoria.guardar_timezone(TEL_OTRO, _offset_para_hora_local(14))

        fake = _proveedor_fake()
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        async def _sin_resultado(accion_id):
            return None

        async def _persistir_ok(accion_id, resultado):
            return None

        monkeypatch.setattr(sm, "_leer_result_actual", _sin_resultado)
        monkeypatch.setattr(sm, "_persistir_result_inline", _persistir_ok)

        accion = {
            "id": 4,
            "telefono": self.TEL_OWNER,
            "payload_json": json.dumps(
                {"numero_destino": TEL_OTRO, "mensaje": "mensaje de tarde"}
            ),
        }

        resultado = await sm.ejecutor_enviar_mensaje_whatsapp(accion, None)

        assert resultado["estado_envio"] == "sent"
        assert len(fake.enviados) == 1

    async def test_tercero_sin_tz_usa_fallback_del_owner_de_madrugada(
        self, memoria, monkeypatch
    ):
        """Si no se conoce la timezone del tercero, el gate aproxima con la
        del owner (más conservador que no aplicar quiet hours). Owner a las
        2am locales → bloqueado aunque el tercero no tenga tz registrada."""
        import json
        import agent.automation.executors.send_message as sm

        await memoria.guardar_mensaje(TEL_OTRO, "user", "hola dona")
        # El tercero NO tiene timezone; el owner sí, y está de madrugada.
        await memoria.guardar_timezone(self.TEL_OWNER, _offset_para_hora_local(2))

        fake = _proveedor_fake()
        monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)

        async def _sin_resultado(accion_id):
            return None

        monkeypatch.setattr(sm, "_leer_result_actual", _sin_resultado)

        accion = {
            "id": 5,
            "telefono": self.TEL_OWNER,
            "payload_json": json.dumps(
                {"numero_destino": TEL_OTRO, "mensaje": "fallback a la tz del owner"}
            ),
        }

        with pytest.raises(RuntimeError, match="provider_enviar_mensaje_failed"):
            await sm.ejecutor_enviar_mensaje_whatsapp(accion, None)

        assert fake.enviados == []

    async def test_automatico_al_propio_owner_sigue_exento_de_madrugada(self, memoria):
        """Control de no-regresión: un AUTOMATICO normal (es_tercero=False,
        el caso de recordatorios/GCal donde el destinatario ES quien
        controla su propio timing) sigue exento de quiet hours a cualquier
        hora — el ejecutor HIGH es el único que activa es_tercero=True."""
        from agent.envio_gate import contexto_envio_automatico

        await memoria.guardar_timezone(TEL, _offset_para_hora_local(2))

        fake = _proveedor_fake()
        with contexto_envio_automatico():
            ok = await fake.enviar_mensaje(TEL, "🔔 recordatorio programado por el propio usuario")

        assert ok is True


# ── 7. Aviso de sobrecarga es PROACTIVO (review Hermes, PR #75) ──────────


class TestSobrecargaEsProactivo:
    """El aviso de sobrecarga nace dentro del webhook (create_task hereda el
    contexto DIRECTO) pero es contenido NO solicitado: debe anular el
    contexto heredado y pasar por el gate como PROACTIVO."""

    @pytest.fixture
    async def main_sobrecarga(self, memoria, monkeypatch):
        import agent.main as main_mod

        async def _cinco_eventos(telefono, horas=24):
            return 5

        async def _no_avisado(telefono):
            return False

        avisados: list[str] = []

        async def _marcar(telefono):
            avisados.append(telefono)

        monkeypatch.setattr(main_mod, "contar_eventos_estres_recientes", _cinco_eventos)
        monkeypatch.setattr(main_mod, "ya_avisado_sobrecarga_hoy", _no_avisado)
        monkeypatch.setattr(main_mod, "marcar_aviso_sobrecarga", _marcar)
        return main_mod, avisados

    async def test_optout_no_recibe_sobrecarga_ni_en_contexto_directo(
        self, memoria, main_sobrecarga
    ):
        """REGRESIÓN (review Hermes): heredando DIRECTO del webhook, el aviso
        de sobrecarga evadía el opt-out."""
        from agent.envio_gate import contexto_envio_directo

        main_mod, avisados = main_sobrecarga
        await memoria.guardar_proactividad(TEL, proactive_enabled=False)

        fake = _proveedor_fake()
        with contexto_envio_directo(TEL):
            await main_mod._verificar_sobrecarga(TEL, fake, "estoy agotado")

        assert fake.enviados == []
        assert avisados == []

    async def test_sobrecarga_cuenta_una_sola_vez(self, memoria, main_sobrecarga):
        """REGRESIÓN (review Hermes): gate + incremento manual = doble conteo."""
        main_mod, avisados = main_sobrecarga

        # tz diurna: el foco es el doble conteo, no las quiet hours (sin
        # timezone el aviso proactivo se bloquea — Fase 1B).
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(12))
        fake = _proveedor_fake()
        await main_mod._verificar_sobrecarga(TEL, fake, "no puedo con todo")

        assert len(fake.enviados) == 1
        assert avisados == [TEL]
        config = await memoria.obtener_proactividad(TEL)
        assert config["mensajes_hoy"] == 1

    async def test_sobrecarga_respeta_limite_diario(self, memoria, main_sobrecarga):
        """Antes el aviso se enviaba aunque el presupuesto diario estuviera
        agotado (solo contaba después); ahora el gate lo verifica ANTES."""
        from agent.proactivity import MAX_MENSAJES_DIARIOS

        main_mod, avisados = main_sobrecarga
        await memoria.guardar_proactividad(
            TEL,
            proactive_enabled=True,
            mensajes_hoy=MAX_MENSAJES_DIARIOS,
            ultimo_reset=datetime.utcnow(),
        )

        fake = _proveedor_fake()
        await main_mod._verificar_sobrecarga(TEL, fake, "qué día pesado")

        assert fake.enviados == []
        assert avisados == []


# ── 8. Guardrail: subclases no deben sobreescribir los métodos públicos ──


class TestGuardrailSubclases:
    def test_providers_concretos_no_sobreescriben_metodos_publicos(self):
        """El gate vive en los métodos públicos de ProveedorWhatsApp: una
        subclase que defina enviar_* (en vez de _enviar_*_impl) lo evadiría.
        Este test falla si alguien lo intenta (review Hermes, PR #75)."""
        from agent.providers.base import ProveedorWhatsApp
        import agent.providers.meta  # noqa: F401 — registra la subclase
        import agent.providers.whapi  # noqa: F401

        publicos = (
            "enviar_mensaje", "enviar_botones", "enviar_lista", "enviar_audio",
            "enviar_documento", "enviar_imagen", "enviar_video",
        )

        def _subclases(cls):
            for sub in cls.__subclasses__():
                yield sub
                yield from _subclases(sub)

        revisadas = 0
        for sub in _subclases(ProveedorWhatsApp):
            # Solo providers de producción (los fakes de tests quedan fuera)
            if not sub.__module__.startswith("agent."):
                continue
            revisadas += 1
            for metodo in publicos:
                assert metodo not in vars(sub), (
                    f"{sub.__name__} sobreescribe {metodo}() y evade el gate "
                    f"de envíos — implementa _{metodo}_impl() en su lugar"
                )

        assert revisadas >= 2  # al menos ProveedorMeta y ProveedorWhapi


# ── 9. Fail-closed también ante error leyendo timezone (quiet hours) ──────


class TestFailClosedTimezone:
    """Un fallo leyendo el opt-out ya bloquea (TestFailClosed). Pero el gate
    tiene un SEGUNDO punto de lectura de DB en el camino proactivo: la
    timezone para quiet hours. Ese error también debe FALLAR CERRADO."""

    async def test_error_timezone_bloquea_proactivo(self, memoria, monkeypatch, caplog):
        # Opt-out habilitado: el envío pasa la primera compuerta y llega a la
        # lectura de timezone.
        await memoria.guardar_proactividad(TEL, proactive_enabled=True)

        async def _explota(telefono):
            raise RuntimeError("db caída leyendo tz")

        monkeypatch.setattr(memoria, "obtener_timezone", _explota)

        fake = _proveedor_fake()
        with caplog.at_level(logging.CRITICAL, logger="dona"):
            ok = await fake.enviar_mensaje(TEL, "resumen proactivo")

        assert ok is False
        assert fake.enviados == []
        assert any("FAIL-CLOSED" in r.message for r in caplog.records)

    async def test_error_timezone_no_bloquea_directo(self, memoria, monkeypatch):
        """El camino DIRECTO ni siquiera consulta la timezone: un fallo de esa
        lectura no debe afectar la conversación reactiva."""
        from agent.envio_gate import contexto_envio_directo

        async def _explota(telefono):
            raise RuntimeError("db caída leyendo tz")

        monkeypatch.setattr(memoria, "obtener_timezone", _explota)

        fake = _proveedor_fake()
        with contexto_envio_directo(TEL):
            ok = await fake.enviar_mensaje(TEL, "respuesta directa")

        assert ok is True
        assert len(fake.enviados) == 1


# ── 10. Contexto DIRECTO imperativo (activar/restaurar) ──────────────────


class TestContextoImperativo:
    """`activar_contexto_directo` / `restaurar_contexto` son la variante sin
    `with` que usa el loop del webhook. Deben tener la misma semántica que el
    context manager: DIRECTO atado al teléfono, y reversible con el token."""

    async def test_activar_permite_directo_con_optout(self, memoria):
        from agent.envio_gate import (
            activar_contexto_directo,
            restaurar_contexto,
        )

        await memoria.guardar_proactividad(TEL, proactive_enabled=False)

        fake = _proveedor_fake()
        token = activar_contexto_directo(TEL)
        try:
            ok = await fake.enviar_mensaje(TEL, "confirmación reactiva")
        finally:
            restaurar_contexto(token)

        assert ok is True
        assert len(fake.enviados) == 1

    async def test_restaurar_revierte_a_proactivo(self, memoria):
        """Tras restaurar el token, el contexto vuelve a lo previo (sin
        contexto → PROACTIVO), y un envío con opt-out queda bloqueado."""
        from agent.envio_gate import (
            activar_contexto_directo,
            restaurar_contexto,
        )

        await memoria.guardar_proactividad(TEL, proactive_enabled=False)

        token = activar_contexto_directo(TEL)
        restaurar_contexto(token)

        fake = _proveedor_fake()
        ok = await fake.enviar_mensaje(TEL, "proactivo tras restaurar")

        assert ok is False
        assert fake.enviados == []


# ── 11. Bookkeeping post-envío es best-effort ────────────────────────────


class TestRegistrarEnvioBestEffort:
    """`registrar_envio_realizado` incrementa el contador diario proactivo en
    el choke point. Es best-effort: un fallo del contador NO debe propagar ni
    romper un envío ya materializado."""

    async def test_fallo_del_contador_no_propaga(self, memoria, monkeypatch, caplog):
        from agent.envio_gate import registrar_envio_realizado

        async def _explota(telefono):
            raise RuntimeError("db caída incrementando")

        monkeypatch.setattr(memoria, "incrementar_mensajes_proactivos", _explota)

        # Sin contexto → PROACTIVO → intenta incrementar → falla → se traga.
        with caplog.at_level(logging.ERROR, logger="dona"):
            await registrar_envio_realizado(TEL)  # no debe lanzar

        assert any(
            "No se pudo incrementar contador proactivo" in r.message
            for r in caplog.records
        )

    async def test_directo_no_incrementa_contador(self, memoria, monkeypatch):
        """Un envío DIRECTO no consume el presupuesto proactivo diario: el
        bookkeeping debe salir temprano sin tocar el contador."""
        from agent.envio_gate import (
            registrar_envio_realizado,
            contexto_envio_directo,
        )

        llamado = {"n": 0}

        async def _contar(telefono):
            llamado["n"] += 1

        monkeypatch.setattr(memoria, "incrementar_mensajes_proactivos", _contar)

        with contexto_envio_directo(TEL):
            await registrar_envio_realizado(TEL)

        assert llamado["n"] == 0
