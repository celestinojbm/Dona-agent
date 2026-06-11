# tests/test_consent_terceros.py — Fase 0 · 2.5: consentimiento de terceros

"""
REGRESIÓN 2.5 (audit Fable 5 + política Hermes 2026-06-10): el ejecutor HIGH
enviaba WhatsApp a TERCEROS fríos (que nunca hablaron con Dona) sin
consentimiento del owner, sin copy de identificación/opt-out y sin límites
por destino ni por owner.

Política implementada ("block until owner affirmative consent per destination"):
  - Flujo dedicado: el preview muestra el texto de permiso y el mensaje FINAL
    (con identificación + PARAR si es primer contacto); el ENVIAR posterior
    registra el consentimiento ANTES de ejecutar.
  - Ejecutor (defensa en profundidad): destino frío sin consentimiento FRESCO
    → RuntimeError fail-closed, venga de donde venga el caller.
  - Best-effort (solo gate de opt-out) queda para destinos que YA hablaron
    con Dona.
  - Límites: 2/día y 3/7d por destino sin respuesta; 8/día si respondió o es
    conocido; 10 terceros nuevos/día y 30/7d por owner.

Los tests marcados REGRESIÓN fallan contra el código viejo.
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta

import pytest


OWNER = "15550009999"
FRIO = "15557770001"
FRIO2 = "15557770002"


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
async def entorno(tmp_path, monkeypatch):
    db_path = tmp_path / "consent.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    import agent.memory
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

    # El flujo dedicado completo ejecuta el ciclo real de créditos.
    await _bi.acreditar(OWNER, 50, "seed")

    import agent.automation.consent_terceros as consent
    return agent.memory, consent


def _proveedor_fake():
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


def _accion_dict(accion_id: int, destino: str, mensaje: str = "su pedido está listo"):
    return {
        "id": accion_id,
        "telefono": OWNER,
        "payload_json": json.dumps({"numero_destino": destino, "mensaje": mensaje}),
    }


@pytest.fixture
def ejecutor_aislado(monkeypatch):
    """Ejecutor con idempotencia/persist en no-op y proveedor fake."""
    import agent.automation.executors.send_message as sm

    fake = _proveedor_fake()

    async def _sin_resultado(accion_id):
        return None

    async def _persistir_ok(accion_id, resultado):
        return None

    monkeypatch.setattr(sm, "_obtener_proveedor", lambda: fake)
    monkeypatch.setattr(sm, "_leer_result_actual", _sin_resultado)
    monkeypatch.setattr(sm, "_persistir_result_inline", _persistir_ok)
    return sm, fake


async def _seed_envios(memoria, destino: str, cuando: list[datetime], owner: str = OWNER):
    from agent.automation.models import EnvioTerceroAutomation
    async with memoria.async_session() as session:
        for ts in cuando:
            session.add(EnvioTerceroAutomation(
                telefono_owner=owner, destino=destino, accion_id=None, enviado_en=ts,
            ))
        await session.commit()


# ── 1. Ejecutor · defensa en profundidad (REGRESIÓN núcleo) ──────────────


class TestEjecutorDefensaProfundidad:
    async def test_destino_frio_sin_consentimiento_bloqueado(self, entorno, ejecutor_aislado):
        """REGRESIÓN: el código viejo enviaba a un tercero frío sin ningún
        consentimiento del owner."""
        _, _ = entorno
        sm, fake = ejecutor_aislado

        with pytest.raises(RuntimeError, match="consent_no_registrado"):
            await sm.ejecutor_enviar_mensaje_whatsapp(_accion_dict(11, FRIO), None)

        assert fake.enviados == []

    async def test_con_consentimiento_fresco_envia_con_copy(self, entorno, ejecutor_aislado):
        """Con consentimiento registrado, el primer contacto sale con
        identificación + opt-out PARAR, y el envío queda logueado."""
        memoria, consent = entorno
        sm, fake = ejecutor_aislado

        await consent.registrar_consentimiento(OWNER, FRIO, 12)
        resultado = await sm.ejecutor_enviar_mensaje_whatsapp(_accion_dict(12, FRIO), None)

        assert resultado["estado_envio"] == "sent"
        assert resultado["primer_contacto"] is True
        assert len(fake.enviados) == 1
        _, cuerpo = fake.enviados[0]
        assert "soy Dona" in cuerpo
        assert "PARAR" in cuerpo
        assert "su pedido está listo" in cuerpo

        from sqlalchemy import select, func
        from agent.automation.models import EnvioTerceroAutomation
        async with memoria.async_session() as session:
            n = (await session.execute(
                select(func.count()).where(EnvioTerceroAutomation.destino == FRIO)
            )).scalar()
        assert n == 1

    async def test_consentimiento_viejo_no_sirve(self, entorno, ejecutor_aislado):
        """El consentimiento expira (ventana de frescura): uno registrado
        hace una hora no habilita un envío de otro camino — aunque sea de
        la MISMA acción."""
        memoria, consent = entorno
        sm, fake = ejecutor_aislado

        from agent.automation.models import ConsentimientoTerceroAutomation
        async with memoria.async_session() as session:
            session.add(ConsentimientoTerceroAutomation(
                telefono_owner=OWNER, destino=FRIO, source_accion_id=13,
                creado=datetime.utcnow() - timedelta(hours=1),
            ))
            await session.commit()

        with pytest.raises(RuntimeError, match="consent_no_registrado"):
            await sm.ejecutor_enviar_mensaje_whatsapp(_accion_dict(13, FRIO), None)
        assert fake.enviados == []

    async def test_consentimiento_de_otra_accion_no_sirve(self, entorno, ejecutor_aislado):
        """Invariante Hermes (visto bueno 2.5, condición #6): el consent
        scope=este_mensaje está atado a SU accion_id — uno fresco de la
        acción 21 NO habilita la acción 22 al mismo destino."""
        _, consent = entorno
        sm, fake = ejecutor_aislado

        await consent.registrar_consentimiento(OWNER, FRIO, 21)

        with pytest.raises(RuntimeError, match="consent_no_registrado"):
            await sm.ejecutor_enviar_mensaje_whatsapp(_accion_dict(22, FRIO), None)
        assert fake.enviados == []

    async def test_destino_conocido_pasa_sin_consentimiento(self, entorno, ejecutor_aislado):
        """Best-effort para quien YA habló con Dona: solo el gate de opt-out
        aplica, sin consent ni copy de primer contacto."""
        memoria, _ = entorno
        sm, fake = ejecutor_aislado

        await memoria.guardar_mensaje(FRIO, "user", "hola dona")
        resultado = await sm.ejecutor_enviar_mensaje_whatsapp(_accion_dict(14, FRIO), None)

        assert resultado["estado_envio"] == "sent"
        assert resultado["primer_contacto"] is False
        _, cuerpo = fake.enviados[0]
        assert "soy Dona" not in cuerpo  # sin copy de primer contacto

    async def test_fail_closed_politica_rota(self, entorno, ejecutor_aislado, monkeypatch):
        _, _ = entorno
        sm, fake = ejecutor_aislado

        async def _explota(owner, destino):
            raise ValueError("db caída")

        import agent.automation.consent_terceros as consent_mod
        monkeypatch.setattr(consent_mod, "evaluar_politica_envio_tercero", _explota)

        with pytest.raises(RuntimeError, match="politica_terceros_error"):
            await sm.ejecutor_enviar_mensaje_whatsapp(_accion_dict(15, FRIO), None)
        assert fake.enviados == []


# ── 2. Flujo dedicado completo ───────────────────────────────────────────


class TestFlujoDedicado:
    async def _preparar_y_aprobar(self, destino: str, mensaje: str = "su pedido está listo"):
        from agent.automation.executors.send_message import preparar_enviar_mensaje_whatsapp
        from agent.automation.action_center import aprobar_accion

        accion = await preparar_enviar_mensaje_whatsapp(
            telefono=OWNER, numero_destino=destino, mensaje=mensaje,
        )
        await aprobar_accion(accion["id"])
        return accion["id"]

    async def test_preview_pide_consentimiento_para_frio(self, entorno, ejecutor_aislado):
        from agent.automation.executors.send_message import preview_confirmacion_high_whatsapp

        _, consent = entorno
        accion_id = await self._preparar_y_aprobar(FRIO)
        preview = await preview_confirmacion_high_whatsapp(accion_id, OWNER)

        assert preview["ok"] is True
        assert preview["requiere_consentimiento"] is True
        assert preview["es_primer_contacto"] is True
        assert preview["texto_consentimiento"] == consent.TEXTO_CONSENTIMIENTO_OWNER
        # El owner ve el mensaje FINAL que saldría (con PARAR)
        assert "PARAR" in preview["mensaje_preview"]
        assert "su pedido está listo" in preview["mensaje_preview"]

    async def test_preview_conocido_sin_consentimiento(self, entorno, ejecutor_aislado):
        memoria, _ = entorno
        await memoria.guardar_mensaje(FRIO, "user", "hola")
        from agent.automation.executors.send_message import preview_confirmacion_high_whatsapp

        accion_id = await self._preparar_y_aprobar(FRIO)
        preview = await preview_confirmacion_high_whatsapp(accion_id, OWNER)

        assert preview["ok"] is True
        assert preview["requiere_consentimiento"] is False
        assert preview["texto_consentimiento"] == ""
        assert preview["mensaje_preview"] == "su pedido está listo"

    async def test_confirmar_registra_consentimiento_y_envia(self, entorno, ejecutor_aislado):
        """REGRESIÓN (contrato 2.5): confirmar con ENVIAR registra el
        consentimiento ANTES de ejecutar y el envío sale compuesto."""
        from agent.automation.executors.send_message import confirmar_high_whatsapp_dedicado

        memoria, _ = entorno
        _, fake = ejecutor_aislado
        accion_id = await self._preparar_y_aprobar(FRIO)

        resultado = await confirmar_high_whatsapp_dedicado(accion_id, "ENVIAR", OWNER)

        assert resultado.get("estado_final") == "completed", resultado
        assert len(fake.enviados) == 1
        assert "PARAR" in fake.enviados[0][1]

        from sqlalchemy import select
        from agent.automation.models import ConsentimientoTerceroAutomation
        async with memoria.async_session() as session:
            fila = (await session.execute(
                select(ConsentimientoTerceroAutomation).where(
                    ConsentimientoTerceroAutomation.destino == FRIO
                )
            )).scalars().first()
        assert fila is not None
        assert fila.telefono_owner == OWNER
        assert fila.source_accion_id == accion_id
        assert fila.scope == "este_mensaje"
        assert "permiso" in fila.texto_confirmacion

    async def test_confirmar_bloquea_por_limite_owner(self, entorno, ejecutor_aislado):
        """10 terceros nuevos hoy → el 11º se bloquea en preview Y confirmar."""
        from agent.automation.executors.send_message import (
            preview_confirmacion_high_whatsapp,
            confirmar_high_whatsapp_dedicado,
        )

        memoria, _ = entorno
        _, fake = ejecutor_aislado
        ahora = datetime.utcnow()
        for i in range(10):
            await _seed_envios(memoria, f"1555000{i:04d}", [ahora - timedelta(hours=1)])

        accion_id = await self._preparar_y_aprobar(FRIO)
        preview = await preview_confirmacion_high_whatsapp(accion_id, OWNER)
        assert preview["ok"] is False
        assert preview["error"] == "limite_owner_terceros_dia"

        resultado = await confirmar_high_whatsapp_dedicado(accion_id, "ENVIAR", OWNER)
        assert resultado.get("estado_final") == "failed"
        assert resultado.get("error") == "limite_owner_terceros_dia"
        assert fake.enviados == []


# ── 3. Política · límites por destino ────────────────────────────────────


class TestPoliticaLimites:
    async def test_destino_sin_respuesta_2_por_dia(self, entorno):
        memoria, consent = entorno
        ahora = datetime.utcnow()
        await _seed_envios(memoria, FRIO, [ahora - timedelta(hours=2), ahora - timedelta(hours=1)])

        politica = await consent.evaluar_politica_envio_tercero(OWNER, FRIO)
        assert politica["permitido"] is False
        assert politica["motivo"] == "limite_destino_dia"

    async def test_destino_sin_respuesta_3_por_semana(self, entorno):
        memoria, consent = entorno
        ahora = datetime.utcnow()
        await _seed_envios(memoria, FRIO, [
            ahora - timedelta(days=2),
            ahora - timedelta(days=3),
            ahora - timedelta(days=4),
        ])

        politica = await consent.evaluar_politica_envio_tercero(OWNER, FRIO)
        assert politica["permitido"] is False
        assert politica["motivo"] == "limite_destino_7d"

    async def test_destino_que_respondio_sube_a_8(self, entorno):
        memoria, consent = entorno
        ahora = datetime.utcnow()
        # Primer envío hace 2 días; el destino respondió ayer
        await _seed_envios(memoria, FRIO, [ahora - timedelta(days=2)])
        await memoria.guardar_mensaje(FRIO, "user", "sí, me interesa")

        # 4 envíos hoy (>2) no bloquean porque respondió
        await _seed_envios(memoria, FRIO, [ahora - timedelta(hours=h) for h in (1, 2, 3, 4)])
        politica = await consent.evaluar_politica_envio_tercero(OWNER, FRIO)
        assert politica["permitido"] is True

        # 8 hoy → tope del tier con respuesta
        await _seed_envios(memoria, FRIO, [ahora - timedelta(minutes=m) for m in (10, 20, 30, 40)])
        politica = await consent.evaluar_politica_envio_tercero(OWNER, FRIO)
        assert politica["permitido"] is False
        assert politica["motivo"] == "limite_destino_dia"

    async def test_owner_30_nuevos_por_semana(self, entorno):
        memoria, consent = entorno
        hace_3d = datetime.utcnow() - timedelta(days=3)
        for i in range(30):
            await _seed_envios(memoria, f"1555111{i:04d}", [hace_3d])

        politica = await consent.evaluar_politica_envio_tercero(OWNER, FRIO2)
        assert politica["permitido"] is False
        assert politica["motivo"] == "limite_owner_terceros_7d"

    async def test_normalizar_destino(self, entorno):
        _, consent = entorno
        assert consent.normalizar_destino("+1 (555) 777-0001") == "15557770001"

    async def test_componer_trunca_cuerpo_no_el_pie(self, entorno):
        _, consent = entorno
        compuesto = consent.componer_mensaje_primer_contacto("Ana", "x" * 5000)
        assert len(compuesto) <= 4000
        assert compuesto.endswith("_Si no quieres recibir más mensajes, responde *PARAR*._")
        assert "soy Dona" in compuesto


# ── 4. PARAR es opt-out TCPA ─────────────────────────────────────────────


class TestPararKeyword:
    def test_parar_es_stop(self):
        from agent.proactivity import es_comando_stop_tcpa
        assert es_comando_stop_tcpa("PARAR") is True
        assert es_comando_stop_tcpa("parar.") is True
        assert es_comando_stop_tcpa("quiero parar un rato") is False
