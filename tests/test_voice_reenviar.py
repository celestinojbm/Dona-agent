# tests/test_voice_reenviar.py — Verifica /voice/reenviar con env var.

"""
PR3 (T0.5 fusionada): el endpoint /voice/reenviar lee el destino desde la
env var VOICE_FORWARD_NUMBER. Sin la var, devuelve 404. Con formato inválido,
devuelve 500. Ningún número personal queda en el código.
"""

import os
import pytest
from fastapi.testclient import TestClient


# agent.main requiere apscheduler. Si no está disponible, saltamos toda la suite.
_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:
    _main_disponible = False


_requiere_main = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler (no instalado en este entorno)",
)


@_requiere_main
class TestVoiceReenviar:

    def setup_method(self):
        from agent.main import app
        self.client = TestClient(app)

    def test_sin_env_var_devuelve_404(self, monkeypatch):
        monkeypatch.delenv("VOICE_FORWARD_NUMBER", raising=False)
        r = self.client.get("/voice/reenviar")
        assert r.status_code == 404
        assert "voice_forward" in r.text or "voice_forward" in r.json().get("detail", "")

    def test_env_var_vacia_devuelve_404(self, monkeypatch):
        monkeypatch.setenv("VOICE_FORWARD_NUMBER", "   ")
        r = self.client.get("/voice/reenviar")
        assert r.status_code == 404

    def test_env_var_formato_invalido_devuelve_500(self, monkeypatch):
        monkeypatch.setenv("VOICE_FORWARD_NUMBER", "no-es-un-numero")
        r = self.client.get("/voice/reenviar")
        assert r.status_code == 500

    def test_env_var_demasiado_corto_devuelve_500(self, monkeypatch):
        monkeypatch.setenv("VOICE_FORWARD_NUMBER", "12345")  # < 10 dígitos
        r = self.client.get("/voice/reenviar")
        assert r.status_code == 500

    def test_env_var_valida_genera_twiml_con_destino(self, monkeypatch):
        monkeypatch.setenv("VOICE_FORWARD_NUMBER", "+15551234567")
        r = self.client.get("/voice/reenviar")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/xml")
        assert "<Dial>+15551234567</Dial>" in r.text
        assert r.text.startswith('<?xml')

    def test_env_var_sin_signo_se_normaliza(self, monkeypatch):
        monkeypatch.setenv("VOICE_FORWARD_NUMBER", "15551234567")
        r = self.client.get("/voice/reenviar")
        assert r.status_code == 200
        # Debe agregar '+' al armar el TwiML.
        assert "<Dial>+15551234567</Dial>" in r.text

    def test_post_funciona_igual_que_get(self, monkeypatch):
        monkeypatch.setenv("VOICE_FORWARD_NUMBER", "+15551234567")
        r = self.client.post("/voice/reenviar")
        assert r.status_code == 200
        assert "<Dial>+15551234567</Dial>" in r.text


@_requiere_main
def test_no_hay_numero_personal_hardcodeado_en_main():
    """
    Smoke test: verifica que el endpoint runtime no contiene un número personal
    embebido. Solo cubre el bloque del endpoint, no docstrings ni tests.
    """
    import inspect
    from agent.main import voice_reenviar

    fuente = inspect.getsource(voice_reenviar)
    # No debe haber ningún literal E.164 dentro del cuerpo del handler.
    import re
    matches = re.findall(r"\+?\d{10,15}", fuente)
    assert matches == [], (
        f"Detectado numero E.164 hardcodeado en voice_reenviar: {matches}"
    )
