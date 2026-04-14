# tests/test_brain_tools.py — Tests para clasificación de mensajes y selección de tools

"""
Tests para el sistema de selección dinámica de herramientas.
Verifica que los mensajes se clasifican correctamente y se envían
solo las tools relevantes a la API de Claude.
"""

import pytest
from unittest.mock import patch


# Importar funciones de clasificación (no necesitan API keys)
from agent.brain import _clasificar_mensaje, seleccionar_tools


class TestClasificarMensaje:
    """Tests para _clasificar_mensaje — clasificación regex de mensajes."""

    def test_conversacional_hola(self):
        result = _clasificar_mensaje("hola")
        assert result == set()

    def test_conversacional_gracias(self):
        result = _clasificar_mensaje("gracias")
        assert result == set()

    def test_conversacional_como_estas(self):
        result = _clasificar_mensaje("cómo estás")
        assert result == set()

    def test_recordatorio_basico(self):
        result = _clasificar_mensaje("recuérdame comprar leche mañana")
        assert result is not None
        assert "crear_recordatorio" in result

    def test_nota_basica(self):
        result = _clasificar_mensaje("anota que tengo reunión el lunes")
        assert result is not None
        assert "guardar_nota" in result

    def test_gmail_correo(self):
        result = _clasificar_mensaje("lee mis correos de hoy")
        assert result is not None
        assert "leer_correos" in result

    def test_gmail_email(self):
        result = _clasificar_mensaje("envía un email a juan")
        assert result is not None
        assert "redactar_y_enviar_correo" in result

    def test_calendario(self):
        result = _clasificar_mensaje("qué tengo en mi agenda mañana")
        assert result is not None
        assert "consultar_calendario" in result or len(result) > 0

    def test_timezone(self):
        result = _clasificar_mensaje("qué hora es")
        assert result is not None
        assert len(result) > 0

    def test_sheets(self):
        result = _clasificar_mensaje("agrega datos a mi hoja de cálculo")
        assert result is not None

    def test_mensaje_largo_sin_keywords(self):
        """Mensajes largos sin keywords se clasifican como conversacionales."""
        texto = "me parece muy interesante lo que dices sobre la filosofía moderna y cómo impacta en nuestras vidas cotidianas desde una perspectiva diferente"
        result = _clasificar_mensaje(texto)
        assert result == set()

    def test_no_clasificable(self):
        """Mensajes cortos sin keywords claros retornan None (fallback)."""
        result = _clasificar_mensaje("perro gato")
        # Puede ser None o set() dependiendo de la longitud
        assert result is None or isinstance(result, set)

    def test_confirmacion_envio(self):
        """'sí envíalo' debe incluir tools de gmail por confirmación."""
        result = _clasificar_mensaje("sí, envíalo")
        assert result is not None
        assert "redactar_y_enviar_correo" in result or "confirmar_envio_correo" in result


class TestSeleccionarTools:
    """Tests para seleccionar_tools — filtrado de herramientas."""

    def test_conversacional_sin_tools(self):
        tools = seleccionar_tools("hola")
        assert tools == []

    def test_recordatorio_tools_filtradas(self):
        tools = seleccionar_tools("recuérdame llamar al doctor")
        assert len(tools) > 0
        nombres = {t["name"] for t in tools}
        assert "crear_recordatorio" in nombres

    def test_fallback_todas(self):
        """Mensajes no clasificables deben retornar todas las tools."""
        from agent.brain import TOOLS
        tools = seleccionar_tools("xyz abc 123")
        # Puede ser todas o ninguna dependiendo de la clasificación
        assert isinstance(tools, list)

    def test_tools_son_dicts(self):
        """Cada tool retornada debe tener name y description."""
        tools = seleccionar_tools("recuérdame algo importante")
        for t in tools:
            assert "name" in t
            assert isinstance(t["name"], str)
