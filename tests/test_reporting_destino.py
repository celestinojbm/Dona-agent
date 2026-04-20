# tests/test_reporting_destino.py — Tests del campo `destino` en detectar_comando_reporte

"""
Verifica que el detector de comando distinga "por correo" de envío normal.
"""

import pytest

from agent.reporting import detectar_comando_reporte


class TestDestino:
    def test_exporta_default_whatsapp(self):
        r = detectar_comando_reporte("dona exporta")
        assert r is not None
        assert r["tipo"] == "exportar"
        assert r["destino"] == "whatsapp"

    def test_exporta_por_correo(self):
        r = detectar_comando_reporte("dona exporta por correo")
        assert r is not None
        assert r["tipo"] == "exportar"
        assert r["destino"] == "email"

    def test_exporta_a_mi_email(self):
        r = detectar_comando_reporte("dona exporta octubre a mi email")
        assert r is not None
        assert r["destino"] == "email"
        assert r["mes"] == 10

    def test_exporta_por_gmail(self):
        r = detectar_comando_reporte("dona exporta por gmail")
        assert r["destino"] == "email"

    def test_reporte_por_correo(self):
        r = detectar_comando_reporte("dona reporte del mes por correo")
        assert r["tipo"] == "resumen"
        assert r["destino"] == "email"

    def test_resumen_financiero_sin_destino(self):
        r = detectar_comando_reporte("dona resumen financiero")
        assert r["destino"] == "whatsapp"

    def test_no_comando_retorna_none(self):
        assert detectar_comando_reporte("hola") is None
        assert detectar_comando_reporte("") is None

    def test_mes_detectado_persiste_con_email(self):
        r = detectar_comando_reporte("dona exporta noviembre por correo")
        assert r["mes"] == 11
        assert r["destino"] == "email"
