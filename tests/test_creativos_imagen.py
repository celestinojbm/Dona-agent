# tests/test_creativos_imagen.py — Tests de generación de imagen (Sprint 2)

"""
Cubre:
  - Detección de comandos (`dona imagen ...`, premium, aspect ratio, confirmar, cancelar)
  - Flujo preparar → confirmar (cobra + encola)
  - Handler `gen_imagen` end-to-end con Gemini mockeado
  - Placeholder cuando no hay GEMINI_API_KEY
  - Cancelar descarta sin cobrar
"""

import asyncio
import importlib
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import agent.memory
import agent.billing
import agent.storage


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """DB aislada + providers de storage/billing recargados."""
    db_path = tmp_path / "creativos.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("JOBS_BACKEND", "inproc")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    import agent.memory as _memory
    import agent.billing as _billing
    import agent.storage as _storage
    import agent.jobs.queue as _queue
    import agent.jobs.worker as _worker
    import agent.jobs as _jobs
    import agent.creativos.prompt_imagen as _prompt_imagen
    import agent.creativos.imagen as _imagen
    import agent.jobs.handlers_creativos as _hc

    importlib.reload(_memory)
    importlib.reload(_billing)
    importlib.reload(_storage)
    importlib.reload(_queue)
    importlib.reload(_worker)
    importlib.reload(_jobs)
    importlib.reload(_prompt_imagen)
    importlib.reload(_imagen)
    importlib.reload(_hc)

    # Mock del optimizer: pass-through idea → {"en": idea, "es": idea}.
    # Evita llamar a Claude en cada test y mantiene `pend.prompt == idea`
    # para no romper asserts existentes. Tests que validan el comportamiento
    # real del optimizer están en test_creativos_prompt_imagen.py.
    async def _fake_optimizar(idea, calidad="standard"):
        return {"en": idea, "es": idea}
    monkeypatch.setattr(_imagen, "optimizar_prompt_imagen", _fake_optimizar, raising=False)
    monkeypatch.setattr(_prompt_imagen, "optimizar_prompt_imagen", _fake_optimizar)

    await _memory.inicializar_db()
    yield {
        "memory": _memory, "billing": _billing, "storage": _storage,
        "jobs": _jobs, "imagen": _imagen,
    }


# ── Detectores ──────────────────────────────────────────────────────────────

