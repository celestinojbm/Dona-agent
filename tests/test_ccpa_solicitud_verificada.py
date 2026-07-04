# tests/test_ccpa_solicitud_verificada.py — CCPA/CPRA verified request (TEMA 7.1/7.2)

"""
Solicitud VERIFICADA de privacidad (export/delete) por OTP de WhatsApp.

Contexto (Roadmap TEMA 7.1/7.2): el teléfono NO es secreto, así que los
endpoints HTTP `/privacy/export` y `/privacy/delete` no pueden ejecutar el
efecto solo con un número. Se exige un *verified consumer request*: un código
de un solo uso enviado por WhatsApp que prueba control del canal, validado en
`/privacy/verify` antes de exportar o borrar. La tabla `solicitudes_privacidad`
traza estado + SLA de 45 días.

Cubre:
- Helpers puros: creación (OTP 6 dígitos, hash no-texto, SLA 45d, anti-spam),
  verificación (código correcto/incorrecto/expirado/demasiados intentos),
  y marcado de completada.
- Endpoints end-to-end: delete real solo con código válido (con provider
  mockeado — NO hay envío real de WhatsApp); teléfono leído del body, no query.
"""

import importlib
import re

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

import agent.memory


@pytest.fixture
async def entorno(tmp_path, monkeypatch):
    """SQLite aislada + app FastAPI fresca + provider mockeado (sin envíos reales)."""
    db_path = tmp_path / "ccpa.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    importlib.reload(agent.memory)
    import agent.main as _main
    importlib.reload(_main)
    await agent.memory.inicializar_db()

    enviados = []

    async def _fake_enviar(telefono, texto, *a, **k):
        enviados.append((telefono, texto))
        return {"ok": True}

    # El endpoint usa el proveedor a nivel de módulo; lo reemplazamos por un
    # recorder. El gate de envío se prueba aparte (test_envio_gate.py).
    monkeypatch.setattr(_main.proveedor, "enviar_mensaje", _fake_enviar)
    return _main, enviados


async def _un_solo(select_stmt):
    async with agent.memory.async_session() as s:
        return (await s.execute(select_stmt)).scalars().first()


# ─── Helpers puros ────────────────────────────────────────────────────────────

class TestCrearSolicitud:
    async def test_devuelve_codigo_6_digitos(self, entorno):
        codigo = await agent.memory.crear_solicitud_privacidad("14075550001", "delete")
        assert re.fullmatch(r"\d{6}", codigo)

    async def test_guarda_hash_no_el_texto(self, entorno):
        codigo = await agent.memory.crear_solicitud_privacidad("14075550002", "export")
        sol = await _un_solo(select(agent.memory.SolicitudPrivacidad))
        assert sol.codigo_hash
        assert codigo not in sol.codigo_hash  # el texto nunca se persiste
        assert sol.codigo_hash == agent.memory._hash_codigo_privacidad(codigo)
        assert sol.estado == "pendiente_verificacion"
        assert sol.tipo == "export"

    async def test_sla_es_45_dias(self, entorno):
        await agent.memory.crear_solicitud_privacidad("14075550003", "delete")
        sol = await _un_solo(select(agent.memory.SolicitudPrivacidad))
        assert (sol.sla_limite - sol.creada).days == 45

    async def test_reutiliza_no_emite_segundo_codigo(self, entorno):
        c1 = await agent.memory.crear_solicitud_privacidad("14075550004", "delete")
        c2 = await agent.memory.crear_solicitud_privacidad("14075550004", "delete")
        assert c1 is not None and c2 is None  # anti-spam: 1 OTP por ventana

    async def test_distinto_tipo_si_emite_codigo(self, entorno):
        c1 = await agent.memory.crear_solicitud_privacidad("14075550005", "delete")
        c2 = await agent.memory.crear_solicitud_privacidad("14075550005", "export")
        assert c1 is not None and c2 is not None  # export y delete son solicitudes distintas

    async def test_tipo_invalido_rechazado(self, entorno):
        with pytest.raises(ValueError):
            await agent.memory.crear_solicitud_privacidad("14075550006", "hackear")


