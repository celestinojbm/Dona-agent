# tests/test_vector_memory.py — Cobertura de agent/vector_memory.py

"""
Fija el comportamiento ACTUAL de la memoria vectorial (pgvector + embeddings
de OpenAI). El módulo no tenía test dedicado.

Cubre, sin red ni DB real:
  - Helpers puros: _es_mensaje_relevante, _limpiar_texto,
    formatear_memoria_vectorial.
  - generar_embedding con httpx mockeado (éxito, non-200, excepción) y sus
    guardias de entrada (sin API key, texto vacío tras limpieza).
  - Guardias tempranas de guardar_en_memoria_vectorial y
    buscar_memoria_relevante (mensaje irrelevante, sin key, embedding None).
  - Sanitización import-time de OPENAI_API_KEY con caracteres no-ASCII
    (patrón importlib.reload tras setear env, ver CLAUDE.md §5).

httpx SIEMPRE mockeado — nunca se llama a OpenAI real.
"""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import vector_memory as vm

# ── Helpers de mock httpx (mismo patrón que test_google_contacts.py) ──────────


def _mock_resp(status: int, json_data: dict | None = None, text: str = ""):
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.text = text
    return r


def _ctx_with_post(response=None, exc: Exception | None = None):
    """Devuelve un context manager async cuyo cliente .post retorna `response`
    o levanta `exc`."""
    client = MagicMock()
    if exc is not None:
        client.post = AsyncMock(side_effect=exc)
    else:
        client.post = AsyncMock(return_value=response)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, client


@pytest.fixture
def con_key(monkeypatch):
    """Fuerza una API key presente sin recargar el módulo."""
    monkeypatch.setattr(vm, "OPENAI_API_KEY", "sk-test-fake")


# ── 1. _es_mensaje_relevante ──────────────────────────────────────────────────


class TestEsMensajeRelevante:
    def test_texto_corto_no_es_relevante(self):
        # < 20 chars nunca es relevante aunque contenga palabra clave.
        assert vm._es_mensaje_relevante("soy X") is False

    def test_largo_sin_palabra_clave_no_es_relevante(self):
        assert vm._es_mensaje_relevante(
            "las nubes blancas cruzan el valle azul"
        ) is False

    def test_largo_con_palabra_clave_es_relevante(self):
        assert vm._es_mensaje_relevante(
            "me llamo Celestino y esto es largo"
        ) is True

    def test_vacio_no_es_relevante(self):
        assert vm._es_mensaje_relevante("") is False


# ── 2. _limpiar_texto ─────────────────────────────────────────────────────────


class TestLimpiarTexto:
    def test_saltos_de_linea_a_espacios(self):
        assert vm._limpiar_texto("hola\nmundo\r!") == "hola mundo !"

    def test_elimina_caracteres_de_control(self):
        assert vm._limpiar_texto("a\x00b\x1fc") == "abc"

    def test_solo_control_queda_vacio(self):
        assert vm._limpiar_texto("\x00\x01 ") == ""

    def test_strip_de_bordes(self):
        assert vm._limpiar_texto("   hola   ") == "hola"

    def test_preserva_tildes_y_enie(self):
        limpio = vm._limpiar_texto("  café ñoño  ")
        assert limpio == "café ñoño"

    def test_normaliza_nfc(self):
        # 'e' + acento combinante (U+0301) → 'é' compuesto (NFC).
        decompuesto = "café"
        assert len(decompuesto) == 5
        limpio = vm._limpiar_texto(decompuesto)
        assert limpio == "café"
        assert len(limpio) == 4


# ── 3. formatear_memoria_vectorial (async) ────────────────────────────────────


class TestFormatearMemoria:
    @pytest.mark.asyncio
    async def test_lista_vacia_devuelve_string_vacio(self):
        assert await vm.formatear_memoria_vectorial([]) == ""

    @pytest.mark.asyncio
    async def test_un_resultado_incluye_header_y_linea(self):
        out = await vm.formatear_memoria_vectorial(
            [{"texto": "vivo en Miami", "fecha": "01/01/2020"}]
        )
        assert out.startswith("[Recuerdos relevantes de conversaciones anteriores]:")
        assert '- "vivo en Miami" (01/01/2020)' in out

    @pytest.mark.asyncio
    async def test_multiples_resultados_una_linea_por_recuerdo(self):
        out = await vm.formatear_memoria_vectorial([
            {"texto": "a", "fecha": "01/01/2020"},
            {"texto": "b", "fecha": "02/02/2021"},
        ])
        # Header + 2 líneas de recuerdo.
        assert len(out.splitlines()) == 3


