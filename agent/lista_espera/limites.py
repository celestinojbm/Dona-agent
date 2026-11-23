"""Límites por IP y globales de la lista de espera (issue #334).

Por qué hace falta además del lockout por correo:
  El lockout de canje usa la clave ``invitacion:<correo>``. Un atacante que
  rota correos (gratis: basta con inventarlos) prueba códigos sin límite. Y el
  alta no tenía ningún límite: un bot podía llenar la tabla con correos falsos.

Política (ventanas fijas de 1 hora, constantes en código):
  - Alta:  ALTA_POR_IP por IP · ALTA_GLOBAL en total.
  - Canje: CANJE_POR_IP por IP · CANJE_GLOBAL en total (con éxito o sin él).
  - Se comprueba la IP ANTES que el cupo global: quien ya superó su tope
    personal no gasta el cupo compartido (mismo criterio que rate_limiter.py).

Dónde vive el contador: en la base (tabla ``lista_espera_limite``), no en
memoria ni en Redis. El backend puede correr con varios workers y sin Redis;
un contador en memoria por worker multiplicaría el límite. El incremento es
un único UPSERT atómico (SQLite y PostgreSQL), sin leer-y-escribir.

De dónde sale la IP: el backend solo ve la IP de la landing (Vercel). La
landing lee la IP del visitante y la manda DENTRO del cuerpo firmado con HMAC,
así que nadie fuera de la landing puede falsearla. Sin IP (o IP inválida) el
request cae en un cubo compartido "sin-ip": fail-closed, no queda sin límite.

Privacidad (CCPA): la IP nunca se guarda en claro. La clave es
HMAC-SHA256(INTERNAL_BRIDGE_SECRET, ip) truncado, y las filas caducan con la
ventana. IPv6 se agrupa por /64 (un cliente IPv6 suele controlar un /64
entero; sin agrupar, rotar direcciones esquivaría el límite).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import time
from datetime import datetime, timedelta

from sqlalchemy import DateTime, Integer, String, delete
from sqlalchemy.orm import Mapped, mapped_column

from agent.memory import Base, async_session

VENTANA_SEGUNDOS = 60 * 60
ALTA_POR_IP = 10
ALTA_GLOBAL = 500
CANJE_POR_IP = 20
CANJE_GLOBAL = 200

_LIMITES = {
    "alta": (ALTA_POR_IP, ALTA_GLOBAL),
    "canje": (CANJE_POR_IP, CANJE_GLOBAL),
}
_SIN_IP = "sin-ip"
_EPOCH = datetime(1970, 1, 1)  # datetimes naive en UTC, como el resto del repo


def _ahora_epoch() -> int:
    return int(time.time())


class ListaEsperaLimite(Base):
    """Contador de una ventana: una fila por (ámbito, sujeto, ventana)."""

    __tablename__ = "lista_espera_limite"

    # "<ámbito>:<ip|global>:<sujeto>:<índice de ventana>" · sin PII.
    clave: Mapped[str] = mapped_column(String(120), primary_key=True)
    conteo: Mapped[int] = mapped_column(Integer, default=0)
    expira_en: Mapped[datetime] = mapped_column(DateTime, index=True)


class LimiteExcedido(RuntimeError):
    def __init__(self, motivo: str, retry_after_segundos: int) -> None:
        super().__init__(motivo)
        self.motivo = motivo  # "ip" | "global"
        self.retry_after_segundos = retry_after_segundos


def normalizar_ip(ip: str | None) -> str:
    """IP canónica para agrupar: IPv4 tal cual, IPv6 por /64, inválida → sin-ip."""
    crudo = (ip or "").strip()
    if not crudo or len(crudo) > 64:
        return _SIN_IP
    try:
        dir_ip = ipaddress.ip_address(crudo)
    except ValueError:
        return _SIN_IP
    if isinstance(dir_ip, ipaddress.IPv6Address):
        if dir_ip.ipv4_mapped is not None:
            return str(dir_ip.ipv4_mapped)
        return str(ipaddress.IPv6Network(f"{dir_ip}/64", strict=False))
    return str(dir_ip)


def _clave_opaca(valor: str) -> str:
    """HMAC de la IP normalizada. Fail-closed sin secret en entorno estricto."""
    from agent.entorno import es_entorno_estricto

    secreto = os.getenv("INTERNAL_BRIDGE_SECRET", "").strip()
    if not secreto:
        if es_entorno_estricto():
            raise RuntimeError(
                "[LISTA-ESPERA] INTERNAL_BRIDGE_SECRET no configurado en entorno "
                "estricto: la clave de IP sería computable por cualquiera."
            )
        secreto = "dona-lista-espera-dev-secret-do-not-use-in-prod"
    return hmac.new(secreto.encode("utf-8"), valor.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def _insert_para(dialecto: str):
    if dialecto == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialecto == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover - el repo solo usa PostgreSQL y SQLite
        raise RuntimeError(f"[LISTA-ESPERA] dialecto sin soporte de UPSERT: {dialecto}")
    return insert


async def _incrementar(session, clave: str, expira_en: datetime) -> int:
    """UPSERT atómico: crea la fila con 1 o suma 1. Devuelve el conteo nuevo."""
    insert = _insert_para(session.bind.dialect.name)
    stmt = (
        insert(ListaEsperaLimite)
        .values(clave=clave, conteo=1, expira_en=expira_en)
        .on_conflict_do_update(
            index_elements=[ListaEsperaLimite.clave],
            set_={"conteo": ListaEsperaLimite.conteo + 1},
        )
        .returning(ListaEsperaLimite.conteo)
    )
    return int((await session.execute(stmt)).scalar_one())


async def consumir(ambito: str, ip: str | None) -> None:
    """Cuenta un intento de ``ambito`` ("alta" | "canje") para esta IP.

    Lanza LimiteExcedido si se supera el tope por IP o el global.
    """
    por_ip, global_ = _LIMITES[ambito]
    epoch = _ahora_epoch()
    ahora = _EPOCH + timedelta(seconds=epoch)
    indice = epoch // VENTANA_SEGUNDOS
    fin_ventana = (indice + 1) * VENTANA_SEGUNDOS
    retry = max(fin_ventana - epoch, 1)
    expira_en = _EPOCH + timedelta(seconds=fin_ventana)

    sujeto = _clave_opaca(normalizar_ip(ip))
    clave_ip = f"{ambito}:ip:{sujeto}:{indice}"
    clave_global = f"{ambito}:global:{indice}"

    async with async_session() as session:
        conteo_ip = await _incrementar(session, clave_ip, expira_en)
        if conteo_ip == 1:
            # Primera vez en esta ventana para esta IP: limpiar ventanas viejas.
            await session.execute(
                delete(ListaEsperaLimite).where(ListaEsperaLimite.expira_en <= ahora)
            )
        if conteo_ip > por_ip:
            await session.commit()
            raise LimiteExcedido("ip", retry)
        conteo_global = await _incrementar(session, clave_global, expira_en)
        await session.commit()
    if conteo_global > global_:
        raise LimiteExcedido("global", retry)
