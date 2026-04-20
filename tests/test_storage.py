# tests/test_storage.py — Tests del storage de assets

"""
Cubre:
  - construir_key: formato y sanitización
  - subir_asset via filesystem (sin R2 configurado)
  - registrar_asset + obtener_asset + listar_assets_usuario
  - eliminar_asset: sólo el owner puede borrar
"""

import os
import pytest
from unittest.mock import patch

from agent import storage


class TestConstruirKey:
    def test_formato_basico(self):
        k = storage.construir_key("5551234567", "image", "image/png", "foto.png")
        parts = k.split("/")
        assert len(parts) == 3
        assert parts[1] == "image"
        assert parts[2].endswith(".png")

    def test_sanitiza_tipo(self):
        k = storage.construir_key("5551", "../evil", "application/octet-stream")
        assert "../" not in k
        assert k.split("/")[1] == "evil"  # prefijo '../' borrado

    def test_hash_telefono_estable(self):
        h1 = storage._hash_telefono("5551234567")
        h2 = storage._hash_telefono("5551234567")
        assert h1 == h2
        assert len(h1) == 12
        assert "5551234567" not in h1  # no filtra el número

    def test_extension_desde_mime(self):
        k = storage.construir_key("5551", "image", "image/jpeg")
        assert k.endswith(".jpg") or k.endswith(".jpeg")

    def test_extension_fallback(self):
        k = storage.construir_key("5551", "misc", "", "")
        assert k.endswith(".bin")


class TestSubirFS:
    @pytest.mark.asyncio
    async def test_subir_filesystem(self, tmp_path, monkeypatch):
        # Forzar fs backend: sin creds de R2
        for var in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"]:
            monkeypatch.delenv(var, raising=False)

        # Apuntar FS_ROOT a tmp
        monkeypatch.setattr(storage, "_FS_ROOT", tmp_path / "assets")

        # Recalcular flags
        monkeypatch.setattr(storage, "R2_ACCOUNT_ID", "")
        monkeypatch.setattr(storage, "R2_ACCESS_KEY_ID", "")
        monkeypatch.setattr(storage, "R2_SECRET_ACCESS_KEY", "")
        monkeypatch.setattr(storage, "R2_BUCKET", "")

        guardado = await storage.subir_asset(
            telefono="5551234567",
            tipo="image",
            contenido=b"\x89PNG fake",
            mime_type="image/png",
            nombre_sugerido="foto.png",
        )
        assert guardado.backend == "fs"
        assert guardado.bytes_size == len(b"\x89PNG fake")
        assert guardado.url_publica.startswith("file://")
        # archivo realmente escrito
        on_disk = (tmp_path / "assets" / guardado.key_storage)
        assert on_disk.exists()
        assert on_disk.read_bytes() == b"\x89PNG fake"

    @pytest.mark.asyncio
    async def test_contenido_vacio_falla(self):
        with pytest.raises(ValueError):
            await storage.subir_asset("5551", "image", b"")


class TestRegistroDB:
    @pytest.mark.asyncio
    async def test_registrar_y_obtener(self, tmp_path, monkeypatch):
        # BD en memoria separada por test
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
        # Forzar reimport de memory para tomar la nueva URL
        import importlib
        import agent.memory
        importlib.reload(agent.memory)
        await agent.memory.inicializar_db()

        # Y reimportar storage para que use el mismo engine
        import agent.storage
        importlib.reload(agent.storage)

        guardado = agent.storage.AssetGuardado(
            url_publica="file:///tmp/x.png",
            key_storage="abc/image/xyz.png",
            backend="fs",
            mime_type="image/png",
            bytes_size=123,
        )
        asset_id = await agent.storage.registrar_asset(
            telefono="5551234567",
            tipo="image",
            guardado=guardado,
            prompt="gato astronauta",
            modelo="nanobanana",
            costo_creditos=2,
            meta={"w": 1024, "h": 1024},
        )
        assert asset_id > 0

        rec = await agent.storage.obtener_asset(asset_id)
        assert rec is not None
        assert rec["tipo"] == "image"
        assert rec["modelo"] == "nanobanana"
        assert rec["costo_creditos"] == 2
        assert rec["meta"]["w"] == 1024

    @pytest.mark.asyncio
    async def test_listar_y_eliminar(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test2.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
        import importlib
        import agent.memory
        importlib.reload(agent.memory)
        await agent.memory.inicializar_db()
        import agent.storage
        importlib.reload(agent.storage)

        g = agent.storage.AssetGuardado(
            url_publica="file:///tmp/y.png", key_storage="abc/image/y.png",
            backend="fs", mime_type="image/png", bytes_size=10,
        )
        a1 = await agent.storage.registrar_asset("5551", "image", g, prompt="a")
        a2 = await agent.storage.registrar_asset("5551", "video", g, prompt="b")
        await agent.storage.registrar_asset("5552", "image", g, prompt="c")  # otro user

        mios = await agent.storage.listar_assets_usuario("5551", limite=10)
        assert len(mios) == 2

        solo_img = await agent.storage.listar_assets_usuario("5551", limite=10, tipo="image")
        assert len(solo_img) == 1

        # No puedo borrar asset de otro
        ok = await agent.storage.eliminar_asset(a1, telefono="5552")
        assert ok is False

        # Sí puedo borrar el mío
        ok = await agent.storage.eliminar_asset(a1, telefono="5551")
        assert ok is True

        restantes = await agent.storage.listar_assets_usuario("5551")
        assert len(restantes) == 1
        assert restantes[0]["id"] == a2
