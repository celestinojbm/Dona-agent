"""Tests de F23 — selector y combinación de modelos.

Todo con el proveedor SIMULADO (sin red, 0 USD). Cubre: catálogo y precios
configurables; capa común de proveedores; selección por chat/agente, cambio a
mitad de conversación sin perder contexto, modo Auto por tarea/coste;
combinación (plan+ejecución y comparación) con el modelo registrado por paso;
sugerencias; y persistencia de preferencia (DB aislada).
"""

import importlib
import sys
from decimal import Decimal

import pytest

import agent.memory
from agent.multi_model import catalogo, seleccion, sugerencias
from agent.multi_model import providers as prov
from agent.multi_model import combinacion
from agent.multi_model.providers import ProveedorSimulado, forzar_proveedor


@pytest.fixture(autouse=True)
def _simulado():
    """Fuerza el proveedor simulado en todos los tests (nunca red real)."""
    forzar_proveedor(ProveedorSimulado())
    yield
    forzar_proveedor(None)


@pytest.fixture
def _flag_on(monkeypatch):
    monkeypatch.setenv("DONA_MULTI_MODEL_ENABLED", "true")


# ───────────────────── Catálogo y precios ─────────────────────

class TestCatalogo:
    def test_modelos_y_proveedores(self):
        ids = {m.id for m in catalogo.modelos_disponibles()}
        assert "claude-sonnet-4-5" in ids
        assert "gpt-4o" in ids
        assert catalogo.existe("claude-haiku-4-5-20251001")
        assert not catalogo.existe("no-existe")
        # Gemini fuera del catálogo hasta tener adaptador de texto real.
        assert "gemini-2.5-flash" not in ids
        assert not catalogo.existe("gemini-2.5-flash")

    def test_precio_override_por_env(self, monkeypatch):
        monkeypatch.setenv("DONA_MODEL_PRICES", '{"gpt-4o":{"in":1.0,"out":2.0}}')
        pin, pout = catalogo.precio_modelo("gpt-4o")
        assert pin == Decimal("1.0") and pout == Decimal("2.0")

    def test_costo_estimado_es_decimal(self):
        c = catalogo.costo_estimado_usd("claude-haiku-4-5-20251001", 1_000_000, 0)
        assert c == Decimal("1.0")  # 1M tokens in * 1.0 USD/Mtok
        assert isinstance(c, Decimal)


# ───────────────────── Capa de proveedores ─────────────────────

class TestProveedores:
    async def test_simulado_sin_red(self):
        p = ProveedorSimulado()
        r = await p.generar(modelo="gpt-4o", mensajes=[{"role": "user", "content": "hola"}])
        assert r.simulado and r.proveedor == "openai"
        assert "simulada" in r.texto
        assert r.costo_usd is not None

    def test_proveedor_para_usa_forzado(self):
        assert isinstance(prov.proveedor_para("claude-sonnet-4-5"), ProveedorSimulado)

    def test_proveedor_para_modelo_desconocido(self):
        forzar_proveedor(None)
        with pytest.raises(ValueError):
            prov.proveedor_para("no-existe")


# ───────────────────── Selección / Auto / cambio ─────────────────────

class TestSeleccion:
    def test_flag_apagado_usa_default(self, monkeypatch):
        monkeypatch.delenv("DONA_MULTI_MODEL_ENABLED", raising=False)
        e = seleccion.elegir(preferencia="gpt-4o", modo_auto=True)
        assert e.modelo == seleccion.MODELO_POR_DEFECTO and e.razon == "flag_apagado"

    def test_preferencia_explicita(self, _flag_on):
        e = seleccion.elegir(preferencia="gpt-4o")
        assert e.modelo == "gpt-4o" and e.razon == "preferencia_explicita"

    def test_preferencia_invalida_cae_a_default(self, _flag_on):
        e = seleccion.elegir(preferencia="no-existe")
        assert e.modelo == seleccion.MODELO_POR_DEFECTO

    def test_auto_tarea_potente_mas_capaz(self, _flag_on):
        e = seleccion.elegir(clase_tarea="razonamiento", modo_auto=True)
        assert e.auto and e.modelo == "claude-sonnet-4-5"  # mayor nivel_coste candidato

    def test_auto_presupuesto_ajustado_mas_barato(self, _flag_on):
        e = seleccion.elegir(clase_tarea="razonamiento", modo_auto=True, presupuesto_creditos=3)
        assert e.modelo == "gpt-4o"  # candidato más barato de razonamiento (nivel 2)

    def test_auto_tarea_barata(self, _flag_on):
        e = seleccion.elegir(clase_tarea="clasificacion", modo_auto=True)
        # Sin Gemini, el único candidato barato de clasificación es Haiku.
        assert e.modelo == "claude-haiku-4-5-20251001"

    def test_cambiar_modelo_preserva_contexto(self):
        hist = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        nuevo_hist, modelo = seleccion.cambiar_modelo(hist, "gpt-4o")
        assert nuevo_hist is hist  # mismo historial, contexto intacto
        assert modelo == "gpt-4o"

    def test_cambiar_modelo_invalido(self):
        with pytest.raises(ValueError):
            seleccion.cambiar_modelo([], "no-existe")

    async def test_generar_usa_proveedor(self):
        r = await seleccion.generar(modelo="gpt-4o", mensajes=[{"role": "user", "content": "x"}])
        assert r.modelo == "gpt-4o" and r.simulado


