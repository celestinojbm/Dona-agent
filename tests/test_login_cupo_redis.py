# tests/test_login_cupo_redis.py — Cupo del login de ingeniería sobre Redis falso.
#
# No hay servidor Redis ni base de datos: el cliente es un sorted-set en
# memoria y el ASGI no arranca el lifespan (no toca SQLite ni Postgres).

import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient

import agent.rate_limiter as rl

SECRET = "test-secret-login-cupo-not-real"


class _FakeRedis:
    """Sorted sets mínimos para consumir_cupo, sin red."""

    def __init__(self):
        self.data: dict[str, dict[str, float]] = {}

    def pipeline(self):
        return _Pipe(self)


class _Pipe:
    def __init__(self, store: _FakeRedis):
        self.store = store
        self.ops: list = []

    def zremrangebyscore(self, key, lo, hi):
        self.ops.append(("zrem", key, float(hi)))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def zrange(self, key, start, end, withscores=False):
        self.ops.append(("zrange", key, start, end, withscores))
        return self

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        out = [self._run(op) for op in self.ops]
        self.ops = []
        return out

    def _zs(self, key):
        return self.store.data.setdefault(key, {})

    def _run(self, op):
        nombre = op[0]
        if nombre == "zrem":
            _, key, hi = op
            zs = self._zs(key)
            for member in [m for m, score in zs.items() if score <= hi]:
                del zs[member]
            return 0
        if nombre == "zcard":
            return len(self._zs(op[1]))
        if nombre == "zrange":
            _, key, start, end, withscores = op
            orden = sorted(self._zs(key).items(), key=lambda kv: kv[1])
            corte = orden[start : end + 1]
            if withscores:
                return [(m, s) for m, s in corte]
            return [m for m, _s in corte]
        if nombre == "zadd":
            _, key, mapping = op
            self._zs(key).update(mapping)
            return len(mapping)
        if nombre == "expire":
            return True
        raise AssertionError(nombre)


class _RedisRoto:
    def pipeline(self):
        raise ConnectionError("redis caído")


@pytest.fixture
def redis_falso(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("RATE_LIMIT_LOGIN_MAX", raising=False)
    monkeypatch.delenv("RATE_LIMIT_LOGIN_WINDOW_SECONDS", raising=False)
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET)
    fake = _FakeRedis()
    monkeypatch.setattr(rl, "_redis", fake)
    rl._cupos_mem.clear()
    reloj = {"t": 2_000_000_000.0}
    monkeypatch.setattr(rl, "_time", lambda: reloj["t"])
    return fake, reloj


def _firmar(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _client():
    import agent.main as main

    # ASGITransport no dispara el lifespan de FastAPI en esta versión de
    # httpx, así que el arranque no abre la base. El endpoint tampoco la usa.
    return AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _post(client, ip: str, usuario: str = "engineering", firma: str | None = None):
    body = json.dumps({"ip": ip, "usuario": usuario}).encode()
    headers = {}
    if firma is not None:
        headers["X-Internal-Signature"] = firma
    else:
        headers["X-Internal-Signature"] = _firmar(body)
    return await client.post("/internal/panel/login-cupo", content=body, headers=headers)


def _claves(fake: _FakeRedis) -> list[str]:
    return list(fake.data)


class TestRedisFalso:
    async def test_cinco_pasan_el_sexto_no_y_no_filtra_la_ip(self, redis_falso):
        fake, _reloj = redis_falso
        async with _client() as c:
            for _ in range(5):
                r = await _post(c, "203.0.113.10")
                assert r.status_code == 200
                assert r.json() == {"permitido": True, "retry_after_segundos": 0}
            r6 = await _post(c, "203.0.113.10")
        assert r6.status_code == 200
        assert r6.json() == {"permitido": False, "retry_after_segundos": 900}
        assert "203.0.113.10" not in r6.text
        assert "engineering" not in r6.text
        assert "existe" not in r6.text.lower()
        claves = _claves(fake)
        assert len(claves) == 1
        assert len(fake.data[claves[0]]) == 5
        assert "203.0.113.10" not in claves[0]

    async def test_otra_ip_y_otro_usuario_son_independientes(self, redis_falso):
        _fake, _reloj = redis_falso
        async with _client() as c:
            for _ in range(5):
                assert (await _post(c, "203.0.113.10", "ana")).json()["permitido"] is True
            assert (await _post(c, "203.0.113.10", "ana")).json()["permitido"] is False
            assert (await _post(c, "203.0.113.11", "ana")).json()["permitido"] is True
            assert (await _post(c, "198.51.100.8", "luis")).json()["permitido"] is True

    async def test_la_ventana_se_reabre(self, redis_falso):
        _fake, reloj = redis_falso
        async with _client() as c:
            for _ in range(5):
                await _post(c, "203.0.113.20")
            assert (await _post(c, "203.0.113.20")).json()["permitido"] is False
            reloj["t"] += 900
            assert (await _post(c, "203.0.113.20")).json()["permitido"] is True

    async def test_firma_invalida_no_consume_cupo(self, redis_falso):
        fake, _reloj = redis_falso
        async with _client() as c:
            body = json.dumps({"ip": "203.0.113.10", "usuario": "engineering"}).encode()
            r = await c.post(
                "/internal/panel/login-cupo",
                content=body,
                headers={"X-Internal-Signature": "00" * 32},
            )
        assert r.status_code == 401
        assert fake.data == {}

    async def test_redis_caido_cae_a_memoria_y_sigue_limitando(self, redis_falso, monkeypatch):
        _fake, _reloj = redis_falso
        monkeypatch.setattr(rl, "_redis", _RedisRoto())
        antes = rl.snapshot_metricas_rate().get("redis_fallback_a_memoria", 0)
        async with _client() as c:
            for _ in range(5):
                assert (await _post(c, "203.0.113.30")).json()["permitido"] is True
            r = await _post(c, "203.0.113.30")
        assert r.json() == {"permitido": False, "retry_after_segundos": 900}
        assert rl.snapshot_metricas_rate().get("redis_fallback_a_memoria", 0) >= antes + 1

    def test_usuario_vacio_es_el_mismo_principal(self):
        assert rl.sujeto_login("203.0.113.1", "") == rl.sujeto_login("203.0.113.1", "engineering")
        assert rl.sujeto_login("203.0.113.1", " Ana ") == "203.0.113.1|ana"
        assert rl.sujeto_login("", None) == "desconocida|engineering"
