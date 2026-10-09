# tests/test_consent_terceros_bordes.py — Fase 0 · 2.5: ramas de borde
#
# Endurece la cobertura de agent/automation/consent_terceros.py fijando el
# comportamiento de las ramas de borde que test_consent_terceros.py no toca:
#
#   1. destino_hablo_con_dona / _destino_respondio_desde con un destino que
#      normaliza a vacío (solo símbolos / cadena vacía) → retornan False ANTES
#      de tocar la DB. Es fail-safe: un destino sin dígitos no puede haber
#      "hablado con Dona", así que jamás debe pasar por el best-effort ni
#      abrir una consulta contra la tabla de mensajes.
#   2. obtener_nombre_owner es best-effort: si obtener_onboarding lanza o no
#      hay onboarding, devuelve "" en vez de propagar el error (el copy de
#      identificación se compone igual, solo sin nombre).
#
# Todos fijan el COMPORTAMIENTO ACTUAL — no cambian lógica de producción.

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
async def entorno(tmp_path, monkeypatch):
    """DB SQLite temporal + módulos recargados, igual patrón que
    test_consent_terceros.py. Devuelve (memory, consent)."""
    db_path = tmp_path / "consent_bordes.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    import agent.memory
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.consent_terceros as _consent
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_consent)
    await agent.memory.inicializar_db()
    return agent.memory, _consent


# ── normalizar a vacío → False sin tocar la DB ───────────────────────────


class TestDestinoNormalizaVacio:
    """Un destino que no deja ningún dígito tras normalizar no puede haber
    conversado con Dona: las consultas de historial retornan False directo."""

    async def test_hablo_con_dona_cadena_vacia_es_false(self, entorno):
        _memory, consent = entorno
        assert await consent.destino_hablo_con_dona("") is False

    async def test_hablo_con_dona_solo_simbolos_es_false(self, entorno):
        _memory, consent = entorno
        # "+++ () -" normaliza a "" (ningún dígito) → False antes de la DB.
        assert await consent.destino_hablo_con_dona("+++ () -") is False

    async def test_hablo_con_dona_none_es_false(self, entorno):
        _memory, consent = entorno
        # normalizar_destino(None) → "" (str(None or "")). No debe reventar.
        assert await consent.destino_hablo_con_dona(None) is False

    async def test_respondio_desde_cadena_vacia_es_false(self, entorno):
        _memory, consent = entorno
        desde = datetime.now(timezone.utc) - timedelta(days=1)
        assert await consent._destino_respondio_desde("", desde) is False

    async def test_respondio_desde_solo_simbolos_es_false(self, entorno):
        _memory, consent = entorno
        desde = datetime.now(timezone.utc) - timedelta(days=1)
        assert await consent._destino_respondio_desde("()-", desde) is False


# ── obtener_nombre_owner best-effort ─────────────────────────────────────


class TestObtenerNombreOwnerBestEffort:
    """El nombre del owner es best-effort para el copy de identificación:
    ausente o error → "" (nunca propaga la excepción ni None)."""

    async def test_sin_onboarding_devuelve_vacio(self, entorno):
        _memory, consent = entorno
        # Owner que nunca hizo onboarding: no hay fila → "".
        assert await consent.obtener_nombre_owner("99999999999") == ""

    async def test_excepcion_en_onboarding_devuelve_vacio(self, entorno, monkeypatch):
        memory, consent = entorno

        async def _boom(*_a, **_k):
            raise RuntimeError("db caída")

        # obtener_nombre_owner hace `from agent.memory import obtener_onboarding`
        # dentro del try, así que parcheamos el atributo del módulo memory.
        monkeypatch.setattr(memory, "obtener_onboarding", _boom)
        assert await consent.obtener_nombre_owner("15550001111") == ""

    async def test_onboarding_none_devuelve_vacio(self, entorno, monkeypatch):
        memory, consent = entorno

        async def _sin_estado(*_a, **_k):
            return None

        # (estado or {}).get("nombre", "") debe tolerar None sin reventar.
        monkeypatch.setattr(memory, "obtener_onboarding", _sin_estado)
        assert await consent.obtener_nombre_owner("15550002222") == ""
