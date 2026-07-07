# tests/test_internal_assets.py — Galería de Activos (Fase 1)
# Endpoint POST /internal/assets (read-only).

"""
Cubre el alcance de la Galería de Activos web:
  - Firma HMAC inválida o ausente → 401.
  - JSON malformado / no objeto → 400.
  - Body sin subscription_id → 400.
  - subscription_id no existe → 404.
  - Sub sin activos → 200 con lista vacía.
  - Sub con activos → 200, forma sanitizada (id, tipo, url_publica, prompt,
    modelo, creado) y SIN telefono / key_storage / backend / costo.
  - Filtro ?tipo= (image) sólo devuelve ese tipo; tipo desconocido = todos.
  - limite acota la cantidad.
  - IDOR: un subscription_id NO ve los activos de otro telefono.

NO cubre:
  - Bridge landing → backend (se prueba en landing/lib/assets-bridge.test.ts).
  - UI del dashboard.
"""

import hashlib
import hmac
import importlib
import json

import pytest
from fastapi.testclient import TestClient

_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:
    _main_disponible = False


_requiere_main = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler (no instalado en este entorno)",
)


SECRET_TEST = "test-secret-not-real-galeria"


def _firmar(body: bytes, secret: str = SECRET_TEST) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _body(**kwargs) -> bytes:
    return json.dumps(kwargs).encode("utf-8")


def _post(client, body: bytes, firma: str | None = None):
    return client.post(
        "/internal/assets",
        content=body,
        headers={"X-Internal-Signature": firma if firma is not None else _firmar(body)},
    )


# ── Fixture: backend con DB aislada y env vars ─────────────────────────────


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db_path = tmp_path / "assets.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)

    import agent.memory
    importlib.reload(agent.memory)

    import asyncio
    asyncio.get_event_loop().run_until_complete(agent.memory.inicializar_db())

    from agent.main import app
    return TestClient(app), agent.memory


async def _crear_sub(memory, subscription_id, telefono):
    async with memory.async_session() as session:
        session.add(memory.SuscripcionStripe(
            subscription_id=subscription_id,
            telefono=telefono,
            customer_id="cus_galeria",
            plan_codigo="premium",
            price_id="price_test",
            status="active",
            creditos_mensuales=100,
        ))
        await session.commit()


