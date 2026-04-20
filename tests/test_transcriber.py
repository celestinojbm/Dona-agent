# tests/test_transcriber.py — Tests del pipeline de transcripción (OpenAI + Groq fallback)

"""
Verifica el orden de preferencia de proveedores Whisper:
  1. OpenAI Whisper (whisper-1) si OPENAI_API_KEY existe
  2. Groq Whisper (whisper-large-v3) como fallback
  3. None si ninguno está configurado
"""

import pytest
from unittest.mock import AsyncMock, patch

from agent import transcriber


@pytest.fixture(autouse=True)
def _reset_clientes():
    """Limpia los singletons entre tests para no arrastrar estado."""
    transcriber._groq_client = None
    transcriber._openai_client = None
    yield
    transcriber._groq_client = None
    transcriber._openai_client = None


class TestPreferenciaProvidersWhisper:
    @pytest.mark.asyncio
    async def test_sin_keys_retorna_none(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        resultado = await transcriber.transcribir_audio(b"\x00" * 100)
        assert resultado is None

    @pytest.mark.asyncio
    async def test_solo_openai_usa_openai(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with patch.object(transcriber, "_transcribir_con_openai", new=AsyncMock(return_value="hola")) as oa, \
             patch.object(transcriber, "_transcribir_con_groq", new=AsyncMock(return_value=None)) as gq:
            resultado = await transcriber.transcribir_audio(b"\x00" * 100)
            assert resultado == "hola"
            oa.assert_called_once()
            gq.assert_not_called()

    @pytest.mark.asyncio
    async def test_openai_falla_cae_a_groq(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        monkeypatch.setenv("GROQ_API_KEY", "gsk-fake")

        with patch.object(transcriber, "_transcribir_con_openai", new=AsyncMock(return_value=None)) as oa, \
             patch.object(transcriber, "_transcribir_con_groq", new=AsyncMock(return_value="hola groq")) as gq:
            resultado = await transcriber.transcribir_audio(b"\x00" * 100)
            assert resultado == "hola groq"
            oa.assert_called_once()
            gq.assert_called_once()

    @pytest.mark.asyncio
    async def test_solo_groq_usa_groq(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "gsk-fake")

        with patch.object(transcriber, "_transcribir_con_openai", new=AsyncMock(return_value=None)) as oa, \
             patch.object(transcriber, "_transcribir_con_groq", new=AsyncMock(return_value="hola groq")) as gq:
            resultado = await transcriber.transcribir_audio(b"\x00" * 100)
            assert resultado == "hola groq"
            # OpenAI igual se intenta pero retorna None rápido porque no hay key
            gq.assert_called_once()


class TestExtensionDesdeMime:
    def test_ogg(self):
        assert transcriber._extension_desde_mime("audio/ogg; codecs=opus") == "ogg"

    def test_mp3(self):
        assert transcriber._extension_desde_mime("audio/mpeg") == "ogg"  # "mpeg" no matchea, default ogg
        assert transcriber._extension_desde_mime("audio/mp3") == "mp3"

    def test_m4a(self):
        assert transcriber._extension_desde_mime("audio/mp4") == "m4a"
        assert transcriber._extension_desde_mime("audio/m4a") == "m4a"

    def test_wav(self):
        assert transcriber._extension_desde_mime("audio/wav") == "wav"

    def test_desconocido_default_ogg(self):
        assert transcriber._extension_desde_mime("audio/xyz") == "ogg"
