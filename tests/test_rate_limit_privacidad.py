# tests/test_rate_limit_privacidad.py — Cupo de POST /privacy/export y /delete.
#
# SQLite en archivo temporal. El proveedor de WhatsApp está mockeado: no hay
# envío real. El cupo usa la memoria del proceso (Redis forzado a None) para
# no tocar un Redis ni una base que no sea este tmp.

import importlib

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

import agent.memory
import agent.rate_limiter as rl


@pytest.fixture
async def entorno(tmp_path, monkeypatch):
    db_path = tmp_path / "privacidad-cupo.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    for var in (
        "RATE_LIMIT_PRIVACY_EXPORT_MAX",
        "RATE_LIMIT_PRIVACY_EXPORT_WINDOW_SECONDS",
        "RATE_LIMIT_PRIVACY_DELETE_MAX",
        "RATE_LIMIT_PRIVACY_DELETE_WINDOW_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)

    # Nunca el cliente Redis de import-time: estos tests no hablan con Redis.
    monkeypatch.setattr(rl, "_redis", None)
    rl._cupos_mem.clear()

    importlib.reload(agent.memory)
    import agent.main as main

    importlib.reload(main)
    await agent.memory.inicializar_db()

    enviados: list[tuple[str, str]] = []

    async def _fake_enviar(telefono, texto, *a, **k):
        enviados.append((telefono, texto))
        return {"ok": True}

    monkeypatch.setattr(main.proveedor, "enviar_mensaje", _fake_enviar)

    reloj = {"t": 1_800_000_000.0}
    monkeypatch.setattr(rl, "_time", lambda: reloj["t"])
    return main, enviados, reloj


def _client(main):
    return AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _filas(tel: str) -> int:
    async with agent.memory.async_session() as s:
        n = await s.scalar(
            select(func.count())
            .select_from(agent.memory.SolicitudPrivacidad)
            .where(agent.memory.SolicitudPrivacidad.telefono == tel)
        )
    return int(n or 0)


def _firma(res) -> tuple:
    return (
        res.status_code,
        res.json(),
        res.headers.get("retry-after"),
        res.headers.get("cache-control"),
    )


class TestExport:
    async def test_el_cuarto_intento_es_429_y_no_dispara_efecto(self, entorno):
        main, enviados, _reloj = entorno
        tel = "14075551001"
        async with _client(main) as c:
            for _ in range(3):
                r = await c.post("/privacy/export", json={"telefono": tel})
                assert r.status_code == 200
            antes = await _filas(tel)
            n_msgs = len(enviados)
            r4 = await c.post("/privacy/export", json={"telefono": tel})
        assert r4.status_code == 429
        assert r4.json() == {"detail": "rate_limit_excedido"}
        assert r4.headers["retry-after"] == "3600"
        assert tel not in r4.text
        assert await _filas(tel) == antes
        assert len(enviados) == n_msgs

    async def test_la_ventana_se_reabre(self, entorno):
        main, _enviados, reloj = entorno
        tel = "14075551002"
        async with _client(main) as c:
            for _ in range(3):
                assert (await c.post("/privacy/export", json={"telefono": tel})).status_code == 200
            assert (await c.post("/privacy/export", json={"telefono": tel})).status_code == 429
            reloj["t"] += 3600
            r = await c.post("/privacy/export", json={"telefono": tel})
        assert r.status_code == 200
        assert "retry-after" not in r.headers

    async def test_otro_usuario_no_hereda_el_cupo(self, entorno):
        main, _enviados, _reloj = entorno
        async with _client(main) as c:
            for _ in range(3):
                assert (
                    await c.post("/privacy/export", json={"telefono": "14075551003"})
                ).status_code == 200
            bloqueado = await c.post("/privacy/export", json={"telefono": "14075551003"})
            libre = await c.post("/privacy/export", json={"telefono": "14075551004"})
        assert bloqueado.status_code == 429
        assert libre.status_code == 200


