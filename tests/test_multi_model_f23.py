"""Tests de F23 — selector y combinación de modelos.

Todo con el proveedor SIMULADO (sin red, 0 USD). Cubre: catálogo y precios
configurables; capa común de proveedores; selección por chat/agente, cambio a
mitad de conversación sin perder contexto, modo Auto por tarea/coste;
combinación (plan+ejecución y comparación) con el modelo registrado por paso;
sugerencias; y persistencia de preferencia (DB aislada).
"""

import importlib
import logging
import sys
from decimal import Decimal

import pytest

import agent.memory
from agent.multi_model import catalogo, combinacion, seleccion, sugerencias
from agent.multi_model import presupuesto as presup
from agent.multi_model import providers as prov
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

    def test_proveedor_para_modelo_desconocido(self, monkeypatch):
        forzar_proveedor(None)
        monkeypatch.setenv("DONA_MULTI_MODEL_ENABLED", "true")
        with pytest.raises(ValueError):
            prov.proveedor_para("no-existe", permitir_real=True)


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


# ═══════════════════ Riesgos de PR #306 / issue #310 ═══════════════════
#
# Tres riesgos señalados sobre F23 ya fusionado en main:
#   1. El flag no frena de verdad las llamadas reales.
#   2. Faltan timeouts y fallback al proveedor de RESPALDO del catálogo.
#   3. Los costos no tienen tope (presupuesto por agente).
# Todo con mocks / proveedor simulado — 0 USD, sin red.


# ───────────────────── Riesgo 1: flag fail-closed por defecto ─────────────

class TestRiesgo1FlagFailClosed:
    def test_proveedor_para_default_es_fail_closed(self, monkeypatch):
        """Un caller que olvide pasar `permitir_real` NUNCA obtiene un
        proveedor real, aunque el flag esté encendido: el default del
        parámetro es False (antes era True → fail-open)."""
        forzar_proveedor(None)
        monkeypatch.setenv("DONA_MULTI_MODEL_ENABLED", "true")
        p = prov.proveedor_para("gpt-4o")  # sin permitir_real explícito
        assert isinstance(p, ProveedorSimulado)

    def test_proveedor_para_permitir_real_no_pisa_flag_apagado(self, monkeypatch):
        """Defensa en profundidad: aunque un caller pase permitir_real=True
        por error, si el flag de verdad está apagado, sigue devolviendo el
        proveedor simulado — nunca sale una llamada real."""
        forzar_proveedor(None)
        monkeypatch.delenv("DONA_MULTI_MODEL_ENABLED", raising=False)
        p = prov.proveedor_para("gpt-4o", permitir_real=True)
        assert isinstance(p, ProveedorSimulado)

    async def test_flag_apagado_ninguna_llamada_real_en_combinacion(self, monkeypatch):
        """Con el flag apagado, ni planificar_y_ejecutar ni comparar_lado_a_lado
        disparan jamás un proveedor real (sin forzar_proveedor de por medio) —
        la ruta completa de F23 cae siempre al simulado."""
        monkeypatch.delenv("DONA_MULTI_MODEL_ENABLED", raising=False)
        forzar_proveedor(None)
        res = await combinacion.comparar_lado_a_lado(
            modelos=["gpt-4o", "claude-sonnet-4-5"],
            mensajes=[{"role": "user", "content": "x"}],
        )
        assert all(r.texto.startswith("[") for r in res.respuestas)  # marca simulada
        assert len(res.respuestas) == 2


# ───────────────────── Riesgo 2: fallback al respaldo del catálogo ────────

