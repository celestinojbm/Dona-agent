# tests/test_internal_reportes.py — Reportes/Medición web (Fase 1)
# Funciones reporting.resumen_*_datos + endpoint POST /internal/reportes.

"""
Cubre el vertical slice de Reportes web:

reporting.resumen_mes_datos / resumen_semana_datos:
  - Agregación correcta con datos sembrados (ventas, gastos, utilidad,
    pedidos, top categorías) aislada por telefono.
  - Sin datos → hay_datos=False y ceros.
  - Comparación vs. semana previa (delta_ventas_pct) presente/ausente.
  - Que NO rompan los strings de WhatsApp (resumen_mes / resumen_semana
    siguen devolviendo su texto con los mismos números).

Endpoint POST /internal/reportes:
  - Firma HMAC inválida o ausente → 401.
  - JSON malformado / no objeto → 400.
  - Body sin subscription_id → 400.
  - subscription_id no existe → 404.
  - periodo mes/semana/desconocido.
  - IDOR: un subscription_id NO ve los datos de otro telefono.

NO cubre:
  - Bridge landing → backend (se prueba en landing/lib/reportes-bridge.test.ts).
  - UI del dashboard (se prueba en landing/app/dashboard/seccion-reportes.test.tsx).
"""

import hashlib
import hmac
import importlib
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:
    _main_disponible = False


_requiere_main = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler (no instalado en este entorno)",
)


SECRET_TEST = "test-secret-not-real-reportes"


def _firmar(body: bytes, secret: str = SECRET_TEST) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _body(**kwargs) -> bytes:
    return json.dumps(kwargs).encode("utf-8")


def _post(client, body: bytes, firma: str | None = None):
    return client.post(
        "/internal/reportes",
        content=body,
        headers={"X-Internal-Signature": firma if firma is not None else _firmar(body)},
    )


# ── Fixture: backend con DB aislada y env vars ─────────────────────────────
#
# Cadena de reload canónica (ver test_automation_perfil_estado.py): recargar
# agent.memory crea un Base nuevo; hay que recargar agent.business.models
# (para re-registrar Transaccion/Pedido en ese Base) y agent.reporting (para
# que apunte a los modelos recargados) ANTES de inicializar_db(), o create_all
# no crea las tablas de negocio.


@pytest.fixture
async def setup(tmp_path, monkeypatch):
    db_path = tmp_path / "reportes.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)

    import agent.business.models as _bm
    import agent.memory
    import agent.reporting as _rep
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_rep)

    await agent.memory.inicializar_db()

    from agent.main import app
    return TestClient(app), agent.memory, _rep


async def _crear_sub(memory, subscription_id, telefono):
    async with memory.async_session() as session:
        session.add(memory.SuscripcionStripe(
            subscription_id=subscription_id,
            telefono=telefono,
            customer_id="cus_reportes",
            plan_codigo="premium",
            price_id="price_test",
            status="active",
            creditos_mensuales=100,
        ))
        await session.commit()


async def _crear_tx(memory, telefono, tipo, monto, categoria="general", fecha=None):
    from agent.business.models import Transaccion
    async with memory.async_session() as session:
        session.add(Transaccion(
            telefono=telefono,
            tipo=tipo,
            monto=monto,
            categoria=categoria,
            descripcion="",
            fecha=fecha or datetime.utcnow(),
        ))
        await session.commit()


async def _crear_pedido(memory, telefono, estado="pendiente", creado=None):
    from agent.business.models import Pedido
    async with memory.async_session() as session:
        session.add(Pedido(
            telefono=telefono,
            cliente_nombre="X",
            descripcion="",
            monto=0.0,
            estado=estado,
            creado=creado or datetime.utcnow(),
        ))
        await session.commit()


# ══════════════════════════════════════════════════════════════════════════
# Parte 1 · reporting.resumen_*_datos (agregación pura, sin HTTP)
# ══════════════════════════════════════════════════════════════════════════


