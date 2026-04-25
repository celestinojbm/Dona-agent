# tests/test_creativos_ajustar.py — Tests del flujo `ajustar` multi-creativo

"""
Cubre:
  - Detección de comando genérico `ajustar: X` (parsear, detección).
  - `ajustar_video`: sin pendiente, con pendiente, con cambio de duración.
  - `ajustar_imagen`: sin pendiente, con pendiente (prompt reemplazado).
  - `ajustar_voz`: sin pendiente, con pendiente (recalcula costo por largo).
  - `_detectar_duracion` (función pura, regex de lenguaje natural).
"""

import importlib
import pytest
from unittest.mock import patch, AsyncMock


# ── Detectores puros ────────────────────────────────────────────────────────

class TestDetectorAjustar:
    def test_es_comando_ajustar_basico(self):
        from agent.creativos.comandos import es_comando_ajustar
        assert es_comando_ajustar("ajustar: plano aéreo")
        assert es_comando_ajustar("cambiar prompt: más oscuro")
        assert es_comando_ajustar("modifica el prompt para que sea noche")
        assert es_comando_ajustar("dona ajusta: nuevo texto")
        assert es_comando_ajustar("editar el texto: otra frase")
        assert es_comando_ajustar("reescribir: versión corta")

    def test_es_comando_ajustar_rechaza_no_matches(self):
        from agent.creativos.comandos import es_comando_ajustar
        assert not es_comando_ajustar("")
        assert not es_comando_ajustar("ajustar")           # sin contenido
        assert not es_comando_ajustar("confirmar")
        assert not es_comando_ajustar("hola")

    def test_parsear_ajustar_extrae_cuerpo(self):
        from agent.creativos.comandos import parsear_ajustar
        assert parsear_ajustar("ajustar: plano aéreo al atardecer")["nueva_idea"] == "plano aéreo al atardecer"
        assert parsear_ajustar("cambiar prompt: más oscuro")["nueva_idea"] == "más oscuro"
        # "el prompt" opcional se descarta, queda sólo el contenido
        assert parsear_ajustar("modifica el prompt para que sea noche")["nueva_idea"] == "para que sea noche"


# ── Detección de duración (pura) ────────────────────────────────────────────

class TestDetectarDuracion:
    def test_default_cuando_no_hay_pistas(self):
        from agent.creativos.video import _detectar_duracion, VIDEO_DURATION_DEFAULT
        assert _detectar_duracion("un café humeante en una barra") == VIDEO_DURATION_DEFAULT

    def test_palabras_corto_devuelven_5s(self):
        from agent.creativos.video import _detectar_duracion
        assert _detectar_duracion("video corto de gato") == 5
        assert _detectar_duracion("video rápido de un auto") == 5
        assert _detectar_duracion("video brevísimo de la playa") == 5
        assert _detectar_duracion("video flash del logo") == 5

    def test_numero_con_seg_devuelve_5s_si_pequeno(self):
        from agent.creativos.video import _detectar_duracion
        assert _detectar_duracion("video de 5 segundos de gato") == 5
        assert _detectar_duracion("video de 5s") == 5
        assert _detectar_duracion("video de 6 seg") == 5
        assert _detectar_duracion("video de cinco segundos") == 5

    def test_numero_grande_devuelve_10s(self):
        from agent.creativos.video import _detectar_duracion
        assert _detectar_duracion("video de 10 segundos") == 10
        assert _detectar_duracion("video de 8s de un perro") == 10

    def test_largo_mantiene_10s(self):
        from agent.creativos.video import _detectar_duracion
        assert _detectar_duracion("video largo de un paseo") == 10
        assert _detectar_duracion("video completo del producto") == 10


# ── Detección de aspect ratio (pura) ────────────────────────────────────────

class TestDetectarAspect:
    def test_default_es_horizontal(self):
        from agent.creativos.video import _detectar_aspect, VIDEO_ASPECT_DEFAULT
        assert _detectar_aspect("un café humeante") == VIDEO_ASPECT_DEFAULT

    def test_vertical_tiktok(self):
        from agent.creativos.video import _detectar_aspect
        assert _detectar_aspect("video vertical de mi producto") == "9:16"
        assert _detectar_aspect("video para tiktok de comida") == "9:16"
        assert _detectar_aspect("video para reels") == "9:16"
        assert _detectar_aspect("video en formato 9:16") == "9:16"
        assert _detectar_aspect("video para historias de Instagram") == "9:16"

    def test_cuadrado(self):
        from agent.creativos.video import _detectar_aspect
        assert _detectar_aspect("video cuadrado del logo") == "1:1"
        assert _detectar_aspect("video 1:1 del plato") == "1:1"

    def test_horizontal_explicito(self):
        from agent.creativos.video import _detectar_aspect
        assert _detectar_aspect("video horizontal del local") == "16:9"
        assert _detectar_aspect("video panorámico de la playa") == "16:9"


