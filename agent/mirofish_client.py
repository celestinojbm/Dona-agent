# agent/mirofish_client.py — Cliente async para el motor MiroFish
# Integrado en Dona por AgentKit

"""
Cliente HTTP asíncrono para comunicarse con el microservicio MiroFish.
MiroFish expone una API REST (Flask) que proporciona:
  - Extracción de entidades y construcción de grafos de conocimiento (Zep Cloud)
  - Simulación de escenarios sociales (OASIS / camel-ai)
  - Generación de reportes (ReACT Agent)

Si MIROFISH_BASE_URL no está configurado, todas las funciones retornan None
y Dona opera normalmente sin esta funcionalidad.
"""

import os
import asyncio
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

MIROFISH_BASE_URL = os.getenv("MIROFISH_BASE_URL", "")
TIMEOUT_CORTO = 15.0    # Segundos — llamadas rápidas
TIMEOUT_LARGO = 120.0   # Segundos — ontología, preparar simulación, reporte


def _disponible() -> bool:
    """Retorna True si MiroFish está configurado."""
    return bool(MIROFISH_BASE_URL)


# ─── GRAFOS DE CONOCIMIENTO ──────────────────────────────────────────────────

async def generar_ontologia(texto: str, nombre_proyecto: str, requerimiento: str = "") -> str | None:
    """
    Sube texto al motor de MiroFish y genera la ontología del proyecto.
    Retorna el project_id, o None si falla.
    """
    if not _disponible():
        return None
    try:
        req = requerimiento or "Analiza las relaciones, personas, compromisos y eventos del texto"
        async with httpx.AsyncClient(timeout=TIMEOUT_LARGO) as client:
            r = await client.post(
                f"{MIROFISH_BASE_URL}/api/graph/ontology/generate",
                data={
                    "simulation_requirement": req,
                    "project_name": nombre_proyecto,
                },
                files={"files": ("contexto.txt", texto.encode("utf-8"), "text/plain")},
            )
            r.raise_for_status()
            data = r.json()
            project_id = data["data"]["project_id"]
            logger.info(f"MiroFish: ontología generada, project_id={project_id}")
            return project_id
    except Exception as e:
        logger.error(f"MiroFish generar_ontologia: {e}")
        return None


async def construir_grafo(project_id: str) -> str | None:
    """
    Construye el grafo en Zep Cloud para el proyecto dado.
    Retorna el task_id del job asíncrono, o None si falla.
    """
    if not _disponible():
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_CORTO) as client:
            r = await client.post(
                f"{MIROFISH_BASE_URL}/api/graph/build",
                json={"project_id": project_id},
            )
            r.raise_for_status()
            task_id = r.json()["data"]["task_id"]
            logger.info(f"MiroFish: grafo en construcción, task_id={task_id}")
            return task_id
    except Exception as e:
        logger.error(f"MiroFish construir_grafo: {e}")
        return None


async def esperar_grafo(task_id: str, max_intentos: int = 30, intervalo: float = 10.0) -> str | None:
    """
    Hace polling hasta que el grafo esté listo.
    Retorna el graph_id cuando status=completed, o None si agota el tiempo.
    """
    if not _disponible():
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_CORTO) as client:
            for intento in range(max_intentos):
                await asyncio.sleep(intervalo)
                r = await client.get(f"{MIROFISH_BASE_URL}/api/graph/task/{task_id}")
                r.raise_for_status()
                data = r.json().get("data", {})
                status = data.get("status", "")
                if status == "completed":
                    graph_id = data.get("graph_id")
                    logger.info(f"MiroFish: grafo listo, graph_id={graph_id}")
                    return graph_id
                if status == "failed":
                    logger.error(f"MiroFish: construcción de grafo falló ({data})")
                    return None
                logger.debug(f"MiroFish: grafo aún en progreso (intento {intento+1}/{max_intentos})")
        logger.warning("MiroFish: timeout esperando grafo")
        return None
    except Exception as e:
        logger.error(f"MiroFish esperar_grafo: {e}")
        return None


async def construir_grafo_completo(
    texto: str,
    telefono: str,
    nombre_proyecto: str | None = None,
    requerimiento: str = "",
) -> tuple[str | None, str | None]:
    """
    Pipeline completo: genera ontología → construye grafo → espera resultado.
    Retorna (project_id, graph_id). Ambos None si algo falla.
    """
    nombre = nombre_proyecto or f"Dona_{telefono.replace('+', '').replace('@', '_')}"
    project_id = await generar_ontologia(texto, nombre, requerimiento)
    if not project_id:
        return None, None

    task_id = await construir_grafo(project_id)
    if not task_id:
        return project_id, None

    graph_id = await esperar_grafo(task_id)
    return project_id, graph_id


# ─── SIMULACIONES ────────────────────────────────────────────────────────────

async def crear_simulacion(project_id: str, graph_id: str) -> str | None:
    """Crea una nueva simulación. Retorna simulation_id o None."""
    if not _disponible():
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_CORTO) as client:
            r = await client.post(
                f"{MIROFISH_BASE_URL}/api/simulation/create",
                json={"project_id": project_id, "graph_id": graph_id},
            )
            r.raise_for_status()
            simulation_id = r.json()["data"]["simulation_id"]
            logger.info(f"MiroFish: simulación creada, id={simulation_id}")
            return simulation_id
    except Exception as e:
        logger.error(f"MiroFish crear_simulacion: {e}")
        return None