class TestRiesgo2FallbackCatalogo:
    def test_catalogo_declara_respaldo_de_otro_proveedor(self):
        sonnet = catalogo.info_modelo("claude-sonnet-4-5")
        gpt = catalogo.info_modelo("gpt-4o")
        assert sonnet.respaldo == "gpt-4o"
        assert gpt.respaldo == "claude-sonnet-4-5"
        # El respaldo es de un PROVEEDOR distinto (resiliencia real).
        assert catalogo.info_modelo(sonnet.respaldo).proveedor != sonnet.proveedor
        assert catalogo.info_modelo(gpt.respaldo).proveedor != gpt.proveedor

    async def test_generar_usa_respaldo_del_catalogo_no_siempre_default(self, _flag_on):
        # Haiku falla → su respaldo de catálogo es gpt-4o (NO el modelo por
        # defecto, que es claude-sonnet-4-5): el fallback debe ir a gpt-4o.
        forzar_proveedor(_ProveedorFalla("claude-haiku-4-5-20251001"))
        r = await seleccion.generar(
            modelo="claude-haiku-4-5-20251001",
            mensajes=[{"role": "user", "content": "x"}],
        )
        assert r.modelo == "gpt-4o"
        assert r.modelo != seleccion.MODELO_POR_DEFECTO

    async def test_generar_default_falla_usa_su_propio_respaldo(self, _flag_on):
        # El modelo por defecto (claude-sonnet-4-5) también tiene respaldo
        # propio en el catálogo (gpt-4o) — no se queda sin red de seguridad
        # por ser "el default".
        forzar_proveedor(_ProveedorFalla("claude-sonnet-4-5"))
        r = await seleccion.generar(
            modelo="claude-sonnet-4-5",
            mensajes=[{"role": "user", "content": "x"}],
        )
        assert r.modelo == "gpt-4o"

    async def test_sin_respaldo_disponible_propaga(self, _flag_on):
        # Si el proveedor forzado falla para AMBOS (el modelo pedido y su
        # respaldo), no hay una tercera alternativa: se propaga el error en
        # vez de reintentar indefinidamente (reintentos acotados a un salto).
        class _FallaTodo(ProveedorSimulado):
            async def generar(self, *, modelo, mensajes, system="", max_tokens=1024, **kw):
                raise RuntimeError(f"boom:{modelo}")

        forzar_proveedor(_FallaTodo())
        with pytest.raises(RuntimeError):
            await seleccion.generar(
                modelo="claude-haiku-4-5-20251001",
                mensajes=[{"role": "user", "content": "x"}],
            )

    def test_timeout_configurable_por_env(self, monkeypatch):
        monkeypatch.setenv("DONA_MODEL_TIMEOUT_S", "5")
        monkeypatch.setenv("DONA_MODEL_MAX_RETRIES", "1")
        importlib.reload(prov)
        assert prov.TIMEOUT_SEGUNDOS == 5.0
        assert prov.MAX_REINTENTOS == 1
        importlib.reload(prov)  # restaura defaults para el resto de la suite


# ───────────────────── Riesgo 3: presupuesto por agente (80% / 100%) ──────


@pytest.fixture(autouse=True)
def _presupuesto_limpio():
    presup.reiniciar_estado()
    yield
    presup.reiniciar_estado()


