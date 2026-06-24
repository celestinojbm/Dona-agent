# tests/test_location_deteccion.py — cobertura de agent/location.py

"""
Fija el comportamiento ACTUAL de la detección de ubicación dinámica:

  * parece_viaje      — pre-filtro barato por palabras clave (sin LLM).
  * detectar_viaje    — viaje temporal; parseo "VIAJE: <ciudad>, <días>",
                        clamp de días [1, 30], title-case y ramas de error.
  * es_ciudad_suelta  — pre-filtros (longitud, nº de palabras, verbo inicial,
                        capitalización, respuestas comunes) antes del LLM.

El LLM (`agent.llm.completar_texto`) se mockea SIEMPRE — nunca llamada real.
Estos tests cubren ramas puras y de parseo; no cambian la lógica de producción.
"""

import agent.location as location
import pytest


# --------------------------------------------------------------------------- #
# Helpers de mock del LLM
# --------------------------------------------------------------------------- #
def _mock_llm(monkeypatch, respuesta):
    """Mockea agent.llm.completar_texto para devolver `respuesta` y registrar
    si fue invocado. location importa completar_texto de forma perezosa, así
    que parchear el módulo agent.llm es suficiente."""
    llamadas = {"n": 0}

    async def fake_completar_texto(prompt, max_tokens=500, telefono=""):
        llamadas["n"] += 1
        return respuesta

    import agent.llm as llm
    monkeypatch.setattr(llm, "completar_texto", fake_completar_texto)
    return llamadas


def _mock_llm_explota(monkeypatch):
    """Mockea completar_texto para que lance — debe ser capturado y → None."""
    async def fake_boom(prompt, max_tokens=500, telefono=""):
        raise RuntimeError("LLM caído")

    import agent.llm as llm
    monkeypatch.setattr(llm, "completar_texto", fake_boom)


# --------------------------------------------------------------------------- #
# parece_viaje — pre-filtro puro
# --------------------------------------------------------------------------- #
class TestPareceViaje:
    @pytest.mark.parametrize("texto", [
        "Estoy en Bogotá esta semana",
        "Llegué a Miami ayer",
        "Viajé de trabajo a Monterrey",
        "Estoy de paso por Lima",
        "Vine a Madrid por unos días",
        "Aterricé hace una hora",
        "Me encuentro en Cancún",
        "Estoy visitando a mi familia",
    ])
    def test_detecta_palabras_de_viaje(self, texto):
        assert location.parece_viaje(texto) is True

    @pytest.mark.parametrize("texto", [
        "Tengo una reunión mañana",
        "Hola, cómo estás",
        "Necesito ayuda con un correo",
        "",
        "estoy enojado contigo",  # 'estoy en ' requiere espacio tras 'en'
    ])
    def test_ignora_texto_sin_viaje(self, texto):
        assert location.parece_viaje(texto) is False

    def test_es_insensible_a_mayusculas(self):
        assert location.parece_viaje("VIAJÉ A PARÍS") is True


# --------------------------------------------------------------------------- #
# detectar_viaje — async, parseo + clamp
# --------------------------------------------------------------------------- #
class TestDetectarViaje:
    async def test_sin_prefiltro_no_llama_al_llm(self, monkeypatch):
        llamadas = _mock_llm(monkeypatch, "VIAJE: Miami, 3")
        resultado = await location.detectar_viaje("Tengo una reunión mañana")
        assert resultado is None
        assert llamadas["n"] == 0  # el pre-filtro corta antes del LLM

    async def test_viaje_con_ciudad_y_dias(self, monkeypatch):
        _mock_llm(monkeypatch, "VIAJE: Miami, 3")
        resultado = await location.detectar_viaje("Llegué a Miami ayer")
        assert resultado == {"ciudad": "Miami", "dias": 3}

    async def test_ciudad_se_normaliza_a_title_case(self, monkeypatch):
        _mock_llm(monkeypatch, "VIAJE: san juan, 5")
        resultado = await location.detectar_viaje("Viajé a san juan")
        assert resultado == {"ciudad": "San Juan", "dias": 5}

    async def test_respuesta_no_devuelve_none(self, monkeypatch):
        _mock_llm(monkeypatch, "NO")
        resultado = await location.detectar_viaje("Estoy en casa tranquilo viaj")
        assert resultado is None

    async def test_dias_se_limita_a_30(self, monkeypatch):
        _mock_llm(monkeypatch, "VIAJE: Tokio, 365")
        resultado = await location.detectar_viaje("Viajé a Tokio")
        assert resultado == {"ciudad": "Tokio", "dias": 30}

    async def test_dias_minimo_es_1(self, monkeypatch):
        _mock_llm(monkeypatch, "VIAJE: Lima, 0")
        resultado = await location.detectar_viaje("Viajé a Lima")
        assert resultado == {"ciudad": "Lima", "dias": 1}

    async def test_dias_negativos_se_elevan_a_1(self, monkeypatch):
        _mock_llm(monkeypatch, "VIAJE: Quito, -7")
        resultado = await location.detectar_viaje("Viajé a Quito")
        assert resultado == {"ciudad": "Quito", "dias": 1}

    async def test_dias_no_numericos_usan_default_3(self, monkeypatch):
        _mock_llm(monkeypatch, "VIAJE: Oslo, mañana")
        resultado = await location.detectar_viaje("Viajé a Oslo")
        assert resultado == {"ciudad": "Oslo", "dias": 3}

    async def test_sin_dias_usa_default_3(self, monkeypatch):
        _mock_llm(monkeypatch, "VIAJE: Berlín")
        resultado = await location.detectar_viaje("Viajé a Berlín")
        assert resultado == {"ciudad": "Berlín", "dias": 3}

    async def test_ciudad_vacia_devuelve_none(self, monkeypatch):
        _mock_llm(monkeypatch, "VIAJE: , 4")
        resultado = await location.detectar_viaje("Viajé sin destino claro")
        assert resultado is None

    async def test_llm_none_devuelve_none(self, monkeypatch):
        _mock_llm(monkeypatch, None)
        resultado = await location.detectar_viaje("Viajé a algún lugar")
        assert resultado is None

    async def test_excepcion_del_llm_devuelve_none(self, monkeypatch):
        _mock_llm_explota(monkeypatch)
        resultado = await location.detectar_viaje("Viajé a ningún lado")
        assert resultado is None


