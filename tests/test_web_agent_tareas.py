# tests/test_web_agent_tareas.py — Tests para la tarea ejemplo consultar_pagina_publica

"""
No requieren Playwright real: mockean el objeto `page` que el runner inyecta.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.web_agent import ContextoTarea
from agent.web_agent.tareas.consultar_pagina_publica import ConsultarPaginaPublica


class TestConsultarPaginaPublica:
    def test_nombre_correcto(self):
        assert ConsultarPaginaPublica.nombre == "consultar_pagina_publica"

    @pytest.mark.asyncio
    async def test_sin_url_falla(self):
        tarea = ConsultarPaginaPublica()
        ctx = ContextoTarea(telefono="5551", page=MagicMock())
        r = await tarea.ejecutar(ctx, {})
        assert r.exito is False
        assert "url" in r.mensaje.lower()

    @pytest.mark.asyncio
    async def test_url_invalida_falla(self):
        tarea = ConsultarPaginaPublica()
        ctx = ContextoTarea(telefono="5551", page=MagicMock())
        r = await tarea.ejecutar(ctx, {"url": "ftp://foo.bar"})
        assert r.exito is False

    @pytest.mark.asyncio
    async def test_carga_pagina_ok(self):
        tarea = ConsultarPaginaPublica()

        # Mock de Playwright Page
        page = MagicMock()
        page.goto = AsyncMock(return_value=None)
        page.title = AsyncMock(return_value="Example Domain")

        # Mock del locator para meta[name=description]
        loc = MagicMock()
        loc.first.get_attribute = AsyncMock(return_value="A domain for illustration")
        page.locator = MagicMock(return_value=loc)

        ctx = ContextoTarea(telefono="5551", page=page)
        r = await tarea.ejecutar(ctx, {"url": "https://example.com", "timeout_ms": 5000})

        assert r.exito is True
        assert r.datos["titulo"] == "Example Domain"
        assert r.datos["url"] == "https://example.com"
        assert "illustration" in r.datos["descripcion"]
        page.goto.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_meta_description_faltante(self):
        """Si no hay meta-description el campo debe quedar vacío, no crashear."""
        tarea = ConsultarPaginaPublica()

        page = MagicMock()
        page.goto = AsyncMock(return_value=None)
        page.title = AsyncMock(return_value="Sin Meta")

        loc = MagicMock()
        loc.first.get_attribute = AsyncMock(side_effect=Exception("not found"))
        page.locator = MagicMock(return_value=loc)

        ctx = ContextoTarea(telefono="5551", page=page)
        r = await tarea.ejecutar(ctx, {"url": "https://x.com"})

        assert r.exito is True
        assert r.datos["titulo"] == "Sin Meta"
        assert r.datos["descripcion"] == ""

    @pytest.mark.asyncio
    async def test_sin_page_inyectado(self):
        tarea = ConsultarPaginaPublica()
        ctx = ContextoTarea(telefono="5551", page=None)
        r = await tarea.ejecutar(ctx, {"url": "https://x.com"})
        assert r.exito is False
        assert "runner" in r.mensaje.lower()
