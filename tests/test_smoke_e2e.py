# tests/test_smoke_e2e.py — Smoke test end-to-end del webhook

"""
Verifica la conexión entre:
  webhook → providers.parsear_webhook → routing → comandos_info → proveedor.enviar_mensaje

No corre el stack completo (DB real, rate limiter real, onboarding, etc.) porque
procesar_webhook tiene muchas dependencias; el test "cose" la mínima superficie
necesaria para probar que el glue del comando 'dona ayuda' funciona extremo a extremo.

Estos tests atrapan regresiones en el wiring entre módulos — no validan la
correctitud individual de cada módulo (eso lo cubren los tests unitarios).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Si APScheduler (dependencia runtime) no está instalado, todos estos tests
# se saltan con un skip claro — no es un fallo de wiring sino del entorno.
apscheduler = pytest.importorskip(
    "apscheduler",
    reason="apscheduler no instalado en el entorno de test — smoke e2e requiere main.py importable",
)


# ── Test 1: El módulo main importa sin errores ─────────────────────────────

def test_main_imports_cleanly():
    """Regression test: cambios de imports en main.py no rompen el startup."""
    import importlib
    import agent.main as m
    importlib.reload(m)  # forzar re-ejecución
    assert hasattr(m, "app")
    assert hasattr(m, "procesar_webhook")


def test_webhook_routes_registradas():
    """Las rutas críticas deben existir en la FastAPI app."""
    from agent.main import app
    paths = {r.path for r in app.routes}
    assert "/webhook" in paths
    assert "/webhook/messages" in paths


# ── Test 2: Smoke — procesar "dona ayuda" end-to-end ───────────────────────

@pytest.mark.asyncio
async def test_dona_ayuda_ruta_a_comandos_info():
    """
    Simula un mensaje 'dona ayuda' y verifica que:
      1. Se rutea al handler de comandos_info (no a brain/LLM)
      2. Se invoca proveedor.enviar_mensaje con el texto de ayuda
    """
    from agent.providers.base import MensajeEntrante

    fake_msg = MensajeEntrante(
        telefono="5551234567",
        texto="dona ayuda",
        mensaje_id="wamid.smoke.1",
        es_propio=False,
    )

    fake_proveedor = MagicMock()
    fake_proveedor.parsear_webhook = AsyncMock(return_value=[fake_msg])
    fake_proveedor.enviar_mensaje = AsyncMock(return_value=True)

    fake_request = MagicMock()

    # Patches para cortocircuitar dependencias que no nos interesan en este smoke
    with patch("agent.main.proveedor", fake_proveedor), \
         patch("agent.main._mensaje_ya_procesado", new=AsyncMock(return_value=False)), \
         patch("agent.main._dentro_de_limite", return_value=True), \
         patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
         patch("agent.main.es_onboarding_activo", new=AsyncMock(return_value=False)):
        from agent.main import procesar_webhook
        res = await procesar_webhook(fake_request)

    # El handler nunca levanta; retorna status
    assert isinstance(res, dict)

    # Se invocó enviar_mensaje con el texto generado por comandos_info
    fake_proveedor.enviar_mensaje.assert_awaited()
    args, _ = fake_proveedor.enviar_mensaje.call_args
    telefono_enviado, texto_enviado = args
    assert telefono_enviado == "5551234567"
    # El texto debe traer el encabezado del comando de ayuda
    assert "Qué puedo hacer" in texto_enviado or "Finanzas" in texto_enviado


@pytest.mark.asyncio
async def test_dona_estado_produce_respuesta():
    """
    'dona estado' puede ser interceptado por enhanced.diagnostics (prioridad mayor)
    o por comandos_info — ambos son respuestas válidas. El smoke sólo verifica
    que NO se crashea y que SE envía algo al usuario.
    """
    from agent.providers.base import MensajeEntrante

    fake_msg = MensajeEntrante(
        telefono="5551234567",
        texto="dona estado",
        mensaje_id="wamid.smoke.2",
        es_propio=False,
    )

    fake_proveedor = MagicMock()
    fake_proveedor.parsear_webhook = AsyncMock(return_value=[fake_msg])
    fake_proveedor.enviar_mensaje = AsyncMock(return_value=True)

    with patch("agent.main.proveedor", fake_proveedor), \
         patch("agent.main._mensaje_ya_procesado", new=AsyncMock(return_value=False)), \
         patch("agent.main._dentro_de_limite", return_value=True), \
         patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
         patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)), \
         patch("agent.main.es_onboarding_activo", new=AsyncMock(return_value=False)):
        from agent.main import procesar_webhook
        await procesar_webhook(MagicMock())

    fake_proveedor.enviar_mensaje.assert_awaited()
    args, _ = fake_proveedor.enviar_mensaje.call_args
    telefono_enviado, texto_enviado = args
    assert telefono_enviado == "5551234567"
    assert texto_enviado  # algo se envió


@pytest.mark.asyncio
async def test_mensaje_propio_no_se_procesa():
    """Mensajes 'echo' del propio bot deben ignorarse sin efectos."""
    from agent.providers.base import MensajeEntrante

    fake_msg = MensajeEntrante(
        telefono="5551234567",
        texto="dona ayuda",
        mensaje_id="wamid.smoke.3",
        es_propio=True,   # ← eco del bot
    )

    fake_proveedor = MagicMock()
    fake_proveedor.parsear_webhook = AsyncMock(return_value=[fake_msg])
    fake_proveedor.enviar_mensaje = AsyncMock(return_value=True)

    with patch("agent.main.proveedor", fake_proveedor):
        from agent.main import procesar_webhook
        await procesar_webhook(MagicMock())

    fake_proveedor.enviar_mensaje.assert_not_awaited()


@pytest.mark.asyncio
async def test_parser_rompe_no_crashea():
    """Si el proveedor lanza al parsear, el handler devuelve error sin romper."""
    fake_proveedor = MagicMock()
    fake_proveedor.parsear_webhook = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("agent.main.proveedor", fake_proveedor):
        from agent.main import procesar_webhook
        res = await procesar_webhook(MagicMock())

    assert res == {"status": "error", "detail": "parse_error"}
