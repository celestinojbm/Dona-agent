"""Lógica de la lista de espera y del canje de códigos de invitación.

Reglas:
  - Alta idempotente: el mismo correo dos veces no duplica filas ni cambia
    un estado "invitado" a "en_espera".
  - Códigos de invitación: vienen de DONA_CODIGOS_INVITACION (lista separada
    por comas, en el entorno del backend). Lista vacía = ningún código es
    válido (fail-closed). Cada código debe tener 80 bits (16 símbolos Crockford
    base32, ver codigos.py); uno débil se ignora. Se comparan con
    hmac.compare_digest tras normalizar (mayúsculas, sin guiones, O→0, I/L→1).
  - Fuerza bruta: los intentos fallidos usan el lockout persistente del
    dashboard con una clave propia ("invitacion:<correo>"). Como rotar
    correos lo esquiva, además hay límite por IP y global (limites.py) en
    el alta y en el canje.
  - Privacidad: el alta responde siempre "en_espera" (no revela si un correo
    ya estaba o canjeó). Retención, acceso y borrado en privacidad.py.
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

from sqlalchemy import update

from agent.lista_espera import codigos, limites
from agent.lista_espera.models import ListaEspera, insert_para
from agent.memory import async_session

logger = logging.getLogger("dona")

LISTA_ESPERA_ENVIO_CORREO_ACTIVO = False

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$")
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


def _codigos_configurados() -> tuple[str, ...]:
    return codigos.cargar(os.getenv("DONA_CODIGOS_INVITACION", ""))


def codigo_valido(codigo: str) -> bool:
    """True si el código coincide con alguno configurado (tiempo constante por código)."""
    # Cargar la configuración ANTES de mirar el candidato: así el error de un
    # código configurado débil sale en el primer canje, sea cual sea. Si no,
    # con los códigos viejos todavía configurados (y usuarios escribiendo esos
    # mismos códigos viejos) el aviso no saldría nunca.
    configurados = _codigos_configurados()
    candidato = codigos.normalizar(codigo)
    # El formato no es secreto: un candidato mal formado se descarta sin comparar.
    if codigos.motivo_debil(candidato) is not None:
        return False
    valido = False
    for c in configurados:
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
    """Alta idempotente. Devuelve SIEMPRE {"estado": "en_espera"}.

    La respuesta no distingue correo nuevo, repetido o ya invitado: sería un
    oráculo para saber si un correo ajeno está en la lista o canjeó una
    invitación. El estado "invitado" solo se ve al canjear un código.

    Lanza EmailInvalido o DemasiadosIntentos (límite por IP o global). El
    límite se cuenta también para correos ya registrados: si no, repetir un
    correo serviría para sondear sin coste (p. ej. por tiempos de respuesta).

    INSERT ... ON CONFLICT DO NOTHING: dos altas simultáneas del mismo correo
    no chocan con el UNIQUE (antes, SELECT + INSERT daba 500 en PostgreSQL).
    Cada alta nueva purga las filas que superan la retención (privacidad.py).
    """
    from agent.lista_espera import privacidad

    e = normalizar_email(email)
    await _consumir_limite("alta", ip)
    origen = origen if origen in _ORIGENES else "web"
    async with async_session() as session:
        insert = insert_para(session.bind.dialect.name)
        creada = await session.execute(
            insert(ListaEspera)
            .values(email=e, estado="en_espera", origen=origen, creado=datetime.utcnow())
            .on_conflict_do_nothing(index_elements=[ListaEspera.email])
            .returning(ListaEspera.id)
        )
        nuevo = creada.scalar_one_or_none() is not None
        await session.commit()
    if nuevo:
        await privacidad.purgar_vencidos()
        await _notificar_alta(e, "en_espera")
    return {"estado": "en_espera"}


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
        insert = insert_para(session.bind.dialect.name)
        # Atómico: crea la fila si no existe y marca invitado solo si no lo
        # estaba (conserva el primer invitado_en). Sin leer-y-escribir.
        await session.execute(
            insert(ListaEspera)
            .values(email=e, estado="en_espera", origen="invitacion", creado=ahora)
            .on_conflict_do_nothing(index_elements=[ListaEspera.email])
        )
        await session.execute(
            update(ListaEspera)
            .where(ListaEspera.email == e, ListaEspera.estado != "invitado")
            .values(estado="invitado", invitado_en=ahora)
        )
        await session.commit()
    await _notificar_alta(e, "invitado")
    return {"estado": "invitado"}
