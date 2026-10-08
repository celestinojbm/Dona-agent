# tests/test_efectos_arranque.py — J4 · el backend arranca sin efectos externos
#
# Con los interruptores de agent/efectos.py apagados (su default), el
# backend no envía mensajes, no procesa cobros, no llama a modelos, no
# programa trabajos ni consume la cola. Se prueba en los choke points
# (gate de envíos, guard de presupuesto LLM, scheduler, worker, rutas) y
# en un arranque completo de la app con la red bloqueada.

import importlib

import httpx
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.testclient import TestClient

from agent.efectos import INTERRUPTORES

_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:  # pragma: no cover - entorno sin dependencias del web
    _main_disponible = False

requiere_main = pytest.mark.skipif(not _main_disponible, reason="agent.main no importable")


@pytest.fixture
def sin_efectos(monkeypatch):
    """Todos los interruptores en su default (apagados)."""
    for var in INTERRUPTORES.values():
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def red_bloqueada(monkeypatch):
    """Cualquier petición HTTP saliente (httpx: SDK de Anthropic/OpenAI,
    proveedores de WhatsApp, Stripe vía httpx) hace fallar el test."""
    llamadas = []

    async def _send_async(self, request, *a, **kw):
        llamadas.append(str(request.url))
        raise AssertionError(f"petición saliente inesperada: {request.url}")

    def _send_sync(self, request, *a, **kw):
        # TestClient usa httpx.Client contra la app ASGI (host "testserver"):
        # eso no es red real y se deja pasar.
        if request.url.host == "testserver":
            return _send_sync_original(self, request, *a, **kw)
        llamadas.append(str(request.url))
        raise AssertionError(f"petición saliente inesperada: {request.url}")

    _send_sync_original = httpx.Client.send
    monkeypatch.setattr(httpx.AsyncClient, "send", _send_async)
    monkeypatch.setattr(httpx.Client, "send", _send_sync)
    return llamadas


# ── Interruptores ───────────────────────────────────────────────────────────


class TestInterruptores:
    def test_todos_apagados_por_defecto(self, sin_efectos):
        from agent.efectos import efecto_habilitado, resumen_efectos

        assert resumen_efectos() == {nombre: False for nombre in INTERRUPTORES}
        assert not efecto_habilitado("whatsapp")

    @pytest.mark.parametrize("valor", ["true", "TRUE", " 1 ", "on", "yes"])
    def test_solo_un_valor_verdadero_explicito_enciende(self, sin_efectos, monkeypatch, valor):
        from agent.efectos import efecto_habilitado

        monkeypatch.setenv("DONA_LLM_ENABLED", valor)
        assert efecto_habilitado("llm")

    @pytest.mark.parametrize("valor", ["", "false", "0", "off", "ture", "enabled"])
    def test_cualquier_otro_valor_queda_apagado(self, sin_efectos, monkeypatch, valor):
        from agent.efectos import efecto_habilitado

        monkeypatch.setenv("DONA_LLM_ENABLED", valor)
        assert not efecto_habilitado("llm")

    def test_scheduler_sin_whatsapp_ni_llm_es_incoherente(self, sin_efectos, monkeypatch):
        from agent.efectos import ConfiguracionEfectosError, problemas_de_efectos, verificar_efectos

        monkeypatch.setenv("DONA_SCHEDULER_ENABLED", "true")
        problemas = problemas_de_efectos()
        assert len(problemas) == 1
        assert "DONA_WHATSAPP_ENABLED=true" in problemas[0]
        assert "DONA_LLM_ENABLED=true" in problemas[0]
        with pytest.raises(ConfiguracionEfectosError):
            verificar_efectos()

    def test_todo_apagado_es_coherente(self, sin_efectos):
        from agent.efectos import problemas_de_efectos, verificar_efectos

        assert problemas_de_efectos() == []
        verificar_efectos()  # no lanza


# ── Choke points ────────────────────────────────────────────────────────────


class TestChokePoints:
    async def test_whatsapp_apagado_bloquea_envios_sin_consultar_db(self, sin_efectos, monkeypatch):
        import agent.memory
        from agent.envio_gate import contexto_envio_directo, puede_enviar

        async def _no_debe_llamarse(*a, **kw):
            raise AssertionError("con WhatsApp apagado no se consulta la DB")

        monkeypatch.setattr(agent.memory, "obtener_proactividad", _no_debe_llamarse)
        assert await puede_enviar("5215550000000") is False
        # Ni siquiera una respuesta DIRECTA al usuario sale.
        with contexto_envio_directo("5215550000000"):
            assert await puede_enviar("5215550000000") is False

    async def test_whatsapp_apagado_el_proveedor_no_llama_a_la_api(self, sin_efectos):
        from agent.providers.base import ProveedorWhatsApp

        class _Proveedor(ProveedorWhatsApp):
            async def _enviar_mensaje_impl(self, telefono, mensaje):
                raise AssertionError("no debe llegar a la API del proveedor")

            async def parsear_webhook(self, request):  # pragma: no cover
                return []

        assert await _Proveedor().enviar_mensaje("5215550000000", "hola") is False

    def test_llm_apagado_activa_el_kill_switch_global(self, sin_efectos, monkeypatch):
        from agent.presupuesto_runtime import kill_switch_global_activo

        monkeypatch.delenv("DONA_LLM_COST_KILL_SWITCH", raising=False)
        assert kill_switch_global_activo() is True
        monkeypatch.setenv("DONA_LLM_ENABLED", "true")
        assert kill_switch_global_activo() is False
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        assert kill_switch_global_activo() is True

    async def test_llm_apagado_completar_texto_no_llama_al_proveedor(
        self, sin_efectos, red_bloqueada
    ):
        from agent.llm import completar_texto

        assert await completar_texto("hola") is None
        assert red_bloqueada == []