async def _crear_asset(memory, telefono, tipo="image", url="https://cdn/x.png",
                       prompt="un gato", modelo="nanobanana", key="k/x.png"):
    async with memory.async_session() as session:
        row = memory.AssetGenerado(
            telefono=telefono,
            tipo=tipo,
            url_publica=url,
            key_storage=key,
            backend="r2",
            prompt=prompt,
            modelo=modelo,
            costo_usd="0.02",
            costo_creditos=3,
            mime_type="image/png",
            bytes_size=1234,
            meta_json=json.dumps({"w": 512, "h": 512}),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


# ── Auth ───────────────────────────────────────────────────────────────────


@_requiere_main
class TestAuth:
    def test_sin_header_401(self, setup):
        client, _ = setup
        r = client.post("/internal/assets", content=_body(subscription_id="s"))
        assert r.status_code == 401

    def test_firma_invalida_401(self, setup):
        client, _ = setup
        r = _post(client, _body(subscription_id="s"), firma="deadbeef")
        assert r.status_code == 401

    def test_firma_de_otro_secret_401(self, setup):
        client, _ = setup
        body = _body(subscription_id="s")
        r = _post(client, body, firma=_firmar(body, secret="atacante"))
        assert r.status_code == 401

    def test_body_modificado_tras_firmar_401(self, setup):
        client, _ = setup
        firma = _firmar(_body(subscription_id="sub_original"))
        r = _post(client, _body(subscription_id="sub_atacante"), firma=firma)
        assert r.status_code == 401


# ── Validación de payload ──────────────────────────────────────────────────


@_requiere_main
class TestPayload:
    def test_no_json_400(self, setup):
        client, _ = setup
        body = b"no soy json"
        r = _post(client, body, firma=_firmar(body))
        assert r.status_code == 400

    def test_array_no_objeto_400(self, setup):
        client, _ = setup
        body = json.dumps([1, 2]).encode("utf-8")
        r = _post(client, body, firma=_firmar(body))
        assert r.status_code == 400

    def test_sin_subscription_id_400(self, setup):
        client, _ = setup
        r = _post(client, _body(otro="x"))
        assert r.status_code == 400
        assert "missing_subscription_id" in r.json().get("detail", "")

    def test_subscription_id_vacio_400(self, setup):
        client, _ = setup
        r = _post(client, _body(subscription_id="   "))
        assert r.status_code == 400


# ── subscription_id inexistente → 404 ──────────────────────────────────────


@_requiere_main
class TestSubInexistente:
    def test_sub_inexistente_404(self, setup):
        client, _ = setup
        r = _post(client, _body(subscription_id="sub_nunca"))
        assert r.status_code == 404
        assert "subscription_no_persistida" in r.json().get("detail", "")


# ── Casos felices ──────────────────────────────────────────────────────────


@_requiere_main
class TestListado:
    @pytest.mark.asyncio
    async def test_sub_sin_activos_lista_vacia(self, setup):
        client, memory = setup
        await _crear_sub(memory, "sub_vacia", "15551110000")
        r = _post(client, _body(subscription_id="sub_vacia"))
        assert r.status_code == 200
        j = r.json()
        assert j == {"assets": [], "count": 0}

    @pytest.mark.asyncio
    async def test_sub_con_activos_forma_sanitizada(self, setup):
        client, memory = setup
        await _crear_sub(memory, "sub_full", "15551112222")
        await _crear_asset(
            memory, "15551112222", tipo="image", url="https://cdn/gato.png",
            prompt="un gato naranja", modelo="nanobanana",
        )
        r = _post(client, _body(subscription_id="sub_full"))
        assert r.status_code == 200
        j = r.json()
        assert j["count"] == 1
        asset = j["assets"][0]
        # Forma exacta esperada
        assert set(asset.keys()) == {
            "id", "tipo", "url_publica", "prompt", "modelo", "creado",
        }
        assert asset["tipo"] == "image"
        assert asset["url_publica"] == "https://cdn/gato.png"
        assert asset["prompt"] == "un gato naranja"
        assert asset["modelo"] == "nanobanana"
        # PII / interno NO expuesto
        body_text = r.text
        assert "15551112222" not in body_text
        assert "key_storage" not in body_text
        assert "backend" not in body_text
        assert "costo" not in body_text

    @pytest.mark.asyncio
    async def test_filtro_tipo_solo_ese_tipo(self, setup):
        client, memory = setup
        await _crear_sub(memory, "sub_mix", "15551113333")
        await _crear_asset(memory, "15551113333", tipo="image")
        await _crear_asset(memory, "15551113333", tipo="video",
                           url="https://cdn/v.mp4", modelo="veo")
        await _crear_asset(memory, "15551113333", tipo="doc",
                           url="https://cdn/d.pdf", modelo="")
        # Sólo imágenes
        r = _post(client, _body(subscription_id="sub_mix", tipo="image"))
        assert r.status_code == 200
        j = r.json()
        assert j["count"] == 1
        assert all(a["tipo"] == "image" for a in j["assets"])

    @pytest.mark.asyncio
    async def test_tipo_desconocido_devuelve_todos(self, setup):
        client, memory = setup
        await _crear_sub(memory, "sub_all", "15551114444")
        await _crear_asset(memory, "15551114444", tipo="image")
        await _crear_asset(memory, "15551114444", tipo="video",
                           url="https://cdn/v.mp4", modelo="veo")
        r = _post(client, _body(subscription_id="sub_all", tipo="basura"))
        assert r.status_code == 200
        assert r.json()["count"] == 2

    @pytest.mark.asyncio
    async def test_limite_acota_cantidad(self, setup):
        client, memory = setup
        await _crear_sub(memory, "sub_muchos", "15551115555")
        for i in range(5):
            await _crear_asset(memory, "15551115555", url=f"https://cdn/{i}.png")
        r = _post(client, _body(subscription_id="sub_muchos", limite=2))
        assert r.status_code == 200
        assert r.json()["count"] == 2


# ── Anti-IDOR ──────────────────────────────────────────────────────────────


@_requiere_main
class TestIDOR:
    @pytest.mark.asyncio
    async def test_sub_no_ve_activos_de_otro_telefono(self, setup):
        """sub_a (telefono A) NO debe ver los activos de telefono B, aunque
        firme correctamente. El backend resuelve telefono desde la sub."""
        client, memory = setup
        await _crear_sub(memory, "sub_a", "15551110001")
        await _crear_sub(memory, "sub_b", "15551110002")
        # Activos SÓLO de B
        await _crear_asset(memory, "15551110002", url="https://cdn/secreto-b.png",
                           prompt="documento privado de B")
        await _crear_asset(memory, "15551110002", tipo="doc",
                           url="https://cdn/secreto-b.pdf", modelo="")

        # A pide sus activos → 0, y no ve nada de B
        r = _post(client, _body(subscription_id="sub_a"))
        assert r.status_code == 200
        j = r.json()
        assert j["count"] == 0
        assert "secreto-b" not in r.text
        assert "documento privado de B" not in r.text

        # B sí ve los suyos (control positivo)
        r2 = _post(client, _body(subscription_id="sub_b"))
        assert r2.status_code == 200
        assert r2.json()["count"] == 2


# ── El endpoint es read-only ───────────────────────────────────────────────


@_requiere_main
class TestReadOnly:
    @pytest.mark.asyncio
    async def test_no_modifica_db(self, setup):
        from sqlalchemy import func, select

        client, memory = setup
        await _crear_sub(memory, "sub_ro", "15551119999")
        await _crear_asset(memory, "15551119999")

        async def _contar():
            async with memory.async_session() as session:
                return (await session.execute(
                    select(func.count()).select_from(memory.AssetGenerado)
                )).scalar_one()

        antes = await _contar()
        for _ in range(3):
            assert _post(client, _body(subscription_id="sub_ro")).status_code == 200
        assert await _contar() == antes
