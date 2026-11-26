"""Privacidad de la lista de espera: retención, acceso y borrado (CCPA).

Qué se guarda por correo: el correo normalizado, el estado (en_espera /
invitado), el origen (web / invitacion) y dos fechas. Nada más: ni IP (los
límites usan un HMAC que caduca en una hora, ver limites.py), ni el código
canjeado, ni datos del navegador.

Retención: RETENCION_DIAS (constante en código; cambiarla exige PR). Una fila
en espera caduca a los RETENCION_DIAS de su alta; una invitada, a los
RETENCION_DIAS de su canje (es la referencia de la invitación). La purga
corre sola en cada alta nueva (sin scheduler) y a mano con el comando de abajo.

Acceso y borrado: /privacy/export y /privacy/delete van por teléfono con OTP
de WhatsApp, y esta tabla no tiene teléfono. Las solicitudes de la lista de
espera llegan por el correo de la política de privacidad; el operador verifica
que la pide el titular del buzón (respondiendo desde ese correo) y ejecuta:

    python -m agent.lista_espera.privacidad exportar <correo>
    python -m agent.lista_espera.privacidad borrar <correo>
    python -m agent.lista_espera.privacidad purgar

No hay endpoint público de borrado a propósito: sin verificar el buzón,
cualquiera podría borrar el lugar de otra persona, y la respuesta diría si el
correo estaba en la lista (enumeración).

Logs: nunca el correo; solo conteos.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, or_, select

from agent.lista_espera.models import ListaEspera
from agent.memory import async_session

logger = logging.getLogger("dona")

RETENCION_DIAS = 365


async def purgar_vencidos(ahora: datetime | None = None) -> int:
    """Borra las filas que superan la retención. Devuelve cuántas borró."""
    limite = (ahora or datetime.utcnow()) - timedelta(days=RETENCION_DIAS)
    async with async_session() as session:
        res = await session.execute(
            delete(ListaEspera).where(
                or_(
                    and_(ListaEspera.estado != "invitado", ListaEspera.creado < limite),
                    and_(
                        ListaEspera.estado == "invitado",
                        # Una fila invitada sin fecha de canje (no debería
                        # existir) caduca por su alta.
                        or_(
                            ListaEspera.invitado_en < limite,
                            and_(ListaEspera.invitado_en.is_(None), ListaEspera.creado < limite),
                        ),
                    ),
                )
            )
        )
        await session.commit()
    borradas = int(res.rowcount or 0)
    if borradas:
        logger.info(f"[LISTA-ESPERA] retención: {borradas} filas vencidas borradas")
    return borradas


async def exportar(email: str) -> dict | None:
    """Datos guardados de un correo (derecho de acceso). None si no está."""
    from agent.lista_espera.servicio import normalizar_email

    e = normalizar_email(email)
    async with async_session() as session:
        fila = (
            await session.execute(select(ListaEspera).where(ListaEspera.email == e))
        ).scalar_one_or_none()
    if fila is None:
        return None
    return {
        "email": fila.email,
        "estado": fila.estado,
        "origen": fila.origen,
        "creado": fila.creado.isoformat() if fila.creado else None,
        "invitado_en": fila.invitado_en.isoformat() if fila.invitado_en else None,
        "retencion_dias": RETENCION_DIAS,
    }


async def borrar(email: str) -> bool:
    """Borra el correo de la lista y su contador de canjes fallidos.

    Devuelve True si había fila en la lista. El contador de intentos
    (``invitacion:<correo>``, guardado como HMAC) se borra siempre: también
    se deriva del correo.
    """
    from agent.dashboard_lockout import registrar_resultado
    from agent.lista_espera.servicio import normalizar_email

    e = normalizar_email(email)
    async with async_session() as session:
        res = await session.execute(delete(ListaEspera).where(ListaEspera.email == e))
        await session.commit()
    # registrar_resultado(..., True) borra la fila del lockout si existe.
    await registrar_resultado(f"invitacion:{e}", True)
    borrada = bool(res.rowcount)
    logger.info(f"[LISTA-ESPERA] borrado por solicitud · había_fila={borrada}")
    return borrada


async def _cli(args: list[str]) -> int:
    from agent.memory import inicializar_db

    if not args or args[0] not in ("exportar", "borrar", "purgar"):
        print(__doc__)
        return 2
    accion = args[0]
    if accion in ("exportar", "borrar") and len(args) != 2:
        print(f"Uso: python -m agent.lista_espera.privacidad {accion} <correo>")
        return 2
    await inicializar_db()
    if accion == "purgar":
        print(f"Filas vencidas borradas: {await purgar_vencidos()}")
    elif accion == "exportar":
        datos = await exportar(args[1])
        print(json.dumps(datos, ensure_ascii=False, indent=2) if datos else "Ese correo no está en la lista.")
    else:
        print("Borrado." if await borrar(args[1]) else "Ese correo no estaba en la lista (contador limpio igual).")
    return 0


if __name__ == "__main__":  # pragma: no cover - ejecución manual del operador
    sys.exit(asyncio.run(_cli(sys.argv[1:])))