class TestDetectores:
    def test_comando_imagen_basico(self):
        from agent.creativos.comandos import es_comando_imagen
        assert es_comando_imagen("dona imagen gato astronauta")
        assert es_comando_imagen("Dona Imagen un perro")
        assert es_comando_imagen("dona imágen con acento")
        assert es_comando_imagen("dona image in english word")

    def test_comando_imagen_natural_verbo_sustantivo(self):
        from agent.creativos.comandos import es_comando_imagen, parsear_imagen
        assert es_comando_imagen("hazme una imagen de un gato")
        assert es_comando_imagen("Genérame una foto del logo")
        assert es_comando_imagen("creame un dibujo de gato")
        assert es_comando_imagen("dame una imagen de paisaje")
        assert es_comando_imagen("quiero una imagen de gato")
        assert es_comando_imagen("necesito un banner para mi negocio")
        assert es_comando_imagen("mándame una imagen de sol")
        assert es_comando_imagen("¿puedes hacerme una imagen de perro?")
        # El prompt se extrae limpio, sin el prefijo verbo+sustantivo
        d = parsear_imagen("hazme una imagen de un gato astronauta")
        assert "gato astronauta" in d["prompt"]
        assert "imagen" not in d["prompt"].lower()

    def test_comando_imagen_natural_verbo_fuerte(self):
        from agent.creativos.comandos import es_comando_imagen, parsear_imagen
        assert es_comando_imagen("dibuja un gato")
        assert es_comando_imagen("dibújame una montaña al atardecer")
        assert es_comando_imagen("ilústrame una escena de batalla")
        assert es_comando_imagen("píntame un paisaje")
        d = parsear_imagen("dibuja un gato astronauta")
        assert d["prompt"] == "un gato astronauta"

    def test_comando_imagen_natural_sustantivo(self):
        from agent.creativos.comandos import es_comando_imagen, parsear_imagen
        assert es_comando_imagen("imagen gato")
        assert es_comando_imagen("imagen de un perro en la playa")
        assert es_comando_imagen("foto del logo nuevo")
        assert es_comando_imagen("dibujo gato astronauta")
        d = parsear_imagen("imagen de un perro en la playa")
        assert "perro" in d["prompt"] and "playa" in d["prompt"]

    def test_comando_imagen_falsos_positivos(self):
        """Mensajes que NO deben matchear el comando imagen."""
        from agent.creativos.comandos import es_comando_imagen
        assert not es_comando_imagen("la imagen está borrosa")
        assert not es_comando_imagen("qué imagen usamos ayer")
        assert not es_comando_imagen("el dibujo del niño")
        assert not es_comando_imagen("hola cómo estás")
        assert not es_comando_imagen("quiero un café")           # verbo débil sin sustantivo_img
        assert not es_comando_imagen("puedes ayudarme con algo") # verbo sin "hacer/generar imagen"
        assert not es_comando_imagen("me gusta tu logo")

    def test_comando_imagen_sin_prompt_rechaza(self):
        from agent.creativos.comandos import es_comando_imagen
        assert not es_comando_imagen("dona imagen")
        assert not es_comando_imagen("dona imagen   ")
        assert not es_comando_imagen("imagen")
        assert not es_comando_imagen("dibuja")
        assert not es_comando_imagen("")

    def test_parsear_simple(self):
        from agent.creativos.comandos import parsear_imagen
        d = parsear_imagen("dona imagen un gato")
        assert d["prompt"] == "un gato"
        assert d["calidad"] == "standard"
        assert d["aspect_ratio"] == "1:1"

    def test_parsear_premium(self):
        from agent.creativos.comandos import parsear_imagen
        d = parsear_imagen("dona imagen premium perro galáctico")
        assert d["calidad"] == "premium"
        assert d["prompt"] == "perro galáctico"

    def test_parsear_aspect_ratio(self):
        from agent.creativos.comandos import parsear_imagen
        d = parsear_imagen("dona imagen --16:9 paisaje epico")
        assert d["aspect_ratio"] == "16:9"
        assert "--16:9" not in d["prompt"]
        assert "paisaje epico" in d["prompt"]

    def test_parsear_aspect_alias(self):
        from agent.creativos.comandos import parsear_imagen
        d = parsear_imagen("dona imagen --vertical retrato")
        assert d["aspect_ratio"] == "9:16"

    def test_confirmar_cancelar(self):
        from agent.creativos.comandos import es_comando_confirmar, es_comando_cancelar
        assert es_comando_confirmar("confirmar")
        assert es_comando_confirmar("sí")
        assert es_comando_confirmar("dale")
        assert es_comando_cancelar("cancelar")
        assert es_comando_cancelar("no")
        assert not es_comando_confirmar("quizás")


# ── preparar / confirmar ────────────────────────────────────────────────────

