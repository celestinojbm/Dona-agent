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

    def test_tipo_desconocido_es_critical_fail_closed(self):
        """REGRESIÓN C4 (fail-open): el default era MEDIUM — un tipo
        inventado/spoofeado obtenía aprobación simple. Lo no clasificado
        se bloquea (CRITICAL) hasta clasificarse explícitamente."""
        assert clasificar_riesgo("tipo_inventado_xyz") == NivelRiesgo.CRITICAL
        assert clasificar_riesgo("") == NivelRiesgo.CRITICAL
        assert esta_bloqueado_t21(clasificar_riesgo("tipo_inventado_xyz")) is True


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

    def test_approved_a_failed_es_valida(self):
        """5.2 · una acción aprobada puede pasar a failed sin pasar por
        running (p.ej. CRITICAL bloqueada ANTES del claim · ya no necesita
        transicionar a running solo para poder marcarse failed)."""
        assert transicion_valida("approved", "failed") is True


class TestTransicionRiesgoAware:
    """5.2 · `transicion_valida(actual, destino, riesgo)` fail-closed.

    Cierra el eslabón "permiso→ejecución" del core loop: una acción CRITICAL
    NUNCA debe transicionar a running, y sólo LOW puede auto-ejecutarse desde
    pending. MEDIUM/HIGH exigen pasar por approved antes de running."""

    def test_critical_nunca_running_desde_approved(self):
        assert transicion_valida("approved", "running", "critical") is False

    def test_critical_nunca_running_desde_pending(self):
        assert transicion_valida("pending", "running", "critical") is False

    def test_high_no_auto_running_desde_pending(self):
        assert transicion_valida("pending", "running", "high") is False

    def test_medium_no_auto_running_desde_pending(self):
        assert transicion_valida("pending", "running", "medium") is False

    def test_low_si_auto_running_desde_pending(self):
        assert transicion_valida("pending", "running", "low") is True

    def test_high_running_desde_approved_ok(self):
        # HIGH aprobada SÍ puede ejecutar (la confirmación dedicada se exige
        # en la capa de endpoint · fuera de esta función).
        assert transicion_valida("approved", "running", "high") is True

    def test_medium_running_desde_approved_ok(self):
        assert transicion_valida("approved", "running", "medium") is True

    def test_riesgo_no_afecta_transiciones_no_running(self):
        # CRITICAL puede rechazarse/cancelarse normalmente · sólo se cierra
        # el camino a running.
        assert transicion_valida("needs_approval", "rejected", "critical") is True
        assert transicion_valida("approved", "cancelled", "critical") is True

    def test_sin_riesgo_retrocompatible(self):
        # Llamadas legacy de 2 args mantienen el comportamiento previo.
        assert transicion_valida("approved", "running") is True
        assert transicion_valida("pending", "running") is True

    def test_acepta_enum(self):
        assert transicion_valida("approved", "running", NivelRiesgo.CRITICAL) is False
        assert transicion_valida("approved", "running", NivelRiesgo.HIGH) is True

    def test_transicion_base_invalida_gana_sobre_riesgo(self):
        # running→running no es válido aunque el riesgo sea LOW.
        assert transicion_valida("running", "running", "low") is False
        # completed→running tampoco, ni con riesgo bajo.
        assert transicion_valida("completed", "running", "low") is False
