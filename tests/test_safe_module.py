# tests/test_safe_module.py — Tests para normalización de teléfono y verificación de owner

"""
Tests para la lógica de seguridad del módulo enhanced/safe_module.py.
Verifica que la normalización E.164 y la verificación de owner funcionan correctamente.
"""

import pytest
from unittest.mock import patch


class TestNormalizarTelefono:
    def test_solo_digitos(self):
        from enhanced.safe_module import _normalizar_telefono
        assert _normalizar_telefono("5215551234567") == "5215551234567"

    def test_con_prefijo_plus(self):
        from enhanced.safe_module import _normalizar_telefono
        assert _normalizar_telefono("+5215551234567") == "5215551234567"

    def test_con_espacios_y_guiones(self):
        from enhanced.safe_module import _normalizar_telefono
        assert _normalizar_telefono("+52 1 555-123-4567") == "5215551234567"

    def test_cadena_vacia(self):
        from enhanced.safe_module import _normalizar_telefono
        assert _normalizar_telefono("") == ""


class TestEsOwner:
    @patch("enhanced.safe_module.OWNER_PHONE", "+5215551234567")
    def test_owner_match_exacto(self):
        from enhanced.safe_module import _es_owner
        assert _es_owner("5215551234567") is True

    @patch("enhanced.safe_module.OWNER_PHONE", "+5215551234567")
    def test_owner_con_plus(self):
        from enhanced.safe_module import _es_owner
        assert _es_owner("+5215551234567") is True

    @patch("enhanced.safe_module.OWNER_PHONE", "+5215551234567")
    def test_no_owner(self):
        from enhanced.safe_module import _es_owner
        assert _es_owner("5215559999999") is False

    @patch("enhanced.safe_module.OWNER_PHONE", "")
    def test_sin_owner_configurado(self):
        from enhanced.safe_module import _es_owner
        assert _es_owner("5215551234567") is False

    @patch("enhanced.safe_module.OWNER_PHONE", "+52 1 555 123 4567")
    def test_owner_con_espacios(self):
        from enhanced.safe_module import _es_owner
        assert _es_owner("5215551234567") is True
