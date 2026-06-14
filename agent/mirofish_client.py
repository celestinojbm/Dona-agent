# agent/mirofish_client.py — Cliente async para el motor MiroFish
# Integrado en Dona

"""
Cliente HTTP asíncrono para comunicarse con el microservicio MiroFish.
MiroFish expone una API REST (Flask) que proporciona:
  - Extracción de entidades y construcción de grafos de conocimiento (Zep Cloud)
  - Simulación de escenarios sociales (OASIS / camel-ai)
  - Generación de reportes (ReACT Agent)

Si MIROFISH_BASE_URL no está configurado, todas las funciones retornan None
y Dona opera normalmente sin esta funcionalidad.
"""

import asyncio
import logging
import os
from datetime import UTC

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("dona")

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


# ─── SIMULACIONES PROGRAMADAS (SCHEDULER) ────────────────────────────────────

# Escenarios predefinidos para simulaciones automáticas
ESCENARIOS_PROGRAMADOS = [
    {
        "id": "optimizacion_recursos",
        "nombre": "Optimización de Recursos",
        "descripcion": "Analiza cómo los fundadores y el equipo pueden optimizar el uso de recursos (tiempo, dinero, infraestructura, IA) para maximizar el impacto del producto.",
        "frecuencia": "lunes",
        "max_rondas": 10,
    },
    {
        "id": "crecimiento_usuarios",
        "nombre": "Estrategias de Crecimiento",
        "descripcion": "Simula cómo diferentes estrategias de adquisición de usuarios afectan el ecosistema de Dona, incluyendo retención, conversión y viralidad.",
        "frecuencia": "miercoles",
        "max_rondas": 10,
    },
    {
        "id": "riesgos_operacionales",
        "nombre": "Riesgos Operacionales",
        "descripcion": "Identifica y analiza los principales riesgos técnicos, de negocio y de equipo que enfrenta Dona Control, con recomendaciones de mitigación.",
        "frecuencia": "viernes",
        "max_rondas": 10,
    },
]


async def guardar_insight_en_zep(
    graph_id: str,
    escenario_id: str,
    escenario_nombre: str,
    contenido_reporte: str,
) -> bool:
    """
    Guarda el insight de una simulación completada en el grafo de Zep via MiroFish.
    Permite que Dona-agent recupere los insights en conversaciones futuras.
    Retorna True si se guardó exitosamente.
    """
    if not _disponible():
        return False
    try:
        from datetime import datetime
        fecha = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        resumen = contenido_reporte[:2000] if len(contenido_reporte) > 2000 else contenido_reporte
        async with httpx.AsyncClient(timeout=TIMEOUT_LARGO) as client:
            r = await client.post(
                f"{MIROFISH_BASE_URL}/api/graph/facts",
                json={
                    "graph_id": graph_id,
                    "facts": [
                        {
                            "fact": f"[INSIGHT SIMULACIÓN - {fecha}] Escenario: {escenario_nombre}\n\n{resumen}",
                            "source": f"mirofish_simulation_{escenario_id}",
                            "metadata": {
                                "tipo": "insight_simulacion",
                                "escenario_id": escenario_id,
                                "fecha": fecha,
                            }
                        }
                    ]
                },
            )
            if r.status_code in (200, 201):
                logger.info(f"MiroFish: insight '{escenario_id}' guardado en grafo {graph_id}")
                return True
            else:
                logger.warning(f"MiroFish guardar_insight: HTTP {r.status_code} — {r.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"MiroFish guardar_insight_en_zep: {e}")
        return False


async def pipeline_simulacion_programada(
    project_id: str,
    graph_id: str,
    escenario: dict,
    notificar_callback=None,
) -> dict:
    """
    Ejecuta una simulación programada completa y guarda el insight en Zep.

    Args:
        project_id: ID del proyecto MiroFish
        graph_id: ID del grafo Zep
        escenario: Dict con id, nombre, descripcion, max_rondas
        notificar_callback: Función async opcional para notificar al admin cuando termine

    Returns:
        Dict con {exito, escenario_id, reporte_resumen, error}
    """
    escenario_id = escenario["id"]
    escenario_nombre = escenario["nombre"]
    escenario_desc = escenario["descripcion"]
    max_rondas = escenario.get("max_rondas", 10)

    logger.info(f"[SCHEDULER] Iniciando simulación programada: {escenario_nombre}")

    try:
        reporte = await pipeline_simulacion(
            project_id=project_id,
            graph_id=graph_id,
            escenario=escenario_desc,
            max_rondas=max_rondas,
        )

        if not reporte:
            logger.error(f"[SCHEDULER] Simulación '{escenario_id}' falló — sin reporte")
            return {"exito": False, "escenario_id": escenario_id, "error": "pipeline_fallo"}

        guardado = await guardar_insight_en_zep(
            graph_id=graph_id,
            escenario_id=escenario_id,
            escenario_nombre=escenario_nombre,
            contenido_reporte=reporte,
        )

        resumen = reporte[:500] if len(reporte) > 500 else reporte
        logger.info(f"[SCHEDULER] Simulación '{escenario_id}' completada. Insight guardado: {guardado}")

        if notificar_callback:
            try:
                await notificar_callback(escenario_nombre, resumen)
            except Exception as e_notif:
                logger.warning(f"[SCHEDULER] Error en notificación: {e_notif}")

        return {
            "exito": True,
            "escenario_id": escenario_id,
            "reporte_resumen": resumen,
            "insight_guardado": guardado,
        }

    except Exception as e:
        logger.error(f"[SCHEDULER] Error en simulación programada '{escenario_id}': {e}")
        return {"exito": False, "escenario_id": escenario_id, "error": str(e)}
