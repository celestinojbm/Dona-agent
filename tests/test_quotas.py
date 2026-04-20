# tests/test_quotas.py — Tests para el sistema de quotas

"""
Tests para quotas (límites por usuario) y onboarding de negocio.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.business.quotas import (
    verificar_quota, obtener_uso, LIMITES,
    registrar_uso_contenido, _contar_contenido_hoy, _contenido_contadores,
    _mensaje_limite,
)


class TestQuotasLimites:
    """Verifica definiciones de límites."""

    def test_limites_definidos(self):
        assert "clientes" in LIMITES
        assert "productos" in LIMITES
        assert "transacciones_mes" in LIMITES
        assert "pedidos_activos" in LIMITES
        assert "cotizaciones_mes" in LIMITES
        assert "seguimientos_activos" in LIMITES
        assert "contenido_dia" in LIMITES

    def test_limites_son_positivos(self):
        for recurso, limite in LIMITES.items():
            assert limite > 0, f"Límite de {recurso} debe ser > 0"

    def test_mensaje_limite_conocido(self):
        msg = _mensaje_limite("clientes", 50)
        assert "50" in msg
        assert "clientes" in msg

    def test_mensaje_limite_desconocido(self):
        msg = _mensaje_limite("recurso_fake", 99)
        assert "99" in msg


class TestContenidoContador:
    """Tests para el contador in-memory de contenido."""

    def setup_method(self):
        _contenido_contadores.clear()

    def test_conteo_inicial_cero(self):
        assert _contar_contenido_hoy("5551234567") == 0

    def test_registrar_incrementa(self):
        registrar_uso_contenido("5551234567")
        assert _contar_contenido_hoy("5551234567") == 1
        registrar_uso_contenido("5551234567")
        assert _contar_contenido_hoy("5551234567") == 2

    def test_usuarios_independientes(self):
        registrar_uso_contenido("5551111111")
        registrar_uso_contenido("5551111111")
        registrar_uso_contenido("5552222222")
        assert _contar_contenido_hoy("5551111111") == 2
        assert _contar_contenido_hoy("5552222222") == 1

    def test_reset_al_cambiar_dia(self):
        from datetime import date, timedelta
        registrar_uso_contenido("5551234567")
        # Simular que la fecha guardada es de ayer
        ayer = (date.today() - timedelta(days=1)).isoformat()
        _contenido_contadores["5551234567"]["fecha"] = ayer
        assert _contar_contenido_hoy("5551234567") == 0


class TestQuotaRecursoDesconocido:
    """Verificar que un recurso desconocido siempre pasa."""

    @pytest.mark.asyncio
    async def test_recurso_inexistente_pasa(self):
        ok, msg = await verificar_quota("5551234567", "recurso_que_no_existe")
        assert ok is True
        assert msg == ""
