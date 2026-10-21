"""Tests de F3 — recibo por acción.

Cubre, con SQLite aislado + mocks (sin proveedores facturables):
- débito idempotente por idempotency_key (reentrega/retry no duplica);
- recibo y saldo atómicos (saldo_posterior == saldo_resultante del mismo commit);
- recibo ajeno/inexistente → no se revela;
- último recibo;
- desglose versionado con dinero como string (nunca float);
- comandos "recibo <id>" / "último recibo";
- flag de exposición;
- uso por proveedor idempotente;
- saldo insuficiente no deja recibo.

La concurrencia real requiere PostgreSQL aislado; aquí el invariante de "un solo
débito" se prueba vía el índice UNIQUE (que protege aun si dos commits corren).
"""

import asyncio
import importlib

import pytest

import agent.memory
import agent.billing
from agent import recibos


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "recibos.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)
    await agent.memory.inicializar_db()
    return agent.billing


# ───────────────────── Idempotencia del débito ─────────────────────

class TestDebitoIdempotente:
    async def test_misma_key_no_duplica_debito(self, db):
        await db.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        n1 = await db.cobrar("5551", 30, "generar_imagen", idempotency_key="acc-1")
        n2 = await db.cobrar("5551", 30, "generar_imagen", idempotency_key="acc-1")
        assert n1 == 70
        assert n2 == 70  # reentrega/retry: mismo saldo, sin re-débito
        assert await db.obtener_saldo("5551") == 70

    async def test_keys_distintas_cobran_cada_una(self, db):
        await db.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        await db.cobrar("5551", 30, "a", idempotency_key="k1")
        n = await db.cobrar("5551", 20, "b", idempotency_key="k2")
        assert n == 50

    async def test_sin_key_cobra_cada_vez(self, db):
        await db.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        await db.cobrar("5551", 10, "a")
        n = await db.cobrar("5551", 10, "a")
        assert n == 80

    async def test_misma_key_concurrente_un_solo_debito(self, db):
        await db.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        res = await asyncio.gather(
            db.cobrar("5551", 40, "x", idempotency_key="race"),
            db.cobrar("5551", 40, "x", idempotency_key="race"),
            return_exceptions=True,
        )
        # Al menos uno tuvo éxito; el UNIQUE garantiza un solo débito real.
        assert await db.obtener_saldo("5551") == 60
        # Ningún resultado numérico puede ser < 60 (no hubo doble débito).
        numericos = [r for r in res if isinstance(r, int)]
        assert all(r == 60 for r in numericos)


# ───────────────────── Recibo atómico + lectura ─────────────────────

class TestReciboLectura:
    async def test_desglose_y_saldo_atomicos(self, db):
        await db.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        desg = recibos.construir_desglose(
            accion="generar_imagen",
            version_tarifa="2026-10",
            proveedores=[
                recibos.linea_proveedor(
                    proveedor="gemini", modelo="2.5-flash",
                    coste_base="0.002", estado="estimado",
                )
            ],
            creditos_cobrados=30,
            saldo_posterior=70,
            estado="estimado",
            margen="0.01",
        )
        await db.cobrar(
            "5551", 30, "generar_imagen",
            idempotency_key="acc-9", accion_ref="job-9", desglose=desg,
        )
        recibo = await db.ultimo_recibo("5551")
        assert recibo is not None
        assert recibo["accion_ref"] == "job-9"
        assert recibo["saldo_resultante"] == 70
        # saldo_posterior del desglose == saldo_resultante del mismo commit
        assert recibo["desglose"]["saldo_posterior"] == 70
        assert recibo["desglose"]["proveedores"][0]["proveedor"] == "gemini"

    async def test_recibo_ajeno_no_se_revela(self, db):
        await db.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        await db.cobrar("5551", 30, "a", idempotency_key="k1", accion_ref="j1")
        rec = await db.ultimo_recibo("5551")
        tx_id = rec["id"]
        # Otro teléfono pide ese id → None (no revela)
        assert await db.obtener_recibo("9999", tx_id) is None
        # El dueño sí lo ve
        assert await db.obtener_recibo("5551", tx_id) is not None

    async def test_recibo_inexistente_none(self, db):
        assert await db.obtener_recibo("5551", 123456) is None
        assert await db.ultimo_recibo("5551") is None

    async def test_saldo_insuficiente_no_deja_recibo(self, db):
        await db.acreditar("5551", 10, "inicial", stripe_session_id="s1")
        with pytest.raises(db.SaldoInsuficienteError):
            await db.cobrar("5551", 50, "cara", idempotency_key="k1", accion_ref="j1")
        assert await db.ultimo_recibo("5551") is None


