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

from unittest.mock import AsyncMock, MagicMock, patch

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


# ── procesar_webhook: parseo de `!exec <accion> <token>` end-to-end ──────────

def _webhook_mensaje(texto: str):
    """Arma un proveedor fake que entrega un único MensajeEntrante del owner."""
    from agent.providers.base import MensajeEntrante

    fake_msg = MensajeEntrante(
        telefono=OWNER,
        texto=texto,
        mensaje_id=f"wamid.exec.{abs(hash(texto)) % 10_000}",
        es_propio=False,
    )
    fake_proveedor = MagicMock()
    fake_proveedor.parsear_webhook = AsyncMock(return_value=[fake_msg])
    fake_proveedor.enviar_mensaje = AsyncMock(return_value=True)
    return fake_proveedor


def _patches_webhook(fake_proveedor):
    """Cortocircuita dependencias del loop de webhook ajenas a este test."""
    return [
        patch("agent.main.proveedor", fake_proveedor),
        patch("agent.main._mensaje_ya_procesado", new=AsyncMock(return_value=False)),
        patch("agent.main._dentro_de_limite", return_value=True),
        patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)),
        patch("agent.main.es_onboarding_activo", new=AsyncMock(return_value=False)),
        patch("enhanced.safe_module.OWNER_PHONE", OWNER),
    ]


@pytest.mark.asyncio
class TestExecWebhookEndToEnd:
    async def test_exec_sin_accion_muestra_uso(self, monkeypatch):
        """`!exec` a secas (owner) → mensaje de uso con el formato `<token>`."""
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "secreto-real")
        fake = _webhook_mensaje("!exec")

        import contextlib
        with contextlib.ExitStack() as stack:
            for p in _patches_webhook(fake):
                stack.enter_context(p)
            from agent.main import procesar_webhook
            await procesar_webhook(MagicMock())

        fake.enviar_mensaje.assert_awaited()
        _, texto = fake.enviar_mensaje.call_args[0]
        assert "Uso" in texto and "token" in texto.lower()
        assert sm.tiene_confirmacion_pendiente(OWNER) is False

    async def test_exec_con_accion_y_token_despacha_confirmacion(self, monkeypatch):
        """`!exec <accion> <token>` correcto (owner) → inicia confirmación."""
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "secreto-real")
        fake = _webhook_mensaje("!exec limpiar_rate_limit secreto-real")

        import contextlib
        with contextlib.ExitStack() as stack:
            for p in _patches_webhook(fake):
                stack.enter_context(p)
            from agent.main import procesar_webhook
            await procesar_webhook(MagicMock())

        fake.enviar_mensaje.assert_awaited()
        _, texto = fake.enviar_mensaje.call_args[0]
        assert "limpiar_rate_limit" in texto
        assert "CONFIRMAR" in texto
        assert sm.tiene_confirmacion_pendiente(OWNER) is True

    async def test_exec_token_incorrecto_por_webhook_no_confirma(self, monkeypatch):
        """`!exec <accion> <token-malo>` (owner) → no autoriza, sin confirmación."""
        monkeypatch.setattr(sm, "ADMIN_EXEC_SECRET", "secreto-real")
        fake = _webhook_mensaje("!exec limpiar_rate_limit token-malo")

        import contextlib
        with contextlib.ExitStack() as stack:
            for p in _patches_webhook(fake):
                stack.enter_context(p)
            from agent.main import procesar_webhook
            await procesar_webhook(MagicMock())

        fake.enviar_mensaje.assert_awaited()
        _, texto = fake.enviar_mensaje.call_args[0]
        assert "No autorizado" in texto
        assert sm.tiene_confirmacion_pendiente(OWNER) is False
