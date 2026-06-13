# tests/test_budget_wire_aux.py — Fase 0 · Entregable F · F-1: rutas LLM restantes

"""
REGRESIÓN (F0-BUD-01 del exit dossier): fuera de brain.py quedaban rutas
REALES al provider sin RuntimeBudgetGuard — agent/llm.py (vía de 8 tareas
ligeras: emotion, nlp, learning, memoria, location, onboarding, real_world,
mirofish-postproceso), los 4 generadores de proactivity.py y vision.py.
Con el kill-switch global activo, esas rutas seguían llamando al provider.

F-1 las gatea TODAS:
  - llm.py = vía AUXILIAR por contrato (cupo propio max_llm_aux_calls,
    costo compartido, timeout y kill-switch idénticos). Bloqueada → None
    (todos los callers degradan).
  - proactivity = trabajo PRINCIPAL background; cada usuario del batch corre
    bajo su PROPIO presupuesto (presupuesto_de_mensaje por unidad).
  - vision = trabajo PRINCIPAL foreground (alimenta la respuesta).
  - clientes muertos eliminados (emotion._claude, mirofish, onboarding).

Los tests de kill-switch FALLAN contra el código viejo (llamaba al provider
igual). Invariante de Hermes: ninguna llamada real al provider sin guard,
en ninguna dimensión.
"""

from __future__ import annotations

import pytest

import agent.llm as llm
import agent.proactivity as proactivity
import agent.vision as vision
import agent.presupuesto_runtime as pr


TEL = "15550005555"


@pytest.fixture(autouse=True)
def _budget_limpio(monkeypatch):
    pr._contadores_eventos.clear()
    pr._owners_suspendidos.clear()
    pr._costo_diario_owner.clear()
    for v in (
        "DONA_LLM_COST_KILL_SWITCH",
        "BUDGET_MAX_LLM_AUX_CALLS_MENSAJE",
        "BUDGET_MAX_LLM_CALLS_MENSAJE",
    ):
        monkeypatch.delenv(v, raising=False)
    yield
    pr._contadores_eventos.clear()
    pr._costo_diario_owner.clear()


# ── Fakes ────────────────────────────────────────────────────────────────


class _FakeDeepSeek:
    """Cliente estilo OpenAI con contador de llamadas reales."""

    def __init__(self, texto="respuesta deepseek"):
        self.llamadas = 0
        cliente = self

        class _Completions:
            async def create(self, **kwargs):
                cliente.llamadas += 1

                class _R:
                    class usage:
                        total_tokens = 50

                    choices = [type("C", (), {"message": type("M", (), {"content": texto})()})()]

                return _R()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class _FakeAnthropic:
    """Cliente estilo Anthropic con contador de llamadas reales."""

    def __init__(self, texto="respuesta haiku"):
        self.llamadas = 0
        cliente = self

        class _Messages:
            async def create(self, **kwargs):
                cliente.llamadas += 1

                class _R:
                    class usage:
                        input_tokens = 10
                        output_tokens = 10

                    content = [type("B", (), {"text": texto})()]
                    stop_reason = "end_turn"

                return _R()

        self.messages = _Messages()


# ── 1. llm.py gateado como vía auxiliar (REGRESIÓN núcleo) ───────────────


