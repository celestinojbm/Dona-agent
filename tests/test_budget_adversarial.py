# tests/test_budget_adversarial.py — Fase 0 · 4.1/4.2 · PR 4: batería adversarial

"""
Batería adversarial del RuntimeBudgetGuard (spec de Hermes, cierre de C6).
Ataca el sistema completo (retry, timeouts, fallback, tool-loop, kill-switch)
en vez de cada unidad, y PINEA dos regresiones contra el código viejo:

1. RETRY MULTIPLICADOR: el loop de generar_respuesta tenía _max_reintentos=3
   hardcodeado Y un retry oculto — los errores NO transitorios (4xx de request
   inválido) también volvían a iterar porque faltaba el `break`. Tres llamadas
   reales al provider por un mismo error irrecuperable. Ahora: máx 1 reintento
   (config llm_max_reintentos), solo 429/5xx/red, solo con presupuesto global.

2. TOOL DESCONOCIDA SIN RESPUESTA: un tool_use con nombre no registrado se
   saltaba sin apendear tool_result — la siguiente llamada al API real
   fallaría con 400 (bloque sin respuesta). Ahora recibe un tool_result de
   error que instruye cerrar.

El resto verifica los invariantes de salida de Hermes: sin segundo retry
oculto, fallback gateado, 9ª tool denegada con tool_result bien formado,
modelo que ignora la denegación se corta igual, nested no reinicia contador,
kill-switch corta a mitad de loop, timeout sin reserva huérfana ni consumo
tardío, sentinel de provider directo y aislamiento entre mensajes concurrentes.
"""

from __future__ import annotations

import asyncio
import time

import pytest

import agent.brain as brain
import agent.presupuesto_runtime as pr


TEL = "15550009999"


@pytest.fixture(autouse=True)
def _budget_limpio(monkeypatch):
    pr._contadores_eventos.clear()
    pr._owners_suspendidos.clear()
    pr._costo_diario_owner.clear()
    for v in (
        "DONA_LLM_COST_KILL_SWITCH",
        "BUDGET_MAX_LLM_CALLS_MENSAJE",
        "BUDGET_LLM_MAX_REINTENTOS",
    ):
        monkeypatch.delenv(v, raising=False)
    yield
    pr._contadores_eventos.clear()
    pr._costo_diario_owner.clear()


# ── Fakes ────────────────────────────────────────────────────────────────


class _Usage:
    input_tokens = 10
    output_tokens = 10


class _BlkText:
    type = "text"

    def __init__(self, txt="listo"):
        self.text = txt


class _BlkToolTZ:
    type = "tool_use"
    name = "guardar_zona_horaria"

    def __init__(self, i, input=None):
        self.id = f"t{i}"
        self.input = {"offset_minutos": -300} if input is None else input


class _BlkToolDesconocida:
    type = "tool_use"
    name = "borrar_todo_el_sistema"

    def __init__(self, i=0):
        self.id = f"x{i}"
        self.input = {}


class _Resp:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content
        self.usage = _Usage()


def _resp_texto(txt="ok"):
    return _Resp("end_turn", [_BlkText(txt)])


def _resp_tools(n):
    return _Resp("tool_use", [_BlkToolTZ(i) for i in range(n)])


def _mock_create(monkeypatch, secuencia):
    """Mockea client.messages.create. `secuencia`: callable(n)->resp/raise."""
    llamadas = {"n": 0, "kwargs": []}

    async def _fake(**kwargs):
        i = llamadas["n"]
        llamadas["n"] += 1
        llamadas["kwargs"].append(kwargs)
        r = secuencia(i)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(brain.client.messages, "create", _fake)
    return llamadas


@pytest.fixture
def sin_fallback(monkeypatch):
    """Neutraliza los clientes de fallback para aislar el path primario."""
    monkeypatch.setattr(brain, "_deepseek_client", None)
    monkeypatch.setattr(brain, "_openai_client", None)