class TestDelete:
    async def test_el_cuarto_intento_es_429_y_no_borra(self, entorno):
        main, enviados, _reloj = entorno
        tel = "14075551011"
        await agent.memory.guardar_mensaje(tel, "user", "dato que no debe borrarse")
        async with _client(main) as c:
            for _ in range(3):
                assert (await c.post("/privacy/delete", json={"telefono": tel})).status_code == 200
            n_msgs = len(enviados)
            r = await c.post("/privacy/delete", json={"telefono": tel})
        assert r.status_code == 429
        assert r.json() == {"detail": "rate_limit_excedido"}
        assert r.headers["retry-after"] == "86400"
        assert len(enviados) == n_msgs
        async with agent.memory.async_session() as s:
            queda = await s.scalar(
                select(func.count())
                .select_from(agent.memory.Mensaje)
                .where(agent.memory.Mensaje.telefono == tel)
            )
        assert int(queda or 0) >= 1

    async def test_la_ventana_se_reabre(self, entorno):
        main, _enviados, reloj = entorno
        tel = "14075551012"
        async with _client(main) as c:
            for _ in range(3):
                assert (await c.post("/privacy/delete", json={"telefono": tel})).status_code == 200
            assert (await c.post("/privacy/delete", json={"telefono": tel})).status_code == 429
            reloj["t"] += 86400
            r = await c.post("/privacy/delete", json={"telefono": tel})
        assert r.status_code == 200

    async def test_otro_usuario_no_hereda_el_cupo(self, entorno):
        main, _enviados, _reloj = entorno
        async with _client(main) as c:
            for _ in range(3):
                assert (
                    await c.post("/privacy/delete", json={"telefono": "14075551013"})
                ).status_code == 200
            bloqueado = await c.post("/privacy/delete", json={"telefono": "14075551013"})
            libre = await c.post("/privacy/delete", json={"telefono": "14075551014"})
        assert bloqueado.status_code == 429
        assert libre.status_code == 200


class TestSinFiltrarExistencia:
    async def test_el_429_es_igual_con_datos_y_sin_datos(self, entorno):
        main, _enviados, _reloj = entorno
        con_datos = "14075551021"
        sin_datos = "14075551022"
        await agent.memory.guardar_mensaje(con_datos, "user", "tengo historial")
        async with _client(main) as c:
            for _ in range(3):
                await c.post("/privacy/export", json={"telefono": con_datos})
                await c.post("/privacy/export", json={"telefono": sin_datos})
            a = await c.post("/privacy/export", json={"telefono": con_datos})
            b = await c.post("/privacy/export", json={"telefono": sin_datos})
        assert a.status_code == 429 and b.status_code == 429
        assert _firma(a) == _firma(b)
        cuerpo = a.text.lower()
        for pista in (con_datos, sin_datos, "existe", "not found", "no hay", "unknown"):
            assert pista not in cuerpo

    async def test_con_y_sin_mas_es_el_mismo_sujeto(self, entorno):
        main, _enviados, _reloj = entorno
        async with _client(main) as c:
            for _ in range(3):
                assert (
                    await c.post("/privacy/delete", json={"telefono": "+14075551023"})
                ).status_code == 200
            r = await c.post("/privacy/delete", json={"telefono": "14075551023"})
        assert r.status_code == 429
        assert "14075551023" not in r.text

    async def test_env_baja_el_tope(self, entorno, monkeypatch):
        main, _enviados, _reloj = entorno
        monkeypatch.setenv("RATE_LIMIT_PRIVACY_EXPORT_MAX", "2")
        tel = "14075551024"
        async with _client(main) as c:
            assert (await c.post("/privacy/export", json={"telefono": tel})).status_code == 200
            assert (await c.post("/privacy/export", json={"telefono": tel})).status_code == 200
            r = await c.post("/privacy/export", json={"telefono": tel})
        assert r.status_code == 429

    async def test_export_no_gasta_el_cupo_de_delete(self, entorno):
        main, _enviados, _reloj = entorno
        tel = "14075551025"
        async with _client(main) as c:
            for _ in range(3):
                assert (await c.post("/privacy/export", json={"telefono": tel})).status_code == 200
            assert (await c.post("/privacy/export", json={"telefono": tel})).status_code == 429
            r = await c.post("/privacy/delete", json={"telefono": tel})
        assert r.status_code == 200
