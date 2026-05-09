# tests/test_onboarding_negocio_extendido.py — Tests T2.0.E.1

"""
Tests para el flujo extendido del onboarding de negocio (T2.0.E.1).

Cubre:
  - Trigger 'diagnóstico' / 'diagnostico' / 'empezar diagnóstico'
  - Pasos 4-9 (oferta, cliente_ideal, objetivo_mes, canales,
    bloqueo, tareas_delegar) capturan el campo correcto
  - Idempotencia: re-recibir el mismo paso no avanza dos veces
  - Flow completo end-to-end: paso 0 → 9 → completado (None)
  - Migración runtime: las 6 columnas existen tras inicializar_db
  - Rechazos ('omitir', 'no', 'skip') vacían el campo del paso
  - Cap de 500 chars para texto libre · evita persistir bloques enormes
  - NO se loguea el contenido bruto de las respuestas (solo paso/length)
"""

import importlib
import logging
import pytest

import agent.memory
import agent.business.onboarding_negocio as onb


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """SQLite aislada por test · recarga módulos para que tomen DATABASE_URL.
    Importante: hay que recargar también agent.business.models para que
    la metadata Base reciba los campos nuevos en la SQLite limpia."""
    db_path = tmp_path / "onb.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _m
    importlib.reload(agent.memory)
    importlib.reload(_m)
    importlib.reload(onb)
    await agent.memory.inicializar_db()
    return onb


# ── Trigger 'diagnóstico' (T2.0.E.1) ─────────────────────────────────────────


class TestTriggerDiagnostico:
    def test_diagnostico_acentuado_en_triggers(self):
        assert "diagnóstico" in onb.TRIGGER_KEYWORDS

    def test_diagnostico_sin_acento_en_triggers(self):
        assert "diagnostico" in onb.TRIGGER_KEYWORDS

    def test_empezar_diagnostico_acentuado(self):
        assert "empezar diagnóstico" in onb.TRIGGER_KEYWORDS

    def test_empezar_diagnostico_sin_acento(self):
        assert "empezar diagnostico" in onb.TRIGGER_KEYWORDS

    def test_texto_default_del_tour_matchea(self):
        # El tour T2.0.D step 8 manda este wa.me text:
        texto = "hola Dona, quiero empezar el diagnóstico de mi negocio."
        match = any(kw in texto.lower() for kw in onb.TRIGGER_KEYWORDS)
        assert match, "El texto del CTA del tour debe activar el flow"

    def test_triggers_legacy_siguen_funcionando(self):
        """Regresión: los triggers v1 no deben romperse."""
        assert "mi negocio" in onb.TRIGGER_KEYWORDS
        assert "configurar negocio" in onb.TRIGGER_KEYWORDS


# ── Mensajes nuevos (T2.0.E.1) ────────────────────────────────────────────────


class TestMensajesExtendidos:
    def test_mensaje_oferta_existe_y_no_vacio(self):
        assert onb.MENSAJE_OFERTA
        assert "oferta" in onb.MENSAJE_OFERTA.lower()

    def test_mensaje_cliente_ideal_existe(self):
        assert "cliente ideal" in onb.MENSAJE_CLIENTE_IDEAL.lower()

    def test_mensaje_objetivo_mes_existe(self):
        assert "objetivo" in onb.MENSAJE_OBJETIVO_MES.lower()

    def test_mensaje_canales_existe(self):
        assert "canales" in onb.MENSAJE_CANALES.lower()

    def test_mensaje_bloqueo_existe(self):
        assert "bloqueo" in onb.MENSAJE_BLOQUEO.lower() or \
               "frustración" in onb.MENSAJE_BLOQUEO.lower()

    def test_mensaje_tareas_delegar_existe(self):
        assert "delegar" in onb.MENSAJE_TAREAS_DELEGAR.lower() or \
               "tareas" in onb.MENSAJE_TAREAS_DELEGAR.lower()


# ── Migración runtime · columnas en SQLite tras inicializar_db ───────────────