class TestLlmAuxGateado:
    async def test_kill_switch_bloquea_completar_texto(self, monkeypatch):
        """REGRESIÓN: contra el código viejo, completar_texto llamaba al
        provider con el kill-switch activo."""
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        ds = _FakeDeepSeek()
        an = _FakeAnthropic()
        monkeypatch.setattr(llm, "_deepseek", ds)
        monkeypatch.setattr(llm, "_anthropic", an)

        r = await llm.completar_texto("clasifica esto", telefono=TEL)

        assert r is None
        assert ds.llamadas == 0
        assert an.llamadas == 0

    async def test_kill_switch_bloquea_completar_con_sistema(self, monkeypatch):
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        ds = _FakeDeepSeek()
        an = _FakeAnthropic()
        monkeypatch.setattr(llm, "_deepseek", ds)
        monkeypatch.setattr(llm, "_anthropic", an)

        r = await llm.completar_con_sistema("sys", "msg", telefono=TEL)

        assert r is None
        assert ds.llamadas == 0 and an.llamadas == 0

    async def test_aux_cero_bloquea_sin_llamar_provider(self, monkeypatch):
        """REGRESIÓN: max_llm_aux_calls=0 → la vía auxiliar degrada (None)
        sin tocar el provider."""
        monkeypatch.setenv("BUDGET_MAX_LLM_AUX_CALLS_MENSAJE", "0")
        ds = _FakeDeepSeek()
        monkeypatch.setattr(llm, "_deepseek", ds)
        monkeypatch.setattr(llm, "_anthropic", None)

        with pr.presupuesto_de_mensaje(TEL):
            r = await llm.completar_texto("clasifica", telefono=TEL)

        assert r is None
        assert ds.llamadas == 0

    async def test_aux_no_compite_con_cupo_principal(self, monkeypatch):
        """Snapshot: la llamada aux usa SU contador (llm_aux_calls), no el
        principal (llm_calls) — el loop de brain conserva sus 3."""
        ds = _FakeDeepSeek()
        monkeypatch.setattr(llm, "_deepseek", ds)
        monkeypatch.setattr(llm, "_anthropic", None)

        with pr.presupuesto_de_mensaje(TEL) as pres:
            r = await llm.completar_texto("clasifica", telefono=TEL)
            assert r == "respuesta deepseek"
            assert pres.llm_aux_calls == 1
            assert pres.llm_calls == 0          # cupo principal intacto
            assert pres.costo_usd > 0           # costo SÍ compartido

    async def test_aux_agotado_no_bloquea_principal(self, monkeypatch):
        """Agotar el cupo aux NO niega el principal (dimensiones aparte)."""
        ds = _FakeDeepSeek()
        monkeypatch.setattr(llm, "_deepseek", ds)
        monkeypatch.setattr(llm, "_anthropic", None)

        with pr.presupuesto_de_mensaje(TEL) as pres:
            for _ in range(pres.config.max_llm_aux_calls):
                pres.reservar_llm_aux()
            assert pres.reservar_llm_aux().permitido is False
            assert pres.reservar_llm().permitido is True

    async def test_costo_aux_puede_bloquear_principal(self, monkeypatch):
        """El techo real es USD: si las aux agotan el costo del mensaje,
        el principal queda bloqueado por max_costo_mensaje (criterio
        Hermes: costo SIEMPRE compartido)."""
        with pr.presupuesto_de_mensaje(TEL) as pres:
            pres.reservar_llm_aux()
            pres.consumir_llm(pres.config.max_costo_usd_mensaje + 0.01)

            dec = pres.reservar_llm()
            assert dec.permitido is False
            assert dec.razon == "max_costo_mensaje"


# ── 2. proactivity gateada + presupuesto por unidad ──────────────────────


