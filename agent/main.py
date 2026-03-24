# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

"""
Servidor principal del agente Dona.
Funciona con cualquier proveedor (Whapi, Meta, Twilio) gracias a la capa de providers.
"""

import os
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse, RedirectResponse
from dotenv import load_dotenv

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
from agent.transcriber import procesar_audio_whapi
from agent.memory_summary import actualizar_resumen_si_necesario

load_dotenv()

# Configuración de logging según entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

# Proveedor de WhatsApp (se configura en .env con WHATSAPP_PROVIDER)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos y el scheduler al arrancar el servidor."""
    await inicializar_db()
    iniciar_scheduler(proveedor)
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor Dona corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield
    detener_scheduler()


app = FastAPI(
    title="Dona — Asistente Personal en WhatsApp",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway/monitoreo."""
    return {"status": "ok", "service": "dona"}


@app.get("/diagnostico")
async def diagnostico():
    """Prueba la conectividad con Whapi desde Railway."""
    token = os.getenv("WHAPI_TOKEN", "")
    resultados = {}

    # Test 1: DNS y TCP a gate.whapi.cloud
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://gate.whapi.cloud/health",
                headers={"Authorization": f"Bearer {token}"}
            )
            resultados["whapi_health"] = {"status": r.status_code, "body": r.json()}
    except Exception as e:
        resultados["whapi_health"] = {"error": type(e).__name__, "detail": str(e)}

    # Test 2: Conectividad general de Railway
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://httpbin.org/ip")
            resultados["railway_ip"] = r.json()
    except Exception as e:
        resultados["railway_ip"] = {"error": type(e).__name__, "detail": str(e)}

    return resultados


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    """Verificación GET del webhook (requerido por Meta Cloud API, no-op para otros)."""
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.get("/admin/onboarding")
async def admin_onboarding_estado(telefono: str, token: str = ""):
    """
    Diagnóstico de onboarding en producción.
    Uso: /admin/onboarding?telefono=521234567890&token=ADMIN_TOKEN
    """
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
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
async def admin_onboarding_reset(telefono: str, fase: int = 0, paso: int = 0, token: str = ""):
    """
    Resetea el estado de onboarding de un usuario.
    Uso: POST /admin/onboarding/reset?telefono=521234567890&fase=0&paso=2&token=ADMIN_TOKEN
    """
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        raise HTTPException(status_code=403, detail="Token inválido")
    from agent.memory import guardar_onboarding
    await guardar_onboarding(telefono, fase=fase, paso=paso)
    return {"status": "ok", "telefono": telefono, "fase": fase, "paso": paso}


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
            mensaje="Error al conectar con Google. Por favor intenta de nuevo."
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
    """Captura el body crudo de cualquier request — para diagnosticar Whapi."""
    body = await request.body()
    headers = dict(request.headers)
    logger.info(f"DEBUG body: {body.decode('utf-8', errors='replace')}")
    logger.info(f"DEBUG headers: {headers}")
    return {"status": "ok", "body": body.decode("utf-8", errors="replace")}


async def procesar_webhook(request: Request):
    """Lógica compartida: parsea el mensaje, llama a Claude y responde."""
    try:
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            if msg.es_propio:
                logger.debug(f"[SKIP] Mensaje propio ignorado: {msg.telefono}")
                continue

            # Si es una nota de voz, transcribirla primero
            if msg.audio_id and not msg.texto:
                token = os.getenv("WHAPI_TOKEN", "")
                logger.info(f"Transcribiendo nota de voz de {msg.telefono}...")
                texto_transcrito = await procesar_audio_whapi(msg.audio_id, msg.audio_mime, token)
                if not texto_transcrito:
                    await proveedor.enviar_mensaje(
                        msg.telefono,
                        "No pude entender tu nota de voz 😅 ¿Puedes escribirlo?"
                    )
                    continue
                msg.texto = texto_transcrito
                logger.info(f"Nota de voz transcrita: \"{texto_transcrito}\"")

            if not msg.texto:
                logger.warning(f"[SKIP] Mensaje sin texto ignorado silenciosamente: tel={msg.telefono} audio_id={msg.audio_id}")
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto[:120]}")

            # ── Comandos de proactividad ("dona pausa", "dona resumen", etc.) ──
            if es_comando_proactividad(msg.texto):
                respuesta_cmd = await manejar_comando_proactividad(msg.telefono, msg.texto)
                await proveedor.enviar_mensaje(msg.telefono, respuesta_cmd)
                logger.info(f"[CMD] Proactividad '{msg.texto}' → {msg.telefono}")
                continue

            # ── Onboarding: interceptar si el usuario está en el flujo ────────
            if await es_onboarding_activo(msg.telefono):
                respuesta_onboarding = await procesar_mensaje_onboarding(msg.telefono, msg.texto)
                if respuesta_onboarding is not None:
                    await proveedor.enviar_mensaje(msg.telefono, respuesta_onboarding)
                    logger.info(f"[ONBOARDING] → {msg.telefono}: {respuesta_onboarding[:60]}...")
                    continue  # No pasar al flujo normal de Dona
                else:
                    logger.info(f"[ONBOARDING] Mensaje fuera de flujo, pasa a Claude: '{msg.texto[:60]}'")

            # ── Detección de ciudad base (solo si el usuario no tiene ninguna) ─
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

            # ── Detección de viaje (ciudad temporal con expiración) ───────────
            # Pre-filtro barato antes de llamar al LLM — solo si hay keywords de viaje
            if parece_viaje(msg.texto):
                import asyncio as _asyncio
                _asyncio.create_task(_detectar_y_guardar_viaje(msg.telefono, msg.texto))

            # ── Flujo normal de Dona ──────────────────────────────────────────
            historial = await obtener_historial(msg.telefono)
            respuesta = await generar_respuesta(
                msg.texto, historial,
                telefono=msg.telefono,
                timestamp_mensaje=msg.timestamp,
                proveedor=proveedor,
            )

            # Actualizar memoria de grafo MiroFish en background si el mensaje tiene contexto relevante
            import asyncio as _asyncio
            import agent.mirofish_client as _mf
            if _mf._disponible() and _tiene_contexto_relevante(msg.texto):
                _asyncio.create_task(
                    _actualizar_memoria_mirofish(msg.telefono, msg.texto)
                )

            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"Respuesta a {msg.telefono}: {respuesta}")

            # Verificar sobrecarga crónica en background
            import asyncio as _asyncio
            _asyncio.create_task(
                _verificar_sobrecarga(msg.telefono, proveedor)
            )

            # Actualizar resumen de memoria a largo plazo si hay 20+ mensajes nuevos
            _asyncio.create_task(
                _actualizar_memoria_largo_plazo_si_necesario(msg.telefono)
            )

            # Registrar interacción para aprendizaje continuo (background)
            _asyncio.create_task(
                _registrar_interaccion_aprendizaje(msg.telefono, len(msg.texto))
            )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook ({type(e).__name__}): {e}", exc_info=True)
        return {"status": "error", "detail": type(e).__name__}


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


async def _verificar_sobrecarga(telefono: str, proveedor):
    """
    Detecta sobrecarga crónica: 3+ eventos de estrés/agotamiento (intensidad ≥2) en 24h.
    Envía un mensaje de cuidado proactivo si se detecta y no se ha enviado hoy.
    Cuenta dentro del límite diario de mensajes proactivos.
    """
    try:
        count = await contar_eventos_estres_recientes(telefono, horas=24)
        if count < 3:
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


async def _actualizar_memoria_mirofish(telefono: str, texto: str):
    """
    Construye o actualiza el grafo de conocimiento del usuario en MiroFish.
    Corre en background — silencioso, sin interrumpir la experiencia del usuario.
    """
    import agent.mirofish_client as mf

    try:
        estado = await obtener_mirofish_estado(telefono)
        project_id_existente = estado.get("project_id") if estado else None

        # Solo construir grafo nuevo si no tiene uno reciente (o no tiene ninguno)
        # Evitar reconstruir en cada mensaje — solo si no existe grafo aún
        if project_id_existente and estado.get("graph_id"):
            logger.debug(f"MiroFish: usuario {telefono} ya tiene grafo, omitiendo actualización")
            return

        logger.info(f"MiroFish: construyendo grafo de memoria para {telefono}")
        project_id, graph_id = await mf.construir_grafo_completo(
            texto=texto,
            telefono=telefono,
            requerimiento="Analiza las relaciones, personas, compromisos y eventos mencionados",
        )

        if project_id:
            await guardar_mirofish_estado(telefono, project_id=project_id, graph_id=graph_id)
            logger.info(f"MiroFish: grafo guardado para {telefono} — project={project_id}, graph={graph_id}")

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
