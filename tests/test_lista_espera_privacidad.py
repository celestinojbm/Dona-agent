# tests/test_lista_espera_privacidad.py — Privacidad de la lista de espera (#334).

"""
Cubre agent/lista_espera/privacidad.py y lo que el alta deja ver:

  - El alta responde lo mismo para un correo nuevo, repetido o ya invitado
    (sin oráculo de pertenencia ni de estado).
  - Solo se guardan las columnas necesarias (ni IP ni código ni navegador).
  - Retención: filas en espera vencidas por alta, invitadas por canje; la
    purga corre sola en cada alta nueva.
  - Acceso (exportar) y borrado por solicitud, que también limpia el
    contador de canjes fallidos derivado del correo.
  - Ningún log contiene el correo.
"""

import importlib
import logging
from datetime import datetime, timedelta

import pytest

import tests.test_lista_espera as _base
from tests.test_lista_espera import CODIGO, _filas, _post

# Mismo fixture que test_lista_espera.py (SQLite temporal + módulos recargados).
setup = _base.setup

ALTA = "/internal/lista-espera"
CANJE = "/internal/lista-espera/invitacion"


async def _insertar(memory, servicio, email, estado, creado, invitado_en=None):
    async with memory.async_session() as session:
        session.add(
            servicio.ListaEspera(
                email=email, estado=estado, origen="web", creado=creado, invitado_en=invitado_en
            )
        )
        await session.commit()


def _privacidad():
    # setup recarga memory: recargar también este módulo para que use el
    # async_session y el modelo nuevos.
    import agent.lista_espera.privacidad as _priv

    return importlib.reload(_priv)


async def test_alta_no_revela_si_el_correo_estaba_o_esta_invitado(setup):
    client, _servicio, _memory = setup
    nuevo = _post(client, ALTA, email="ana@negocio.com")
    repetido = _post(client, ALTA, email="ANA@negocio.com")
    _post(client, CANJE, email="ana@negocio.com", codigo=CODIGO)
    invitado = _post(client, ALTA, email="ana@negocio.com")
    assert nuevo.status_code == repetido.status_code == invitado.status_code == 200
    assert nuevo.json() == repetido.json() == invitado.json() == {"estado": "en_espera"}


async def test_solo_guarda_las_columnas_necesarias(setup):
    _client, servicio, _memory = setup
    columnas = {c.name for c in servicio.ListaEspera.__table__.columns}
    # Una columna nueva aquí (IP, código, user-agent...) tiene que justificarse
    # en privacidad.py y en la política de privacidad, no colarse.
    assert columnas == {"id", "email", "estado", "origen", "creado", "invitado_en"}


async def test_purga_respeta_la_retencion(setup):
    _client, servicio, memory = setup
    priv = _privacidad()
    ahora = datetime.utcnow()
    viejo = ahora - timedelta(days=priv.RETENCION_DIAS + 1)
    reciente = ahora - timedelta(days=priv.RETENCION_DIAS - 1)
    await _insertar(memory, servicio, "espera-vieja@n.com", "en_espera", viejo)
    await _insertar(memory, servicio, "espera-reciente@n.com", "en_espera", reciente)
    # Invitada: cuenta desde el canje, no desde el alta.
    await _insertar(memory, servicio, "inv-canje-reciente@n.com", "invitado", viejo, reciente)
    await _insertar(memory, servicio, "inv-canje-viejo@n.com", "invitado", viejo, viejo)
    await _insertar(memory, servicio, "inv-sin-fecha@n.com", "invitado", viejo, None)

    assert await priv.purgar_vencidos(ahora) == 3
    quedan = {f.email for f in await _filas(memory, servicio)}
    assert quedan == {"espera-reciente@n.com", "inv-canje-reciente@n.com"}


async def test_alta_nueva_purga_las_vencidas(setup):
    client, servicio, memory = setup
    priv = _privacidad()
    viejo = datetime.utcnow() - timedelta(days=priv.RETENCION_DIAS + 30)
    await _insertar(memory, servicio, "olvidado@n.com", "en_espera", viejo)
    _post(client, ALTA, email="nueva@n.com")
    assert {f.email for f in await _filas(memory, servicio)} == {"nueva@n.com"}


async def test_exportar_devuelve_lo_guardado(setup):
    client, _servicio, _memory = setup
    priv = _privacidad()
    _post(client, ALTA, email="Bea@Negocio.com")
    datos = await priv.exportar("  bea@negocio.com ")
    assert datos["email"] == "bea@negocio.com"
    assert datos["estado"] == "en_espera" and datos["origen"] == "web"
    assert datos["invitado_en"] is None and datos["retencion_dias"] == priv.RETENCION_DIAS
    assert await priv.exportar("nadie@negocio.com") is None


async def test_borrar_quita_la_fila_y_el_contador_de_canjes(setup):
    client, servicio, memory = setup
    priv = _privacidad()
    from sqlalchemy import select

    import agent.dashboard_lockout as lock

    _post(client, ALTA, email="cris@negocio.com")
    for _ in range(3):
        _post(client, CANJE, email="cris@negocio.com", codigo="MALO-MALO-1")
    async with memory.async_session() as session:
        assert (await session.execute(select(lock.DashboardLoginIntento))).scalars().all()

    assert await priv.borrar("CRIS@negocio.com") is True
    assert await _filas(memory, servicio) == []
    async with memory.async_session() as session:
        assert (await session.execute(select(lock.DashboardLoginIntento))).scalars().all() == []
    # Borrar algo que no está no falla.
    assert await priv.borrar("cris@negocio.com") is False


async def test_borrar_y_exportar_rechazan_correo_invalido(setup):
    _client, servicio, _memory = setup
    priv = _privacidad()
    for fn in (priv.borrar, priv.exportar):
        with pytest.raises(servicio.EmailInvalido):
            await fn("no-es-correo")


async def test_ningun_log_contiene_el_correo(setup, caplog):
    client, servicio, memory = setup
    priv = _privacidad()
    correo = "secreto.dueno@negocio.com"
    viejo = datetime.utcnow() - timedelta(days=priv.RETENCION_DIAS + 1)
    await _insertar(memory, servicio, "vencido.dueno@negocio.com", "en_espera", viejo)
    with caplog.at_level(logging.DEBUG, logger="dona"):
        _post(client, ALTA, email=correo)
        _post(client, CANJE, email=correo, codigo="MALO-MALO-1")
        _post(client, CANJE, email=correo, codigo=CODIGO)
        await priv.exportar(correo)
        await priv.borrar(correo)
    # Solo los logs de la app: el driver de SQLite de los tests (aiosqlite) en
    # DEBUG imprime los parámetros SQL, y eso no es un log de Dona.
    texto = "\n".join(
        r.getMessage() for r in caplog.records if r.name == "dona" or r.name.startswith("agent")
    ).lower()
    assert "secreto.dueno" not in texto and "vencido.dueno" not in texto
    assert "retención: 1 filas" in texto  # la purga sí deja constancia, sin correos


async def test_cli_valida_argumentos(setup, capsys):
    _client, _servicio, _memory = setup
    priv = _privacidad()
    assert await priv._cli([]) == 2
    assert await priv._cli(["borrar"]) == 2
    assert await priv._cli(["exportar", "nadie@negocio.com"]) == 0
    assert "no está en la lista" in capsys.readouterr().out
