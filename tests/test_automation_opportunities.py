# tests/test_automation_opportunities.py — T2.1.A · Opportunity Engine

import pytest
from agent.automation.opportunities import (
    detectar_oportunidades, _id_oportunidad,
)


PERFIL_VACIO = {
    "nombre_negocio": "Mi Negocio",
    "industria": "comida",
    "moneda": "MXN",
    "meta_mensual": 0.0,
    "oferta_principal": "",
    "cliente_ideal": "",
    "objetivo_mes": "",
    "canales_actuales": "",
    "bloqueo_actual": "",
    "tareas_delegar": "",
}


PERFIL_COMPLETO = {
    "nombre_negocio": "Pastelería Test",
    "industria": "comida",
    "moneda": "MXN",
    "meta_mensual": 50000.0,
    "oferta_principal": "Pasteles para eventos",
    "cliente_ideal": "Familias en CDMX",
    "objetivo_mes": "Conseguir 10 clientes nuevos",
    "canales_actuales": "WhatsApp, Instagram",
    "bloqueo_actual": "Responder mensajes a tiempo",
    "tareas_delegar": "seguimiento a clientes y cotizaciones",
}


class TestIDOportunidad:
    def test_id_es_determinista(self):
        a = _id_oportunidad("5215551234567", "mejorar_oferta")
        b = _id_oportunidad("5215551234567", "mejorar_oferta")
        assert a == b

    def test_id_no_filtra_telefono(self):
        tel = "5215551234567"
        opp_id = _id_oportunidad(tel, "mejorar_oferta")
        assert tel not in opp_id

    def test_id_distinto_por_tipo(self):
        a = _id_oportunidad("5551", "mejorar_oferta")
        b = _id_oportunidad("5551", "calendario_contenido")
        assert a != b


class TestDeteccionPerfilVacio:
    def test_perfil_vacio_sugiere_mejorar_oferta(self):
        opps = detectar_oportunidades(PERFIL_VACIO, "5551")
        tipos = {o["tipo"] for o in opps}
        assert "mejorar_oferta" in tipos


class TestDeteccionPerfilCompleto:
    def test_perfil_completo_genera_multiples_oportunidades(self):
        opps = detectar_oportunidades(PERFIL_COMPLETO, "5552")
        assert len(opps) >= 4

    def test_plan_semanal_aparece_si_perfil_completo(self):
        opps = detectar_oportunidades(PERFIL_COMPLETO, "5552")
        tipos = {o["tipo"] for o in opps}
        assert "plan_semanal" in tipos

    def test_calendario_contenido_aparece_si_canales(self):
        opps = detectar_oportunidades(PERFIL_COMPLETO, "5552")
        tipos = {o["tipo"] for o in opps}
        assert "calendario_contenido" in tipos

    def test_reactivacion_aparece_si_tareas_mencionan_seguimiento(self):
        opps = detectar_oportunidades(PERFIL_COMPLETO, "5552")
        tipos = {o["tipo"] for o in opps}
        assert "reactivacion_clientes" in tipos

    def test_campana_whatsapp_aparece_si_whatsapp_es_canal_y_hay_oferta(self):
        opps = detectar_oportunidades(PERFIL_COMPLETO, "5552")
        tipos = {o["tipo"] for o in opps}
        assert "campana_whatsapp_simple" in tipos

    def test_checklist_ventas_aparece_si_hay_bloqueo(self):
        opps = detectar_oportunidades(PERFIL_COMPLETO, "5552")
        tipos = {o["tipo"] for o in opps}
        assert "checklist_ventas" in tipos


class TestEstructuraOportunidad:
    def test_oportunidad_tiene_todos_los_campos(self):
        opps = detectar_oportunidades(PERFIL_COMPLETO, "5553")
        assert opps
        for o in opps:
            for k in ("id", "tipo", "titulo", "descripcion", "razon",
                      "prioridad", "impacto_estimado", "riesgo",
                      "fuente_datos", "playbook_sugerido"):
                assert k in o, f"Falta clave '{k}' en oportunidad"
            assert isinstance(o["fuente_datos"], list)
            assert o["prioridad"] in (1, 2, 3, 4, 5)
            assert o["impacto_estimado"] in ("alto", "medio", "bajo")


class TestOrdenPrioridad:
    def test_resultados_ordenados_por_prioridad(self):
        opps = detectar_oportunidades(PERFIL_COMPLETO, "5554")
        prioridades = [o["prioridad"] for o in opps]
        assert prioridades == sorted(prioridades)


class TestIdempotencia:
    def test_mismo_perfil_misma_lista(self):
        a = detectar_oportunidades(PERFIL_COMPLETO, "5555")
        b = detectar_oportunidades(PERFIL_COMPLETO, "5555")
        ids_a = [o["id"] for o in a]
        ids_b = [o["id"] for o in b]
        assert ids_a == ids_b


class TestNoDeteccionSiCondicionAusente:
    def test_sin_canales_no_calendario(self):
        perfil = dict(PERFIL_COMPLETO)
        perfil["canales_actuales"] = ""
        opps = detectar_oportunidades(perfil, "5556")
        tipos = {o["tipo"] for o in opps}
        assert "calendario_contenido" not in tipos

    def test_sin_whatsapp_no_campana(self):
        perfil = dict(PERFIL_COMPLETO)
        perfil["canales_actuales"] = "Instagram, referidos"
        opps = detectar_oportunidades(perfil, "5557")
        tipos = {o["tipo"] for o in opps}
        assert "campana_whatsapp_simple" not in tipos

    def test_sin_bloqueo_no_checklist(self):
        perfil = dict(PERFIL_COMPLETO)
        perfil["bloqueo_actual"] = ""
        opps = detectar_oportunidades(perfil, "5558")
        tipos = {o["tipo"] for o in opps}
        assert "checklist_ventas" not in tipos
