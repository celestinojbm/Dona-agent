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
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import (
    inicializar_db, guardar_mensaje, obtener_historial,
    obtener_mirofish_estado, guardar_mirofish_estado,
)
from agent.providers import obtener_proveedor
from agent.scheduler import iniciar_scheduler, detener_scheduler
from agent.transcriber import procesar_audio_whapi

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
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

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


@app.post("/webhook")
async def webhook_handler(request: Request):
    """Webhook genérico."""
    return await procesar_webhook(request)


@app.post("/webhook/messages")
async def webhook_messages_handler(request: Request):
    """Whapi envía aquí cuando el evento es 'messages' (agrega /messages a la URL base)."""
    return await procesar_webhook(request)