# ───────────────────── Uso por proveedor ─────────────────────

class TestUsoProveedor:
    async def test_registrar_uso_idempotente(self, db):
        await db.registrar_uso_proveedor(
            "5551", "job-1", "gemini", modelo="2.5", intento=1, estado="observado"
        )
        # Mismo (accion_ref, proveedor, intento) → no duplica
        await db.registrar_uso_proveedor(
            "5551", "job-1", "gemini", modelo="2.5", intento=1, estado="observado"
        )
        from sqlalchemy import func, select
        from agent.memory import UsoProveedorAccion, async_session
        async with async_session() as s:
            total = (await s.execute(
                select(func.count()).select_from(UsoProveedorAccion)
                .where(UsoProveedorAccion.accion_ref == "job-1")
            )).scalar_one()
        assert total == 1


# ───────────────────── Desglose / dinero como string ─────────────────────

class TestDesglose:
    def test_dinero_es_string_nunca_float(self):
        linea = recibos.linea_proveedor(proveedor="anthropic", coste_base=0.0123)
        assert isinstance(linea["coste_base"], str)
        desg = recibos.construir_desglose(
            accion="x", version_tarifa="v1", proveedores=[linea],
            creditos_cobrados=5, saldo_posterior=5, estado="estimado",
            margen=0.5, coste_base_total=0.75,
        )
        assert desg["version"] == recibos.VERSION_DESGLOSE
        assert isinstance(desg["margen"], str)
        assert isinstance(desg["coste_base_total"], str)
        assert desg["creditos_cobrados"] == 5  # entero
        # Ningún valor de dinero quedó como float
        assert not isinstance(desg["margen"], float)

    def test_estado_invalido_se_normaliza(self):
        desg = recibos.construir_desglose(
            accion="x", version_tarifa="v1", proveedores=[],
            creditos_cobrados=1, saldo_posterior=1, estado="raro",
        )
        assert desg["estado"] == "estimado"


# ───────────────────── Comandos / flag / formato ─────────────────────

class TestComandos:
    def test_parse_recibo_id(self):
        assert recibos.es_comando_recibo("recibo 42") == ("id", 42)
        assert recibos.es_comando_recibo("dona recibo #7") == ("id", 7)

    def test_parse_ultimo(self):
        assert recibos.es_comando_recibo("último recibo") == ("ultimo", None)
        assert recibos.es_comando_recibo("recibo") == ("ultimo", None)

    def test_no_comando(self):
        assert recibos.es_comando_recibo("hola") is None
        assert recibos.es_comando_recibo("recibo abc") is None

    def test_flag_apagado_por_defecto(self, monkeypatch):
        monkeypatch.delenv("DONA_CREDIT_RECEIPTS_ENABLED", raising=False)
        assert recibos.recibos_habilitado() is False
        monkeypatch.setenv("DONA_CREDIT_RECEIPTS_ENABLED", "true")
        assert recibos.recibos_habilitado() is True

    def test_formato_incluye_campos_clave(self):
        tx = {
            "id": 5,
            "delta": -30,
            "razon": "generar_imagen",
            "accion_ref": "job-5",
            "saldo_resultante": 70,
            "creado": "2026-10-20T00:00:00",
            "desglose": {
                "accion": "generar_imagen",
                "creditos_cobrados": 30,
                "saldo_posterior": 70,
                "proveedores": [
                    {"proveedor": "gemini", "modelo": "2.5", "estado": "observado",
                     "coste_base": "0.002", "moneda": "USD"},
                ],
            },
        }
        txt = recibos.formatear_recibo(tx)
        assert "Recibo #5" in txt
        assert "generar_imagen" in txt
        assert "gemini" in txt
        assert "observado" in txt
        assert "No es una factura fiscal" in txt


