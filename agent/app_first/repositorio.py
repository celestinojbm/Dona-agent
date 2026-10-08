# agent/app_first/repositorio.py — Acceso a datos de Dona app-first (J7.1)

"""
Única puerta a las tablas ``app_*``. Reglas que aplica en el servidor:

  - Aislamiento: toda operación sobre datos de un workspace recibe un
    ``Contexto`` resuelto con ``resolver_contexto(usuario_id, workspace_id)``,
    que exige membresía. Cada consulta filtra por ``ctx.workspace_id``: un id
    de otro workspace lanza ``NoEncontrado`` (la API lo convierte en 404, no
    en 403, para no revelar que existe).
  - Permisos: gestionar agentes y áreas exige rol owner/admin
    (``SinPermiso``).
  - Valores cerrados: roles, estados y motivos fuera de los conjuntos de
    ``models.py`` lanzan ``ValorInvalido``.
  - Actividad: cada cambio relevante deja una fila en ``app_actividad``,
    con los datos pasados por ``automation.audit.sanitizar_payload``.

Contraseñas: scrypt de la biblioteca estándar (sin dependencias nuevas),
comparación en tiempo constante.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select

from agent.app_first import models as m


class ErrorAppFirst(Exception):
    """Base de los errores de dominio de app-first. `status`/`codigo` son
    los que la API devuelve (agent/app_first/api.py)."""

    status = 400
    codigo = "error"


class NoEncontrado(ErrorAppFirst):
    """El objeto no existe o pertenece a otro workspace (→ 404)."""

    status, codigo = 404, "no_encontrado"


class SinPermiso(ErrorAppFirst):
    """El usuario es miembro pero su rol no permite la operación (→ 403)."""

    status, codigo = 403, "sin_permiso"


class ValorInvalido(ErrorAppFirst):
    """Valor fuera de un conjunto cerrado o dato obligatorio vacío (→ 400)."""

    status, codigo = 400, "valor_invalido"


class Conflicto(ErrorAppFirst):
    """Choca con un dato existente (p. ej. email ya registrado) (→ 409)."""

    status, codigo = 409, "conflicto"


@dataclass(frozen=True)
class Contexto:
    """Quién actúa y en qué workspace. Se construye SOLO en el servidor."""

    usuario_id: int
    workspace_id: int
    rol: str

    @property
    def es_admin(self) -> bool:
        return self.rol in ("owner", "admin")


def _sesion():
    # Import diferido: los tests recargan agent.memory con otra DATABASE_URL.
    from agent.memory import async_session

    return async_session()


def _exigir(valor: str, permitidos: tuple[str, ...], campo: str) -> str:
    if valor not in permitidos:
        raise ValorInvalido(f"{campo} inválido: {valor!r}")
    return valor


def _texto(valor: str | None, campo: str, maximo: int) -> str:
    limpio = (valor or "").strip()
    if not limpio:
        raise ValorInvalido(f"{campo} es obligatorio")
    if len(limpio) > maximo:
        raise ValorInvalido(f"{campo} supera {maximo} caracteres")
    return limpio


# ── Contraseñas ─────────────────────────────────────────────────────────

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    if len(password or "") < 10:
        raise ValorInvalido("la contraseña debe tener al menos 10 caracteres")
    sal = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=sal, dklen=32, **_SCRYPT)
    b64 = base64.b64encode
    return "scrypt${n}${r}${p}${sal}${dk}".format(
        **_SCRYPT, sal=b64(sal).decode(), dk=b64(dk).decode()
    )


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        algo, n, r, p, sal, dk = almacenado.split("$")
        if algo != "scrypt":
            return False
        calculado = hashlib.scrypt(
            (password or "").encode("utf-8"),
            salt=base64.b64decode(sal),
            dklen=32,
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return hmac.compare_digest(calculado, base64.b64decode(dk))
    except Exception:
        return False


def _normalizar_email(email: str) -> str:
    limpio = (email or "").strip().lower()
    if "@" not in limpio or len(limpio) > 320 or limpio.startswith("@") or limpio.endswith("@"):
        raise ValorInvalido("email inválido")
    return limpio


# ── Actividad ───────────────────────────────────────────────────────────


def _actividad(
    session,
    workspace_id: int,
    actor_tipo: str,
    actor_id: int | None,
    evento: str,
    objeto_tipo: str = "",
    objeto_id: int | None = None,
    datos: dict[str, Any] | None = None,
) -> None:
    from agent.automation.audit import sanitizar_payload

    session.add(
        m.AppActividad(
            workspace_id=workspace_id,
            actor_tipo=_exigir(actor_tipo, m.TIPOS_ACTOR, "actor_tipo"),
            actor_id=actor_id,
            evento=evento,
            objeto_tipo=objeto_tipo,
            objeto_id=objeto_id,
            datos_json=json.dumps(sanitizar_payload(datos or {}), ensure_ascii=False),
        )
    )


# ── Usuarios y workspaces ───────────────────────────────────────────────


async def crear_usuario(email: str, password: str, nombre: str = "") -> int:
    email_n = _normalizar_email(email)
    hashed = hash_password(password)
    async with _sesion() as session:
        existe = await session.scalar(select(m.AppUsuario.id).where(m.AppUsuario.email == email_n))
        if existe:
            raise Conflicto("ya existe una cuenta con ese email")
        usuario = m.AppUsuario(email=email_n, password_hash=hashed, nombre=(nombre or "").strip()[:120])
        session.add(usuario)
        await session.commit()
        return usuario.id


async def verificar_credenciales(email: str, password: str) -> int | None:
    """id del usuario si email y contraseña son correctos y la cuenta está
    activa; si no, None (sin distinguir el motivo)."""
    try:
        email_n = _normalizar_email(email)
    except ValorInvalido:
        return None
    async with _sesion() as session:
        usuario = await session.scalar(select(m.AppUsuario).where(m.AppUsuario.email == email_n))
    if usuario is None or usuario.desactivado:
        # Mismo coste que un intento real: no revela si el email existe.
        verificar_password(password, hash_password("x" * 16))
        return None
    return usuario.id if verificar_password(password, usuario.password_hash) else None


async def crear_workspace(usuario_id: int, nombre: str) -> int:
    """Crea el workspace y deja al creador como owner."""
    nombre_l = _texto(nombre, "nombre", 120)
    async with _sesion() as session:
        if await session.get(m.AppUsuario, usuario_id) is None:
            raise NoEncontrado("usuario")
        ws = m.AppWorkspace(nombre=nombre_l, creado_por=usuario_id)
        session.add(ws)
        await session.flush()
        session.add(m.AppMembresia(workspace_id=ws.id, usuario_id=usuario_id, rol="owner"))
        _actividad(session, ws.id, "usuario", usuario_id, "workspace_creado", "workspace", ws.id)
        await session.commit()
        return ws.id


async def listar_workspaces(usuario_id: int) -> list[dict[str, Any]]:
    async with _sesion() as session:
        filas = (
            await session.execute(
                select(m.AppWorkspace, m.AppMembresia.rol)
                .join(m.AppMembresia, m.AppMembresia.workspace_id == m.AppWorkspace.id)
                .where(m.AppMembresia.usuario_id == usuario_id)
                .order_by(m.AppWorkspace.id)
            )
        ).all()
    return [{"id": ws.id, "nombre": ws.nombre, "rol": rol} for ws, rol in filas]


async def resolver_contexto(usuario_id: int, workspace_id: int) -> Contexto:
    """Contexto de trabajo si el usuario es miembro; si no, NoEncontrado."""
    async with _sesion() as session:
        mem = await session.get(m.AppMembresia, (workspace_id, usuario_id))
        usuario = await session.get(m.AppUsuario, usuario_id)
    if mem is None or usuario is None or usuario.desactivado:
        raise NoEncontrado("workspace")
    return Contexto(usuario_id=usuario_id, workspace_id=workspace_id, rol=mem.rol)


async def agregar_miembro(ctx: Contexto, usuario_id: int, rol: str = "miembro") -> None:
    if not ctx.es_admin:
        raise SinPermiso("solo owner/admin agregan miembros")
    _exigir(rol, m.ROLES_MIEMBRO, "rol")
    if rol == "owner":
        raise ValorInvalido("no se asigna owner al agregar")
    async with _sesion() as session:
        if await session.get(m.AppUsuario, usuario_id) is None:
            raise NoEncontrado("usuario")
        if await session.get(m.AppMembresia, (ctx.workspace_id, usuario_id)) is not None:
            raise Conflicto("ya es miembro")
        session.add(m.AppMembresia(workspace_id=ctx.workspace_id, usuario_id=usuario_id, rol=rol))
        _actividad(session, ctx.workspace_id, "usuario", ctx.usuario_id, "miembro_agregado",
                   "usuario", usuario_id, {"rol": rol})
        await session.commit()


# ── Lectura por workspace (helper central de aislamiento) ───────────────


async def _del_workspace(session, modelo, objeto_id: int, ctx: Contexto):
    obj = await session.get(modelo, objeto_id)
    if obj is None or obj.workspace_id != ctx.workspace_id:
        raise NoEncontrado(modelo.__tablename__)
    return obj


# ── Áreas ───────────────────────────────────────────────────────────────


async def crear_area(ctx: Contexto, nombre: str, descripcion: str = "") -> int:
    if not ctx.es_admin:
        raise SinPermiso("solo owner/admin crean áreas")
    async with _sesion() as session:
        area = m.AppArea(workspace_id=ctx.workspace_id, nombre=_texto(nombre, "nombre", 120),
                         descripcion=(descripcion or "").strip())
        session.add(area)
        await session.flush()
        _actividad(session, ctx.workspace_id, "usuario", ctx.usuario_id, "area_creada", "area", area.id)
        await session.commit()
        return area.id


async def listar_areas(ctx: Contexto) -> list[dict[str, Any]]:
    async with _sesion() as session:
        filas = (await session.scalars(
            select(m.AppArea).where(m.AppArea.workspace_id == ctx.workspace_id).order_by(m.AppArea.id)
        )).all()
    return [{"id": a.id, "nombre": a.nombre, "descripcion": a.descripcion} for a in filas]


# ── Proyectos ───────────────────────────────────────────────────────────


def _proyecto_a_dict(p: m.AppProyecto) -> dict[str, Any]:
    return {
        "id": p.id,
        "area_id": p.area_id,
        "nombre": p.nombre,
        "objetivo": p.objetivo,
        "criterios_aceptacion": json.loads(p.criterios_aceptacion_json or "[]"),
        "responsable_usuario_id": p.responsable_usuario_id,
        "estado": p.estado,
        "creado": p.creado.isoformat() if p.creado else None,
    }


async def crear_proyecto(
    ctx: Contexto,
    area_id: int,
    nombre: str,
    objetivo: str,
    criterios_aceptacion: list[str],
    responsable_usuario_id: int | None = None,
) -> int:
    criterios = [c.strip() for c in (criterios_aceptacion or []) if c and c.strip()]
    if not criterios:
        raise ValorInvalido("el proyecto necesita al menos un criterio de aceptación")
    responsable = responsable_usuario_id or ctx.usuario_id
    async with _sesion() as session:
        await _del_workspace(session, m.AppArea, area_id, ctx)
        if await session.get(m.AppMembresia, (ctx.workspace_id, responsable)) is None:
            raise ValorInvalido("el responsable debe ser miembro del workspace")
        proyecto = m.AppProyecto(
            workspace_id=ctx.workspace_id,
            area_id=area_id,
            nombre=_texto(nombre, "nombre", 160),
            objetivo=_texto(objetivo, "objetivo", 4000),
            criterios_aceptacion_json=json.dumps(criterios, ensure_ascii=False),
            responsable_usuario_id=responsable,
        )
        session.add(proyecto)
        await session.flush()
        _actividad(session, ctx.workspace_id, "usuario", ctx.usuario_id, "proyecto_creado",
                   "proyecto", proyecto.id)
        await session.commit()
        return proyecto.id


async def obtener_proyecto(ctx: Contexto, proyecto_id: int) -> dict[str, Any]:
    async with _sesion() as session:
        return _proyecto_a_dict(await _del_workspace(session, m.AppProyecto, proyecto_id, ctx))


async def listar_proyectos(ctx: Contexto, area_id: int | None = None) -> list[dict[str, Any]]:
    consulta = select(m.AppProyecto).where(m.AppProyecto.workspace_id == ctx.workspace_id)
    if area_id is not None:
        consulta = consulta.where(m.AppProyecto.area_id == area_id)
    async with _sesion() as session:
        filas = (await session.scalars(consulta.order_by(m.AppProyecto.id))).all()
    return [_proyecto_a_dict(p) for p in filas]


# ── Agentes ─────────────────────────────────────────────────────────────


def _agente_a_dict(a: m.AppAgente) -> dict[str, Any]:
    return {
        "id": a.id,
        "nombre": a.nombre,
        "rol": a.rol,
        "instrucciones": a.instrucciones,
        "herramientas_permitidas": json.loads(a.herramientas_permitidas_json or "[]"),
        "modelo": a.modelo,
        "presupuesto_max_unidades": a.presupuesto_max_unidades,
    }


async def crear_agente(
    ctx: Contexto,
    nombre: str,
    rol: str,
    instrucciones: str = "",
    herramientas_permitidas: list[str] | None = None,
    presupuesto_max_unidades: int = 0,
    modelo: str = "simulado",
) -> int:
    if not ctx.es_admin:
        raise SinPermiso("solo owner/admin definen agentes")
    _exigir(rol, m.ROLES_AGENTE, "rol")
    if presupuesto_max_unidades < 0:
        raise ValorInvalido("presupuesto negativo")
    async with _sesion() as session:
        agente = m.AppAgente(
            workspace_id=ctx.workspace_id,
            nombre=_texto(nombre, "nombre", 120),
            rol=rol,
            instrucciones=(instrucciones or "").strip(),
            herramientas_permitidas_json=json.dumps(sorted(set(herramientas_permitidas or []))),
            modelo=_texto(modelo, "modelo", 80),
            presupuesto_max_unidades=presupuesto_max_unidades,
        )
        session.add(agente)
        await session.flush()
        _actividad(session, ctx.workspace_id, "usuario", ctx.usuario_id, "agente_creado",
                   "agente", agente.id, {"rol": rol})
        await session.commit()
        return agente.id


async def listar_agentes(ctx: Contexto) -> list[dict[str, Any]]:
    async with _sesion() as session:
        filas = (await session.scalars(
            select(m.AppAgente).where(m.AppAgente.workspace_id == ctx.workspace_id).order_by(m.AppAgente.id)
        )).all()
    return [_agente_a_dict(a) for a in filas]


async def obtener_agente(ctx: Contexto, agente_id: int) -> dict[str, Any]:
    async with _sesion() as session:
        return _agente_a_dict(await _del_workspace(session, m.AppAgente, agente_id, ctx))


# ── Tareas ──────────────────────────────────────────────────────────────

# Transiciones permitidas (origen → destinos). El runner (J7.2) y la API
# solo cambian estados por aquí.
TRANSICIONES_TAREA: dict[str, tuple[str, ...]] = {
    "pendiente": ("en_ejecucion", "cancelada"),
    "en_ejecucion": ("necesita_aprobacion", "bloqueada", "completada", "fallida", "cancelada", "pendiente"),
    "necesita_aprobacion": ("en_ejecucion", "bloqueada", "cancelada"),
    "bloqueada": ("pendiente", "cancelada"),
    "fallida": ("pendiente",),  # reintento explícito
    "completada": (),
    "cancelada": (),
}


def _tarea_a_dict(t: m.AppTarea) -> dict[str, Any]:
    return {
        "id": t.id,
        "proyecto_id": t.proyecto_id,
        "titulo": t.titulo,
        "descripcion": t.descripcion,
        "asignada_a_agente_id": t.asignada_a_agente_id,
        "estado": t.estado,
        "motivo_bloqueo": t.motivo_bloqueo,
        "creado": t.creado.isoformat() if t.creado else None,
        "actualizado": t.actualizado.isoformat() if t.actualizado else None,
    }


async def crear_tarea(
    ctx: Contexto,
    proyecto_id: int,
    titulo: str,
    descripcion: str = "",
    agente_id: int | None = None,
) -> int:
    async with _sesion() as session:
        proyecto = await _del_workspace(session, m.AppProyecto, proyecto_id, ctx)
        if proyecto.estado != "activo":
            raise ValorInvalido("el proyecto no está activo")
        if agente_id is not None:
            await _del_workspace(session, m.AppAgente, agente_id, ctx)
        tarea = m.AppTarea(
            workspace_id=ctx.workspace_id,
            proyecto_id=proyecto_id,
            titulo=_texto(titulo, "titulo", 200),
            descripcion=(descripcion or "").strip(),
            asignada_a_agente_id=agente_id,
            creada_por=ctx.usuario_id,
        )
        session.add(tarea)
        await session.flush()
        _actividad(session, ctx.workspace_id, "usuario", ctx.usuario_id, "tarea_creada", "tarea", tarea.id)
        await session.commit()
        return tarea.id


async def obtener_tarea(ctx: Contexto, tarea_id: int) -> dict[str, Any]:
    async with _sesion() as session:
        return _tarea_a_dict(await _del_workspace(session, m.AppTarea, tarea_id, ctx))


async def listar_tareas(ctx: Contexto, proyecto_id: int) -> list[dict[str, Any]]:
    async with _sesion() as session:
        await _del_workspace(session, m.AppProyecto, proyecto_id, ctx)
        filas = (await session.scalars(
            select(m.AppTarea)
            .where(m.AppTarea.workspace_id == ctx.workspace_id, m.AppTarea.proyecto_id == proyecto_id)
            .order_by(m.AppTarea.id)
        )).all()
    return [_tarea_a_dict(t) for t in filas]


async def cambiar_estado_tarea(
    ctx: Contexto,
    tarea_id: int,
    nuevo_estado: str,
    motivo_bloqueo: str = "",
    actor_tipo: str = "usuario",
    actor_id: int | None = None,
) -> dict[str, Any]:
    _exigir(nuevo_estado, m.ESTADOS_TAREA, "estado")
    if nuevo_estado == "bloqueada":
        _exigir(motivo_bloqueo, m.MOTIVOS_BLOQUEO, "motivo_bloqueo")
    elif motivo_bloqueo:
        raise ValorInvalido("motivo_bloqueo solo aplica a estado bloqueada")
    async with _sesion() as session:
        tarea = await _del_workspace(session, m.AppTarea, tarea_id, ctx)
        if nuevo_estado not in TRANSICIONES_TAREA[tarea.estado]:
            raise ValorInvalido(f"transición no permitida: {tarea.estado} → {nuevo_estado}")
        anterior = tarea.estado
        tarea.estado = nuevo_estado
        tarea.motivo_bloqueo = motivo_bloqueo
        tarea.actualizado = datetime.utcnow()
        _actividad(
            session, ctx.workspace_id, actor_tipo,
            actor_id if actor_id is not None else ctx.usuario_id,
            "tarea_estado", "tarea", tarea.id,
            {"de": anterior, "a": nuevo_estado, "motivo_bloqueo": motivo_bloqueo},
        )
        await session.commit()
        return _tarea_a_dict(tarea)


# ── Chat del proyecto y actividad ───────────────────────────────────────


async def agregar_mensaje(
    ctx: Contexto, proyecto_id: int, contenido: str, tarea_id: int | None = None
) -> int:
    async with _sesion() as session:
        await _del_workspace(session, m.AppProyecto, proyecto_id, ctx)
        if tarea_id is not None:
            tarea = await _del_workspace(session, m.AppTarea, tarea_id, ctx)
            if tarea.proyecto_id != proyecto_id:
                raise NoEncontrado("app_tareas")
        msg = m.AppMensajeProyecto(
            workspace_id=ctx.workspace_id,
            proyecto_id=proyecto_id,
            tarea_id=tarea_id,
            autor_tipo="usuario",
            autor_id=ctx.usuario_id,
            contenido=_texto(contenido, "contenido", 8000),
        )
        session.add(msg)
        await session.commit()
        return msg.id


async def listar_mensajes(ctx: Contexto, proyecto_id: int, limite: int = 100) -> list[dict[str, Any]]:
    async with _sesion() as session:
        await _del_workspace(session, m.AppProyecto, proyecto_id, ctx)
        filas = (await session.scalars(
            select(m.AppMensajeProyecto)
            .where(
                m.AppMensajeProyecto.workspace_id == ctx.workspace_id,
                m.AppMensajeProyecto.proyecto_id == proyecto_id,
            )
            .order_by(m.AppMensajeProyecto.id.desc())
            .limit(max(1, min(limite, 500)))
        )).all()
    return [
        {"id": x.id, "tarea_id": x.tarea_id, "autor_tipo": x.autor_tipo, "autor_id": x.autor_id,
         "contenido": x.contenido, "creado": x.creado.isoformat() if x.creado else None}
        for x in reversed(filas)
    ]


async def listar_actividad(ctx: Contexto, limite: int = 50) -> list[dict[str, Any]]:
    async with _sesion() as session:
        filas = (await session.scalars(
            select(m.AppActividad)
            .where(m.AppActividad.workspace_id == ctx.workspace_id)
            .order_by(m.AppActividad.id.desc())
            .limit(max(1, min(limite, 200)))
        )).all()
    return [
        {"id": a.id, "actor_tipo": a.actor_tipo, "actor_id": a.actor_id, "evento": a.evento,
         "objeto_tipo": a.objeto_tipo, "objeto_id": a.objeto_id,
         "datos": json.loads(a.datos_json or "{}"),
         "creado": a.creado.isoformat() if a.creado else None}
        for a in filas
    ]
