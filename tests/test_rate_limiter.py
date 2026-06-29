# tests/test_rate_limiter.py — Cobertura del rate limiting por teléfono.
#
# CLAUDE.md §3.5: "Rate limiting por teléfono en rate_limiter.py. No bypassar."
# La auditoría encontró este módulo SIN cobertura. Estos tests ejercitan el path
# in-memory (sin REDIS_URL en CI): límite por usuario, aislamiento entre usuarios,
# reseteo por ventana, tope global y limpieza.

import pytest

import agent.rate_limiter as rl


@pytest.fixture(autouse=True)
def _reset_rate_limit(monkeypatch):
    """Fuerza el path in-memory y limpia el estado antes y después de cada test."""
    monkeypatch.setattr(rl, "_redis", None, raising=False)
    rl.limpiar_rate_limit()
    yield
    rl.limpiar_rate_limit()


def test_permite_hasta_el_maximo_y_bloquea_el_siguiente():
    tel = "+15550001111"
    for i in range(rl._RATE_LIMIT_MAX):
        assert rl.dentro_de_limite(tel) is True, f"la llamada {i + 1} debería pasar"
    # El mensaje N+1 dentro de la ventana se bloquea.
    assert rl.dentro_de_limite(tel) is False


def test_limite_es_por_usuario_no_compartido_entre_usuarios():
    a, b = "+15550000001", "+15550000002"
    for _ in range(rl._RATE_LIMIT_MAX):
        assert rl.dentro_de_limite(a) is True
    assert rl.dentro_de_limite(a) is False  # A bloqueado
    assert rl.dentro_de_limite(b) is True   # B intacto (límite es por teléfono)


def test_la_ventana_se_resetea_al_pasar_el_tiempo(monkeypatch):
    tel = "+15550003333"
    reloj = [1000.0]
    monkeypatch.setattr(rl, "_time", lambda: reloj[0])
    for _ in range(rl._RATE_LIMIT_MAX):
        assert rl.dentro_de_limite(tel) is True
    assert rl.dentro_de_limite(tel) is False
    # Avanzar más allá de la ventana deslizante → vuelve a permitir.
    reloj[0] += rl._RATE_LIMIT_VENTANA + 1
    assert rl.dentro_de_limite(tel) is True


def test_tope_global_bloquea_aunque_sea_otro_usuario(monkeypatch):
    # Bajar el tope global para no iterar 1000 veces.
    monkeypatch.setattr(rl, "_RATE_LIMIT_GLOBAL", 3)
    assert rl.dentro_de_limite("+15550000010") is True
    assert rl.dentro_de_limite("+15550000011") is True
    assert rl.dentro_de_limite("+15550000012") is True
    # El 4º excede el tope GLOBAL aunque sea un teléfono distinto y sin límite propio.
    assert rl.dentro_de_limite("+15550000013") is False


def test_limpiar_rate_limit_resetea_el_estado():
    tel = "+15550004444"
    for _ in range(rl._RATE_LIMIT_MAX):
        rl.dentro_de_limite(tel)
    assert rl.dentro_de_limite(tel) is False
    rl.limpiar_rate_limit()
    assert rl.dentro_de_limite(tel) is True


# ── TEMA 8.2 — Endurecimiento del rate limiter ───────────────────────────────
# Hallazgos de la auditoría Fable5 (A9): (1) el cupo GLOBAL se verificaba ANTES
# que el límite por usuario, así que un solo abusador agotaba el presupuesto
# compartido y tiraba a todos (DoS); (2) en el path Redis el member del sorted
# set era el timestamp crudo, y dos requests en el mismo float colapsaban en una
# sola entrada (ZADD actualiza score, no añade) → subconteo y bypass del límite;
# (3) el fallback a memoria por error de Redis no emitía métrica observable.


def test_usuario_bloqueado_no_consume_cupo_global(monkeypatch):
    """DoS (A9): un mensaje rechazado por el LÍMITE PERSONAL no debe inflar el
    cupo global. Si lo inflara, un solo número martillando su propio tope
    agotaría el presupuesto compartido y bloquearía a todos los demás."""
    monkeypatch.setattr(rl, "_RATE_LIMIT_MAX", 2)
    tel = "+15551112222"
    assert rl.dentro_de_limite(tel) is True
    assert rl.dentro_de_limite(tel) is True
    # 3er mensaje: excede su límite personal → rechazado.
    assert rl.dentro_de_limite(tel) is False
    # El cupo global solo registró los 2 permitidos, NO el rechazado.
    assert len(rl._rate_limit_global_mem) == 2


