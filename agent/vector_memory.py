"""
agent/vector_memory.py — Memoria vectorial con pgvector para Dona.

Guarda fragmentos de conversación como embeddings y permite búsqueda
semántica para recuperar contexto relevante de conversaciones pasadas.

Usa text-embedding-3-small de OpenAI (1536 dimensiones, $0.02/1M tokens).
Si no hay OPENAI_API_KEY, usa un embedding simulado para desarrollo.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims, $0.02/1M tokens
EMBEDDING_DIMS = 1536

# Tipos de mensajes que vale la pena vectorizar
_TIPOS_RELEVANTES = {
    "nombre", "proyecto", "meta", "objetivo", "cliente", "socio",
    "empresa", "trabajo", "familia", "preferencia", "habito", "rutina",
    "problema", "logro", "plan", "fecha", "lugar", "contacto"
}

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
    Elimina caracteres de control y reemplaza caracteres no-ASCII problemáticos
    por su equivalente ASCII más cercano (ej: \xd8 → espacio).
    """
    import unicodedata
    # Normalizar a NFC (forma compuesta) para unificar caracteres Unicode
    texto = unicodedata.normalize("NFC", texto)
    # Reemplazar saltos de línea por espacios
    texto = texto.replace("\n", " ").replace("\r", " ")
    # Eliminar caracteres de control (0x00-0x1F excepto espacio)
    texto = "".join(c for c in texto if ord(c) >= 0x20 or c == " ")
    return texto.strip()


async def generar_embedding(texto: str) -> Optional[list[float]]:
    """
    Genera un embedding de 1536 dimensiones para el texto dado.
    Usa OpenAI text-embedding-3-small.
    """
    if not OPENAI_API_KEY:
        logger.warning("[VECTOR] OPENAI_API_KEY no configurada — embeddings desactivados")
        return None

    try:
        import openai
        texto_limpio = _limpiar_texto(texto)
        if not texto_limpio:
            return None
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texto_limpio,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"[VECTOR] Error generando embedding: {e}")
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
        from agent.memory import _get_engine
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession

        engine = _get_engine()
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
        from agent.memory import _get_engine
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession

        engine = _get_engine()
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