class TestMigracionRuntime:
    @pytest.mark.asyncio
    async def test_columnas_nuevas_existen_en_sqlite(self, db):
        """Las 6 columnas T2.0.E.1 deben crearse vía Base.metadata.create_all
        en SQLite (test) y vía MIGRACIONES_NEGOCIO en Postgres (prod)."""
        from sqlalchemy import text as _t
        async with agent.memory.engine.begin() as conn:
            r = await conn.execute(_t("PRAGMA table_info(perfil_negocio)"))
            cols = {row[1] for row in r.fetchall()}
        nuevas = {
            "oferta_principal", "cliente_ideal", "objetivo_mes",
            "canales_actuales", "bloqueo_actual", "tareas_delegar",
        }
        faltantes = nuevas - cols
        assert not faltantes, f"Faltan columnas en perfil_negocio: {faltantes}"

    @pytest.mark.asyncio
    async def test_default_columnas_es_string_vacio(self, db):
        """Default de los 6 campos nuevos debe ser '' · no NULL."""
        await db.iniciar_onboarding_negocio("5551")
        from agent.business.models import PerfilNegocio
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(PerfilNegocio).where(PerfilNegocio.telefono == "5551")
            )
            p = r.scalar_one()
        assert p.oferta_principal == ""
        assert p.cliente_ideal == ""
        assert p.objetivo_mes == ""
        assert p.canales_actuales == ""
        assert p.bloqueo_actual == ""
        assert p.tareas_delegar == ""


# ── Flow completo end-to-end ──────────────────────────────────────────────────


class TestFlowCompletoExtendido:
    @pytest.mark.asyncio
    async def test_recorre_los_10_pasos_y_completa(self, db):
        tel = "5550000001"
        await db.iniciar_onboarding_negocio(tel)

        # Pasos 0-3 (clásicos)
        await db.procesar_paso_onboarding(tel, "Mi Pastelería Test")
        await db.procesar_paso_onboarding(tel, "1")  # comida
        await db.procesar_paso_onboarding(tel, "MXN")
        await db.procesar_paso_onboarding(tel, "50000")

        # Pasos 4-9 (T2.0.E.1)
        await db.procesar_paso_onboarding(tel, "Pasteles para eventos")
        await db.procesar_paso_onboarding(tel, "Familias en CDMX para fiestas")
        await db.procesar_paso_onboarding(tel, "10 pedidos nuevos este mes")
        await db.procesar_paso_onboarding(tel, "WhatsApp, Instagram, referidos")
        await db.procesar_paso_onboarding(tel, "Responder mensajes a tiempo")
        msg_final = await db.procesar_paso_onboarding(
            tel, "Cotizaciones automáticas y recordatorios"
        )

        # Resultado: onboarding_paso = None, todos los campos guardados
        from agent.business.models import PerfilNegocio
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(PerfilNegocio).where(PerfilNegocio.telefono == tel)
            )
            p = r.scalar_one()

        assert p.onboarding_paso is None
        assert p.nombre_negocio == "Mi Pastelería Test"
        assert p.industria == "comida"
        assert p.moneda == "MXN"
        assert p.meta_mensual == 50000.0
        assert p.oferta_principal == "Pasteles para eventos"
        assert p.cliente_ideal == "Familias en CDMX para fiestas"
        assert p.objetivo_mes == "10 pedidos nuevos este mes"
        assert p.canales_actuales == "WhatsApp, Instagram, referidos"
        assert p.bloqueo_actual == "Responder mensajes a tiempo"
        assert p.tareas_delegar == "Cotizaciones automáticas y recordatorios"

        # Mensaje final muestra el resumen estructurado clásico
        assert "Mi Pastelería Test" in msg_final
        assert "MXN" in msg_final
        assert "50,000" in msg_final


# ── Pasos individuales · cada uno persiste en su campo ──────────────────────


