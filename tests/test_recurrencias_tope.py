# tests/test_recurrencias_tope.py — Fase 0 · 2.4: tope de recurrencias + catch-up

"""
REGRESIÓN 2.4 (audit Fable 5 2026-06-09): (a) recurrencias sub-diarias sin
fecha_fin ni tope → mensajes cada 30/60 min PARA SIEMPRE; (b) catch-up storm:
tras un downtime, _calcular_proxima_ocurrencia avanzaba de a UN paso, así que
fecha_hora quedaba en el pasado y cada tick del scheduler reenviaba hasta
ponerse al día (12h de downtime con cada_30_minutos = ~24 mensajes seguidos).

Política (criterio Hermes): el atraso se SANEA avanzando al futuro, no
reenviando. Catch-up máx 1 y solo FRESCO (45min sub-diarias de 30min, 90min
horarias, 6h diarias+). fecha_fin default de 7 días para sub-diarias nuevas;
contención lógica equivalente para las existentes. Cap diario por tarea
(16/12) como cinturón. Catch-up de diarias+ no entra en quiet hours locales.

Los tests marcados REGRESIÓN fallan contra el código viejo.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from datetime import datetime, timedelta

import pytest


TEL = "15550004444"


@pytest.fixture
async def entorno(tmp_path, monkeypatch):
    db_path = tmp_path / "recurr.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    import agent.memory
    import agent.business.models as _bm
    import agent.automation.models as _am
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    await agent.memory.inicializar_db()

    import agent.scheduler as _sch
    importlib.reload(_sch)
    _sch._recordatorios_gcal_enviados_mem.clear()
    _sch._envios_recurrentes_hoy.clear()

    return agent.memory, _sch


def _proveedor_fake():
    from agent.providers.base import ProveedorWhatsApp

    class FakeProveedor(ProveedorWhatsApp):
        def __init__(self):
            self.enviados: list[tuple[str, str]] = []
            self.devolver = True

        async def parsear_webhook(self, request):
            return []

        async def _enviar_mensaje_impl(self, telefono, mensaje):
            self.enviados.append((telefono, mensaje))
            return self.devolver

    return FakeProveedor()


async def _seed(memoria, *, atraso: timedelta, recurrencia: dict | None,
                fecha_fin: datetime | None = None,
                creado: datetime | None = None) -> int:
    async with memoria.async_session() as session:
        r = memoria.Recordatorio(
            telefono=TEL,
            mensaje="tomar agua",
            fecha_hora=datetime.utcnow() - atraso,
            recurrencia=json.dumps(recurrencia) if recurrencia else None,
            fecha_fin=fecha_fin,
            creado=creado or datetime.utcnow(),
        )
        session.add(r)
        await session.commit()
        return r.id


async def _fecha_hora(memoria, rid: int):
    from sqlalchemy import select
    async with memoria.async_session() as session:
        r = (await session.execute(
            select(memoria.Recordatorio).where(memoria.Recordatorio.id == rid)
        )).scalar_one()
        return r


async def _limpiar_claim(memoria, rid: int):
    """Backdatea el claim (ultimo_envio) para que NO enmascare al test: el
    storm real aparece cuando la ventana del claim de 2.3 expira."""
    from sqlalchemy import update
    async with memoria.async_session() as session:
        await session.execute(
            update(memoria.Recordatorio)
            .where(memoria.Recordatorio.id == rid)
            .values(ultimo_envio=datetime.utcnow() - timedelta(minutes=30))
        )
        await session.commit()


def _offset_para_hora_local(hora_objetivo: int) -> int:
    ahora = datetime.utcnow()
    minutos_utc = ahora.hour * 60 + ahora.minute
    return (hora_objetivo * 60 + 30 - minutos_utc) % 1440


# ── 1. Catch-up storm (REGRESIÓN núcleo) ─────────────────────────────────


class TestCatchUpStorm:
    async def test_downtime_12h_cada_30_no_envia_y_avanza(self, entorno):
        """REGRESIÓN: 12h de atraso en cada_30_minutos. Viejo: enviaba YA y
        dejaba fecha_hora en el pasado (storm de un envío por tick). Nuevo:
        0 envíos y fecha_hora saneada al futuro."""
        memoria, sch = entorno
        rid = await _seed(memoria, atraso=timedelta(hours=12),
                          recurrencia={"tipo": "cada_30_minutos"})

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert fake.enviados == []
        r = await _fecha_hora(memoria, rid)
        assert r.fecha_hora > datetime.utcnow()

    async def test_ticks_repetidos_tras_downtime_siguen_en_cero(self, entorno):
        memoria, sch = entorno
        rid = await _seed(memoria, atraso=timedelta(hours=12),
                          recurrencia={"tipo": "cada_30_minutos"})

        fake = _proveedor_fake()
        for _ in range(3):
            await sch._verificar_y_enviar_recordatorios_impl(fake)
            await _limpiar_claim(memoria, rid)

        assert fake.enviados == []

    async def test_atraso_fresco_envia_una_vez_y_no_repite(self, entorno):
        """REGRESIÓN: atraso de 40 min (fresco, <45) en cada_30_minutos.
        Viejo: enviaba y avanzaba fecha_hora a -10 min (pasado) → el
        siguiente tick re-enviaba. Nuevo: envía 1 y avanza al futuro."""
        memoria, sch = entorno
        rid = await _seed(memoria, atraso=timedelta(minutes=40),
                          recurrencia={"tipo": "cada_30_minutos"})

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)
        assert len(fake.enviados) == 1
        r = await _fecha_hora(memoria, rid)
        assert r.fecha_hora > datetime.utcnow()

        await _limpiar_claim(memoria, rid)
        await sch._verificar_y_enviar_recordatorios_impl(fake)
        assert len(fake.enviados) == 1

    async def test_diario_atraso_corto_envia_atraso_largo_sanea(self, entorno):
        """Diarias+: máx 1 catch-up y solo si el atraso es razonable (6h)."""
        memoria, sch = entorno
        fake = _proveedor_fake()

        await _seed(memoria, atraso=timedelta(hours=2),
                    recurrencia={"tipo": "diario"})
        await sch._verificar_y_enviar_recordatorios_impl(fake)
        assert len(fake.enviados) == 1  # catch-up fresco permitido

        rid2 = await _seed(memoria, atraso=timedelta(hours=8),
                           recurrencia={"tipo": "diario"})
        await sch._verificar_y_enviar_recordatorios_impl(fake)
        assert len(fake.enviados) == 1  # atraso de 8h → saneado sin envío
        r2 = await _fecha_hora(memoria, rid2)
        assert r2.fecha_hora > datetime.utcnow()

    async def test_unico_atrasado_si_se_envia(self, entorno):
        """Control: un aviso único explícito llega aunque sea tarde (mejor
        tarde que nunca) — sin cambio de comportamiento."""
        memoria, sch = entorno
        await _seed(memoria, atraso=timedelta(hours=12), recurrencia=None)

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert len(fake.enviados) == 1

    async def test_fallo_de_envio_no_multiplica(self, entorno):
        """Aceptación Hermes: un fallo del proveedor no convierte el
        reintento en catch-up múltiple."""
        memoria, sch = entorno
        rid = await _seed(memoria, atraso=timedelta(minutes=5),
                          recurrencia={"tipo": "cada_30_minutos"})

        fake = _proveedor_fake()
        fake.devolver = False
        await sch._verificar_y_enviar_recordatorios_impl(fake)
        assert len(fake.enviados) == 1  # intento fallido (impl llamado)

        fake.devolver = True
        await sch._verificar_y_enviar_recordatorios_impl(fake)  # claim liberado por el fallo
        # El tick de recuperación manda recordatorio + aviso de canal
        # recuperado; lo que se pina es que el RECORDATORIO salió una vez
        # más (un reintento), no una tormenta.
        recordatorios = [m for _, m in fake.enviados if "tomar agua" in m]
        assert len(recordatorios) == 2
        r = await _fecha_hora(memoria, rid)
        assert r.fecha_hora > datetime.utcnow()


# ── 2. fecha_fin: default y contención ───────────────────────────────────


class TestFechaFin:
    async def test_sub_diaria_nueva_recibe_default_7_dias(self, entorno):
        """REGRESIÓN: guardar cada_30_minutos sin fecha_fin quedaba infinito."""
        memoria, _ = entorno
        r = await memoria.guardar_recordatorio(
            TEL, "hidratarse", datetime.utcnow() + timedelta(minutes=30),
            recurrencia={"tipo": "cada_30_minutos"},
        )
        assert r.fecha_fin is not None
        delta = r.fecha_fin - datetime.utcnow()
        assert timedelta(days=6, hours=23) < delta <= timedelta(days=7, minutes=5)

    async def test_diaria_nueva_sin_default(self, entorno):
        """El default solo aplica a sub-diarias; una diaria puede ser abierta."""
        memoria, _ = entorno
        r = await memoria.guardar_recordatorio(
            TEL, "revisar caja", datetime.utcnow() + timedelta(hours=1),
            recurrencia={"tipo": "diario"},
        )
        assert r.fecha_fin is None

    async def test_recurrencia_desconocida_se_degrada_a_una_vez(self, entorno):
        """2.4: un tipo de recurrencia fuera del set canónico (p.ej. alucinado
        por el LLM, que deja el tipo libre en el schema) NO se persiste como
        recurrencia — se guarda como una sola vez, evitando una recurrencia que
        el scheduler no sabría acotar (quedaría sin tope / se auto-cancelaría)."""
        memoria, _ = entorno
        r = await memoria.guardar_recordatorio(
            TEL, "algo raro", datetime.utcnow() + timedelta(minutes=10),
            recurrencia={"tipo": "cada_minuto"},
        )
        assert r.recurrencia is None   # degradado a una sola vez
        assert r.fecha_fin is None

    async def test_recurrencia_valida_se_conserva(self, entorno):
        """Una recurrencia válida (semanal) sí se persiste como recurrencia."""
        memoria, _ = entorno
        r = await memoria.guardar_recordatorio(
            TEL, "reporte", datetime.utcnow() + timedelta(hours=1),
            recurrencia={"tipo": "semanal", "dia": 0},
        )
        assert r.recurrencia is not None
        assert json.loads(r.recurrencia)["tipo"] == "semanal"

    async def test_fecha_fin_explicita_se_respeta(self, entorno):
        memoria, _ = entorno
        fin = datetime.utcnow() + timedelta(days=2)
        r = await memoria.guardar_recordatorio(
            TEL, "medicina", datetime.utcnow() + timedelta(hours=1),
            recurrencia={"tipo": "cada_hora"}, fecha_fin=fin,
        )
        assert r.fecha_fin == fin

    async def test_sub_diaria_vieja_sin_fecha_fin_queda_contenida(self, entorno):
        """REGRESIÓN: tarea sub-diaria EXISTENTE (pre-default) creada hace 8
        días sin fecha_fin → se cancela sin enviar (contención lógica, sin
        migración). Viejo: seguía enviando para siempre."""
        memoria, sch = entorno
        rid = await _seed(
            memoria, atraso=timedelta(minutes=5),
            recurrencia={"tipo": "cada_30_minutos"},
            creado=datetime.utcnow() - timedelta(days=8),
        )

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert fake.enviados == []
        r = await _fecha_hora(memoria, rid)
        assert r.cancelado is True

    async def test_fecha_fin_vencida_cancela_sin_enviar(self, entorno):
        """REGRESIÓN: con fecha_fin ya pasada, el viejo enviaba UNA ocurrencia
        más antes de cancelar. Nuevo: cancela sin enviar."""
        memoria, sch = entorno
        rid = await _seed(
            memoria, atraso=timedelta(minutes=5),
            recurrencia={"tipo": "diario"},
            fecha_fin=datetime.utcnow() - timedelta(hours=1),
        )

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert fake.enviados == []
        r = await _fecha_hora(memoria, rid)
        assert r.cancelado is True


# ── 3. Cap diario por tarea ──────────────────────────────────────────────


class TestCapDiario:
    async def test_cap_alcanzado_sanea_sin_enviar(self, entorno):
        memoria, sch = entorno
        rid = await _seed(memoria, atraso=timedelta(minutes=5),
                          recurrencia={"tipo": "cada_30_minutos"})

        # Simular que la tarea ya consumió su cap diario (16)
        clave = (rid, sch._clave_dia(datetime.utcnow()))
        sch._envios_recurrentes_hoy[clave] = sch._CAP_DIARIO_SUB_DIARIO["cada_30_minutos"]

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert fake.enviados == []
        r = await _fecha_hora(memoria, rid)
        assert r.fecha_hora > datetime.utcnow()  # avanzó, no quedó atascado

    async def test_envio_incrementa_contador(self, entorno):
        memoria, sch = entorno
        rid = await _seed(memoria, atraso=timedelta(minutes=5),
                          recurrencia={"tipo": "cada_30_minutos"})

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        clave = (rid, sch._clave_dia(datetime.utcnow()))
        assert sch._envios_recurrentes_hoy.get(clave) == 1

    async def test_contadores_de_otros_dias_se_podan(self, entorno):
        _, sch = entorno
        sch._envios_recurrentes_hoy[(99, "2020-01-01")] = 5
        sch._podar_contadores_diarios(datetime.utcnow())
        assert (99, "2020-01-01") not in sch._envios_recurrentes_hoy


# ── 4. Quiet hours en catch-up de diarias+ ───────────────────────────────


class TestQuietHoursCatchUp:
    async def test_catchup_diario_en_madrugada_local_sanea(self, entorno):
        """Un diario atrasado 2h cuya entrega caería a las 3:30 am locales
        NO se entrega: se sanea al futuro (la hora ya no es la elegida)."""
        memoria, sch = entorno
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(3))
        rid = await _seed(memoria, atraso=timedelta(hours=2),
                          recurrencia={"tipo": "diario"})

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert fake.enviados == []
        r = await _fecha_hora(memoria, rid)
        assert r.fecha_hora > datetime.utcnow()

    async def test_catchup_diario_de_dia_se_entrega(self, entorno):
        memoria, sch = entorno
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(11))
        await _seed(memoria, atraso=timedelta(hours=2),
                    recurrencia={"tipo": "diario"})

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert len(fake.enviados) == 1

    async def test_entrega_puntual_no_consulta_quiet_hours(self, entorno):
        """Una ocurrencia puntual (atraso < 15 min) se entrega aunque sea de
        madrugada: esa hora SÍ la eligió el usuario (paridad con el gate)."""
        memoria, sch = entorno
        await memoria.guardar_timezone(TEL, _offset_para_hora_local(3))
        await _seed(memoria, atraso=timedelta(minutes=5),
                    recurrencia={"tipo": "diario"})

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert len(fake.enviados) == 1


# ── 5. avanzar_recurrencia_hasta_futuro (unit) ───────────────────────────


class TestAvanzarHastaFuturo:
    async def test_intervalo_fijo_salta_analiticamente(self, entorno):
        memoria, _ = entorno
        fecha = datetime.utcnow() - timedelta(hours=12)
        proxima, saltadas = memoria.avanzar_recurrencia_hasta_futuro(
            fecha, '{"tipo": "cada_30_minutos"}', None
        )
        assert proxima > datetime.utcnow()
        assert proxima - datetime.utcnow() <= timedelta(minutes=30)
        assert saltadas == 24

    async def test_semanal_muy_atrasado_llega_a_futuro(self, entorno):
        memoria, _ = entorno
        fecha = datetime.utcnow() - timedelta(weeks=10)
        proxima, saltadas = memoria.avanzar_recurrencia_hasta_futuro(
            fecha, json.dumps({"tipo": "semanal", "dia": fecha.weekday()}), None
        )
        assert proxima is not None
        assert proxima > datetime.utcnow()

    async def test_recurrencia_invalida_devuelve_none(self, entorno):
        memoria, _ = entorno
        proxima, _ = memoria.avanzar_recurrencia_hasta_futuro(
            datetime.utcnow() - timedelta(hours=1), '{"tipo": "inexistente"}', None
        )
        assert proxima is None
