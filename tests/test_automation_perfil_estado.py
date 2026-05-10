# tests/test_automation_perfil_estado.py — hotfix perfil insuficiente

"""Verifica que el backend reporta correctamente el estado del perfil
y los endpoints incluyen los campos perfil_estado/razón/siguiente_paso
para que el dashboard pueda explicar al usuario por qué no se generan
acciones."""

import importlib
import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "ps.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    import agent.business.models as _bm
    import agent.automation.models as _am
    import agent.automation.audit as _au
    import agent.automation.action_center as _ac
    import agent.automation.opportunities as _op
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    importlib.reload(_au)
    importlib.reload(_ac)
    importlib.reload(_op)
    await agent.memory.inicializar_db()
    return _op


async def _crear_perfil(telefono: str, **kwargs):
    from agent.business.models import PerfilNegocio
    from datetime import datetime
    defaults = {
        "telefono": telefono,
        "nombre_negocio": "",
        "industria": "general",
        "moneda": "MXN",
        "meta_mensual": 0.0,
        "oferta_principal": "",
        "cliente_ideal": "",
        "objetivo_mes": "",
        "canales_actuales": "",
        "bloqueo_actual": "",
        "tareas_delegar": "",
        "creado": datetime.utcnow(),
        "actualizado": datetime.utcnow(),
        "onboarding_paso": None,
    }
    defaults.update(kwargs)
    async with agent.memory.async_session() as session:
        session.add(PerfilNegocio(**defaults))
        await session.commit()


# ─── analizar_estado_perfil (función pura) ────────────────────────────────


class TestAnalizarEstadoPerfil:
    def test_perfil_none_es_missing(self, db):
        r = db.analizar_estado_perfil(None)
        assert r["estado"] == "missing"
        assert r["campos_llenos"] == 0
        assert "WhatsApp" in r["siguiente_paso"]

    def test_perfil_sin_nombre_es_missing(self, db):
        r = db.analizar_estado_perfil({"nombre_negocio": ""})
        assert r["estado"] == "missing"

    def test_perfil_con_nombre_pero_sin_diagnostico_es_incomplete(self, db):
        r = db.analizar_estado_perfil({
            "nombre_negocio": "Mi Tienda",
        })
        assert r["estado"] == "incomplete"
        assert r["campos_llenos"] == 0
        assert "0 de 6" in r["razon"]

    def test_perfil_con_un_solo_campo_es_incomplete(self, db):
        r = db.analizar_estado_perfil({
            "nombre_negocio": "X",
            "oferta_principal": "Pasteles",
        })
        assert r["estado"] == "incomplete"
        assert r["campos_llenos"] == 1

    def test_perfil_con_2_campos_ya_es_ready(self, db):
        r = db.analizar_estado_perfil({
            "nombre_negocio": "X",
            "oferta_principal": "Pasteles",
            "cliente_ideal": "Familias",
        })
        assert r["estado"] == "ready"
        assert r["campos_llenos"] == 2

    def test_perfil_completo_es_ready(self, db):
        r = db.analizar_estado_perfil({
            "nombre_negocio": "X",
            "oferta_principal": "A",
            "cliente_ideal": "B",
            "objetivo_mes": "C",
            "canales_actuales": "D",
            "bloqueo_actual": "E",
            "tareas_delegar": "F",
        })
        assert r["estado"] == "ready"
        assert r["campos_llenos"] == 6


# ─── detectar_oportunidades_con_estado_para_telefono ──────────────────────


class TestDetectarConEstado:
    @pytest.mark.asyncio
    async def test_sin_perfil_devuelve_missing_y_lista_vacia(self, db):
        r = await db.detectar_oportunidades_con_estado_para_telefono("5550")
        assert r["perfil_estado"] == "missing"
        assert r["oportunidades"] == []
        assert r["perfil_siguiente_paso"]

    @pytest.mark.asyncio
    async def test_perfil_solo_con_nombre_devuelve_incomplete(self, db):
        await _crear_perfil("5551", nombre_negocio="Mi Negocio")
        r = await db.detectar_oportunidades_con_estado_para_telefono("5551")
        assert r["perfil_estado"] == "incomplete"
        assert r["oportunidades"] == []
        assert r["perfil_campos_llenos"] == 0

    @pytest.mark.asyncio
    async def test_perfil_completo_devuelve_ready_y_oportunidades(self, db):
        await _crear_perfil(
            "5552",
            nombre_negocio="Pastelería",
            oferta_principal="Pasteles",
            cliente_ideal="Familias en CDMX",
            objetivo_mes="10 ventas",
            canales_actuales="WhatsApp",
            bloqueo_actual="Tiempo",
            tareas_delegar="seguimiento clientes",
        )
        r = await db.detectar_oportunidades_con_estado_para_telefono("5552")
        assert r["perfil_estado"] == "ready"
        assert len(r["oportunidades"]) >= 4

    @pytest.mark.asyncio
    async def test_perfil_minimo_2_campos_es_ready(self, db):
        await _crear_perfil(
            "5553",
            nombre_negocio="X",
            oferta_principal="A",
            cliente_ideal="B",
        )
        r = await db.detectar_oportunidades_con_estado_para_telefono("5553")
        assert r["perfil_estado"] == "ready"


# ─── Retrocompatibilidad: detectar_oportunidades_para_telefono sigue ──────


class TestRetrocompat:
    @pytest.mark.asyncio
    async def test_sin_perfil_lista_vacia(self, db):
        r = await db.detectar_oportunidades_para_telefono("5560")
        assert r == []

    @pytest.mark.asyncio
    async def test_perfil_completo_genera_oportunidades(self, db):
        await _crear_perfil(
            "5561",
            nombre_negocio="X",
            oferta_principal="A",
            cliente_ideal="B",
            objetivo_mes="C",
            canales_actuales="D",
            bloqueo_actual="E",
            tareas_delegar="F",
        )
        r = await db.detectar_oportunidades_para_telefono("5561")
        assert len(r) >= 4
