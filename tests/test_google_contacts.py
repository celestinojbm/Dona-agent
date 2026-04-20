# tests/test_google_contacts.py — Tests de contactos (helpers + integración People API)

"""
Tests unitarios de helpers puros + tests con httpx mockeado para las funciones
que llaman Google People API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import google_contacts


def _mock_resp(status: int, json_data: dict | None = None, text: str = ""):
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.text = text
    return r


def _ctx_with_get(get_responses: list):
    client = MagicMock()
    client.get = AsyncMock(side_effect=list(get_responses))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, client


@pytest.fixture
def mock_token(monkeypatch):
    async def fake(t): return "fake-token"
    monkeypatch.setattr(google_contacts, "_token", fake)


@pytest.fixture
def mock_token_none(monkeypatch):
    async def fake(t): return None
    monkeypatch.setattr(google_contacts, "_token", fake)


class TestNormalizarTelefono:
    def test_solo_digitos_queda_igual(self):
        assert google_contacts._normalizar_telefono("14076936023") == "14076936023"

    def test_remueve_plus(self):
        assert google_contacts._normalizar_telefono("+14076936023") == "14076936023"

    def test_remueve_guiones_y_espacios(self):
        assert google_contacts._normalizar_telefono("+1-407-693 6023") == "14076936023"

    def test_remueve_parentesis(self):
        assert google_contacts._normalizar_telefono("(407) 693-6023") == "4076936023"

    def test_vacio(self):
        assert google_contacts._normalizar_telefono("") == ""
        assert google_contacts._normalizar_telefono(None) == ""


class TestParsearContacto:
    def test_completo(self):
        person = {
            "names": [{"displayName": "Juan Pérez"}],
            "emailAddresses": [{"value": "juan@example.com"}, {"value": "j@work.com"}],
            "phoneNumbers": [{"value": "+1 407 693 6023"}],
        }
        c = google_contacts._parsear_contacto(person)
        assert c["nombre"] == "Juan Pérez"
        assert c["emails"] == ["juan@example.com", "j@work.com"]
        assert c["telefonos"] == ["+1 407 693 6023"]
        assert c["telefonos_normalizados"] == ["14076936023"]

    def test_sin_nombre(self):
        c = google_contacts._parsear_contacto({"emailAddresses": [{"value": "x@y.com"}]})
        assert c["nombre"] == ""
        assert c["emails"] == ["x@y.com"]
        assert c["telefonos"] == []

    def test_vacio(self):
        c = google_contacts._parsear_contacto({})
        assert c == {"nombre": "", "emails": [], "telefonos": [], "telefonos_normalizados": []}


class TestListarContactos:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_vacio(self, mock_token_none):
        assert await google_contacts.listar_contactos("5551") == []

    @pytest.mark.asyncio
    async def test_lista_paginada_respeta_limite(self, mock_token):
        ctx, client = _ctx_with_get([
            _mock_resp(200, {
                "connections": [
                    {"names": [{"displayName": "Ana"}], "emailAddresses": [{"value": "a@x.com"}]},
                    {"names": [{"displayName": "Bob"}], "phoneNumbers": [{"value": "+15551112222"}]},
                ],
                "nextPageToken": None,
            })
        ])
        with patch("agent.google_contacts.httpx.AsyncClient", return_value=ctx):
            contactos = await google_contacts.listar_contactos("5551", limite=10)
        assert len(contactos) == 2
        assert contactos[0]["nombre"] == "Ana"
        assert contactos[1]["telefonos_normalizados"] == ["15551112222"]

    @pytest.mark.asyncio
    async def test_403_sin_scope_retorna_vacio(self, mock_token):
        ctx, _ = _ctx_with_get([_mock_resp(403, text="Forbidden")])
        with patch("agent.google_contacts.httpx.AsyncClient", return_value=ctx):
            assert await google_contacts.listar_contactos("5551") == []

    @pytest.mark.asyncio
    async def test_excepcion_retorna_vacio(self, mock_token):
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("network boom"))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=None)
        with patch("agent.google_contacts.httpx.AsyncClient", return_value=ctx):
            assert await google_contacts.listar_contactos("5551") == []


class TestBuscarPorTelefono:
    @pytest.mark.asyncio
    async def test_numero_corto_retorna_none(self, mock_token):
        # 6 dígitos es menor al mínimo (7)
        assert await google_contacts.buscar_por_telefono("5551", "555123") is None

    @pytest.mark.asyncio
    async def test_numero_vacio_retorna_none(self, mock_token):
        assert await google_contacts.buscar_por_telefono("5551", "") is None

    @pytest.mark.asyncio
    async def test_match_exacto(self, mock_token):
        ctx, _ = _ctx_with_get([
            _mock_resp(200, {
                "connections": [
                    {"names": [{"displayName": "Juan"}], "phoneNumbers": [{"value": "+14076936023"}]},
                ],
                "nextPageToken": None,
            })
        ])
        with patch("agent.google_contacts.httpx.AsyncClient", return_value=ctx):
            m = await google_contacts.buscar_por_telefono("5551", "14076936023")
        assert m is not None
        assert m["nombre"] == "Juan"

    @pytest.mark.asyncio
    async def test_match_tolerante_sin_codigo_pais(self, mock_token):
        """Contacto guardado como +14076936023, buscamos '4076936023' — debe matchear."""
        ctx, _ = _ctx_with_get([
            _mock_resp(200, {
                "connections": [
                    {"names": [{"displayName": "Juan"}], "phoneNumbers": [{"value": "+14076936023"}]},
                ],
                "nextPageToken": None,
            })
        ])
        with patch("agent.google_contacts.httpx.AsyncClient", return_value=ctx):
            m = await google_contacts.buscar_por_telefono("5551", "(407) 693-6023")
        assert m is not None
        assert m["nombre"] == "Juan"

    @pytest.mark.asyncio
    async def test_no_match_retorna_none(self, mock_token):
        ctx, _ = _ctx_with_get([
            _mock_resp(200, {
                "connections": [
                    {"names": [{"displayName": "Otro"}], "phoneNumbers": [{"value": "+19991234567"}]},
                ],
                "nextPageToken": None,
            })
        ])
        with patch("agent.google_contacts.httpx.AsyncClient", return_value=ctx):
            m = await google_contacts.buscar_por_telefono("5551", "4076936023")
        assert m is None


class TestBuscarPorNombre:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_vacio(self, mock_token_none):
        assert await google_contacts.buscar_por_nombre("5551", "Juan") == []

    @pytest.mark.asyncio
    async def test_nombre_vacio_retorna_vacio(self, mock_token):
        assert await google_contacts.buscar_por_nombre("5551", "   ") == []

    @pytest.mark.asyncio
    async def test_resultado_exitoso(self, mock_token):
        ctx, client = _ctx_with_get([
            _mock_resp(200, {
                "results": [
                    {"person": {
                        "names": [{"displayName": "Juan Pérez"}],
                        "emailAddresses": [{"value": "juan@ex.com"}],
                    }},
                    {"person": {
                        "names": [{"displayName": "Juanita"}],
                        "phoneNumbers": [{"value": "+15551112222"}],
                    }},
                ]
            })
        ])
        with patch("agent.google_contacts.httpx.AsyncClient", return_value=ctx):
            coincidencias = await google_contacts.buscar_por_nombre("5551", "Juan")
        assert len(coincidencias) == 2
        assert coincidencias[0]["nombre"] == "Juan Pérez"
        assert coincidencias[0]["emails"] == ["juan@ex.com"]
        # Verifica que se llamó al endpoint searchContacts
        args, kwargs = client.get.call_args
        assert "searchContacts" in args[0]
        assert kwargs["params"]["query"] == "Juan"

    @pytest.mark.asyncio
    async def test_error_retorna_vacio(self, mock_token):
        ctx, _ = _ctx_with_get([_mock_resp(500, text="err")])
        with patch("agent.google_contacts.httpx.AsyncClient", return_value=ctx):
            assert await google_contacts.buscar_por_nombre("5551", "Juan") == []
