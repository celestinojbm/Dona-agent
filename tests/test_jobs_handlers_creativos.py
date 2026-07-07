# tests/test_jobs_handlers_creativos.py — Idempotencia del reembolso de jobs

"""
Cubre BILL-01 (Fase 0): `_reembolsar` en agent/jobs/handlers_creativos.py
debe pasar una `idempotency_key` determinística basada en el job a
`acreditar()`, así un doble reembolso del MISMO job (ej. arq reintentando un
job tras un shutdown que ya alcanzó a reembolsar) no duplica créditos.

Escenario real: el worker es matado (SIGTERM/redeploy) DESPUÉS de que
`_reembolsar` ya corrió una vez pero ANTES de que el job se marque
'error'/'done' — arq reintenta (retry_jobs=True, max_tries=5 default) y el
handler vuelve a fallar, llamando `_reembolsar` de nuevo con el mismo job_id.
Sin idempotency_key, el segundo reembolso duplicaría los créditos.
"""

import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest

import agent.memory


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """DB SQLite aislada por test."""
    db_path = tmp_path / "handlers_creativos.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    import agent.billing as billing
    importlib.reload(billing)
    import agent.jobs.handlers_creativos as handlers
    importlib.reload(handlers)
    await agent.memory.inicializar_db()
    return billing, handlers


class TestReembolsoIdempotentePorJob:
    @pytest.mark.asyncio
    async def test_doble_reembolso_mismo_job_acredita_una_sola_vez(self, db):
        billing, handlers = db
        telefono = "5559990001"
        await billing.acreditar(telefono, 100, "seed", stripe_session_id="seed_1")
        saldo_pre = await billing.obtener_saldo(telefono)  # 100

        # Simula: el worker reembolsa por un fallo del provider (job_id=42).
        saldo_1 = await handlers._reembolsar(
            telefono, 10, "provider falló", scope="gen_imagen", job_id=42,
        )
        assert saldo_1 == saldo_pre + 10

        # Simula el escenario BILL-01: arq reintenta el MISMO job (mismo
        # job_id=42) tras un shutdown que ya había reembolsado — el handler
        # vuelve a fallar y llama _reembolsar de nuevo.
        saldo_2 = await handlers._reembolsar(
            telefono, 10, "provider falló", scope="gen_imagen", job_id=42,
        )

        # Sólo se acreditó UNA vez: el segundo reembolso es no-op idempotente.
        assert saldo_2 == saldo_1
        assert await billing.obtener_saldo(telefono) == saldo_pre + 10

    @pytest.mark.asyncio
    async def test_reembolsos_de_jobs_distintos_acreditan_ambos(self, db):
        billing, handlers = db
        telefono = "5559990002"
        await billing.acreditar(telefono, 100, "seed", stripe_session_id="seed_2")
        saldo_pre = await billing.obtener_saldo(telefono)

        await handlers._reembolsar(telefono, 10, "provider falló", job_id=1)
        await handlers._reembolsar(telefono, 15, "fallo al guardar", job_id=2)

        # Jobs distintos → idempotency_key distinta → ambos reembolsos aplican.
        assert await billing.obtener_saldo(telefono) == saldo_pre + 25

    @pytest.mark.asyncio
    async def test_sin_job_id_no_hay_dedup_compat_legacy(self, db):
        """Compat: llamadas sin job_id (legacy/tests) no ganan dedup — mismo
        comportamiento que antes de BILL-01. No debe romper nada existente."""
        billing, handlers = db
        telefono = "5559990003"
        await billing.acreditar(telefono, 100, "seed", stripe_session_id="seed_3")
        saldo_pre = await billing.obtener_saldo(telefono)

        await handlers._reembolsar(telefono, 10, "provider falló")
        await handlers._reembolsar(telefono, 10, "provider falló")

        # Sin idempotency_key, cada llamada es un acreditar() independiente.
        assert await billing.obtener_saldo(telefono) == saldo_pre + 20

    @pytest.mark.asyncio
    async def test_creditos_cero_no_reembolsa(self, db):
        billing, handlers = db
        telefono = "5559990004"
        resultado = await handlers._reembolsar(telefono, 0, "sin costo", job_id=99)
        assert resultado is None


