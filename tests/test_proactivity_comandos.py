# tests/test_proactivity_comandos.py — cobertura de helpers de agent/proactivity.py

"""
Fija el comportamiento ACTUAL de los helpers de control de proactividad y de los
formateadores puros de agent/proactivity.py, que no tenían test dedicado:

  * es_comando_proactividad        — detección exacta (case-insensitive, strip)
                                     del set COMANDOS_PROACTIVIDAD.
  * manejar_comando_proactividad   — despacho de cada comando: pausa, activación
                                     (con limpieza de supresión), resumen, semana,
                                     olvido de patrones, y fallback desconocido.
  * _hora_local_str                — conversión UTC → hora local con offset puro.
  * _es_recordatorio_importante    — detección por palabra clave (subcadena,
                                     case-insensitive) de recordatorios relevantes.

DB, LLM y envío externo SIEMPRE mockeados — nunca llamadas reales. Estos tests
cubren ramas existentes; NO cambian la lógica de producción ni debilitan guardas
de TCPA/opt-out (solo fijan lo que el código ya hace).
"""

from datetime import datetime

import agent.proactivity as proactivity
import pytest


# --------------------------------------------------------------------------- #
# es_comando_proactividad — detección pura
# --------------------------------------------------------------------------- #
class TestEsComandoProactividad:
    @pytest.mark.parametrize("cmd", sorted(proactivity.COMANDOS_PROACTIVIDAD))
    def test_cada_comando_del_set_se_reconoce(self, cmd):
        assert proactivity.es_comando_proactividad(cmd) is True

    def test_case_insensitive_y_con_espacios(self):
        assert proactivity.es_comando_proactividad("  DONA PAUSA  ") is True
        assert proactivity.es_comando_proactividad("Dona Resumen") is True

    @pytest.mark.parametrize(
        "texto",
        ["hola", "pausa", "dona", "dona pausala", "resumen", ""],
    )
    def test_textos_que_no_son_comando(self, texto):
        assert proactivity.es_comando_proactividad(texto) is False


# --------------------------------------------------------------------------- #
# manejar_comando_proactividad — despacho con dependencias mockeadas
# --------------------------------------------------------------------------- #
def _mock_guardar_proactividad(monkeypatch):
    """Captura las llamadas a agent.memory.guardar_proactividad (importada de
    forma perezosa dentro de la función)."""
    import agent.memory as memory

    registro = []

    async def fake_guardar(telefono, proactive_enabled):
        registro.append((telefono, proactive_enabled))

    monkeypatch.setattr(memory, "guardar_proactividad", fake_guardar)
    return registro