# ── Scheduler ───────────────────────────────────────────────────────────────


class TestScheduler:
    async def test_apagado_no_registra_ni_arranca(self, sin_efectos, monkeypatch):
        import agent.scheduler as sched_mod

        nuevo = AsyncIOScheduler(timezone="UTC")
        monkeypatch.setattr(sched_mod, "scheduler", nuevo)
        sched_mod.iniciar_scheduler(proveedor=object())
        assert nuevo.get_jobs() == []
        assert not nuevo.running

    async def test_encendido_sin_self_ping_e_idempotente(self, monkeypatch):
        import agent.scheduler as sched_mod

        for var in ("DONA_SCHEDULER_ENABLED", "DONA_WHATSAPP_ENABLED", "DONA_LLM_ENABLED"):
            monkeypatch.setenv(var, "true")
        nuevo = AsyncIOScheduler(timezone="UTC")
        monkeypatch.setattr(sched_mod, "scheduler", nuevo)
        try:
            sched_mod.iniciar_scheduler(proveedor=object())
            ids = {j.id for j in nuevo.get_jobs()}
            assert "verificar_recordatorios" in ids
            assert "self_ping_keep_alive" not in ids
            assert not hasattr(sched_mod, "_self_ping")
            total = len(ids)
            # Segunda llamada en el mismo proceso: no duplica jobs.
            sched_mod.iniciar_scheduler(proveedor=object())
            assert len(nuevo.get_jobs()) == total
        finally:
            nuevo.shutdown(wait=False)


# ── Worker ──────────────────────────────────────────────────────────────────


class TestWorker:
    async def test_apagado_no_ejecuta_ni_toca_el_job(self, sin_efectos, monkeypatch):
        import agent.jobs.worker as worker

        async def _no(*a, **kw):
            raise AssertionError("con el worker apagado no se toca el job")

        monkeypatch.setattr(worker, "marcar_running", _no)
        monkeypatch.setattr(worker, "_dispatch", _no)
        await worker.ejecutar_job_inproc(1, "echo", "5215550000000", {})
        await worker.ejecutar_job({}, 1, "echo", "5215550000000", {})

    async def test_worker_arq_se_niega_a_arrancar(self, sin_efectos):
        from agent.jobs.worker import WorkerSettings

        with pytest.raises(RuntimeError, match="DONA_WORKER_ENABLED"):
            await WorkerSettings.on_startup({})

    def test_worker_arq_no_tiene_trabajos_recurrentes(self):
        from agent.jobs.worker import WorkerSettings

        # Un solo responsable por trabajo recurrente: el scheduler del web.
        assert not getattr(WorkerSettings, "cron_jobs", None)


# ── Readiness en entorno estricto ───────────────────────────────────────────


_BASE_ESTRICTA = {
    "ENVIRONMENT": "production",
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
    "ENCRYPTION_KEY": "x",
    "INTERNAL_BRIDGE_SECRET": "x",
    "ADMIN_TOKEN": "x",
}