class TestPasosExtendidosIndividuales:
    @pytest.mark.asyncio
    async def test_paso_4_persiste_oferta_principal(self, db):
        tel = "5550000004"
        await self._llegar_a_paso(db, tel, 4)
        ret = await db.procesar_paso_onboarding(tel, "Servicio de catering")
        # El siguiente prompt debe ser cliente_ideal
        assert ret is not None
        assert "cliente ideal" in ret.lower()
        assert (await self._campo(tel, "oferta_principal")) == "Servicio de catering"

    @pytest.mark.asyncio
    async def test_paso_5_persiste_cliente_ideal(self, db):
        tel = "5550000005"
        await self._llegar_a_paso(db, tel, 5)
        ret = await db.procesar_paso_onboarding(tel, "Empresas medianas")
        assert "objetivo" in ret.lower()
        assert (await self._campo(tel, "cliente_ideal")) == "Empresas medianas"

    @pytest.mark.asyncio
    async def test_paso_6_persiste_objetivo_mes(self, db):
        tel = "5550000006"
        await self._llegar_a_paso(db, tel, 6)
        ret = await db.procesar_paso_onboarding(tel, "Cerrar 5 ventas grandes")
        assert "canales" in ret.lower()
        assert (await self._campo(tel, "objetivo_mes")) == "Cerrar 5 ventas grandes"

    @pytest.mark.asyncio
    async def test_paso_7_persiste_canales_actuales(self, db):
        tel = "5550000007"
        await self._llegar_a_paso(db, tel, 7)
        ret = await db.procesar_paso_onboarding(tel, "Instagram y referidos")
        assert "bloqueo" in ret.lower() or "frustración" in ret.lower()
        assert (await self._campo(tel, "canales_actuales")) == "Instagram y referidos"

    @pytest.mark.asyncio
    async def test_paso_8_persiste_bloqueo_actual(self, db):
        tel = "5550000008"
        await self._llegar_a_paso(db, tel, 8)
        ret = await db.procesar_paso_onboarding(tel, "No tengo tiempo para vender")
        assert "delegar" in ret.lower() or "tareas" in ret.lower()
        assert (
            await self._campo(tel, "bloqueo_actual")
        ) == "No tengo tiempo para vender"

    @pytest.mark.asyncio
    async def test_paso_9_persiste_tareas_delegar_y_completa(self, db):
        tel = "5550000009"
        await self._llegar_a_paso(db, tel, 9)
        ret = await db.procesar_paso_onboarding(tel, "Cobranza y seguimiento")
        # Mensaje completado
        assert ret is not None
        assert "configurado" in ret.lower() or "🎉" in ret
        assert (
            await self._campo(tel, "tareas_delegar")
        ) == "Cobranza y seguimiento"
        # Onboarding paso debe ser None
        from agent.business.models import PerfilNegocio
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(PerfilNegocio).where(PerfilNegocio.telefono == tel)
            )
            assert r.scalar_one().onboarding_paso is None

    # ── helpers ────────────────────────────────────────────────────────
    async def _llegar_a_paso(self, db, tel, paso_destino):
        """Avanza el flow hasta dejar onboarding_paso = paso_destino."""
        await db.iniciar_onboarding_negocio(tel)
        respuestas = ["Negocio Test", "1", "MXN", "10000",
                      "oferta", "cliente", "objetivo", "canales", "bloqueo"]
        # Ejecutar paso 0 hasta paso_destino - 1
        for i in range(paso_destino):
            await db.procesar_paso_onboarding(tel, respuestas[i])

    async def _campo(self, tel, nombre):
        from agent.business.models import PerfilNegocio
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(PerfilNegocio).where(PerfilNegocio.telefono == tel)
            )
            return getattr(r.scalar_one(), nombre)


# ── Rechazos · "omitir" deja el campo vacío ──────────────────────────────────


class TestRechazos:
    @pytest.mark.parametrize("respuesta", [
        "omitir", "OMITIR", "no", "No", "skip", "saltar", "ninguno", "nada",
        "no sé", "luego", "más tarde",
    ])
    @pytest.mark.asyncio
    async def test_rechazo_paso_oferta_deja_vacio(self, db, respuesta):
        tel = f"5559900{abs(hash(respuesta)) % 1000:03d}"
        # Avanzar a paso 4
        await db.iniciar_onboarding_negocio(tel)
        for r in ["Negocio", "1", "MXN", "10000"]:
            await db.procesar_paso_onboarding(tel, r)
        # Paso 4 con rechazo
        nxt = await db.procesar_paso_onboarding(tel, respuesta)
        assert nxt is not None
        assert "cliente ideal" in nxt.lower()
        # Campo vacío
        from agent.business.models import PerfilNegocio
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(PerfilNegocio).where(PerfilNegocio.telefono == tel)
            )
            assert r.scalar_one().oferta_principal == ""


# ── Cap de 500 chars · evita bloques enormes ─────────────────────────────────


class TestCapTextoLibre:
    @pytest.mark.asyncio
    async def test_oferta_se_capa_a_500_chars(self, db):
        tel = "5557770001"
        # Avanzar a paso 4
        await db.iniciar_onboarding_negocio(tel)
        for r in ["Neg", "1", "MXN", "0"]:
            await db.procesar_paso_onboarding(tel, r)
        # Mensaje grande
        big = "a" * 1000
        await db.procesar_paso_onboarding(tel, big)
        from agent.business.models import PerfilNegocio
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(PerfilNegocio).where(PerfilNegocio.telefono == tel)
            )
            p = r.scalar_one()
        assert len(p.oferta_principal) == 500


