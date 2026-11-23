"""Lógica de la lista de espera y del canje de códigos de invitación.

Reglas:
  - Alta idempotente: el mismo correo dos veces no duplica filas ni cambia
    un estado "invitado" a "en_espera".
  - Códigos de invitación: vienen de DONA_CODIGOS_INVITACION (lista separada
    por comas, en el entorno del backend). Lista vacía = ningún código es
    válido (fail-closed). Se comparan con hmac.compare_digest, sin distinguir
    mayúsculas, y deben tener al menos 8 caracteres.
  - Fuerza bruta: los intentos fallidos usan el lockout persistente del
    dashboard con una clave propia ("invitacion:<correo>"). Como rotar
    correos lo esquiva, además hay límite por IP y global (limites.py) en
    el alta y en el canje.
  - Correos: no se envía nada. El aviso de alta queda detrás de
    LISTA_ESPERA_ENVIO_CORREO_ACTIVO (constante en código: encenderla exige
    PR revisado, como DONA_EN_PAUSA en la landing).
"""

from __future__ import annotations

import hmac
import logging
import os
import re
from datetime import datetime

from sqlalchemy import select

from agent.lista_espera import limites
from agent.lista_espera.models import ListaEspera
from agent.memory import async_session

logger = logging.getLogger("dona")

LISTA_ESPERA_ENVIO_CORREO_ACTIVO = False

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$")
_MIN_LARGO_CODIGO = 8
_ORIGENES = ("web", "invitacion")


class EmailInvalido(ValueError):
    pass


class CodigoInvalido(ValueError):
    pass


class DemasiadosIntentos(RuntimeError):
    def __init__(self, retry_after_segundos: int) -> None:
        super().__init__("demasiados_intentos")
        self.retry_after_segundos = retry_after_segundos


def normalizar_email(email: str) -> str:
    e = (email or "").strip().lower()
    if len(e) > 254 or not _EMAIL_RE.match(e):
        raise EmailInvalido("email_invalido")
    return e


def _codigos_configurados() -> list[str]:
    crudos = os.getenv("DONA_CODIGOS_INVITACION", "")
    return [
        c.strip().upper()
        for c in crudos.split(",")
        if len(c.strip()) >= _MIN_LARGO_CODIGO
    ]


def codigo_valido(codigo: str) -> bool:
    """True si el código coincide con alguno configurado (tiempo constante por código)."""
    candidato = (codigo or "").strip().upper()
    if len(candidato) < _MIN_LARGO_CODIGO:
        return False
    valido = False
    for c in _codigos_configurados():
        # Sin cortocircuito: se comparan todos para no filtrar cuál coincide.
        valido = hmac.compare_digest(c.encode("utf-8"), candidato.encode("utf-8")) or valido
    return valido


async def _notificar_alta(email: str, estado: str) -> bool:
    """Aviso por correo del alta. Apagado: no sale nada hasta que haya un
    proveedor de correo verificado y LISTA_ESPERA_ENVIO_CORREO_ACTIVO."""
    if not LISTA_ESPERA_ENVIO_CORREO_ACTIVO:
        logger.info(f"[LISTA-ESPERA] aviso por correo desactivado · estado={estado}")
        return False
    raise NotImplementedError("Envío de correos de la lista de espera sin proveedor")


async def _consumir_limite(ambito: str, ip: str | None) -> None:
    try:
        await limites.consumir(ambito, ip)
    except limites.LimiteExcedido as exc:
        logger.warning(f"[LISTA-ESPERA] límite {ambito} excedido · motivo={exc.motivo}")
        raise DemasiadosIntentos(exc.retry_after_segundos) from exc


async def registrar(email: str, origen: str = "web", ip: str | None = None) -> dict:
    """Alta idempotente. Devuelve {"estado": ..., "nuevo": bool}.

    Lanza EmailInvalido o DemasiadosIntentos (límite por IP o global). El
    límite se cuenta también para correos ya registrados: si no, repetir un
    correo serviría para sondear estados sin coste.
    """
    e = normalizar_email(email)
    await _consumir_limite("alta", ip)
    origen = origen if origen in _ORIGENES else "web"
    async with async_session() as session:
        fila = (
            await session.execute(select(ListaEspera).where(ListaEspera.email == e))
        ).scalar_one_or_none()
        if fila is not None:
            return {"estado": fila.estado, "nuevo": False}
        fila = ListaEspera(email=e, estado="en_espera", origen=origen)
        session.add(fila)
        await session.commit()
    await _notificar_alta(e, "en_espera")
    return {"estado": "en_espera", "nuevo": True}


async def canjear_invitacion(email: str, codigo: str, ip: str | None = None) -> dict:
    """Marca el correo como invitado si el código es válido.

    Lanza EmailInvalido, CodigoInvalido o DemasiadosIntentos. El límite por
    IP y global cuenta cada intento antes de mirar el código (con éxito o
    sin él), así no revela nada sobre qué códigos valen.
    """
    from agent.dashboard_lockout import registrar_resultado, verificar_lockout

    e = normalizar_email(email)
    await _consumir_limite("canje", ip)
    clave = f"invitacion:{e}"
    lock = await verificar_lockout(clave)
    if lock.get("bloqueado"):
        raise DemasiadosIntentos(int(lock.get("retry_after_segundos") or 60))

    if not codigo_valido(codigo):
        res = await registrar_resultado(clave, False)
        if res.get("bloqueado"):
            raise DemasiadosIntentos(int(res.get("retry_after_segundos") or 60))
        raise CodigoInvalido("codigo_invalido")

    await registrar_resultado(clave, True)
    ahora = datetime.utcnow()
    async with async_session() as session:
        fila = (
            await session.execute(select(ListaEspera).where(ListaEspera.email == e))
        ).scalar_one_or_none()
        if fila is None:
            fila = ListaEspera(email=e, origen="invitacion")
            session.add(fila)
        if fila.estado != "invitado":
            fila.estado = "invitado"
            fila.invitado_en = ahora
        await session.commit()
    await _notificar_alta(e, "invitado")
    return {"estado": "invitado"}
