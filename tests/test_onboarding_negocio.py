# tests/test_onboarding_negocio.py — Tests para onboarding de negocio

"""
Tests para el flujo de onboarding de negocio self-service.
"""

import pytest
from agent.business.onboarding_negocio import (
    MENSAJE_INICIO, MENSAJE_INDUSTRIA, MENSAJE_MONEDA, MENSAJE_META,
    MENSAJE_COMPLETADO, TRIGGER_KEYWORDS,
    _INDUSTRIAS, _MONEDAS, _INDUSTRIA_LABEL,
)


class TestMensajes:
    """Verifica que los mensajes del flujo están bien definidos."""

    def test_mensaje_inicio_pregunta_nombre(self):
        assert "nombre" in MENSAJE_INICIO.lower() or "llama" in MENSAJE_INICIO.lower()

    def test_mensaje_industria_tiene_opciones(self):
        # El template usa {nombre}
        msg = MENSAJE_INDUSTRIA.format(nombre="Test")
        assert "1." in msg
        assert "5." in msg

    def test_mensaje_moneda_tiene_opciones(self):
        assert "MXN" in MENSAJE_MONEDA
        assert "USD" in MENSAJE_MONEDA
        assert "COP" in MENSAJE_MONEDA

    def test_mensaje_meta_permite_omitir(self):
        assert "no" in MENSAJE_META.lower()

    def test_mensaje_completado_formateado(self):
        msg = MENSAJE_COMPLETADO.format(
            nombre="Mi Tienda", industria="Retail",
            moneda="MXN", meta_texto="Meta mensual: $50,000"
        )
        assert "Mi Tienda" in msg
        assert "Retail" in msg
        assert "50,000" in msg


class TestMapeos:
    """Verifica que los mapeos de industria y moneda funcionan."""

    def test_industria_numeros(self):
        assert _INDUSTRIAS["1"] == "comida"
        assert _INDUSTRIAS["2"] == "servicios"
        assert _INDUSTRIAS["3"] == "retail"
        assert _INDUSTRIAS["4"] == "freelance"
        assert _INDUSTRIAS["5"] == "otro"

    def test_industria_texto(self):
        assert _INDUSTRIAS["restaurante"] == "comida"
        assert _INDUSTRIAS["tienda"] == "retail"
        assert _INDUSTRIAS["freelance"] == "freelance"

    def test_industria_default(self):
        assert _INDUSTRIAS.get("algo_raro", "otro") == "otro"

    def test_moneda_numeros(self):
        assert _MONEDAS["1"] == "MXN"
        assert _MONEDAS["2"] == "USD"
        assert _MONEDAS["5"] == "EUR"

    def test_moneda_texto(self):
        assert _MONEDAS["usd"] == "USD"
        assert _MONEDAS["euros"] == "EUR"
        assert _MONEDAS["pesos"] == "MXN"

    def test_industria_labels_completas(self):
        for key in {"comida", "servicios", "retail", "freelance", "otro"}:
            assert key in _INDUSTRIA_LABEL


class TestTriggers:
    """Verifica que las keywords de trigger están definidas."""

    def test_triggers_no_vacios(self):
        assert len(TRIGGER_KEYWORDS) > 0

    def test_triggers_comunes(self):
        assert "mi negocio" in TRIGGER_KEYWORDS
        assert "mi tienda" in TRIGGER_KEYWORDS
        assert "configurar negocio" in TRIGGER_KEYWORDS

    def test_trigger_match(self):
        texto = "quiero configurar mi negocio"
        assert any(kw in texto.lower() for kw in TRIGGER_KEYWORDS)

    def test_no_trigger_casual(self):
        texto = "hola cómo estás"
        assert not any(kw in texto.lower() for kw in TRIGGER_KEYWORDS)
