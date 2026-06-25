# tests/test_crypto_cifrado.py — Cobertura del cifrado de tokens sensibles (Fernet)

"""
Fija el COMPORTAMIENTO ACTUAL de ``agent/crypto.py``: round-trip de cifrado,
modo transparente sin clave, fail-open de ``descifrar`` (compat con texto plano
legacy / claves rotadas) y fail-closed de ``cifrar`` en entorno estricto.

Las ramas de ``_inicializar_fernet`` en entorno estricto (clave ausente o
inválida) ya están cubiertas por
``test_fail_closed_entorno.py::TestCryptoFailClosed``. Aquí se cubren las
funciones públicas ``cifrar`` / ``descifrar`` / ``esta_activo`` y el camino feliz
de inicialización, que no tenían cobertura funcional.

El módulo cachea ``_fernet`` en import-time; para no depender de ese estado se
inyecta un Fernet real (o ``None``) con ``monkeypatch.setattr`` sobre el global,
mismo patrón que el resto del repo usa para sustituir estado de módulo.
"""

import pytest
from cryptography.fernet import Fernet

import agent.crypto as crypto


@pytest.fixture
def fernet_activo(monkeypatch):
    """Inyecta un Fernet real en el módulo (cifrado activo), independiente del
    estado de import."""
    f = Fernet(Fernet.generate_key())
    monkeypatch.setattr(crypto, "_fernet", f)
    return f


@pytest.fixture
def fernet_inactivo(monkeypatch):
    """Cifrado desactivado (sin clave) — modo texto plano."""
    monkeypatch.setattr(crypto, "_fernet", None)


# ── Round-trip con cifrado activo ────────────────────────────────────────────
class TestRoundTrip:
    def test_cifrar_descifrar_recupera_el_original(self, fernet_activo):
        original = "ya29.token-oauth-secreto"
        cifrado = crypto.cifrar(original)
        assert cifrado != original  # efectivamente cifró
        assert crypto.descifrar(cifrado) == original

    def test_cifrar_produce_salidas_distintas_por_iv(self, fernet_activo):
        # Fernet usa IV/timestamp: dos cifrados del mismo texto difieren...
        a = crypto.cifrar("mismo")
        b = crypto.cifrar("mismo")
        assert a != b
        # ...pero ambos descifran al mismo original.
        assert crypto.descifrar(a) == crypto.descifrar(b) == "mismo"

    def test_round_trip_unicode(self, fernet_activo):
        original = "ñandú · café · 你好 · 🔐"
        assert crypto.descifrar(crypto.cifrar(original)) == original

    def test_esta_activo_true_con_fernet(self, fernet_activo):
        assert crypto.esta_activo() is True


# ── Modo transparente (sin clave) ────────────────────────────────────────────
class TestModoTransparente:
    def test_cifrar_sin_clave_devuelve_original(self, fernet_inactivo):
        assert crypto.cifrar("hola") == "hola"

    def test_descifrar_sin_clave_devuelve_original(self, fernet_inactivo):
        assert crypto.descifrar("hola") == "hola"

    def test_esta_activo_false_sin_fernet(self, fernet_inactivo):
        assert crypto.esta_activo() is False


# ── Valores vacíos / falsy se devuelven tal cual ─────────────────────────────
class TestValoresVacios:
    @pytest.mark.parametrize("valor", ["", None])
    def test_cifrar_valor_vacio_se_devuelve_tal_cual(self, fernet_activo, valor):
        assert crypto.cifrar(valor) == valor

    @pytest.mark.parametrize("valor", ["", None])
    def test_descifrar_valor_vacio_se_devuelve_tal_cual(self, fernet_activo, valor):
        assert crypto.descifrar(valor) == valor


# ── descifrar es fail-open a propósito (compat texto plano / clave rotada) ───
class TestDescifrarFailOpen:
    def test_descifrar_texto_plano_legacy_devuelve_original(self, fernet_activo):
        # Un valor no cifrado (migración pendiente) se devuelve sin tocar.
        assert crypto.descifrar("texto-plano-no-cifrado") == "texto-plano-no-cifrado"

    def test_descifrar_con_otra_clave_devuelve_el_ciphertext(self, monkeypatch):
        # Token cifrado con clave A; el proceso ahora tiene clave B distinta.
        cifrado_con_a = Fernet(Fernet.generate_key()).encrypt(b"x").decode()
        monkeypatch.setattr(crypto, "_fernet", Fernet(Fernet.generate_key()))
        # No puede descifrar → fail-open: devuelve el ciphertext tal cual.
        assert crypto.descifrar(cifrado_con_a) == cifrado_con_a


# ── cifrar es fail-closed cuando el cifrado está activo pero encrypt falla ────
class _FernetRoto:
    """Fernet falso cuyo ``encrypt`` siempre falla (simula corrupción/bug)."""

    def encrypt(self, *_a, **_k):
        raise ValueError("boom")


class TestCifrarFailClosed:
    def test_en_estricto_relanza_si_encrypt_falla(self, monkeypatch):
        monkeypatch.setattr(crypto, "_fernet", _FernetRoto())
        monkeypatch.setenv("ENVIRONMENT", "prod")  # estricto (fail-closed)
        with pytest.raises(RuntimeError, match="entorno estricto"):
            crypto.cifrar("valor-sensible")

    def test_en_dev_degrada_a_original_si_encrypt_falla(self, monkeypatch):
        monkeypatch.setattr(crypto, "_fernet", _FernetRoto())
        monkeypatch.setenv("ENVIRONMENT", "development")  # permisivo
        assert crypto.cifrar("valor-sensible") == "valor-sensible"


# ── _inicializar_fernet: camino feliz y clave inválida en dev ────────────────
class TestInicializar:
    def test_clave_valida_activa_cifrado(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
        f = crypto._inicializar_fernet()
        assert f is not None
        # El objeto devuelto cifra/descifra de verdad.
        assert f.decrypt(f.encrypt(b"x")) == b"x"

    def test_clave_invalida_en_dev_degrada_a_none(self, monkeypatch):
        # En permisivo, una clave inválida NO aborta: degrada a texto plano.
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ENCRYPTION_KEY", "no-es-una-clave-fernet")
        assert crypto._inicializar_fernet() is None
