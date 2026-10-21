"""Tests de F12 — primer resultado en 5 minutos (backend).

Cubre con SQLite aislado + mocks: usuario nuevo obtiene un resultado (borrador);
dobles webhooks/recargas no duplican el seed (idempotente); el primer resultado
se registra una sola vez (retoma sin re-medir ni duplicar); TTFV se calcula;
seed desactivado no deja saldo negativo. El borrador no llama a proveedores.

"5 minutos" es meta a medir con usuarios reales — no se declara validada aquí.
"""

import importlib
import sys

import pytest

import agent.memory
import agent.billing


def _recargar():
    for mod in (
        "agent.primer_valor.logica",
        "agent.primer_valor.models",
    ):
        sys.modules.pop(mod, None)
    import agent.primer_valor.models  # noqa: F401
    import agent.primer_valor.logica as logica
    return logica


@pytest.fixture
async def pv(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'fv.db'}")
    monkeypatch.setenv("DONA_FIRST_VALUE_ONBOARDING_ENABLED", "true")
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)
    logica = _recargar()
    await agent.memory.inicializar_db()
    return logica


class TestSeed:
    async def test_seed_idempotente(self, pv, monkeypatch):
        monkeypatch.setenv("DONA_FIRST_VALUE_WELCOME_CREDITS", "25")
        s1 = await pv.sembrar_creditos_bienvenida("5551")
        # Doble webhook / recarga → NO duplica
        s2 = await pv.sembrar_creditos_bienvenida("5551")
        assert s1 == 25
        assert s2 == 25
        assert await agent.billing.obtener_saldo("5551") == 25

    async def test_seed_desactivado_no_acredita(self, pv, monkeypatch):
        monkeypatch.setenv("DONA_FIRST_VALUE_WELCOME_CREDITS", "0")
        s = await pv.sembrar_creditos_bienvenida("5551")
        assert s is None
        assert await agent.billing.obtener_saldo("5551") == 0  # sin negativo

    async def test_welcome_credits_nunca_negativo(self, pv, monkeypatch):
        monkeypatch.setenv("DONA_FIRST_VALUE_WELCOME_CREDITS", "-5")
        assert pv.creditos_bienvenida() == 0


class TestPrimerResultado:
    async def test_usuario_nuevo_obtiene_borrador(self, pv):
        # Borrador determinístico, sin proveedor facturable.
        txt = pv.generar_borrador_seguimiento(nombre="Celestino", contexto="la cotización")
        assert "Celestino" in txt
        assert "la cotización" in txt

    async def test_registrar_primer_resultado_una_vez(self, pv):
        primero = await pv.registrar_primer_resultado("5551", "job-1", "borrador_seguimiento")
        segundo = await pv.registrar_primer_resultado("5551", "job-2", "imagen")
        assert primero is True
        assert segundo is False  # ya había primer resultado → no re-mide ni duplica

    async def test_iniciar_idempotente(self, pv):
        await pv.iniciar("5551")
        f1 = await pv._fila("5551")
        await pv.iniciar("5551")
        f2 = await pv._fila("5551")
        assert f1.started_at == f2.started_at  # no se pisa

    async def test_ttfv_se_calcula(self, pv):
        await pv.iniciar("5551")
        await pv.registrar_primer_resultado("5551", "job-1", "borrador_seguimiento")
        ttfv = await pv.ttfv_segundos("5551")
        assert ttfv is not None and ttfv >= 0

    async def test_ttfv_none_sin_resultado(self, pv):
        await pv.iniciar("5551")
        assert await pv.ttfv_segundos("5551") is None

    async def test_evento_solo_etapas_validas(self, pv):
        await pv.registrar_evento("5551", "preview")
        await pv.registrar_evento("5551", "etapa_inventada")  # ignorada
        from sqlalchemy import func, select
        from agent.primer_valor.models import EventoOnboarding
        from agent.memory import async_session
        async with async_session() as s:
            total = (await s.execute(
                select(func.count()).select_from(EventoOnboarding)
            )).scalar_one()
        assert total == 1


def test_flag_apagado_por_defecto(monkeypatch):
    monkeypatch.delenv("DONA_FIRST_VALUE_ONBOARDING_ENABLED", raising=False)
    from agent.primer_valor.logica import primer_valor_habilitado
    assert primer_valor_habilitado() is False
