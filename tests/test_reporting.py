# tests/test_reporting.py — Tests del detector de comandos de reporte

"""
Tests unitarios del parser de comandos en `agent.reporting.detectar_comando_reporte`.
Las funciones que tocan DB se testean en integración (no en este archivo).
"""

import pytest
from agent.reporting import detectar_comando_reporte


class TestDetectorComandos:
    def test_vacio_retorna_none(self):
        assert detectar_comando_reporte("") is None
        assert detectar_comando_reporte("   ") is None

    def test_sin_prefijo_dona_ignora(self):
        assert detectar_comando_reporte("resumen del mes") is None
        assert detectar_comando_reporte("exporta csv") is None

    def test_resumen_del_mes(self):
        r = detectar_comando_reporte("dona resumen del mes")
        assert r == {"tipo": "resumen", "año": None, "mes": None, "destino": "whatsapp"}

    def test_resumen_mensual(self):
        r = detectar_comando_reporte("dona resumen mensual")
        assert r and r["tipo"] == "resumen"

    def test_resumen_financiero(self):
        r = detectar_comando_reporte("dona resumen financiero")
        assert r and r["tipo"] == "resumen"

    def test_resumen_con_mes_nombre(self):
        r = detectar_comando_reporte("dona resumen octubre")
        assert r == {"tipo": "resumen", "año": None, "mes": 10, "destino": "whatsapp"}

    def test_resumen_con_mes_y_de(self):
        r = detectar_comando_reporte("dona resumen de marzo")
        assert r == {"tipo": "resumen", "año": None, "mes": 3, "destino": "whatsapp"}

    def test_resumen_solo_no_matchea(self):
        """'dona resumen' solo debe NO matchear reporte — es del morning brief."""
        assert detectar_comando_reporte("dona resumen") is None

    def test_reporte_palabra_directa(self):
        r = detectar_comando_reporte("dona reporte")
        assert r == {"tipo": "resumen", "año": None, "mes": None, "destino": "whatsapp"}

    def test_reporte_con_mes(self):
        r = detectar_comando_reporte("dona reporte de diciembre")
        assert r == {"tipo": "resumen", "año": None, "mes": 12, "destino": "whatsapp"}

    def test_exporta(self):
        r = detectar_comando_reporte("dona exporta")
        assert r == {"tipo": "exportar", "año": None, "mes": None, "destino": "whatsapp"}

    def test_exporta_csv(self):
        r = detectar_comando_reporte("dona exporta csv")
        assert r == {"tipo": "exportar", "año": None, "mes": None, "destino": "whatsapp"}

    def test_exportar_con_mes(self):
        r = detectar_comando_reporte("dona exportar ventas de noviembre")
        assert r == {"tipo": "exportar", "año": None, "mes": 11, "destino": "whatsapp"}

    def test_acentos_normalizados(self):
        # "octubre" sin acento, pero probar con acentos en otro contexto
        r = detectar_comando_reporte("dona resumen financiéro")
        assert r and r["tipo"] == "resumen"