class TestRiesgo3PresupuestoAgente:
    def test_sin_agente_no_se_gatea(self):
        """Compat: si no se pasa `agente`, esta dimensión no aplica (no rompe
        a los callers existentes de F23 que todavía no declaran agente)."""
        presup.verificar_presupuesto("")  # no lanza
        presup.registrar_gasto("", 999.0)
        assert presup.gasto_diario_de("") == 0.0

    def test_avisa_al_80_por_ciento(self, monkeypatch, caplog):
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "1.0")
        with caplog.at_level(logging.WARNING, logger="dona"):
            presup.registrar_gasto("ventas", 0.5)
            assert not any("al 80%" in r.message or "80%" in r.message for r in caplog.records)
            presup.registrar_gasto("ventas", 0.35)  # acumulado 0.85 → cruza 80%
        avisos = [r for r in caplog.records if "presupuesto del agente" in r.message]
        assert len(avisos) == 1
        assert "80%" in avisos[0].message or "85%" in avisos[0].message

    def test_avisa_una_sola_vez_por_dia(self, monkeypatch, caplog):
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "1.0")
        with caplog.at_level(logging.WARNING, logger="dona"):
            presup.registrar_gasto("ventas", 0.9)
            presup.registrar_gasto("ventas", 0.05)
            presup.registrar_gasto("ventas", 0.01)
        avisos = [r for r in caplog.records if "presupuesto del agente" in r.message]
        assert len(avisos) == 1

    def test_bloquea_al_100_por_ciento(self, monkeypatch):
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "1.0")
        presup.registrar_gasto("soporte", 1.0)
        with pytest.raises(presup.PresupuestoAgenteAgotadoError) as exc:
            presup.verificar_presupuesto("soporte")
        assert exc.value.agente == "soporte"
        assert exc.value.gastado == pytest.approx(1.0)
        assert exc.value.limite == pytest.approx(1.0)

    def test_agentes_distintos_no_comparten_presupuesto(self, monkeypatch):
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "1.0")
        presup.registrar_gasto("ventas", 1.0)
        presup.verificar_presupuesto("soporte")  # no lanza: presupuesto propio

    def test_limite_invalido_cae_a_default_fail_closed(self, monkeypatch):
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "no-es-numero")
        assert presup.limite_usd_dia_agente() == presup.LIMITE_USD_DIA_AGENTE_DEFAULT
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "-5")
        assert presup.limite_usd_dia_agente() == presup.LIMITE_USD_DIA_AGENTE_DEFAULT

    async def test_generar_bloquea_sin_llamar_al_proveedor(self, monkeypatch, _flag_on):
        """Al 100% del tope, generar() lanza SIN llamar a ningún proveedor
        (ni el primario ni el respaldo) — se verifica ANTES de la llamada."""
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "1.0")
        presup.registrar_gasto("ventas", 1.0)

        contador = {"n": 0}

        class _ContadorProveedor(ProveedorSimulado):
            async def generar(self, **kw):
                contador["n"] += 1
                return await super().generar(**kw)

        forzar_proveedor(_ContadorProveedor())
        with pytest.raises(presup.PresupuestoAgenteAgotadoError):
            await seleccion.generar(
                modelo="gpt-4o",
                mensajes=[{"role": "user", "content": "x"}],
                agente="ventas",
            )
        assert contador["n"] == 0

    async def test_generar_bajo_el_tope_registra_gasto_del_agente(self, monkeypatch, _flag_on):
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "10.0")
        r = await seleccion.generar(
            modelo="gpt-4o",
            mensajes=[{"role": "user", "content": "hola"}],
            agente="ventas",
        )
        assert r.costo_usd is not None
        assert presup.gasto_diario_de("ventas") == pytest.approx(float(r.costo_usd))

    async def test_comparacion_se_detiene_al_agotar_presupuesto_de_agente(self, monkeypatch):
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "0.000001")
        res = await combinacion.comparar_lado_a_lado(
            modelos=["gpt-4o", "claude-sonnet-4-5"],
            mensajes=[{"role": "user", "content": "x"}],
            agente="ventas",
        )
        # El tope diminuto se agota en la primera llamada; la comparación se
        # detiene sin propagar la excepción (API estable para el caller).
        assert len(res.respuestas) <= 1

    async def test_plan_se_detiene_al_agotar_presupuesto_de_agente(self, monkeypatch):
        monkeypatch.setenv("DONA_PRESUPUESTO_AGENTE_USD_DIA", "0.000001")
        res = await combinacion.planificar_y_ejecutar(
            modelo_plan="claude-sonnet-4-5",
            modelo_exec="gpt-4o",
            mensajes=[{"role": "user", "content": "organiza mi semana"}],
            agente="ventas",
        )
        assert "presupuesto de agente agotado" in res.pasos[-1].texto
