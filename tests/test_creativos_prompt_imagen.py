# tests/test_creativos_prompt_imagen.py — Tests del optimizer bilingüe de imagen

"""
Cubre:
  - `_parsear_en_es`: parser tolerante de la respuesta del LLM (EN/ES).
  - `optimizar_prompt_imagen`:
      - Respuesta OK del LLM → devuelve `{"en": ..., "es": ...}`.
      - LLM cae (excepción) → fallback `{"en": idea+sufijo, "es": idea}`.
      - LLM responde `None` → mismo fallback.
      - Respuesta sin formato EN/ES → caller usa texto crudo como EN y
        idea como ES (último recurso).
      - Idea vacía → `{"en": "", "es": ""}` sin llamar al LLM.
      - Calidad "premium" → usa el system prompt premium (Ideogram-oriented).
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock


# ── Parser ──────────────────────────────────────────────────────────────────

class TestParserEnEs:
    def test_formato_canonico(self):
        from agent.creativos.prompt_imagen import _parsear_en_es
        en, es = _parsear_en_es(
            "EN: A cat astronaut floating in space, cinematic lighting\n"
            "ES: Un gato astronauta flotando en el espacio, iluminación cinematográfica"
        )
        assert en.startswith("A cat astronaut")
        assert es.startswith("Un gato astronauta")

    def test_tolera_asteriscos_markdown(self):
        from agent.creativos.prompt_imagen import _parsear_en_es
        en, es = _parsear_en_es("**EN:** hello world\n**ES:** hola mundo")
        assert en == "hello world"
        assert es == "hola mundo"

    def test_tolera_guion_en_vez_de_dospuntos(self):
        from agent.creativos.prompt_imagen import _parsear_en_es
        en, es = _parsear_en_es("EN - foo bar\nES - hola mundo")
        assert en == "foo bar"
        assert es == "hola mundo"

    def test_strip_comillas_externas(self):
        from agent.creativos.prompt_imagen import _parsear_en_es
        en, es = _parsear_en_es('EN: "a dog"\nES: "un perro"')
        assert en == "a dog"
        assert es == "un perro"

    def test_sin_formato_retorna_vacios(self):
        from agent.creativos.prompt_imagen import _parsear_en_es
        en, es = _parsear_en_es("Respuesta libre sin EN ni ES.")
        assert en == "" and es == ""

    def test_solo_en(self):
        from agent.creativos.prompt_imagen import _parsear_en_es
        en, es = _parsear_en_es("EN: a cat")
        assert en == "a cat"
        assert es == ""

    def test_multilinea_en_cada_seccion(self):
        from agent.creativos.prompt_imagen import _parsear_en_es
        texto = (
            "EN: a cat astronaut\n"
            "floating in space, cinematic\n"
            "ES: un gato astronauta\n"
            "flotando en el espacio, cinematográfico"
        )
        en, es = _parsear_en_es(texto)
        assert "floating in space" in en
        assert "flotando en el espacio" in es


# ── optimizar_prompt_imagen ─────────────────────────────────────────────────

class TestOptimizarPromptImagen:
    @pytest.mark.asyncio
    async def test_idea_vacia_no_llama_llm(self):
        from agent.creativos.prompt_imagen import optimizar_prompt_imagen
        with patch("agent.llm.completar_con_sistema", new=AsyncMock()) as m:
            r = await optimizar_prompt_imagen("")
            assert r == {"en": "", "es": ""}
            m.assert_not_called()

    @pytest.mark.asyncio
    async def test_respuesta_ok_devuelve_en_y_es(self):
        from agent.creativos.prompt_imagen import optimizar_prompt_imagen
        fake = AsyncMock(return_value=(
            "EN: Modern minimalist pizza logo, warm red palette, vector style\n"
            "ES: Logo minimalista moderno de pizza, paleta rojo cálido, estilo vector"
        ))
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_imagen("logo de pizza para mi local")
        assert "Modern minimalist pizza" in r["en"]
        assert "minimalista moderno" in r["es"]

    @pytest.mark.asyncio
    async def test_llm_falla_fallback_con_sufijo(self):
        """Si el LLM lanza, cae a fallback: idea + sufijo para EN, idea crudo para ES."""
        from agent.creativos.prompt_imagen import optimizar_prompt_imagen, _SUFIJO_FALLBACK

        async def _boom(**kw):
            raise RuntimeError("llm down")

        with patch("agent.llm.completar_con_sistema", new=_boom):
            r = await optimizar_prompt_imagen("gato astronauta")
        assert r["en"] == f"gato astronauta{_SUFIJO_FALLBACK}"
        assert r["es"] == "gato astronauta"

    @pytest.mark.asyncio
    async def test_llm_devuelve_none_fallback(self):
        from agent.creativos.prompt_imagen import optimizar_prompt_imagen, _SUFIJO_FALLBACK
        fake = AsyncMock(return_value=None)
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_imagen("perro")
        assert r["en"] == f"perro{_SUFIJO_FALLBACK}"
        assert r["es"] == "perro"

    @pytest.mark.asyncio
    async def test_respuesta_sin_formato_usa_crudo_como_en(self):
        """Si el LLM no respeta EN/ES, el texto crudo va como EN y la idea como ES."""
        from agent.creativos.prompt_imagen import optimizar_prompt_imagen
        fake = AsyncMock(return_value="A beautiful sunset over mountains, cinematic")
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_imagen("atardecer en las montañas")
        assert r["en"] == "A beautiful sunset over mountains, cinematic"
        assert r["es"] == "atardecer en las montañas"

    @pytest.mark.asyncio
    async def test_calidad_premium_usa_sistema_premium(self):
        """Verifica que `calidad='premium'` selecciona el system prompt premium."""
        from agent.creativos.prompt_imagen import optimizar_prompt_imagen, _SISTEMA_PREMIUM
        fake = AsyncMock(return_value="EN: flyer\nES: volante")
        with patch("agent.llm.completar_con_sistema", new=fake):
            await optimizar_prompt_imagen("flyer de pizza $9.99", calidad="premium")
        # El kwarg `system` pasado al LLM debe ser el sistema premium
        args, kwargs = fake.call_args
        assert kwargs.get("system") == _SISTEMA_PREMIUM

    @pytest.mark.asyncio
    async def test_calidad_standard_usa_sistema_standard(self):
        from agent.creativos.prompt_imagen import optimizar_prompt_imagen, _SISTEMA_STANDARD
        fake = AsyncMock(return_value="EN: cat\nES: gato")
        with patch("agent.llm.completar_con_sistema", new=fake):
            await optimizar_prompt_imagen("gato", calidad="standard")
        _, kwargs = fake.call_args
        assert kwargs.get("system") == _SISTEMA_STANDARD

    @pytest.mark.asyncio
    async def test_solo_es_recibido_usa_idea_como_en_fallback_logico(self):
        """Si el parser sólo extrae ES, el EN se rellena con el ES (mejor que nada)."""
        from agent.creativos.prompt_imagen import optimizar_prompt_imagen
        fake = AsyncMock(return_value="ES: un gato astronauta")
        with patch("agent.llm.completar_con_sistema", new=fake):
            r = await optimizar_prompt_imagen("gato")
        # El caller pone EN = ES cuando sólo tiene ES
        assert r["en"] == "un gato astronauta"
        assert r["es"] == "un gato astronauta"
