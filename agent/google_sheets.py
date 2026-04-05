# agent/google_sheets.py — Integración con Google Sheets API
"""
Funciones para leer y escribir Google Sheets usando el mismo token OAuth
que Google Calendar (reutiliza _obtener_token_valido de google_calendar.py).

Requiere que el usuario haya autorizado con los scopes:
  - https://www.googleapis.com/auth/spreadsheets
  - https://www.googleapis.com/auth/drive.readonly
"""

import re
import logging
import urllib.parse

import httpx

logger = logging.getLogger("agentkit")

_SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"


# ── Utilidades ────────────────────────────────────────────────────────────────

def extraer_spreadsheet_id(url_o_id: str) -> str:
    """
    Extrae el spreadsheet_id de un URL de Google Sheets.
    Si ya es un ID (sin '/'), lo devuelve tal cual.

    Ejemplos:
      https://docs.google.com/spreadsheets/d/ABC123/edit  → 'ABC123'
      ABC123                                              → 'ABC123'
    """
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_o_id)
    if match:
        return match.group(1)
    return url_o_id.strip()


def _col_letra(n: int) -> str:
    """
    Convierte un índice de columna (0-based) a letra A1.
    0→A, 1→B, 25→Z, 26→AA, etc.
    """
    resultado = ""
    n += 1
    while n:
        n, resto = divmod(n - 1, 26)
        resultado = chr(65 + resto) + resultado
    return resultado


def _a1(fila: int, col: int) -> str:
    """Convierte (fila 0-based, col 0-based) a notación A1 (1-based)."""
    return f"{_col_letra(col)}{fila + 1}"


def _rango_seguro(hoja: str) -> str:
    """Codifica el nombre de la hoja para usarlo en URLs de la API."""
    return urllib.parse.quote(hoja, safe="")


# ── API helpers ───────────────────────────────────────────────────────────────

async def _token(telefono: str) -> str | None:
    """Obtiene un token válido de Google (con refresh automático)."""
    from agent.google_calendar import _obtener_token_valido
    return await _obtener_token_valido(telefono)


async def verificar_acceso_hoja(
    telefono: str,
    spreadsheet_id: str,
) -> tuple[bool, str, list[str]]:
    """
    Verifica acceso a la hoja y devuelve (tiene_acceso, titulo_doc, nombres_tabs).
    'sin_permiso' como titulo indica que el token no tiene el scope de Sheets.
    """
    tok = await _token(telefono)
    if not tok:
        return False, "", []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_SHEETS_API}/{spreadsheet_id}",
                params={"fields": "properties.title,sheets.properties.title"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            if resp.status_code == 403:
                return False, "sin_permiso", []
            if resp.status_code == 404:
                return False, "no_encontrada", []
            if resp.status_code != 200:
                logger.error(f"Sheets metadata: {resp.status_code} {resp.text[:200]}")
                return False, "", []

            data = resp.json()
            titulo = data.get("properties", {}).get("title", "")
            tabs = [
                s["properties"]["title"]
                for s in data.get("sheets", [])
                if "properties" in s
            ]
            return True, titulo, tabs

    except Exception as e:
        logger.error(f"verificar_acceso_hoja error: {e}")
        return False, "", []


async def leer_rango(
    telefono: str,
    spreadsheet_id: str,
    hoja_nombre: str,
    max_filas: int = 50,
    rango_extra: str = "",
) -> list[list[str]]:
    """
    Lee datos de una hoja.

    Args:
        rango_extra: Si se especifica (ej: "A1:E10"), usa ese rango exacto.
                     Si no, lee las primeras max_filas filas.

    Returns:
        Lista de filas, cada fila es lista de strings.
    """
    tok = await _token(telefono)
    if not tok:
        return []

    if rango_extra:
        rango = f"{hoja_nombre}!{rango_extra}"
    else:
        rango = f"{hoja_nombre}!A1:Z{max_filas}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_SHEETS_API}/{spreadsheet_id}/values/{_rango_seguro(rango)}",
                headers={"Authorization": f"Bearer {tok}"},
            )
            if resp.status_code == 403:
                logger.warning(f"Sheets leer: 403 para {telefono} — sin scope de Sheets")
                return []
            if resp.status_code != 200:
                logger.error(f"Sheets leer: {resp.status_code} {resp.text[:200]}")
                return []
            return resp.json().get("values", [])

    except Exception as e:
        logger.error(f"leer_rango error para {telefono}: {e}")
        return []