class TestResumenMesDatos:
    @pytest.mark.asyncio
    async def test_agrega_ventas_gastos_utilidad_y_categorias(self, setup):
        _, memory, reporting = setup
        tel = "15550001111"
        ahora = datetime.utcnow()
        await _crear_tx(memory, tel, "venta", 100.0, fecha=ahora)
        await _crear_tx(memory, tel, "venta", 50.0, fecha=ahora)
        await _crear_tx(memory, tel, "gasto", 30.0, categoria="insumos", fecha=ahora)
        await _crear_tx(memory, tel, "gasto", 20.0, categoria="renta", fecha=ahora)
        await _crear_pedido(memory, tel, creado=ahora)

        d = await reporting.resumen_mes_datos(tel, ahora.year, ahora.month)
        assert d["periodo"] == "mes"
        assert d["ventas"] == 150.0
        assert d["gastos"] == 50.0
        assert d["utilidad"] == 100.0
        assert d["num_pedidos"] == 1
        assert d["num_transacciones"] == 4
        assert d["hay_datos"] is True
        # Top categorías: insumos (30) por encima de renta (20)
        cats = d["top_categorias"]
        assert cats[0] == {"categoria": "insumos", "total": 30.0}
        assert {"categoria": "renta", "total": 20.0} in cats
        # Serializable: sin telefono ni objetos crudos
        json.dumps(d)
        assert "telefono" not in d

    @pytest.mark.asyncio
    async def test_sin_datos_hay_datos_false_y_ceros(self, setup):
        _, memory, reporting = setup
        d = await reporting.resumen_mes_datos("15550002222")
        assert d["hay_datos"] is False
        assert d["ventas"] == 0
        assert d["gastos"] == 0
        assert d["utilidad"] == 0
        assert d["num_pedidos"] == 0
        assert d["top_categorias"] == []

    @pytest.mark.asyncio
    async def test_aislamiento_por_telefono(self, setup):
        _, memory, reporting = setup
        ahora = datetime.utcnow()
        await _crear_tx(memory, "15550003333", "venta", 999.0, fecha=ahora)
        # Otro teléfono no ve la venta anterior
        d = await reporting.resumen_mes_datos("15550004444", ahora.year, ahora.month)
        assert d["ventas"] == 0
        assert d["hay_datos"] is False


class TestResumenSemanaDatos:
    @pytest.mark.asyncio
    async def test_agrega_y_estados_de_pedidos(self, setup):
        _, memory, reporting = setup
        tel = "15550005555"
        await _crear_tx(memory, tel, "venta", 200.0)
        await _crear_tx(memory, tel, "gasto", 80.0, categoria="publicidad")
        await _crear_pedido(memory, tel, estado="entregado")
        await _crear_pedido(memory, tel, estado="pendiente")

        d = await reporting.resumen_semana_datos(tel)
        assert d["periodo"] == "semana"
        assert d["ventas"] == 200.0
        assert d["gastos"] == 80.0
        assert d["utilidad"] == 120.0
        assert d["num_pedidos"] == 2
        assert d["pedidos_entregados"] == 1
        assert d["pedidos_pendientes"] == 1
        assert d["hay_datos"] is True
        json.dumps(d)

    @pytest.mark.asyncio
    async def test_comparacion_semana_previa_presente(self, setup):
        _, memory, reporting = setup
        from datetime import timedelta
        tel = "15550006666"
        ahora = datetime.utcnow()
        # Semana actual: 200 en ventas
        await _crear_tx(memory, tel, "venta", 200.0, fecha=ahora - timedelta(days=1))
        # Semana previa: 100 en ventas (hace ~10 días)
        await _crear_tx(memory, tel, "venta", 100.0, fecha=ahora - timedelta(days=10))

        d = await reporting.resumen_semana_datos(tel)
        comp = d["comparacion_semana_previa"]
        assert comp is not None
        # 200 vs 100 → +100%
        assert comp["delta_ventas_pct"] == 100.0

    @pytest.mark.asyncio
    async def test_sin_semana_previa_comparacion_null(self, setup):
        _, memory, reporting = setup
        tel = "15550007777"
        await _crear_tx(memory, tel, "venta", 200.0)
        d = await reporting.resumen_semana_datos(tel)
        assert d["comparacion_semana_previa"] is None


