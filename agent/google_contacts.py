# agent/google_contacts.py — Integración con Google People API (Contactos)

"""
Permite a Dona consultar los contactos del usuario para:
  - Auto-populate nombre cuando llega un mensaje de un número desconocido.
  - Resolver "envíale un correo a Juan Pérez" → email del contacto.
  - Listar contactos recientes para sugerencias.

Usa Google People API con scope `contacts.readonly`.
"""

import re
import logging
import httpx

logger = logging.getLogger("agentkit")

_PEOPLE_API = "https://people.googleapis.com/v1"

# Campos que pedimos (mínimos necesarios para uso de Dona).
_FIELDS = "names,emailAddresses,phoneNumbers"


async def _token(telefono: str) -> str | None:
    from agent.google_calendar import _obtener_token_valido
    return await _obtener_token_valido(telefono)


def _normalizar_telefono(n: str) -> str:
    """Deja solo dígitos; útil para comparar números con distintos formatos."""
    return re.sub(r"\D", "", n or "")


def _parsear_contacto(person: dict) -> dict:
    """Extrae los campos útiles de un objeto Person de Google."""
    nombre = ""
    if person.get("names"):
        nombre = person["names"][0].get("displayName", "")
    emails = [e.get("value", "") for e in person.get("emailAddresses", []) if e.get("value")]
    telefonos = [p.get("value", "") for p in person.get("phoneNumbers", []) if p.get("value")]
    return {
        "nombre": nombre,
        "emails": emails,
        "telefonos": telefonos,
        "telefonos_normalizados": [_normalizar_telefono(t) for t in telefonos],
    }


async def listar_contactos(telefono: str, limite: int = 100) -> list[dict]:
    """
    Lista los contactos del usuario (máximo 1000 por página en People API).
    Devuelve lista de dicts: {nombre, emails, telefonos, telefonos_normalizados}.
    """
    tok = await _token(telefono)
    if not tok:
        return []
    contactos: list[dict] = []
    page_token = None
    restante = limite

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            while restante > 0:
                params = {
                    "personFields": _FIELDS,
                    "pageSize": min(restante, 1000),
                    "sortOrder": "LAST_MODIFIED_DESCENDING",
                }
                if page_token:
                    params["pageToken"] = page_token
                resp = await client.get(
                    f"{_PEOPLE_API}/people/me/connections",
                    params=params,
                    headers={"Authorization": f"Bearer {tok}"},
                )
                if resp.status_code == 403:
                    logger.warning("[CONTACTS] 403 — falta scope contacts.readonly (re-autorizar)")
                    return contactos
                if resp.status_code != 200:
                    logger.error(f"[CONTACTS] listar {resp.status_code}: {resp.text[:200]}")
                    return contactos
                data = resp.json()
                for p in data.get("connections", []):
                    contactos.append(_parsear_contacto(p))
                    restante -= 1
                    if restante <= 0:
                        break
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        return contactos
    except Exception as e:
        logger.error(f"[CONTACTS] Excepción listando ({type(e).__name__}): {e}")
        return contactos


async def buscar_por_telefono(telefono_usuario: str, numero_buscado: str) -> dict | None:
    """
    Busca un contacto por número de teléfono. Compara solo dígitos (ignora +, -, espacios).
    Matchea si el número guardado termina con el número buscado (para que "+14076936023"
    matchee con "4076936023" y viceversa).

    Returns:
        dict del contacto o None si no se encuentra.
    """
    digits_buscar = _normalizar_telefono(numero_buscado)
    if not digits_buscar or len(digits_buscar) < 7:
        return None

    # People API tiene un endpoint de búsqueda nativo, pero requiere que el
    # índice esté "warm" (ver docs). Para MVP usamos listar + filtrar en memoria.
    contactos = await listar_contactos(telefono_usuario, limite=1000)
    for c in contactos:
        for t_norm in c["telefonos_normalizados"]:
            if not t_norm:
                continue
            # Match si uno termina con el otro (tolerante a códigos de país)
            if t_norm.endswith(digits_buscar) or digits_buscar.endswith(t_norm):
                return c
    return None


async def buscar_por_nombre(telefono_usuario: str, nombre_buscado: str) -> list[dict]:
    """
    Usa el endpoint nativo de búsqueda de People API. Devuelve hasta 30 resultados.
    Útil para resolver "envíale un correo a Juan".
    """
    tok = await _token(telefono_usuario)
    if not tok or not nombre_buscado.strip():
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_PEOPLE_API}/people:searchContacts",
                params={
                    "query": nombre_buscado.strip()[:100],
                    "readMask": _FIELDS,
                    "pageSize": 30,
                },
                headers={"Authorization": f"Bearer {tok}"},
            )
            if resp.status_code != 200:
                logger.error(f"[CONTACTS] search {resp.status_code}: {resp.text[:200]}")
                return []
            data = resp.json()
            return [_parsear_contacto(r["person"]) for r in data.get("results", []) if r.get("person")]
    except Exception as e:
        logger.error(f"[CONTACTS] Excepción buscando nombre ({type(e).__name__}): {e}")
        return []