async def preparar_simulacion(simulation_id: str, escenario: str) -> bool:
    """Prepara la simulación con el escenario dado. Retorna True si ok."""
    if not _disponible():
        return False
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_LARGO) as client:
            r = await client.post(
                f"{MIROFISH_BASE_URL}/api/simulation/prepare",
                json={"simulation_id": simulation_id, "simulation_requirement": escenario},
            )
            r.raise_for_status()
            logger.info(f"MiroFish: simulación {simulation_id} preparada")
            return True
    except Exception as e:
        logger.error(f"MiroFish preparar_simulacion: {e}")
        return False


async def iniciar_simulacion(simulation_id: str, max_rondas: int = 10) -> bool:
    """Inicia la simulación. Retorna True si arrancó ok."""
    if not _disponible():
        return False
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_CORTO) as client:
            r = await client.post(
                f"{MIROFISH_BASE_URL}/api/simulation/start",
                json={"simulation_id": simulation_id, "max_rounds": max_rondas},
            )
            r.raise_for_status()
            logger.info(f"MiroFish: simulación {simulation_id} iniciada")
            return True
    except Exception as e:
        logger.error(f"MiroFish iniciar_simulacion: {e}")
        return False


async def esperar_simulacion(
    simulation_id: str, max_intentos: int = 36, intervalo: float = 10.0
) -> bool:
    """
    Polling hasta que la simulación termine.
    Retorna True si completed, False si falla o agota el tiempo (~6 min max).
    """
    if not _disponible():
        return False
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_CORTO) as client:
            for intento in range(max_intentos):
                await asyncio.sleep(intervalo)
                r = await client.get(f"{MIROFISH_BASE_URL}/api/simulation/{simulation_id}/status")
                r.raise_for_status()
                status = r.json().get("data", {}).get("status", "")
                if status in ("completed", "stopped"):
                    logger.info(f"MiroFish: simulación {simulation_id} terminada ({status})")
                    return True
                if status == "failed":
                    logger.error(f"MiroFish: simulación {simulation_id} falló")
                    return False
                logger.debug(f"MiroFish: simulación en progreso (intento {intento+1}/{max_intentos})")
        logger.warning(f"MiroFish: timeout esperando simulación {simulation_id}")
        return False
    except Exception as e:
        logger.error(f"MiroFish esperar_simulacion: {e}")
        return False


# ─── REPORTES ────────────────────────────────────────────────────────────────

async def generar_reporte(simulation_id: str) -> str | None:
    """Genera el reporte de una simulación. Retorna report_id o None."""
    if not _disponible():
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_LARGO) as client:
            r = await client.post(
                f"{MIROFISH_BASE_URL}/api/report/generate",
                json={"simulation_id": simulation_id},
            )
            r.raise_for_status()
            report_id = r.json()["data"]["report_id"]
            logger.info(f"MiroFish: reporte {report_id} solicitado")
            return report_id
    except Exception as e:
        logger.error(f"MiroFish generar_reporte: {e}")
        return None


async def esperar_reporte(
    report_id: str, max_intentos: int = 24, intervalo: float = 5.0
) -> str | None:
    """
    Polling hasta que el reporte esté listo.
    Retorna el contenido del reporte o None.
    """
    if not _disponible():
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_CORTO) as client:
            for intento in range(max_intentos):
                await asyncio.sleep(intervalo)
                r = await client.get(f"{MIROFISH_BASE_URL}/api/report/generate/status/{report_id}")
                r.raise_for_status()
                data = r.json().get("data", {})
                if data.get("status") == "completed":
                    # Obtener contenido
                    r2 = await client.get(f"{MIROFISH_BASE_URL}/api/report/{report_id}")
                    r2.raise_for_status()
                    contenido = r2.json().get("data", {}).get("content", "")
                    logger.info(f"MiroFish: reporte {report_id} listo ({len(contenido)} chars)")
                    return contenido
                logger.debug(f"MiroFish: reporte en progreso (intento {intento+1}/{max_intentos})")
        logger.warning(f"MiroFish: timeout esperando reporte {report_id}")
        return None
    except Exception as e:
        logger.error(f"MiroFish esperar_reporte: {e}")
        return None


# ─── PIPELINE COMPLETO DE SIMULACIÓN ────────────────────────────────────────

async def pipeline_simulacion(
    project_id: str,
    graph_id: str,
    escenario: str,
    max_rondas: int = 10,
) -> str | None:
    """
    Ejecuta el pipeline completo de simulación y retorna el texto del reporte.
    Diseñado para correr como tarea asyncio en background.
    Retorna el contenido del reporte, o None si algo falla.
    """
    simulation_id = await crear_simulacion(project_id, graph_id)
    if not simulation_id:
        return None

    if not await preparar_simulacion(simulation_id, escenario):
        return None

    if not await iniciar_simulacion(simulation_id, max_rondas):
        return None

    if not await esperar_simulacion(simulation_id):
        return None

    report_id = await generar_reporte(simulation_id)
    if not report_id:
        return None

    return await esperar_reporte(report_id)