class TestNoRompeWhatsApp:
    """Los strings de WhatsApp deben seguir devolviendo texto con los mismos
    números tras el refactor a helpers compartidos."""

    @pytest.mark.asyncio
    async def test_resumen_mes_sigue_siendo_string(self, setup):
        _, memory, reporting = setup
        tel = "15550008888"
        ahora = datetime.utcnow()
        await _crear_tx(memory, tel, "venta", 150.0, fecha=ahora)
        s = await reporting.resumen_mes(tel, ahora.year, ahora.month)
        assert isinstance(s, str)
        assert "Resumen de" in s
        assert "150" in s  # el monto aparece formateado

    @pytest.mark.asyncio
    async def test_resumen_semana_vacio_sigue_string_vacio(self, setup):
        _, memory, reporting = setup
        # Sin movimientos → string vacío (contrato del weekly recap)
        s = await reporting.resumen_semana("15550009999")
        assert s == ""

    @pytest.mark.asyncio
    async def test_string_y_datos_coinciden_en_numeros(self, setup):
        _, memory, reporting = setup
        tel = "15550010000"
        ahora = datetime.utcnow()
        await _crear_tx(memory, tel, "venta", 300.0, fecha=ahora)
        await _crear_tx(memory, tel, "gasto", 100.0, fecha=ahora)
        s = await reporting.resumen_mes(tel, ahora.year, ahora.month)
        d = await reporting.resumen_mes_datos(tel, ahora.year, ahora.month)
        assert d["ventas"] == 300.0
        assert d["utilidad"] == 200.0
        # El string debe contener los mismos totales
        assert "300" in s
        assert "200" in s

    @pytest.mark.asyncio
    async def test_resumen_semana_string_con_pedidos_y_comparacion(self, setup):
        """El string semanal de WhatsApp incluye la línea de pedidos
        (entregados/en curso), transacciones y la comparación vs. semana
        previa cuando hay datos suficientes."""
        from datetime import timedelta
        _, memory, reporting = setup
        tel = "15550011111"
        ahora = datetime.utcnow()
        await _crear_tx(memory, tel, "venta", 400.0, fecha=ahora - timedelta(days=1))
        await _crear_tx(memory, tel, "venta", 200.0, fecha=ahora - timedelta(days=10))
        await _crear_pedido(memory, tel, estado="entregado",
                            creado=ahora - timedelta(days=1))
        await _crear_pedido(memory, tel, estado="pendiente",
                            creado=ahora - timedelta(days=1))
        s = await reporting.resumen_semana(tel)
        assert "Pedidos" in s
        assert "entregados" in s
        assert "Transacciones" in s
        # 400 vs 200 → +100.0% en ventas
        assert "semana pasada" in s
        assert "100.0%" in s


# ══════════════════════════════════════════════════════════════════════════
# Parte 2 · endpoint POST /internal/reportes
# ══════════════════════════════════════════════════════════════════════════


@_requiere_main
class TestAuth:
    def test_sin_header_401(self, setup):
        client, _, _ = setup
        r = client.post("/internal/reportes", content=_body(subscription_id="s"))
        assert r.status_code == 401

    def test_firma_invalida_401(self, setup):
        client, _, _ = setup
        r = _post(client, _body(subscription_id="s"), firma="deadbeef")
        assert r.status_code == 401

    def test_firma_de_otro_secret_401(self, setup):
        client, _, _ = setup
        body = _body(subscription_id="s")
        r = _post(client, body, firma=_firmar(body, secret="atacante"))
        assert r.status_code == 401

    def test_body_modificado_tras_firmar_401(self, setup):
        client, _, _ = setup
        firma = _firmar(_body(subscription_id="sub_original"))
        r = _post(client, _body(subscription_id="sub_atacante"), firma=firma)
        assert r.status_code == 401


@_requiere_main
class TestPayload:
    def test_no_json_400(self, setup):
        client, _, _ = setup
        body = b"no soy json"
        r = _post(client, body, firma=_firmar(body))
        assert r.status_code == 400

    def test_array_no_objeto_400(self, setup):
        client, _, _ = setup
        body = json.dumps([1, 2]).encode("utf-8")
        r = _post(client, body, firma=_firmar(body))
        assert r.status_code == 400

    def test_sin_subscription_id_400(self, setup):
        client, _, _ = setup
        r = _post(client, _body(otro="x"))
        assert r.status_code == 400
        assert "missing_subscription_id" in r.json().get("detail", "")

    def test_subscription_id_vacio_400(self, setup):
        client, _, _ = setup
        r = _post(client, _body(subscription_id="   "))
        assert r.status_code == 400


