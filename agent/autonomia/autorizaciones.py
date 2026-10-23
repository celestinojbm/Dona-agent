"""Ciclo de vida de autorizaciones + configuración de autonomía (F1).

`confirmar_X` DEBE llamar a `verificar_y_consumir` antes de ejecutar: sólo una
autorización persistida, del mismo usuario, no vencida, con el mismo hash de
argumentos y dentro del máximo, y aún no consumida, permite ejecutar. El consumo
es de uso único y atómico (UPDATE condicional por estado) → ni retries ni
concurrencia ejecutan dos veces.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update

from agent.autonomia.models import AutonomiaPorAccion, AutorizacionAccion
from agent.autonomia.politica import (
    DecisionPolitica,
    evaluar_politica,
    hash_argumentos,
)
from agent.memory import async_session

logger = logging.getLogger("dona")

VENCIMIENTO_DEFECTO_MIN = 30


@dataclass(frozen=True)
class ResultadoVerificacion:
    ok: bool
    razon: str


async def obtener_config(telefono: str, tipo_accion: str) -> AutonomiaPorAccion | None:
    async with async_session() as s:
        return (await s.execute(
            select(AutonomiaPorAccion).where(
                AutonomiaPorAccion.telefono == telefono,
                AutonomiaPorAccion.tipo_accion == tipo_accion,
            )
        )).scalar_one_or_none()


async def fijar_nivel(
    telefono: str,
    tipo_accion: str,
    nivel: int,
    *,
    umbral_creditos: int | None = None,
    tope_por_accion: int | None = None,
    tope_periodo: int | None = None,
    periodo: str = "",
    zona_horaria: str = "",
) -> AutonomiaPorAccion:
    """Crea o actualiza la configuración de autonomía (upsert por usuario+tipo).
    Sube la versión en cada cambio (invalida autorizaciones de política viejas)."""
    if not (1 <= int(nivel) <= 4):
        raise ValueError("nivel debe estar entre 1 y 4")
    async with async_session() as s:
        row = (await s.execute(
            select(AutonomiaPorAccion).where(
                AutonomiaPorAccion.telefono == telefono,
                AutonomiaPorAccion.tipo_accion == tipo_accion,
            )
        )).scalar_one_or_none()
        if row is None:
            row = AutonomiaPorAccion(
                telefono=telefono,
                tipo_accion=tipo_accion,
                nivel=int(nivel),
                umbral_creditos=umbral_creditos,
                tope_por_accion=tope_por_accion,
                tope_periodo=tope_periodo,
                periodo=periodo,
                zona_horaria=zona_horaria,
                version=1,
                actualizado=datetime.utcnow(),
            )
            s.add(row)
        else:
            row.nivel = int(nivel)
            row.umbral_creditos = umbral_creditos
            row.tope_por_accion = tope_por_accion
            row.tope_periodo = tope_periodo
            row.periodo = periodo
            row.zona_horaria = zona_horaria
            row.version = int(row.version) + 1
            row.actualizado = datetime.utcnow()
        await s.commit()
        await s.refresh(row)
        return row


async def _crear_autorizacion(
    *,
    telefono: str,
    accion_ref: str,
    tipo_accion: str,
    args: dict | None,
    cotizacion_creditos: int,
    maximo_creditos: int,
    origen: str,
    vencimiento_min: int = VENCIMIENTO_DEFECTO_MIN,
    version_politica: int = 0,
) -> AutorizacionAccion:
    from sqlalchemy.exc import IntegrityError

    autz = AutorizacionAccion(
        telefono=telefono,
        accion_ref=accion_ref[:120],
        tipo_accion=tipo_accion,
        args_hash=hash_argumentos(args),
        cotizacion_creditos=int(cotizacion_creditos),
        maximo_creditos=int(maximo_creditos),
        origen=origen,
        estado="vigente",
        vencimiento=datetime.utcnow() + timedelta(minutes=vencimiento_min),
        version_politica=int(version_politica),
        creado=datetime.utcnow(),
    )
    async with async_session() as s:
        s.add(autz)
        try:
            await s.commit()
            await s.refresh(autz)
            return autz
        except IntegrityError:
            await s.rollback()
            # Ya existe autorización para este accion_ref (uso único por acción).
            existente = (await s.execute(
                select(AutorizacionAccion).where(
                    AutorizacionAccion.accion_ref == accion_ref[:120]
                )
            )).scalar_one()
            return existente


async def autorizar_o_confirmar(
    *,
    telefono: str,
    accion_ref: str,
    tipo_accion: str,
    args: dict | None,
    cotizacion_creditos: int,
    consumo_periodo_creditos: int = 0,
    destinatario_autorizado: bool = True,
    clase_accion: str = "gasto",
    vencimiento_min: int = VENCIMIENTO_DEFECTO_MIN,
) -> tuple[str, DecisionPolitica]:
    """preparar→cotizar→evaluar→autorizar. Devuelve ("autorizado"|
    "requiere_confirmacion", decision). Si la política autoriza (L2–L4, o clase
    lectura/borrador) crea una autorización de ORIGEN política; si no, no crea
    nada (espera confirmación humana vía crear_autorizacion_humana).

    `clase_accion` (lectura|borrador|gasto|envio) implementa la decisión #8:
    sólo lectura/borrador auto-ejecutan sin confirmar."""
    config = await obtener_config(telefono, tipo_accion)
    decision = evaluar_politica(
        tipo_accion=tipo_accion,
        cotizacion_creditos=cotizacion_creditos,
        config=config,
        consumo_periodo_creditos=consumo_periodo_creditos,
        destinatario_autorizado=destinatario_autorizado,
        clase_accion=clase_accion,
    )
    if decision.requiere_humano:
        return "requiere_confirmacion", decision

    await _crear_autorizacion(
        telefono=telefono,
        accion_ref=accion_ref,
        tipo_accion=tipo_accion,
        args=args,
        cotizacion_creditos=cotizacion_creditos,
        maximo_creditos=cotizacion_creditos,
        origen="politica",
        vencimiento_min=vencimiento_min,
        version_politica=int(getattr(config, "version", 0) or 0),
    )
    return "autorizado", decision


async def crear_autorizacion_humana(
    *,
    telefono: str,
    accion_ref: str,
    tipo_accion: str,
    args: dict | None,
    cotizacion_creditos: int,
    maximo_creditos: int | None = None,
    vencimiento_min: int = VENCIMIENTO_DEFECTO_MIN,
) -> AutorizacionAccion:
    """Registra la aprobación humana explícita (la que `confirmar_X` consumirá)."""
    return await _crear_autorizacion(
        telefono=telefono,
        accion_ref=accion_ref,
        tipo_accion=tipo_accion,
        args=args,
        cotizacion_creditos=cotizacion_creditos,
        maximo_creditos=int(maximo_creditos if maximo_creditos is not None else cotizacion_creditos),
        origen="humana",
        vencimiento_min=vencimiento_min,
    )


async def verificar_y_consumir(
    *,
    telefono: str,
    accion_ref: str,
    args: dict | None,
    cotizacion_creditos: int,
) -> ResultadoVerificacion:
    """Verifica y consume (uso único) la autorización. Rechaza: inexistente,
    ajena, vencida, argumentos modificados, cotización sobre el máximo, ya
    consumida/revocada. El consumo es atómico (UPDATE condicional por estado)."""
    ahora = datetime.utcnow()
    async with async_session() as s:
        autz = (await s.execute(
            select(AutorizacionAccion).where(
                AutorizacionAccion.accion_ref == accion_ref[:120]
            )
        )).scalar_one_or_none()

        if autz is None:
            return ResultadoVerificacion(False, "inexistente")
        # Recibo ajeno/autorización ajena: no se ejecuta.
        if autz.telefono != telefono:
            return ResultadoVerificacion(False, "ajena")
        if autz.estado != "vigente":
            return ResultadoVerificacion(False, f"estado_{autz.estado}")
        if autz.vencimiento is not None and autz.vencimiento <= ahora:
            await s.execute(
                update(AutorizacionAccion)
                .where(AutorizacionAccion.id == autz.id, AutorizacionAccion.estado == "vigente")
                .values(estado="vencida")
            )
            await s.commit()
            return ResultadoVerificacion(False, "vencida")
        if autz.args_hash != hash_argumentos(args):
            return ResultadoVerificacion(False, "argumentos_modificados")
        if int(cotizacion_creditos) > int(autz.maximo_creditos):
            return ResultadoVerificacion(False, "supera_maximo")

        # Consumo atómico de uso único: sólo una ejecución gana.
        res = await s.execute(
            update(AutorizacionAccion)
            .where(
                AutorizacionAccion.id == autz.id,
                AutorizacionAccion.estado == "vigente",
            )
            .values(estado="consumida", consumida_en=ahora)
        )
        await s.commit()
        if res.rowcount == 0:
            return ResultadoVerificacion(False, "carrera_ya_consumida")
        return ResultadoVerificacion(True, "ok")


async def revocar(telefono: str, accion_ref: str) -> bool:
    """Revoca una autorización vigente (detiene la cola). Inmediato."""
    async with async_session() as s:
        res = await s.execute(
            update(AutorizacionAccion)
            .where(
                AutorizacionAccion.accion_ref == accion_ref[:120],
                AutorizacionAccion.telefono == telefono,
                AutorizacionAccion.estado == "vigente",
            )
            .values(estado="revocada")
        )
        await s.commit()
        return res.rowcount > 0
