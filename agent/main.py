# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Dona

"""
Servidor principal del agente Dona.
Funciona con cualquier proveedor (Whapi, Meta, Twilio) gracias a la capa de providers.
"""

import os
import re
import hmac
import logging
import httpx
from time import monotonic
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

load_dotenv()

# Configurar logging ANTES de cualquier import que use logger
from agent.logging_config import configurar_logging
configurar_logging()

# Forzar el check de STRIPE_WEBHOOK_SECRET al startup. Si ENVIRONMENT=production
# y la variable no está configurada, agent.billing levanta RuntimeError al
# import y aborta el deploy antes de empezar a servir tráfico.
import agent.billing  # noqa: F401

from agent.brain import generar_respuesta
from agent.memory import (
    inicializar_db, guardar_mensaje, obtener_historial,
    obtener_mirofish_estado, guardar_mirofish_estado,
    obtener_ubicacion, guardar_ubicacion, guardar_ciudad_temporal,
)
from agent.location import parece_viaje, detectar_viaje, es_ciudad_suelta
from agent.learning import registrar_interaccion
from agent.onboarding import procesar_mensaje_onboarding, es_onboarding_activo
from agent.proactivity import (
    es_comando_proactividad, manejar_comando_proactividad,
    es_comando_stop_tcpa, es_comando_start_tcpa,
    manejar_stop_tcpa, manejar_start_tcpa,
)
from agent.memory import (
    contar_eventos_estres_recientes, ya_avisado_sobrecarga_hoy, marcar_aviso_sobrecarga,
    incrementar_mensajes_proactivos,
)
from agent.providers import obtener_proveedor
from agent.scheduler import iniciar_scheduler, detener_scheduler
from agent.transcriber import procesar_audio_whapi, procesar_audio_meta
from agent.memory_summary import actualizar_resumen_si_necesario

logger = logging.getLogger("dona")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Proveedor de WhatsApp (se configura en .env con WHATSAPP_PROVIDER)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))

# ── Deduplicación de mensajes ─────────────────────────────────────────────────
# Usa PostgreSQL para persistir IDs procesados (sobrevive restarts).
# Fallback a in-memory si la DB falla.
import collections as _collections
_mensajes_procesados_mem: _collections.OrderedDict = _collections.OrderedDict()
_MAX_IDS_DEDUP = 1000

# ── Rate limiting por número de teléfono ─────────────────────────────────────
# Usa Redis si disponible (persistente), sino fallback a in-memory.
from agent.rate_limiter import dentro_de_limite as _dentro_de_limite


# ── Métricas en memoria para el endpoint /admin/metrics ──────────────────────
import threading as _threading

class _Metricas:
    """Contadores atómicos simples para métricas de la aplicación."""
    def __init__(self):
        self._lock = _threading.Lock()
        self.requests_total = 0
        self.requests_por_ruta: dict[str, int] = {}
        self.errores_total = 0
        self.mensajes_procesados = 0
        self.latencia_sum_ms = 0.0
        self.latencia_count = 0
        self.requests_lentos = 0  # > 5s

    def registrar_request(self, ruta: str, duracion_ms: float, status_code: int):
        with self._lock:
            self.requests_total += 1
            self.requests_por_ruta[ruta] = self.requests_por_ruta.get(ruta, 0) + 1
            self.latencia_sum_ms += duracion_ms
            self.latencia_count += 1
            if status_code >= 500:
                self.errores_total += 1
            if duracion_ms > 5000:
                self.requests_lentos += 1

    def registrar_mensaje(self):
        with self._lock:
            self.mensajes_procesados += 1

    def snapshot(self) -> dict:
        with self._lock:
            avg = (self.latencia_sum_ms / self.latencia_count) if self.latencia_count else 0
            return {
                "requests_total": self.requests_total,
                "requests_por_ruta": dict(self.requests_por_ruta),
                "errores_5xx": self.errores_total,
                "mensajes_procesados": self.mensajes_procesados,
                "latencia_promedio_ms": round(avg, 1),
                "requests_lentos_5s": self.requests_lentos,
            }

metricas = _Metricas()


# ── Middleware: Request logging + timing ──────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Registra cada request con duración y status code."""
    async def dispatch(self, request: Request, call_next):
        inicio = monotonic()
        ruta = request.url.path
        metodo = request.method

        try:
            response = await call_next(request)
        except Exception:
            duracion_ms = (monotonic() - inicio) * 1000
            metricas.registrar_request(ruta, duracion_ms, 500)
            logger.error(f"{metodo} {ruta} 500 {duracion_ms:.0f}ms")
            raise

        duracion_ms = (monotonic() - inicio) * 1000
        metricas.registrar_request(ruta, duracion_ms, response.status_code)

        # Solo loguear requests no triviales (omitir health checks frecuentes)
        if ruta != "/" or response.status_code != 200:
            nivel = logging.WARNING if duracion_ms > 5000 else logging.INFO
            logger.log(nivel, f"{metodo} {ruta} {response.status_code} {duracion_ms:.0f}ms")

        return response


# ── Middleware: Security headers ──────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad a cada respuesta."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # No cachear respuestas de API
        if not request.url.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos y el scheduler al arrancar el servidor."""
    await inicializar_db()
    # Crear tablas de Dona 2.0 (enhanced/) si no existen
    from enhanced.models import inicializar_tablas_enhanced
    await inicializar_tablas_enhanced()
    # Sembrar catálogo de sistemas si está vacío
    from enhanced.catalog import sembrar_catalogo
    await sembrar_catalogo()
    iniciar_scheduler(proveedor)
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor Dona corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield
    detener_scheduler()


app = FastAPI(
    title="Dona — Asistente Personal en WhatsApp",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if ENVIRONMENT == "production" else "/docs",
    redoc_url=None if ENVIRONMENT == "production" else "/redoc",
)

# Registrar middleware (orden importa: el último agregado se ejecuta primero)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.get("/privacy")
async def privacy_policy():
    """Política de privacidad (CCPA/CPRA + marco multi-estado EEUU)."""
    from agent.legal_pages import privacy_policy_html
    return HTMLResponse(privacy_policy_html())


@app.get("/terms")
async def terms_of_service():
    """Términos de servicio."""
    from agent.legal_pages import terms_html
    return HTMLResponse(terms_html())


@app.get("/privacy/export")
async def privacy_export(telefono: str):
    """
    Export de datos del usuario (portabilidad — CCPA/CPRA derecho de acceso).
    Requiere que el usuario se autentique enviando un código de verificación
    por WhatsApp primero. Por ahora retorna instrucciones de contacto.
    """
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    # MVP: exigir confirmación por WhatsApp antes de exportar (evita scraping).
    # Implementación completa requiere flujo de verificación de código de un solo uso.
    return {
        "status": "pending_verification",
        "mensaje": (
            "Para ejercer tu derecho de acceso/portabilidad, escríbenos a "
            f"{os.getenv('LEGAL_EMAIL', 'privacy@dona.ai')} desde una dirección de correo "
            "asociada a tu cuenta, o envía el comando 'dona exportar datos' por WhatsApp. "
            "Responderemos dentro de 45 días (CCPA/CPRA)."
        ),
    }


@app.post("/privacy/delete")
async def privacy_delete(
    request: Request,
    telefono: str,
    confirmacion: str = "",
):
    """
    Solicitud de borrado de datos (CCPA/CPRA derecho de eliminación).
    Requiere que el usuario confirme enviando el comando 'dona borrar mis datos'
    por WhatsApp. Este endpoint inicia el ticket; la verificación ocurre por WhatsApp.
    """
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    if confirmacion != "BORRAR":
        return {
            "status": "instrucciones",
            "mensaje": (
                "Para confirmar el borrado de tus datos envía por WhatsApp el mensaje: "
                "'dona borrar mis datos'. Dona te pedirá confirmación antes de proceder. "
                "Alternativamente, escribe a "
                f"{os.getenv('LEGAL_EMAIL', 'privacy@dona.ai')} desde un correo asociado."
            ),
        }
    # Confirmación explícita: registrar solicitud.
    logger.info(f"[PRIVACY] Solicitud de borrado registrada para {telefono}")
    return {
        "status": "registered",
        "mensaje": (
            "Tu solicitud ha sido registrada. Responde al mensaje de confirmación que "
            "te enviaremos por WhatsApp para completar el borrado (45 días máx.)."
        ),
    }


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway/monitoreo. Verifica DB real."""
    from sqlalchemy import text as _text
    try:
        from agent.memory import async_session
        async with async_session() as session:
            await session.execute(_text("SELECT 1"))
        return {"status": "ok", "service": "dona", "db": "connected"}
    except Exception as e:
        logger.error(f"[HEALTH] DB check failed: {e}")
        return {"status": "degraded", "service": "dona", "db": "error"}


_TELEFONO_RE = re.compile(r"^\+?\d{10,15}$")


def _telefono_valido(telefono: str) -> bool:
    """Valida formato E.164 laxo (10-15 dígitos, '+' opcional)."""
    return bool(telefono) and bool(_TELEFONO_RE.match(telefono.strip()))


def _verificar_admin(request: Request, token_query: str = "") -> bool:
    """Verifica autenticación admin via header (preferido) o query param (legacy).
    Usa hmac.compare_digest para evitar timing attacks."""
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token:
        return False
    # Preferir header Authorization: Bearer <token>
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return hmac.compare_digest(auth_header[7:], admin_token)
    # Fallback a query param (legacy, menos seguro)
    if token_query:
        return hmac.compare_digest(token_query, admin_token)
    return False


@app.get("/diagnostico")
async def diagnostico(request: Request, token: str = ""):
    """Prueba la conectividad con Whapi desde Railway. Requiere auth admin."""
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")

    whapi_token = os.getenv("WHAPI_TOKEN", "")
    resultados = {}

    # Test 1: DNS y TCP a gate.whapi.cloud
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://gate.whapi.cloud/health",
                headers={"Authorization": f"Bearer {whapi_token}"}
            )
            resultados["whapi_health"] = {"status": r.status_code, "body": r.json()}
    except Exception as e:
        resultados["whapi_health"] = {"error": type(e).__name__, "detail": str(e)}

    # Test 2: Conectividad general
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://httpbin.org/ip")
            resultados["railway_ip"] = r.json()
    except Exception as e:
        resultados["railway_ip"] = {"error": type(e).__name__, "detail": str(e)}

    return resultados


@app.get("/admin/metrics")
async def admin_metrics(request: Request, token: str = ""):
    """Métricas de la aplicación: requests, errores, latencia, mensajes."""
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")
    from datetime import datetime as _dt, timezone as _tz
    data = metricas.snapshot()
    data["timestamp"] = _dt.now(_tz.utc).isoformat()
    data["uptime_info"] = "desde último deploy"
    return data


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    """Verificación GET del webhook (requerido por Meta Cloud API, no-op para otros)."""
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.get("/admin/onboarding")
async def admin_onboarding_estado(request: Request, telefono: str, token: str = ""):
    """
    Diagnóstico de onboarding en producción.
    Uso: /admin/onboarding?telefono=521234567890 + Header Authorization: Bearer <token>
    """
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    from agent.memory import obtener_onboarding, obtener_ubicacion
    estado = await obtener_onboarding(telefono)
    ubicacion = await obtener_ubicacion(telefono)
    return {
        "telefono": telefono,
        "onboarding": estado,
        "ubicacion": ubicacion,
    }


