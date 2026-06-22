# tests/test_tema0_failclosed.py — Fase 0 · Tema 0 · fail-closed de cifrado y DB

"""
0.4 — `cifrar()` NO debe degradar a texto plano si el cifrado está activo pero
falla: en entorno estricto relanza (no persistir un secreto sin cifrar). El
código viejo hacía log + `return valor` (fail-open silencioso). `descifrar` sí
queda fail-open a propósito (compat con valores legacy en texto plano).

0.3 — `inicializar_db` no debe arrancar con un esquema roto: en entorno estricto
RELANZA tras agotar reintentos (antes: '# No relanzar' → fail-open). Dev/test
sigue lenient para no bloquear el desarrollo.
"""

import asyncio

import pytest


# ── 0.4 · cifrar() fail-closed ─────────────────────────────────────────────


class _FernetEncryptRoto:
    def encrypt(self, _b):
        raise ValueError("encrypt boom")


class _FernetDecryptRoto:
    def decrypt(self, _b):
        raise ValueError("decrypt boom")


def test_cifrar_falla_en_estricto_relanza(monkeypatch):
    import agent.crypto as crypto

    monkeypatch.setattr(crypto, "es_entorno_estricto", lambda: True)
    monkeypatch.setattr(crypto, "_fernet", _FernetEncryptRoto())
    with pytest.raises(RuntimeError):
        crypto.cifrar("token-oauth-secreto")


def test_cifrar_falla_en_dev_devuelve_original(monkeypatch):
    import agent.crypto as crypto

    monkeypatch.setattr(crypto, "es_entorno_estricto", lambda: False)
    monkeypatch.setattr(crypto, "_fernet", _FernetEncryptRoto())
    assert crypto.cifrar("token") == "token"


def test_cifrar_sin_fernet_no_aplica_failclosed(monkeypatch):
    """Sin cifrado activo (clave ausente) cifrar es pass-through aunque sea
    estricto: la exigencia de clave en estricto la cubre _inicializar_fernet al
    importar, no cifrar()."""
    import agent.crypto as crypto

    monkeypatch.setattr(crypto, "es_entorno_estricto", lambda: True)
    monkeypatch.setattr(crypto, "_fernet", None)
    assert crypto.cifrar("token") == "token"


def test_descifrar_mantiene_fail_open(monkeypatch):
    """descifrar es fail-open a propósito: un valor que no descifra suele ser
    texto plano legacy (migración pendiente) — devolverlo no es una fuga."""
    import agent.crypto as crypto

    monkeypatch.setattr(crypto, "es_entorno_estricto", lambda: True)
    monkeypatch.setattr(crypto, "_fernet", _FernetDecryptRoto())
    assert crypto.descifrar("valor-legacy-en-claro") == "valor-legacy-en-claro"


# ── 0.3 · inicializar_db fail-closed ───────────────────────────────────────


async def _noop_async(*_a, **_k):
    return None


class _FakeEngineBoom:
    """Engine cuyo begin() revienta — simula DB caída sin tocar la real
    (AsyncEngine.begin es read-only, no se puede monkeypatch directo)."""

    def begin(self):
        raise OSError("db down")


async def test_inicializar_db_aborta_en_estricto(monkeypatch):
    """Fallo persistente de DB en entorno estricto → RELANZA (no arranca con
    esquema roto). Antes: '# No relanzar' → fail-open."""
    import agent.entorno
    import agent.memory as memory

    monkeypatch.setattr(agent.entorno, "es_entorno_estricto", lambda: True)
    monkeypatch.setattr(asyncio, "sleep", _noop_async)  # sin backoff real
    monkeypatch.setattr(memory, "engine", _FakeEngineBoom())
    with pytest.raises(RuntimeError):
        await memory.inicializar_db()


async def test_inicializar_db_lenient_en_dev(monkeypatch):
    """En dev/test un fallo de DB NO bloquea el arranque (no relanza)."""
    import agent.entorno
    import agent.memory as memory

    monkeypatch.setattr(agent.entorno, "es_entorno_estricto", lambda: False)
    monkeypatch.setattr(memory, "engine", _FakeEngineBoom())
    monkeypatch.setattr(memory, "_migrar_columnas", _noop_async)
    # No debe relanzar.
    await memory.inicializar_db()