class TestVerificar:
    async def test_codigo_correcto_verifica(self, entorno):
        codigo = await agent.memory.crear_solicitud_privacidad("14075550010", "delete")
        res = await agent.memory.verificar_solicitud_privacidad("14075550010", codigo)
        assert res["ok"] and res["tipo"] == "delete" and res["solicitud_id"]
        sol = await _un_solo(select(agent.memory.SolicitudPrivacidad))
        assert sol.estado == "verificada"

    async def test_codigo_incorrecto_falla_y_cuenta_intento(self, entorno):
        await agent.memory.crear_solicitud_privacidad("14075550011", "delete")
        res = await agent.memory.verificar_solicitud_privacidad("14075550011", "000000")
        assert not res["ok"] and res["razon"] == "codigo_invalido"
        sol = await _un_solo(select(agent.memory.SolicitudPrivacidad))
        assert sol.intentos == 1 and sol.estado == "pendiente_verificacion"

    async def test_sin_solicitud_pendiente(self, entorno):
        res = await agent.memory.verificar_solicitud_privacidad("14075559999", "123456")
        assert not res["ok"] and res["razon"] == "sin_solicitud"

    async def test_demasiados_intentos_marca_fallida(self, entorno):
        codigo = await agent.memory.crear_solicitud_privacidad("14075550012", "delete")
        for _ in range(6):
            res = await agent.memory.verificar_solicitud_privacidad("14075550012", "000000")
        assert res["razon"] == "demasiados_intentos"
        # Tras fallar, ni el código correcto sirve (estado != pendiente).
        res2 = await agent.memory.verificar_solicitud_privacidad("14075550012", codigo)
        assert not res2["ok"] and res2["razon"] == "sin_solicitud"

    async def test_codigo_expirado(self, entorno):
        codigo = await agent.memory.crear_solicitud_privacidad("14075550013", "export")
        async with agent.memory.async_session() as s:
            await s.execute(update(agent.memory.SolicitudPrivacidad).values(
                expira=agent.memory.datetime.utcnow() - agent.memory.timedelta(minutes=1)))
            await s.commit()
        res = await agent.memory.verificar_solicitud_privacidad("14075550013", codigo)
        assert not res["ok"] and res["razon"] == "expirada"


# ─── Endpoints end-to-end ─────────────────────────────────────────────────────

def _client(main):
    return AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


def _codigo_del_ultimo_otp(enviados):
    assert enviados, "no se envió ningún OTP por WhatsApp"
    m = re.search(r"\b(\d{6})\b", enviados[-1][1])
    assert m, f"no se halló código en: {enviados[-1][1]!r}"
    return m.group(1)


async def _contar_mensajes(tel):
    async with agent.memory.async_session() as s:
        rows = (await s.execute(
            select(agent.memory.Mensaje).where(agent.memory.Mensaje.telefono == tel)
        )).scalars().all()
    return len(rows)


class TestEndpointFlujoVerificado:
    async def test_delete_borra_solo_con_codigo_valido(self, entorno):
        main, enviados = entorno
        tel = "14075550100"
        await agent.memory.guardar_mensaje(tel, "user", "hola dona")
        assert await _contar_mensajes(tel) >= 1

        async with _client(main) as c:
            # Paso 1: solicitar borrado → envía OTP (mockeado)
            r1 = await c.post("/privacy/delete", json={"telefono": tel})
            assert r1.status_code == 200 and r1.json()["status"] == "verification_sent"
            codigo = _codigo_del_ultimo_otp(enviados)

            # Código INCORRECTO no borra nada
            rbad = await c.post("/privacy/verify", json={"telefono": tel, "codigo": "000000"})
            assert rbad.status_code == 400
            assert await _contar_mensajes(tel) >= 1  # dato intacto

            # Código correcto → borra de verdad
            r2 = await c.post("/privacy/verify", json={"telefono": tel, "codigo": codigo})
            assert r2.status_code == 200
            body = r2.json()
            assert body["status"] == "completed" and body["tipo"] == "delete"
            assert body["registros_eliminados"] >= 1
            assert await _contar_mensajes(tel) == 0  # dato eliminado

        sol = await _un_solo(select(agent.memory.SolicitudPrivacidad))
        assert sol.estado == "completada"

    async def test_export_devuelve_datos_tras_verificar(self, entorno):
        main, enviados = entorno
        tel = "14075550101"
        await agent.memory.guardar_mensaje(tel, "user", "un mensaje mío")
        async with _client(main) as c:
            r1 = await c.post("/privacy/export", json={"telefono": tel})
            assert r1.json()["status"] == "verification_sent"
            codigo = _codigo_del_ultimo_otp(enviados)
            r2 = await c.post("/privacy/verify", json={"telefono": tel, "codigo": codigo})
            assert r2.status_code == 200
            body = r2.json()
            assert body["status"] == "completed" and body["tipo"] == "export"
            assert "datos" in body
        # el export NO borra
        assert await _contar_mensajes(tel) >= 1

    async def test_delete_sin_verificar_no_ejecuta(self, entorno):
        main, enviados = entorno
        tel = "14075550102"
        await agent.memory.guardar_mensaje(tel, "user", "sigo aquí")
        async with _client(main) as c:
            await c.post("/privacy/delete", json={"telefono": tel})
            # verify con teléfono sin solicitud → falla, nada se borra
            r = await c.post("/privacy/verify", json={"telefono": "14075559998", "codigo": "123456"})
            assert r.status_code == 400
        assert await _contar_mensajes(tel) >= 1

    async def test_telefono_invalido_400(self, entorno):
        main, _ = entorno
        async with _client(main) as c:
            r = await c.post("/privacy/delete", json={"telefono": "no-es-un-numero"})
            assert r.status_code == 400

    async def test_reuse_no_reenvia_otp(self, entorno):
        main, enviados = entorno
        tel = "14075550103"
        async with _client(main) as c:
            await c.post("/privacy/delete", json={"telefono": tel})
            n1 = len(enviados)
            r2 = await c.post("/privacy/delete", json={"telefono": tel})
            assert r2.json()["status"] == "verification_pending"
            assert len(enviados) == n1  # no reenvió (anti-spam)