# ── Fixture para los tests de ajustar_X ─────────────────────────────────────

@pytest.fixture
async def db(tmp_path, monkeypatch):
    """DB aislada + recarga de módulos para que DATABASE_URL aplique."""
    db_path = tmp_path / "ajustar.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("JOBS_BACKEND", "inproc")

    import agent.memory as _memory
    import agent.billing as _billing
    import agent.storage as _storage
    import agent.jobs.queue as _queue
    import agent.jobs.worker as _worker
    import agent.jobs as _jobs
    import agent.creativos.prompt_imagen as _pi
    import agent.creativos.imagen as _imagen
    import agent.creativos.voz as _voz
    import agent.creativos.video as _video
    import agent.creativos.prompt_video as _pv

    importlib.reload(_memory)
    importlib.reload(_billing)
    importlib.reload(_storage)
    importlib.reload(_queue)
    importlib.reload(_worker)
    importlib.reload(_jobs)
    importlib.reload(_pi)
    importlib.reload(_imagen)
    importlib.reload(_voz)
    importlib.reload(_pv)
    importlib.reload(_video)

    # Pass-through del optimizer de imagen: evita llamar a Claude y mantiene
    # `pend.prompt == idea` para los asserts del flujo ajustar.
    async def _fake_optimizar_img(idea, calidad="standard"):
        return {"en": idea, "es": idea}
    monkeypatch.setattr(_pi, "optimizar_prompt_imagen", _fake_optimizar_img)

    await _memory.inicializar_db()
    yield {
        "memory": _memory, "billing": _billing, "imagen": _imagen,
        "voz": _voz, "video": _video,
    }


# ── ajustar_imagen ──────────────────────────────────────────────────────────

class TestAjustarImagen:
    @pytest.mark.asyncio
    async def test_sin_pendiente_devuelve_estado_sin_pendiente(self, db):
        imagen = db["imagen"]
        r = await imagen.ajustar_imagen("5551", "nuevo prompt")
        assert r["estado"] == "sin_pendiente"

    @pytest.mark.asyncio
    async def test_reemplaza_prompt_sin_cobrar(self, db):
        imagen = db["imagen"]
        billing = db["billing"]
        await billing.acreditar("5551", 100, "inicial", stripe_session_id="s-img")
        await imagen.preparar_imagen("5551", prompt="gato", calidad="standard")

        r = await imagen.ajustar_imagen("5551", "perro astronauta en Marte")
        assert r["estado"] == "ok"
        assert r["prompt"] == "perro astronauta en Marte"
        # No se cobró nada
        assert await billing.obtener_saldo("5551") == 100
        # Pendiente actualizado
        pend = imagen.obtener_pendiente("5551")
        assert pend is not None
        assert pend.prompt == "perro astronauta en Marte"
        assert pend.calidad == "standard"  # mantiene calidad

    @pytest.mark.asyncio
    async def test_ajustar_no_afecta_aspect_ni_calidad(self, db):
        imagen = db["imagen"]
        await imagen.preparar_imagen("5551", prompt="x", calidad="premium", aspect_ratio="16:9")
        r = await imagen.ajustar_imagen("5551", "nuevo")
        assert r["calidad"] == "premium"
        assert r["aspect_ratio"] == "16:9"
        assert r["costo_creditos"] == 4  # premium

    @pytest.mark.asyncio
    async def test_nuevo_prompt_vacio_falla(self, db):
        imagen = db["imagen"]
        await imagen.preparar_imagen("5551", prompt="x")
        with pytest.raises(ValueError):
            await imagen.ajustar_imagen("5551", "")


# ── ajustar_voz ─────────────────────────────────────────────────────────────

class TestAjustarVoz:
    @pytest.mark.asyncio
    async def test_sin_pendiente(self, db):
        voz = db["voz"]
        r = await voz.ajustar_voz("5552", "nuevo texto")
        assert r["estado"] == "sin_pendiente"

    @pytest.mark.asyncio
    async def test_reemplaza_texto_y_recalcula_costo(self, db):
        voz = db["voz"]
        billing = db["billing"]
        await billing.acreditar("5552", 100, "inicial", stripe_session_id="s-voz")

        # Texto corto → costo bajo
        await voz.preparar_voz("5552", "Hola mundo")
        pend = voz.obtener_pendiente("5552")
        costo_inicial = pend.costo_creditos

        # Ajustamos a un texto largo (> 500 chars) → debería recalcular a COSTO_VOZ_LARGA
        texto_largo = ("Esto es una frase muy larga. " * 30).strip()
        r = await voz.ajustar_voz("5552", texto_largo)
        assert r["estado"] == "ok"
        assert r["chars"] == len(texto_largo)
        assert r["costo_creditos"] > costo_inicial
        assert await billing.obtener_saldo("5552") == 100  # nada cobrado

    @pytest.mark.asyncio
    async def test_mantiene_voice_id(self, db):
        voz = db["voz"]
        await voz.preparar_voz("5552", "original", voice_id="custom-voice-abc")
        r = await voz.ajustar_voz("5552", "reemplazado")
        assert r["voice_id"] == "custom-voice-abc"