# ── Fake Redis (sorted sets) para ejercitar el path Redis sin servidor ────────
class _FakeRedisZSets:
    """Mínimo viable de un Redis con sorted sets: modela la unicidad de members
    (ZADD del mismo member sobreescribe el score, no añade fila) — exactamente
    la semántica que hace fallar el bug del member=timestamp."""

    def __init__(self):
        self.data: dict[str, dict[str, float]] = {}

    def pipeline(self):
        return _FakePipe(self)


class _FakePipe:
    def __init__(self, store: "_FakeRedisZSets"):
        self.store = store
        self.ops: list = []

    def zremrangebyscore(self, key, lo, hi):
        self.ops.append(("zremrangebyscore", key, hi))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        resultados = []
        for op in self.ops:
            resultados.append(self._run(op))
        self.ops = []
        return resultados

    def _run(self, op):
        nombre = op[0]
        d = self.store.data
        if nombre == "zremrangebyscore":
            _, key, hi = op
            hi = float(hi)
            zs = d.get(key, {})
            for m in [m for m, s in zs.items() if s <= hi]:
                del zs[m]
            d[key] = zs
            return 0
        if nombre == "zcard":
            return len(d.get(op[1], {}))
        if nombre == "zadd":
            _, key, mapping = op
            zs = d.setdefault(key, {})
            zs.update(mapping)  # member duplicado → sobreescribe (no añade)
            return len(mapping)
        if nombre == "expire":
            return True
        raise AssertionError(f"op no soportada: {nombre}")


def test_redis_member_unico_no_colapsa_en_mismo_timestamp(monkeypatch):
    """Concurrencia (A9): con el reloj congelado, si el member fuera el
    timestamp crudo todos los requests colapsarían en UNA entrada (zcard=1) y el
    usuario enviaría sin tope. Con un member único (uuid) cada request es una
    fila distinta y el límite por usuario se respeta aunque coincida el ms."""
    fake = _FakeRedisZSets()
    monkeypatch.setattr(rl, "_redis", fake)
    monkeypatch.setattr(rl, "_time", lambda: 1000.0)  # reloj congelado
    tel = "+15557778888"
    for i in range(rl._RATE_LIMIT_MAX):
        assert rl.dentro_de_limite(tel) is True, f"la llamada {i + 1} debería pasar"
    assert rl.dentro_de_limite(tel) is False
    # Cada request quedó como member distinto pese al timestamp idéntico.
    assert len(fake.data[f"rate:user:{tel}"]) == rl._RATE_LIMIT_MAX


def test_redis_usuario_bloqueado_no_consume_cupo_global(monkeypatch):
    """El orden por-usuario-antes-de-global también aplica en el path Redis: un
    request rechazado por el tope personal no debe añadirse al sorted set global."""
    fake = _FakeRedisZSets()
    monkeypatch.setattr(rl, "_redis", fake)
    monkeypatch.setattr(rl, "_time", lambda: 2000.0)
    monkeypatch.setattr(rl, "_RATE_LIMIT_MAX", 2)
    tel = "+15553334444"
    assert rl.dentro_de_limite(tel) is True
    assert rl.dentro_de_limite(tel) is True
    assert rl.dentro_de_limite(tel) is False
    assert len(fake.data.get("rate:global", {})) == 2


def test_redis_error_cae_a_memoria_y_registra_metrica(monkeypatch):
    """Degradación honesta (A9): si Redis falla, el gate cae al path en memoria
    (conservador, per-worker) Y deja una métrica observable del evento."""

    class _RedisRoto:
        def pipeline(self):
            raise ConnectionError("redis caído")

    monkeypatch.setattr(rl, "_redis", _RedisRoto())
    antes = rl.snapshot_metricas_rate().get("redis_fallback_a_memoria", 0)
    assert rl.dentro_de_limite("+15550009999") is True  # degradó a memoria
    despues = rl.snapshot_metricas_rate().get("redis_fallback_a_memoria", 0)
    assert despues == antes + 1