@pytest.fixture
def sleep_instantaneo(monkeypatch):
    """El backoff del retry no duerme de verdad; registra cuánto pidió."""
    esperas = []

    async def _fake_sleep(s):
        esperas.append(s)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    return esperas


@pytest.fixture
def tools_mockeadas(monkeypatch):
    """Mockea la tool más barata (guardar_timezone) contando ejecuciones."""
    ejecuciones = []

    async def _fake_tz(telefono, offset_min, *a, **k):
        ejecuciones.append(offset_min)

    import agent.memory as memoria
    monkeypatch.setattr(memoria, "guardar_timezone", _fake_tz)
    return ejecuciones


def _config_con(**overrides):
    base = pr.cargar_config()
    return base.__class__(**{**base.__dict__, **overrides})


# ── 1. Retry apretado a máx 1 (REGRESIÓN núcleo) ─────────────────────────


class TestRetryApretado:
    async def test_error_transitorio_reintenta_una_sola_vez(
        self, monkeypatch, sin_fallback, sleep_instantaneo
    ):
        """REGRESIÓN: contra el código viejo (_max_reintentos=3) se hacían
        3 llamadas reales al provider. Ahora: original + 1 reintento = 2."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: Exception("529 overloaded"))

        resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 2  # viejo: 3
        assert len(sleep_instantaneo) == 1  # un solo backoff
        assert isinstance(resp, str) and resp

    async def test_error_no_transitorio_no_reintenta(
        self, monkeypatch, sin_fallback, sleep_instantaneo
    ):
        """REGRESIÓN (retry oculto): el código viejo no tenía `break` para
        errores no transitorios — un 400 de request inválido también
        iteraba 3 veces. Ahora: UNA llamada y directo al fallback."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(
            monkeypatch, lambda n: Exception("400 invalid_request_error")
        )

        resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 1  # viejo: 3
        assert sleep_instantaneo == []  # sin backoff inútil
        assert isinstance(resp, str) and resp

    async def test_reintentos_configurables_a_cero(
        self, monkeypatch, sin_fallback, sleep_instantaneo
    ):
        """BUDGET_LLM_MAX_REINTENTOS=0 → ni un reintento."""
        monkeypatch.setenv("BUDGET_LLM_MAX_REINTENTOS", "0")
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: Exception("503 unavailable"))

        await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 1
        assert sleep_instantaneo == []

    async def test_retry_respeta_presupuesto_de_tiempo(
        self, monkeypatch, sin_fallback, sleep_instantaneo
    ):
        """Error transitorio pero el tiempo restante del mensaje no alcanza
        para el backoff → no duerme, no reintenta, va al fallback."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: Exception("529 overloaded"))

        with pr.presupuesto_de_mensaje(TEL) as pres:
            # Quedan ~1.5s de presupuesto; el backoff pide 2s.
            pres.iniciado = time.monotonic() - (pres.config.hard_segundos - 1.5)
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 1
        assert sleep_instantaneo == []
        assert isinstance(resp, str) and resp

    async def test_retry_respeta_cupo_de_llamadas(
        self, monkeypatch, sin_fallback, sleep_instantaneo
    ):
        """Error transitorio pero el cupo max_llm_calls ya se agotó con el
        intento real → no reintenta (el intento fallido consume cupo)."""
        monkeypatch.setenv("BUDGET_MAX_LLM_CALLS_MENSAJE", "1")
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: Exception("500 server error"))

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 1
        assert sleep_instantaneo == []
        assert isinstance(resp, str) and resp

    def test_clasificacion_transitorio_cerrada(self):
        """Solo 429/5xx/red reintenta (spec Hermes). 4xx de request NO."""
        assert brain._es_error_llm_transitorio(Exception("429 rate_limit_error"))
        assert brain._es_error_llm_transitorio(Exception("503 Service Unavailable"))
        assert brain._es_error_llm_transitorio(Exception("overloaded_error"))
        assert not brain._es_error_llm_transitorio(Exception("400 invalid_request_error"))
        assert not brain._es_error_llm_transitorio(Exception("401 authentication_error"))
        assert not brain._es_error_llm_transitorio(Exception("permission denied"))

        class APIConnectionError(Exception):
            pass

        assert brain._es_error_llm_transitorio(APIConnectionError("conexión caída"))


# ── 2. Timeout de provider: sin retry, sin reserva huérfana ──────────────


class TestTimeoutSinRunaway:
    async def test_timeout_no_reintenta_ni_deja_reserva_huerfana(
        self, monkeypatch, sin_fallback
    ):
        """Provider colgado → timeout del guard → respuesta segura SIN
        reintento. Semántica determinista (criterio Hermes): el intento real
        consume cupo (anti-retry-infinito) pero NO consume costo, y el
        evento queda cerrado."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])

        intentos = {"n": 0}

        async def _colgado(**kwargs):
            intentos["n"] += 1
            await asyncio.sleep(5)
            return _resp_texto()

        monkeypatch.setattr(brain.client.messages, "create", _colgado)

        pres = pr.PresupuestoMensaje(TEL, config=_config_con(llm_timeout_segundos=0.05))
        token = pr._presupuesto_actual.set(pres)
        try:
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)
        finally:
            pr._presupuesto_actual.reset(token)

        assert intentos["n"] == 1          # sin retry post-timeout
        assert pres.llm_calls == 1         # cupo del intento real: consumido
        assert pres.costo_usd == 0.0       # costo: NO consumido (nada llegó)
        assert pr.snapshot_eventos().get("timeout_llm", 0) >= 1
        assert isinstance(resp, str) and resp

    async def test_respuesta_tardia_post_timeout_no_consume(
        self, monkeypatch, sin_fallback
    ):
        """El provider 'responde' después de que el timeout cerró: la
        corrutina queda cancelada — no hay segunda respuesta ni consumo
        tardío de presupuesto."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])

        completo = {"flag": False}

        async def _tardio(**kwargs):
            await asyncio.sleep(0.3)
            completo["flag"] = True
            return _resp_texto()

        monkeypatch.setattr(brain.client.messages, "create", _tardio)

        pres = pr.PresupuestoMensaje(TEL, config=_config_con(llm_timeout_segundos=0.05))
        token = pr._presupuesto_actual.set(pres)
        try:
            await brain.generar_respuesta("hola", [], telefono=TEL)
        finally:
            pr._presupuesto_actual.reset(token)

        await asyncio.sleep(0.4)  # margen para que el "tardío" intentara llegar
        assert completo["flag"] is False  # cancelado: nunca completó
        assert pres.costo_usd == 0.0      # sin consumo tardío


# ── 3. Fallback gateado ──────────────────────────────────────────────────


class _FakeOpenAIClient:
    """Cliente estilo OpenAI con contador de llamadas reales."""

    def __init__(self, texto="respuesta del fallback"):
        self.llamadas = 0
        cliente = self

        class _Completions:
            async def create(self, **kwargs):
                cliente.llamadas += 1

                class _R:
                    class usage:
                        total_tokens = 100

                    choices = [type("C", (), {"message": type("M", (), {"content": texto})()})()]

                return _R()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class TestFallbackGateado:
    async def test_fallback_no_se_llama_sin_presupuesto(self, monkeypatch):
        """Primario falla y el cupo LLM ya se agotó → el fallback NO llama
        a su provider (mock contador en 0)."""
        monkeypatch.setenv("BUDGET_MAX_LLM_CALLS_MENSAJE", "1")
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        _mock_create(monkeypatch, lambda n: Exception("400 invalid_request_error"))

        deepseek = _FakeOpenAIClient()
        monkeypatch.setattr(brain, "_deepseek_client", deepseek)
        monkeypatch.setattr(brain, "_openai_client", None)

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert deepseek.llamadas == 0
        assert isinstance(resp, str) and resp

    async def test_fallback_con_presupuesto_llama_una_vez(self, monkeypatch):
        """Con presupuesto disponible, el fallback corre UNA vez bajo el
        guard y responde."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(
            monkeypatch, lambda n: Exception("400 invalid_request_error")
        )

        deepseek = _FakeOpenAIClient("texto del fallback")
        monkeypatch.setattr(brain, "_deepseek_client", deepseek)
        monkeypatch.setattr(brain, "_openai_client", None)

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)

        assert llamadas["n"] == 1          # primario: una sola (sin retry oculto)
        assert deepseek.llamadas == 1      # fallback: exactamente una
        assert "texto del fallback" in resp