@app.post("/admin/onboarding/reset")
async def admin_onboarding_reset(request: Request, telefono: str, fase: int = 0, paso: int = 0, token: str = ""):
    """
    Resetea el estado de onboarding de un usuario.
    Uso: POST /admin/onboarding/reset?telefono=521234567890&fase=0&paso=2 + Header Auth
    """
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    from agent.memory import guardar_onboarding
    await guardar_onboarding(telefono, fase=fase, paso=paso)
    return {"status": "ok", "telefono": telefono, "fase": fase, "paso": paso}


@app.get("/admin/jobs-recientes")
async def admin_jobs_recientes(request: Request, telefono: str, limite: int = 10, token: str = ""):
    """Diagnóstico: últimos N jobs creativos del usuario con estado y error_msg."""
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    from agent.jobs import listar_jobs_usuario
    jobs = await listar_jobs_usuario(telefono, limite=limite)
    return {"telefono": telefono, "total": len(jobs), "jobs": jobs}


@app.get("/admin/r2-check")
async def admin_r2_check(request: Request, token: str = ""):
    """
    Diagnóstico de Cloudflare R2.
    Reporta qué env vars están seteadas, intenta un put/get de prueba y retorna
    el error exacto si falla. No registra nada en DB.
    """
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")

    from agent import storage as _st

    presencia = {
        "R2_ACCOUNT_ID": bool(_st.R2_ACCOUNT_ID),
        "R2_ACCESS_KEY_ID": bool(_st.R2_ACCESS_KEY_ID),
        "R2_SECRET_ACCESS_KEY": bool(_st.R2_SECRET_ACCESS_KEY),
        "R2_BUCKET": _st.R2_BUCKET or None,
        "R2_PUBLIC_URL": _st.R2_PUBLIC_URL or None,
    }
    longitudes = {
        "R2_ACCOUNT_ID_len": len(_st.R2_ACCOUNT_ID),
        "R2_ACCESS_KEY_ID_len": len(_st.R2_ACCESS_KEY_ID),
        "R2_SECRET_ACCESS_KEY_len": len(_st.R2_SECRET_ACCESS_KEY),
    }
    disponible = _st._r2_disponible()
    if not disponible:
        return {
            "status": "config_incompleta",
            "disponible": False,
            "presencia": presencia,
            "longitudes": longitudes,
            "mensaje": "Falta alguna de las 4 env vars obligatorias.",
        }

    # Intento real: put + delete de un objeto de prueba
    import uuid as _uuid
    key_prueba = f"diagnostico/r2-check-{_uuid.uuid4().hex[:8]}.txt"
    try:
        url = await _st._subir_r2(key_prueba, b"dona r2 ok", "text/plain")
        # best-effort borrado
        borrado = await _st._borrar_r2(key_prueba)
        return {
            "status": "ok",
            "disponible": True,
            "presencia": presencia,
            "longitudes": longitudes,
            "url_prueba": url,
            "borrado": borrado,
            "mensaje": "R2 funcional. La URL retornada es la que usaría para assets reales.",
        }
    except Exception as e:
        return {
            "status": "error",
            "disponible": True,
            "presencia": presencia,
            "longitudes": longitudes,
            "excepcion_tipo": type(e).__name__,
            "excepcion_mensaje": str(e)[:500],
            "mensaje": "Credenciales presentes pero R2 tiró excepción al subir.",
        }


@app.post("/admin/seed-creditos")
async def admin_seed_creditos(request: Request, telefono: str, creditos: int = 100, razon: str = "seed admin", token: str = ""):
    """
    Acredita N créditos al usuario indicado. Sirve para seed manual mientras
    Stripe no está configurado, o para regalar créditos.
    Uso: POST /admin/seed-creditos?telefono=15551234567&creditos=100 + Header Auth
    """
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    if creditos <= 0 or creditos > 100000:
        raise HTTPException(status_code=400, detail="creditos fuera de rango (1-100000)")
    from agent.billing import acreditar, obtener_saldo
    nuevo_saldo = await acreditar(telefono, creditos, razon)
    saldo_actual = await obtener_saldo(telefono)
    return {
        "status": "ok",
        "telefono": telefono,
        "acreditado": creditos,
        "saldo_retornado": nuevo_saldo,
        "saldo_verificado": saldo_actual,
    }


@app.get("/admin/recordatorios")
async def admin_recordatorios(request: Request, telefono: str, token: str = ""):
    """
    Diagnóstico de recordatorios en producción.
    Uso: /admin/recordatorios?telefono=15551234567 + Header Authorization: Bearer <token>
    """
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    from agent.memory import obtener_recordatorios_activos, obtener_timezone
    from datetime import datetime as dt, timedelta
    activos = await obtener_recordatorios_activos(telefono)
    offset = await obtener_timezone(telefono)
    ahora_utc = dt.utcnow()
    return {
        "telefono": telefono,
        "ahora_utc": ahora_utc.isoformat(),
        "offset_minutos": offset,
        "recordatorios_activos": activos,
        "total": len(activos),
    }


@app.get("/admin/inbound/token")
async def admin_generar_token_inbound(request: Request, telefono: str, token: str = ""):
    """
    Genera una URL de webhook inbound firmada para el usuario dado.
    El usuario pega esta URL en Zapier/Make/n8n para que servicios externos
    puedan enviarle mensajes proactivos por WhatsApp.

    Uso: GET /admin/inbound/token?telefono=15551234567 + Authorization: Bearer <admin>
    """
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    from agent.inbound_tokens import generar_token
    tok = generar_token(telefono.lstrip("+"))
    base_url = os.getenv("BASE_URL", "").rstrip("/")
    url = f"{base_url}/webhook/inbound/{tok}" if base_url else f"/webhook/inbound/{tok}"
    return {
        "telefono": telefono,
        "token": tok,
        "url_webhook": url,
        "metodo": "POST",
        "content_type": "application/json",
        "body_ejemplo": {"mensaje": "Texto que Dona reenviará al usuario"},
    }


@app.post("/webhook/inbound/{token}")
async def webhook_inbound(token: str, request: Request):
    """
    Recibe un JSON de un servicio externo (Zapier/Make/n8n) y reenvía el
    mensaje al WhatsApp del usuario asociado al token.

    El token se genera con /admin/inbound/token y es opaco para el servicio externo.

    Body JSON: {"mensaje": "texto a enviar"}
    """
    from agent.inbound_tokens import verificar_token
    telefono = verificar_token(token)
    if not telefono:
        raise HTTPException(status_code=403, detail="Token inválido")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")
    mensaje = (body or {}).get("mensaje", "").strip() if isinstance(body, dict) else ""
    if not mensaje:
        raise HTTPException(status_code=400, detail="Falta campo 'mensaje'")
    # Límite defensivo para no quemar quota con un payload gigante de un Zap mal configurado
    if len(mensaje) > 4000:
        mensaje = mensaje[:4000] + "…"
    ok = await proveedor.enviar_mensaje(telefono, mensaje)
    if not ok:
        logger.error(f"[INBOUND] Fallo enviando a {telefono[:4]}***")
        raise HTTPException(status_code=502, detail="Fallo enviando a WhatsApp")
    logger.info(f"[INBOUND] Mensaje proactivo entregado a {telefono[:4]}*** ({len(mensaje)} chars)")
    return {"status": "ok", "chars": len(mensaje)}


@app.get("/auth/google/login")
async def google_oauth_login(telefono: str):
    """
    Inicia el flujo OAuth de Google Calendar para el usuario dado.
    Redirige al usuario a la pantalla de autorización de Google.
    Uso: GET /auth/google/login?telefono=521234567890
    """
    from agent.google_calendar import esta_disponible, generar_url_oauth
    if not esta_disponible():
        raise HTTPException(
            status_code=503,
            detail="Google Calendar no está configurado (faltan GOOGLE_CLIENT_ID/SECRET)"
        )
    if not _telefono_valido(telefono):
        raise HTTPException(status_code=400, detail="Formato de teléfono inválido")
    url = generar_url_oauth(telefono)
    logger.info(f"[GOOGLE] Iniciando OAuth para {telefono}")
    return RedirectResponse(url)


@app.get("/auth/google/callback")
async def google_oauth_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):
    """
    Callback de Google OAuth.
    Google redirige aquí tras la autorización del usuario.
    Intercambia el código por tokens, los guarda y confirma por WhatsApp.
    """
    import asyncio as _asyncio
    from agent.google_calendar import intercambiar_codigo, decodificar_state

    if error:
        logger.warning(f"[GOOGLE] OAuth rechazado: {error}")
        return HTMLResponse(_html_oauth_resultado(exito=False, mensaje=f"Acceso denegado: {error}"))

    if not code or not state:
        return HTMLResponse(_html_oauth_resultado(exito=False, mensaje="Parámetros inválidos."))

    try:
        telefono = decodificar_state(state)
    except ValueError as ve:
        logger.warning(f"[GOOGLE] State OAuth rechazado: {ve}")
        return HTMLResponse(_html_oauth_resultado(
            exito=False,
            mensaje="Enlace de autorización inválido o expirado. Inicia el proceso de nuevo."
        ))
    except Exception as e:
        logger.error(f"[GOOGLE] Error decodificando state: {e}")
        return HTMLResponse(_html_oauth_resultado(exito=False, mensaje="Enlace inválido."))

    if not _telefono_valido(telefono):
        logger.warning(f"[GOOGLE] Teléfono inválido tras decodificar state")
        return HTMLResponse(_html_oauth_resultado(exito=False, mensaje="Enlace inválido."))

    exito, email = await intercambiar_codigo(code, telefono)

    if not exito:
        return HTMLResponse(_html_oauth_resultado(
            exito=False,
            mensaje=email if email else "Error al conectar con Google. Por favor intenta de nuevo."
        ))

    # Notificar al usuario por WhatsApp en background (no bloquear la respuesta HTML)
    _asyncio.create_task(_notificar_google_conectado(telefono, email))

    logger.info(f"[GOOGLE] OAuth completado para {telefono} ({email})")
    return HTMLResponse(_html_oauth_resultado(exito=True, email=email))