# ───────────────────── Combinación ─────────────────────

class TestCombinacion:
    async def test_plan_y_ejecucion_registra_modelo_por_paso(self):
        res = await combinacion.planificar_y_ejecutar(
            modelo_plan="claude-sonnet-4-5",
            modelo_exec="gpt-4o",
            mensajes=[{"role": "user", "content": "organiza mi semana"}],
        )
        assert res.modo == "plan_y_ejecucion"
        assert res.pasos[0].nombre == "planificación"
        assert res.pasos[0].modelo == "claude-sonnet-4-5"
        # Los pasos de ejecución usan el modelo ejecutor.
        assert all(p.modelo == "gpt-4o" for p in res.pasos[1:])

    async def test_comparacion_lado_a_lado(self):
        res = await combinacion.comparar_lado_a_lado(
            modelos=["claude-sonnet-4-5", "gpt-4o"],
            mensajes=[{"role": "user", "content": "idea de campaña"}],
        )
        assert res.modo == "comparacion"
        assert [r.modelo for r in res.respuestas] == ["claude-sonnet-4-5", "gpt-4o"]

    async def test_pasos_para_recibo_incluye_modelo(self):
        res = await combinacion.comparar_lado_a_lado(
            modelos=["gpt-4o"], mensajes=[{"role": "user", "content": "x"}]
        )
        lineas = combinacion.pasos_para_recibo(res)
        assert lineas and lineas[0]["modelo"] == "gpt-4o"
        assert "modelo gpt-4o" in lineas[0]["detalle"]


# ───────────────────── Sugerencias ─────────────────────

class TestSugerencias:
    def test_chips_y_modelo_recomendado(self):
        s = sugerencias.sugerencias_para(clase_tarea="borrador")
        assert "Confirmar" in s.respuestas_sugeridas
        assert "Enviar borrador" in s.siguientes_acciones
        assert catalogo.existe(s.modelo_recomendado)

    def test_clase_desconocida_usa_defaults(self):
        s = sugerencias.sugerencias_para(clase_tarea="rarisimo")
        assert s.respuestas_sugeridas and s.siguientes_acciones


# ───────────────────── Persistencia (DB aislada) ─────────────────────

@pytest.fixture
async def prefs(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'mm.db'}")
    monkeypatch.setenv("DONA_MULTI_MODEL_ENABLED", "true")
    importlib.reload(agent.memory)
    for mod in ("agent.multi_model.preferencias", "agent.multi_model.models"):
        sys.modules.pop(mod, None)
    importlib.import_module("agent.multi_model.models")  # registra tabla en Base
    p = importlib.import_module("agent.multi_model.preferencias")
    await agent.memory.inicializar_db()
    return p


class TestPreferencias:
    async def test_fijar_y_obtener(self, prefs):
        await prefs.fijar_preferencia("5551", "chat", "c1", modelo_id="gpt-4o")
        got = await prefs.obtener_preferencia("5551", "chat", "c1")
        assert got["modelo_id"] == "gpt-4o" and got["modo_auto"] is False

    async def test_modo_auto_por_agente(self, prefs):
        await prefs.fijar_preferencia("5551", "agente", "a1", modo_auto=True)
        got = await prefs.obtener_preferencia("5551", "agente", "a1")
        assert got["modo_auto"] is True

    async def test_scope_invalido(self, prefs):
        with pytest.raises(ValueError):
            await prefs.fijar_preferencia("5551", "otro", "x", modelo_id="gpt-4o")

    async def test_modelo_invalido(self, prefs):
        with pytest.raises(ValueError):
            await prefs.fijar_preferencia("5551", "chat", "c1", modelo_id="no-existe")

    async def test_preferencia_ajena_no_se_ve(self, prefs):
        await prefs.fijar_preferencia("5551", "chat", "c1", modelo_id="gpt-4o")
        assert await prefs.obtener_preferencia("9999", "chat", "c1") is None


# ───────────────────── Endurecimiento / rutas de error (mocks) ─────────────────────

class _ProveedorFalla(ProveedorSimulado):
    """Proveedor mock que falla para un modelo dado; útil para probar fallback."""

    def __init__(self, modelo_que_falla, excepcion=RuntimeError("boom")):
        super().__init__(etiqueta="falla")
        self.modelo_que_falla = modelo_que_falla
        self.excepcion = excepcion

    async def generar(self, *, modelo, mensajes, system="", max_tokens=1024, **kw):
        if modelo == self.modelo_que_falla:
            raise self.excepcion
        return await super().generar(
            modelo=modelo, mensajes=mensajes, system=system, max_tokens=max_tokens
        )


