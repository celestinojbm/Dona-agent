# tests/test_exec_segundo_factor.py — TEMA 5 · 5.3: 2º factor para !exec

"""
Batería adversarial para el segundo factor del comando `!exec`.

Contexto de amenaza (Roadmap TEMA 5 · 5.3): el `!exec` corría gateado solo
por `_es_owner(telefono)`. El caller-ID de WhatsApp (`from`) es **spoofeable**:
quien logre forjar el número del owner podía disparar acciones de sistema
privilegiadas (limpiar rate limit / dedup, reciclar pool, reiniciar scheduler)
— primitivas de denegación de servicio y evasión de controles.

El fix agrega un **segundo factor** (secreto compartido `ADMIN_EXEC_SECRET`)
comparado con `hmac.compare_digest`, fail-closed si no está configurado. El
número del owner ya no basta por sí solo.
"""

import pytest

import enhanced.execution as ex
import enhanced.safe_module as sm


@pytest.fixture(autouse=True)
def _limpiar_confirmaciones():
    """Cada test arranca sin confirmaciones pendientes residuales."""
    sm._confirmaciones.clear()
    yield
    sm._confirmaciones.clear()


# ── _segundo_factor_valido ───────────────────────────────────────────────────

class TestSegundoFactorValido:
    def test_fail_closed_sin_secreto_configurado(self, monkeypatch):
        """Sin ADMIN_EXEC_SECRET, el segundo factor SIEMPRE es inválido."""
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "")
        assert sm._segundo_factor_valido("lo-que-sea") is False
        # Incluso un token vacío contra secreto vacío debe fallar (no compare_digest("","")==True).
        assert sm._segundo_factor_valido("") is False

    def test_token_correcto(self, monkeypatch):
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "s3cr3t-largo-y-random")
        assert sm._segundo_factor_valido("s3cr3t-largo-y-random") is True

    def test_token_incorrecto(self, monkeypatch):
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "s3cr3t-largo-y-random")
        assert sm._segundo_factor_valido("otro-token") is False

    def test_token_vacio_con_secreto_configurado(self, monkeypatch):
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "s3cr3t-largo-y-random")
        assert sm._segundo_factor_valido("") is False

    def test_prefijo_del_secreto_no_pasa(self, monkeypatch):
        """Un token que es prefijo del secreto no debe validar (longitud distinta)."""
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "s3cr3t-largo-y-random")
        assert sm._segundo_factor_valido("s3cr3t") is False


# ── iniciar_ejecucion: enforcement server-side ───────────────────────────────

OWNER = "14076936023"


@pytest.mark.asyncio
class TestIniciarEjecucionConSegundoFactor:
    async def test_owner_spoofeado_sin_token_no_ejecuta(self, monkeypatch):
        """
        Escenario adversarial: el atacante forja el número del owner (caller-ID
        spoofeado) → `_es_owner` daría True, pero NO tiene el segundo factor.
        La acción NO debe iniciar confirmación.
        """
        monkeypatch.setattr(sm, "OWNER_PHONE", OWNER)
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "secreto-real")

        resp = await ex.ejecucion.iniciar_ejecucion(OWNER, "limpiar_rate_limit", "")

        assert "limpiar_rate_limit" not in resp or "pendiente" not in resp.lower()
        assert sm.tiene_confirmacion_pendiente(OWNER) is False

    async def test_owner_spoofeado_token_incorrecto_no_ejecuta(self, monkeypatch):
        monkeypatch.setattr(sm, "OWNER_PHONE", OWNER)
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "secreto-real")

        resp = await ex.ejecucion.iniciar_ejecucion(OWNER, "limpiar_rate_limit", "token-malo")

        assert sm.tiene_confirmacion_pendiente(OWNER) is False
        assert "pendiente" not in resp.lower()

    async def test_fail_closed_sin_secreto_configurado(self, monkeypatch):
        """Aún siendo el owner legítimo, si no hay secreto configurado, !exec no corre."""
        monkeypatch.setattr(sm, "OWNER_PHONE", OWNER)
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "")

        resp = await ex.ejecucion.iniciar_ejecucion(OWNER, "limpiar_rate_limit", "cualquier-cosa")

        assert sm.tiene_confirmacion_pendiente(OWNER) is False
        assert "pendiente" not in resp.lower()

    async def test_owner_con_token_correcto_inicia_confirmacion(self, monkeypatch):
        """El owner legítimo CON el segundo factor sí inicia el flujo de confirmación."""
        monkeypatch.setattr(sm, "OWNER_PHONE", OWNER)
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "secreto-real")

        resp = await ex.ejecucion.iniciar_ejecucion(OWNER, "limpiar_rate_limit", "secreto-real")

        assert sm.tiene_confirmacion_pendiente(OWNER) is True
        assert "limpiar_rate_limit" in resp
        assert "CONFIRMAR" in resp

    async def test_accion_inexistente_no_filtra_por_segundo_factor(self, monkeypatch):
        """
        El chequeo del segundo factor va ANTES de resolver la acción: un token
        inválido no debe permitir sondear qué acciones existen.
        """
        monkeypatch.setattr(sm, "OWNER_PHONE", OWNER)
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "secreto-real")

        resp = await ex.ejecucion.iniciar_ejecucion(OWNER, "accion_que_no_existe", "token-malo")

        assert sm.tiene_confirmacion_pendiente(OWNER) is False
        # No debe revelar la lista de acciones válidas ante un 2º factor inválido.
        assert "limpiar_rate_limit" not in resp