@_requiere_main
class TestSubInexistente:
    def test_sub_inexistente_404(self, setup):
        client, _, _ = setup
        r = _post(client, _body(subscription_id="sub_nunca"))
        assert r.status_code == 404
        assert "subscription_no_persistida" in r.json().get("detail", "")


@_requiere_main
class TestPeriodo:
    @pytest.mark.asyncio
    async def test_default_es_mes(self, setup):
        client, memory, _ = setup
        await _crear_sub(memory, "sub_mes", "15551110000")
        r = _post(client, _body(subscription_id="sub_mes"))
        assert r.status_code == 200
        rep = r.json()["reporte"]
        assert rep["periodo"] == "mes"
        assert rep["hay_datos"] is False

    @pytest.mark.asyncio
    async def test_periodo_semana(self, setup):
        client, memory, _ = setup
        await _crear_sub(memory, "sub_sem", "15551110001")
        r = _post(client, _body(subscription_id="sub_sem", periodo="semana"))
        assert r.status_code == 200
        rep = r.json()["reporte"]
        assert rep["periodo"] == "semana"

    @pytest.mark.asyncio
    async def test_periodo_desconocido_cae_a_mes(self, setup):
        client, memory, _ = setup
        await _crear_sub(memory, "sub_raro", "15551110002")
        r = _post(client, _body(subscription_id="sub_raro", periodo="anual"))
        assert r.status_code == 200
        assert r.json()["reporte"]["periodo"] == "mes"

    @pytest.mark.asyncio
    async def test_con_datos_devuelve_numeros(self, setup):
        client, memory, _ = setup
        tel = "15551110003"
        await _crear_sub(memory, "sub_datos", tel)
        ahora = datetime.utcnow()
        await _crear_tx(memory, tel, "venta", 500.0, fecha=ahora)
        await _crear_tx(memory, tel, "gasto", 200.0, categoria="insumos", fecha=ahora)
        r = _post(client, _body(subscription_id="sub_datos"))
        assert r.status_code == 200
        rep = r.json()["reporte"]
        assert rep["ventas"] == 500.0
        assert rep["gastos"] == 200.0
        assert rep["utilidad"] == 300.0
        assert rep["hay_datos"] is True
        # No expone PII
        assert tel not in r.text


@_requiere_main
class TestIDOR:
    @pytest.mark.asyncio
    async def test_sub_no_ve_datos_de_otro_telefono(self, setup):
        """sub_a (telefono A) NO debe ver los datos de negocio de telefono B,
        aunque firme correctamente. El backend resuelve telefono desde la sub."""
        client, memory, _ = setup
        await _crear_sub(memory, "sub_a", "15551110001")
        await _crear_sub(memory, "sub_b", "15551110002")
        ahora = datetime.utcnow()
        # Ventas SÓLO de B
        await _crear_tx(memory, "15551110002", "venta", 9999.0, fecha=ahora)
        await _crear_tx(memory, "15551110002", "gasto", 1234.0,
                        categoria="secreto-b", fecha=ahora)

        # A pide su reporte → ceros, y no ve nada de B
        r = _post(client, _body(subscription_id="sub_a"))
        assert r.status_code == 200
        rep = r.json()["reporte"]
        assert rep["ventas"] == 0
        assert rep["gastos"] == 0
        assert rep["hay_datos"] is False
        assert "secreto-b" not in r.text
        assert "9999" not in r.text

        # B sí ve los suyos (control positivo)
        r2 = _post(client, _body(subscription_id="sub_b"))
        assert r2.status_code == 200
        assert r2.json()["reporte"]["ventas"] == 9999.0


@_requiere_main
class TestReadOnly:
    @pytest.mark.asyncio
    async def test_no_modifica_db(self, setup):
        from sqlalchemy import func, select

        from agent.business.models import Transaccion
        client, memory, _ = setup
        tel = "15551119999"
        await _crear_sub(memory, "sub_ro", tel)
        await _crear_tx(memory, tel, "venta", 10.0)

        async def _contar():
            async with memory.async_session() as session:
                return (await session.execute(
                    select(func.count()).select_from(Transaccion)
                )).scalar_one()

        antes = await _contar()
        for _ in range(3):
            assert _post(client, _body(subscription_id="sub_ro")).status_code == 200
        assert await _contar() == antes
