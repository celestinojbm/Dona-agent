# agent/google_calendar.py — Integración con Google Calendar vía OAuth 2.0
# Dona

"""
Conecta Dona con el Google Calendar real del usuario.

Flujo OAuth sin dependencias de Google SDK (solo httpx):
  1. generar_url_oauth(telefono)           → URL de autorización de Google
  2. intercambiar_codigo(code, telefono)   → guarda tokens en DB
  3. _obtener_token_valido(telefono)       → acceso con refresh automático
  4. listar_eventos_hoy(telefono)          → eventos del día desde Calendar API
  5. crear_evento(telefono, ...)           → nuevo evento en el calendario

Variables de entorno necesarias:
  GOOGLE_CLIENT_ID       — ID de la aplicación OAuth (Google Cloud Console)
  GOOGLE_CLIENT_SECRET   — Secreto de la aplicación
  BASE_URL               — URL pública del servidor (ej: https://dona.onrender.com)
"""

import os
import base64
import hmac
import hashlib
import secrets
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
# Secret para firmar el parámetro `state` de OAuth (protección CSRF).
# Reusa ENCRYPTION_KEY si existe, si no deriva de GOOGLE_CLIENT_SECRET.
_OAUTH_STATE_SECRET = (
    os.getenv("OAUTH_STATE_SECRET")
    or os.getenv("ENCRYPTION_KEY")
    or GOOGLE_CLIENT_SECRET
    or "dona-oauth-state-fallback-DO-NOT-USE-IN-PROD"
).encode()
_OAUTH_STATE_TTL_SECONDS = 600  # 10 minutos
BASE_URL = (
    os.getenv("BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or "http://localhost:8000"
).rstrip("/")
REDIRECT_URI = f"{BASE_URL}/auth/google/callback"

# Alcances de Google que Dona necesita (Calendar + Sheets + Drive + Gmail + Contacts)
# NOTA: agregar scopes obliga a los usuarios existentes a re-autorizar en Google
# (se muestra la pantalla de consent con los permisos nuevos). No requiere
# intervención del desarrollador.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",     # leer y crear eventos
    "https://www.googleapis.com/auth/spreadsheets",        # leer y escribir hojas
    "https://www.googleapis.com/auth/drive.readonly",      # listar Sheets del usuario
    "https://www.googleapis.com/auth/drive.file",          # crear/subir archivos propios de Dona
    "https://www.googleapis.com/auth/gmail.readonly",      # leer correos
    "https://www.googleapis.com/auth/gmail.send",          # enviar correos
    "https://www.googleapis.com/auth/contacts.readonly",   # leer contactos del usuario
    "https://www.googleapis.com/auth/tasks",               # leer y gestionar Google Tasks
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",      # mostrar el email al confirmar
]

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def esta_disponible() -> bool:
    """Retorna True si las credenciales de Google están configuradas en el entorno."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def codificar_state(telefono: str) -> str:
    """
    Codifica el `state` de OAuth con protección CSRF:
      - nonce aleatorio (16 bytes → 128 bits de entropía)
      - timestamp de expiración
      - firma HMAC-SHA256 del payload
    Formato: base64url(nonce | expira_ts | telefono) + "." + hex(hmac)
    """
    nonce = secrets.token_urlsafe(16)
    expira_ts = int(datetime.utcnow().timestamp()) + _OAUTH_STATE_TTL_SECONDS
    payload = f"{nonce}|{expira_ts}|{telefono}"
    firma = hmac.new(_OAUTH_STATE_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{payload_b64}.{firma}"


def decodificar_state(state: str) -> str:
    """
    Decodifica y valida el `state` de OAuth. Retorna el teléfono si es válido.
    Lanza ValueError si la firma es inválida o el state expiró.
    """
    try:
        payload_b64, firma = state.split(".", 1)
    except ValueError:
        # Compatibilidad: state legacy (solo base64 del teléfono, sin firma)
        # Lo aceptamos en modo degradado pero logueamos warning.
        try:
            telefono_legacy = base64.urlsafe_b64decode(state.encode()).decode()
            logger.warning(f"[OAUTH] State sin firma (legacy) para {telefono_legacy}")
            return telefono_legacy
        except Exception:
            raise ValueError("State OAuth malformado")

    # Re-agregar padding base64 si es necesario
    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload = base64.urlsafe_b64decode((payload_b64 + padding).encode()).decode()
    except Exception:
        raise ValueError("State OAuth malformado (base64)")

    partes = payload.split("|", 2)
    if len(partes) != 3:
        raise ValueError("State OAuth malformado (payload)")
    _nonce, expira_ts_str, telefono = partes

    # Validar firma (timing-safe)
    firma_esperada = hmac.new(_OAUTH_STATE_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(firma, firma_esperada):
        raise ValueError("Firma de state OAuth inválida (posible CSRF)")

    # Validar expiración
    try:
        expira_ts = int(expira_ts_str)
    except ValueError:
        raise ValueError("Timestamp de state OAuth inválido")
    if datetime.utcnow().timestamp() > expira_ts:
        raise ValueError("State OAuth expirado")

    return telefono


def generar_url_oauth(telefono: str) -> str:
    """
    Genera la URL de autorización de Google para que el usuario conceda acceso.

    - access_type=offline  → Google entrega refresh_token (necesario para renovar sin re-login)
    - prompt=consent       → fuerza que Google muestre la pantalla de consentimiento siempre
                             (garantiza que el refresh_token aparezca en la respuesta)
    """
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": codificar_state(telefono),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def intercambiar_codigo(code: str, telefono: str) -> tuple[bool, str]:
    """
    Intercambia el authorization code por access_token y refresh_token.
    Guarda los tokens cifrados en la base de datos.

    Returns:
        (exito: bool, email: str) — el email es solo para mostrar al usuario.
    """
    from agent.memory import guardar_google_auth

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Intercambio de código → tokens
            resp = await client.post(_TOKEN_URL, data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            })

            if resp.status_code != 200:
                error_detail = resp.text[:500]
                logger.error(f"Google token exchange: {resp.status_code} {error_detail}")
                # No exponer detalles del error al usuario final (puede filtrar info del flujo OAuth)
                return False, "No pudimos completar la autorización con Google. Intenta de nuevo."

            tokens = resp.json()
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token", "")
            expires_in = tokens.get("expires_in", 3600)
            # Guardamos con 60s de margen para renovar antes de que venza
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)

            # 2. Obtener email del usuario para confirmación visual
            email = ""
            try:
                info_resp = await client.get(
                    _USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if info_resp.status_code == 200:
                    email = info_resp.json().get("email", "")
            except Exception:
                pass  # el email es solo informativo, no crítico

            # 3. Persistir en DB
            await guardar_google_auth(
                telefono=telefono,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                email=email,
            )

            logger.info(f"Google Calendar conectado para {telefono} ({email})")
            return True, email

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"intercambiar_codigo error para {telefono}: {e}\n{tb}")
        # No exponer traceback ni tipo de excepción al usuario final
        return False, "Error interno al conectar con Google. Intenta de nuevo en unos momentos."


async def _obtener_token_valido(telefono: str) -> str | None:
    """
    Retorna un access_token vigente para el usuario.
    Si el token expiró, lo renueva automáticamente con el refresh_token.
    Retorna None si el usuario no tiene Google Calendar conectado.
    """
    from agent.memory import obtener_google_auth, guardar_google_auth

    auth = await obtener_google_auth(telefono)
    if not auth:
        return None

    # Token aún vigente → devolver directamente
    if auth["expires_at"] and datetime.utcnow() < auth["expires_at"]:
        return auth["access_token"]

    # Token expirado → refrescar con refresh_token
    refresh_token = auth.get("refresh_token", "")
    if not refresh_token:
        logger.warning(f"Google: token expirado sin refresh_token para {telefono}")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_TOKEN_URL, data={
                "refresh_token": refresh_token,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            })

            if resp.status_code != 200:
                logger.error(f"Google token refresh: {resp.status_code} {resp.text[:200]}")
                return None

            tokens = resp.json()
            new_access_token = tokens["access_token"]
            expires_in = tokens.get("expires_in", 3600)
            new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)

            # Actualizar DB (el refresh_token no cambia en la renovación)
            await guardar_google_auth(
                telefono=telefono,
                access_token=new_access_token,
                refresh_token=refresh_token,
                expires_at=new_expires_at,
                email=auth.get("email", ""),
            )

            logger.info(f"Google token refrescado para {telefono}")
            return new_access_token

    except Exception as e:
        logger.error(f"_obtener_token_valido refresh error para {telefono}: {e}")
        return None


async def listar_eventos_hoy(telefono: str, offset_min: int = 0) -> list[dict]:
    """
    Retorna los eventos del día actual desde Google Calendar del usuario.

    Args:
        telefono:   Número del usuario
        offset_min: Offset de zona horaria del usuario en minutos (para calcular "hoy" correctamente)

    Returns:
        Lista de dicts con titulo, inicio, fin, descripcion, lugar.
        Lista vacía si el usuario no está autenticado o no hay eventos.
    """
    token = await _obtener_token_valido(telefono)
    if not token:
        return []

    # Rango "hoy" calculado en la hora local del usuario
    ahora_utc = datetime.now(timezone.utc)
    offset = timedelta(minutes=offset_min)
    ahora_local = ahora_utc + offset
    inicio_dia_local = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_dia_local = inicio_dia_local + timedelta(days=1)

    def _a_rfc3339(dt_local: datetime) -> str:
        """Convierte datetime local a RFC 3339 con offset explícito."""
        signo = "+" if offset_min >= 0 else "-"
        hh = abs(offset_min) // 60
        mm = abs(offset_min) % 60
        return dt_local.strftime("%Y-%m-%dT%H:%M:%S") + f"{signo}{hh:02d}:{mm:02d}"

    params = {
        "calendarId": "primary",
        "timeMin": _a_rfc3339(inicio_dia_local),
        "timeMax": _a_rfc3339(fin_dia_local),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 15,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_CALENDAR_API}/calendars/primary/events",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )

            if resp.status_code != 200:
                logger.error(f"Google Calendar list: {resp.status_code} {resp.text[:200]}")
                return []

            items = resp.json().get("items", [])
            eventos = []
            for item in items:
                start = item.get("start", {})
                end = item.get("end", {})
                eventos.append({
                    "titulo": item.get("summary", "(sin título)"),
                    "inicio": start.get("dateTime", start.get("date", "")),
                    "fin": end.get("dateTime", end.get("date", "")),
                    "descripcion": item.get("description", ""),
                    "lugar": item.get("location", ""),
                    "id": item.get("id", ""),
                })
            return eventos

    except Exception as e:
        logger.error(f"listar_eventos_hoy error para {telefono}: {e}")
        return []


async def crear_evento(
    telefono: str,
    titulo: str,
    inicio_iso: str,
    fin_iso: str,
    descripcion: str = "",
    lugar: str = "",
) -> dict | None:
    """
    Crea un nuevo evento en Google Calendar del usuario.

    Args:
        telefono:   Número del usuario
        titulo:     Título del evento
        inicio_iso: Inicio en ISO 8601 con offset (ej: "2026-03-24T15:00:00-04:00")
        fin_iso:    Fin en ISO 8601 con offset
        descripcion: Detalles adicionales (opcional)
        lugar:      Ubicación del evento (opcional)

    Returns:
        Dict con id, titulo y link del evento, o None si falló.
    """
    token = await _obtener_token_valido(telefono)
    if not token:
        return None

    body: dict = {
        "summary": titulo,
        "start": {"dateTime": inicio_iso},
        "end": {"dateTime": fin_iso},
    }
    if descripcion:
        body["description"] = descripcion
    if lugar:
        body["location"] = lugar

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_CALENDAR_API}/calendars/primary/events",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code not in (200, 201):
                logger.error(f"Google Calendar create: {resp.status_code} {resp.text[:300]}")
                return None

            evento = resp.json()
            logger.info(f"Evento creado en Google Calendar para {telefono}: '{titulo}'")
            return {
                "id": evento.get("id", ""),
                "titulo": evento.get("summary", titulo),
                "link": evento.get("htmlLink", ""),
            }

    except Exception as e:
        logger.error(f"crear_evento error para {telefono}: {e}")
        return None


async def editar_evento(
    telefono: str,
    evento_id: str,
    titulo: str | None = None,
    inicio_iso: str | None = None,
    fin_iso: str | None = None,
    descripcion: str | None = None,
    lugar: str | None = None,
) -> dict | None:
    """
    Edita un evento existente en Google Calendar del usuario (PATCH parcial).

    Args:
        telefono:    Número del usuario
        evento_id:   ID del evento en Google Calendar
        titulo:      Nuevo título (opcional)
        inicio_iso:  Nueva hora de inicio ISO 8601 (opcional)
        fin_iso:     Nueva hora de fin ISO 8601 (opcional)
        descripcion: Nueva descripción (opcional)
        lugar:       Nuevo lugar (opcional)

    Returns:
        Dict con id, titulo y link del evento actualizado, o None si falló.
    """
    token = await _obtener_token_valido(telefono)
    if not token:
        return None

    body: dict = {}
    if titulo is not None:
        body["summary"] = titulo
    if inicio_iso is not None:
        body["start"] = {"dateTime": inicio_iso}
    if fin_iso is not None:
        body["end"] = {"dateTime": fin_iso}
    if descripcion is not None:
        body["description"] = descripcion
    if lugar is not None:
        body["location"] = lugar

    if not body:
        logger.warning(f"editar_evento: no hay cambios para el evento {evento_id}")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(
                f"{_CALENDAR_API}/calendars/primary/events/{evento_id}",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code != 200:
                logger.error(f"Google Calendar patch: {resp.status_code} {resp.text[:300]}")
                return None

            evento = resp.json()
            logger.info(f"Evento {evento_id} editado en Google Calendar para {telefono}")
            return {
                "id": evento.get("id", evento_id),
                "titulo": evento.get("summary", titulo or ""),
                "link": evento.get("htmlLink", ""),
            }

    except Exception as e:
        logger.error(f"editar_evento error para {telefono}: {e}")
        return None


async def eliminar_evento(telefono: str, evento_id: str) -> bool:
    """
    Elimina un evento de Google Calendar del usuario.

    Args:
        telefono:  Número del usuario
        evento_id: ID del evento en Google Calendar

    Returns:
        True si se eliminó correctamente, False si falló.
    """
    token = await _obtener_token_valido(telefono)
    if not token:
        return False

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{_CALENDAR_API}/calendars/primary/events/{evento_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

            # Google devuelve 204 No Content al eliminar exitosamente
            if resp.status_code in (200, 204):
                logger.info(f"Evento {evento_id} eliminado de Google Calendar para {telefono}")
                return True
            else:
                logger.error(f"Google Calendar delete: {resp.status_code} {resp.text[:200]}")
                return False

    except Exception as e:
        logger.error(f"eliminar_evento error para {telefono}: {e}")
        return False


async def listar_eventos_rango(
    telefono: str,
    inicio_iso: str,
    fin_iso: str,
    max_resultados: int = 20,
) -> list[dict]:
    """
    Retorna eventos de Google Calendar en un rango de fechas específico.

    Args:
        telefono:       Número del usuario
        inicio_iso:     Inicio del rango en ISO 8601 con offset
        fin_iso:        Fin del rango en ISO 8601 con offset
        max_resultados: Máximo de eventos a retornar (default 20)

    Returns:
        Lista de dicts con id, titulo, inicio, fin, descripcion, lugar.
    """
    token = await _obtener_token_valido(telefono)
    if not token:
        return []

    params = {
        "calendarId": "primary",
        "timeMin": inicio_iso,
        "timeMax": fin_iso,
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": max_resultados,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_CALENDAR_API}/calendars/primary/events",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )

            if resp.status_code != 200:
                logger.error(f"Google Calendar list rango: {resp.status_code} {resp.text[:200]}")
                return []

            items = resp.json().get("items", [])
            eventos = []
            for item in items:
                start = item.get("start", {})
                end = item.get("end", {})
                eventos.append({
                    "id": item.get("id", ""),
                    "titulo": item.get("summary", "(sin título)"),
                    "inicio": start.get("dateTime", start.get("date", "")),
                    "fin": end.get("dateTime", end.get("date", "")),
                    "descripcion": item.get("description", ""),
                    "lugar": item.get("location", ""),
                })
            return eventos

    except Exception as e:
        logger.error(f"listar_eventos_rango error para {telefono}: {e}")
        return []


async def obtener_proximos_eventos(
    telefono: str,
    offset_min: int = 0,
    minutos_anticipacion: int = 30,
    ventana_horas: int = 24,
) -> list[dict]:
    """
    Retorna eventos que comienzan en los próximos `minutos_anticipacion` minutos.
    Usado por el scheduler para enviar recordatorios proactivos.

    Args:
        telefono:             Número del usuario
        offset_min:           Offset de zona horaria del usuario en minutos
        minutos_anticipacion: Cuántos minutos antes del evento enviar el recordatorio
        ventana_horas:        Cuántas horas hacia adelante buscar eventos

    Returns:
        Lista de eventos que comienzan pronto (dentro del margen de anticipación).
    """
    token = await _obtener_token_valido(telefono)
    if not token:
        return []

    ahora_utc = datetime.now(timezone.utc)
    fin_ventana = ahora_utc + timedelta(hours=ventana_horas)

    # Buscar eventos en la próxima ventana
    params = {
        "calendarId": "primary",
        "timeMin": ahora_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timeMax": fin_ventana.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_CALENDAR_API}/calendars/primary/events",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )

            if resp.status_code != 200:
                return []

            items = resp.json().get("items", [])
            proximos = []

            for item in items:
                start = item.get("start", {})
                inicio_str = start.get("dateTime", "")
                if not inicio_str:
                    continue  # Eventos de todo el día — omitir

                try:
                    # Parsear el inicio del evento
                    inicio_dt = datetime.fromisoformat(inicio_str)
                    if inicio_dt.tzinfo is None:
                        inicio_dt = inicio_dt.replace(tzinfo=timezone.utc)

                    # Calcular cuántos minutos faltan
                    minutos_restantes = (inicio_dt - ahora_utc).total_seconds() / 60

                    # Solo incluir si está dentro del margen de anticipación
                    if 0 <= minutos_restantes <= minutos_anticipacion:
                        proximos.append({
                            "id": item.get("id", ""),
                            "titulo": item.get("summary", "(sin título)"),
                            "inicio": inicio_str,
                            "fin": item.get("end", {}).get("dateTime", ""),
                            "descripcion": item.get("description", ""),
                            "lugar": item.get("location", ""),
                            "minutos_restantes": int(minutos_restantes),
                        })
                except Exception:
                    continue

            return proximos

    except Exception as e:
        logger.error(f"obtener_proximos_eventos error para {telefono}: {e}")
        return []