def _html_oauth_resultado(exito: bool, email: str = "", mensaje: str = "") -> str:
    """Página HTML mínima que se muestra al usuario tras el flujo OAuth."""
    if exito:
        email_str = f" ({email})" if email else ""
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Google Calendar conectado</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; text-align: center;
           padding: 48px 24px; background: #f9fafb; color: #111; }}
    .card {{ background: white; border-radius: 16px; padding: 40px;
             max-width: 400px; margin: 0 auto; box-shadow: 0 2px 16px #0001; }}
    h1 {{ font-size: 2rem; margin-bottom: 8px; }}
    p {{ color: #555; line-height: 1.6; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>✅ ¡Listo!</h1>
    <p>Google Calendar conectado correctamente{email_str}.</p>
    <p>Ya puedes cerrar esta pestaña y volver a WhatsApp.<br>
       Dona ahora puede leer y crear eventos en tu calendario.</p>
  </div>
</body>
</html>"""
    else:
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Error</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; text-align: center;
           padding: 48px 24px; background: #f9fafb; color: #111; }}
    .card {{ background: white; border-radius: 16px; padding: 40px;
             max-width: 400px; margin: 0 auto; box-shadow: 0 2px 16px #0001; }}
    h1 {{ font-size: 2rem; margin-bottom: 8px; }}
    p {{ color: #555; line-height: 1.6; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>❌ Error</h1>
    <p>{mensaje or "No se pudo conectar Google Calendar."}</p>
    <p>Por favor cierra esta pestaña y pídele a Dona el enlace de nuevo.</p>
  </div>
</body>
</html>"""


async def _notificar_google_conectado(telefono: str, email: str):
    """Envía un WhatsApp de confirmación cuando el usuario conecta Google.

    El mensaje lista las capacidades que quedan habilitadas con los scopes
    actuales (Calendar + Gmail + Sheets + Drive + Tasks + Contacts). Se
    mantiene relativamente breve — los ejemplos están pensados para que el
    usuario pueda copiarlos y probarlos.
    """
    try:
        email_str = f" ({email})" if email else ""
        mensaje = (
            f"¡Tu Google está conectado{email_str}! 🔗\n\n"
            "Ahora puedo ayudarte con:\n"
            "📅 *Calendario* — \"qué tengo hoy?\", \"agéndame reunión mañana 3pm\"\n"
            "✉️ *Correo* — \"lee mis correos no leídos\", \"mándale un correo a Juan\"\n"
            "✅ *Tareas* — \"agrega tarea llamar al banco\", \"qué tengo pendiente?\"\n"
            "📊 *Sheets* — \"registra en mi hoja\", \"qué hojas tengo\"\n"
            "📁 *Drive* — respaldo automático de tus exports CSV\n"
            "👥 *Contactos* — te busco por nombre al escribir correos\n\n"
            "Prueba con *\"dona ayuda\"* para ver todo lo que sé hacer."
        )
        await proveedor.enviar_mensaje(telefono, mensaje)
    except Exception as e:
        logger.error(f"_notificar_google_conectado error para {telefono}: {e}")


@app.post("/debug")
async def debug_handler(request: Request):
    """Captura el body crudo de cualquier request — para diagnosticar Whapi. Solo en dev."""
    if ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not found")
    body = await request.body()
    headers = dict(request.headers)
    logger.info(f"DEBUG body: {body.decode('utf-8', errors='replace')}")
    logger.info(f"DEBUG headers: {headers}")
    return {"status": "ok", "body": body.decode("utf-8", errors="replace")}


async def _mensaje_ya_procesado(mensaje_id: str, telefono: str) -> bool:
    """
    Verifica si un mensaje ya fue procesado. Usa DB con fallback a memoria.
    Registra el mensaje como procesado si es nuevo.
    """
    # Check memoria primero (rápido, cubre el caso de mensajes en ráfaga)
    if mensaje_id in _mensajes_procesados_mem:
        return True

    try:
        from agent.memory import async_session, MensajeProcesado
        from sqlalchemy import select as _select
        async with async_session() as session:
            result = await session.execute(
                _select(MensajeProcesado).where(MensajeProcesado.mensaje_id == mensaje_id)
            )
            if result.scalar_one_or_none():
                _mensajes_procesados_mem[mensaje_id] = True
                return True

            # Registrar como procesado
            session.add(MensajeProcesado(mensaje_id=mensaje_id, telefono=telefono))
            await session.commit()
    except Exception as e:
        logger.debug(f"[DEDUP] Error DB, usando solo memoria: {e}")

    # Registrar en memoria también
    _mensajes_procesados_mem[mensaje_id] = True
    if len(_mensajes_procesados_mem) > _MAX_IDS_DEDUP:
        _mensajes_procesados_mem.popitem(last=False)

    return False


async def procesar_webhook(request: Request):
    """Lógica compartida: parsea el mensaje, llama a Claude y responde."""
    import asyncio as _asyncio

    # ── Parseo del webhook (único punto que puede fallar antes de tener telefono) ──
    try:
        mensajes = await proveedor.parsear_webhook(request)
    except Exception as _e_parse:
        logger.error(f"[WEBHOOK] Error parseando payload: {type(_e_parse).__name__}: {_e_parse}", exc_info=True)
        return {"status": "error", "detail": "parse_error"}

    for msg in mensajes:
        # ── Cada mensaje se procesa de forma independiente ────────────────────
        # Un fallo en un mensaje NO debe bloquear los mensajes siguientes.
        try:
            if msg.es_propio:
                logger.debug(f"[SKIP] Mensaje propio ignorado: {msg.telefono}")
                continue

            # ── Deduplicación: ignorar si ya procesamos este mensaje_id ─────
            if msg.mensaje_id:
                if await _mensaje_ya_procesado(msg.mensaje_id, msg.telefono):
                    logger.debug(f"[DEDUP] Mensaje duplicado ignorado: {msg.mensaje_id} ({msg.telefono})")
                    continue

            # ── Rate limiting: máx 10 mensajes por minuto por número ──
            if not _dentro_de_limite(msg.telefono):
                logger.warning(f"[RATE] Límite excedido para {msg.telefono} — mensaje ignorado")
                continue

            # Si es una nota de voz, transcribirla primero
            _es_audio = False
            if msg.audio_id and not msg.texto:
                _proveedor_nombre = os.getenv("WHATSAPP_PROVIDER", "whapi").lower()
                logger.info(f"Transcribiendo nota de voz de {msg.telefono} (proveedor: {_proveedor_nombre})...")
                if _proveedor_nombre == "meta":
                    texto_transcrito = await procesar_audio_meta(msg.audio_id, msg.audio_mime)
                else:
                    token = os.getenv("WHAPI_TOKEN", "")
                    texto_transcrito = await procesar_audio_whapi(msg.audio_id, msg.audio_mime, token)
                if not texto_transcrito:
                    await proveedor.enviar_mensaje(
                        msg.telefono,
                        "No pude entender tu nota de voz 😅 ¿Puedes escribirlo?"
                    )
                    continue
                msg.texto = texto_transcrito
                _es_audio = True
                logger.info(f"Nota de voz transcrita: \"{texto_transcrito}\"")

            # ── Imagen + caption creativo (bg_remove | video) → preparar ──
            # Se evalúa ANTES de Vision: si el caption es un comando creativo
            # no tiene sentido gastar Claude Vision describiendo la imagen.
            # Orden: bg_remove es más específico ("quita el fondo"), video
            # genérico después ("hazme un video de este producto...").
            if msg.image_id and msg.image_caption:
                try:
                    from agent.creativos.comandos import (
                        es_comando_bg_remove, texto_bg_remove_preview,
                        es_comando_video, parsear_video, texto_video_preview,
                    )
                    if es_comando_bg_remove(msg.image_caption):
                        from agent.vision import descargar_imagen_meta
                        from agent.creativos.bg_remove import preparar_bg_remove_desde_bytes

                        img_bytes, img_mime = await descargar_imagen_meta(msg.image_id)
                        if not img_bytes:
                            await proveedor.enviar_mensaje(
                                msg.telefono,
                                "No pude descargar tu imagen 😅 ¿Puedes reenviarla?",
                            )
                            continue
                        preview = await preparar_bg_remove_desde_bytes(
                            msg.telefono, img_bytes, img_mime or "image/jpeg",
                        )
                        await proveedor.enviar_mensaje(
                            msg.telefono, texto_bg_remove_preview(preview),
                        )
                        logger.info(
                            f"[CMD] preparar_bg_remove (desde caption) → {msg.telefono} "
                            f"costo={preview['costo_creditos']}"
                        )
                        continue

                    if es_comando_video(msg.image_caption):
                        from agent.vision import descargar_imagen_meta
                        from agent.creativos.video import preparar_video_desde_bytes

                        datos_v = parsear_video(msg.image_caption)
                        prompt_v = (datos_v.get("prompt") or "").strip()
                        if not prompt_v:
                            # Caption tipo "haz un video" sin más — usamos un
                            # prompt genérico que le dice al modelo que
                            # mantenga el sujeto de la imagen en movimiento.
                            prompt_v = "Anima esta imagen en escenas naturales y cinematográficas"

                        img_bytes, img_mime = await descargar_imagen_meta(msg.image_id)
                        if not img_bytes:
                            await proveedor.enviar_mensaje(
                                msg.telefono,
                                "No pude descargar tu imagen 😅 ¿Puedes reenviarla?",
                            )
                            continue

                        res = await preparar_video_desde_bytes(
                            msg.telefono, prompt_v, img_bytes, img_mime or "image/jpeg",
                        )
                        if res.get("estado") == "source_no_servible":
                            await proveedor.enviar_mensaje(
                                msg.telefono,
                                "Guardé tu imagen pero está en almacenamiento local y "
                                "no puedo usarla como referencia externa. Configura R2 "
                                "o reenvíala y vuelve a intentar.",
                            )
                            continue
                        await proveedor.enviar_mensaje(
                            msg.telefono, texto_video_preview(res),
                        )
                        logger.info(
                            f"[CMD] preparar_video (desde caption con imagen) → "
                            f"{msg.telefono} costo={res['costo_creditos']}"
                        )
                        continue
                except Exception as _e_bg:
                    logger.error(f"[CMD] Error en comando creativo desde caption: {_e_bg}")

            # Si es una imagen, procesarla con visión
            _es_imagen = False
            if msg.image_id and not msg.texto:
                logger.info(f"Procesando imagen de {msg.telefono}...")
                from agent.vision import procesar_imagen
                texto_imagen = await procesar_imagen(msg.image_id, msg.image_caption)
                if not texto_imagen:
                    await proveedor.enviar_mensaje(
                        msg.telefono,
                        "No pude analizar la imagen 😅 ¿Puedes describirla o escribir lo que necesitas?"
                    )
                    continue
                msg.texto = texto_imagen
                _es_imagen = True  # Marcar para no avanzar el onboarding
                logger.info(f"Imagen procesada: \"{texto_imagen[:80]}\"")

            if not msg.texto:
                logger.warning(f"[SKIP] Mensaje sin texto ignorado silenciosamente: tel={msg.telefono} audio_id={msg.audio_id}")
                continue

            metricas.registrar_mensaje()
            logger.info(f"Mensaje de {msg.telefono}: {msg.texto[:120]}")

            # ── Auto-popular nombre desde Google Contacts (best-effort, una vez) ──
            # Si el usuario no tiene nombre aún, intentar resolverlo desde sus propios
            # contactos (algunos tienen una entrada "Me" / "Yo"). Silencioso si no hay
            # match o si aún no autorizó Google — el onboarding tradicional lo cubrirá.
            try:
                from agent.memory import obtener_onboarding, guardar_onboarding
                _ob = await obtener_onboarding(msg.telefono)
                if not _ob or not (_ob.get("nombre") or "").strip():
                    from agent.google_contacts import buscar_por_telefono
                    _match = await buscar_por_telefono(msg.telefono, msg.telefono)
                    if _match and _match.get("nombre"):
                        await guardar_onboarding(msg.telefono, nombre=_match["nombre"])
                        logger.info(f"[CONTACTS] Auto-populated nombre='{_match['nombre']}' para {msg.telefono}")
            except Exception as _e_ac:
                logger.debug(f"[CONTACTS] auto-populate skip ({type(_e_ac).__name__}): {_e_ac}")

            # ── Dona 2.0: Confirmaciones pendientes (SafeModule) ─────────
            try:
                from enhanced.safe_module import tiene_confirmacion_pendiente
                if tiene_confirmacion_pendiente(msg.telefono):
                    from enhanced.safe_module import SafeModule
                    _sm = SafeModule()
                    _procesado, _resp_conf = await _sm.procesar_confirmacion(msg.telefono, msg.texto)
                    if _procesado:
                        await proveedor.enviar_mensaje(msg.telefono, _resp_conf)
                        logger.info(f"[ENHANCED] Confirmación procesada para {msg.telefono}")
                        continue
            except Exception as _e_conf:
                logger.error(f"[ENHANCED] Error en confirmación: {_e_conf}")

            # ── Dona 2.0: Comandos del sistema ──────────────────────────
            _texto_lower = msg.texto.strip().lower()
            # Normalizar: quitar espacios entre ! y la palabra, ej "! diagnostic" → "!diagnostic"
            _texto_cmd = _texto_lower.replace(" ", "")

            # !help → muestra todos los comandos disponibles
            if _texto_cmd in ("!help", "!ayuda", "!comandos"):
                from enhanced.safe_module import _es_owner
                if _es_owner(msg.telefono):
                    _help = (
                        "*Comandos Dona 2.0 (admin):*\n\n"
                        "*Diagnóstico*\n"
                        "  !diagnostic — Reporte técnico completo\n"
                        "  dona status — Vista simplificada\n\n"
                        "*Ejecución*\n"
                        "  !actions — Lista acciones correctivas\n"
                        "  !exec <acción> — Ejecutar con confirmación\n\n"
                        "*Insights*\n"
                        "  !insights — Reporte semanal bajo demanda\n\n"
                        "*Sistemas*\n"
                        "  catálogo — Ver sistemas disponibles\n"
                        "  mis sistemas — Ver tus sistemas activos\n\n"
                        "*Otros*\n"
                        "  !help — Este mensaje"
                    )
                else:
                    _help = (
                        "*Comandos disponibles:*\n\n"
                        "  dona status — Estado del sistema\n"
                        "  catálogo — Ver sistemas disponibles\n"
                        "  mis sistemas — Ver tus sistemas activos\n"
                        "  borrar mis datos — Eliminar todos tus datos\n\n"
                        "También puedes activar sistemas con lenguaje natural:\n"
                        '"quiero organizar mis gastos"\n'
                        '"necesito un tracker de hábitos"'
                    )
                await proveedor.enviar_mensaje(msg.telefono, _help)
                continue
            if _texto_cmd in ("!diagnostic", "!diagnostico", "!diag"):
                from enhanced.diagnostics import diagnostico
                from enhanced.safe_module import _es_owner
                if _es_owner(msg.telefono):
                    checks = await diagnostico.ejecutar_diagnostico(msg.telefono)
                    resp_diag = diagnostico.formatear_vista_owner(checks)
                else:
                    resp_diag = "Este comando requiere permisos de administrador."
                await proveedor.enviar_mensaje(msg.telefono, resp_diag)
                continue
            # "dona status" → vista simplificada para cualquier usuario
            if _texto_cmd in ("donastatus", "donaestado", "donadiagnostico", "donadiagnóstico") or \
               _texto_lower in ("dona status", "dona estado", "dona diagnóstico", "dona diagnostico"):
                from enhanced.diagnostics import diagnostico
                checks = await diagnostico.ejecutar_diagnostico(msg.telefono)
                resp_diag = diagnostico.formatear_vista_usuario(checks)
                await proveedor.enviar_mensaje(msg.telefono, resp_diag)
                continue

            # ── Dona 2.0: Ejecución con supervisión (!actions, !exec) ──
            if _texto_cmd in ("!actions", "!acciones"):
                from enhanced.execution import ejecucion
                from enhanced.safe_module import _es_owner
                if _es_owner(msg.telefono):
                    await proveedor.enviar_mensaje(msg.telefono, ejecucion.listar_acciones())
                else:
                    await proveedor.enviar_mensaje(msg.telefono, "Este comando requiere permisos de administrador.")
                continue
            if _texto_cmd.startswith("!exec") or _texto_lower.startswith("!exec "):
                from enhanced.execution import ejecucion
                from enhanced.safe_module import _es_owner
                if not _es_owner(msg.telefono):
                    await proveedor.enviar_mensaje(msg.telefono, "Este comando requiere permisos de administrador.")
                    continue
                # Extraer nombre de la acción: "!exec limpiar_rate_limit" → "limpiar_rate_limit"
                _partes = msg.texto.strip().split(maxsplit=1)
                if len(_partes) < 2:
                    await proveedor.enviar_mensaje(msg.telefono, "Uso: *!exec <nombre_accion>*\nEscribe *!actions* para ver las disponibles.")
                    continue
                _nombre_accion = _partes[1].strip().lower()
                resp_exec = await ejecucion.iniciar_ejecucion(msg.telefono, _nombre_accion)
                await proveedor.enviar_mensaje(msg.telefono, resp_exec)
                continue
            # ── Dona 2.0: Reporte semanal bajo demanda ───────────────────
            if _texto_cmd in ("!insights", "!reporte"):
                from enhanced.insights import insights as _insights_mod
                from enhanced.safe_module import _es_owner
                if _es_owner(msg.telefono):
                    reporte = await _insights_mod.generar_reporte_semanal()
                    await proveedor.enviar_mensaje(msg.telefono, reporte)
                else:
                    await proveedor.enviar_mensaje(msg.telefono, "Este comando requiere permisos de administrador.")
                continue

            # ── Exportar datos (CCPA/CPRA derecho de portabilidad) ───────
            if _texto_lower in (
                "dona exportar datos", "exportar mis datos", "dona export datos",
                "dona export my data", "export my data",
            ):
                try:
                    from agent.memory import exportar_datos_usuario
                    export = await exportar_datos_usuario(msg.telefono)
                    total = export.get("_total_registros", 0)
                    _msg_export = (
                        f"📦 *Export de tus datos (CCPA §1798.100)*\n\n"
                        f"Total: {total} registros en {len(export)-1} categorías.\n\n"
                        f"Por el tamaño, te enviaremos el archivo JSON completo "
                        f"al email asociado en las próximas 24 horas. "
                        f"Si no lo recibes, escríbenos a "
                        f"{os.getenv('LEGAL_EMAIL', 'privacy@dona.ai')}."
                    )
                    logger.info(f"[PRIVACY] Export solicitado por {msg.telefono}: {total} registros")
                except Exception as _e_exp:
                    logger.error(f"[PRIVACY] Error exportando datos: {_e_exp}")
                    _msg_export = (
                        "No pudimos generar el export automáticamente. "
                        f"Escríbenos a {os.getenv('LEGAL_EMAIL', 'privacy@dona.ai')} "
                        "y responderemos dentro de 45 días."
                    )
                await proveedor.enviar_mensaje(msg.telefono, _msg_export)
                continue

            # ── Borrado de datos del usuario (derecho al olvido) ─────────
            if _texto_cmd in ("!borrarmisdatos", "!deletemydata") or \
               _texto_lower in (
                   "!borrar mis datos", "borrar mis datos", "eliminar mis datos",
                   "dona borrar mis datos", "dona eliminar mis datos",
               ):
                from enhanced.safe_module import tiene_confirmacion_pendiente as _tcp
                # Usar flujo de confirmación CONFIRMAR
                if _texto_lower == "confirmar":
                    pass  # Se maneja arriba en confirmaciones pendientes
                else:
                    # Pedir confirmación
                    _aviso = (
                        "⚠️ *Esto eliminará TODOS tus datos de Dona:*\n\n"
                        "• Mensajes e historial\n"
                        "• Recordatorios y tareas\n"
                        "• Notas y listas\n"
                        "• Conexión de Google Calendar/Gmail\n"
                        "• Sistemas activos\n"
                        "• Perfil y preferencias\n\n"
                        "Esta acción es *irreversible*.\n\n"
                        "Escribe *CONFIRMAR* para proceder o cualquier otra cosa para cancelar."
                    )
                    from enhanced.safe_module import AccionConfirmable, NivelPermiso, SafeModule
                    _sm_borrar = SafeModule()
                    _sm_borrar.nombre = "borrado_datos"

                    async def _ejecutar_borrado(_tel=msg.telefono):
                        from agent.memory import borrar_datos_usuario
                        conteos = await borrar_datos_usuario(_tel)
                        total = sum(v for v in conteos.values() if isinstance(v, int))
                        return {
                            "exito": True,
                            "mensaje": f"Todos tus datos han sido eliminados ({total} registros). Adiós y gracias por usar Dona. 💙",
                        }

                    accion = AccionConfirmable(
                        nombre="borrar_datos_usuario",
                        descripcion="Eliminar todos los datos del usuario",
                        nivel=NivelPermiso.USUARIO,
                        ejecutar=_ejecutar_borrado,
                    )
                    resp_borrar = await _sm_borrar.solicitar_confirmacion(msg.telefono, accion)
                    await proveedor.enviar_mensaje(msg.telefono, resp_borrar)
                    continue

            # ── Dona 2.0: Catálogo de sistemas ─────────────────────────
            try:
                from enhanced.nlp_detector import es_consulta_catalogo
                if es_consulta_catalogo(msg.texto):
                    from enhanced.catalog import obtener_catalogo_activo
                    from enhanced.system_manager import gestor_sistemas
                    catalogo = await obtener_catalogo_activo()
                    resp_cat = gestor_sistemas.formatear_catalogo(catalogo)
                    await proveedor.enviar_mensaje(msg.telefono, resp_cat)
                    continue

                # "mis sistemas" → listar sistemas activos del usuario
                if _texto_lower in ("mis sistemas", "mis sistemas activos"):
                    from enhanced.system_manager import gestor_sistemas
                    resp_sis = await gestor_sistemas.listar_sistemas_usuario(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, resp_sis)
                    continue
            except Exception as _e_cat:
                logger.error(f"[ENHANCED] Error en catálogo/sistemas: {_e_cat}")

            # ── TCPA opt-out (STOP/UNSUBSCRIBE/BAJA) — PRIORIDAD MÁXIMA ────────
            # Ley federal de EEUU requiere respuesta inmediata a opt-out.
            # Se procesa ANTES que cualquier otro flujo (onboarding, comandos, IA).
            if es_comando_stop_tcpa(msg.texto):
                try:
                    respuesta_stop = await manejar_stop_tcpa(msg.telefono)
                except Exception as _e_stop:
                    logger.error(f"[TCPA] Error en opt-out: {_e_stop}")
                    respuesta_stop = "Has sido dado de baja. No te enviaremos más mensajes proactivos."
                await proveedor.enviar_mensaje(msg.telefono, respuesta_stop)
                logger.info(f"[TCPA] STOP → {msg.telefono}")
                continue

            if es_comando_start_tcpa(msg.texto):
                try:
                    respuesta_start = await manejar_start_tcpa(msg.telefono)
                except Exception as _e_start:
                    logger.error(f"[TCPA] Error en re-opt-in: {_e_start}")
                    respuesta_start = "Proactividad reactivada."
                await proveedor.enviar_mensaje(msg.telefono, respuesta_start)
                logger.info(f"[TCPA] START → {msg.telefono}")
                continue

            # ── Recordatorio en lenguaje natural ("recuérdame mañana 9am que...") ──
            try:
                from agent.reminders_nl import parsear as _parsear_nl
                from agent.memory import obtener_timezone, guardar_recordatorio
                _offset = await obtener_timezone(msg.telefono) or 0
                _rec = _parsear_nl(msg.texto, offset_tz_minutos=_offset)
            except Exception:
                _rec = None
            if _rec:
                fecha_utc, mensaje_rec = _rec
                try:
                    await guardar_recordatorio(
                        telefono=msg.telefono,
                        mensaje=mensaje_rec,
                        fecha_hora=fecha_utc,
                        offset_tz_minutos=_offset,
                    )
                    from datetime import timedelta as _td
                    fecha_local = fecha_utc + _td(minutes=_offset)
                    confirm = (
                        f"Listo ✅ Te recuerdo: \"{mensaje_rec}\"\n"
                        f"📅 {fecha_local.strftime('%d/%m/%Y %H:%M')} (tu hora local)"
                    )
                    await proveedor.enviar_mensaje(msg.telefono, confirm)
                    logger.info(f"[REMINDER_NL] '{mensaje_rec}' para {fecha_utc.isoformat()} → {msg.telefono}")
                except Exception as _e_rec:
                    logger.error(f"[REMINDER_NL] Error guardando: {_e_rec}")
                    await proveedor.enviar_mensaje(
                        msg.telefono,
                        "No pude guardar el recordatorio. ¿Puedes intentar de nuevo?"
                    )
                continue

            # ── Comandos informativos ("dona ayuda", "dona estado") ───────
            try:
                from agent.comandos_info import (
                    es_comando_ayuda,
                    es_comando_estado,
                    generar_texto_ayuda,
                    generar_texto_estado,
                )
                if es_comando_ayuda(msg.texto):
                    texto_ayuda = await generar_texto_ayuda(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, texto_ayuda)
                    logger.info(f"[CMD] ayuda → {msg.telefono}")
                    continue
                if es_comando_estado(msg.texto):
                    texto_estado = await generar_texto_estado(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, texto_estado)
                    logger.info(f"[CMD] estado → {msg.telefono}")
                    continue
            except Exception as _e_info:
                logger.error(f"[CMD] Error en comando informativo: {_e_info}")

            # ── Comandos de billing ("dona saldo", "dona recargar", "dona mis assets") ──
            try:
                from agent.billing_commands import (
                    es_comando_saldo, es_comando_recargar, es_comando_mis_assets,
                    texto_saldo, texto_recargar, texto_mis_assets,
                )
                if es_comando_saldo(msg.texto):
                    await proveedor.enviar_mensaje(msg.telefono, await texto_saldo(msg.telefono))
                    logger.info(f"[CMD] saldo → {msg.telefono}")
                    continue
                if es_comando_recargar(msg.texto):
                    await proveedor.enviar_mensaje(msg.telefono, await texto_recargar(msg.telefono))
                    logger.info(f"[CMD] recargar → {msg.telefono}")
                    continue
                if es_comando_mis_assets(msg.texto):
                    await proveedor.enviar_mensaje(msg.telefono, await texto_mis_assets(msg.telefono))
                    logger.info(f"[CMD] mis_assets → {msg.telefono}")
                    continue
            except Exception as _e_bil:
                logger.error(f"[CMD] Error en comando billing: {_e_bil}")

            # ── Comandos creativos ("dona imagen <prompt>" + confirmar/cancelar) ──
            try:
                from agent.creativos.comandos import (
                    es_comando_imagen, parsear_imagen,
                    es_comando_confirmar, es_comando_cancelar,
                    es_solicitud_imagen_sin_sujeto,
                    es_comando_bg_remove_ultima,
                    es_comando_voz, parsear_voz,
                    es_comando_documento, parsear_documento,
                    es_comando_video, parsear_video,
                    es_comando_video_avatar, parsear_video_avatar,
                    texto_preview, texto_encolada, texto_sin_pendiente, texto_cancelada,
                    texto_documento_preview, texto_documento_encolada,
                    texto_video_preview, texto_video_encolada,
                    texto_video_avatar_preview, texto_video_avatar_encolada,
                    texto_pedir_sujeto,
                    texto_bg_remove_preview, texto_bg_remove_encolada,
                    texto_bg_remove_sin_imagen, texto_bg_remove_no_servible,
                    texto_voz_preview, texto_voz_encolada,
                    es_confirmar_inequivoco, es_cancelar_inequivoco,
                    texto_sin_nada_que_confirmar, texto_sin_nada_que_cancelar,
                    es_comando_ajustar, parsear_ajustar,
                    texto_video_ajustado, texto_imagen_ajustada, texto_voz_ajustada,
                )
                from agent.creativos.imagen import (
                    preparar_imagen, confirmar_imagen, cancelar_imagen,
                    ajustar_imagen, obtener_pendiente,
                )
                from agent.creativos.bg_remove import (
                    preparar_bg_remove_desde_ultimo_asset,
                    confirmar_bg_remove, cancelar_bg_remove,
                    obtener_pendiente as obtener_pendiente_bg,
                )
                from agent.creativos.voz import (
                    preparar_voz, confirmar_voz, cancelar_voz,
                    ajustar_voz, obtener_pendiente as obtener_pendiente_voz,
                )
                from agent.creativos.pdf import (
                    preparar_documento, confirmar_documento, cancelar_documento,
                    obtener_pendiente as obtener_pendiente_doc,
                )
                from agent.creativos.video import (
                    preparar_video, confirmar_video, cancelar_video,
                    ajustar_video,
                    obtener_pendiente as obtener_pendiente_video,
                )
                from agent.creativos.video_avatar import (
                    preparar_video_avatar, confirmar_video_avatar, cancelar_video_avatar,
                    obtener_pendiente as obtener_pendiente_video_avatar,
                )

                # Voz (TTS) — chequear ANTES de es_comando_imagen porque "hazme
                # un audio de..." podría engancharse en el match de imagen.
                if es_comando_voz(msg.texto):
                    datos_voz = parsear_voz(msg.texto)
                    if datos_voz["texto"]:
                        preview_voz = await preparar_voz(msg.telefono, datos_voz["texto"])
                        await proveedor.enviar_mensaje(msg.telefono, texto_voz_preview(preview_voz))
                        logger.info(f"[CMD] preparar_voz → {msg.telefono} costo={preview_voz['costo_creditos']} chars={preview_voz['chars']}")
                        continue

                # Video con avatar (HeyGen) — chequear ANTES de video genérico
                # (avatar pide `avatar|presentador|locutor`, más específico).
                if es_comando_video_avatar(msg.texto):
                    datos_va = parsear_video_avatar(msg.texto)
                    if datos_va["texto"]:
                        try:
                            preview_va = await preparar_video_avatar(
                                msg.telefono, datos_va["texto"],
                            )
                            await proveedor.enviar_mensaje(
                                msg.telefono, texto_video_avatar_preview(preview_va),
                            )
                            logger.info(
                                f"[CMD] preparar_video_avatar → {msg.telefono} "
                                f"chars={preview_va['chars']} costo={preview_va['costo_creditos']}"
                            )
                        except Exception as _e_va:
                            logger.error(f"[CMD] Error preparando video avatar: {_e_va}")
                            await proveedor.enviar_mensaje(
                                msg.telefono,
                                "No pude armar el video con avatar. Prueba así:\n"
                                "_dona video con avatar diciendo: Hola, soy Juan..._",
                            )
                        continue

                # Video genérico (Replicate) — ANTES de documento/imagen.
                if es_comando_video(msg.texto):
                    datos_v = parsear_video(msg.texto)
                    if datos_v["prompt"]:
                        try:
                            preview_v = await preparar_video(msg.telefono, datos_v["prompt"])
                            await proveedor.enviar_mensaje(
                                msg.telefono, texto_video_preview(preview_v),
                            )
                            logger.info(
                                f"[CMD] preparar_video → {msg.telefono} "
                                f"costo={preview_v['costo_creditos']}"
                            )
                        except Exception as _e_v:
                            logger.error(f"[CMD] Error preparando video: {_e_v}")
                            await proveedor.enviar_mensaje(
                                msg.telefono,
                                "No pude preparar el video. Prueba así:\n"
                                "_dona video de un gato persa mirando la lluvia_",
                            )
                        continue

                # Documento (factura / presupuesto / recibo) — ANTES de imagen
                # porque "hazme una factura" podría enganchar en la regex de imagen.
                if es_comando_documento(msg.texto):
                    datos_doc = parsear_documento(msg.texto)
                    if datos_doc["tipo"] and datos_doc["cuerpo"]:
                        try:
                            preview_doc = await preparar_documento(
                                msg.telefono, datos_doc["tipo"], datos_doc["cuerpo"],
                            )
                            await proveedor.enviar_mensaje(
                                msg.telefono, texto_documento_preview(preview_doc),
                            )
                            logger.info(
                                f"[CMD] preparar_documento → {msg.telefono} "
                                f"tipo={datos_doc['tipo']} items={preview_doc['items_count']} "
                                f"total={preview_doc['total']}"
                            )
                        except Exception as _e_doc:
                            logger.error(f"[CMD] Error preparando documento: {_e_doc}")
                            await proveedor.enviar_mensaje(
                                msg.telefono,
                                "No pude armar el documento con esos datos. Prueba así:\n"
                                "_dona factura para Juan Pérez, consultoría SEO $500_",
                            )
                        continue

                # bg_remove sobre última imagen — chequear ANTES de es_comando_imagen
                # (la regex de imagen es permisiva y podría engullir este intent).
                if es_comando_bg_remove_ultima(msg.texto):
                    res = await preparar_bg_remove_desde_ultimo_asset(msg.telefono)
                    if res.get("estado") == "sin_imagen":
                        await proveedor.enviar_mensaje(msg.telefono, texto_bg_remove_sin_imagen())
                    elif res.get("estado") == "source_no_servible":
                        await proveedor.enviar_mensaje(msg.telefono, texto_bg_remove_no_servible())
                    else:
                        await proveedor.enviar_mensaje(msg.telefono, texto_bg_remove_preview(res))
                    logger.info(f"[CMD] preparar_bg_remove (desde última) → {msg.telefono} estado={res.get('estado','ok')}")
                    continue

                if es_comando_imagen(msg.texto):
                    datos = parsear_imagen(msg.texto)
                    preview = await preparar_imagen(
                        msg.telefono,
                        prompt=datos["prompt"],
                        calidad=datos["calidad"],
                        aspect_ratio=datos["aspect_ratio"],
                    )
                    await proveedor.enviar_mensaje(msg.telefono, texto_preview(preview))
                    logger.info(f"[CMD] preparar_imagen → {msg.telefono} costo={preview['costo_creditos']}")
                    continue

                # Solicitud de imagen sin sujeto ("genera una imagen", "dibuja") →
                # preguntamos de qué, en lugar de delegar al LLM (que tiende a negar).
                if es_solicitud_imagen_sin_sujeto(msg.texto):
                    await proveedor.enviar_mensaje(msg.telefono, texto_pedir_sujeto())
                    logger.info(f"[CMD] solicitud_imagen_sin_sujeto → {msg.telefono}")
                    continue

                # confirmar/cancelar sólo aplican si HAY pendiente — si no, dejamos
                # que el mensaje caiga al flujo normal (LLM) para no consumir 'sí'
                # que el usuario estaba diciendo a otra cosa.
                _pend = obtener_pendiente(msg.telefono)
                _pend_bg = obtener_pendiente_bg(msg.telefono)
                _pend_voz = obtener_pendiente_voz(msg.telefono)
                _pend_doc = obtener_pendiente_doc(msg.telefono)
                _pend_video = obtener_pendiente_video(msg.telefono)
                _pend_video_avatar = obtener_pendiente_video_avatar(msg.telefono)

                # Pendiente de video avatar (HeyGen) — precedencia alta.
                if _pend_video_avatar and es_comando_confirmar(msg.texto):
                    resultado = await confirmar_video_avatar(msg.telefono)
                    if resultado["estado"] == "ok":
                        await proveedor.enviar_mensaje(
                            msg.telefono,
                            texto_video_avatar_encolada(resultado["job_id"]),
                        )
                    elif resultado["estado"] == "saldo_insuficiente":
                        await proveedor.enviar_mensaje(msg.telefono, resultado["mensaje"])
                    else:
                        await proveedor.enviar_mensaje(msg.telefono, texto_sin_pendiente())
                    logger.info(f"[CMD] confirmar_video_avatar → {msg.telefono} estado={resultado['estado']}")
                    continue
                if _pend_video_avatar and es_comando_cancelar(msg.texto):
                    cancelar_video_avatar(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, texto_cancelada())
                    logger.info(f"[CMD] cancelar_video_avatar → {msg.telefono}")
                    continue

                # Ajuste del pendiente (video/imagen/voz) — antes que confirmar,
                # para que "ajustar: ..." no caiga en el flujo normal. Se rutea
                # por tipo de pendiente activo (sólo hay uno por teléfono, ver
                # cancelar_otros_pendientes).
                if (_pend_video or _pend or _pend_voz) and es_comando_ajustar(msg.texto):
                    datos_adj = parsear_ajustar(msg.texto)
                    nueva_idea = (datos_adj.get("nueva_idea") or "").strip()
                    if not nueva_idea:
                        await proveedor.enviar_mensaje(
                            msg.telefono,
                            "Decime cómo querés ajustarlo. Ej: *ajustar: plano aéreo al atardecer con cámara lenta*",
                        )
                        continue
                    if _pend_video:
                        resultado = await ajustar_video(msg.telefono, nueva_idea)
                        render = texto_video_ajustado
                        etiqueta = "video"
                    elif _pend:
                        resultado = await ajustar_imagen(msg.telefono, nueva_idea)
                        render = texto_imagen_ajustada
                        etiqueta = "imagen"
                    else:
                        resultado = await ajustar_voz(msg.telefono, nueva_idea)
                        render = texto_voz_ajustada
                        etiqueta = "voz"
                    if resultado.get("estado") == "ok":
                        await proveedor.enviar_mensaje(msg.telefono, render(resultado))
                    else:
                        await proveedor.enviar_mensaje(msg.telefono, texto_sin_pendiente())
                    logger.info(f"[CMD] ajustar_{etiqueta} → {msg.telefono} estado={resultado.get('estado')}")
                    continue

                # Pendiente de video (Replicate) — precedencia alta.
                if _pend_video and es_comando_confirmar(msg.texto):
                    resultado = await confirmar_video(msg.telefono)
                    if resultado["estado"] == "ok":
                        await proveedor.enviar_mensaje(
                            msg.telefono,
                            texto_video_encolada(resultado["job_id"]),
                        )
                    elif resultado["estado"] == "saldo_insuficiente":
                        await proveedor.enviar_mensaje(msg.telefono, resultado["mensaje"])
                    else:
                        await proveedor.enviar_mensaje(msg.telefono, texto_sin_pendiente())
                    logger.info(f"[CMD] confirmar_video → {msg.telefono} estado={resultado['estado']}")
                    continue
                if _pend_video and es_comando_cancelar(msg.texto):
                    cancelar_video(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, texto_cancelada())
                    logger.info(f"[CMD] cancelar_video → {msg.telefono}")
                    continue

                # Pendiente de documento tiene precedencia (flujo específico).
                if _pend_doc and es_comando_confirmar(msg.texto):
                    resultado = await confirmar_documento(msg.telefono)
                    if resultado["estado"] == "ok":
                        await proveedor.enviar_mensaje(
                            msg.telefono,
                            texto_documento_encolada(resultado["job_id"], resultado["tipo"]),
                        )
                    elif resultado["estado"] == "saldo_insuficiente":
                        await proveedor.enviar_mensaje(msg.telefono, resultado["mensaje"])
                    else:
                        await proveedor.enviar_mensaje(msg.telefono, texto_sin_pendiente())
                    logger.info(f"[CMD] confirmar_documento → {msg.telefono} estado={resultado['estado']}")
                    continue
                if _pend_doc and es_comando_cancelar(msg.texto):
                    cancelar_documento(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, texto_cancelada())
                    logger.info(f"[CMD] cancelar_documento → {msg.telefono}")
                    continue

                # Pendiente de voz tiene precedencia (flujo específico).
                if _pend_voz and es_comando_confirmar(msg.texto):
                    resultado = await confirmar_voz(msg.telefono)
                    if resultado["estado"] == "ok":
                        await proveedor.enviar_mensaje(msg.telefono, texto_voz_encolada(resultado["job_id"]))
                    elif resultado["estado"] == "saldo_insuficiente":
                        await proveedor.enviar_mensaje(msg.telefono, resultado["mensaje"])
                    else:
                        await proveedor.enviar_mensaje(msg.telefono, texto_sin_pendiente())
                    logger.info(f"[CMD] confirmar_voz → {msg.telefono} estado={resultado['estado']}")
                    continue
                if _pend_voz and es_comando_cancelar(msg.texto):
                    cancelar_voz(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, texto_cancelada())
                    logger.info(f"[CMD] cancelar_voz → {msg.telefono}")
                    continue

                # Pendiente de bg_remove tiene precedencia si existe — flujo más corto.
                if _pend_bg and es_comando_confirmar(msg.texto):
                    resultado = await confirmar_bg_remove(msg.telefono)
                    if resultado["estado"] == "ok":
                        await proveedor.enviar_mensaje(
                            msg.telefono, texto_bg_remove_encolada(resultado["job_id"]),
                        )
                    elif resultado["estado"] == "saldo_insuficiente":
                        await proveedor.enviar_mensaje(msg.telefono, resultado["mensaje"])
                    else:
                        await proveedor.enviar_mensaje(msg.telefono, texto_sin_pendiente())
                    logger.info(f"[CMD] confirmar_bg_remove → {msg.telefono} estado={resultado['estado']}")
                    continue
                if _pend_bg and es_comando_cancelar(msg.texto):
                    cancelar_bg_remove(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, texto_cancelada())
                    logger.info(f"[CMD] cancelar_bg_remove → {msg.telefono}")
                    continue

                if _pend and es_comando_confirmar(msg.texto):
                    resultado = await confirmar_imagen(msg.telefono)
                    if resultado["estado"] == "ok":
                        await proveedor.enviar_mensaje(
                            msg.telefono,
                            texto_encolada(resultado["job_id"], resultado["prompt"]),
                        )
                    elif resultado["estado"] == "saldo_insuficiente":
                        await proveedor.enviar_mensaje(msg.telefono, resultado["mensaje"])
                    else:
                        await proveedor.enviar_mensaje(msg.telefono, texto_sin_pendiente())
                    logger.info(f"[CMD] confirmar_imagen → {msg.telefono} estado={resultado['estado']}")
                    continue

                if _pend and es_comando_cancelar(msg.texto):
                    cancelar_imagen(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, texto_cancelada())
                    logger.info(f"[CMD] cancelar_imagen → {msg.telefono}")
                    continue

                # Si el usuario escribe EXPLÍCITAMENTE "confirmar" o "cancelar"
                # (tokens inequívocos, no ambiguos como "sí"/"no") y NO hay
                # ningún pendiente, le respondemos directamente — evita que el
                # LLM alucine que había algo que ejecutar.
                _hay_pendiente = any([
                    _pend, _pend_bg, _pend_voz, _pend_doc, _pend_video, _pend_video_avatar,
                ])
                if not _hay_pendiente and es_confirmar_inequivoco(msg.texto):
                    await proveedor.enviar_mensaje(msg.telefono, texto_sin_nada_que_confirmar())
                    logger.info(f"[CMD] confirmar sin pendiente → {msg.telefono}")
                    continue
                if not _hay_pendiente and es_cancelar_inequivoco(msg.texto):
                    await proveedor.enviar_mensaje(msg.telefono, texto_sin_nada_que_cancelar())
                    logger.info(f"[CMD] cancelar sin pendiente → {msg.telefono}")
                    continue
            except Exception as _e_cr:
                logger.error(f"[CMD] Error en comando creativo: {_e_cr}")

            # ── Comandos de reporte financiero ("dona resumen del mes", "dona exporta") ──
            try:
                from agent.reporting import detectar_comando_reporte
                _rep = detectar_comando_reporte(msg.texto)
            except Exception:
                _rep = None
            if _rep:
                try:
                    if _rep["tipo"] == "resumen":
                        from agent.reporting import resumen_mes
                        texto_resumen = await resumen_mes(msg.telefono, _rep.get("año"), _rep.get("mes"))
                        await proveedor.enviar_mensaje(msg.telefono, texto_resumen)
                    else:  # exportar
                        from agent.reporting import exportar_transacciones_csv
                        csv_bytes = await exportar_transacciones_csv(msg.telefono, _rep.get("año"), _rep.get("mes"))
                        año = _rep.get("año") or __import__("datetime").datetime.utcnow().year
                        mes = _rep.get("mes")
                        filename = f"transacciones_{año}{f'_{mes:02d}' if mes else ''}.csv"
                        destino = _rep.get("destino", "whatsapp")

                        # ── Ruta "email": adjuntar CSV en Gmail al propio usuario ──
                        if destino == "email":
                            email_destinatario = ""
                            try:
                                from agent.memory import obtener_google_auth
                                auth = await obtener_google_auth(msg.telefono)
                                if auth:
                                    email_destinatario = auth.get("email", "") or ""
                            except Exception:
                                pass

                            if not email_destinatario:
                                await proveedor.enviar_mensaje(
                                    msg.telefono,
                                    "Para mandar el CSV por correo necesito que conectes Google. "
                                    "Escribe 'dona conectar google' y lo autorizas."
                                )
                            else:
                                periodo_str = (
                                    f"{_rep.get('mes'):02d}/{año}" if _rep.get("mes") else f"todo {año}"
                                )
                                try:
                                    from agent.gmail import enviar_correo_con_adjunto, GmailScopeError
                                    ok_mail = await enviar_correo_con_adjunto(
                                        msg.telefono,
                                        email_destinatario,
                                        f"Tu export de Dona — {periodo_str}",
                                        (
                                            f"Hola, te envío el export de transacciones de {periodo_str}.\n\n"
                                            f"Archivo: {filename} ({len(csv_bytes)} bytes).\n\n"
                                            "Generado automáticamente por Dona."
                                        ),
                                        adjuntos=[{
                                            "nombre": filename,
                                            "contenido": csv_bytes,
                                            "mime_type": "text/csv",
                                        }],
                                    )
                                    if ok_mail:
                                        await proveedor.enviar_mensaje(
                                            msg.telefono,
                                            f"Listo, te envié el CSV a {email_destinatario}."
                                        )
                                    else:
                                        await proveedor.enviar_mensaje(
                                            msg.telefono,
                                            "No pude enviar el correo con el adjunto. Intenta de nuevo en un momento."
                                        )
                                except GmailScopeError:
                                    await proveedor.enviar_mensaje(
                                        msg.telefono,
                                        "Me faltan permisos de Gmail. Re-autoriza con 'dona conectar google'."
                                    )
                        else:
                            # ── Ruta WhatsApp (default): adjuntar + backup en Drive ──
                            enviar_doc_fn = getattr(proveedor, "enviar_documento", None)
                            ok_doc = False
                            if enviar_doc_fn:
                                ok_doc = await enviar_doc_fn(
                                    msg.telefono, csv_bytes, filename, "text/csv",
                                    caption=f"Export de transacciones ({len(csv_bytes)} bytes)",
                                )

                            # Backup en Google Drive (best-effort, no bloquea)
                            drive_link = None
                            try:
                                from agent.google_drive import subir_archivo, compartir_con_link
                                subida = await subir_archivo(
                                    msg.telefono, filename, csv_bytes,
                                    mime_type="text/csv",
                                    descripcion=f"Export de transacciones generado por Dona ({len(csv_bytes)} bytes)",
                                )
                                if subida and subida.get("id"):
                                    drive_link = await compartir_con_link(msg.telefono, subida["id"])
                                    if not drive_link:
                                        drive_link = subida.get("webViewLink")
                            except Exception as _e_drv:
                                logger.warning(f"[REPORTE] Drive upload falló (no bloqueante): {_e_drv}")

                            if ok_doc and drive_link:
                                await proveedor.enviar_mensaje(
                                    msg.telefono,
                                    f"También lo guardé en tu Drive: {drive_link}"
                                )
                            elif not ok_doc:
                                # No se pudo adjuntar por WhatsApp → mandar link de Drive si existe
                                if drive_link:
                                    await proveedor.enviar_mensaje(
                                        msg.telefono,
                                        f"No pude adjuntar el CSV por este canal, pero lo subí a tu Drive:\n{drive_link}"
                                    )
                                else:
                                    await proveedor.enviar_mensaje(
                                        msg.telefono,
                                        "No pude adjuntar el CSV por este canal. "
                                        f"Generado localmente: {filename} ({len(csv_bytes)} bytes)."
                                    )
                    logger.info(f"[REPORTE] {_rep['tipo']} → {msg.telefono}")
                except Exception as _e_rep:
                    logger.error(f"[REPORTE] Error generando {_rep['tipo']}: {_e_rep}")
                    await proveedor.enviar_mensaje(
                        msg.telefono,
                        "Hubo un problema generando el reporte. Intenta de nuevo."
                    )
                continue

            # ── Comandos de proactividad ("dona pausa", "dona resumen", etc.) ──
            if es_comando_proactividad(msg.texto):
                try:
                    respuesta_cmd = await manejar_comando_proactividad(msg.telefono, msg.texto)
                except Exception as _e_cmd:
                    logger.error(f"[CMD] Error en comando proactividad: {_e_cmd}")
                    respuesta_cmd = "Hubo un problema procesando ese comando. Intenta de nuevo."
                await proveedor.enviar_mensaje(msg.telefono, respuesta_cmd)
                logger.info(f"[CMD] Proactividad '{msg.texto}' → {msg.telefono}")
                continue

            # ── Onboarding: interceptar si el usuario está en el flujo ────────
            try:
                _onboarding_activo = await es_onboarding_activo(msg.telefono)
            except Exception as _e_ob:
                logger.error(f"[ONBOARDING] Error verificando estado: {_e_ob}")
                _onboarding_activo = False

            if _onboarding_activo and not _es_imagen:
                try:
                    respuesta_onboarding = await procesar_mensaje_onboarding(msg.telefono, msg.texto)
                except Exception as _e_ob2:
                    logger.error(f"[ONBOARDING] Error procesando mensaje: {_e_ob2}")
                    respuesta_onboarding = None
                if respuesta_onboarding is not None:
                    await proveedor.enviar_mensaje(msg.telefono, respuesta_onboarding)
                    logger.info(f"[ONBOARDING] → {msg.telefono}: {respuesta_onboarding[:60]}...")
                    continue  # No pasar al flujo normal de Dona
                else:
                    logger.info(f"[ONBOARDING] Mensaje fuera de flujo, pasa a Claude: '{msg.texto[:60]}'")
            elif _onboarding_activo and _es_imagen:
                logger.info(f"[ONBOARDING] Imagen recibida durante onboarding — pasa a Claude sin avanzar estado")

            # ── Onboarding de negocio: flujo guiado de configuración ────────
            try:
                from agent.business.onboarding_negocio import (
                    esta_en_onboarding_negocio, procesar_paso_onboarding,
                    necesita_onboarding_negocio, iniciar_onboarding_negocio,
                )
                if await esta_en_onboarding_negocio(msg.telefono):
                    resp_biz = await procesar_paso_onboarding(msg.telefono, msg.texto)
                    if resp_biz:
                        await proveedor.enviar_mensaje(msg.telefono, resp_biz)
                        await guardar_mensaje(msg.telefono, "user", msg.texto)
                        await guardar_mensaje(msg.telefono, "assistant", resp_biz)
                        logger.info(f"[BIZ-ONBOARD] → {msg.telefono}: {resp_biz[:60]}...")
                        continue
                elif not _es_imagen and await necesita_onboarding_negocio(msg.telefono, msg.texto):
                    resp_biz = await iniciar_onboarding_negocio(msg.telefono)
                    await proveedor.enviar_mensaje(msg.telefono, resp_biz)
                    await guardar_mensaje(msg.telefono, "user", msg.texto)
                    await guardar_mensaje(msg.telefono, "assistant", resp_biz)
                    logger.info(f"[BIZ-ONBOARD] Iniciado → {msg.telefono}")
                    continue
            except Exception as _e_biz:
                logger.error(f"[BIZ-ONBOARD] Error: {_e_biz}")

            # ── Detección de ciudad base (solo si el usuario no tiene ninguna) ─
            try:
                ub = await obtener_ubicacion(msg.telefono)
                if not ub or not ub.get("ciudad"):
                    if len(msg.texto.strip().split()) <= 4:
                        ciudad_detectada = await es_ciudad_suelta(msg.texto)
                        if ciudad_detectada:
                            await guardar_ubicacion(msg.telefono, ciudad=ciudad_detectada)
                            await proveedor.enviar_mensaje(
                                msg.telefono,
                                f"Perfecto, guardé *{ciudad_detectada}* como tu ciudad 🌍\n"
                                f"A partir de mañana incluiré el clima en tu resumen matutino.",
                            )
                            logger.info(f"[CIUDAD] Ciudad base guardada: {ciudad_detectada} ({msg.telefono})")
                            continue
                        else:
                            logger.debug(f"[CIUDAD] Texto corto '{msg.texto[:30]}' no detectado como ciudad")
            except Exception as _e_ciudad:
                logger.error(f"[CIUDAD] Error detectando ciudad: {_e_ciudad}")
                # No es fatal — continuar al flujo normal

            # ── Detección de viaje (ciudad temporal con expiración) ───────────
            if parece_viaje(msg.texto):
                _asyncio.create_task(_detectar_y_guardar_viaje(msg.telefono, msg.texto))

            # ── Dona 2.0: Detección NLP de sistemas del catálogo ────────────
            try:
                from enhanced.nlp_detector import detectar_sistema, _pasa_filtro_rapido
                if _pasa_filtro_rapido(msg.texto):
                    from enhanced.catalog import obtener_catalogo_activo
                    from enhanced.system_manager import gestor_sistemas
                    _catalogo = await obtener_catalogo_activo()
                    _match = await detectar_sistema(msg.texto, _catalogo)
                    if _match:
                        resp_sis = await gestor_sistemas.instanciar_sistema(
                            msg.telefono, _match["catalog_id"]
                        )
                        await proveedor.enviar_mensaje(msg.telefono, resp_sis)
                        await guardar_mensaje(msg.telefono, "user", msg.texto)
                        await guardar_mensaje(msg.telefono, "assistant", resp_sis)
                        logger.info(f"[SISTEMAS] Sistema '{_match['nombre']}' activado para {msg.telefono}")
                        continue
            except Exception as _e_nlp:
                logger.debug(f"[SISTEMAS] Error en detección NLP: {_e_nlp}")

            # ── Dona 2.0: Interacción con sistemas activos ──────────────────
            try:
                from enhanced.system_processor import procesar_mensaje_sistema
                _resp_sistema = await procesar_mensaje_sistema(msg.telefono, msg.texto)
                if _resp_sistema:
                    await proveedor.enviar_mensaje(msg.telefono, _resp_sistema)
                    await guardar_mensaje(msg.telefono, "user", msg.texto)
                    await guardar_mensaje(msg.telefono, "assistant", _resp_sistema)
                    logger.info(f"[SISTEMAS] Interacción procesada para {msg.telefono}")
                    continue
            except Exception as _e_sys:
                logger.debug(f"[SISTEMAS] Error en procesador de sistemas: {_e_sys}")

            # ── Historial de conversación ─────────────────────────────────────
            try:
                historial = await obtener_historial(msg.telefono)
            except Exception as _e_hist:
                logger.error(f"[WEBHOOK] Error cargando historial para {msg.telefono}: {_e_hist}")
                historial = []  # Continuar sin historial antes que no responder

            # ── Generar respuesta con Claude (con timeout de 90s) ────────────
            try:
                respuesta = await _asyncio.wait_for(
                    generar_respuesta(
                        msg.texto, historial,
                        telefono=msg.telefono,
                        timestamp_mensaje=msg.timestamp,
                        proveedor=proveedor,
                    ),
                    timeout=90.0,
                )
            except _asyncio.TimeoutError:
                logger.error(f"[WEBHOOK] Claude API timeout (90s) para {msg.telefono}")
                respuesta = "Disculpa, tardé demasiado en procesar tu mensaje. ¿Puedes intentarlo de nuevo?"

            # ── Guardar mensajes en DB (no fatal si falla) ────────────────────
            try:
                await guardar_mensaje(msg.telefono, "user", msg.texto)
                await guardar_mensaje(msg.telefono, "assistant", respuesta)
            except Exception as _e_save:
                logger.error(f"[WEBHOOK] Error guardando mensajes en DB: {_e_save}")
                # No es fatal — la respuesta ya se generó, hay que enviarla

            # ── Enviar respuesta al usuario ───────────────────────────────────
            enviado = await proveedor.enviar_mensaje(msg.telefono, respuesta)
            if not enviado:
                logger.error(f"[WEBHOOK] Fallo al enviar respuesta a {msg.telefono} — proveedor retornó False")
            else:
                logger.info(f"Respuesta a {msg.telefono}: {respuesta[:120]}")

            # ── Si el usuario mandó audio, responder también con audio (TTS) ──
            # No es fatal si falla: ya le enviamos el texto.
            if _es_audio and os.getenv("DONA_TTS_HABILITADO", "1") != "0":
                try:
                    from agent.tts import sintetizar_audio
                    audio_bytes = await sintetizar_audio(respuesta)
                    if audio_bytes:
                        enviar_audio_fn = getattr(proveedor, "enviar_audio", None)
                        if enviar_audio_fn:
                            await enviar_audio_fn(msg.telefono, audio_bytes, "audio/ogg")
                except Exception as _e_tts:
                    logger.error(f"[TTS] Error generando/enviando audio: {_e_tts}")

            # ── Tareas de background (no bloquean la respuesta) ───────────────
            import agent.mirofish_client as _mf
            if _mf._disponible() and _tiene_contexto_relevante(msg.texto):
                _asyncio.create_task(_actualizar_memoria_mirofish(msg.telefono, msg.texto))

            _asyncio.create_task(_verificar_sobrecarga(msg.telefono, proveedor, msg.texto))
            _asyncio.create_task(_actualizar_memoria_largo_plazo_si_necesario(msg.telefono))
            _asyncio.create_task(_registrar_interaccion_aprendizaje(msg.telefono, len(msg.texto)))
            _asyncio.create_task(_registrar_sesion_bg(msg.telefono))

        except Exception as _e_msg:
            # Fallo inesperado procesando este mensaje — loguear y seguir con el siguiente
            logger.error(
                f"[WEBHOOK] Error inesperado procesando mensaje de {getattr(msg, 'telefono', '?')}: "
                f"{type(_e_msg).__name__}: {_e_msg}",
                exc_info=True
            )
            # Intentar enviar mensaje de error al usuario como último recurso
            try:
                from agent.brain import obtener_mensaje_error
                await proveedor.enviar_mensaje(getattr(msg, 'telefono', ''), obtener_mensaje_error())
            except Exception:
                pass  # Si esto también falla, no hay más que hacer

    return {"status": "ok"}


# Palabras clave que indican contexto relevante para el grafo de memoria MiroFish
_KEYWORDS_CONTEXTO = {
    "reunión", "reunion", "proyecto", "contrato", "llamada", "cita",
    "cliente", "socio", "proveedor", "equipo", "empresa", "acuerdo",
    "presentación", "presentacion", "negociación", "negociacion",
    "propuesta", "junta", "entrevista", "socio", "alianza",
}


def _tiene_contexto_relevante(texto: str) -> bool:
    """Retorna True si el mensaje contiene información social/profesional relevante."""
    texto_lower = texto.lower()
    return len(texto) > 30 and any(kw in texto_lower for kw in _KEYWORDS_CONTEXTO)


# Palabras que indican que el mensaje es una consulta analítica, no estrés real
_KEYWORDS_ANALISIS = {
    "qué pasaría", "que pasaria", "qué pasa si", "que pasa si",
    "qué consecuencias", "que consecuencias", "cómo reaccionaría",
    "como reaccionaria", "qué impacto", "que impacto",
    "si cancelo", "si cambio", "si dejo", "si acepto", "si rechazo",
    "analiza", "analizar", "explorar", "pensar las consecuencias",
}


async def _verificar_sobrecarga(telefono: str, proveedor, texto_mensaje: str = ""):
    """
    Detecta sobrecarga crónica: 4+ eventos de estrés/agotamiento (intensidad ≥2) en 24h.
    Envía un mensaje de cuidado proactivo si se detecta y no se ha enviado hoy.
    Cuenta dentro del límite diario de mensajes proactivos.
    No se activa si el mensaje actual es una consulta analítica (análisis de decisiones).
    """
    try:
        # No disparar sobrecarga si el mensaje es una consulta de análisis de consecuencias
        if texto_mensaje:
            texto_lower = texto_mensaje.lower()
            if any(kw in texto_lower for kw in _KEYWORDS_ANALISIS):
                logger.debug(f"_verificar_sobrecarga: mensaje analítico, omitiendo ({telefono})")
                return

        count = await contar_eventos_estres_recientes(telefono, horas=24)
        if count < 4:  # Subido de 3 a 4 para reducir falsos positivos
            return
        if await ya_avisado_sobrecarga_hoy(telefono):
            return

        from agent.memory import obtener_onboarding
        estado = await obtener_onboarding(telefono)
        nombre = estado.get("nombre", "") if estado else ""

        mensaje = (
            f"{nombre + ', h' if nombre else 'H'}e notado que llevas un día muy intenso. 💙\n\n"
            "Está bien no poder con todo. ¿Hay algo que pueda quitarte del plato "
            "o simplemente necesitas que te escuche?"
        )

        enviado = await proveedor.enviar_mensaje(telefono, mensaje)
        if enviado:
            await marcar_aviso_sobrecarga(telefono)
            await incrementar_mensajes_proactivos(telefono)
            logger.info(f"Aviso de sobrecarga enviado a {telefono}")

    except Exception as e:
        logger.debug(f"_verificar_sobrecarga error ({telefono}): {e}")


# Umbral de mensajes relevantes acumulados antes de re-sincronizar el grafo
_MIROFISH_SYNC_UMBRAL_MENSAJES = 15
# Días máximos sin sincronizar antes de forzar actualización
_MIROFISH_SYNC_DIAS_MAX = 7


async def _actualizar_memoria_mirofish(telefono: str, texto: str):
    """
    Actualiza el grafo de conocimiento del usuario en MiroFish de forma inteligente.
    Estrategia de actualización continua:
      1. Siempre acumula el texto relevante en contexto_pendiente.
      2. Construye el grafo inicial si el usuario no tiene ninguno.
      3. Re-sincroniza el grafo cuando se cumple alguna condición:
         - Se acumularon 15+ mensajes relevantes nuevos, O
         - Han pasado 7+ días desde la última sincronización.
    Corre en background — silencioso, sin interrumpir la experiencia del usuario.
    """
    import agent.mirofish_client as mf
    from datetime import timezone as tz

    try:
        estado = await obtener_mirofish_estado(telefono)
        project_id = estado.get("project_id") if estado else None
        graph_id = estado.get("graph_id") if estado else None
        ctx_pendiente = (estado.get("contexto_pendiente") or "") if estado else ""
        mensajes_count = (estado.get("mensajes_desde_sync") or 0) if estado else 0
        ultima_sync = estado.get("actualizado") if estado else None

        # Acumular el texto nuevo al contexto pendiente (máx 8000 chars para no saturar)
        ctx_nuevo = (ctx_pendiente + "\n" + texto).strip()
        if len(ctx_nuevo) > 8000:
            ctx_nuevo = ctx_nuevo[-8000:]  # Mantener los más recientes
        mensajes_count += 1

        # Guardar el contexto acumulado actualizado
        await guardar_mirofish_estado(
            telefono,
            contexto_pendiente=ctx_nuevo,
            mensajes_desde_sync=mensajes_count,
        )

        # Determinar si es necesario sincronizar el grafo ahora
        dias_sin_sync = 999
        if ultima_sync:
            # Normalizar a UTC para comparar
            ahora_utc = datetime.utcnow().replace(tzinfo=tz.utc)
            sync_utc = ultima_sync.replace(tzinfo=tz.utc) if ultima_sync.tzinfo is None else ultima_sync
            dias_sin_sync = (ahora_utc - sync_utc).days

        necesita_sync = (
            not project_id  # Primera vez — nunca ha tenido grafo
            or not graph_id
            or mensajes_count >= _MIROFISH_SYNC_UMBRAL_MENSAJES
            or dias_sin_sync >= _MIROFISH_SYNC_DIAS_MAX
        )

        if not necesita_sync:
            logger.debug(
                f"MiroFish: acumulando contexto para {telefono} "
                f"({mensajes_count}/{_MIROFISH_SYNC_UMBRAL_MENSAJES} mensajes, "
                f"{dias_sin_sync}/{_MIROFISH_SYNC_DIAS_MAX} días)"
            )
            return

        # Construir o actualizar el grafo
        motivo = "inicial" if not project_id else f"{mensajes_count} msgs nuevos / {dias_sin_sync}d sin sync"
        logger.info(f"MiroFish: sincronizando grafo para {telefono} (motivo: {motivo})")

        requerimiento = (
            "Analiza y actualiza las relaciones, personas clave, proyectos activos, "
            "compromisos, metas y eventos relevantes del usuario. "
            "Prioriza la información más reciente sobre la más antigua."
        )

        project_id_nuevo, graph_id_nuevo = await mf.construir_grafo_completo(
            texto=ctx_nuevo,
            telefono=telefono,
            nombre_proyecto=f"Dona_{telefono.replace('+', '').replace('@', '_')}",
            requerimiento=requerimiento,
        )

        if project_id_nuevo:
            await guardar_mirofish_estado(
                telefono,
                project_id=project_id_nuevo,
                graph_id=graph_id_nuevo,
                resetear_sync=True,  # Limpia contexto_pendiente y mensajes_desde_sync
            )
            logger.info(
                f"MiroFish: grafo actualizado para {telefono} — "
                f"project={project_id_nuevo}, graph={graph_id_nuevo}"
            )
        else:
            logger.warning(f"MiroFish: sincronización falló para {telefono}, se reintentará en el próximo ciclo")

    except Exception as e:
        logger.error(f"MiroFish _actualizar_memoria_mirofish error ({telefono}): {e}")


async def _registrar_interaccion_aprendizaje(telefono: str, longitud_mensaje: int):
    """
    Registra el evento de mensaje enviado para el aprendizaje continuo.
    Carga el offset del usuario para convertir hora UTC a hora local.
    """
    try:
        from agent.memory import obtener_timezone
        offset = await obtener_timezone(telefono) or 0
        await registrar_interaccion(
            telefono,
            "message_sent",
            metadata={"longitud": longitud_mensaje},
            offset_min=offset,
        )
    except Exception as e:
        logger.debug(f"_registrar_interaccion_aprendizaje ({telefono}): {e}")


async def _registrar_sesion_bg(telefono: str):
    """Registra interacción en la sesión de conversación (background)."""
    try:
        from agent.memory import registrar_interaccion_sesion
        await registrar_interaccion_sesion(telefono)
    except Exception as e:
        logger.debug(f"_registrar_sesion_bg ({telefono}): {e}")


async def _actualizar_memoria_largo_plazo_si_necesario(telefono: str):
    """
    Verifica si hay ≥20 mensajes nuevos desde el último resumen y, si es así,
    genera un nuevo resumen consolidado con Haiku.
    Corre en background — silencioso, sin interrumpir la respuesta principal.
    """
    try:
        actualizado = await actualizar_resumen_si_necesario(telefono)
        if actualizado:
            logger.info(f"[MEMORIA] Resumen largo plazo actualizado para {telefono}")
    except Exception as e:
        logger.debug(f"_actualizar_memoria_largo_plazo_si_necesario ({telefono}): {e}")


async def _detectar_y_guardar_viaje(telefono: str, texto: str):
    """
    Detecta viaje en el texto y guarda la ciudad temporal.
    Corre en background — no bloquea la respuesta principal.
    """
    try:
        viaje = await detectar_viaje(texto)
        if viaje:
            await guardar_ciudad_temporal(telefono, viaje["ciudad"], viaje["dias"])
            logger.info(
                f"Ciudad temporal guardada para {telefono}: "
                f"{viaje['ciudad']} ({viaje['dias']} días)"
            )
    except Exception as e:
        logger.debug(f"_detectar_y_guardar_viaje ({telefono}): {e}")


@app.post("/webhook/stripe")
async def webhook_stripe(request: Request):
    """
    Webhook de Stripe para eventos de pago. Verifica firma, procesa el evento,
    y acredita créditos al usuario cuando corresponde.
    Idempotente: reentregas del mismo `session_id` no duplican créditos.
    """
    from agent.billing import verificar_firma_stripe, procesar_evento_stripe

    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    evento = verificar_firma_stripe(body, sig)
    if evento is None:
        logger.warning("[STRIPE] Firma inválida o payload no parseable — rechazando")
        raise HTTPException(status_code=400, detail="signature_invalid")

    try:
        resultado = await procesar_evento_stripe(evento)
    except Exception as e:
        logger.exception(f"[STRIPE] Error procesando evento: {e}")
        # Retornamos 500 para que Stripe reintente
        raise HTTPException(status_code=500, detail="processing_error")

    # Notificar al usuario por WhatsApp si fue una acreditación exitosa
    if resultado.get("handled"):
        tel = resultado.get("telefono", "")
        creditos = resultado.get("creditos", 0)
        saldo = resultado.get("saldo", 0)
        if tel and creditos:
            try:
                await proveedor.enviar_mensaje(
                    tel,
                    f"✅ ¡Gracias por tu compra!\n"
                    f"Se acreditaron *{creditos} créditos* a tu cuenta.\n"
                    f"Saldo actual: *{saldo} créditos*."
                )
            except Exception as _e_notif:
                logger.warning(f"[STRIPE] No se pudo notificar por WhatsApp a {tel}: {_e_notif}")

    return {"status": "ok", **resultado}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """Webhook genérico."""
    return await procesar_webhook(request)


@app.post("/webhook/messages")
async def webhook_messages_handler(request: Request):
    """Whapi envía aquí cuando el evento es 'messages' (agrega /messages a la URL base)."""
    return await procesar_webhook(request)

@app.get("/voice/reenviar")
@app.post("/voice/reenviar")
async def voice_reenviar():
    """Responde con TwiML para reenviar llamadas entrantes al número del administrador.

    Lee el destino desde la variable de entorno ``VOICE_FORWARD_NUMBER`` (formato
    E.164 con '+'). Si no está configurada, devuelve 404 — no hay número por
    defecto en el código.
    """
    destino = os.getenv("VOICE_FORWARD_NUMBER", "").strip()
    if not destino:
        raise HTTPException(status_code=404, detail="voice_forward_no_configurado")
    # Mínimo gate de formato: E.164, '+' opcional, 10–15 dígitos.
    if not re.fullmatch(r"\+?\d{10,15}", destino):
        logger.error("[VOICE] VOICE_FORWARD_NUMBER tiene formato inválido — rechazando")
        raise HTTPException(status_code=500, detail="voice_forward_formato_invalido")
    if not destino.startswith("+"):
        destino = "+" + destino
    twiml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Dial>{destino}</Dial></Response>'
    )
    return PlainTextResponse(content=twiml, media_type="application/xml")