# ── 3b. Timeout en fallback + cap de entrada (4.1) ───────────────────────


class TestFallbackTimeoutYCapEntrada:
    async def test_fallback_colgado_no_cuelga(self, monkeypatch):
        """4.1: un fallback (DeepSeek) que se cuelga queda acotado por
        con_timeout_llm — el guard lo corta y la respuesta vuelve segura en
        vez de colgar el request para siempre."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        # Primario falla con error NO transitorio → sin retry, directo al fallback.
        _mock_create(monkeypatch, lambda n: Exception("400 invalid_request_error"))

        colgado = {"n": 0}

        class _DeepseekColgado:
            def __init__(self):
                colg = colgado

                class _Completions:
                    async def create(self, **kwargs):
                        colg["n"] += 1
                        await asyncio.sleep(5)  # se cuelga
                        raise AssertionError("no debería completar tras el timeout")

                class _Chat:
                    completions = _Completions()

                self.chat = _Chat()

        monkeypatch.setattr(brain, "_deepseek_client", _DeepseekColgado())
        monkeypatch.setattr(brain, "_openai_client", None)

        pres = pr.PresupuestoMensaje(TEL, config=_config_con(llm_timeout_segundos=0.05))
        token = pr._presupuesto_actual.set(pres)
        try:
            resp = await brain.generar_respuesta("hola", [], telefono=TEL)
        finally:
            pr._presupuesto_actual.reset(token)

        assert colgado["n"] == 1                # el fallback se intentó una vez
        assert isinstance(resp, str) and resp   # respuesta segura, sin colgarse
        assert pr.snapshot_eventos().get("timeout_llm", 0) >= 1

    async def test_mensaje_gigante_se_trunca(self, monkeypatch, sin_fallback):
        """4.1: un mensaje desmesurado se trunca al cap antes de construir el
        request — no se manda completo al provider (anti blowup de tokens)."""
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto("ok"))

        cap = brain._MAX_LONGITUD_MENSAJE_USUARIO
        gigante = "A" * (cap + 5000)
        resp = await brain.generar_respuesta(gigante, [], telefono=TEL)

        assert isinstance(resp, str) and resp
        enviado = str(llamadas["kwargs"][0]["messages"])
        assert ("A" * (cap + 1)) not in enviado   # no se mandó el mensaje completo
        assert ("A" * 200) in enviado             # pero sí su prefijo real (truncado)


# ── 4. Tool-loop adversarial ─────────────────────────────────────────────


class TestToolLoopAdversarial:
    async def test_novena_tool_denegada_con_tool_result_bien_formado(
        self, monkeypatch, tools_mockeadas
    ):
        """9 tools pedidas: 8 ejecutan, la 9ª NO, y su tool_result existe,
        referencia el id correcto e instruye cerrar (no queda sin responder)."""
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto())

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain._manejar_tool_use(
                _resp_tools(9), [], "system", TEL, None
            )

        assert len(tools_mockeadas) == 8
        # El siguiente request lleva los 9 tool_results (8 éxitos + 1 denegación)
        kwargs = llamadas["kwargs"][0]
        resultados = kwargs["messages"][-1]["content"]
        assert len(resultados) == 9
        denegado = resultados[-1]
        assert denegado["tool_use_id"] == "t8"
        assert "límite" in denegado["content"].lower()
        assert isinstance(resp, str) and resp

    async def test_modelo_ignora_denegacion_se_corta_sin_runaway(
        self, monkeypatch, tools_mockeadas
    ):
        """El modelo ignora el tool_result de denegación y SIGUE pidiendo
        tools en cada vuelta: el sistema corta por max_llm_calls sin diálogo
        infinito, y el contador de tools NO se reinicia entre vueltas."""
        llamadas = _mock_create(monkeypatch, lambda n: _resp_tools(12))

        with pr.presupuesto_de_mensaje(TEL) as pres:
            resp = await brain._manejar_tool_use(
                _resp_tools(12), [], "system", TEL, None
            )

        assert len(tools_mockeadas) == pres.config.max_tool_calls  # 8 TOTAL
        assert llamadas["n"] == pres.config.max_llm_calls          # 3, ni una más
        assert isinstance(resp, str) and resp

    async def test_nested_no_reinicia_contador(self, monkeypatch, tools_mockeadas):
        """Vueltas de 5 tools: la segunda vuelta solo ejecuta las 3 que
        caben en el presupuesto del MENSAJE (5+3=8), no 5+5."""
        secuencia = [_resp_tools(5), _resp_texto()]
        llamadas = _mock_create(
            monkeypatch, lambda n: secuencia[min(n, len(secuencia) - 1)]
        )

        with pr.presupuesto_de_mensaje(TEL):
            await brain._manejar_tool_use(_resp_tools(5), [], "system", TEL, None)

        assert len(tools_mockeadas) == 8  # 5 + 3 — el contador es del mensaje

    async def test_kill_switch_durante_loop_corta_todo(self, monkeypatch):
        """El kill-switch se activa tras la primera tool: el resto del loop
        se deniega y el cierre es controlado (sin más llamadas LLM)."""
        ejecuciones = []

        async def _tz_que_activa_switch(telefono, offset_min, *a, **k):
            ejecuciones.append(offset_min)
            monkeypatch.setenv("DONA_LLM_COST_KILL_SWITCH", "true")

        import agent.memory as memoria
        monkeypatch.setattr(memoria, "guardar_timezone", _tz_que_activa_switch)
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto())

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain._manejar_tool_use(
                _resp_tools(5), [], "system", TEL, None
            )

        assert len(ejecuciones) == 1   # solo la primera corrió
        assert llamadas["n"] == 0      # la llamada LLM siguiente: denegada
        assert isinstance(resp, str) and resp


# ── 5. Tool desconocida / malformed (REGRESIÓN tool_result faltante) ─────


class TestToolsMalformedYDesconocidas:
    async def test_tool_desconocida_recibe_tool_result(self, monkeypatch):
        """REGRESIÓN: el código viejo saltaba la tool desconocida SIN
        apendear tool_result — el API real rechaza la siguiente llamada
        (400, bloque sin respuesta). Ahora recibe un error que instruye
        cerrar, y jamás se ejecuta nada por nombre no registrado."""
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto())

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain._manejar_tool_use(
                _Resp("tool_use", [_BlkToolDesconocida()]), [], "system", TEL, None
            )

        resultados = llamadas["kwargs"][0]["messages"][-1]["content"]
        assert len(resultados) == 1  # viejo: 0 (sin respuesta al bloque)
        assert resultados[0]["tool_use_id"] == "x0"
        assert "no existe" in resultados[0]["content"]
        assert isinstance(resp, str) and resp

    async def test_tool_malformed_no_crashea(self, monkeypatch, tools_mockeadas):
        """tool_use sin los args requeridos: no crash, no ejecución, error
        seguro como tool_result."""
        llamadas = _mock_create(monkeypatch, lambda n: _resp_texto())
        bloque_roto = _BlkToolTZ(0, input={})  # sin offset_minutos

        with pr.presupuesto_de_mensaje(TEL):
            resp = await brain._manejar_tool_use(
                _Resp("tool_use", [bloque_roto]), [], "system", TEL, None
            )

        assert tools_mockeadas == []  # nunca llegó a ejecutar
        resultados = llamadas["kwargs"][0]["messages"][-1]["content"]
        assert "error" in resultados[0]["content"].lower()
        assert isinstance(resp, str) and resp

    def test_denegaciones_usan_razones_cerradas(self):
        """Toda denegación lleva una razón del set CERRADO (no strings
        arbitrarios que rompan observabilidad)."""
        with pr.presupuesto_de_mensaje(TEL) as pres:
            for _ in range(pres.config.max_tool_calls):
                pres.reservar_tool()
            dec = pres.reservar_tool()

        assert dec.permitido is False
        assert dec.razon in pr.RAZONES_BLOQUEO


# ── 6. Sentinel de arquitectura: nadie llama al provider directo ─────────


class TestSentinelProviderDirecto:
    async def test_toda_llamada_provider_pasa_por_el_wrapper(
        self, monkeypatch, tools_mockeadas, sin_fallback
    ):
        """Sentinel (criterio Hermes): si una futura edición de brain llama
        a client.messages.create SIN pasar por _invocar_claude_gateado, este
        test la detecta en el flujo foreground completo (texto + tools)."""
        dentro = {"activo": False, "violaciones": 0, "llamadas": 0}

        _wrapper_original = brain._invocar_claude_gateado

        async def _wrapper_marcado(api_kwargs, telefono):
            dentro["activo"] = True
            try:
                return await _wrapper_original(api_kwargs, telefono)
            finally:
                dentro["activo"] = False

        monkeypatch.setattr(brain, "_invocar_claude_gateado", _wrapper_marcado)

        secuencia = [_resp_tools(2), _resp_texto()]

        async def _probe(**kwargs):
            if not dentro["activo"]:
                dentro["violaciones"] += 1
            i = min(dentro["llamadas"], len(secuencia) - 1)
            dentro["llamadas"] += 1
            return secuencia[i]

        monkeypatch.setattr(brain.client.messages, "create", _probe)
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [{"name": "x"}])

        with pr.presupuesto_de_mensaje(TEL):
            await brain.generar_respuesta("hola", [], telefono=TEL)

        assert dentro["llamadas"] >= 2     # ejerció texto + recursión de tools
        assert dentro["violaciones"] == 0  # ninguna llamada fuera del wrapper


# ── 7. Concurrencia: presupuestos de mensajes aislados ───────────────────


class TestConcurrenciaPresupuestos:
    async def test_mensajes_concurrentes_no_se_contaminan(self):
        """Dos mensajes del mismo usuario en paralelo: agotar el presupuesto
        de A no afecta a B (ContextVar por task), pero el costo DIARIO del
        owner sí es compartido (límite global)."""
        resultados = {}

        async def _mensaje_a():
            with pr.presupuesto_de_mensaje(TEL) as pres:
                for _ in range(pres.config.max_llm_calls):
                    pres.reservar_llm()
                resultados["a_bloqueado"] = not pres.reservar_llm().permitido
                pres.consumir_llm(0.05)
                await asyncio.sleep(0.01)

        async def _mensaje_b():
            await asyncio.sleep(0.005)  # arranca con A ya agotado
            with pr.presupuesto_de_mensaje(TEL) as pres:
                resultados["b_permitido"] = pres.reservar_llm().permitido

        await asyncio.gather(_mensaje_a(), _mensaje_b())

        assert resultados["a_bloqueado"] is True
        assert resultados["b_permitido"] is True
        # El costo diario del owner acumula lo de A (dimensión compartida)
        assert pr.costo_diario_de(TEL) == pytest.approx(0.05)
