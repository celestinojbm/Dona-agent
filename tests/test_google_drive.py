# tests/test_google_drive.py — Tests de integración con Google Drive API

"""
Tests con httpx mockeado para agent.google_drive.
Cubre: subir_archivo (multipart), compartir_con_link (2-step), listar_sheets.
Mockea _token() para no depender de OAuth real.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import google_drive


def _mock_response(status: int, json_data: dict | None = None, text: str = ""):
    """Crea una respuesta fake de httpx."""
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.text = text or json.dumps(json_data or {})
    return r


def _fake_client_context(responses: list, post_responses: list | None = None, get_responses: list | None = None):
    """
    Construye un AsyncClient fake.
    - `responses`: fallback único usado tanto para post como get (backcompat).
    - `post_responses` / `get_responses`: colas independientes por método.
    """
    client = MagicMock()
    client.post = AsyncMock(side_effect=list(post_responses if post_responses is not None else responses))
    client.get = AsyncMock(side_effect=list(get_responses if get_responses is not None else responses))

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, client


@pytest.fixture
def mock_token(monkeypatch):
    """Mockea _token() para devolver un token fake."""
    async def fake_token(telefono):
        return "fake-token-abc"
    monkeypatch.setattr(google_drive, "_token", fake_token)


@pytest.fixture
def mock_token_none(monkeypatch):
    """Mockea _token() para devolver None (usuario sin OAuth)."""
    async def fake_token(telefono):
        return None
    monkeypatch.setattr(google_drive, "_token", fake_token)


class TestSubirArchivo:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_none(self, mock_token_none):
        resultado = await google_drive.subir_archivo(
            "5551234567", "test.csv", b"contenido"
        )
        assert resultado is None

    @pytest.mark.asyncio
    async def test_contenido_vacio_retorna_none(self, mock_token):
        resultado = await google_drive.subir_archivo(
            "5551234567", "test.csv", b""
        )
        assert resultado is None

    @pytest.mark.asyncio
    async def test_upload_exitoso(self, mock_token):
        ctx, client = _fake_client_context([
            _mock_response(200, {
                "id": "1ABC",
                "name": "test.csv",
                "webViewLink": "https://drive.google.com/file/d/1ABC/view",
                "webContentLink": "https://drive.google.com/uc?id=1ABC",
                "mimeType": "text/csv",
            })
        ])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            resultado = await google_drive.subir_archivo(
                "5551234567", "test.csv", b"a,b,c\n1,2,3\n", mime_type="text/csv"
            )
        assert resultado["id"] == "1ABC"
        assert resultado["name"] == "test.csv"
        assert "webViewLink" in resultado
        # Verifica que se llamó al endpoint de upload
        args, kwargs = client.post.call_args
        assert "upload/drive/v3/files" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer fake-token-abc"
        # El content-type debe ser multipart/related
        assert "multipart/related" in kwargs["headers"]["Content-Type"]

    @pytest.mark.asyncio
    async def test_403_sin_scope_retorna_none(self, mock_token):
        ctx, _ = _fake_client_context([_mock_response(403, text="Forbidden")])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            resultado = await google_drive.subir_archivo(
                "5551234567", "test.csv", b"contenido"
            )
        assert resultado is None

    @pytest.mark.asyncio
    async def test_500_retorna_none(self, mock_token):
        ctx, _ = _fake_client_context([_mock_response(500, text="Server Error")])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            resultado = await google_drive.subir_archivo(
                "5551234567", "test.csv", b"contenido"
            )
        assert resultado is None

    @pytest.mark.asyncio
    async def test_carpeta_id_incluye_parents(self, mock_token):
        ctx, client = _fake_client_context([
            _mock_response(200, {"id": "2XYZ", "name": "x.csv"})
        ])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            await google_drive.subir_archivo(
                "5551234567", "x.csv", b"data",
                carpeta_id="FOLDER_123"
            )
        # Ver el body para confirmar que incluye parents
        args, kwargs = client.post.call_args
        body = kwargs["content"]
        assert b"FOLDER_123" in body
        assert b"parents" in body


class TestCompartirConLink:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_none(self, mock_token_none):
        assert await google_drive.compartir_con_link("5551234567", "fileid") is None

    @pytest.mark.asyncio
    async def test_flujo_exitoso(self, mock_token):
        ctx, client = _fake_client_context(
            [],
            post_responses=[_mock_response(200, {"id": "perm1", "role": "reader", "type": "anyone"})],
            get_responses=[_mock_response(200, {"webViewLink": "https://drive.google.com/file/d/FID/view"})],
        )
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            link = await google_drive.compartir_con_link("5551234567", "FID")
        assert link == "https://drive.google.com/file/d/FID/view"
        # Verifica que el POST creó permiso tipo "anyone"
        args, kwargs = client.post.call_args
        assert kwargs["json"] == {"role": "reader", "type": "anyone"}

    @pytest.mark.asyncio
    async def test_permiso_falla_retorna_none(self, mock_token):
        ctx, _ = _fake_client_context([_mock_response(500, text="err")])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            link = await google_drive.compartir_con_link("5551234567", "FID")
        assert link is None


class TestListarSheets:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_lista_vacia(self, mock_token_none):
        assert await google_drive.listar_sheets("5551234567") == []

    @pytest.mark.asyncio
    async def test_listar_exitoso(self, mock_token):
        ctx, client = _fake_client_context([
            _mock_response(200, {"files": [
                {"id": "s1", "name": "Ventas 2026", "modifiedTime": "2026-04-10T10:00:00Z"},
                {"id": "s2", "name": "Gastos", "modifiedTime": "2026-04-01T10:00:00Z"},
            ]})
        ])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            sheets = await google_drive.listar_sheets("5551234567", limite=10)
        assert len(sheets) == 2
        assert sheets[0]["name"] == "Ventas 2026"
        # Verifica filtro por mimeType sheet
        args, kwargs = client.get.call_args
        assert "spreadsheet" in kwargs["params"]["q"]

    @pytest.mark.asyncio
    async def test_limite_se_respeta_en_pageSize(self, mock_token):
        ctx, client = _fake_client_context([
            _mock_response(200, {"files": []})
        ])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            await google_drive.listar_sheets("5551234567", limite=5)
        args, kwargs = client.get.call_args
        assert kwargs["params"]["pageSize"] == 5

    @pytest.mark.asyncio
    async def test_limite_topea_en_100(self, mock_token):
        ctx, client = _fake_client_context([
            _mock_response(200, {"files": []})
        ])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            await google_drive.listar_sheets("5551234567", limite=500)
        args, kwargs = client.get.call_args
        assert kwargs["params"]["pageSize"] == 100

    @pytest.mark.asyncio
    async def test_error_retorna_lista_vacia(self, mock_token):
        ctx, _ = _fake_client_context([_mock_response(500, text="err")])
        with patch("agent.google_drive.httpx.AsyncClient", return_value=ctx):
            assert await google_drive.listar_sheets("5551234567") == []