# ── ajustar_video ───────────────────────────────────────────────────────────
# Mockeamos optimizar_prompt_video para no llamar al LLM en tests.

async def _fake_optimizar(idea, tiene_imagen_referencia=False):
    return {"en": f"{idea} (EN)", "es": f"{idea} (ES)"}


class TestAjustarVideo:
    @pytest.mark.asyncio
    async def test_sin_pendiente(self, db):
        video = db["video"]
        r = await video.ajustar_video("5553", "nueva idea")
        assert r["estado"] == "sin_pendiente"

    @pytest.mark.asyncio
    async def test_reemplaza_idea_y_prompts(self, db):
        video = db["video"]
        billing = db["billing"]
        await billing.acreditar("5553", 500, "inicial", stripe_session_id="s-vid")

        with patch("agent.creativos.prompt_video.optimizar_prompt_video",
                   new=AsyncMock(side_effect=_fake_optimizar)):
            await video.preparar_video("5553", "un café humeante")
            r = await video.ajustar_video("5553", "un café al atardecer en la playa")

        assert r["estado"] == "ok"
        assert r["idea_usuario"] == "un café al atardecer en la playa"
        # El preview muestra la versión ES
        assert "(ES)" in r["prompt_optimizado"]
        # Saldo intacto
        assert await billing.obtener_saldo("5553") == 500

    @pytest.mark.asyncio
    async def test_mantiene_duracion_si_nueva_idea_no_la_menciona(self, db):
        video = db["video"]
        with patch("agent.creativos.prompt_video.optimizar_prompt_video",
                   new=AsyncMock(side_effect=_fake_optimizar)):
            # Preparamos con duración explícita de 10s
            await video.preparar_video("5553", "un gato corriendo", duration_s=10)
            pend = video.obtener_pendiente("5553")
            assert pend.duration_s == 10
            costo_antes = pend.costo_creditos

            # Nueva idea sin mencionar duración → mantiene 10s
            r = await video.ajustar_video("5553", "un perro bailando")
        assert r["duration_s"] == 10
        assert r["costo_creditos"] == costo_antes

    @pytest.mark.asyncio
    async def test_ajuste_con_duracion_corta_recalcula_costo(self, db):
        video = db["video"]
        with patch("agent.creativos.prompt_video.optimizar_prompt_video",
                   new=AsyncMock(side_effect=_fake_optimizar)):
            # Prep con default 10s
            await video.preparar_video("5553", "un café humeante", duration_s=10)
            costo_10s = video.obtener_pendiente("5553").costo_creditos

            # Ajuste mencionando "corto" → baja a 5s
            r = await video.ajustar_video("5553", "mejor hazlo corto")
        assert r["duration_s"] == 5
        assert r["costo_creditos"] < costo_10s

    @pytest.mark.asyncio
    async def test_preparar_con_idea_corta_setea_5s(self, db):
        video = db["video"]
        with patch("agent.creativos.prompt_video.optimizar_prompt_video",
                   new=AsyncMock(side_effect=_fake_optimizar)):
            preview = await video.preparar_video("5553", "video corto de un gato")
        assert preview["duration_s"] == 5
        # 5s cuesta menos que 10s
        from agent.billing import COSTO_VIDEO_5S, COSTO_VIDEO_CORTO
        assert preview["costo_creditos"] == COSTO_VIDEO_5S
        assert COSTO_VIDEO_5S < COSTO_VIDEO_CORTO

    @pytest.mark.asyncio
    async def test_preparar_detecta_aspect_vertical(self, db):
        video = db["video"]
        with patch("agent.creativos.prompt_video.optimizar_prompt_video",
                   new=AsyncMock(side_effect=_fake_optimizar)):
            preview = await video.preparar_video("5553", "video vertical para tiktok de un plato")
        assert preview["aspect_ratio"] == "9:16"
        pend = video.obtener_pendiente("5553")
        assert pend.aspect_ratio == "9:16"

    @pytest.mark.asyncio
    async def test_ajuste_puede_cambiar_aspect(self, db):
        video = db["video"]
        with patch("agent.creativos.prompt_video.optimizar_prompt_video",
                   new=AsyncMock(side_effect=_fake_optimizar)):
            await video.preparar_video("5553", "un café humeante")  # default 16:9
            pend = video.obtener_pendiente("5553")
            assert pend.aspect_ratio == "16:9"

            r = await video.ajustar_video("5553", "mejor en vertical para instagram")
        assert r["aspect_ratio"] == "9:16"
