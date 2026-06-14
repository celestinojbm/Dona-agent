# agent/google_tasks.py — Integración con Google Tasks API

"""
Gestión de listas de tareas del usuario en Google Tasks.

Reutiliza el mismo OAuth que Calendar/Sheets/Gmail: scope `tasks` agregado
en google_calendar.py. Si el usuario ya autorizó antes de que se agregara
el scope, la primera llamada devolverá 403 → el caller debe pedirle que
re-autorice (`dona conectar google`).

Endpoints cubiertos (v1):
  - listar_listas(telefono)                    → todas las listas del usuario
  - listar_tareas(telefono, lista_id=None)     → pendientes de una lista
  - crear_tarea(telefono, titulo, ...)         → inserta tarea nueva
  - completar_tarea(telefono, lista_id, id)    → marca status=completed
  - eliminar_tarea(telefono, lista_id, id)     → delete duro
"""

import logging
from datetime import UTC, datetime

import httpx

logger = logging.getLogger("dona")

_TASKS_API = "https://tasks.googleapis.com/tasks/v1"


class GoogleTasksScopeError(Exception):
    """El token no tiene el scope de Tasks. El usuario debe re-autorizar."""
    pass


async def _token(telefono: str) -> str | None:
    from agent.google_calendar import _obtener_token_valido
    return await _obtener_token_valido(telefono)


async def listar_listas(telefono: str) -> list[dict]:
    """
    Retorna todas las listas de tareas del usuario.
    [{"id": "...", "titulo": "My Tasks"}, ...]  (vacío si no hay token o error)
    """
    tok = await _token(telefono)
    if not tok:
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_TASKS_API}/users/@me/lists",
                headers={"Authorization": f"Bearer {tok}"},
                params={"maxResults": 100},
            )
            if resp.status_code == 403:
                logger.warning(f"[TASKS] 403 listar_listas — falta scope 'tasks' para {telefono}")
                return []
            if resp.status_code != 200:
                logger.error(f"[TASKS] listar_listas {resp.status_code} {resp.text[:200]}")
                return []
            items = resp.json().get("items", [])
            return [{"id": it["id"], "titulo": it.get("title", "")} for it in items]
    except Exception as e:
        logger.error(f"[TASKS] listar_listas error: {e}")
        return []


async def _lista_por_defecto(telefono: str, tok: str) -> str | None:
    """Retorna el id de la primera lista del usuario (Google crea una por default: '@default')."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_TASKS_API}/users/@me/lists",
            headers={"Authorization": f"Bearer {tok}"},
            params={"maxResults": 1},
        )
        if resp.status_code != 200:
            return None
        items = resp.json().get("items", [])
        return items[0]["id"] if items else None


async def listar_tareas(
    telefono: str,
    lista_id: str | None = None,
    incluir_completadas: bool = False,
    limite: int = 50,
) -> list[dict]:
    """
    Retorna las tareas de una lista. Si `lista_id` es None, usa la lista por defecto.
    """
    tok = await _token(telefono)
    if not tok:
        return []
    try:
        if not lista_id:
            lista_id = await _lista_por_defecto(telefono, tok)
            if not lista_id:
                return []

        params = {
            "maxResults": max(1, min(limite, 100)),
            "showCompleted": "true" if incluir_completadas else "false",
            "showHidden": "false",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_TASKS_API}/lists/{lista_id}/tasks",
                headers={"Authorization": f"Bearer {tok}"},
                params=params,
            )
            if resp.status_code == 403:
                logger.warning(f"[TASKS] 403 listar_tareas — falta scope 'tasks' para {telefono}")
                return []
            if resp.status_code != 200:
                logger.error(f"[TASKS] listar_tareas {resp.status_code} {resp.text[:200]}")
                return []
            items = resp.json().get("items", [])
            return [
                {
                    "id": t.get("id", ""),
                    "titulo": t.get("title", ""),
                    "notas": t.get("notes", ""),
                    "estado": t.get("status", "needsAction"),
                    "vencimiento": t.get("due", ""),  # RFC3339
                    "lista_id": lista_id,
                }
                for t in items
            ]
    except Exception as e:
        logger.error(f"[TASKS] listar_tareas error: {e}")
        return []


async def crear_tarea(
    telefono: str,
    titulo: str,
    notas: str = "",
    vencimiento_iso: str | None = None,
    lista_id: str | None = None,
) -> dict | None:
    """
    Crea una tarea. `vencimiento_iso` debe ser RFC3339 (ej: "2026-04-20T00:00:00.000Z").
    Google Tasks ignora la hora del vencimiento (solo la fecha importa).

    Retorna dict con la tarea creada o None si falla.
    """
    tok = await _token(telefono)
    if not tok:
        return None
    if not titulo or not titulo.strip():
        return None
    try:
        if not lista_id:
            lista_id = await _lista_por_defecto(telefono, tok)
            if not lista_id:
                return None

        body: dict = {"title": titulo.strip()}
        if notas:
            body["notes"] = notas
        if vencimiento_iso:
            body["due"] = vencimiento_iso

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_TASKS_API}/lists/{lista_id}/tasks",
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.status_code == 403:
                raise GoogleTasksScopeError("Token sin scope de Tasks")
            if resp.status_code not in (200, 201):
                logger.error(f"[TASKS] crear_tarea {resp.status_code} {resp.text[:200]}")
                return None
            j = resp.json()
            logger.info(f"[TASKS] Tarea creada para {telefono}: '{titulo[:40]}'")
            return {
                "id": j.get("id", ""),
                "titulo": j.get("title", ""),
                "estado": j.get("status", "needsAction"),
                "vencimiento": j.get("due", ""),
                "lista_id": lista_id,
            }
    except GoogleTasksScopeError:
        raise
    except Exception as e:
        logger.error(f"[TASKS] crear_tarea error: {e}")
        return None


async def completar_tarea(telefono: str, lista_id: str, tarea_id: str) -> bool:
    """Marca la tarea como completada (status='completed')."""
    tok = await _token(telefono)
    if not tok or not lista_id or not tarea_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(
                f"{_TASKS_API}/lists/{lista_id}/tasks/{tarea_id}",
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/json",
                },
                json={
                    "status": "completed",
                    "completed": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                },
            )
            if resp.status_code == 403:
                raise GoogleTasksScopeError("Token sin scope de Tasks")
            if resp.status_code != 200:
                logger.error(f"[TASKS] completar_tarea {resp.status_code} {resp.text[:200]}")
                return False
            return True
    except GoogleTasksScopeError:
        raise
    except Exception as e:
        logger.error(f"[TASKS] completar_tarea error: {e}")
        return False


async def eliminar_tarea(telefono: str, lista_id: str, tarea_id: str) -> bool:
    """Borra la tarea definitivamente."""
    tok = await _token(telefono)
    if not tok or not lista_id or not tarea_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{_TASKS_API}/lists/{lista_id}/tasks/{tarea_id}",
                headers={"Authorization": f"Bearer {tok}"},
            )
            if resp.status_code == 403:
                raise GoogleTasksScopeError("Token sin scope de Tasks")
            # 204 = No Content → éxito
            if resp.status_code not in (200, 204):
                logger.error(f"[TASKS] eliminar_tarea {resp.status_code} {resp.text[:200]}")
                return False
            return True
    except GoogleTasksScopeError:
        raise
    except Exception as e:
        logger.error(f"[TASKS] eliminar_tarea error: {e}")
        return False
