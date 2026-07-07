# tests/test_google_sheets.py — cobertura de agent/google_sheets.py

"""
Fija el comportamiento ACTUAL de la integración con Google Sheets:

  * extraer_spreadsheet_id  — parseo de URL / passthrough de ID (puro).
  * _col_letra / _a1        — conversión de índice a notación A1 (puro), con
                              énfasis en los bordes de acarreo (Z→AA, ZZ→AAA).
  * _rango_seguro           — URL-encoding del nombre de la hoja (puro).
  * verificar_acceso_hoja   — mapeo de status (200/403/404/otros), parseo de
                              tabs, sin token y ramas de excepción.
  * leer_rango              — rango por defecto vs rango_extra, 403, error, None.
  * agregar_fila_api        — 200/201 OK, error, sin token, excepción.
  * actualizar_celda_api    — 200 OK, error, sin token, excepción.
  * buscar_y_actualizar     — matching case-insensitive de columnas y valores,
                              columnas ausentes, fila no encontrada, éxito.

httpx se mockea SIEMPRE (nunca red real) y `_token` se parchea para no tocar
Google Calendar / OAuth. Estos tests cubren ramas puras y de parseo; no
cambian la lógica de producción.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import google_sheets


# --------------------------------------------------------------------------- #
# Helpers de mock de httpx (mismo patrón que test_google_contacts.py)
# --------------------------------------------------------------------------- #
def _mock_resp(status: int, json_data: dict | None = None, text: str = ""):
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.text = text
    return r


def _ctx(method: str, responses: list):
    """Crea un AsyncClient mockeado cuyo `method` (get/post/put) devuelve
    los `responses` en orden. Devuelve (ctx, client)."""
    client = MagicMock()
    setattr(client, method, AsyncMock(side_effect=list(responses)))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, client


def _ctx_explota(method: str):
    """AsyncClient cuyo `method` lanza — para probar ramas de excepción."""
    client = MagicMock()
    setattr(client, method, AsyncMock(side_effect=RuntimeError("network boom")))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


@pytest.fixture
def mock_token(monkeypatch):
    async def fake(t):
        return "fake-token"
    monkeypatch.setattr(google_sheets, "_token", fake)


@pytest.fixture
def mock_token_none(monkeypatch):
    async def fake(t):
        return None
    monkeypatch.setattr(google_sheets, "_token", fake)


# --------------------------------------------------------------------------- #
# extraer_spreadsheet_id — puro
# --------------------------------------------------------------------------- #
class TestExtraerSpreadsheetId:
    def test_url_completa(self):
        url = "https://docs.google.com/spreadsheets/d/ABC123xyz_-/edit#gid=0"
        assert google_sheets.extraer_spreadsheet_id(url) == "ABC123xyz_-"

    def test_url_sin_sufijo(self):
        url = "https://docs.google.com/spreadsheets/d/1AbC2dEf3"
        assert google_sheets.extraer_spreadsheet_id(url) == "1AbC2dEf3"

    def test_id_suelto_passthrough(self):
        assert google_sheets.extraer_spreadsheet_id("ABC123") == "ABC123"

    def test_id_con_espacios_se_recorta(self):
        assert google_sheets.extraer_spreadsheet_id("  ABC123  ") == "ABC123"

    def test_id_con_guiones_y_underscores(self):
        assert google_sheets.extraer_spreadsheet_id("a-b_c-1") == "a-b_c-1"

    def test_toma_primer_segmento_tras_d(self):
        url = "https://docs.google.com/spreadsheets/d/XYZ/edit/otra/cosa"
        assert google_sheets.extraer_spreadsheet_id(url) == "XYZ"


# --------------------------------------------------------------------------- #
# _col_letra / _a1 — puros, énfasis en bordes de acarreo
# --------------------------------------------------------------------------- #
class TestColLetra:
    @pytest.mark.parametrize("n,esperado", [
        (0, "A"),
        (1, "B"),
        (25, "Z"),
        (26, "AA"),
        (27, "AB"),
        (51, "AZ"),
        (52, "BA"),
        (701, "ZZ"),
        (702, "AAA"),
    ])
    def test_indice_a_letra(self, n, esperado):
        assert google_sheets._col_letra(n) == esperado


class TestA1:
    @pytest.mark.parametrize("fila,col,esperado", [
        (0, 0, "A1"),
        (2, 1, "B3"),
        (0, 25, "Z1"),
        (9, 26, "AA10"),
        (99, 0, "A100"),
    ])
    def test_fila_col_a_a1(self, fila, col, esperado):
        assert google_sheets._a1(fila, col) == esperado


# --------------------------------------------------------------------------- #
# _rango_seguro — URL-encoding puro
# --------------------------------------------------------------------------- #
class TestRangoSeguro:
    def test_nombre_simple(self):
        assert google_sheets._rango_seguro("Hoja1") == "Hoja1"

    def test_espacios_se_codifican(self):
        assert google_sheets._rango_seguro("Mi Hoja") == "Mi%20Hoja"

    def test_signos_de_rango_se_codifican(self):
        # '!' y ':' no son "safe" — deben quedar percent-encoded
        assert google_sheets._rango_seguro("Hoja1!A1:B2") == "Hoja1%21A1%3AB2"

    def test_acentos_se_codifican(self):
        # 'ó' → %C3%B3 (UTF-8)
        assert google_sheets._rango_seguro("Añó") == "A%C3%B1%C3%B3"


# --------------------------------------------------------------------------- #
# verificar_acceso_hoja — mapeo de status + parseo de tabs
# --------------------------------------------------------------------------- #
class TestVerificarAccesoHoja:
    async def test_sin_token(self, mock_token_none):
        assert await google_sheets.verificar_acceso_hoja("5551", "SID") == (False, "", [])

    async def test_ok_devuelve_titulo_y_tabs(self, mock_token):
        data = {
            "properties": {"title": "Mi Doc"},
            "sheets": [
                {"properties": {"title": "Ventas"}},
                {"properties": {"title": "Gastos"}},
                {"sin_properties": True},  # se ignora
            ],
        }
        ctx, _ = _ctx("get", [_mock_resp(200, data)])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            ok, titulo, tabs = await google_sheets.verificar_acceso_hoja("5551", "SID")
        assert ok is True
        assert titulo == "Mi Doc"
        assert tabs == ["Ventas", "Gastos"]

    async def test_403_sin_permiso(self, mock_token):
        ctx, _ = _ctx("get", [_mock_resp(403, text="Forbidden")])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.verificar_acceso_hoja("5551", "SID") == (
                False, "sin_permiso", [],
            )

    async def test_404_no_encontrada(self, mock_token):
        ctx, _ = _ctx("get", [_mock_resp(404, text="Not found")])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.verificar_acceso_hoja("5551", "SID") == (
                False, "no_encontrada", [],
            )

    async def test_otro_status_devuelve_falso_vacio(self, mock_token):
        ctx, _ = _ctx("get", [_mock_resp(500, text="Server error")])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.verificar_acceso_hoja("5551", "SID") == (
                False, "", [],
            )

    async def test_excepcion_devuelve_falso_vacio(self, mock_token):
        ctx = _ctx_explota("get")
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.verificar_acceso_hoja("5551", "SID") == (
                False, "", [],
            )

    async def test_ok_sin_titulo_ni_tabs(self, mock_token):
        ctx, _ = _ctx("get", [_mock_resp(200, {})])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            ok, titulo, tabs = await google_sheets.verificar_acceso_hoja("5551", "SID")
        assert (ok, titulo, tabs) == (True, "", [])


# --------------------------------------------------------------------------- #
# leer_rango — rango por defecto vs rango_extra, errores
# --------------------------------------------------------------------------- #
class TestLeerRango:
    async def test_sin_token(self, mock_token_none):
        assert await google_sheets.leer_rango("5551", "SID", "Hoja1") == []

    async def test_ok_devuelve_valores(self, mock_token):
        filas = [["a", "b"], ["1", "2"]]
        ctx, client = _ctx("get", [_mock_resp(200, {"values": filas})])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            resultado = await google_sheets.leer_rango("5551", "SID", "Hoja1")
        assert resultado == filas
        # rango por defecto: Hoja1!A1:Z50 (max_filas default = 50), URL-encoded
        url_llamada = client.get.call_args.args[0]
        assert "Hoja1%21A1%3AZ50" in url_llamada

    async def test_rango_extra_se_usa(self, mock_token):
        ctx, client = _ctx("get", [_mock_resp(200, {"values": []})])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            await google_sheets.leer_rango(
                "5551", "SID", "Hoja1", rango_extra="A1:E10",
            )
        url_llamada = client.get.call_args.args[0]
        assert "Hoja1%21A1%3AE10" in url_llamada

    async def test_max_filas_personalizado(self, mock_token):
        ctx, client = _ctx("get", [_mock_resp(200, {"values": []})])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            await google_sheets.leer_rango("5551", "SID", "Hoja1", max_filas=5)
        assert "Hoja1%21A1%3AZ5" in client.get.call_args.args[0]

    async def test_ok_sin_values_devuelve_vacio(self, mock_token):
        ctx, _ = _ctx("get", [_mock_resp(200, {})])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.leer_rango("5551", "SID", "Hoja1") == []

    async def test_403_devuelve_vacio(self, mock_token):
        ctx, _ = _ctx("get", [_mock_resp(403, text="Forbidden")])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.leer_rango("5551", "SID", "Hoja1") == []

    async def test_otro_status_devuelve_vacio(self, mock_token):
        ctx, _ = _ctx("get", [_mock_resp(500, text="boom")])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.leer_rango("5551", "SID", "Hoja1") == []

    async def test_excepcion_devuelve_vacio(self, mock_token):
        ctx = _ctx_explota("get")
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.leer_rango("5551", "SID", "Hoja1") == []


# --------------------------------------------------------------------------- #
# agregar_fila_api — append
# --------------------------------------------------------------------------- #
class TestAgregarFilaApi:
    async def test_sin_token(self, mock_token_none):
        assert await google_sheets.agregar_fila_api("5551", "SID", "Hoja1", ["a"]) is False

    async def test_200_ok(self, mock_token):
        ctx, _ = _ctx("post", [_mock_resp(200, {})])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.agregar_fila_api(
                "5551", "SID", "Hoja1", ["a", "b"],
            ) is True

    async def test_201_ok(self, mock_token):
        ctx, _ = _ctx("post", [_mock_resp(201, {})])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.agregar_fila_api(
                "5551", "SID", "Hoja1", ["a"],
            ) is True

    async def test_error_devuelve_falso(self, mock_token):
        ctx, _ = _ctx("post", [_mock_resp(400, text="Bad request")])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.agregar_fila_api(
                "5551", "SID", "Hoja1", ["a"],
            ) is False

    async def test_excepcion_devuelve_falso(self, mock_token):
        ctx = _ctx_explota("post")
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.agregar_fila_api(
                "5551", "SID", "Hoja1", ["a"],
            ) is False


# --------------------------------------------------------------------------- #
# actualizar_celda_api — update
# --------------------------------------------------------------------------- #
class TestActualizarCeldaApi:
    async def test_sin_token(self, mock_token_none):
        assert await google_sheets.actualizar_celda_api(
            "5551", "SID", "Hoja1", "B3", "x",
        ) is False

    async def test_200_ok(self, mock_token):
        ctx, _ = _ctx("put", [_mock_resp(200, {})])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.actualizar_celda_api(
                "5551", "SID", "Hoja1", "B3", "nuevo",
            ) is True

    async def test_error_devuelve_falso(self, mock_token):
        ctx, _ = _ctx("put", [_mock_resp(403, text="Forbidden")])
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.actualizar_celda_api(
                "5551", "SID", "Hoja1", "B3", "x",
            ) is False

    async def test_excepcion_devuelve_falso(self, mock_token):
        ctx = _ctx_explota("put")
        with patch("agent.google_sheets.httpx.AsyncClient", return_value=ctx):
            assert await google_sheets.actualizar_celda_api(
                "5551", "SID", "Hoja1", "B3", "x",
            ) is False


# --------------------------------------------------------------------------- #
# buscar_y_actualizar — lógica pura de matching (leer_rango + update mockeados)
# --------------------------------------------------------------------------- #
class TestBuscarYActualizar:
    _FILAS = [
        ["Nombre", "Estado", "Monto"],
        ["Ana", "Abierto", "100"],
        ["Bob", "Cerrado", "200"],
    ]

    def _patch_leer(self, monkeypatch, filas):
        async def fake_leer(*a, **k):
            return filas
        monkeypatch.setattr(google_sheets, "leer_rango", fake_leer)

    def _patch_actualizar(self, monkeypatch, resultado=True, capturado=None):
        async def fake_act(telefono, sid, hoja, celda, valor):
            if capturado is not None:
                capturado["celda"] = celda
                capturado["valor"] = valor
            return resultado
        monkeypatch.setattr(google_sheets, "actualizar_celda_api", fake_act)

    async def test_hoja_vacia(self, monkeypatch):
        self._patch_leer(monkeypatch, [])
        ok, msg = await google_sheets.buscar_y_actualizar(
            "5551", "SID", "Hoja1", "Nombre", "Ana", "Estado", "Cerrado",
        )
        assert ok is False
        assert "No se pudo leer" in msg

    async def test_columna_busqueda_no_existe(self, monkeypatch):
        self._patch_leer(monkeypatch, self._FILAS)
        ok, msg = await google_sheets.buscar_y_actualizar(
            "5551", "SID", "Hoja1", "Telefono", "Ana", "Estado", "Cerrado",
        )
        assert ok is False
        assert "Telefono" in msg and "no encontrada" in msg

    async def test_columna_actualizar_no_existe(self, monkeypatch):
        self._patch_leer(monkeypatch, self._FILAS)
        ok, msg = await google_sheets.buscar_y_actualizar(
            "5551", "SID", "Hoja1", "Nombre", "Ana", "Prioridad", "Alta",
        )
        assert ok is False
        assert "Prioridad" in msg and "no encontrada" in msg

    async def test_valor_no_encontrado(self, monkeypatch):
        self._patch_leer(monkeypatch, self._FILAS)
        ok, msg = await google_sheets.buscar_y_actualizar(
            "5551", "SID", "Hoja1", "Nombre", "Carlos", "Estado", "Cerrado",
        )
        assert ok is False
        assert "No encontré" in msg

    async def test_actualizacion_exitosa_celda_correcta(self, monkeypatch):
        self._patch_leer(monkeypatch, self._FILAS)
        capturado = {}
        self._patch_actualizar(monkeypatch, resultado=True, capturado=capturado)
        ok, msg = await google_sheets.buscar_y_actualizar(
            "5551", "SID", "Hoja1", "Nombre", "Bob", "Estado", "Pagado",
        )
        assert ok is True
        # Bob está en la fila de datos 2 → fila 3 de la hoja (header=1); Estado=col B
        assert capturado["celda"] == "B3"
        assert capturado["valor"] == "Pagado"
        assert "fila 3" in msg

    async def test_matching_case_insensitive(self, monkeypatch):
        self._patch_leer(monkeypatch, self._FILAS)
        capturado = {}
        self._patch_actualizar(monkeypatch, resultado=True, capturado=capturado)
        # columnas y valor con mayúsculas/minúsculas distintas al header/celda
        ok, _ = await google_sheets.buscar_y_actualizar(
            "5551", "SID", "Hoja1", "NOMBRE", "ana", "estado", "Cerrado",
        )
        assert ok is True
        assert capturado["celda"] == "B2"  # Ana = fila datos 1 → hoja fila 2

    async def test_escritura_falla_devuelve_error(self, monkeypatch):
        self._patch_leer(monkeypatch, self._FILAS)
        self._patch_actualizar(monkeypatch, resultado=False)
        ok, msg = await google_sheets.buscar_y_actualizar(
            "5551", "SID", "Hoja1", "Nombre", "Ana", "Estado", "Cerrado",
        )
        assert ok is False
        assert "Error al escribir" in msg
