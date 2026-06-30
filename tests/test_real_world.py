# tests/test_real_world.py — cobertura de agent/real_world.py

"""
Fija el comportamiento ACTUAL de las integraciones con el mundo real de Dona:

  * obtener_clima        — parseo del pronóstico de OpenWeather, mapeo de iconos,
                           flag de lluvia, redondeo de temperatura y ramas de error.
  * hay_lluvia_en_horas  — ventana de ±2h alrededor de una hora dada.
  * resumen_clima_str    — formateo puro de la frase del morning brief.
  * obtener_noticias     — parseo de NewsAPI y hash de URL.
  * extraer_industria    — pre-filtros (longitud) + normalización del LLM.
  * calcular_trafico     — parseo de Distance Matrix y fallback de tráfico.

Toda llamada HTTP (`httpx.AsyncClient`) y el LLM (`agent.llm.completar_texto`) se
mockean SIEMPRE — nunca llamada real. Las API keys de módulo se inyectan con
`monkeypatch.setattr` (el módulo las lee a nivel de import). Estos tests cubren
ramas puras, de parseo y de error; no cambian la lógica de producción.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import agent.real_world as rw
import httpx
import pytest


# --------------------------------------------------------------------------- #
# Helpers de mock HTTP
# --------------------------------------------------------------------------- #
def _resp(json_data=None, raise_exc=None):
    r = MagicMock()
    r.json = MagicMock(return_value=json_data or {})
    if raise_exc:
        r.raise_for_status = MagicMock(side_effect=raise_exc)
    else:
        r.raise_for_status = MagicMock(return_value=None)
    return r


def _patch_get(get_result):
    """Devuelve un context manager que parchea httpx.AsyncClient para que
    client.get(...) devuelva `get_result` (una respuesta) o lance si es Exception."""
    client = MagicMock()
    if isinstance(get_result, Exception):
        client.get = AsyncMock(side_effect=get_result)
    else:
        client.get = AsyncMock(return_value=get_result)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return patch("agent.real_world.httpx.AsyncClient", MagicMock(return_value=ctx))


def _clima_payload(items):
    return {"list": items}


def _item_clima(main, descripcion, temp, dt_txt="2026-06-29 12:00:00"):
    return {
        "dt_txt": dt_txt,
        "main": {"temp": temp},
        "weather": [{"main": main, "description": descripcion}],
    }


# --------------------------------------------------------------------------- #
# obtener_clima
# --------------------------------------------------------------------------- #
class TestObtenerClima:
    @pytest.mark.asyncio
    async def test_sin_key_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(rw, "OPENWEATHER_KEY", "")
        assert await rw.obtener_clima("Orlando") is None

    @pytest.mark.asyncio
    async def test_sin_ciudad_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(rw, "OPENWEATHER_KEY", "k")
        assert await rw.obtener_clima("") is None

    @pytest.mark.asyncio
    async def test_parseo_basico(self, monkeypatch):
        monkeypatch.setattr(rw, "OPENWEATHER_KEY", "k")
        payload = _clima_payload([_item_clima("Clear", "cielo despejado", 24.7)])
        with _patch_get(_resp(payload)):
            res = await rw.obtener_clima("Orlando")
        assert res is not None and len(res) == 1
        p = res[0]
        assert p["temp"] == 25  # 24.7 redondeado
        assert p["descripcion"] == "Cielo despejado"  # capitalize
        assert p["icono"] == "☀️ despejado"
        assert p["llueve"] is False
        assert p["main"] == "clear"

    @pytest.mark.asyncio
    async def test_lluvia_marca_flag(self, monkeypatch):
        monkeypatch.setattr(rw, "OPENWEATHER_KEY", "k")
        payload = _clima_payload([_item_clima("Rain", "lluvia ligera", 18)])
        with _patch_get(_resp(payload)):
            res = await rw.obtener_clima("Orlando")
        assert res[0]["llueve"] is True
        assert res[0]["icono"] == "🌧️ lluvia"

    @pytest.mark.asyncio
    async def test_main_desconocido_usa_icono_por_defecto(self, monkeypatch):
        monkeypatch.setattr(rw, "OPENWEATHER_KEY", "k")
        payload = _clima_payload([_item_clima("Tornado", "tornado", 30)])
        with _patch_get(_resp(payload)):
            res = await rw.obtener_clima("Orlando")
        assert res[0]["icono"] == "🌤️"
        assert res[0]["llueve"] is False

    @pytest.mark.asyncio
    async def test_lista_vacia_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(rw, "OPENWEATHER_KEY", "k")
        with _patch_get(_resp(_clima_payload([]))):
            assert await rw.obtener_clima("Orlando") is None

    @pytest.mark.asyncio
    async def test_error_http_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(rw, "OPENWEATHER_KEY", "k")
        with _patch_get(RuntimeError("API caída")):
            assert await rw.obtener_clima("Orlando") is None


# --------------------------------------------------------------------------- #
# hay_lluvia_en_horas
# --------------------------------------------------------------------------- #
class TestHayLluviaEnHoras:
    @pytest.mark.asyncio
    async def test_sin_pronostico_devuelve_false(self, monkeypatch):
        async def fake_clima(ciudad):
            return None
        monkeypatch.setattr(rw, "obtener_clima", fake_clima)
        assert await rw.hay_lluvia_en_horas("Orlando", datetime(2026, 6, 29, 12)) is False

    @pytest.mark.asyncio
    async def test_lluvia_dentro_de_la_ventana(self, monkeypatch):
        async def fake_clima(ciudad):
            return [{"hora": "2026-06-29 13:00:00", "llueve": True}]
        monkeypatch.setattr(rw, "obtener_clima", fake_clima)
        # 13:00 está a 1h de 12:00 → dentro de ±2h
        assert await rw.hay_lluvia_en_horas("Orlando", datetime(2026, 6, 29, 12)) is True

    @pytest.mark.asyncio
    async def test_lluvia_fuera_de_la_ventana(self, monkeypatch):
        async def fake_clima(ciudad):
            return [{"hora": "2026-06-29 18:00:00", "llueve": True}]
        monkeypatch.setattr(rw, "obtener_clima", fake_clima)
        # 18:00 está a 6h de 12:00 → fuera de ±2h
        assert await rw.hay_lluvia_en_horas("Orlando", datetime(2026, 6, 29, 12)) is False

    @pytest.mark.asyncio
    async def test_sin_lluvia_en_ventana_devuelve_false(self, monkeypatch):
        async def fake_clima(ciudad):
            return [{"hora": "2026-06-29 12:00:00", "llueve": False}]
        monkeypatch.setattr(rw, "obtener_clima", fake_clima)
        assert await rw.hay_lluvia_en_horas("Orlando", datetime(2026, 6, 29, 12)) is False

    @pytest.mark.asyncio
    async def test_hora_malformada_se_ignora(self, monkeypatch):
        async def fake_clima(ciudad):
            return [{"hora": "fecha-basura", "llueve": True}]
        monkeypatch.setattr(rw, "obtener_clima", fake_clima)
        assert await rw.hay_lluvia_en_horas("Orlando", datetime(2026, 6, 29, 12)) is False


# --------------------------------------------------------------------------- #
# resumen_clima_str — puro
# --------------------------------------------------------------------------- #
class TestResumenClimaStr:
    def test_vacio_devuelve_cadena_vacia(self):
        assert rw.resumen_clima_str([]) == ""
        assert rw.resumen_clima_str(None) == ""

    def test_sin_lluvia(self):
        pron = [{"icono": "☀️ despejado", "descripcion": "Despejado", "temp": 28, "llueve": False}]
        frase = rw.resumen_clima_str(pron)
        assert frase == "☀️ despejado Despejado, 28°C"
        assert "lluvia" not in frase

    def test_con_lluvia_agrega_aviso(self):
        pron = [
            {"icono": "☁️ nublado", "descripcion": "Nublado", "temp": 20, "llueve": False},
            {"icono": "🌧️ lluvia", "descripcion": "Lluvia", "temp": 19, "llueve": True},
        ]
        frase = rw.resumen_clima_str(pron)
        # Usa el primer elemento para icono/descripcion/temp...
        assert frase.startswith("☁️ nublado Nublado, 20°C")
        # ...pero detecta lluvia en cualquier elemento del día.
        assert "lluvia prevista" in frase


# --------------------------------------------------------------------------- #
# obtener_noticias
# --------------------------------------------------------------------------- #
class TestObtenerNoticias:
    @pytest.mark.asyncio
    async def test_sin_key_devuelve_lista_vacia(self, monkeypatch):
        monkeypatch.setattr(rw, "NEWS_API_KEY", "")
        assert await rw.obtener_noticias("logística") == []

    @pytest.mark.asyncio
    async def test_sin_industria_devuelve_lista_vacia(self, monkeypatch):
        monkeypatch.setattr(rw, "NEWS_API_KEY", "k")
        assert await rw.obtener_noticias("") == []

    @pytest.mark.asyncio
    async def test_parseo_y_hash_de_url(self, monkeypatch):
        import hashlib
        monkeypatch.setattr(rw, "NEWS_API_KEY", "k")
        url = "https://ejemplo.com/nota"
        payload = {"articles": [{"title": "Titular", "description": "Resumen", "url": url}]}
        with _patch_get(_resp(payload)):
            res = await rw.obtener_noticias("logística")
        assert len(res) == 1
        art = res[0]
        assert art["titulo"] == "Titular"
        assert art["resumen"] == "Resumen"
        assert art["url"] == url
        assert art["url_hash"] == hashlib.md5(url.encode()).hexdigest()[:16]

    @pytest.mark.asyncio
    async def test_campos_faltantes_usan_default_vacio(self, monkeypatch):
        monkeypatch.setattr(rw, "NEWS_API_KEY", "k")
        payload = {"articles": [{}]}
        with _patch_get(_resp(payload)):
            res = await rw.obtener_noticias("logística")
        assert res[0]["titulo"] == ""
        assert res[0]["resumen"] == ""
        assert res[0]["url"] == ""

    @pytest.mark.asyncio
    async def test_error_http_devuelve_lista_vacia(self, monkeypatch):
        monkeypatch.setattr(rw, "NEWS_API_KEY", "k")
        with _patch_get(RuntimeError("NewsAPI caída")):
            assert await rw.obtener_noticias("logística") == []


# --------------------------------------------------------------------------- #
# extraer_industria
# --------------------------------------------------------------------------- #
class TestExtraerIndustria:
    @pytest.mark.asyncio
    async def test_contexto_corto_devuelve_none(self):
        assert await rw.extraer_industria("muy corto") is None

    @pytest.mark.asyncio
    async def test_contexto_vacio_devuelve_none(self):
        assert await rw.extraer_industria("") is None

    @pytest.mark.asyncio
    async def test_normaliza_respuesta_del_llm(self, monkeypatch):
        async def fake_completar(prompt, max_tokens=20):
            return "  Logística  "
        import agent.llm as llm
        monkeypatch.setattr(llm, "completar_texto", fake_completar)
        ctx = "x" * 60  # >= 50 chars para pasar el pre-filtro
        assert await rw.extraer_industria(ctx) == "logística"

    @pytest.mark.asyncio
    async def test_respuesta_demasiado_larga_devuelve_none(self, monkeypatch):
        async def fake_completar(prompt, max_tokens=20):
            return "a" * 45  # >= 40 chars → se descarta
        import agent.llm as llm
        monkeypatch.setattr(llm, "completar_texto", fake_completar)
        assert await rw.extraer_industria("x" * 60) is None

    @pytest.mark.asyncio
    async def test_llm_vacio_devuelve_none(self, monkeypatch):
        async def fake_completar(prompt, max_tokens=20):
            return ""
        import agent.llm as llm
        monkeypatch.setattr(llm, "completar_texto", fake_completar)
        assert await rw.extraer_industria("x" * 60) is None

    @pytest.mark.asyncio
    async def test_llm_explota_devuelve_none(self, monkeypatch):
        async def fake_boom(prompt, max_tokens=20):
            raise RuntimeError("LLM caído")
        import agent.llm as llm
        monkeypatch.setattr(llm, "completar_texto", fake_boom)
        assert await rw.extraer_industria("x" * 60) is None


# --------------------------------------------------------------------------- #
# calcular_trafico
# --------------------------------------------------------------------------- #
class TestCalcularTrafico:
    @pytest.mark.asyncio
    async def test_sin_key_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(rw, "MAPS_API_KEY", "")
        assert await rw.calcular_trafico("A", "B") is None

    @pytest.mark.asyncio
    async def test_sin_origen_o_destino_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(rw, "MAPS_API_KEY", "k")
        assert await rw.calcular_trafico("", "B") is None
        assert await rw.calcular_trafico("A", "") is None

    @pytest.mark.asyncio
    async def test_con_trafico(self, monkeypatch):
        monkeypatch.setattr(rw, "MAPS_API_KEY", "k")
        payload = {
            "rows": [{"elements": [{
                "status": "OK",
                "duration": {"value": 600},            # 10 min
                "duration_in_traffic": {"value": 900},  # 15 min
            }]}]
        }
        with _patch_get(_resp(payload)):
            res = await rw.calcular_trafico("A", "B")
        assert res == {"normal_min": 10, "trafico_min": 15, "delay_min": 5}

    @pytest.mark.asyncio
    async def test_sin_duration_in_traffic_usa_fallback(self, monkeypatch):
        monkeypatch.setattr(rw, "MAPS_API_KEY", "k")
        payload = {
            "rows": [{"elements": [{
                "status": "OK",
                "duration": {"value": 600},  # 10 min, sin duration_in_traffic
            }]}]
        }
        with _patch_get(_resp(payload)):
            res = await rw.calcular_trafico("A", "B")
        assert res == {"normal_min": 10, "trafico_min": 10, "delay_min": 0}

    @pytest.mark.asyncio
    async def test_status_no_ok_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(rw, "MAPS_API_KEY", "k")
        payload = {"rows": [{"elements": [{"status": "ZERO_RESULTS"}]}]}
        with _patch_get(_resp(payload)):
            assert await rw.calcular_trafico("A", "B") is None

    @pytest.mark.asyncio
    async def test_error_http_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(rw, "MAPS_API_KEY", "k")
        with _patch_get(RuntimeError("Maps caída")):
            assert await rw.calcular_trafico("A", "B") is None
