# agent/tools.py — Herramientas de Dona
# Generado por AgentKit

"""
Herramientas de gestión de productividad personal para Dona.
Incluye: tareas, recordatorios, listas y eventos de calendario.
Todas las operaciones se guardan por número de teléfono del usuario.
"""

import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    """Carga la configuración de Dona desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
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
# ════════════════════════════════════════════════════════════

# Almacenamiento en memoria (en producción usar base de datos)
_tareas: dict[str, list[dict]] = {}
_listas: dict[str, dict[str, list[dict]]] = {}
_recordatorios: dict[str, list[dict]] = {}
_eventos: dict[str, list[dict]] = {}


def agregar_tarea(telefono: str, descripcion: str, prioridad: str = "normal") -> dict:
    """
    Crea una nueva tarea para el usuario.

    Args:
        telefono: Número del usuario
        descripcion: Descripción de la tarea
        prioridad: "alta", "normal" o "baja"

    Returns:
        La tarea creada con su ID
    """
    if telefono not in _tareas:
        _tareas[telefono] = []

    tarea = {
        "id": len(_tareas[telefono]) + 1,
        "descripcion": descripcion,
        "prioridad": prioridad,
        "completada": False,
        "creada": datetime.utcnow().isoformat(),
    }
    _tareas[telefono].append(tarea)
    logger.info(f"Tarea creada para {telefono}: {descripcion}")
    return tarea


def completar_tarea(telefono: str, tarea_id: int) -> bool:
    """Marca una tarea como completada. Retorna True si la encontró."""
    for tarea in _tareas.get(telefono, []):
        if tarea["id"] == tarea_id:
            tarea["completada"] = True
            return True
    return False


def listar_tareas(telefono: str, solo_pendientes: bool = True) -> list[dict]:
    """
    Retorna las tareas del usuario.

    Args:
        telefono: Número del usuario
        solo_pendientes: Si True, filtra las completadas
    """
    tareas = _tareas.get(telefono, [])
    if solo_pendientes:
        return [t for t in tareas if not t["completada"]]
    return tareas


def eliminar_tarea(telefono: str, tarea_id: int) -> bool:
    """Elimina una tarea por ID. Retorna True si la encontró."""
    tareas = _tareas.get(telefono, [])
    antes = len(tareas)
    _tareas[telefono] = [t for t in tareas if t["id"] != tarea_id]
    return len(_tareas[telefono]) < antes


# ════════════════════════════════════════════════════════════
# GESTIÓN DE RECORDATORIOS
# Dona guarda recordatorios con fecha/hora y descripción.
# ════════════════════════════════════════════════════════════

def agregar_recordatorio(telefono: str, descripcion: str, fecha_hora: str, recurrente: bool = False) -> dict:
    """
    Crea un recordatorio para el usuario.

    Args:
        telefono: Número del usuario
        descripcion: Qué recordar
        fecha_hora: Cuándo (ej: "2026-03-19 20:00")
        recurrente: Si el recordatorio se repite
    """
    if telefono not in _recordatorios:
        _recordatorios[telefono] = []

    recordatorio = {
        "id": len(_recordatorios[telefono]) + 1,
        "descripcion": descripcion,
        "fecha_hora": fecha_hora,
        "recurrente": recurrente,
        "activo": True,
        "creado": datetime.utcnow().isoformat(),
    }
    _recordatorios[telefono].append(recordatorio)
    logger.info(f"Recordatorio creado para {telefono}: {descripcion} a las {fecha_hora}")
    return recordatorio


def listar_recordatorios(telefono: str) -> list[dict]:
    """Retorna los recordatorios activos del usuario."""
    return [r for r in _recordatorios.get(telefono, []) if r["activo"]]


def cancelar_recordatorio(telefono: str, recordatorio_id: int) -> bool:
    """Cancela un recordatorio por ID. Retorna True si lo encontró."""
    for r in _recordatorios.get(telefono, []):
        if r["id"] == recordatorio_id:
            r["activo"] = False
            return True
    return False


# ════════════════════════════════════════════════════════════
# GESTIÓN DE LISTAS
# Dona puede manejar múltiples listas por usuario:
# compras, metas, ideas, libros, películas, etc.
# ════════════════════════════════════════════════════════════

def agregar_a_lista(telefono: str, nombre_lista: str, item: str) -> dict:
    """
    Agrega un ítem a una lista del usuario (la crea si no existe).

    Args:
        telefono: Número del usuario
        nombre_lista: Nombre de la lista (ej: "compras", "metas")
        item: Elemento a agregar
    """
    if telefono not in _listas:
        _listas[telefono] = {}

    nombre_lista = nombre_lista.lower().strip()
    if nombre_lista not in _listas[telefono]:
        _listas[telefono][nombre_lista] = []

    elemento = {
        "id": len(_listas[telefono][nombre_lista]) + 1,
        "texto": item,
        "completado": False,
        "agregado": datetime.utcnow().isoformat(),
    }
    _listas[telefono][nombre_lista].append(elemento)
    return elemento


def ver_lista(telefono: str, nombre_lista: str) -> list[dict]:
    """Retorna todos los ítems de una lista."""
    nombre_lista = nombre_lista.lower().strip()
    return _listas.get(telefono, {}).get(nombre_lista, [])


def listar_nombres_listas(telefono: str) -> list[str]:
    """Retorna los nombres de todas las listas del usuario."""
    return list(_listas.get(telefono, {}).keys())


def tachar_de_lista(telefono: str, nombre_lista: str, item_id: int) -> bool:
    """Marca un ítem de lista como completado."""
    nombre_lista = nombre_lista.lower().strip()
    for item in _listas.get(telefono, {}).get(nombre_lista, []):
        if item["id"] == item_id:
            item["completado"] = True
            return True
    return False


# ════════════════════════════════════════════════════════════
# GESTIÓN DE CALENDARIO Y EVENTOS
# Dona puede agendar, listar y cancelar eventos.
# ════════════════════════════════════════════════════════════

def agendar_evento(telefono: str, titulo: str, fecha_hora: str, descripcion: str = "") -> dict:
    """
    Agrega un evento al calendario del usuario.

    Args:
        telefono: Número del usuario
        titulo: Nombre del evento
        fecha_hora: Cuándo ocurre (ej: "2026-03-20 15:00")
        descripcion: Detalles adicionales opcionales
    """
    if telefono not in _eventos:
        _eventos[telefono] = []

    evento = {
        "id": len(_eventos[telefono]) + 1,
        "titulo": titulo,
        "fecha_hora": fecha_hora,
        "descripcion": descripcion,
        "cancelado": False,
        "creado": datetime.utcnow().isoformat(),
    }
    _eventos[telefono].append(evento)
    logger.info(f"Evento agendado para {telefono}: {titulo} el {fecha_hora}")
    return evento


def listar_eventos(telefono: str, fecha_filtro: str = None) -> list[dict]:
    """
    Retorna los eventos del usuario.

    Args:
        telefono: Número del usuario
        fecha_filtro: Si se proporciona, filtra por esa fecha (ej: "2026-03-20")
    """
    eventos = [e for e in _eventos.get(telefono, []) if not e["cancelado"]]
    if fecha_filtro:
        eventos = [e for e in eventos if e["fecha_hora"].startswith(fecha_filtro)]
    return eventos


def cancelar_evento(telefono: str, evento_id: int) -> bool:
    """Cancela un evento por ID. Retorna True si lo encontró."""
    for evento in _eventos.get(telefono, []):
        if evento["id"] == evento_id:
            evento["cancelado"] = True
            return True
    return False