class TestManejarComandoProactividad:
    async def test_pausa_desactiva_proactividad(self, monkeypatch):
        reg = _mock_guardar_proactividad(monkeypatch)
        resp = await proactivity.manejar_comando_proactividad("+15551110000", "dona pausa")
        assert "no te enviaré mensajes proactivos" in resp.lower()
        # Persistió proactive_enabled=False al menos una vez para ese usuario.
        assert reg, "esperaba al menos una persistencia"
        assert all(estado is False for _, estado in reg)

    @pytest.mark.parametrize("cmd", ["dona pausa", "dona pausar", "dona silencio"])
    async def test_los_tres_alias_de_pausa_persisten_false(self, monkeypatch, cmd):
        reg = _mock_guardar_proactividad(monkeypatch)
        await proactivity.manejar_comando_proactividad("+15551110001", cmd)
        assert reg and all(estado is False for _, estado in reg)

    async def test_activar_reactiva_y_limpia_supresion(self, monkeypatch):
        reg = _mock_guardar_proactividad(monkeypatch)
        limpiezas = []
        import agent.envio_gate as envio_gate

        def fake_limpiar(telefono):
            limpiezas.append(telefono)

        monkeypatch.setattr(envio_gate, "limpiar_supresion_emergencia", fake_limpiar)

        resp = await proactivity.manejar_comando_proactividad("+15551110002", "dona actívate")
        assert "proactivo" in resp.lower()
        assert reg and all(estado is True for _, estado in reg)
        # Coherencia con re-opt-in: se levanta la supresión de emergencia.
        assert limpiezas == ["+15551110002"]

    @pytest.mark.parametrize("cmd", ["dona actívate", "dona activar", "dona activa"])
    async def test_los_tres_alias_de_activar_persisten_true(self, monkeypatch, cmd):
        reg = _mock_guardar_proactividad(monkeypatch)
        import agent.envio_gate as envio_gate
        monkeypatch.setattr(envio_gate, "limpiar_supresion_emergencia", lambda t: None)
        await proactivity.manejar_comando_proactividad("+15551110003", cmd)
        assert reg and all(estado is True for _, estado in reg)

    async def test_resumen_delega_en_morning_brief(self, monkeypatch):
        import agent.memory as memory

        async def fake_onboarding(telefono):
            return {"nombre": "Celestino", "contexto": "vende café"}

        capturado = {}

        async def fake_brief(telefono, nombre, contexto, bajo_demanda=False):
            capturado.update(
                telefono=telefono, nombre=nombre, contexto=contexto, bajo_demanda=bajo_demanda
            )
            return "BRIEF_OK"

        monkeypatch.setattr(memory, "obtener_onboarding", fake_onboarding)
        monkeypatch.setattr(proactivity, "_generar_morning_brief", fake_brief)

        resp = await proactivity.manejar_comando_proactividad("+15551110004", "dona resumen")
        assert resp == "BRIEF_OK"
        assert capturado["nombre"] == "Celestino"
        assert capturado["contexto"] == "vende café"
        assert capturado["bajo_demanda"] is True

    async def test_semana_delega_en_weekly_review(self, monkeypatch):
        import agent.memory as memory

        async def fake_onboarding(telefono):
            return {"nombre": "Ana", "contexto": "consultora"}

        capturado = {}

        async def fake_weekly(telefono, nombre, contexto):
            capturado.update(telefono=telefono, nombre=nombre, contexto=contexto)
            return "WEEKLY_OK"

        monkeypatch.setattr(memory, "obtener_onboarding", fake_onboarding)
        monkeypatch.setattr(proactivity, "_generar_weekly_review", fake_weekly)

        resp = await proactivity.manejar_comando_proactividad("+15551110005", "dona semana")
        assert resp == "WEEKLY_OK"
        assert capturado["nombre"] == "Ana"

    async def test_resumen_sin_onboarding_usa_vacios(self, monkeypatch):
        import agent.memory as memory

        async def fake_onboarding(telefono):
            return None

        capturado = {}

        async def fake_brief(telefono, nombre, contexto, bajo_demanda=False):
            capturado.update(nombre=nombre, contexto=contexto)
            return "OK"

        monkeypatch.setattr(memory, "obtener_onboarding", fake_onboarding)
        monkeypatch.setattr(proactivity, "_generar_morning_brief", fake_brief)

        await proactivity.manejar_comando_proactividad("+15551110006", "dona resumen")
        assert capturado["nombre"] == ""
        assert capturado["contexto"] == ""

    @pytest.mark.parametrize("cmd", ["dona olvida mis patrones", "dona olvida patrones"])
    async def test_olvidar_patrones_borra_aprendizaje(self, monkeypatch, cmd):
        import agent.memory as memory

        borrados = []

        async def fake_borrar(telefono):
            borrados.append(telefono)

        monkeypatch.setattr(memory, "borrar_datos_aprendizaje", fake_borrar)

        resp = await proactivity.manejar_comando_proactividad("+15551110007", cmd)
        assert "borré" in resp.lower() or "desde cero" in resp.lower()
        assert borrados == ["+15551110007"]

    async def test_comando_desconocido_devuelve_fallback(self, monkeypatch):
        # No debería tocar ninguna dependencia; mockeamos guardar por las dudas.
        _mock_guardar_proactividad(monkeypatch)
        resp = await proactivity.manejar_comando_proactividad("+15551110008", "dona xyz")
        assert resp == "No reconocí ese comando."


# --------------------------------------------------------------------------- #
# _hora_local_str — formateo puro
# --------------------------------------------------------------------------- #
class TestHoraLocalStr:
    def test_sin_offset_usa_la_hora_utc(self):
        utc = datetime(2026, 6, 30, 14, 5)
        assert proactivity._hora_local_str(utc) == "30/06 14:05"

    def test_offset_positivo_suma_minutos(self):
        utc = datetime(2026, 6, 30, 14, 0)
        # +90 min → 15:30
        assert proactivity._hora_local_str(utc, 90) == "30/06 15:30"

    def test_offset_negativo_cruza_medianoche_hacia_atras(self):
        utc = datetime(2026, 7, 1, 0, 30)
        # -60 min → 30/06 23:30
        assert proactivity._hora_local_str(utc, -60) == "30/06 23:30"


# --------------------------------------------------------------------------- #
# _es_recordatorio_importante — detección por palabra clave
# --------------------------------------------------------------------------- #
class TestEsRecordatorioImportante:
    @pytest.mark.parametrize(
        "mensaje",
        [
            "tengo una reunión con el banco",
            "Cita con el dentista",
            "no olvidar el VUELO a Madrid",
            "pago de la factura mañana",
            "entrevista de trabajo el lunes",
        ],
    )
    def test_mensajes_importantes(self, mensaje):
        assert proactivity._es_recordatorio_importante(mensaje) is True

    @pytest.mark.parametrize(
        "mensaje",
        [
            "tomar agua",
            "regar las plantas",
            "estirar un poco",
            "",
        ],
    )
    def test_mensajes_no_importantes(self, mensaje):
        assert proactivity._es_recordatorio_importante(mensaje) is False

    def test_deteccion_por_subcadena_e_insensible_a_mayusculas(self):
        # "boda" aparece como subcadena dentro de la palabra → coincide (comportamiento actual).
        assert proactivity._es_recordatorio_importante("BODA de mi prima") is True