class TestPrepararConfirmar:
    @pytest.mark.asyncio
    async def test_preparar_guarda_pendiente(self, db):
        imagen = db["imagen"]
        preview = await imagen.preparar_imagen("5551", prompt="gato", calidad="standard")
        assert preview["prompt"] == "gato"
        assert preview["costo_creditos"] == 2
        assert preview["saldo_actual"] == 0
        assert preview["alcanza"] is False

        pend = imagen.obtener_pendiente("5551")
        assert pend is not None
        assert pend.prompt == "gato"

    @pytest.mark.asyncio
    async def test_preparar_premium_costo_4(self, db):
        imagen = db["imagen"]
        preview = await imagen.preparar_imagen("5551", prompt="x", calidad="premium")
        assert preview["costo_creditos"] == 4

    @pytest.mark.asyncio
    async def test_confirmar_sin_pendiente(self, db):
        imagen = db["imagen"]
        r = await imagen.confirmar_imagen("5551_nuevo")
        assert r["estado"] == "sin_pendiente"

    @pytest.mark.asyncio
    async def test_confirmar_saldo_insuficiente(self, db):
        imagen = db["imagen"]
        await imagen.preparar_imagen("5551", prompt="gato")
        # No tiene créditos
        r = await imagen.confirmar_imagen("5551")
        assert r["estado"] == "saldo_insuficiente"
        assert "recargar" in r["mensaje"].lower()

    @pytest.mark.asyncio
    async def test_confirmar_ok_cobra_y_encola(self, db):
        billing = db["billing"]
        imagen = db["imagen"]
        jobs = db["jobs"]

        await billing.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        await imagen.preparar_imagen("5551", prompt="astronauta")

        r = await imagen.confirmar_imagen("5551")
        assert r["estado"] == "ok"
        assert r["job_id"] > 0
        # Se cobró (100 - 2)
        assert await billing.obtener_saldo("5551") == 98
        # Ya no hay pendiente
        assert imagen.obtener_pendiente("5551") is None

        # El job existe en la cola
        estado = await jobs.obtener_estado(r["job_id"])
        assert estado is not None
        assert estado["tipo"] == "gen_imagen"
        assert estado["params"]["prompt"] == "astronauta"

    @pytest.mark.asyncio
    async def test_cancelar_descarta_sin_cobrar(self, db):
        billing = db["billing"]
        imagen = db["imagen"]
        await billing.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        await imagen.preparar_imagen("5551", prompt="x")

        assert imagen.cancelar_imagen("5551") is True
        assert imagen.obtener_pendiente("5551") is None
        # No se cobró
        assert await billing.obtener_saldo("5551") == 100
        # Segundo cancel retorna False (ya no había)
        assert imagen.cancelar_imagen("5551") is False


# ── generar_imagen (low-level) ──────────────────────────────────────────────

class TestGenerarImagen:
    @pytest.mark.asyncio
    async def test_sin_api_key_usa_placeholder(self, db):
        from agent.creativos.imagen import generar_imagen
        img, meta = await generar_imagen("prompt", api_key="")
        assert len(img) > 0
        assert meta["placeholder"] is True
        assert meta["modelo"] == "placeholder"
        assert meta["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_prompt_vacio_falla(self, db):
        from agent.creativos.imagen import generar_imagen
        with pytest.raises(ValueError):
            await generar_imagen("", api_key="fake")
        with pytest.raises(ValueError):
            await generar_imagen("   ", api_key="fake")

    @pytest.mark.asyncio
    async def test_respuesta_ok(self, db, monkeypatch):
        """Mock httpx para simular Gemini devolviendo imagen base64."""
        import base64
        from agent.creativos import imagen as imagen_mod

        fake_bytes = b"\x89PNG\r\nfake"
        fake_b64 = base64.b64encode(fake_bytes).decode()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "candidates": [{
                "content": {"parts": [
                    {"inlineData": {"data": fake_b64, "mimeType": "image/png"}}
                ]}
            }]
        }

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, *a, **kw): return mock_response

        monkeypatch.setattr(imagen_mod, "MAX_RETRIES", 0)
        with patch("httpx.AsyncClient", _FakeClient):
            img, meta = await imagen_mod.generar_imagen("un gato", api_key="fake-key")

        assert img == fake_bytes
        assert meta["mime_type"] == "image/png"
        assert meta["placeholder"] is False

    @pytest.mark.asyncio
    async def test_respuesta_4xx_sin_retry(self, db, monkeypatch):
        from agent.creativos import imagen as imagen_mod

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "prompt filtered"

        llamadas = []

        class _FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, *a, **kw):
                llamadas.append(1)
                return mock_response

        monkeypatch.setattr(imagen_mod, "MAX_RETRIES", 2)
        with patch("httpx.AsyncClient", _FakeClient):
            with pytest.raises(imagen_mod.GeminiError):
                await imagen_mod.generar_imagen("x", api_key="fake")

        # 4xx no reintenta
        assert len(llamadas) == 1


