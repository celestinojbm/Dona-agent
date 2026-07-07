# tests/test_admin_auth_bearer_only.py — SEC-AUTH-03 · Fase 0 · TEMA 6

"""
Cubre el endurecimiento de auth admin: el token ya NO se acepta por query
string, SOLO por header ``Authorization: Bearer <token>``. Los tests recorren
todos los endpoints admin que pasaban ``token`` como query param legacy y
verifican el guard ``_verificar_admin(request)`` en cada uno:

  (a) token en query string  → 403 (rechazado, ya no es válido)
  (b) header Bearer correcto  → 200 (ruta feliz sigue funcionando)

El caso (a) ejercita la línea del guard en cada handler (el fallback de query
string quedaba en historial del navegador, logs de proxies/CDN y edge logs de
Render, fuera del control del formatter de la app). El caso (b) recorre además
el cuerpo del endpoint sobre una SQLite aislada para dar margen de cobertura.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:
    _main_disponible = False


_requiere_main = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler",
)

ADMIN_TOKEN = "test-admin-token-bearer-only"
TEL = "15551234567"


# ── (a) token en query string → 403 en cada endpoint admin ───────────────────
#
# El guard ``if not _verificar_admin(request)`` es la primera sentencia de cada
# handler, así que la ruta 403 no toca DB ni red — basta con el TestClient del
# app cargado en import-time. Cada entrada incluye los query params requeridos
# (p. ej. ``telefono``) para que FastAPI no corte con 422 ANTES del handler y el
# guard llegue a ejecutarse.

_ENDPOINTS_QUERY_RECHAZADA = [
    # (metodo, path_con_params_requeridos_y_token_en_query)
    ("get", f"/diagnostico?token={ADMIN_TOKEN}"),
    ("get", f"/admin/metrics?token={ADMIN_TOKEN}"),
    ("get", f"/admin/tools-catalog?token={ADMIN_TOKEN}"),
    ("get", f"/admin/onboarding?telefono={TEL}&token={ADMIN_TOKEN}"),
    ("post", f"/admin/onboarding/reset?telefono={TEL}&token={ADMIN_TOKEN}"),
    ("get", f"/admin/jobs-recientes?telefono={TEL}&token={ADMIN_TOKEN}"),
    ("get", f"/admin/r2-check?token={ADMIN_TOKEN}"),
    (
        "post",
        f"/admin/seed-creditos?telefono={TEL}&creditos=10&token={ADMIN_TOKEN}",
    ),
    ("get", f"/admin/recordatorios?telefono={TEL}&token={ADMIN_TOKEN}"),
    ("get", f"/admin/inbound/token?telefono={TEL}&token={ADMIN_TOKEN}"),
    ("get", f"/admin/automation/prune/preview?token={ADMIN_TOKEN}"),
    ("post", f"/admin/automation/prune?confirm=BORRAR&token={ADMIN_TOKEN}"),
    ("get", f"/admin/automation/scheduler/status?token={ADMIN_TOKEN}"),
    (
        "get",
        f"/admin/automation/credits/reconciliar/preview?token={ADMIN_TOKEN}",
    ),
    ("post", f"/admin/automation/credits/reconciliar?token={ADMIN_TOKEN}"),
]


@_requiere_main
class TestTokenEnQueryStringRechazado:
    """SEC-AUTH-03: ningún endpoint admin acepta ya el token por query string."""

    def setup_method(self):
        from agent.main import app
        self.client = TestClient(app)

    @pytest.mark.parametrize("metodo,url", _ENDPOINTS_QUERY_RECHAZADA)
    def test_query_string_devuelve_403(self, monkeypatch, metodo, url):
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        r = getattr(self.client, metodo)(url)
        assert r.status_code == 403, (
            f"{metodo.upper()} {url} debería rechazar el token por query "
            f"string con 403, devolvió {r.status_code}"
        )

    @pytest.mark.parametrize("metodo,url", _ENDPOINTS_QUERY_RECHAZADA)
    def test_sin_token_alguno_devuelve_403(self, monkeypatch, metodo, url):
        # Aun con el query param presente pero SIN header, es 403: confirma que
        # el guard no cae por otra vía.
        monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
        # Quitamos el token del query para el caso "sin credencial alguna".
        url_sin_token = url.replace(f"&token={ADMIN_TOKEN}", "").replace(
            f"?token={ADMIN_TOKEN}", ""
        )
        # Si tras quitar el token la URL empieza con '&', re-normaliza a '?'.
        url_sin_token = url_sin_token.replace("?&", "?")
        r = getattr(self.client, metodo)(url_sin_token)
        assert r.status_code in (403, 422), (
            f"{metodo.upper()} {url_sin_token} sin credencial debería ser 403, "
            f"devolvió {r.status_code}"
        )


# ── (b) header Bearer correcto → 200 recorriendo el cuerpo del handler ───────
#
# Sobre una SQLite aislada (mismo patrón que test_automation_endpoints.py:
# reload de módulos tras setear env vars). Solo endpoints read-only baratos.


@pytest.fixture
async def app_db(tmp_path, monkeypatch):
    """App FastAPI fresca con SQLite aislada y ADMIN_TOKEN de test.

    Recargamos también los modelos de automation ANTES de inicializar_db para
    que sus tablas (automation_reservas_credito, automation_misiones, etc.)
    queden registradas en el metadata y existan en la SQLite de test —mismo
    patrón que tests/test_automation_endpoints.py.
    """
    db_path = tmp_path / "admin_auth.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    import agent.automation.models as _am
    import agent.business.models as _bm
    import agent.memory
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    import agent.main as _main
    importlib.reload(_main)
    await agent.memory.inicializar_db()
    return _main.app


_ENDPOINTS_BEARER_200 = [
    ("get", "/admin/metrics"),
    ("get", "/admin/tools-catalog"),
    ("get", f"/admin/onboarding?telefono={TEL}"),
    ("post", f"/admin/onboarding/reset?telefono={TEL}&fase=0&paso=0"),
    ("get", f"/admin/jobs-recientes?telefono={TEL}"),
    ("get", f"/admin/recordatorios?telefono={TEL}"),
    ("get", f"/admin/inbound/token?telefono={TEL}"),
    ("get", "/admin/automation/prune/preview"),
    ("get", "/admin/automation/scheduler/status"),
    ("get", "/admin/automation/credits/reconciliar/preview"),
]


@_requiere_main
class TestBearerHeaderAcepta:
    """Regresión: el header Authorization: Bearer sigue dando 200 (ruta feliz)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metodo,url", _ENDPOINTS_BEARER_200)
    async def test_bearer_correcto_devuelve_200(self, app_db, metodo, url):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_db), base_url="http://test"
        ) as c:
            r = await getattr(c, metodo)(
                url, headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
            )
        assert r.status_code == 200, (
            f"{metodo.upper()} {url} con Bearer correcto debería ser 200, "
            f"devolvió {r.status_code}: {r.text[:200]}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metodo,url", _ENDPOINTS_BEARER_200)
    async def test_bearer_invalido_devuelve_403(self, app_db, metodo, url):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_db), base_url="http://test"
        ) as c:
            r = await getattr(c, metodo)(
                url, headers={"Authorization": "Bearer token-equivocado"}
            )
        assert r.status_code == 403
