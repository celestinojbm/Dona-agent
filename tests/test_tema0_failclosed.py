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


# ── 0.3 · rama Postgres (advisory lock + verificación de tablas) ───────────
# Los tests normales corren en SQLite, así que la rama `if _ES_POSTGRES:` no se
# ejerce. Estos la cubren con una conexión fake (incluye la verificación y el
# fail-closed del esquema incompleto).


class _FakeResultRows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConnPG:
    """Conexión Postgres fake: responde a la query de information_schema con
    una cola de respuestas (una por llamada; reusa la última al agotarse) y
    registra el DDL de creación explícita."""

    def __init__(self, info_responses):
        from sqlalchemy.dialects.postgresql import dialect as _pg

        self.dialect = _pg()
        self._info = list(info_responses)
        self._last = info_responses[-1] if info_responses else []
        self.ddl = []

    async def run_sync(self, _fn):
        return None  # create_all: no-op (las tablas las simula information_schema)

    async def execute(self, stmt, *_a, **_k):
        s = str(stmt)
        if "information_schema" in s:
            rows = self._info.pop(0) if self._info else self._last
            return _FakeResultRows(rows)
        if "CREATE TABLE" in s:
            self.ddl.append(s)
        return _FakeResultRows([])


class _FakeBeginCtx:
    def __init__(self, conn):
        self._c = conn

    async def __aenter__(self):
        return self._c

    async def __aexit__(self, *_a):
        return False


class _FakeEnginePG:
    def __init__(self, conn):
        self._c = conn

    def begin(self):
        return _FakeBeginCtx(self._c)


def _filas(tablas):
    return [(t,) for t in tablas]


async def test_inicializar_db_postgres_crea_tablas_faltantes(monkeypatch):
    """Rama Postgres: tras create_all falta una tabla → se crea explícita y la
    re-verificación la encuentra → arranca OK."""
    import agent.entorno
    import agent.memory as memory

    monkeypatch.setattr(agent.entorno, "es_entorno_estricto", lambda: True)
    monkeypatch.setattr(memory, "_ES_POSTGRES", True)
    monkeypatch.setattr(memory, "_migrar_columnas", _noop_async)

    todas = sorted(memory.Base.metadata.tables.keys())
    falta = todas[0]
    conn = _FakeConnPG([_filas(todas[1:]), _filas(todas)])  # 1ra: falta; re-verify: todas
    monkeypatch.setattr(memory, "engine", _FakeEnginePG(conn))

    await memory.inicializar_db()  # no relanza
    assert any(falta in ddl for ddl in conn.ddl)  # se forzó la creación de la faltante


async def test_inicializar_db_postgres_todas_presentes(monkeypatch):
    """Rama Postgres: todas las tablas presentes tras create_all → sin DDL extra."""
    import agent.entorno
    import agent.memory as memory

    monkeypatch.setattr(agent.entorno, "es_entorno_estricto", lambda: False)
    monkeypatch.setattr(memory, "_ES_POSTGRES", True)
    monkeypatch.setattr(memory, "_migrar_columnas", _noop_async)

    todas = sorted(memory.Base.metadata.tables.keys())
    conn = _FakeConnPG([_filas(todas)])
    monkeypatch.setattr(memory, "engine", _FakeEnginePG(conn))

    await memory.inicializar_db()
    assert conn.ddl == []  # no hizo falta crear nada


async def test_inicializar_db_postgres_esquema_incompleto_aborta(monkeypatch):
    """Fail-closed (0.3): si tras create_all + creación explícita la tabla SIGUE
    faltando (fallo real de esquema), en estricto se aborta el arranque."""
    import agent.entorno
    import agent.memory as memory

    monkeypatch.setattr(agent.entorno, "es_entorno_estricto", lambda: True)
    monkeypatch.setattr(asyncio, "sleep", _noop_async)
    monkeypatch.setattr(memory, "_ES_POSTGRES", True)
    monkeypatch.setattr(memory, "_migrar_columnas", _noop_async)

    todas = sorted(memory.Base.metadata.tables.keys())
    # information_schema SIEMPRE devuelve el set sin la primera tabla → faltante
    # persistente tanto en la verificación inicial como en la re-verificación.
    conn = _FakeConnPG([_filas(todas[1:])])
    monkeypatch.setattr(memory, "engine", _FakeEnginePG(conn))

    with pytest.raises(RuntimeError):
        await memory.inicializar_db()
