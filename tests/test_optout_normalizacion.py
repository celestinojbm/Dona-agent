# tests/test_optout_normalizacion.py — Fase 0 · 2.5 · normalización del opt-out TCPA

"""
REGRESIÓN 2.5: el gate comparaba el teléfono CRUDO contra el opt-out, pero cada
proveedor entrega el número distinto (whapi '<díg>@s.whatsapp.net', meta '<díg>',
twilio 'whatsapp:+<díg>') y el owner tipea numero_destino con '+'. Un STOP de un
tercero se guardaba bajo su chat_id y NO matcheaba cuando el ejecutor consultaba
el gate con el numero_destino → el mensaje salía pese al opt-out (riesgo TCPA).

Fix: clave canónica (solo dígitos) + dual-write del opt-out (cruda + canónica en
sync) y supresión normalizada. El gate lee la fila canónica como autoritativa
(con fallback a la cruda para filas pre-existentes), así las 3 representaciones
del mismo número colapsan a la misma decisión.

Verificado adversarialmente (workflow map-tcpa-optout-surface): guard contra la
colisión de clave '', re-opt-in cross-formato, y sin fila 'stale enabled'.
"""

import importlib

import pytest


TEL = "5215551234567"
SUFFIX = f"{TEL}@s.whatsapp.net"   # whapi
TWILIO = f"whatsapp:+{TEL}"         # twilio
PLUS = f"+{TEL}"                    # numero_destino tipeado por el owner


@pytest.fixture
async def entorno(tmp_path, monkeypatch):
    db = tmp_path / "optout.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db}")

    import agent.memory
    import agent.business.models as _bm
    import agent.automation.models as _am
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    await agent.memory.inicializar_db()

    import agent.envio_gate as gate
    import agent.proactivity as proactivity
    gate._supresion_emergencia.clear()
    return agent.memory, gate, proactivity


# ── clave canónica ─────────────────────────────────────────────────────────


def test_clave_canonica_colapsa_los_3_formatos():
    import agent.envio_gate as gate

    assert gate.clave_canonica(SUFFIX) == TEL
    assert gate.clave_canonica(TWILIO) == TEL
    assert gate.clave_canonica(PLUS) == TEL
    assert gate.clave_canonica(TEL) == TEL


def test_clave_canonica_sin_digitos_no_colapsa_a_vacio():
    """Guard (verificador): una entrada sin dígitos NO debe colapsar a '' —
    si no, todos los destinos no numéricos compartirían la misma fila/clave y
    un STOP de uno afectaría a todos."""
    import agent.envio_gate as gate

    assert gate.normalizar_telefono("grupo-abc") == ""
    assert gate.clave_canonica("grupo-abc") == "grupo-abc"   # fallback al crudo
    assert gate.clave_canonica("grupo-uno") != gate.clave_canonica("grupo-dos")


# ── opt-out de tercero cross-formato (corazón de 2.5) ──────────────────────


@pytest.mark.parametrize(
    "formato_stop, formato_envio",
    [
        (SUFFIX, PLUS),    # whapi → owner tipea con '+'
        (TEL, PLUS),       # meta → owner tipea con '+'
        (TWILIO, TEL),     # twilio → owner tipea sin '+'
        (PLUS, SUFFIX),    # cruzado
    ],
)
async def test_stop_tercero_bloquea_pese_a_formato_distinto(
    entorno, formato_stop, formato_envio
):
    memoria, gate, proactivity = entorno
    await proactivity.manejar_stop_tcpa(formato_stop)
    # Simular cross-worker: la supresión in-memory no cruza procesos; el bloqueo
    # debe venir del opt-out DURABLE vía la lectura canónica.
    gate._supresion_emergencia.clear()
    with gate.contexto_envio_automatico():
        assert await gate.puede_enviar(formato_envio) is False


async def test_start_reactiva_mismo_formato(entorno):
    memoria, gate, proactivity = entorno
    await proactivity.manejar_stop_tcpa(SUFFIX)
    gate._supresion_emergencia.clear()
    with gate.contexto_envio_automatico():
        assert await gate.puede_enviar(PLUS) is False

    await proactivity.manejar_start_tcpa(SUFFIX)
    with gate.contexto_envio_automatico():
        assert await gate.puede_enviar(PLUS) is True
        assert await gate.puede_enviar(SUFFIX) is True


async def test_start_reactiva_cross_formato(entorno):
    """Re-opt-in desde OTRA representación del mismo número: la fila canónica
    enabled es autoritativa y deja pasar, sin que una cruda vieja disabled trabe
    (gap de re-opt-in roto que marcó el verificador)."""
    memoria, gate, proactivity = entorno
    await proactivity.manejar_stop_tcpa(SUFFIX)
    await proactivity.manejar_start_tcpa(PLUS)
    gate._supresion_emergencia.clear()
    with gate.contexto_envio_automatico():
        assert await gate.puede_enviar(SUFFIX) is True
        assert await gate.puede_enviar(PLUS) is True


async def test_stop_persiste_bajo_ambas_claves(entorno):
    memoria, gate, proactivity = entorno
    await proactivity.manejar_stop_tcpa(SUFFIX)
    crudo = await memoria.obtener_proactividad(SUFFIX)
    canon = await memoria.obtener_proactividad(TEL)
    assert crudo is not None and crudo["proactive_enabled"] is False
    assert canon is not None and canon["proactive_enabled"] is False


async def test_dona_pausa_normaliza(entorno):
    """El segundo writer de opt-out ('dona pausa') usa la misma clave canónica."""
    memoria, gate, proactivity = entorno
    await proactivity.manejar_comando_proactividad(SUFFIX, "dona pausa")
    gate._supresion_emergencia.clear()
    with gate.contexto_envio_automatico():
        assert await gate.puede_enviar(PLUS) is False


# ── supresión de emergencia normalizada (in-memory) ────────────────────────


def test_supresion_normalizada_cross_formato():
    import agent.envio_gate as gate

    gate._supresion_emergencia.clear()
    gate.registrar_supresion_emergencia(SUFFIX)
    assert gate.esta_suprimido_emergencia(PLUS) is True
    assert gate.esta_suprimido_emergencia(TWILIO) is True
    gate.limpiar_supresion_emergencia(TEL)
    assert gate.esta_suprimido_emergencia(SUFFIX) is False


def test_supresion_sin_digitos_no_colisiona():
    import agent.envio_gate as gate

    gate._supresion_emergencia.clear()
    gate.registrar_supresion_emergencia("grupo-uno")
    assert gate.esta_suprimido_emergencia("grupo-dos") is False
    assert gate.esta_suprimido_emergencia(TEL) is False


# ── owner sin regresión ────────────────────────────────────────────────────


async def test_owner_habilitado_por_default_puede_recibir(entorno):
    memoria, gate, proactivity = entorno
    with gate.contexto_envio_automatico():
        assert await gate.puede_enviar(TEL) is True


async def test_owner_optout_crudo_preexistente_respetado(entorno):
    """Un opt-out guardado SOLO bajo el formato crudo (fila pre-existente, sin
    canónica) se respeta: el gate cae a la lectura exacta — sin migración."""
    memoria, gate, proactivity = entorno
    await memoria.guardar_proactividad(SUFFIX, proactive_enabled=False)
    gate._supresion_emergencia.clear()
    with gate.contexto_envio_automatico():
        assert await gate.puede_enviar(SUFFIX) is False
