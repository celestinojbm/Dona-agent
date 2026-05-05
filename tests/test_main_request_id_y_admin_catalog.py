# tests/test_main_request_id_y_admin_catalog.py — Tests T1.6 endpoint level

"""
Cubre:
  - Header X-Request-ID se devuelve en cada response.
  - X-Request-ID forwarded del cliente se respeta.
  - /admin/tools-catalog responde 403 sin token, 200 con token.
  - /admin/metrics sigue funcionando (regresión).
  - El status breakdown nuevo aparece en /admin/metrics.
"""

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


@_requiere_main
class TestRequestIdHeader:
    def setup_method(self):
        from agent.main import app
        self.client = TestClient(app)

    def test_response_incluye_x_request_id(self):
        r = self.client.get("/")  # health check
        # Aunque sea 200 o 503, el middleware corre.
        assert "x-request-id" in {k.lower() for k in r.headers.keys()}
        rid = r.headers.get("X-Request-ID") or r.headers.get("x-request-id")
        assert rid
        # Debe tener prefijo req_ (generado por el backend, no había header
        # entrante).
        assert rid.startswith("req_")

    def test_x_request_id_forwarded_se_respeta(self):
        r = self.client.get("/", headers={"X-Request-ID": "lnd_abc123"})
        rid = r.headers.get("X-Request-ID") or r.headers.get("x-request-id")
        assert rid == "lnd_abc123"

    def test_x_request_id_invalido_se_descarta_y_genera_uno_nuevo(self):
        r = self.client.get("/", headers={"X-Request-ID": "evil$inject!"})
        rid = r.headers.get("X-Request-ID") or r.headers.get("x-request-id")
        assert rid
        # El forwarded se rechazó, el middleware generó uno nuevo.
        assert rid.startswith("req_")
        assert rid != "evil$inject!"


@_requiere_main
class TestAdminToolsCatalog:
    def setup_method(self):
        from agent.main import app
        self.client = TestClient(app)

    def test_sin_token_devuelve_403(self):
        r = self.client.get("/admin/tools-catalog")
        assert r.status_code == 403

    def test_con_token_invalido_devuelve_403(self):
        r = self.client.get(
            "/admin/tools-catalog",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 403

    def test_con_token_correcto_devuelve_catalogo(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
        r = self.client.get(
            "/admin/tools-catalog",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert "por_riesgo" in body
        assert "por_permiso" in body
        assert "tools" in body
        assert body["total"] > 0
        # Spot-check: obtener_saldo está y es leer/autonomo.
        nombres = {t["nombre"] for t in body["tools"]}
        assert "obtener_saldo" in nombres


@_requiere_main
class TestAdminMetricsRegresion:
    def setup_method(self):
        from agent.main import app
        self.client = TestClient(app)

    def test_metrics_sigue_funcionando(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
        r = self.client.get(
            "/admin/metrics",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        assert r.status_code == 200
        body = r.json()
        # Campos viejos siguen presentes.
        assert "requests_total" in body
        assert "requests_por_ruta" in body
        assert "errores_5xx" in body
        # Campos nuevos T1.6.
        assert "por_status_class" in body
        assert "endpoints_criticos" in body
        # por_status_class tiene los 4 buckets.
        assert set(body["por_status_class"].keys()) == {"2xx", "3xx", "4xx", "5xx"}