# ─────────── Respuestas de Celestino: tarifa, desglose por paso, retención ───────────

class TestTarifa:
    def test_margen_30_pct(self):
        from decimal import Decimal
        from agent import tarifa
        assert tarifa.aplicar_margen("1.00") == Decimal("1.30")
        assert tarifa.margen_str() == "0.30"

    def test_creditos_redondeo_hacia_arriba(self):
        from agent import tarifa
        # coste 1.00 + 30% = 1.30 ; con valor_credito 1.00 → ceil(1.30) = 2
        assert tarifa.creditos_por_costo("1.00", valor_credito_usd="1.00") == 2
        # coste 0.10 + 30% = 0.13 ; valor 1.00 → ceil(0.13) = 1
        assert tarifa.creditos_por_costo("0.10", valor_credito_usd="1.00") == 1

    def test_valor_credito_desde_env(self, monkeypatch):
        from agent import tarifa
        monkeypatch.setenv("DONA_VALOR_CREDITO_USD", "0.50")
        # 1.00 + 30% = 1.30 ; /0.50 = 2.6 → ceil = 3
        assert tarifa.creditos_por_costo("1.00") == 3

    def test_sin_valor_credito_lanza(self, monkeypatch):
        import pytest as _pytest
        from agent import tarifa
        monkeypatch.delenv("DONA_VALOR_CREDITO_USD", raising=False)
        with _pytest.raises(ValueError):
            tarifa.creditos_por_costo("1.00")


class TestDesgloseCelestino:
    def test_margen_y_version_por_defecto(self):
        from agent import tarifa
        desg = recibos.construir_desglose(
            accion="x", proveedores=[], creditos_cobrados=2, saldo_posterior=8,
            estado="observado",
        )
        assert desg["margen"] == "0.30"  # 30% por defecto
        assert desg["version_tarifa"] == tarifa.VERSION_TARIFA

    def test_desglose_por_paso(self):
        pasos = [
            recibos.linea_paso(nombre="Buscar leads", creditos=1, estado="completado"),
            recibos.linea_paso(nombre="Redactar", creditos=1, estado="completado"),
        ]
        desg = recibos.construir_desglose(
            accion="seguimiento", proveedores=[], pasos=pasos,
            creditos_cobrados=2, saldo_posterior=8, estado="observado",
        )
        assert len(desg["pasos"]) == 2
        tx = {"id": 7, "delta": -2, "saldo_resultante": 8, "desglose": desg}
        txt = recibos.formatear_recibo(tx)
        assert "Por paso" in txt
        assert "Buscar leads" in txt


class TestRetencion:
    async def test_purga_uso_proveedor_90_dias(self, db):
        from datetime import datetime, timedelta
        from sqlalchemy import update
        from agent.memory import UsoProveedorAccion, async_session
        # Fila reciente y fila vieja (100 días)
        await db.registrar_uso_proveedor("5551", "job-new", "gemini", intento=1)
        await db.registrar_uso_proveedor("5551", "job-old", "gemini", intento=1)
        async with async_session() as s:
            await s.execute(
                update(UsoProveedorAccion)
                .where(UsoProveedorAccion.accion_ref == "job-old")
                .values(creado=datetime.utcnow() - timedelta(days=100))
            )
            await s.commit()
        borradas = await db.purgar_uso_proveedor(dias=90)
        assert borradas == 1
        # La reciente sobrevive
        from sqlalchemy import func, select
        async with async_session() as s:
            quedan = (await s.execute(
                select(func.count()).select_from(UsoProveedorAccion)
            )).scalar_one()
        assert quedan == 1
