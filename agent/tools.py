# agent/tools.py — Herramientas de Dona (persistentes en PostgreSQL)
# Dona — Migrado a DB en Fase 1 de estabilización

"""
Herramientas de gestión de productividad personal para Dona.
Incluye: tareas, recordatorios, listas y eventos de calendario.
Todas las operaciones se guardan por número de teléfono del usuario.

NOTA: Antes de Fase 1, estos datos se almacenaban en diccionarios en memoria
y se perdían en cada restart. Ahora persisten en PostgreSQL.
"""

import logging
from datetime import datetime

import yaml
from sqlalchemy import delete, select, update

logger = logging.getLogger("dona")


def cargar_info_negocio() -> dict:
    """Carga la configuración de Dona desde business.yaml."""
    try:
        with open("config/business.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_info_dona() -> dict:
    """Retorna información general de Dona y sus capacidades."""
    info = cargar_info_negocio()
    return {
        "nombre": info.get("agente", {}).get("nombre", "Dona"),
        "descripcion": info.get("negocio", {}).get("descripcion", ""),
        "capacidades": info.get("agente", {}).get("casos_de_uso", []),
        "horario": info.get("negocio", {}).get("horario", "24/7"),
    }


# ════════════════════════════════════════════════════════════
# GESTIÓN DE TAREAS
# Dona puede crear, completar, listar y eliminar tareas
# por usuario (identificado por su número de teléfono).
# Persistente en PostgreSQL via SQLAlchemy async.
# ════════════════════════════════════════════════════════════


async def agregar_tarea(telefono: str, descripcion: str, prioridad: str = "normal") -> dict:
    """
    Crea una nueva tarea para el usuario.

    Args:
        telefono: Número del usuario
        descripcion: Descripción de la tarea
        prioridad: "alta", "normal" o "baja"

    Returns:
        La tarea creada con su ID
    """
    from agent.memory import Tarea, async_session

    async with async_session() as session:
        tarea = Tarea(
            telefono=telefono,
            descripcion=descripcion,
            prioridad=prioridad,
        )
        session.add(tarea)
        await session.commit()
        await session.refresh(tarea)

        logger.info(f"Tarea creada para {telefono}: {descripcion}")
        return {
            "id": tarea.id,
            "descripcion": tarea.descripcion,
            "prioridad": tarea.prioridad,
            "completada": tarea.completada,
            "creada": tarea.creada.isoformat() if tarea.creada else datetime.utcnow().isoformat(),
        }


async def completar_tarea(telefono: str, tarea_id: int) -> bool:
    """Marca una tarea como completada. Retorna True si la encontró."""
    from agent.memory import Tarea, async_session

    async with async_session() as session:
        result = await session.execute(
            update(Tarea)
            .where(Tarea.id == tarea_id, Tarea.telefono == telefono)
            .values(completada=True)
        )
        await session.commit()
        return result.rowcount > 0


async def listar_tareas(telefono: str, solo_pendientes: bool = True) -> list[dict]:
    """
    Retorna las tareas del usuario.

    Args:
        telefono: Número del usuario
        solo_pendientes: Si True, filtra las completadas
    """
    from agent.memory import Tarea, async_session

    async with async_session() as session:
        query = select(Tarea).where(Tarea.telefono == telefono)
        if solo_pendientes:
            query = query.where(Tarea.completada == False)
        query = query.order_by(Tarea.creada.desc())
        result = await session.execute(query)
        tareas = result.scalars().all()

        return [
            {
                "id": t.id,
                "descripcion": t.descripcion,
                "prioridad": t.prioridad,
                "completada": t.completada,
                "creada": t.creada.isoformat() if t.creada else "",
            }
            for t in tareas
        ]


async def eliminar_tarea(telefono: str, tarea_id: int) -> bool:
    """Elimina una tarea por ID. Retorna True si la encontró."""
    from agent.memory import Tarea, async_session

    async with async_session() as session:
        result = await session.execute(
            delete(Tarea).where(Tarea.id == tarea_id, Tarea.telefono == telefono)
        )
        await session.commit()
        return result.rowcount > 0


# ════════════════════════════════════════════════════════════
# GESTIÓN DE RECORDATORIOS (tools.py internos)
# Dona guarda recordatorios con fecha/hora y descripción.
# NOTA: Estos son recordatorios simples de tools.py.
# Los recordatorios con scheduler están en memory.py (tabla Recordatorio).
# ════════════════════════════════════════════════════════════

async def agregar_recordatorio(telefono: str, descripcion: str, fecha_hora: str, recurrente: bool = False) -> dict:
    """
    Crea un recordatorio para el usuario.
    Usa la tabla Recordatorio de memory.py para persistencia y scheduling real.
    """
    from agent.memory import Recordatorio, async_session

    fecha_dt = None
    try:
        fecha_dt = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        try:
            fecha_dt = datetime.fromisoformat(fecha_hora)
        except (ValueError, TypeError):
            fecha_dt = datetime.utcnow()

    async with async_session() as session:
        rec = Recordatorio(
            telefono=telefono,
            mensaje=descripcion,
            fecha_hora=fecha_dt,
        )
        session.add(rec)
        await session.commit()
        await session.refresh(rec)

        logger.info(f"Recordatorio creado para {telefono}: {descripcion} a las {fecha_hora}")
        return {
            "id": rec.id,
            "descripcion": descripcion,
            "fecha_hora": fecha_hora,
            "recurrente": recurrente,
            "activo": True,
            "creado": rec.creado.isoformat() if rec.creado else datetime.utcnow().isoformat(),
        }


async def listar_recordatorios(telefono: str) -> list[dict]:
    """Retorna los recordatorios activos del usuario."""
    from agent.memory import Recordatorio, async_session

    async with async_session() as session:
        result = await session.execute(
            select(Recordatorio).where(
                Recordatorio.telefono == telefono,
                Recordatorio.enviado == False,
                Recordatorio.cancelado == False,
            ).order_by(Recordatorio.fecha_hora)
        )
        recs = result.scalars().all()

        return [
            {
                "id": r.id,
                "descripcion": r.mensaje,
                "fecha_hora": r.fecha_hora.isoformat() if r.fecha_hora else "",
                "activo": True,
            }
            for r in recs
        ]


async def cancelar_recordatorio(telefono: str, recordatorio_id: int) -> bool:
    """Cancela un recordatorio por ID. Retorna True si lo encontró."""
    from agent.memory import Recordatorio, async_session

    async with async_session() as session:
        result = await session.execute(
            update(Recordatorio)
            .where(Recordatorio.id == recordatorio_id, Recordatorio.telefono == telefono)
            .values(cancelado=True)
        )
        await session.commit()
        return result.rowcount > 0


# ════════════════════════════════════════════════════════════
# GESTIÓN DE LISTAS
# Dona puede manejar múltiples listas por usuario:
# compras, metas, ideas, libros, películas, etc.
# ════════════════════════════════════════════════════════════

async def agregar_a_lista(telefono: str, nombre_lista: str, item: str) -> dict:
    """
    Agrega un ítem a una lista del usuario (la crea si no existe).

    Args:
        telefono: Número del usuario
        nombre_lista: Nombre de la lista (ej: "compras", "metas")
        item: Elemento a agregar
    """
    from agent.memory import ItemLista, Lista, async_session

    nombre_lista = nombre_lista.lower().strip()

    async with async_session() as session:
        # Buscar o crear la lista
        result = await session.execute(
            select(Lista).where(
                Lista.telefono == telefono,
                Lista.nombre == nombre_lista,
            )
        )
        lista = result.scalar_one_or_none()

        if not lista:
            lista = Lista(telefono=telefono, nombre=nombre_lista)
            session.add(lista)
            await session.flush()

        # Agregar ítem
        elemento = ItemLista(lista_id=lista.id, texto=item)
        session.add(elemento)
        await session.commit()
        await session.refresh(elemento)

        return {
            "id": elemento.id,
            "texto": elemento.texto,
            "completado": elemento.completado,
            "agregado": elemento.agregado.isoformat() if elemento.agregado else datetime.utcnow().isoformat(),
        }


async def ver_lista(telefono: str, nombre_lista: str) -> list[dict]:
    """Retorna todos los ítems de una lista."""
    from agent.memory import ItemLista, Lista, async_session

    nombre_lista = nombre_lista.lower().strip()

    async with async_session() as session:
        result = await session.execute(
            select(Lista).where(
                Lista.telefono == telefono,
                Lista.nombre == nombre_lista,
            )
        )
        lista = result.scalar_one_or_none()
        if not lista:
            return []

        items_result = await session.execute(
            select(ItemLista).where(ItemLista.lista_id == lista.id).order_by(ItemLista.agregado)
        )
        items = items_result.scalars().all()

        return [
            {
                "id": it.id,
                "texto": it.texto,
                "completado": it.completado,
                "agregado": it.agregado.isoformat() if it.agregado else "",
            }
            for it in items
        ]


async def listar_nombres_listas(telefono: str) -> list[str]:
    """Retorna los nombres de todas las listas del usuario."""
    from agent.memory import Lista, async_session

    async with async_session() as session:
        result = await session.execute(
            select(Lista.nombre).where(Lista.telefono == telefono).order_by(Lista.nombre)
        )
        return [row[0] for row in result.all()]


async def tachar_de_lista(telefono: str, nombre_lista: str, item_id: int) -> bool:
    """Marca un ítem de lista como completado."""
    from agent.memory import ItemLista, Lista, async_session

    nombre_lista = nombre_lista.lower().strip()

    async with async_session() as session:
        result = await session.execute(
            select(Lista).where(
                Lista.telefono == telefono,
                Lista.nombre == nombre_lista,
            )
        )
        lista = result.scalar_one_or_none()
        if not lista:
            return False

        up_result = await session.execute(
            update(ItemLista)
            .where(ItemLista.id == item_id, ItemLista.lista_id == lista.id)
            .values(completado=True)
        )
        await session.commit()
        return up_result.rowcount > 0


# ════════════════════════════════════════════════════════════
# GESTIÓN DE CALENDARIO Y EVENTOS
# Dona puede agendar, listar y cancelar eventos.
# ════════════════════════════════════════════════════════════

async def agendar_evento(telefono: str, titulo: str, fecha_hora: str, descripcion: str = "") -> dict:
    """
    Agrega un evento al calendario del usuario.

    Args:
        telefono: Número del usuario
        titulo: Nombre del evento
        fecha_hora: Cuándo ocurre (ej: "2026-03-20 15:00")
        descripcion: Detalles adicionales opcionales
    """
    from agent.memory import EventoUsuario, async_session

    async with async_session() as session:
        evento = EventoUsuario(
            telefono=telefono,
            titulo=titulo,
            fecha_hora=fecha_hora,
            descripcion=descripcion,
        )
        session.add(evento)
        await session.commit()
        await session.refresh(evento)

        logger.info(f"Evento agendado para {telefono}: {titulo} el {fecha_hora}")
        return {
            "id": evento.id,
            "titulo": evento.titulo,
            "fecha_hora": evento.fecha_hora,
            "descripcion": evento.descripcion,
            "cancelado": evento.cancelado,
            "creado": evento.creado.isoformat() if evento.creado else datetime.utcnow().isoformat(),
        }


async def listar_eventos(telefono: str, fecha_filtro: str = None) -> list[dict]:
    """
    Retorna los eventos del usuario.

    Args:
        telefono: Número del usuario
        fecha_filtro: Si se proporciona, filtra por esa fecha (ej: "2026-03-20")
    """
    from agent.memory import EventoUsuario, async_session

    async with async_session() as session:
        query = select(EventoUsuario).where(
            EventoUsuario.telefono == telefono,
            EventoUsuario.cancelado == False,
        )
        if fecha_filtro:
            query = query.where(EventoUsuario.fecha_hora.startswith(fecha_filtro))
        query = query.order_by(EventoUsuario.fecha_hora)
        result = await session.execute(query)
        eventos = result.scalars().all()

        return [
            {
                "id": e.id,
                "titulo": e.titulo,
                "fecha_hora": e.fecha_hora,
                "descripcion": e.descripcion,
                "cancelado": e.cancelado,
                "creado": e.creado.isoformat() if e.creado else "",
            }
            for e in eventos
        ]


async def cancelar_evento(telefono: str, evento_id: int) -> bool:
    """Cancela un evento por ID. Retorna True si lo encontró."""
    from agent.memory import EventoUsuario, async_session

    async with async_session() as session:
        result = await session.execute(
            update(EventoUsuario)
            .where(EventoUsuario.id == evento_id, EventoUsuario.telefono == telefono)
            .values(cancelado=True)
        )
        await session.commit()
        return result.rowcount > 0