# ── Call-sites de _reembolsar dentro de cada handler ────────────────────────
#
# Los tests de arriba ejercen `_reembolsar` en aislamiento. Estos ejercen los
# CALL-SITES reales: el `await _reembolsar(..., job_id=job_id)` dentro del
# `except` de cada handler creativo — el path fallo-del-provider → reembolso
# que ahora propaga la idempotency_key derivada de `params["_job_id"]`.
#
# Cada caso rompe el provider (o el guardado en storage) y verifica que:
#   1. el handler re-lanza (contrato: el error sube a `_ejecutar_con_estado`),
#   2. el reembolso se acredita EXACTAMENTE una vez,
#   3. un reintento del MISMO job (mismo `_job_id`, escenario BILL-01 de arq)
#      NO duplica el reembolso — es no-op idempotente.


def _provider_mock() -> MagicMock:
    """WhatsApp provider falso: enviar_* nunca hacen I/O real."""
    prov = MagicMock()
    prov.enviar_mensaje = AsyncMock(return_value=True)
    prov.enviar_imagen = AsyncMock(return_value=True)
    prov.enviar_audio = AsyncMock(return_value=True)
    prov.enviar_video = AsyncMock(return_value=True)
    prov.enviar_documento = AsyncMock(return_value=True)
    return prov


# (id, handler_attr, params_base, provider_module, provider_func, error_module, error_attr)
# provider_module/func → dónde parchear la función low-level que el handler
# importa localmente; error_* → la excepción específica que dispara el path de
# reembolso del provider (primer `except` de cada handler).
_CASOS_PROVIDER = [
    (
        "gen_imagen",
        "_handler_gen_imagen",
        {"prompt": "gato astronauta", "costo_creditos": 2},
        "agent.creativos.imagen",
        "generar_imagen",
        "agent.creativos.imagen",
        "GeminiError",
    ),
    (
        "bg_remove",
        "_handler_bg_remove",
        {"source_url": "https://example.com/x.jpg", "costo_creditos": 1},
        "agent.creativos.bg_remove",
        "remove_background",
        "agent.creativos.bg_remove",
        "PhotoroomError",
    ),
    (
        "gen_voz",
        "_handler_gen_voz",
        {"texto": "hola mundo", "costo_creditos": 3},
        "agent.creativos.voz",
        "text_to_speech",
        "agent.creativos.voz",
        "ElevenLabsError",
    ),
    (
        "gen_documento",
        "_handler_gen_documento",
        {"tipo": "factura", "datos": {"cliente": {"nombre": "Ana"}}, "costo_creditos": 2},
        "agent.creativos.pdf",
        "generar_pdf",
        "agent.creativos.pdf",
        "PDFError",
    ),
    (
        "gen_video",
        "_handler_gen_video",
        {"prompt": "olas rompiendo", "duration_s": 5, "costo_creditos": 20},
        "agent.creativos.video",
        "generar_video",
        "agent.creativos.video",
        "ReplicateError",
    ),
    (
        "gen_video_avatar",
        "_handler_gen_video_avatar",
        {"texto": "bienvenidos", "avatar_id": "a1", "voice_id": "v1", "costo_creditos": 30},
        "agent.creativos.video_avatar",
        "generar_video_avatar",
        "agent.creativos.video_avatar",
        "HeyGenError",
    ),
]