# ── 4. generar_embedding (httpx mockeado) ─────────────────────────────────────


class TestGenerarEmbedding:
    @pytest.mark.asyncio
    async def test_sin_api_key_retorna_none(self, monkeypatch):
        monkeypatch.setattr(vm, "OPENAI_API_KEY", "")
        assert await vm.generar_embedding("cualquier texto largo") is None

    @pytest.mark.asyncio
    async def test_texto_vacio_tras_limpieza_retorna_none(self, con_key):
        # Con key presente, pero el texto queda vacío tras _limpiar_texto.
        assert await vm.generar_embedding("\x00\x01") is None

    @pytest.mark.asyncio
    async def test_exito_devuelve_embedding(self, con_key):
        vector = [0.1, 0.2, 0.3]
        resp = _mock_resp(200, {"data": [{"embedding": vector}]})
        ctx, client = _ctx_with_post(response=resp)
        with patch("agent.vector_memory.httpx.AsyncClient", return_value=ctx):
            out = await vm.generar_embedding("me llamo Celestino")
        assert out == vector
        client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_status_no_200_retorna_none(self, con_key):
        resp = _mock_resp(429, text="rate limited")
        ctx, _ = _ctx_with_post(response=resp)
        with patch("agent.vector_memory.httpx.AsyncClient", return_value=ctx):
            assert await vm.generar_embedding("texto de prueba largo") is None

    @pytest.mark.asyncio
    async def test_excepcion_en_post_retorna_none(self, con_key):
        ctx, _ = _ctx_with_post(exc=RuntimeError("boom"))
        with patch("agent.vector_memory.httpx.AsyncClient", return_value=ctx):
            assert await vm.generar_embedding("otro texto de prueba") is None


# ── 5. Guardias tempranas de guardar/buscar ───────────────────────────────────


class TestGuardarGuardias:
    @pytest.mark.asyncio
    async def test_mensaje_irrelevante_no_guarda(self):
        # Mensaje corto/irrelevante → False sin tocar red ni DB.
        assert await vm.guardar_en_memoria_vectorial("5551", "hola") is False

    @pytest.mark.asyncio
    async def test_embedding_none_no_guarda(self, monkeypatch):
        # Mensaje relevante pero embedding falla → False (no llega a DB).
        async def fake_embed(_texto):
            return None
        monkeypatch.setattr(vm, "generar_embedding", fake_embed)
        relevante = "me llamo Celestino y trabajo en Dona todos los días"
        assert await vm.guardar_en_memoria_vectorial("5551", relevante) is False


class TestBuscarGuardias:
    @pytest.mark.asyncio
    async def test_sin_api_key_retorna_lista_vacia(self, monkeypatch):
        monkeypatch.setattr(vm, "OPENAI_API_KEY", "")
        assert await vm.buscar_memoria_relevante("5551", "mi meta") == []

    @pytest.mark.asyncio
    async def test_embedding_none_retorna_lista_vacia(self, con_key, monkeypatch):
        async def fake_embed(_texto):
            return None
        monkeypatch.setattr(vm, "generar_embedding", fake_embed)
        assert await vm.buscar_memoria_relevante("5551", "mi objetivo") == []


# ── 6. Sanitización import-time de OPENAI_API_KEY ─────────────────────────────


class TestSanitizacionApiKey:
    def test_key_no_ascii_se_limpia_al_importar(self, monkeypatch):
        # Patrón CLAUDE.md §5: setear env var + importlib.reload.
        import agent.vector_memory as mod
        original = mod.OPENAI_API_KEY  # snapshot para restaurar sin pulir global
        monkeypatch.setenv("OPENAI_API_KEY", "sk-tëst\n")  # ë + salto
        importlib.reload(mod)
        try:
            # ë (no-ASCII) eliminada, salto de línea recortado.
            assert mod.OPENAI_API_KEY == "sk-tst"
        finally:
            # Restaurar el atributo directamente: un segundo reload leería la
            # env aún parcheada y dejaría el módulo sucio para el resto del suite.
            mod.OPENAI_API_KEY = original

    def test_key_ascii_limpia_no_cambia(self, monkeypatch):
        import agent.vector_memory as mod
        original = mod.OPENAI_API_KEY
        monkeypatch.setenv("OPENAI_API_KEY", "sk-limpia-123")
        importlib.reload(mod)
        try:
            assert mod.OPENAI_API_KEY == "sk-limpia-123"
        finally:
            mod.OPENAI_API_KEY = original
