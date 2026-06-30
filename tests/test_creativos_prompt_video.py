# tests/test_creativos_prompt_video.py — Tests del optimizer bilingüe de video

"""
Cubre `agent/creativos/prompt_video.py` (antes sin test dedicado):
  - `_parsear_en_es`: parser tolerante de la respuesta del LLM (EN/ES) —
    formato canónico, asteriscos markdown, guion en vez de dos puntos,
    comillas externas, multilínea, sin formato, solo EN, solo ES.
  - `optimizar_prompt_video`:
      - Idea vacía → `{"en": "", "es": ""}` sin llamar al LLM.
      - Respuesta OK del LLM → devuelve `{"en": ..., "es": ...}`.
      - LLM cae (excepción) → fallback `{"en": idea+sufijo, "es": idea}`.
      - LLM responde `None` → mismo fallback.
      - Respuesta sin formato EN/ES → texto crudo como EN e idea como ES.
      - Solo ES parseado → EN se rellena con el ES.
      - Solo EN parseado → ES se rellena con la idea original.
      - `tiene_imagen_referencia` selecciona el system prompt correcto
        (image-to-video vs text-to-video).

Todos los tests mockean `agent.llm.completar_con_sistema`: NUNCA se llama al
LLM real. Se fija el COMPORTAMIENTO ACTUAL del módulo, no se cambia.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock


# ── Parser ──────────────────────────────────────────────────────────────────

class TestParserEnEs:
    def test_formato_canonico(self):
        from agent.creativos.prompt_video import _parsear_en_es
        en, es = _parsear_en_es(
            "EN: Cinematic close-up shot of a tiramisu, warm candlelight\n"
            "ES: Plano cinematográfico cercano de un tiramisú, luz cálida de velas"
        )
        assert en.startswith("Cinematic close-up shot")
        assert es.startswith("Plano cinematográfico cercano")

    def test_tolera_asteriscos_markdown(self):
        from agent.creativos.prompt_video import _parsear_en_es
        en, es = _parsear_en_es("**EN:** hello world\n**ES:** hola mundo")
        assert en == "hello world"
        assert es == "hola mundo"

    def test_tolera_guion_en_vez_de_dospuntos(self):
        from agent.creativos.prompt_video import _parsear_en_es
        en, es = _parsear_en_es("EN - foo bar\nES - hola mundo")
        assert en == "foo bar"
        assert es == "hola mundo"

    def test_strip_comillas_externas(self):
        from agent.creativos.prompt_video import _parsear_en_es
        en, es = _parsear_en_es('EN: "a flying dog"\nES: "un perro volando"')
        assert en == "a flying dog"
        assert es == "un perro volando"

    def test_sin_formato_retorna_vacios(self):
        from agent.creativos.prompt_video import _parsear_en_es
        en, es = _parsear_en_es("Respuesta libre sin marcadores.")
        assert en == "" and es == ""

    def test_solo_en(self):
        from agent.creativos.prompt_video import _parsear_en_es
        en, es = _parsear_en_es("EN: a cat walking")
        assert en == "a cat walking"
        assert es == ""

    def test_solo_es(self):
        from agent.creativos.prompt_video import _parsear_en_es
        en, es = _parsear_en_es("ES: un gato caminando")
        assert en == ""
        assert es == "un gato caminando"

    def test_multilinea_en_cada_seccion(self):
        from agent.creativos.prompt_video import _parsear_en_es
        texto = (
            "EN: a cinematic shot\n"
            "of a sunset, slow pan\n"
            "ES: un plano cinematográfico\n"
            "de un atardecer, paneo lento"
        )
        en, es = _parsear_en_es(texto)
        assert "slow pan" in en
        assert "paneo lento" in es

    def test_entrada_none_no_explota(self):
        from agent.creativos.prompt_video import _parsear_en_es
        en, es = _parsear_en_es(None)
        assert en == "" and es == ""


# ── optimizar_prompt_video ───────────────────────────────────────────────────

class TestOptimizarPromptVideo:
    @pytest.mark.asyncio
    async def test_idea_vacia_no_llama_llm(self):
        from agent.creativos.prompt_video import optimizar_prompt_video
        with patch("agent.llm.completar_con_sistema", new=AsyncMock()) as m:
            r = await optimizar_prompt_video("")
            assert r == {"en": "", "es": ""}
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_idea_solo_espacios_no_llama_llm(self):
        from agent.creativos.prompt_video import optimizar_prompt_video
        with patch("agent.llm.completar_con_sistema", new=AsyncMock()) as m:
            r = await optimizar_prompt_video("   \n  ")
            assert r == {"en": "", "es": ""}
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_respuesta_ok_devuelve_en_y_es(self):
        from agent.creativos.prompt_video import optimizar_prompt_video
        fake = AsyncMock(return_value=(
            "EN: Cinematic dolly-in of a tiramisu on an elegant table, golden hour\n"
            "ES: Acercamiento cinematográfico a un tiramisú en una mesa elegante, hora dorada"
        ))
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_video("video de mi tiramisú en un restaurante")
        assert "Cinematic dolly-in" in r["en"]
        assert "Acercamiento cinematográfico" in r["es"]

    @pytest.mark.asyncio
    async def test_llm_falla_fallback_con_sufijo(self):
        """Si el LLM lanza, cae a fallback: idea + sufijo para EN, idea crudo para ES."""
        from agent.creativos.prompt_video import (
            optimizar_prompt_video,
            _SUFIJO_FALLBACK,
        )

        async def _boom(**kw):
            raise RuntimeError("llm down")

        with patch("agent.llm.completar_con_sistema", new=_boom):
            r = await optimizar_prompt_video("gato astronauta")
        assert r["en"] == f"gato astronauta{_SUFIJO_FALLBACK}"
        assert r["es"] == "gato astronauta"

    @pytest.mark.asyncio
    async def test_llm_devuelve_none_fallback(self):
        from agent.creativos.prompt_video import (
            optimizar_prompt_video,
            _SUFIJO_FALLBACK,
        )
        fake = AsyncMock(return_value=None)
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_video("perro corriendo")
        assert r["en"] == f"perro corriendo{_SUFIJO_FALLBACK}"
        assert r["es"] == "perro corriendo"

    @pytest.mark.asyncio
    async def test_respuesta_sin_formato_usa_crudo_como_en(self):
        """Si el LLM no respeta EN/ES, el texto crudo va como EN y la idea como ES."""
        from agent.creativos.prompt_video import optimizar_prompt_video
        fake = AsyncMock(return_value="A beautiful sunset over mountains, cinematic")
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_video("atardecer en las montañas")
        assert r["en"] == "A beautiful sunset over mountains, cinematic"
        assert r["es"] == "atardecer en las montañas"

    @pytest.mark.asyncio
    async def test_solo_es_recibido_rellena_en_con_es(self):
        """Si el parser sólo extrae ES, el EN se rellena con el ES (mejor que nada)."""
        from agent.creativos.prompt_video import optimizar_prompt_video
        fake = AsyncMock(return_value="ES: un gato astronauta flotando")
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_video("gato")
        assert r["en"] == "un gato astronauta flotando"
        assert r["es"] == "un gato astronauta flotando"

    @pytest.mark.asyncio
    async def test_solo_en_recibido_rellena_es_con_idea(self):
        """Si el parser sólo extrae EN, el ES se rellena con la idea original."""
        from agent.creativos.prompt_video import optimizar_prompt_video
        fake = AsyncMock(return_value="EN: a cinematic flying cat")
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_video("gato volador")
        assert r["en"] == "a cinematic flying cat"
        assert r["es"] == "gato volador"

    @pytest.mark.asyncio
    async def test_imagen_referencia_usa_sistema_image_to_video(self):
        """`tiene_imagen_referencia=True` debe usar el system prompt image-to-video."""
        from agent.creativos.prompt_video import (
            optimizar_prompt_video,
            _SISTEMA_IMAGEN_A_VIDEO,
        )
        fake = AsyncMock(return_value="EN: orbit\nES: órbita")
        with patch("agent.llm.completar_con_sistema", new=fake):
            await optimizar_prompt_video("animá mi foto", tiene_imagen_referencia=True)
        _, kwargs = fake.call_args
        assert kwargs.get("system") == _SISTEMA_IMAGEN_A_VIDEO

    @pytest.mark.asyncio
    async def test_sin_imagen_usa_sistema_texto_a_video(self):
        from agent.creativos.prompt_video import (
            optimizar_prompt_video,
            _SISTEMA_TEXTO_A_VIDEO,
        )
        fake = AsyncMock(return_value="EN: cat\nES: gato")
        with patch("agent.llm.completar_con_sistema", new=fake):
            await optimizar_prompt_video("un gato", tiene_imagen_referencia=False)
        _, kwargs = fake.call_args
        assert kwargs.get("system") == _SISTEMA_TEXTO_A_VIDEO
