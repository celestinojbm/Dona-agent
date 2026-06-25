# tests/test_emotion_deteccion.py — cobertura de agent/emotion.py

"""
Fija el comportamiento ACTUAL de la inteligencia emocional de Dona:

  * _es_crisis                    — detección rápida por palabras clave (sin LLM),
                                    case-insensitive y por subcadena.
  * detectar_emocion              — atajo de crisis sin LLM; parseo del JSON del
                                    LLM (con texto extra alrededor) y todas las
                                    ramas de fallback a "neutral".
  * obtener_instrucciones_tono    — mapeo puro estado → instrucciones, fallback a
                                    neutral, y sufijo de validación condicional.
  * obtener_contexto_emocional_str — línea de contexto solo si es reciente (<2h)
                                    y no neutral.

El LLM (`agent.llm.completar_texto`) se mockea SIEMPRE — nunca llamada real.
Estos tests cubren ramas puras / de parseo; no cambian la lógica de producción.
"""

from datetime import datetime, timedelta

import agent.emotion as emotion
import pytest


# --------------------------------------------------------------------------- #
# Helpers de mock del LLM
# --------------------------------------------------------------------------- #
def _mock_llm(monkeypatch, respuesta):
    """Mockea agent.llm.completar_texto para devolver `respuesta` y registrar si
    fue invocado. emotion importa completar_texto de forma perezosa dentro de la
    función, así que parchear el módulo agent.llm es suficiente."""
    llamadas = {"n": 0}

    async def fake_completar_texto(prompt, max_tokens=500, telefono=""):
        llamadas["n"] += 1
        return respuesta

    import agent.llm as llm
    monkeypatch.setattr(llm, "completar_texto", fake_completar_texto)
    return llamadas


def _mock_llm_explota(monkeypatch):
    """Mockea completar_texto para que lance — debe capturarse y → neutral."""
    async def fake_boom(prompt, max_tokens=500, telefono=""):
        raise RuntimeError("LLM caído")

    import agent.llm as llm
    monkeypatch.setattr(llm, "completar_texto", fake_boom)


# --------------------------------------------------------------------------- #
# _es_crisis — detección pura por palabras clave
# --------------------------------------------------------------------------- #
class TestEsCrisis:
    @pytest.mark.parametrize("frase", sorted(emotion._PALABRAS_CRISIS))
    def test_cada_palabra_clave_dispara_crisis(self, frase):
        assert emotion._es_crisis(frase) is True

    def test_subcadena_dentro_de_mensaje_largo(self):
        msg = "Hoy estuvo pesado y la verdad ya no aguanto esta situación"
        assert emotion._es_crisis(msg) is True

    def test_case_insensitive(self):
        assert emotion._es_crisis("ME QUIERO MORIR") is True

    @pytest.mark.parametrize("texto", [
        "",
        "Todo bien, gracias",
        "Necesito que me ayudes con una factura",
        "Estoy cansado pero le sigo dando",
    ])
    def test_mensajes_no_crisis(self, texto):
        assert emotion._es_crisis(texto) is False


# --------------------------------------------------------------------------- #
# detectar_emocion — atajo de crisis + parseo del LLM + fallbacks
# --------------------------------------------------------------------------- #
class TestDetectarEmocion:
    async def test_crisis_no_llama_al_llm(self, monkeypatch):
        llamadas = _mock_llm(monkeypatch, '{"state":"neutral"}')
        res = await emotion.detectar_emocion("me quiero morir")
        assert res["state"] == "crisis"
        assert res["intensity"] == 3
        assert res["needs_validation"] is True
        # El atajo de crisis no debe gastar el LLM.
        assert llamadas["n"] == 0

    async def test_json_valido_se_parsea(self, monkeypatch):
        payload = (
            '{"state":"stress","intensity":2,'
            '"needs_validation":true,"contexto":"mucho trabajo"}'
        )
        llamadas = _mock_llm(monkeypatch, payload)
        res = await emotion.detectar_emocion("tengo mil cosas encima")
        assert res == {
            "state": "stress",
            "intensity": 2,
            "needs_validation": True,
            "contexto": "mucho trabajo",
        }
        assert llamadas["n"] == 1

    async def test_json_con_texto_alrededor_se_extrae(self, monkeypatch):
        ruido = (
            'Claro, aquí tienes el análisis:\n'
            '{"state":"celebration","intensity":3,"needs_validation":false,'
            '"contexto":"cerró un trato"}\n¡Espero que sirva!'
        )
        _mock_llm(monkeypatch, ruido)
        res = await emotion.detectar_emocion("¡cerré el trato!")
        assert res["state"] == "celebration"
        assert res["intensity"] == 3

    async def test_contexto_usuario_se_acepta(self, monkeypatch):
        # El contexto (incluso largo) no debe romper la llamada.
        _mock_llm(monkeypatch, '{"state":"neutral"}')
        res = await emotion.detectar_emocion("hola", contexto_usuario="x" * 500)
        assert res["state"] == "neutral"

    async def test_respuesta_vacia_cae_a_neutral(self, monkeypatch):
        _mock_llm(monkeypatch, "")
        res = await emotion.detectar_emocion("mensaje cualquiera")
        assert res == {
            "state": "neutral",
            "intensity": 1,
            "needs_validation": False,
            "contexto": "",
        }

    async def test_json_invalido_cae_a_neutral(self, monkeypatch):
        _mock_llm(monkeypatch, "no soy json {{")
        res = await emotion.detectar_emocion("mensaje cualquiera")
        assert res["state"] == "neutral"

    async def test_json_sin_state_cae_a_neutral(self, monkeypatch):
        _mock_llm(monkeypatch, '{"intensity":2,"needs_validation":true}')
        res = await emotion.detectar_emocion("mensaje cualquiera")
        assert res["state"] == "neutral"

    async def test_llm_explota_cae_a_neutral(self, monkeypatch):
        _mock_llm_explota(monkeypatch)
        res = await emotion.detectar_emocion("mensaje cualquiera")
        assert res["state"] == "neutral"