# --------------------------------------------------------------------------- #
# es_ciudad_suelta — async, muchos pre-filtros antes del LLM
# --------------------------------------------------------------------------- #
class TestEsCiudadSuelta:
    @pytest.mark.parametrize("texto", [
        "una dos tres cuatro cinco",   # > 4 palabras
        "",                            # vacío
        "   ",                         # solo espacios
        "Ab",                          # < 3 caracteres
    ])
    async def test_prefiltros_de_forma_cortan_antes_del_llm(self, monkeypatch, texto):
        llamadas = _mock_llm(monkeypatch, "CIUDAD: Algo")
        resultado = await location.es_ciudad_suelta(texto)
        assert resultado is None
        assert llamadas["n"] == 0

    @pytest.mark.parametrize("texto", [
        "Vivo en Miami",   # empieza con verbo
        "Soy de Lima",
        "Estoy aquí",
        "Mi ciudad favorita",
    ])
    async def test_verbo_o_pronombre_inicial_corta(self, monkeypatch, texto):
        llamadas = _mock_llm(monkeypatch, "CIUDAD: Algo")
        resultado = await location.es_ciudad_suelta(texto)
        assert resultado is None
        assert llamadas["n"] == 0

    @pytest.mark.parametrize("texto", ["miami", "bogota", "lima peru"])
    async def test_sin_mayuscula_inicial_corta(self, monkeypatch, texto):
        llamadas = _mock_llm(monkeypatch, "CIUDAD: Algo")
        resultado = await location.es_ciudad_suelta(texto)
        assert resultado is None
        assert llamadas["n"] == 0

    @pytest.mark.parametrize("texto", ["Hola", "Gracias", "Listo", "Perfecto"])
    async def test_respuestas_comunes_no_son_ciudades(self, monkeypatch, texto):
        llamadas = _mock_llm(monkeypatch, "CIUDAD: Algo")
        resultado = await location.es_ciudad_suelta(texto)
        assert resultado is None
        assert llamadas["n"] == 0

    async def test_ciudad_valida_llama_al_llm_y_normaliza(self, monkeypatch):
        llamadas = _mock_llm(monkeypatch, "CIUDAD: miami")
        resultado = await location.es_ciudad_suelta("Miami")
        assert resultado == "Miami"
        assert llamadas["n"] == 1

    async def test_ciudad_dos_palabras_valida(self, monkeypatch):
        _mock_llm(monkeypatch, "CIUDAD: San José")
        resultado = await location.es_ciudad_suelta("San José")
        assert resultado == "San José"

    async def test_llm_dice_no(self, monkeypatch):
        _mock_llm(monkeypatch, "NO")
        resultado = await location.es_ciudad_suelta("Xqzptv")
        assert resultado is None

    async def test_llm_none_devuelve_none(self, monkeypatch):
        _mock_llm(monkeypatch, None)
        resultado = await location.es_ciudad_suelta("Algo")
        assert resultado is None

    async def test_ciudad_vacia_del_llm_devuelve_none(self, monkeypatch):
        _mock_llm(monkeypatch, "CIUDAD: ")
        resultado = await location.es_ciudad_suelta("Cualquiera")
        assert resultado is None

    async def test_excepcion_del_llm_devuelve_none(self, monkeypatch):
        _mock_llm_explota(monkeypatch)
        resultado = await location.es_ciudad_suelta("Veracruz")
        assert resultado is None
