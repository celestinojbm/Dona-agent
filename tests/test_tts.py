# tests/test_tts.py — Tests del módulo TTS

"""
Verifica el fallback silencioso cuando OPENAI_API_KEY no está
y el truncado del texto largo.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import tts


@pytest.fixture(autouse=True)
def _reset_client():
    tts._openai_client = None
    yield
    tts._openai_client = None


class TestTTS:
    @pytest.mark.asyncio
    async def test_sin_api_key_retorna_none(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        resultado = await tts.sintetizar_audio("Hola mundo")
        assert resultado is None

    @pytest.mark.asyncio
    async def test_texto_vacio_retorna_none(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        assert await tts.sintetizar_audio("") is None
        assert await tts.sintetizar_audio("   ") is None

    @pytest.mark.asyncio
    async def test_truncado_a_max_chars(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")

        captured = {}

        mock_response = MagicMock()
        mock_response.aread = AsyncMock(return_value=b"fake-audio-bytes")

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return mock_response

        fake_client = MagicMock()
        fake_client.audio.speech.create = fake_create
        tts._openai_client = fake_client

        texto_largo = "a" * 1000
        resultado = await tts.sintetizar_audio(texto_largo)
        assert resultado == b"fake-audio-bytes"
        assert len(captured["input"]) == tts._MAX_CHARS_TTS
        assert captured["response_format"] == "opus"
        assert captured["model"] == "tts-1"