class TestProactividadGateada:
    async def test_kill_switch_bloquea_generacion_proactiva(self, monkeypatch):
        """REGRESIÓN: el generador proactivo llamaba a _claude con el
        kill-switch activo."""
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        an = _FakeAnthropic()
        monkeypatch.setattr(proactivity, "_claude", an)

        r = await proactivity._invocar_claude_proactivo(
            dict(model="claude-sonnet-4-6", max_tokens=100,
                 messages=[{"role": "user", "content": "hola"}]),
            TEL,
        )

        assert r is None
        assert an.llamadas == 0

    async def test_con_presupuesto_llama_y_consume(self, monkeypatch):
        an = _FakeAnthropic()
        monkeypatch.setattr(proactivity, "_claude", an)

        with pr.presupuesto_de_mensaje(TEL) as pres:
            r = await proactivity._invocar_claude_proactivo(
                dict(model="claude-sonnet-4-6", max_tokens=100,
                     messages=[{"role": "user", "content": "hola"}]),
                TEL,
            )
            assert r is not None
            assert pres.llm_calls == 1
            assert pres.costo_usd > 0

        assert an.llamadas == 1

    async def test_verificar_proactividad_abre_presupuesto_por_unidad(self, monkeypatch):
        """Cada usuario del batch corre bajo su PROPIO presupuesto (criterio
        Hermes: unidad granular, no batch global) — y dentro de la unidad
        hay contexto (sin radar reserva_sin_contexto)."""
        presupuestos_vistos = []

        async def _fake_evaluar(usuario, ahora_local, offset_min):
            pres = pr.presupuesto_actual()
            # Referencia fuerte al objeto (id() se recicla tras GC)
            presupuestos_vistos.append(
                (usuario["telefono"], pres.telefono if pres else None, pres)
            )
            return None  # sin mensaje → no envía

        monkeypatch.setattr(proactivity, "_evaluar_disparadores", _fake_evaluar)

        import agent.memory as memoria
        usuarios = [
            {"telefono": "111", "nombre": "A", "mensajes_hoy": 0},
            {"telefono": "222", "nombre": "B", "mensajes_hoy": 0},
        ]

        async def _fake_usuarios():
            return usuarios

        async def _fake_tz(t):
            return 0

        monkeypatch.setattr(memoria, "obtener_usuarios_proactividad_activos", _fake_usuarios)
        monkeypatch.setattr(memoria, "obtener_timezone", _fake_tz)

        await proactivity.verificar_proactividad(proveedor=None)

        assert len(presupuestos_vistos) == 2
        # Dentro de cada unidad HAY presupuesto y es el del usuario correcto
        assert presupuestos_vistos[0][1] == "111"
        assert presupuestos_vistos[1][1] == "222"
        # Y son presupuestos DISTINTOS (no un batch global compartido)
        assert presupuestos_vistos[0][2] is not presupuestos_vistos[1][2]
        assert pr.snapshot_eventos().get("reserva_sin_contexto", 0) == 0


# ── 3. vision gateada (principal foreground) ─────────────────────────────


class TestVisionGateada:
    async def test_kill_switch_bloquea_analisis(self, monkeypatch):
        """REGRESIÓN: vision llamaba al provider con el kill-switch activo."""
        monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        creaciones = []

        class _FakeCliente(_FakeAnthropic):
            pass

        def _fake_ctor(api_key=None, **k):
            c = _FakeCliente()
            creaciones.append(c)
            return c

        monkeypatch.setattr(vision.anthropic, "AsyncAnthropic", _fake_ctor)

        r = await vision.analizar_imagen_con_claude(b"bytes", "image/jpeg", "")

        assert r is None
        assert all(c.llamadas == 0 for c in creaciones)

    async def test_con_presupuesto_analiza_y_consume(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        clientes = []

        def _fake_ctor(api_key=None, **k):
            c = _FakeAnthropic("texto de la imagen")
            clientes.append(c)
            return c

        monkeypatch.setattr(vision.anthropic, "AsyncAnthropic", _fake_ctor)

        with pr.presupuesto_de_mensaje(TEL) as pres:
            r = await vision.analizar_imagen_con_claude(b"bytes", "image/jpeg", "")
            assert r == "texto de la imagen"
            assert pres.llm_calls == 1   # principal (alimenta la respuesta)
            assert pres.costo_usd > 0

        assert sum(c.llamadas for c in clientes) == 1


# ── 4. Clientes provider muertos eliminados ──────────────────────────────


class TestClientesMuertosEliminados:
    def test_emotion_sin_cliente_propio(self):
        """REGRESIÓN: emotion.py instanciaba un AsyncAnthropic que nunca
        usaba (superficie de bypass latente)."""
        import agent.emotion as emotion
        assert not hasattr(emotion, "_claude")

    def test_config_aux_existe_con_default_seguro(self):
        cfg = pr.cargar_config()
        assert cfg.max_llm_aux_calls == 3
        assert "max_llm_aux_calls" in pr.RAZONES_BLOQUEO