class TestFlagApagadoSinRed:
    async def test_generar_flag_off_usa_simulado(self, monkeypatch):
        # Flag apagado + SIN proveedor forzado → proveedor_para devuelve simulado;
        # nunca se intenta un proveedor real / API de pago.
        monkeypatch.delenv("DONA_MULTI_MODEL_ENABLED", raising=False)
        forzar_proveedor(None)
        r = await seleccion.generar(
            modelo="gpt-4o", mensajes=[{"role": "user", "content": "x"}]
        )
        assert r.simulado is True

    def test_proveedor_para_flag_off_es_simulado(self, monkeypatch):
        forzar_proveedor(None)
        p = prov.proveedor_para("gpt-4o", permitir_real=False)
        assert isinstance(p, ProveedorSimulado)


class TestTimeoutRetry:
    async def test_reintenta_transitorio_y_luego_ok(self):
        import asyncio

        llamadas = {"n": 0}

        async def factory():
            llamadas["n"] += 1
            if llamadas["n"] < 3:
                raise asyncio.TimeoutError()
            return "ok"

        res = await prov.invocar_con_timeout_retry(factory, timeout=1, reintentos=3)
        assert res == "ok" and llamadas["n"] == 3

    async def test_no_transitorio_no_reintenta(self):
        llamadas = {"n": 0}

        async def factory():
            llamadas["n"] += 1
            raise ValueError("4xx inválido")

        with pytest.raises(ValueError):
            await prov.invocar_con_timeout_retry(factory, timeout=1, reintentos=3)
        assert llamadas["n"] == 1  # no reintentó

    async def test_timeout_agota_reintentos(self):
        import asyncio

        async def factory():
            await asyncio.sleep(10)  # nunca termina a tiempo

        with pytest.raises(asyncio.TimeoutError):
            await prov.invocar_con_timeout_retry(factory, timeout=0.01, reintentos=1)


class TestFallback:
    async def test_generar_cae_a_default_si_falla(self, _flag_on):
        # El modelo pedido falla; fallback al modelo por defecto (distinto).
        forzar_proveedor(_ProveedorFalla("gpt-4o"))
        r = await seleccion.generar(
            modelo="gpt-4o", mensajes=[{"role": "user", "content": "x"}]
        )
        assert r.modelo == seleccion.MODELO_POR_DEFECTO

    async def test_sin_fallback_propaga(self, _flag_on):
        forzar_proveedor(_ProveedorFalla("gpt-4o"))
        with pytest.raises(RuntimeError):
            await seleccion.generar(
                modelo="gpt-4o", mensajes=[{"role": "user", "content": "x"}],
                permitir_fallback=False,
            )


class TestTopesDeCoste:
    async def test_comparar_limita_modelos(self):
        # Más modelos que el tope → se recortan a TOPE_MODELOS_COMPARAR.
        modelos = ["gpt-4o", "claude-sonnet-4-5", "claude-haiku-4-5-20251001", "gpt-4o"]
        res = await combinacion.comparar_lado_a_lado(
            modelos=modelos, mensajes=[{"role": "user", "content": "x"}]
        )
        assert len(res.respuestas) == combinacion.TOPE_MODELOS_COMPARAR

    async def test_planificar_acota_pasos(self):
        res = await combinacion.planificar_y_ejecutar(
            modelo_plan="claude-sonnet-4-5", modelo_exec="gpt-4o",
            mensajes=[{"role": "user", "content": "x"}], max_pasos=99,
        )
        # 1 (planificación) + a lo sumo TOPE_PASOS de ejecución.
        assert len(res.pasos) <= combinacion.TOPE_PASOS + 1

    async def test_tope_coste_detiene_comparacion(self):
        # tope_coste_usd=0 → no se hace ninguna consulta tras agotar presupuesto.
        res = await combinacion.comparar_lado_a_lado(
            modelos=["gpt-4o", "claude-sonnet-4-5"],
            mensajes=[{"role": "user", "content": "x"}],
            tope_coste_usd="0",
        )
        assert res.respuestas == []


class TestValidacionPrecios:
    def test_precios_invalidos_se_ignoran(self, monkeypatch):
        # JSON válido pero con entradas/campos malformados → se ignoran; el
        # precio base se mantiene (no rompe).
        monkeypatch.setenv(
            "DONA_MODEL_PRICES",
            '{"gpt-4o":{"in":"abc","out":-5}, "claude-sonnet-4-5":"nope"}',
        )
        pin, pout = catalogo.precio_modelo("gpt-4o")
        assert pin == Decimal("2.5") and pout == Decimal("10.0")  # base intacto
        # sonnet con cfg no-dict → base intacto
        s_in, s_out = catalogo.precio_modelo("claude-sonnet-4-5")
        assert s_in == Decimal("3.0") and s_out == Decimal("15.0")

    def test_json_invalido_se_ignora(self, monkeypatch):
        monkeypatch.setenv("DONA_MODEL_PRICES", "no es json")
        pin, pout = catalogo.precio_modelo("gpt-4o")
        assert pin == Decimal("2.5") and pout == Decimal("10.0")