# ── Handler gen_imagen end-to-end ───────────────────────────────────────────

class TestHandlerGenImagen:
    @pytest.mark.asyncio
    async def test_handler_genera_sube_registra_envia(self, db, tmp_path, monkeypatch):
        """
        E2E: encola job → worker corre handler → asset registrado en DB
        → provider.enviar_imagen invocado.
        """
        storage = db["storage"]
        billing = db["billing"]
        imagen = db["imagen"]
        jobs = db["jobs"]

        # Forzar filesystem backend
        monkeypatch.setattr(storage, "_FS_ROOT", tmp_path / "assets")
        monkeypatch.setattr(storage, "R2_ACCOUNT_ID", "")
        monkeypatch.setattr(storage, "R2_ACCESS_KEY_ID", "")
        monkeypatch.setattr(storage, "R2_SECRET_ACCESS_KEY", "")

        # Mock del provider de WhatsApp
        fake_provider = MagicMock()
        fake_provider.enviar_imagen = AsyncMock(return_value=True)
        fake_provider.enviar_mensaje = AsyncMock(return_value=True)

        monkeypatch.setattr(
            "agent.jobs.handlers_creativos._proveedor_whatsapp",
            lambda: fake_provider,
        )

        # Flujo completo
        await billing.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        await imagen.preparar_imagen("5551", prompt="dragón bailando salsa")
        r = await imagen.confirmar_imagen("5551")
        assert r["estado"] == "ok"

        # Esperar al worker inproc
        for _ in range(60):
            await asyncio.sleep(0.05)
            estado = await jobs.obtener_estado(r["job_id"])
            if estado["estado"] in ("done", "error"):
                break

        assert estado["estado"] == "done", f"Job falló: {estado}"
        asset_id = estado["asset_id_resultado"]
        assert asset_id is not None

        # Asset registrado
        asset = await storage.obtener_asset(asset_id)
        assert asset is not None
        assert asset["tipo"] == "image"
        assert asset["prompt"] == "dragón bailando salsa"

        # Provider invocado (con bytes porque fs:// no cumple condicion de URL http)
        assert fake_provider.enviar_imagen.called or fake_provider.enviar_mensaje.called

    @pytest.mark.asyncio
    async def test_handler_error_gemini_notifica(self, db, tmp_path, monkeypatch):
        """Si generar_imagen lanza, el usuario recibe texto y el job queda en error."""
        storage = db["storage"]
        billing = db["billing"]
        imagen = db["imagen"]
        jobs = db["jobs"]

        monkeypatch.setattr(storage, "_FS_ROOT", tmp_path / "assets")

        fake_provider = MagicMock()
        fake_provider.enviar_imagen = AsyncMock(return_value=True)
        fake_provider.enviar_mensaje = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "agent.jobs.handlers_creativos._proveedor_whatsapp",
            lambda: fake_provider,
        )

        # Romper generar_imagen
        from agent.creativos.imagen import GeminiError
        async def _boom(*a, **kw):
            raise GeminiError("contenido bloqueado")
        monkeypatch.setattr("agent.creativos.imagen.generar_imagen", _boom)
        # El handler hace import local, necesitamos parchear allí también
        import agent.jobs.handlers_creativos as hc
        monkeypatch.setattr(hc, "_proveedor_whatsapp", lambda: fake_provider)

        await billing.acreditar("5551", 100, "inicial", stripe_session_id="s1")
        await imagen.preparar_imagen("5551", prompt="algo")
        r = await imagen.confirmar_imagen("5551")

        for _ in range(60):
            await asyncio.sleep(0.05)
            estado = await jobs.obtener_estado(r["job_id"])
            if estado["estado"] in ("done", "error"):
                break

        assert estado["estado"] == "error"
        assert "bloqueado" in (estado["error_msg"] or "")
        # El usuario fue notificado
        assert fake_provider.enviar_mensaje.called
