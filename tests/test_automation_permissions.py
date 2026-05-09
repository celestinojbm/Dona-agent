# tests/test_automation_permissions.py — T2.1.A · Permission & Risk

"""Tests del sistema de clasificación de riesgo y reglas de aprobación."""

import pytest
from agent.automation.permissions import (
    NivelRiesgo,
    clasificar_riesgo,
    requiere_aprobacion,
    puede_auto_ejecutar,
    esta_bloqueado_t21,
    estado_inicial_para_riesgo,
    ESTADOS_VALIDOS,
    transicion_valida,
)


class TestClasificacionRiesgo:
    @pytest.mark.parametrize("tipo, esperado", [
        ("generar_plan_semanal", NivelRiesgo.LOW),
        ("generar_calendario_contenido", NivelRiesgo.LOW),
        ("analizar_diagnostico", NivelRiesgo.LOW),
        ("preparar_mensaje_whatsapp", NivelRiesgo.MEDIUM),
        ("borrador_copy_oferta", NivelRiesgo.MEDIUM),
        ("enviar_mensaje_whatsapp", NivelRiesgo.HIGH),
        ("publicar_red_social", NivelRiesgo.HIGH),
        ("gastar_creditos_masivo", NivelRiesgo.CRITICAL),
        ("borrar_datos_negocio", NivelRiesgo.CRITICAL),
        ("envio_masivo_clientes", NivelRiesgo.CRITICAL),
    ])
    def test_clasificacion_directa(self, tipo, esperado):
        assert clasificar_riesgo(tipo) == esperado

    def test_tipo_desconocido_es_medium(self):
        assert clasificar_riesgo("tipo_inventado_xyz") == NivelRiesgo.MEDIUM
        assert clasificar_riesgo("") == NivelRiesgo.MEDIUM


class TestReglasAprobacion:
    def test_low_no_requiere_aprobacion(self):
        assert requiere_aprobacion(NivelRiesgo.LOW) is False
        assert puede_auto_ejecutar(NivelRiesgo.LOW) is True

    def test_medium_requiere_aprobacion(self):
        assert requiere_aprobacion(NivelRiesgo.MEDIUM) is True
        assert puede_auto_ejecutar(NivelRiesgo.MEDIUM) is False

    def test_high_requiere_aprobacion(self):
        assert requiere_aprobacion(NivelRiesgo.HIGH) is True
        assert puede_auto_ejecutar(NivelRiesgo.HIGH) is False

    def test_critical_requiere_aprobacion_y_esta_bloqueado(self):
        assert requiere_aprobacion(NivelRiesgo.CRITICAL) is True
        assert puede_auto_ejecutar(NivelRiesgo.CRITICAL) is False
        assert esta_bloqueado_t21(NivelRiesgo.CRITICAL) is True

    def test_solo_critical_bloqueado(self):
        for r in (NivelRiesgo.LOW, NivelRiesgo.MEDIUM, NivelRiesgo.HIGH):
            assert esta_bloqueado_t21(r) is False

    def test_acepta_strings(self):
        # Helper también acepta strings
        assert requiere_aprobacion("low") is False
        assert puede_auto_ejecutar("low") is True
        assert esta_bloqueado_t21("critical") is True


class TestEstadoInicial:
    def test_low_inicial_pending(self):
        assert estado_inicial_para_riesgo(NivelRiesgo.LOW) == "pending"

    def test_medium_inicial_needs_approval(self):
        assert estado_inicial_para_riesgo(NivelRiesgo.MEDIUM) == "needs_approval"

    def test_high_inicial_needs_approval(self):
        assert estado_inicial_para_riesgo(NivelRiesgo.HIGH) == "needs_approval"

    def test_critical_inicial_needs_approval(self):
        # Aunque luego se bloquee, el estado inicial es needs_approval
        assert estado_inicial_para_riesgo(NivelRiesgo.CRITICAL) == "needs_approval"


class TestTransiciones:
    def test_estados_validos_no_vacios(self):
        assert "pending" in ESTADOS_VALIDOS
        assert "needs_approval" in ESTADOS_VALIDOS
        assert "approved" in ESTADOS_VALIDOS
        assert "running" in ESTADOS_VALIDOS
        assert "completed" in ESTADOS_VALIDOS
        assert "rejected" in ESTADOS_VALIDOS
        assert "failed" in ESTADOS_VALIDOS
        assert "cancelled" in ESTADOS_VALIDOS

    @pytest.mark.parametrize("a, b", [
        ("pending", "running"),
        ("pending", "cancelled"),
        ("needs_approval", "approved"),
        ("needs_approval", "rejected"),
        ("approved", "running"),
        ("running", "completed"),
        ("running", "failed"),
    ])
    def test_transiciones_validas(self, a, b):
        assert transicion_valida(a, b) is True

    @pytest.mark.parametrize("a, b", [
        ("completed", "running"),
        ("rejected", "approved"),
        ("running", "approved"),
        ("pending", "completed"),
        ("approved", "rejected"),
        ("xxx", "yyy"),
    ])
    def test_transiciones_invalidas(self, a, b):
        assert transicion_valida(a, b) is False
