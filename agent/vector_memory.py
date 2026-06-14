"""
agent/vector_memory.py — Memoria vectorial con pgvector para Dona.

Guarda fragmentos de conversación como embeddings y permite búsqueda
semántica para recuperar contexto relevante de conversaciones pasadas.

Usa text-embedding-3-small de OpenAI (1536 dimensiones, $0.02/1M tokens).
Si no hay OPENAI_API_KEY, los embeddings quedan desactivados silenciosamente.
"""
from __future__ import annotations

import logging
import os
import unicodedata

import httpx

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
# Sanitizar la API key: eliminar cualquier carácter no-ASCII, espacios y saltos
_raw_key = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_KEY = _raw_key.encode("ascii", errors="ignore").decode("ascii").strip()
if _raw_key and _raw_key != OPENAI_API_KEY:
    logger.warning("[VECTOR] OPENAI_API_KEY contenía caracteres no-ASCII — se limpiaron automáticamente")

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims, $0.02/1M tokens
EMBEDDING_DIMS = 1536
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"

# Palabras clave que indican información personal relevante
_PALABRAS_CLAVE = [
    "me llamo", "mi nombre", "soy ", "trabajo en", "mi empresa",
    "mi cliente", "mi socio", "mi meta", "quiero lograr", "mi objetivo",
    "vivo en", "soy de", "tengo ", "mi proyecto", "estoy desarrollando",
    "mi número", "mi correo", "mi teléfono", "mi dirección",
    "prefiero", "me gusta", "no me gusta", "odio", "amo",
    "mi rutina", "cada mañana", "cada noche", "todos los días",
    "mi LLC", "mi negocio", "fundé", "cofundé", "lanzamos",
    "mi familia", "mi esposa", "mi esposo", "mis hijos", "mi pareja",
    "importante para mí", "lo más importante", "mi prioridad",
    "en los próximos", "para este año", "mi plan es",
]


def _es_mensaje_relevante(texto: str) -> bool:
    """Determina si un mensaje contiene información personal relevante para vectorizar."""
    if len(texto) < 20:
        return False
    texto_lower = texto.lower()
    return any(kw in texto_lower for kw in _PALABRAS_CLAVE)


def _limpiar_texto(texto: str) -> str:
    """
    Normaliza el texto para evitar errores de encoding.
    Preserva caracteres Unicode válidos (tildes, ñ, etc.) pero elimina
    caracteres de control y normaliza la forma Unicode.
    """
    # Normalizar a NFC (forma compuesta) para unificar caracteres Unicode
    texto = unicodedata.normalize("NFC", texto)
    # Reemplazar saltos de línea por espacios
    texto = texto.replace("\n", " ").replace("\r", " ")
    # Eliminar caracteres de control (0x00-0x1F) excepto espacio
    texto = "".join(c for c in texto if ord(c) >= 0x20)
    return texto.strip()


async def generar_embedding(texto: str) -> list[float] | None:
    """
    Genera un embedding de 1536 dimensiones para el texto dado.
    Usa la API REST de OpenAI directamente con httpx para evitar
    problemas de encoding del cliente oficial de OpenAI.
    """
    if not OPENAI_API_KEY:
        logger.warning("[VECTOR] OPENAI_API_KEY no configurada — embeddings desactivados")
        return None

    texto_limpio = _limpiar_texto(texto)
    if not texto_limpio:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENAI_EMBEDDINGS_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": texto_limpio,
                },
            )

        if response.status_code != 200:
            error_body = response.text[:200]
            logger.error(f"[VECTOR] OpenAI API error {response.status_code}: {error_body}")
            return None

        data = response.json()
        embedding = data["data"][0]["embedding"]
        return embedding

    except Exception as e:
        logger.error(f"[VECTOR] Error generando embedding: {type(e).__name__}: {e}")
        return None


async def guardar_en_memoria_vectorial(
    telefono: str,
    texto: str,
    tipo: str = "conversacion"
) -> bool:
    """
    Guarda un fragmento de texto como vector en la base de datos.
    Solo guarda si el mensaje contiene información personal relevante.
    Retorna True si se guardó, False si se omitió.
    """
    if not _es_mensaje_relevante(texto):
        return False

    embedding = await generar_embedding(texto)
    if embedding is None:
        return False

    try:
        from agent.memory import engine
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(engine) as session:
            await session.execute(
                text("""
                    INSERT INTO memoria_vectorial (telefono, texto, embedding, tipo)
                    VALUES (:telefono, :texto, CAST(:embedding AS vector), :tipo)
                """),
                {
                    "telefono": telefono,
                    "texto": texto[:2000],  # Limitar a 2000 chars
                    "embedding": str(embedding),
                    "tipo": tipo
                }
            )
            await session.commit()
        logger.info(f"[VECTOR] Guardado fragmento para {telefono}: '{texto[:60]}...'")
        return True
    except Exception as e:
        logger.error(f"[VECTOR] Error guardando en memoria vectorial: {e}")
        return False


async def buscar_memoria_relevante(
    telefono: str,
    consulta: str,
    limite: int = 5,
    umbral_similitud: float = 0.70
) -> list[dict]:
    """
    Busca en la memoria vectorial los fragmentos más relevantes para la consulta.
    Retorna lista de dicts con 'texto', 'fecha', 'similitud'.
    """
    if not OPENAI_API_KEY:
        return []

    embedding_consulta = await generar_embedding(consulta)
    if embedding_consulta is None:
        return []

    try:
        from agent.memory import engine
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(engine) as session:
            result = await session.execute(
                text("""
                    SELECT texto, fecha, 
                           1 - (embedding <=> CAST(:embedding AS vector)) AS similitud
                    FROM memoria_vectorial
                    WHERE telefono = :telefono
                      AND embedding IS NOT NULL
                      AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :umbral
                    ORDER BY embedding <=> CAST(:embedding AS vector)
                    LIMIT :limite
                """),
                {
                    "telefono": telefono,
                    "embedding": str(embedding_consulta),
                    "umbral": umbral_similitud,
                    "limite": limite
                }
            )
            rows = result.fetchall()

        return [
            {
                "texto": row[0],
                "fecha": row[1].strftime("%d/%m/%Y") if row[1] else "fecha desconocida",
                "similitud": round(float(row[2]), 3)
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"[VECTOR] Error buscando en memoria vectorial: {e}")
        return []


async def formatear_memoria_vectorial(resultados: list[dict]) -> str:
    """
    Formatea los resultados de búsqueda vectorial para inyectarlos al contexto de Claude.
    """
    if not resultados:
        return ""

    lineas = ["[Recuerdos relevantes de conversaciones anteriores]:"]
    for r in resultados:
        lineas.append(f"- \"{r['texto']}\" ({r['fecha']})")

    return "\n".join(lineas)
