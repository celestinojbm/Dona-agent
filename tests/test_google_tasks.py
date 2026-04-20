# tests/test_google_tasks.py — Tests de integración con Google Tasks API

"""
Tests con httpx mockeado para agent.google_tasks.
Cubre: listar_listas, listar_tareas (con y sin lista_id), crear_tarea,
completar_tarea, eliminar_tarea, y los caminos de 403 / sin token.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import google_tasks


def _mock_resp(status: int, json_data: dict | None = None, text: str = ""):
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.text = text
    return r


def _fake_client(get_responses=None, post_responses=None, patch_responses=None, delete_responses=None):
    client = MagicMock()
    client.get = AsyncMock(side_effect=list(get_responses or []))
    client.post = AsyncMock(side_effect=list(post_responses or []))
    client.patch = AsyncMock(side_effect=list(patch_responses or []))
    client.delete = AsyncMock(side_effect=list(delete_responses or []))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, client


@pytest.fixture
def mock_token(monkeypatch):
    async def fake(t): return "fake-token"
    monkeypatch.setattr(google_tasks, "_token", fake)


@pytest.fixture
def mock_token_none(monkeypatch):
    async def fake(t): return None
    monkeypatch.setattr(google_tasks, "_token", fake)


class TestListarListas:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_vacio(self, mock_token_none):
        assert await google_tasks.listar_listas("5551") == []

    @pytest.mark.asyncio
    async def test_listar_exitoso(self, mock_token):
        ctx, _ = _fake_client(get_responses=[
            _mock_resp(200, {"items": [
                {"id": "L1", "title": "My Tasks"},
                {"id": "L2", "title": "Negocio"},
            ]})
        ])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            listas = await google_tasks.listar_listas("5551")
        assert len(listas) == 2
        assert listas[0] == {"id": "L1", "titulo": "My Tasks"}

    @pytest.mark.asyncio
    async def test_403_retorna_vacio(self, mock_token):
        ctx, _ = _fake_client(get_responses=[_mock_resp(403, text="Forbidden")])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            assert await google_tasks.listar_listas("5551") == []

    @pytest.mark.asyncio
    async def test_error_retorna_vacio(self, mock_token):
        ctx, _ = _fake_client(get_responses=[_mock_resp(500, text="oops")])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            assert await google_tasks.listar_listas("5551") == []


class TestListarTareas:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_vacio(self, mock_token_none):
        assert await google_tasks.listar_tareas("5551") == []

    @pytest.mark.asyncio
    async def test_listar_con_lista_explicita(self, mock_token):
        ctx, client = _fake_client(get_responses=[
            _mock_resp(200, {"items": [
                {"id": "T1", "title": "Llamar proveedor", "status": "needsAction"},
                {"id": "T2", "title": "Pagar facturas", "status": "needsAction", "due": "2026-04-20T00:00:00.000Z"},
            ]})
        ])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            tareas = await google_tasks.listar_tareas("5551", lista_id="L1")
        assert len(tareas) == 2
        assert tareas[0]["titulo"] == "Llamar proveedor"
        assert tareas[1]["vencimiento"] == "2026-04-20T00:00:00.000Z"
        # Endpoint correcto
        args, kwargs = client.get.call_args
        assert "/lists/L1/tasks" in args[0]
        assert kwargs["params"]["showCompleted"] == "false"

    @pytest.mark.asyncio
    async def test_lista_por_defecto_auto(self, mock_token):
        # Primer GET resuelve la default (lists?maxResults=1), segundo GET trae tareas
        ctx, client = _fake_client(get_responses=[
            _mock_resp(200, {"items": [{"id": "DEFAULT", "title": "My Tasks"}]}),
            _mock_resp(200, {"items": [{"id": "T1", "title": "Comprar café"}]}),
        ])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            tareas = await google_tasks.listar_tareas("5551")
        assert len(tareas) == 1
        assert tareas[0]["lista_id"] == "DEFAULT"

    @pytest.mark.asyncio
    async def test_incluir_completadas(self, mock_token):
        ctx, client = _fake_client(get_responses=[_mock_resp(200, {"items": []})])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            await google_tasks.listar_tareas("5551", lista_id="L1", incluir_completadas=True)
        assert client.get.call_args.kwargs["params"]["showCompleted"] == "true"

    @pytest.mark.asyncio
    async def test_limite_topea_100(self, mock_token):
        ctx, client = _fake_client(get_responses=[_mock_resp(200, {"items": []})])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            await google_tasks.listar_tareas("5551", lista_id="L1", limite=500)
        assert client.get.call_args.kwargs["params"]["maxResults"] == 100

    @pytest.mark.asyncio
    async def test_403_retorna_vacio(self, mock_token):
        ctx, _ = _fake_client(get_responses=[_mock_resp(403)])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            assert await google_tasks.listar_tareas("5551", lista_id="L1") == []


class TestCrearTarea:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_none(self, mock_token_none):
        assert await google_tasks.crear_tarea("5551", "Algo") is None

    @pytest.mark.asyncio
    async def test_titulo_vacio_retorna_none(self, mock_token):
        assert await google_tasks.crear_tarea("5551", "   ") is None

    @pytest.mark.asyncio
    async def test_crear_con_lista_explicita(self, mock_token):
        ctx, client = _fake_client(
            post_responses=[_mock_resp(200, {"id": "T9", "title": "Comprar leche", "status": "needsAction"})]
        )
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            t = await google_tasks.crear_tarea("5551", "Comprar leche", lista_id="L1", notas="urgente")
        assert t is not None
        assert t["id"] == "T9"
        assert t["lista_id"] == "L1"
        args, kwargs = client.post.call_args
        assert "/lists/L1/tasks" in args[0]
        assert kwargs["json"]["title"] == "Comprar leche"
        assert kwargs["json"]["notes"] == "urgente"

    @pytest.mark.asyncio
    async def test_crear_con_vencimiento(self, mock_token):
        ctx, client = _fake_client(
            post_responses=[_mock_resp(200, {"id": "T1", "title": "X", "status": "needsAction", "due": "2026-04-20T00:00:00.000Z"})]
        )
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            t = await google_tasks.crear_tarea(
                "5551", "X", lista_id="L1", vencimiento_iso="2026-04-20T00:00:00.000Z"
            )
        assert t["vencimiento"] == "2026-04-20T00:00:00.000Z"
        assert client.post.call_args.kwargs["json"]["due"] == "2026-04-20T00:00:00.000Z"

    @pytest.mark.asyncio
    async def test_403_levanta_scope_error(self, mock_token):
        ctx, _ = _fake_client(post_responses=[_mock_resp(403, text="Forbidden")])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(google_tasks.GoogleTasksScopeError):
                await google_tasks.crear_tarea("5551", "X", lista_id="L1")

    @pytest.mark.asyncio
    async def test_error_servidor_retorna_none(self, mock_token):
        ctx, _ = _fake_client(post_responses=[_mock_resp(500, text="err")])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            assert await google_tasks.crear_tarea("5551", "X", lista_id="L1") is None


class TestCompletarTarea:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_false(self, mock_token_none):
        assert await google_tasks.completar_tarea("5551", "L1", "T1") is False

    @pytest.mark.asyncio
    async def test_ids_vacios_retorna_false(self, mock_token):
        assert await google_tasks.completar_tarea("5551", "", "T1") is False
        assert await google_tasks.completar_tarea("5551", "L1", "") is False

    @pytest.mark.asyncio
    async def test_patch_exitoso(self, mock_token):
        ctx, client = _fake_client(patch_responses=[_mock_resp(200, {"id": "T1", "status": "completed"})])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            ok = await google_tasks.completar_tarea("5551", "L1", "T1")
        assert ok is True
        args, kwargs = client.patch.call_args
        assert "/lists/L1/tasks/T1" in args[0]
        assert kwargs["json"]["status"] == "completed"
        assert "completed" in kwargs["json"]

    @pytest.mark.asyncio
    async def test_403_levanta_scope_error(self, mock_token):
        ctx, _ = _fake_client(patch_responses=[_mock_resp(403)])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(google_tasks.GoogleTasksScopeError):
                await google_tasks.completar_tarea("5551", "L1", "T1")


class TestEliminarTarea:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_false(self, mock_token_none):
        assert await google_tasks.eliminar_tarea("5551", "L1", "T1") is False

    @pytest.mark.asyncio
    async def test_delete_204_exito(self, mock_token):
        ctx, client = _fake_client(delete_responses=[_mock_resp(204)])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            ok = await google_tasks.eliminar_tarea("5551", "L1", "T1")
        assert ok is True
        args, _ = client.delete.call_args
        assert "/lists/L1/tasks/T1" in args[0]

    @pytest.mark.asyncio
    async def test_403_levanta_scope_error(self, mock_token):
        ctx, _ = _fake_client(delete_responses=[_mock_resp(403)])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(google_tasks.GoogleTasksScopeError):
                await google_tasks.eliminar_tarea("5551", "L1", "T1")

    @pytest.mark.asyncio
    async def test_error_retorna_false(self, mock_token):
        ctx, _ = _fake_client(delete_responses=[_mock_resp(500, text="err")])
        with patch("agent.google_tasks.httpx.AsyncClient", return_value=ctx):
            assert await google_tasks.eliminar_tarea("5551", "L1", "T1") is False