async def agregar_fila_api(
    telefono: str,
    spreadsheet_id: str,
    hoja_nombre: str,
    valores: list,
) -> bool:
    """
    Agrega una fila al final de la tabla en la hoja indicada.

    Args:
        valores: Lista ordenada de valores (en el mismo orden que los headers).

    Returns:
        True si fue exitoso.
    """
    tok = await _token(telefono)
    if not tok:
        return False

    # El rango de referencia es la hoja completa — Sheets API encuentra el final
    rango = f"{hoja_nombre}!A:Z"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_SHEETS_API}/{spreadsheet_id}/values/{_rango_seguro(rango)}:append",
                params={
                    "valueInputOption": "USER_ENTERED",
                    "insertDataOption": "INSERT_ROWS",
                },
                json={"values": [valores]},
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code not in (200, 201):
                logger.error(f"Sheets append: {resp.status_code} {resp.text[:300]}")
                return False
            logger.info(f"Fila agregada en {spreadsheet_id}/{hoja_nombre} para {telefono}")
            return True

    except Exception as e:
        logger.error(f"agregar_fila_api error para {telefono}: {e}")
        return False


async def actualizar_celda_api(
    telefono: str,
    spreadsheet_id: str,
    hoja_nombre: str,
    rango_a1: str,
    valor: str,
) -> bool:
    """
    Actualiza una celda o rango específico.

    Args:
        rango_a1: Notación A1 de la celda/rango (ej: "B3", "C5:C5").
        valor:    Nuevo valor a escribir.
    """
    tok = await _token(telefono)
    if not tok:
        return False

    rango_completo = f"{hoja_nombre}!{rango_a1}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(
                f"{_SHEETS_API}/{spreadsheet_id}/values/{_rango_seguro(rango_completo)}",
                params={"valueInputOption": "USER_ENTERED"},
                json={"range": rango_completo, "values": [[valor]]},
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code != 200:
                logger.error(f"Sheets update: {resp.status_code} {resp.text[:200]}")
                return False
            return True

    except Exception as e:
        logger.error(f"actualizar_celda_api error para {telefono}: {e}")
        return False


async def buscar_y_actualizar(
    telefono: str,
    spreadsheet_id: str,
    hoja_nombre: str,
    columna_busqueda: str,
    valor_busqueda: str,
    columna_actualizar: str,
    nuevo_valor: str,
) -> tuple[bool, str]:
    """
    Busca una fila por criterio (columna=valor) y actualiza otra columna.

    Returns:
        (exito, descripcion) — ej: (True, "Actualicé fila 4: Estado → 'Cerrado'")
    """
    filas = await leer_rango(telefono, spreadsheet_id, hoja_nombre, max_filas=500)
    if not filas:
        return False, "No se pudo leer la hoja"

    headers = [h.strip().lower() for h in filas[0]] if filas else []

    # Encontrar índice de columnas
    try:
        col_busq = headers.index(columna_busqueda.strip().lower())
    except ValueError:
        return False, f"Columna '{columna_busqueda}' no encontrada. Columnas disponibles: {', '.join(filas[0])}"

    try:
        col_act = headers.index(columna_actualizar.strip().lower())
    except ValueError:
        return False, f"Columna '{columna_actualizar}' no encontrada. Columnas disponibles: {', '.join(filas[0])}"

    # Buscar la fila (empezamos en fila 1 para saltar el header)
    fila_encontrada = None
    for i, fila in enumerate(filas[1:], start=1):
        if col_busq < len(fila) and fila[col_busq].strip().lower() == valor_busqueda.strip().lower():
            fila_encontrada = i
            break

    if fila_encontrada is None:
        return False, f"No encontré ninguna fila donde '{columna_busqueda}' sea '{valor_busqueda}'"

    # Construir notación A1 (fila_encontrada es 0-based dentro de filas, pero la hoja es 1-based con header en fila 1)
    celda = _a1(fila_encontrada, col_act)
    exito = await actualizar_celda_api(telefono, spreadsheet_id, hoja_nombre, celda, nuevo_valor)

    if exito:
        return True, f"Actualicé fila {fila_encontrada + 1} — {filas[0][col_act]}: '{nuevo_valor}' (celda {hoja_nombre}!{celda})"
    return False, "Error al escribir en la hoja"
