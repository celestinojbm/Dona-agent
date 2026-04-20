# tests/test_web_agent.py — Tests del registro y runner del web-agent

"""
Tests del scaffolding web_agent. No requieren Playwright instalado:
el runner detecta su ausencia y devuelve un ResultadoTarea explicativo.
"""

import pytest

from agent.web_agent import (
    WebAgentTarea,
    ResultadoTarea,
    ContextoTarea,
    registrar,
    obtener,
    nombres_registrados,
    ejecutar_tarea,
)
from agent.web_agent import runner as _runner
from agent.web_agent import registro as _registro


class _TareaTest(WebAgentTarea):
    """Tarea de prueba que no toca browser — útil para test del runner."""
    nombre = "tarea_test"

    async def ejecutar(self, contexto, parametros):
        return ResultadoTarea(
            exito=True,
            datos={"echo": parametros},
            mensaje="ok",
        )


@pytest.fixture(autouse=True)
def _limpiar_registro():
    """Resetea el registro entre tests para aislar cada caso."""
    _registro._TAREAS.clear()
    yield
    _registro._TAREAS.clear()


class TestRegistro:
    def test_registrar_y_obtener(self):
        t = _TareaTest()
        registrar(t)
        assert obtener("tarea_test") is t

    def test_obtener_inexistente(self):
        assert obtener("no_existe") is None

    def test_nombres_registrados_ordenados(self):
        class T1(WebAgentTarea):
            nombre = "zebra"
            async def ejecutar(self, c, p): return ResultadoTarea(exito=True)

        class T2(WebAgentTarea):
            nombre = "alfa"
            async def ejecutar(self, c, p): return ResultadoTarea(exito=True)

        registrar(T1())
        registrar(T2())
        assert nombres_registrados() == ["alfa", "zebra"]

    def test_registrar_nombre_vacio_error(self):
        class TareaSinNombre(WebAgentTarea):
            nombre = ""
            async def ejecutar(self, c, p): return ResultadoTarea(exito=True)

        with pytest.raises(ValueError):
            registrar(TareaSinNombre())


class TestRunner:
    @pytest.mark.asyncio
    async def test_tarea_no_registrada(self):
        resultado = await ejecutar_tarea("no_existe", "5551", {})
        assert resultado.exito is False
        assert "no registrada" in resultado.mensaje.lower()

    @pytest.mark.asyncio
    async def test_playwright_no_disponible(self, monkeypatch):
        """Si Playwright no está instalado, el runner lo reporta en vez de crashear."""
        registrar(_TareaTest())
        monkeypatch.setattr(_runner, "_playwright_disponible", lambda: False)
        resultado = await ejecutar_tarea("tarea_test", "5551", {"k": "v"})
        assert resultado.exito is False
        assert "playwright" in resultado.mensaje.lower()


class TestResultadoTarea:
    def test_defaults(self):
        r = ResultadoTarea(exito=True)
        assert r.datos == {}
        assert r.mensaje == ""
        assert r.cookies_actualizadas == []
        assert r.requiere_mfa is False


class TestContextoTarea:
    def test_defaults(self):
        c = ContextoTarea(telefono="5551")
        assert c.page is None
        assert c.cookies == []
        assert c.solicitar_mfa is None