class TestReembolsoDesdeHandlers:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "caso_id, handler_attr, params_base, prov_mod, prov_fn, err_mod, err_attr",
        _CASOS_PROVIDER,
        ids=[c[0] for c in _CASOS_PROVIDER],
    )
    async def test_provider_falla_reembolsa_idempotente(
        self, db, monkeypatch, caso_id, handler_attr, params_base,
        prov_mod, prov_fn, err_mod, err_attr,
    ):
        """El provider lanza su Error → el handler reembolsa con job_id y
        re-lanza. Reintentar el mismo job no duplica el reembolso."""
        billing, handlers = db
        telefono = f"55500{caso_id[:4]}"
        await billing.acreditar(telefono, 200, "seed", stripe_session_id=f"seed_{caso_id}")
        saldo_pre = await billing.obtener_saldo(telefono)

        # Romper la función low-level del provider en su módulo de origen
        # (el handler la importa localmente, así que se parchea allí).
        error_cls = getattr(importlib.import_module(err_mod), err_attr)

        async def _boom(*a, **kw):
            raise error_cls("provider reventó")

        monkeypatch.setattr(f"{prov_mod}.{prov_fn}", _boom)
        monkeypatch.setattr(handlers, "_proveedor_whatsapp", _provider_mock)
        # bg_remove descarga la imagen fuente ANTES de llamar al provider; sin
        # mock haría un GET real y caería en OTRO except (descarga). Lo dejamos
        # exitoso para llegar al path del provider (PhotoroomError).
        async def _descarga_ok(*a, **kw):
            return b"\x00fuente", "image/jpeg"
        monkeypatch.setattr(handlers, "_descargar_url", _descarga_ok)

        costo = params_base["costo_creditos"]
        job_id = 4242
        params = {**params_base, "_job_id": job_id}
        handler = getattr(handlers, handler_attr)

        # 1er intento: el provider falla → reembolso + re-lanza.
        with pytest.raises(error_cls):
            await handler(telefono, params)
        assert await billing.obtener_saldo(telefono) == saldo_pre + costo

        # 2º intento del MISMO job (retry de arq tras un reembolso ya emitido):
        # vuelve a fallar, llama _reembolsar con el mismo job_id → no-op.
        with pytest.raises(error_cls):
            await handler(telefono, params)
        assert await billing.obtener_saldo(telefono) == saldo_pre + costo

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "caso_id, handler_attr, params_base, prov_mod, prov_fn",
        [(c[0], c[1], c[2], c[3], c[4]) for c in _CASOS_PROVIDER],
        ids=[c[0] for c in _CASOS_PROVIDER],
    )
    async def test_guardado_falla_reembolsa_idempotente(
        self, db, monkeypatch, caso_id, handler_attr, params_base, prov_mod, prov_fn,
    ):
        """El provider produce bytes OK pero `storage.subir_asset` revienta →
        el handler ejecuta el segundo path de reembolso (fallo al guardar) con
        job_id. Reintentar el mismo job no duplica el reembolso."""
        import agent.storage as storage
        importlib.reload(storage)

        billing, handlers = db
        telefono = f"55501{caso_id[:4]}"
        await billing.acreditar(telefono, 200, "seed", stripe_session_id=f"seedg_{caso_id}")
        saldo_pre = await billing.obtener_saldo(telefono)

        # Provider OK: devuelve (bytes, meta) válidos.
        async def _ok(*a, **kw):
            return b"\x00binario", {"mime_type": "image/png", "modelo": "fake", "folio": "F1", "total": 10, "moneda": "USD"}

        monkeypatch.setattr(f"{prov_mod}.{prov_fn}", _ok)

        # storage.subir_asset revienta → dispara el except "fallo al guardar".
        async def _subir_boom(*a, **kw):
            raise RuntimeError("R2 caído")

        monkeypatch.setattr(storage, "subir_asset", _subir_boom)
        monkeypatch.setattr(handlers, "_proveedor_whatsapp", _provider_mock)
        # bg_remove: dejar la descarga de la fuente exitosa para llegar a subir.
        async def _descarga_ok(*a, **kw):
            return b"\x00fuente", "image/jpeg"
        monkeypatch.setattr(handlers, "_descargar_url", _descarga_ok)

        costo = params_base["costo_creditos"]
        params = {**params_base, "_job_id": 7777}
        handler = getattr(handlers, handler_attr)

        with pytest.raises(RuntimeError):
            await handler(telefono, params)
        assert await billing.obtener_saldo(telefono) == saldo_pre + costo

        # Retry del mismo job: idempotente, no doble reembolso.
        with pytest.raises(RuntimeError):
            await handler(telefono, params)
        assert await billing.obtener_saldo(telefono) == saldo_pre + costo

    @pytest.mark.asyncio
    async def test_bg_remove_descarga_falla_reembolsa_idempotente(self, db, monkeypatch):
        """bg_remove tiene un path de reembolso extra: si NO puede descargar la
        imagen fuente (antes de tocar el provider), reembolsa con job_id. Cubre
        el primer `except` del handler."""
        billing, handlers = db
        telefono = "5550dl01"
        await billing.acreditar(telefono, 100, "seed", stripe_session_id="seed_dl")
        saldo_pre = await billing.obtener_saldo(telefono)

        async def _descarga_boom(*a, **kw):
            raise RuntimeError("404 al bajar la fuente")

        monkeypatch.setattr(handlers, "_descargar_url", _descarga_boom)
        monkeypatch.setattr(handlers, "_proveedor_whatsapp", _provider_mock)

        params = {"source_url": "https://example.com/x.jpg", "costo_creditos": 1, "_job_id": 9090}

        with pytest.raises(RuntimeError):
            await handlers._handler_bg_remove(telefono, params)
        assert await billing.obtener_saldo(telefono) == saldo_pre + 1

        # Retry del mismo job: no duplica el reembolso.
        with pytest.raises(RuntimeError):
            await handlers._handler_bg_remove(telefono, params)
        assert await billing.obtener_saldo(telefono) == saldo_pre + 1
