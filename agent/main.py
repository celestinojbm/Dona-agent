# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

"""
Servidor principal del agente Dona.
Funciona con cualquier proveedor (Whapi, Meta, Twilio) gracias a la capa de providers.
"""

import os
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

from agent.brain import generar_respuesta
from agent.memory import (
    inicializar_db, guardar_mensaje, obtener_historial,
    obtener_mirofish_estado, guardar_mirofish_estado,
    obtener_ubicacion, guardar_ubicacion, guardar_ciudad_temporal,
)
from agent.location import parece_viaje, detectar_viaje, es_ciudad_suelta
from agent.learning import registrar_interaccion
from agent.onboarding import procesar_mensaje_onboarding, es_onboarding_activo
from agent.proactivity import es_comando_proactividad, manejar_comando_proactividad
from agent.memory import (
    contar_eventos_estres_recientes, ya_avisado_sobrecarga_hoy, marcar_aviso_sobrecarga,
    incrementar_mensajes_proactivos,
)
from agent.providers import obtener_proveedor
from agent.scheduler import iniciar_scheduler, detener_scheduler
from agent.transcriber import procesar_audio_whapi, procesar_audio_meta
from agent.memory_summary import actualizar_resumen_si_necesario

logger = logging.getLogger("agentkit")
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


def _verificar_admin(request: Request, token_query: str = "") -> bool:
    """Verifica autenticación admin via header (preferido) o query param (legacy)."""
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token:
        return False
    # Preferir header Authorization: Bearer <token>
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:] == admin_token:
        return True
    # Fallback a query param (legacy, menos seguro)
    return token_query == admin_token


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
    from agent.memory import guardar_onboarding
    await guardar_onboarding(telefono, fase=fase, paso=paso)
    return {"status": "ok", "telefono": telefono, "fase": fase, "paso": paso}


@app.get("/admin/recordatorios")
async def admin_recordatorios(request: Request, telefono: str, token: str = ""):
    """
    Diagnóstico de recordatorios en producción.
    Uso: /admin/recordatorios?telefono=14076936023 + Header Authorization: Bearer <token>
    """
    if not _verificar_admin(request, token):
        raise HTTPException(status_code=403, detail="Token inválido")
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
    except Exception:
        return HTMLResponse(_html_oauth_resultado(exito=False, mensaje="State inválido."))

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
    """Envía un WhatsApp de confirmación cuando el usuario conecta Google Calendar."""
    try:
        email_str = f" ({email})" if email else ""
        mensaje = (
            f"¡Tu Google Calendar está conectado{email_str}! 🗓️\n\n"
            "Ahora puedo:\n"
            "• Ver tus eventos del día — *\"qué tengo hoy?\"*\n"
            "• Crear eventos directamente — *\"agéndame reunión mañana a las 3pm\"*\n\n"
            "Todo se sincroniza con tu Google Calendar real."
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
                logger.info(f"Nota de voz transcrita: \"{texto_transcrito}\"")

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

            # ── Borrado de datos del usuario (derecho al olvido) ─────────
            if _texto_cmd in ("!borrarmisdatos", "!deletemydata") or \
               _texto_lower in ("!borrar mis datos", "borrar mis datos", "eliminar mis datos"):
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

            # ── Tareas de background (no bloquean la respuesta) ───────────────
            import agent.mirofish_client as _mf
            if _mf._disponible() and _tiene_contexto_relevante(msg.texto):
                _asyncio.create_task(_actualizar_memoria_mirofish(msg.telefono, msg.texto))

            _asyncio.create_task(_verificar_sobrecarga(msg.telefono, proveedor, msg.texto))
            _asyncio.create_task(_actualizar_memoria_largo_plazo_si_necesario(msg.telefono))
            _asyncio.create_task(_registrar_interaccion_aprendizaje(msg.telefono, len(msg.texto)))

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
    """Responde con TwiML para reenviar llamadas entrantes al número personal del administrador."""
    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Dial>+14076936023</Dial></Response>'
    return PlainTextResponse(content=twiml, media_type="application/xml")