# --------------------------------------------------------------------------- #
# obtener_instrucciones_tono — mapeo puro estado → instrucciones
# --------------------------------------------------------------------------- #
class TestObtenerInstruccionesTono:
    @pytest.mark.parametrize("state", [
        "stress", "frustration", "exhaustion",
        "celebration", "anxiety", "crisis", "neutral",
    ])
    def test_cada_estado_devuelve_instrucciones(self, state):
        out = emotion.obtener_instrucciones_tono({"state": state}, "Celestino")
        assert isinstance(out, str)
        assert out  # no vacío

    def test_estado_desconocido_cae_a_neutral(self):
        desconocido = emotion.obtener_instrucciones_tono(
            {"state": "marciano"}, "Celestino"
        )
        neutral = emotion.obtener_instrucciones_tono(
            {"state": "neutral"}, "Celestino"
        )
        assert desconocido == neutral

    def test_emotion_vacio_usa_neutral(self):
        out = emotion.obtener_instrucciones_tono({}, "Celestino")
        neutral = emotion.obtener_instrucciones_tono(
            {"state": "neutral"}, "Celestino"
        )
        assert out == neutral

    def test_nombre_se_interpola(self):
        out = emotion.obtener_instrucciones_tono(
            {"state": "stress", "intensity": 2}, "Celestino"
        )
        assert "Celestino" in out
        assert "2/3" in out

    @pytest.mark.parametrize("state", ["stress", "frustration", "exhaustion", "anxiety"])
    def test_needs_validation_agrega_sufijo(self, state):
        out = emotion.obtener_instrucciones_tono(
            {"state": state, "needs_validation": True}, "Celestino"
        )
        assert "ANTES de recibir soluciones" in out

    @pytest.mark.parametrize("state", ["neutral", "celebration", "crisis"])
    def test_needs_validation_no_agrega_sufijo_en_estos_estados(self, state):
        out = emotion.obtener_instrucciones_tono(
            {"state": state, "needs_validation": True}, "Celestino"
        )
        assert "ANTES de recibir soluciones" not in out

    def test_sin_needs_validation_no_agrega_sufijo(self):
        out = emotion.obtener_instrucciones_tono(
            {"state": "stress", "needs_validation": False}, "Celestino"
        )
        assert "ANTES de recibir soluciones" not in out


# --------------------------------------------------------------------------- #
# obtener_contexto_emocional_str — línea de contexto reciente
# --------------------------------------------------------------------------- #
class TestObtenerContextoEmocionalStr:
    def test_neutral_devuelve_vacio(self):
        ahora = datetime.utcnow()
        assert emotion.obtener_contexto_emocional_str("neutral", 1, ahora) == ""

    def test_actualizado_none_devuelve_vacio(self):
        assert emotion.obtener_contexto_emocional_str("stress", 2, None) == ""

    def test_estado_viejo_devuelve_vacio(self):
        viejo = datetime.utcnow() - timedelta(hours=3)
        assert emotion.obtener_contexto_emocional_str("stress", 2, viejo) == ""

    def test_estado_reciente_no_neutral_devuelve_linea(self):
        reciente = datetime.utcnow() - timedelta(minutes=30)
        out = emotion.obtener_contexto_emocional_str("stress", 2, reciente)
        assert "stress" in out
        assert "2/3" in out
        assert out.startswith("[") and out.endswith("]")
