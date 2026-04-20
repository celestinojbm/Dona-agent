# tests/test_gmail_query.py — Tests del traductor de queries naturales de Gmail

"""
Verifica que `_traducir_query_natural` en agent/gmail.py:
  - Agrega `category:primary` por default (lee la bandeja principal)
  - NO agrega primary cuando el usuario pide explícitamente otras categorías
  - Traduce operadores comunes (from, asunto, fechas, adjuntos)
"""

import pytest
from agent.gmail import _traducir_query_natural


class TestPrimaryDefault:
    def test_default_incluye_primary(self):
        q = _traducir_query_natural("correos de juan")
        assert "category:primary" in q
        assert "from:juan" in q

    def test_busqueda_generica_incluye_primary(self):
        q = _traducir_query_natural("factura")
        assert "category:primary" in q

    def test_solo_no_leidos_incluye_primary(self):
        q = _traducir_query_natural("correos sin leer")
        assert "category:primary" in q
        assert "is:unread" in q


class TestBypassPrimary:
    def test_promociones_bypass(self):
        q = _traducir_query_natural("busca en promociones")
        assert "category:primary" not in q
        assert "category:promotions" in q

    def test_social_bypass(self):
        q = _traducir_query_natural("correos de social")
        assert "category:primary" not in q
        assert "category:social" in q

    def test_todas_las_categorias_bypass(self):
        q = _traducir_query_natural("busca en todas las categorias sobre factura")
        assert "category:primary" not in q

    def test_incluye_spam_bypass(self):
        q = _traducir_query_natural("busca incluyendo spam")
        assert "category:primary" not in q

    def test_bandeja_completa_bypass(self):
        q = _traducir_query_natural("busca en bandeja completa")
        assert "category:primary" not in q


class TestOperadoresBasicos:
    def test_from_detectado(self):
        q = _traducir_query_natural("correos de pedro@empresa.com")
        assert "from:pedro@empresa.com" in q

    def test_asunto_detectado(self):
        q = _traducir_query_natural("correos con asunto:reunion")
        assert "subject:reunion" in q

    def test_adjunto_detectado(self):
        q = _traducir_query_natural("correos con adjunto")
        assert "has:attachment" in q

    def test_hoy_mapea_newer_1d(self):
        q = _traducir_query_natural("correos de hoy")
        assert "newer_than:1d" in q

    def test_esta_semana_mapea_newer_7d(self):
        q = _traducir_query_natural("correos de esta semana")
        assert "newer_than:7d" in q

    def test_este_mes_mapea_newer_30d(self):
        q = _traducir_query_natural("correos de este mes")
        assert "newer_than:30d" in q


class TestCombinaciones:
    def test_from_semana_no_leidos_mantiene_primary(self):
        q = _traducir_query_natural("correos sin leer de juan esta semana")
        assert "from:juan" in q
        assert "is:unread" in q
        assert "newer_than:7d" in q
        assert "category:primary" in q

    def test_promociones_con_from_sin_primary(self):
        q = _traducir_query_natural("promociones de amazon")
        assert "category:promotions" in q
        assert "category:primary" not in q
