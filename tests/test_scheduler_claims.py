# tests/test_scheduler_claims.py — Fase 0 · 2.3: claims atómicos del scheduler

"""
REGRESIÓN 2.3 (audit Fable 5 2026-06-09): los jobs del scheduler hacían
SELECT pendientes → enviar → marcar enviado, sin lock. Con >1 proceso
corriendo el scheduler (gunicorn --workers N, segunda instancia), TODOS los
procesos pasan el SELECT antes de que alguno marque → envíos duplicados de
recordatorios, eventos de Google Calendar y seguimientos CRM.

Fix: claim atómico ANTES de enviar (misma familia que el dedup C9 de #73):
  - Recordatorios: UPDATE condicional sobre `ultimo_envio` con ventana de
    expiración (autosana si un proceso muere tras reclamar) — sin migración.
  - GCal: INSERT ... ON CONFLICT DO NOTHING sobre la PK `clave`.
  - Seguimientos: UPDATE completado false→true; reversión si el envío falla.

Los tests de ticks concurrentes FALLAN contra el código viejo (ambos ticks
envían).
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timedelta

import pytest


TEL = "15550003333"


# ── Fixture ──────────────────────────────────────────────────────────────


@pytest.fixture
async def entorno(tmp_path, monkeypatch):
    """DB SQLite aislada + módulos recargados sobre ella."""
    db_path = tmp_path / "schedlock.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    import agent.memory
    import agent.business.models as _bm
    import agent.automation.models as _am
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    await agent.memory.inicializar_db()

    import agent.business.crm as _crm
    importlib.reload(_crm)

    # scheduler importa funciones de memory a nivel de módulo — re-bindear.
    import agent.scheduler as _sch
    importlib.reload(_sch)
    # El caché GCal in-memory es estado de módulo: aislarlo entre tests.
    _sch._recordatorios_gcal_enviados_mem.clear()

    return agent.memory, _sch, _crm


def _proveedor_fake(demora_s: float = 0.0):
    """Proveedor real (subclase) que registra envíos; la demora opcional
    ensancha la ventana de carrera entre ticks concurrentes."""
    from agent.providers.base import ProveedorWhatsApp

    class FakeProveedor(ProveedorWhatsApp):
        def __init__(self):
            self.enviados: list[tuple[str, str]] = []
            self.devolver = True

        async def parsear_webhook(self, request):
            return []

        async def _enviar_mensaje_impl(self, telefono, mensaje):
            if demora_s:
                await asyncio.sleep(demora_s)
            self.enviados.append((telefono, mensaje))
            return self.devolver

    return FakeProveedor()


async def _seed_recordatorio(memoria, *, recurrencia: str | None = None,
                             ultimo_envio: datetime | None = None) -> int:
    async with memoria.async_session() as session:
        r = memoria.Recordatorio(
            telefono=TEL,
            mensaje="pagar la renta",
            fecha_hora=datetime.utcnow() - timedelta(minutes=2),
            recurrencia=recurrencia,
            ultimo_envio=ultimo_envio,
        )
        session.add(r)
        await session.commit()
        return r.id


async def _seed_seguimiento(memoria, crm_mod) -> int:
    from agent.business.models import Seguimiento
    async with memoria.async_session() as session:
        s = Seguimiento(
            telefono=TEL,
            cliente_nombre="Juan",
            descripcion="cotización pendiente",
            fecha_programada=datetime.utcnow() - timedelta(minutes=5),
        )
        session.add(s)
        await session.commit()
        return s.id


# ── 1. Recordatorios: ticks concurrentes (REGRESIÓN núcleo de 2.3) ───────


class TestRecordatoriosConcurrentes:
    async def test_dos_ticks_concurrentes_envian_una_sola_vez(self, entorno):
        """REGRESIÓN: contra el código viejo ambos ticks pasan el SELECT
        antes de que alguno marque → 2 envíos del mismo recordatorio."""
        memoria, sch, _ = entorno
        await _seed_recordatorio(memoria)

        fake = _proveedor_fake(demora_s=0.05)
        await asyncio.gather(
            sch._verificar_y_enviar_recordatorios_impl(fake),
            sch._verificar_y_enviar_recordatorios_impl(fake),
        )

        assert len(fake.enviados) == 1

    async def test_ocho_claims_concurrentes_un_ganador(self, entorno):
        memoria, _, _ = entorno
        rid = await _seed_recordatorio(memoria)

        resultados = await asyncio.gather(
            *[memoria.claim_recordatorio_para_envio(rid) for _ in range(8)]
        )

        assert sum(resultados) == 1

    async def test_flujo_normal_sigue_enviando(self, entorno):
        """Control anti-sobre-bloqueo: un solo tick envía y marca normal."""
        memoria, sch, _ = entorno
        rid = await _seed_recordatorio(memoria)

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert len(fake.enviados) == 1
        # Único → marcado enviado; no vuelve a salir en el siguiente tick.
        await sch._verificar_y_enviar_recordatorios_impl(fake)
        assert len(fake.enviados) == 1


# ── 2. Recordatorios: ciclo de vida del claim ────────────────────────────


class TestClaimRecordatorio:
    async def test_claim_expira_tras_ventana(self, entorno):
        """Un proceso que muere tras reclamar no pierde la ocurrencia para
        siempre: pasada la ventana, otro proceso puede reclamar."""
        memoria, _, _ = entorno
        rid = await _seed_recordatorio(
            memoria,
            ultimo_envio=datetime.utcnow() - timedelta(
                minutes=memoria.VENTANA_CLAIM_RECORDATORIO_MIN + 1
            ),
        )

        assert await memoria.claim_recordatorio_para_envio(rid) is True

    async def test_claim_reciente_bloquea(self, entorno):
        memoria, _, _ = entorno
        rid = await _seed_recordatorio(memoria, ultimo_envio=datetime.utcnow())

        assert await memoria.claim_recordatorio_para_envio(rid) is False

    async def test_envio_fallido_libera_claim_y_registra_fallo(self, entorno):
        """Si el proveedor falla, el claim se libera (reintento al próximo
        tick, sin esperar la ventana) y el contador de fallos avanza."""
        memoria, sch, _ = entorno
        rid = await _seed_recordatorio(memoria)

        fake = _proveedor_fake()
        fake.devolver = False
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        async with memoria.async_session() as session:
            from sqlalchemy import select
            r = (await session.execute(
                select(memoria.Recordatorio).where(memoria.Recordatorio.id == rid)
            )).scalar_one()
            assert r.intentos_fallidos == 1
            assert r.ultimo_envio is None  # claim liberado

        # Reintento inmediato posible (proveedor recuperado). El tick de
        # recuperación envía el recordatorio + el aviso de canal recuperado.
        fake.devolver = True
        await sch._verificar_y_enviar_recordatorios_impl(fake)
        recordatorios = [m for _, m in fake.enviados if "pagar la renta" in m]
        assert len(recordatorios) == 2  # el intento fallido también pasó por _impl

    async def test_recurrente_avanza_y_no_reenvia_en_el_mismo_tick(self, entorno):
        memoria, sch, _ = entorno
        rid = await _seed_recordatorio(memoria, recurrencia='{"tipo": "diario"}')

        fake = _proveedor_fake()
        await sch._verificar_y_enviar_recordatorios_impl(fake)
        await sch._verificar_y_enviar_recordatorios_impl(fake)

        assert len(fake.enviados) == 1
        async with memoria.async_session() as session:
            from sqlalchemy import select
            r = (await session.execute(
                select(memoria.Recordatorio).where(memoria.Recordatorio.id == rid)
            )).scalar_one()
            assert r.fecha_hora > datetime.utcnow()  # reagendado al futuro


# ── 3. Google Calendar: claim por clave ──────────────────────────────────


class TestClaimGCal:
    async def test_claim_unico_ganador(self, entorno):
        memoria, _, _ = entorno

        resultados = await asyncio.gather(
            *[memoria.claim_gcal_enviado("gcal_reminder_X_ev1") for _ in range(8)]
        )

        assert sum(resultados) == 1

    async def test_liberar_permite_reintento(self, entorno):
        memoria, _, _ = entorno

        assert await memoria.claim_gcal_enviado("gcal_reminder_X_ev2") is True
        assert await memoria.claim_gcal_enviado("gcal_reminder_X_ev2") is False
        await memoria.liberar_claim_gcal("gcal_reminder_X_ev2")
        assert await memoria.claim_gcal_enviado("gcal_reminder_X_ev2") is True


# ── 4. Seguimientos CRM: ticks concurrentes ──────────────────────────────


class TestSeguimientosConcurrentes:
    async def test_dos_ticks_concurrentes_envian_una_sola_vez(self, entorno):
        """REGRESIÓN: el job de seguimientos completaba DESPUÉS de enviar —
        dos procesos concurrentes enviaban el mismo seguimiento."""
        memoria, sch, crm = entorno
        await _seed_seguimiento(memoria, crm)

        fake = _proveedor_fake(demora_s=0.05)
        await asyncio.gather(
            sch._verificar_seguimientos_vencidos(fake),
            sch._verificar_seguimientos_vencidos(fake),
        )

        assert len(fake.enviados) == 1

    async def test_envio_fallido_revierte_y_reintenta(self, entorno):
        memoria, sch, crm = entorno
        sid = await _seed_seguimiento(memoria, crm)

        fake = _proveedor_fake()
        fake.devolver = False
        await sch._verificar_seguimientos_vencidos(fake)

        from agent.business.models import Seguimiento
        from sqlalchemy import select
        async with memoria.async_session() as session:
            s = (await session.execute(
                select(Seguimiento).where(Seguimiento.id == sid)
            )).scalar_one()
            assert s.completado is False  # revertido → reintentable

        fake.devolver = True
        await sch._verificar_seguimientos_vencidos(fake)
        async with memoria.async_session() as session:
            s = (await session.execute(
                select(Seguimiento).where(Seguimiento.id == sid)
            )).scalar_one()
            assert s.completado is True

    async def test_completado_no_se_reenvia(self, entorno):
        """Control: seguimiento ya completado no dispara envío."""
        memoria, sch, crm = entorno
        sid = await _seed_seguimiento(memoria, crm)
        await crm.completar_seguimiento(TEL, sid)

        fake = _proveedor_fake()
        await sch._verificar_seguimientos_vencidos(fake)

        assert fake.enviados == []
