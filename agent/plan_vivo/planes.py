"""Lógica del plan vivo (F14): creación, avance de pasos y estado.

Concurrencia optimista por `revision`: cada escritura exige la revisión que leyó
y la incrementa; una revisión vieja no pisa una nueva (rowcount 0 → conflicto).
Un paso terminal (completado|fallido) no regresa a pendiente ante un retry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update

from agent.memory import async_session
from agent.plan_vivo.models import (
    ESTADOS_PASO_TERMINALES,
    ESTADOS_PLAN,
    PlanTarea,
)

logger = logging.getLogger("dona")

_MAX_RESULTADO = 500


def plan_vivo_habilitado() -> bool:
    return os.getenv("DONA_LIVE_PLAN_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _sanear_resultado(texto: str) -> str:
    """Resultado de paso saneado: sin razonamiento interno, acotado."""
    t = (texto or "").strip().replace("\n", " ")
    return t[:_MAX_RESULTADO]


def hash_plan(version: int, pasos: list[dict], coste_maximo: int, destinatarios: list | None) -> str:
    """Hash que liga la confirmación a esta versión del plan. Cambiar pasos,
    coste o destinatarios cambia el hash → exige nueva autorización."""
    canon = json.dumps(
        {
            "version": int(version),
            "pasos": [p.get("titulo", "") for p in pasos],
            "coste_maximo": int(coste_maximo),
            "destinatarios": sorted(destinatarios or []),
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResultadoPlan:
    ok: bool
    razon: str
    revision: int | None = None


def _normalizar_pasos(titulos: list[str]) -> list[dict]:
    return [
        {"id": f"p{i+1}", "titulo": t, "estado": "pendiente", "intento": 0, "resultado": ""}
        for i, t in enumerate(titulos)
    ]


async def crear_plan(
    *,
    telefono: str,
    accion_ref: str,
    titulos_pasos: list[str],
    coste_maximo: int,
    version: int = 1,
    autorizacion_id: int | None = None,
    destinatarios: list | None = None,
    job_id: str = "",
) -> PlanTarea:
    """Crea el plan en estado 'preparado' (lo que el usuario confirma)."""
    from sqlalchemy.exc import IntegrityError

    pasos = _normalizar_pasos(titulos_pasos)
    h = hash_plan(version, pasos, coste_maximo, destinatarios)
    plan = PlanTarea(
        telefono=telefono,
        accion_ref=accion_ref[:120],
        autorizacion_id=autorizacion_id,
        version=version,
        hash_plan=h,
        coste_maximo=int(coste_maximo),
        pasos_json=json.dumps(pasos, ensure_ascii=False),
        estado="preparado",
        revision=0,
        job_id=job_id[:120],
        creado=datetime.utcnow(),
        actualizado=datetime.utcnow(),
    )
    async with async_session() as s:
        s.add(plan)
        try:
            await s.commit()
            await s.refresh(plan)
            return plan
        except IntegrityError:
            await s.rollback()
            existente = (await s.execute(
                select(PlanTarea).where(PlanTarea.accion_ref == accion_ref[:120])
            )).scalar_one()
            return existente


async def obtener_plan(telefono: str, plan_id: int) -> dict | None:
    """Devuelve el plan SÓLO si pertenece a `telefono` (ajeno → None)."""
    async with async_session() as s:
        p = (await s.execute(
            select(PlanTarea).where(
                PlanTarea.id == plan_id, PlanTarea.telefono == telefono
            )
        )).scalar_one_or_none()
        return _plan_a_dict(p) if p is not None else None


def _plan_a_dict(p: PlanTarea) -> dict:
    return {
        "id": p.id,
        "telefono": p.telefono,
        "accion_ref": p.accion_ref,
        "version": p.version,
        "hash_plan": p.hash_plan,
        "coste_maximo": p.coste_maximo,
        "estado": p.estado,
        "revision": p.revision,
        "pasos": json.loads(p.pasos_json or "[]"),
    }


def coincide_version(plan: dict, version: int, hash_esperado: str) -> bool:
    """El checklist que se ejecuta debe ser la versión/hash autorizados."""
    return int(plan.get("version", -1)) == int(version) and plan.get("hash_plan") == hash_esperado


async def marcar_paso(
    *,
    plan_id: int,
    paso_id: str,
    estado: str,
    resultado: str = "",
    intento: int | None = None,
    revision_esperada: int,
) -> ResultadoPlan:
    """Actualiza un paso con concurrencia optimista. Un paso terminal no
    regresa; una revisión vieja no pisa una nueva."""
    async with async_session() as s:
        p = (await s.execute(
            select(PlanTarea).where(PlanTarea.id == plan_id)
        )).scalar_one_or_none()
        if p is None:
            return ResultadoPlan(False, "inexistente")
        if int(p.revision) != int(revision_esperada):
            return ResultadoPlan(False, "revision_desactualizada", revision=p.revision)

        pasos = json.loads(p.pasos_json or "[]")
        objetivo = next((x for x in pasos if x.get("id") == paso_id), None)
        if objetivo is None:
            return ResultadoPlan(False, "paso_inexistente", revision=p.revision)

        # No regresar un paso terminal (retry idempotente).
        if objetivo["estado"] in ESTADOS_PASO_TERMINALES and estado not in ESTADOS_PASO_TERMINALES:
            return ResultadoPlan(False, "no_regresa", revision=p.revision)

        objetivo["estado"] = estado
        objetivo["resultado"] = _sanear_resultado(resultado)
        if intento is not None:
            objetivo["intento"] = int(intento)

        res = await s.execute(
            update(PlanTarea)
            .where(PlanTarea.id == plan_id, PlanTarea.revision == revision_esperada)
            .values(
                pasos_json=json.dumps(pasos, ensure_ascii=False),
                revision=PlanTarea.revision + 1,
                actualizado=datetime.utcnow(),
            )
        )
        await s.commit()
        if res.rowcount == 0:
            return ResultadoPlan(False, "revision_desactualizada")
        return ResultadoPlan(True, "ok", revision=revision_esperada + 1)


async def avanzar_estado(
    *, plan_id: int, estado: str, revision_esperada: int
) -> ResultadoPlan:
    """Cambia el estado del plan con concurrencia optimista."""
    if estado not in ESTADOS_PLAN:
        return ResultadoPlan(False, "estado_invalido")
    async with async_session() as s:
        res = await s.execute(
            update(PlanTarea)
            .where(PlanTarea.id == plan_id, PlanTarea.revision == revision_esperada)
            .values(estado=estado, revision=PlanTarea.revision + 1, actualizado=datetime.utcnow())
        )
        await s.commit()
        if res.rowcount == 0:
            return ResultadoPlan(False, "revision_desactualizada")
        return ResultadoPlan(True, "ok", revision=revision_esperada + 1)
