# tests/test_ccpa_borrado_gcal_exacto.py
# Fase 2 · TEMA 7 · 7.3 — el borrado CCPA no debe tocar datos de terceros.

"""
Batería adversarial para el borrado del derecho al olvido (`borrar_datos_usuario`).

El bug histórico: la caché de dedup de Google Calendar se borraba con
`DELETE ... WHERE clave LIKE '%{telefono}%'`. Como la clave tiene la forma
`gcal_reminder_{telefono}_{evento_id}`, un teléfono que es SUBCADENA de otro
(p. ej. "5511" ⊂ "115511") hacía que borrar al primero eliminara también las
claves de dedup del segundo. Consecuencia doble:
  1. Privacidad (CCPA 7.3): se borran datos de un tercero que no lo pidió.
  2. TCPA: sin su marca de dedup, ese tercero volvería a recibir el MISMO
     recordatorio de calendario (envío duplicado = exposición legal per-evento).

El borrado debe ser por MATCH ANCLADO al prefijo exacto del usuario, nunca por
subcadena.
"""

import importlib

import pytest

import agent.memory


@pytest.fixture
async def memoria(tmp_path, monkeypatch):
    """SQLite aislada con las tablas de agent/memory.py recreadas."""
    db_path = tmp_path / "ccpa.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    await agent.memory.inicializar_db()
    return agent.memory


@pytest.mark.asyncio
async def test_borrado_gcal_no_toca_dedup_de_un_tercero(memoria):
    """Borrar "5511" NO debe eliminar la dedup GCal de "115511" (superstring)."""
    from sqlalchemy import select

    from agent.memory import RecordatorioGCalEnviado, async_session

    victima = "5511"        # ejerce el derecho al olvido
    tercero = "115511"      # su teléfono CONTIENE "5511" como subcadena
    clave_victima = f"gcal_reminder_{victima}_evtA"
    clave_tercero = f"gcal_reminder_{tercero}_evtB"

    async with async_session() as s:
        s.add(RecordatorioGCalEnviado(clave=clave_victima))
        s.add(RecordatorioGCalEnviado(clave=clave_tercero))
        await s.commit()

    conteos = await memoria.borrar_datos_usuario(victima)

    async with async_session() as s:
        claves = set(
            (await s.execute(select(RecordatorioGCalEnviado.clave))).scalars().all()
        )

    # La dedup del usuario borrado SÍ se elimina...
    assert clave_victima not in claves
    assert conteos.get("recordatorios_gcal_enviados") == 1
    # ...pero la del tercero permanece intacta.
    assert clave_tercero in claves


@pytest.mark.asyncio
async def test_borrado_gcal_elimina_todas_las_claves_propias(memoria):
    """El usuario borrado pierde TODAS sus claves GCal (varios eventos)."""
    from sqlalchemy import select

    from agent.memory import RecordatorioGCalEnviado, async_session

    tel = "5599001"
    claves_propias = [f"gcal_reminder_{tel}_ev{i}" for i in range(3)]
    clave_ajena = "gcal_reminder_5599_otro"  # prefijo distinto: NO debe borrarse

    async with async_session() as s:
        for c in claves_propias:
            s.add(RecordatorioGCalEnviado(clave=c))
        s.add(RecordatorioGCalEnviado(clave=clave_ajena))
        await s.commit()

    conteos = await memoria.borrar_datos_usuario(tel)

    async with async_session() as s:
        restantes = set(
            (await s.execute(select(RecordatorioGCalEnviado.clave))).scalars().all()
        )

    assert conteos.get("recordatorios_gcal_enviados") == 3
    assert restantes == {clave_ajena}
