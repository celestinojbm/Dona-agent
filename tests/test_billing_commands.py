# tests/test_billing_commands.py — Tests de comandos de billing

"""
Verifica detección y render de `dona saldo`, `dona recargar`, `dona mis assets`.
"""

import importlib
import pytest
from unittest.mock import patch, AsyncMock

import agent.memory
import agent.billing
import agent.storage
import agent.billing_commands


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = tmp_path / "cmd.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    importlib.reload(agent.billing)
    importlib.reload(agent.storage)
    importlib.reload(agent.billing_commands)
    await agent.memory.inicializar_db()
    return agent.billing_commands


class TestDetectores:
    def test_saldo_variantes(self):
        assert agent.billing_commands.es_comando_saldo("dona saldo")
        assert agent.billing_commands.es_comando_saldo("Dona Créditos")
        assert agent.billing_commands.es_comando_saldo("  dona mi saldo  ")

    def test_saldo_rechaza(self):
        assert not agent.billing_commands.es_comando_saldo("saldo")
        assert not agent.billing_commands.es_comando_saldo("dona")
        assert not agent.billing_commands.es_comando_saldo("")

    def test_recargar_variantes(self):
        assert agent.billing_commands.es_comando_recargar("dona recargar")
        assert agent.billing_commands.es_comando_recargar("dona comprar créditos")

    def test_mis_assets_variantes(self):
        assert agent.billing_commands.es_comando_mis_assets("dona mis assets")
        assert agent.billing_commands.es_comando_mis_assets("dona mi galería")
        assert agent.billing_commands.es_comando_mis_assets("dona mis imagenes")


class TestTextoSaldo:
    @pytest.mark.asyncio
    async def test_saldo_cero(self, db):
        texto = await db.texto_saldo("5551")
        assert "0 créditos" in texto
        assert "recargar" in texto.lower()

    @pytest.mark.asyncio
    async def test_saldo_con_movimientos(self, db):
        await agent.billing.acreditar("5551", 100, "pack inicial", stripe_session_id="s1")
        await agent.billing.cobrar("5551", 10, "gen imagen")
        texto = await db.texto_saldo("5551")
        assert "90 créditos" in texto
        assert "pack inicial" in texto
        assert "gen imagen" in texto


class TestTextoRecargar:
    @pytest.mark.asyncio
    async def test_sin_stripe_configurado(self, db, monkeypatch):
        for k in ("STRIPE_PRICE_PAQUETE_100", "STRIPE_PRICE_PAQUETE_500", "STRIPE_PRICE_PAQUETE_2000"):
            monkeypatch.delenv(k, raising=False)
        texto = await db.texto_recargar("5551")
        assert "no está conectado" in texto.lower() or "no disponible" in texto.lower()

    @pytest.mark.asyncio
    async def test_con_stripe_muestra_paquetes(self, db, monkeypatch):
        monkeypatch.setenv("STRIPE_PRICE_PAQUETE_100", "price_100")
        monkeypatch.setenv("STRIPE_PRICE_PAQUETE_500", "price_500")
        with patch("agent.billing_commands.crear_checkout", new=AsyncMock(return_value="https://checkout.stripe.com/x")):
            texto = await db.texto_recargar("5551")
        assert "100 créditos" in texto
        assert "500 créditos" in texto
        assert "https://checkout.stripe.com/x" in texto


class TestTextoMisAssets:
    @pytest.mark.asyncio
    async def test_sin_assets(self, db):
        texto = await db.texto_mis_assets("5551")
        assert "galería" in texto.lower() or "creaciones" in texto.lower()

    @pytest.mark.asyncio
    async def test_con_assets_muestra_lista(self, db):
        g = agent.storage.AssetGuardado(
            url_publica="https://assets.dona.app/abc.png",
            key_storage="abc/image/x.png",
            backend="r2", mime_type="image/png", bytes_size=100,
        )
        await agent.storage.registrar_asset(
            "5551", "image", g, prompt="gato astronauta", modelo="nanobanana",
        )
        texto = await db.texto_mis_assets("5551")
        assert "gato astronauta" in texto
        assert "image" in texto