# ── Logging seguro · no se loguea el contenido bruto ────────────────────────


class TestLoggingSeguro:
    @pytest.mark.asyncio
    async def test_no_loguea_texto_libre_del_usuario(self, db, caplog):
        tel = "5556660001"
        await db.iniciar_onboarding_negocio(tel)
        # Pasos 0-3
        for r in ["Mi Tienda", "3", "MXN", "10000"]:
            await db.procesar_paso_onboarding(tel, r)
        # Paso 4 con respuesta sensible
        secreto = "El cliente Juan Pérez (+5215555111222) compró pasteles"
        with caplog.at_level(logging.INFO, logger="dona"):
            caplog.clear()
            await db.procesar_paso_onboarding(tel, secreto)
        # Ningún log debe contener el texto crudo
        for record in caplog.records:
            msg = record.getMessage()
            assert "Juan Pérez" not in msg
            assert "5215555111222" not in msg
            assert secreto not in msg
        # Pero sí debe loguear paso/length
        relevant = [r.getMessage() for r in caplog.records
                    if "BIZ-ONBOARD" in r.getMessage()]
        assert any("paso=" in m and "resp_len=" in m for m in relevant)

    @pytest.mark.asyncio
    async def test_no_loguea_telefono_completo(self, db, caplog):
        tel = "5215551234567"
        with caplog.at_level(logging.INFO, logger="dona"):
            caplog.clear()
            await db.iniciar_onboarding_negocio(tel)
            await db.procesar_paso_onboarding(tel, "Mi Negocio")
        for record in caplog.records:
            msg = record.getMessage()
            if "BIZ-ONBOARD" in msg:
                # Mismo telefono completo NO debe estar en el log
                assert "5215551234567" not in msg


# ── Idempotencia · re-recibir el mismo paso ─────────────────────────────────


class TestIdempotencia:
    @pytest.mark.asyncio
    async def test_paso_4_no_avanza_dos_veces_si_ya_paso(self, db):
        """Si el matcher ya avanzó del paso 4, una nueva invocación con
        otro texto no debe re-procesarlo como paso 4."""
        tel = "5552220001"
        await db.iniciar_onboarding_negocio(tel)
        for r in ["Neg", "1", "MXN", "0"]:
            await db.procesar_paso_onboarding(tel, r)
        # Paso 4
        await db.procesar_paso_onboarding(tel, "Oferta original")
        # Estamos en paso 5 ahora
        await db.procesar_paso_onboarding(tel, "Cliente ideal A")
        # oferta_principal no debe haber cambiado
        from agent.business.models import PerfilNegocio
        from sqlalchemy import select
        async with agent.memory.async_session() as session:
            r = await session.execute(
                select(PerfilNegocio).where(PerfilNegocio.telefono == tel)
            )
            p = r.scalar_one()
        assert p.oferta_principal == "Oferta original"
        assert p.cliente_ideal == "Cliente ideal A"

    @pytest.mark.asyncio
    async def test_no_perfil_o_paso_none_retorna_none(self, db):
        # Sin perfil
        ret = await db.procesar_paso_onboarding("5550000999", "hola")
        assert ret is None
        # Con perfil completado
        tel = "5550000998"
        await db.iniciar_onboarding_negocio(tel)
        for r in ["N", "1", "MXN", "0", "a", "b", "c", "d", "e", "f"]:
            await db.procesar_paso_onboarding(tel, r)
        ret = await db.procesar_paso_onboarding(tel, "tarde")
        assert ret is None  # ya completó


# ── esta_en_onboarding_negocio cubre los pasos 4-9 ──────────────────────────


class TestEstaEnOnboarding:
    @pytest.mark.asyncio
    async def test_estado_paso_4(self, db):
        tel = "5551110004"
        await db.iniciar_onboarding_negocio(tel)
        for r in ["Neg", "1", "MXN", "0"]:
            await db.procesar_paso_onboarding(tel, r)
        # Ahora está en paso 4
        assert await db.esta_en_onboarding_negocio(tel) is True

    @pytest.mark.asyncio
    async def test_estado_completado_falso(self, db):
        tel = "5551110099"
        await db.iniciar_onboarding_negocio(tel)
        for r in ["N", "1", "MXN", "0", "a", "b", "c", "d", "e", "f"]:
            await db.procesar_paso_onboarding(tel, r)
        assert await db.esta_en_onboarding_negocio(tel) is False
