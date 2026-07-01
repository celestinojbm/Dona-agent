# tests/test_crypto_roundtrip.py — Round-trip funcional del cifrado de tokens

"""Cubre el camino feliz de ``agent.crypto`` con una clave Fernet REAL.

Los tests existentes (``test_fail_closed_entorno``, ``test_tema0_failclosed``)
ya fijan el comportamiento fail-closed/fail-open usando mocks de Fernet, pero
nadie ejercita el cifrado real de extremo a extremo: que ``cifrar`` luego
``descifrar`` devuelva el valor original, que el valor vacío sea pass-through
con cifrado activo, que ``esta_activo`` refleje el estado, y que ``descifrar``
mantenga su fail-open (texto plano legacy) atravesando un Fernet REAL.

``agent.crypto`` construye ``_fernet`` en import-time, así que estos tests
recargan el módulo con ``importlib.reload`` tras setear las env vars — el
patrón documentado en CLAUDE.md §5. El fixture restaura el módulo a su estado
ambiente (ENVIRONMENT=test, sin ENCRYPTION_KEY) al terminar para no contaminar
otros tests que importan ``agent.crypto``.
"""

import importlib

import pytest
from cryptography.fernet import Fernet


@pytest.fixture
def cargar_crypto(monkeypatch):
    """Loader que recarga ``agent.crypto`` con env controlado y restaura el
    módulo a su estado original en el teardown."""
    import agent.crypto as crypto

    def _cargar(key=None, environment="test"):
        monkeypatch.setenv("ENVIRONMENT", environment)
        if key is None:
            monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        else:
            monkeypatch.setenv("ENCRYPTION_KEY", key)
        importlib.reload(crypto)
        return crypto

    yield _cargar

    # Revierte las env vars antes de recargar para dejar el módulo coherente
    # con el entorno ambiente (ENVIRONMENT=test, ENCRYPTION_KEY ausente).
    monkeypatch.undo()
    importlib.reload(crypto)


def test_roundtrip_devuelve_original(cargar_crypto):
    """cifrar → descifrar con una clave válida recupera el valor original."""
    crypto = cargar_crypto(key=Fernet.generate_key().decode())
    secreto = "token-oauth-simulado-muy-secreto"  # gitleaks:allow — valor de prueba
    cifrado = crypto.cifrar(secreto)
    assert cifrado != secreto  # realmente cifró
    assert crypto.descifrar(cifrado) == secreto


def test_cifrar_con_clave_no_es_texto_plano(cargar_crypto):
    """Con cifrado activo, el output no contiene el secreto en claro."""
    crypto = cargar_crypto(key=Fernet.generate_key().decode())
    secreto = "valor-sensible-123"  # gitleaks:allow — valor de prueba
    cifrado = crypto.cifrar(secreto)
    assert secreto not in cifrado


def test_dos_cifrados_distintos_mismo_plano(cargar_crypto):
    """Fernet incluye timestamp/IV: dos cifrados del mismo valor difieren pero
    ambos descifran al original."""
    crypto = cargar_crypto(key=Fernet.generate_key().decode())
    secreto = "mismo-secreto"
    a = crypto.cifrar(secreto)
    b = crypto.cifrar(secreto)
    assert a != b
    assert crypto.descifrar(a) == secreto
    assert crypto.descifrar(b) == secreto


def test_esta_activo_con_clave_valida(cargar_crypto):
    crypto = cargar_crypto(key=Fernet.generate_key().decode())
    assert crypto.esta_activo() is True


def test_esta_activo_sin_clave_en_dev(cargar_crypto):
    """Sin ENCRYPTION_KEY en entorno permisivo, el cifrado no se activa."""
    crypto = cargar_crypto(key=None, environment="development")
    assert crypto.esta_activo() is False


def test_cifrar_valor_vacio_pass_through(cargar_crypto):
    """El valor vacío es pass-through aunque el cifrado esté activo
    (rama ``not valor``)."""
    crypto = cargar_crypto(key=Fernet.generate_key().decode())
    assert crypto.cifrar("") == ""


def test_descifrar_valor_vacio_pass_through(cargar_crypto):
    crypto = cargar_crypto(key=Fernet.generate_key().decode())
    assert crypto.descifrar("") == ""


def test_descifrar_texto_plano_legacy_fail_open(cargar_crypto):
    """Fail-open real: con cifrado ACTIVO, descifrar un valor que no es
    ciphertext válido (texto plano legacy / migración pendiente) lo devuelve
    tal cual en vez de romper."""
    crypto = cargar_crypto(key=Fernet.generate_key().decode())
    plano = "token-legacy-sin-cifrar"
    assert crypto.descifrar(plano) == plano


def test_descifrar_con_otra_clave_fail_open(cargar_crypto):
    """Un ciphertext de OTRA clave no descifra; fail-open lo devuelve sin
    romper (no es una fuga: es un blob indescifrable, no el secreto)."""
    otro_fernet = Fernet(Fernet.generate_key())
    ajeno = otro_fernet.encrypt(b"secreto-de-otra-instancia").decode()
    crypto = cargar_crypto(key=Fernet.generate_key().decode())
    assert crypto.descifrar(ajeno) == ajeno


def test_dev_con_clave_valida_activa_cifrado(cargar_crypto):
    """Una clave válida activa el cifrado incluso en entorno permisivo."""
    crypto = cargar_crypto(key=Fernet.generate_key().decode(), environment="development")
    assert crypto.esta_activo() is True
    assert crypto.descifrar(crypto.cifrar("x")) == "x"
