# tests/test_automation_playbooks.py — T2.1.A · Playbook Engine

import pytest
from agent.automation.playbooks import (
    listar_playbooks, obtener_playbook, existe_playbook,
)
from agent.automation.permissions import NivelRiesgo


class TestCatalogoPlaybooks:
    def test_listar_devuelve_lista_no_vacia(self):
        pbs = listar_playbooks()
        assert isinstance(pbs, list)
        assert len(pbs) >= 6

    def test_los_6_playbooks_iniciales_existen(self):
        ids = {p["id"] for p in listar_playbooks()}
        esperados = {
            "diagnostico_a_plan_semanal",
            "calendario_contenido_7d",
            "reactivacion_clientes",
            "mejora_oferta",
            "campana_whatsapp_simple",
            "checklist_ventas",
        }
        assert esperados.issubset(ids), \
            f"Faltan playbooks: {esperados - ids}"

    def test_existe_helper(self):
        assert existe_playbook("diagnostico_a_plan_semanal")
        assert not existe_playbook("inexistente_xxx")


class TestEstructuraPlaybook:
    @pytest.mark.parametrize("playbook_id", [
        "diagnostico_a_plan_semanal",
        "calendario_contenido_7d",
        "reactivacion_clientes",
        "mejora_oferta",
        "campana_whatsapp_simple",
        "checklist_ventas",
    ])
    def test_estructura_completa(self, playbook_id):
        pb = obtener_playbook(playbook_id)
        for k in ("id", "nombre", "objetivo", "pasos",
                  "herramientas_requeridas", "riesgo",
                  "costo_creditos_estimado", "requires_approval",
                  "outputs_esperados"):
            assert k in pb, f"Falta clave '{k}' en playbook {playbook_id}"
        assert pb["id"] == playbook_id
        assert isinstance(pb["pasos"], list) and len(pb["pasos"]) > 0
        assert pb["costo_creditos_estimado"] >= 0
        assert pb["riesgo"] in {"low", "medium", "high", "critical"}

    def test_obtener_playbook_inexistente_raises(self):
        with pytest.raises(KeyError):
            obtener_playbook("xxxnope")


class TestRiesgoMaximo:
    def test_diagnostico_a_plan_es_low(self):
        # Solo tiene pasos LOW
        pb = obtener_playbook("diagnostico_a_plan_semanal")
        assert pb["riesgo"] == NivelRiesgo.LOW.value
        assert pb["requires_approval"] is False

    def test_reactivacion_es_high_por_envio_real(self):
        # Tiene paso enviar_mensaje_whatsapp (HIGH)
        pb = obtener_playbook("reactivacion_clientes")
        assert pb["riesgo"] == NivelRiesgo.HIGH.value
        assert pb["requires_approval"] is True

    def test_campana_whatsapp_es_high_por_envio_masivo(self):
        # Tiene paso enviar_campana_masiva (HIGH)
        pb = obtener_playbook("campana_whatsapp_simple")
        assert pb["riesgo"] == NivelRiesgo.HIGH.value


class TestCostoEstimado:
    def test_costo_es_suma_pasos(self):
        from agent.automation.costos import COSTO_POR_TIPO_ACCION
        pb = obtener_playbook("checklist_ventas")
        suma = sum(
            COSTO_POR_TIPO_ACCION.get(p["tipo_accion"], 5)
            for p in pb["pasos"]
        )
        assert pb["costo_creditos_estimado"] == suma
