# agent/app_first/api.py — API interna de Dona app-first (J7.4)

"""
``POST /internal/app/{accion}`` — bridge firmado landing → backend.

Contrato:
  - Cuerpo JSON firmado con ``X-Internal-Signature`` = HMAC-SHA256 del body
    con ``INTERNAL_BRIDGE_SECRET`` (el mismo bridge que ya usa la landing).
  - Identidad: ``usuario_id`` lo pone la landing desde SU sesión de servidor
    (nunca del navegador) y viaja firmado. El workspace se valida aquí por
    membresía (``resolver_contexto``): un workspace ajeno es 404.
  - Errores de dominio → 400 / 403 / 404 / 409. Sin trazas ni datos internos.

Puertas (todas apagadas por defecto):
  - ``DONA_APP_PILOTO_ENABLED=true`` habilita la API (si no: 404, como si no
    existiera). La web pública sigue en pausa; esto es solo el piloto.
  - Registro solo por invitación: el email debe estar en
    ``DONA_APP_INVITADOS`` (lista separada por comas). Lista vacía = cerrado.
  - Login con lockout persistente (agent/dashboard_lockout.py, contadores
    propios con prefijo ``app:``).

La UI que consume esta API es J7.5 (landing ``/app``).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agent.app_first import ejecucion as run
from agent.app_first import repositorio as repo

logger = logging.getLogger("dona")

router = APIRouter(prefix="/internal/app")

AGENTES_INICIALES = (
    # (nombre, rol, herramientas, presupuesto en unidades simuladas)
    ("Responsable", "responsable", [], 50),
    ("Ejecutor", "ejecutor", ["redactar", "resumir", "publicar_resultado"], 50),
)


def piloto_habilitado() -> bool:
    return os.getenv("DONA_APP_PILOTO_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def _invitados() -> set[str]:
    crudo = os.getenv("DONA_APP_INVITADOS", "")
    return {e.strip().lower() for e in crudo.split(",") if e.strip()}


class _ErrorPeticion(Exception):
    def __init__(self, status: int, codigo: str):
        self.status, self.codigo = status, codigo


def _entero(payload: dict, campo: str) -> int:
    valor = payload.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise _ErrorPeticion(400, f"{campo}_invalido")
    return valor


def _texto(payload: dict, campo: str, obligatorio: bool = True) -> str:
    valor = payload.get(campo, "")
    if not isinstance(valor, str):
        raise _ErrorPeticion(400, f"{campo}_invalido")
    if obligatorio and not valor.strip():
        raise _ErrorPeticion(400, f"falta_{campo}")
    return valor


async def _ctx(payload: dict) -> repo.Contexto:
    return await repo.resolver_contexto(_entero(payload, "usuario_id"), _entero(payload, "workspace_id"))


# ── Acceso ──────────────────────────────────────────────────────────────


async def _registro(p: dict) -> dict:
    email = _texto(p, "email").strip().lower()
    if email not in _invitados():
        # Mismo error para "no invitado" y "registro cerrado".
        raise _ErrorPeticion(403, "registro_solo_por_invitacion")
    uid = await repo.crear_usuario(email, _texto(p, "password"), _texto(p, "nombre", False))
    ws = await repo.crear_workspace(uid, _texto(p, "nombre_workspace", False).strip() or "Mi espacio")
    ctx = await repo.resolver_contexto(uid, ws)
    area = await repo.crear_area(ctx, "General", "Área inicial; renómbrala o crea otras.")
    for nombre, rol, herramientas, presupuesto in AGENTES_INICIALES:
        await repo.crear_agente(ctx, nombre, rol, herramientas_permitidas=herramientas,
                                presupuesto_max_unidades=presupuesto)
    return {"usuario_id": uid, "workspace_id": ws, "area_id": area}


async def _verificar(p: dict) -> dict:
    from agent.dashboard_lockout import registrar_resultado, verificar_lockout

    email = _texto(p, "email").strip().lower()
    clave_lockout = f"app:{email}"
    estado = await verificar_lockout(clave_lockout)
    if estado["bloqueado"]:
        raise _ErrorPeticion(429, "demasiados_intentos")
    uid = await repo.verificar_credenciales(email, _texto(p, "password"))
    await registrar_resultado(clave_lockout, uid is not None)
    if uid is None:
        raise _ErrorPeticion(401, "credenciales_invalidas")
    return {"usuario_id": uid, "workspaces": await repo.listar_workspaces(uid)}


# ── Trabajo ─────────────────────────────────────────────────────────────


async def _workspaces(p: dict) -> dict:
    return {"workspaces": await repo.listar_workspaces(_entero(p, "usuario_id"))}


async def _inicio(p: dict) -> dict:
    ctx = await _ctx(p)
    return {
        "areas": await repo.listar_areas(ctx),
        "proyectos": await repo.listar_proyectos(ctx),
        "aprobaciones_pendientes": await run.listar_aprobaciones(ctx),
        "actividad": await repo.listar_actividad(ctx, 20),
    }


async def _area_crear(p: dict) -> dict:
    ctx = await _ctx(p)
    return {"id": await repo.crear_area(ctx, _texto(p, "nombre"), _texto(p, "descripcion", False))}


async def _proyecto_crear(p: dict) -> dict:
    ctx = await _ctx(p)
    criterios = p.get("criterios_aceptacion")
    if not isinstance(criterios, list) or not all(isinstance(c, str) for c in criterios):
        raise _ErrorPeticion(400, "criterios_aceptacion_invalido")
    return {"id": await repo.crear_proyecto(
        ctx, _entero(p, "area_id"), _texto(p, "nombre"), _texto(p, "objetivo"), criterios)}


async def _proyecto(p: dict) -> dict:
    ctx = await _ctx(p)
    pid = _entero(p, "proyecto_id")
    return {
        "proyecto": await repo.obtener_proyecto(ctx, pid),
        "tareas": await repo.listar_tareas(ctx, pid),
        "mensajes": await repo.listar_mensajes(ctx, pid),
    }


async def _agentes(p: dict) -> dict:
    return {"agentes": await repo.listar_agentes(await _ctx(p))}


async def _tarea_crear(p: dict) -> dict:
    ctx = await _ctx(p)
    agente = p.get("agente_id")
    agente_id = _entero(p, "agente_id") if agente is not None else None
    tid = await repo.crear_tarea(ctx, _entero(p, "proyecto_id"), _texto(p, "titulo"),
                                 _texto(p, "descripcion", False), agente_id)
    return {"id": tid}


async def _tarea(p: dict) -> dict:
    ctx = await _ctx(p)
    tid = _entero(p, "tarea_id")
    return {
        "tarea": await repo.obtener_tarea(ctx, tid),
        "ejecuciones": await run.listar_ejecuciones(ctx, tid),
        "evidencias": await run.listar_evidencias(ctx, tid),
    }


async def _tarea_ejecutar(p: dict) -> dict:
    ctx = await _ctx(p)
    return {"ejecucion_id": await run.encolar_tarea(ctx, _entero(p, "tarea_id"))}


async def _tarea_cancelar(p: dict) -> dict:
    await run.cancelar_tarea(await _ctx(p), _entero(p, "tarea_id"))
    return {"ok": True}


async def _tarea_reintentar(p: dict) -> dict:
    ctx = await _ctx(p)
    return {"ejecucion_id": await run.reintentar_tarea(ctx, _entero(p, "tarea_id"))}


async def _aprobacion_decidir(p: dict) -> dict:
    ctx = await _ctx(p)
    aprobar = p.get("aprobar")
    if not isinstance(aprobar, bool):
        raise _ErrorPeticion(400, "aprobar_invalido")
    return {"estado": await run.decidir_aprobacion(ctx, _entero(p, "aprobacion_id"), aprobar)}


async def _mensaje_crear(p: dict) -> dict:
    ctx = await _ctx(p)
    tarea = p.get("tarea_id")
    return {"id": await repo.agregar_mensaje(
        ctx, _entero(p, "proyecto_id"), _texto(p, "contenido"),
        _entero(p, "tarea_id") if tarea is not None else None)}


ACCIONES: dict[str, Callable[[dict], Awaitable[dict]]] = {
    "auth.registro": _registro,
    "auth.verificar": _verificar,
    "workspaces": _workspaces,
    "inicio": _inicio,
    "area.crear": _area_crear,
    "proyecto.crear": _proyecto_crear,
    "proyecto": _proyecto,
    "agentes": _agentes,
    "tarea.crear": _tarea_crear,
    "tarea": _tarea,
    "tarea.ejecutar": _tarea_ejecutar,
    "tarea.cancelar": _tarea_cancelar,
    "tarea.reintentar": _tarea_reintentar,
    "aprobacion.decidir": _aprobacion_decidir,
    "mensaje.crear": _mensaje_crear,
}


def _json(status: int, cuerpo: dict[str, Any]) -> JSONResponse:
    return JSONResponse(cuerpo, status_code=status, headers={"Cache-Control": "no-store"})


@router.post("/{accion}")
async def internal_app(accion: str, request: Request) -> JSONResponse:
    if not piloto_habilitado():
        return _json(404, {"error": "not_found"})
    manejador = ACCIONES.get(accion)
    if manejador is None:
        return _json(404, {"error": "accion_desconocida"})

    from agent.main import _verificar_firma_interna  # import diferido: main incluye este router

    body = await request.body()
    if not _verificar_firma_interna(body, request.headers.get("X-Internal-Signature", "")):
        return _json(401, {"error": "signature_invalid"})
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _json(400, {"error": "json_invalid"})
    if not isinstance(payload, dict):
        return _json(400, {"error": "json_not_object"})

    try:
        return _json(200, await manejador(payload))
    except _ErrorPeticion as e:
        return _json(e.status, {"error": e.codigo})
    except repo.ErrorAppFirst as e:
        # El mensaje de dominio es seguro (sin PII ni internos) y ayuda a la UI.
        return _json(e.status, {"error": e.codigo, "detalle": str(e)[:200]})
    except Exception:
        logger.exception(f"[APP-FIRST] /internal/app/{accion} falló")
        return _json(500, {"error": "error_interno"})