class TestReadiness:
    @pytest.fixture
    def estricto(self, sin_efectos, monkeypatch):
        for var in (
            "STRIPE_WEBHOOK_SECRET", "DASHBOARD_PASSWORD_SECRET", "INBOUND_WEBHOOK_SECRET",
            "ANTHROPIC_API_KEY", "WHATSAPP_PROVIDER", "WHAPI_WEBHOOK_TOKEN", "META_APP_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)
        for k, v in _BASE_ESTRICTA.items():
            monkeypatch.setenv(k, v)

    def test_pausa_arranca_sin_secretos_de_cobro_envio_ni_modelos(self, estricto):
        from agent.readiness import evaluar_readiness, verificar_readiness

        assert evaluar_readiness() == []
        verificar_readiness()  # no lanza

    def test_base_sigue_siendo_obligatoria(self, estricto, monkeypatch):
        from agent.readiness import evaluar_readiness

        monkeypatch.delenv("ADMIN_TOKEN")
        assert any(p.startswith("ADMIN_TOKEN") for p in evaluar_readiness())

    @pytest.mark.parametrize(
        "efecto,var_secreto",
        [
            ("DONA_STRIPE_ENABLED", "STRIPE_WEBHOOK_SECRET"),
            ("DONA_STRIPE_ENABLED", "DASHBOARD_PASSWORD_SECRET"),
            ("DONA_INBOUND_ENABLED", "INBOUND_WEBHOOK_SECRET"),
            ("DONA_LLM_ENABLED", "ANTHROPIC_API_KEY"),
            ("DONA_WHATSAPP_ENABLED", "WHATSAPP_PROVIDER"),
        ],
    )
    def test_encender_un_efecto_exige_su_secreto(self, estricto, monkeypatch, efecto, var_secreto):
        from agent.readiness import evaluar_readiness

        monkeypatch.setenv(efecto, "true")
        assert any(p.startswith(var_secreto) for p in evaluar_readiness())

    def test_incoherencia_de_interruptores_es_problema_de_readiness(self, estricto, monkeypatch):
        from agent.readiness import evaluar_readiness

        monkeypatch.setenv("DONA_SCHEDULER_ENABLED", "true")
        assert any("DONA_SCHEDULER_ENABLED=true requiere" in p for p in evaluar_readiness())

    def test_billing_e_inbound_importan_en_estricto_sin_sus_secretos(self, estricto):
        import agent.billing
        import agent.inbound_tokens

        importlib.reload(agent.billing)  # no lanza con Stripe apagado
        importlib.reload(agent.inbound_tokens)  # no lanza con inbound apagado

    def test_billing_aborta_si_stripe_encendido_sin_secreto(self, estricto, monkeypatch):
        import agent.billing

        monkeypatch.setenv("DONA_STRIPE_ENABLED", "true")
        with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
            agent.billing._check_stripe_webhook_secret()

    def test_proveedores_se_construyen_en_estricto_con_whatsapp_apagado(self, estricto):
        from agent.providers.meta import ProveedorMeta
        from agent.providers.whapi import ProveedorWhapi

        ProveedorWhapi()
        ProveedorMeta()


# ── Rutas HTTP ──────────────────────────────────────────────────────────────


@requiere_main
class TestRutas:
    @pytest.fixture
    def cliente(self, sin_efectos, monkeypatch):
        import agent.main as main

        async def _no(*a, **kw):
            raise AssertionError("no debe procesarse con el efecto apagado")

        monkeypatch.setattr(main, "procesar_webhook", _no)
        import agent.billing

        monkeypatch.setattr(agent.billing, "procesar_evento_stripe", _no)
        return TestClient(main.app)

    @pytest.mark.parametrize(
        "metodo,ruta,efecto",
        [
            ("get", "/webhook", "whatsapp"),
            ("post", "/webhook", "whatsapp"),
            ("post", "/webhook/messages", "whatsapp"),
            ("post", "/webhook/inbound/token-cualquiera", "inbound"),
            ("post", "/webhook/stripe", "stripe"),
            ("post", "/internal/stripe-event", "stripe"),
            ("post", "/internal/chat", "llm"),
            ("post", "/privacy/export", "whatsapp"),
            ("post", "/privacy/delete", "whatsapp"),
        ],
    )
    def test_entrada_cortada_antes_de_procesar(self, cliente, red_bloqueada, metodo, ruta, efecto):
        res = getattr(cliente, metodo)(ruta, **({} if metodo == "get" else {"json": {}}))
        assert res.status_code == 503
        assert res.json() == {"error": "efecto_deshabilitado", "efecto": efecto}
        assert red_bloqueada == []

    def test_health_vida(self, cliente):
        res = cliente.get("/health/vida")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    def test_health_listo_con_db(self, cliente):
        res = cliente.get("/health/listo")
        assert res.status_code == 200
        cuerpo = res.json()
        assert cuerpo["status"] == "ok"
        assert cuerpo["db"] is True
        assert cuerpo["efectos"] == {nombre: False for nombre in INTERRUPTORES}

    def test_health_listo_con_db_caida_no_filtra_detalles(self, cliente, monkeypatch):
        import agent.memory

        class _SesionRota:
            async def __aenter__(self):
                raise ConnectionError("postgresql://usuario:clave@host-interno/db rechazó")

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(agent.memory, "async_session", lambda: _SesionRota())
        res = cliente.get("/health/listo")
        assert res.status_code == 503
        assert res.json()["db"] is False
        assert "host-interno" not in res.text and "clave" not in res.text


# ── Arranque completo ───────────────────────────────────────────────────────


@requiere_main
class TestArranque:
    def test_arranque_y_apagado_sin_efectos(self, sin_efectos, red_bloqueada, monkeypatch, tmp_path):
        """Lifespan completo (DB, reaper, scheduler) con todo apagado y la red
        bloqueada: arranca, no programa trabajos, no sale a internet y se
        apaga limpio."""
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'arranque.db'}")
        import agent.memory

        importlib.reload(agent.memory)
        import agent.main as main
        import agent.scheduler as sched_mod

        nuevo = AsyncIOScheduler(timezone="UTC")
        monkeypatch.setattr(sched_mod, "scheduler", nuevo)

        with TestClient(main.app) as cliente:
            assert cliente.get("/health/vida").status_code == 200
            assert cliente.get("/health/listo").json()["db"] is True
            assert nuevo.get_jobs() == []
            assert not nuevo.running
        assert red_bloqueada == []
