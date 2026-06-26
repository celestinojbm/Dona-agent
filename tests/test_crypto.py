# tests/test_crypto.py — Cifrado de datos sensibles (tokens OAuth) · API pública

"""
Cobertura de la API pública de ``agent.crypto`` (cifrar / descifrar /
esta_activo) y de las ramas de ``_inicializar_fernet`` no ejercitadas por
``test_fail_closed_entorno.py`` (que solo cubre los abort fail-closed).

Estos tests FIJAN el comportamiento actual del módulo:
  - round-trip cifrar→descifrar con una clave Fernet activa,
  - passthrough cuando NO hay clave configurada (``_fernet is None``),
  - fail-OPEN de ``descifrar`` ante valores no cifrados (legacy/migración),
  - fail-CLOSED de ``cifrar`` en entorno estricto si ``encrypt`` falla,
  - fail-OPEN de ``cifrar`` en dev/test si ``encrypt`` falla.

``_fernet`` se cachea en import-time. Para ejercitar la API con cifrado activo
se inyecta un Fernet real vía ``monkeypatch.setattr`` (auto-restaurado), sin
recargar el módulo: las funciones leen el global ``_fernet`` en cada llamada y
``_inicializar_fernet`` lee ``os.getenv`` en cada invocación, así que no hace
falta ``importlib.reload`` para estos casos.
"""

from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

import agent.crypto as crypto


@pytest.fixture
def fernet_real() -> Fernet:
    """Fernet con clave generada al vuelo (nunca una clave real de prod)."""
    return Fernet(Fernet.generate_key())


@pytest.fixture
def crypto_activo(monkeypatch, fernet_real):
    """``agent.crypto`` con cifrado activo: inyecta el Fernet real en el global
    ``_fernet`` (restaurado por monkeypatch al terminar el test)."""
    monkeypatch.setattr(crypto, "_fernet", fernet_real)
    return crypto


# ── API pública con cifrado activo ───────────────────────────────────────────

class TestCifradoActivo:
    def test_round_trip_recupera_el_original(self, crypto_activo):
        original = "ya29.token-oauth-secreto-1234567890"
        cifrado = crypto_activo.cifrar(original)
        assert cifrado != original  # realmente cifró
        assert crypto_activo.descifrar(cifrado) == original

    def test_cifrar_es_no_determinista(self, crypto_activo):
        """Fernet incluye IV+timestamp: dos cifrados del mismo texto difieren,
        pero ambos descifran al original."""
        a = crypto_activo.cifrar("mismo-valor")
        b = crypto_activo.cifrar("mismo-valor")
        assert a != b
        assert crypto_activo.descifrar(a) == "mismo-valor"
        assert crypto_activo.descifrar(b) == "mismo-valor"

    def test_esta_activo_true_con_clave(self, crypto_activo):
        assert crypto_activo.esta_activo() is True

    def test_cifrar_valor_vacio_es_passthrough(self, crypto_activo):
        # `not valor` corta antes de tocar Fernet.
        assert crypto_activo.cifrar("") == ""

    def test_descifrar_valor_vacio_es_passthrough(self, crypto_activo):
        assert crypto_activo.descifrar("") == ""

    def test_descifrar_valor_no_cifrado_devuelve_original(self, crypto_activo):
        """Fail-OPEN deliberado: un valor legacy en texto plano (no es un token
        Fernet válido) se devuelve tal cual en vez de explotar."""
        assert crypto_activo.descifrar("texto-plano-legacy") == "texto-plano-legacy"


# ── API pública SIN clave (modo transparente) ────────────────────────────────

class TestSinClave:
    def test_cifrar_y_descifrar_passthrough(self, monkeypatch):
        monkeypatch.setattr(crypto, "_fernet", None)
        assert crypto.cifrar("dato-sensible") == "dato-sensible"
        assert crypto.descifrar("dato-sensible") == "dato-sensible"

    def test_esta_activo_false_sin_clave(self, monkeypatch):
        monkeypatch.setattr(crypto, "_fernet", None)
        assert crypto.esta_activo() is False


# ── Fail-closed / fail-open de cifrar ante error de encrypt ───────────────────

class TestCifrarErrorDeEncrypt:
    def _fernet_que_explota(self):
        f = MagicMock()
        f.encrypt.side_effect = RuntimeError("encrypt reventó")
        return f

    def test_entorno_estricto_relanza_y_no_degrada(self, monkeypatch):
        """Si el cifrado está activo pero ``encrypt`` falla en entorno estricto,
        NO debe devolver el valor en claro: relanza RuntimeError."""
        monkeypatch.setattr(crypto, "_fernet", self._fernet_que_explota())
        monkeypatch.setenv("ENVIRONMENT", "prod")  # estricto
        with pytest.raises(RuntimeError, match="entorno estricto"):
            crypto.cifrar("secreto")

    def test_entorno_dev_degrada_a_original_con_log(self, monkeypatch):
        """En dev/test explícito, el mismo fallo de ``encrypt`` devuelve el
        valor original (fail-open) en vez de abortar."""
        monkeypatch.setattr(crypto, "_fernet", self._fernet_que_explota())
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert crypto.cifrar("secreto") == "secreto"


# ── _inicializar_fernet: ramas no cubiertas por el fail-closed suite ──────────

class TestInicializarFernet:
    def test_clave_valida_construye_fernet_funcional(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        f = crypto._inicializar_fernet()
        assert f is not None
        # El Fernet devuelto realmente cifra y descifra.
        assert f.decrypt(f.encrypt(b"x")) == b"x"

    def test_clave_invalida_en_dev_retorna_none(self, monkeypatch):
        """En dev/test una clave inválida NO aborta: loguea y degrada a None
        (texto plano). El abort solo ocurre en entorno estricto."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ENCRYPTION_KEY", "no-es-una-clave-fernet")
        assert crypto._inicializar_fernet() is None
