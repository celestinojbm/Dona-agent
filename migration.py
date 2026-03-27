#!/usr/bin/env python3
# migration.py — Crea las tablas de Dona en Supabase PostgreSQL
#
# Ejecutar UNA SOLA VEZ desde tu máquina local:
#   python migration.py
#
# Requiere la URL de conexión DIRECTA de Supabase (puerto 5432, no el pooler).
# Puedes pasarla como variable de entorno o como argumento:
#   DATABASE_DIRECT_URL="postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres" python migration.py
#   python migration.py "postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres"

import sys
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# ── URL de conexión ────────────────────────────────────────────────────────────
# Prioridad: argumento CLI > variable de entorno DATABASE_DIRECT_URL > DATABASE_URL
def obtener_url() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    url = os.getenv("DATABASE_DIRECT_URL") or os.getenv("DATABASE_URL", "")
    # Quitar el prefijo de asyncpg si viene de .env
    for prefijo in ("postgresql+asyncpg://", "postgres+asyncpg://"):
        if url.startswith(prefijo):
            url = "postgresql://" + url[len(prefijo):]
    if not url or not url.startswith("postgresql"):
        print("ERROR: No se encontró la URL de Supabase.")
        print("Uso: python migration.py \"postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres\"")
        sys.exit(1)
    return url


# ── DDL de todas las tablas ────────────────────────────────────────────────────
TABLAS = [
    # Historial de mensajes por usuario
    """
    CREATE TABLE IF NOT EXISTS mensajes (
        id          SERIAL PRIMARY KEY,
        telefono    VARCHAR(50) NOT NULL,
        role        VARCHAR(20) NOT NULL,
        content     TEXT        NOT NULL,
        timestamp   TIMESTAMP   NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_mensajes_telefono ON mensajes (telefono)",

    # Zona horaria inferida por usuario
    """
    CREATE TABLE IF NOT EXISTS timezone_usuarios (
        telefono        VARCHAR(50) PRIMARY KEY,
        offset_minutos  INTEGER   NOT NULL DEFAULT 0,
        actualizado     TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,

    # Recordatorios (únicos y recurrentes)
    """
    CREATE TABLE IF NOT EXISTS recordatorios (
        id                  SERIAL PRIMARY KEY,
        telefono            VARCHAR(50)  NOT NULL,
        mensaje             TEXT         NOT NULL,
        fecha_hora          TIMESTAMP    NOT NULL,
        enviado             BOOLEAN      NOT NULL DEFAULT FALSE,
        creado              TIMESTAMP    NOT NULL DEFAULT NOW(),
        recurrencia         TEXT,
        cancelado           BOOLEAN      NOT NULL DEFAULT FALSE,
        offset_tz_minutos   INTEGER,
        fecha_fin           TIMESTAMP,
        intentos_fallidos   INTEGER      NOT NULL DEFAULT 0,
        ultimo_envio        TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_recordatorios_telefono  ON recordatorios (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_recordatorios_fecha_hora ON recordatorios (fecha_hora)",

    # Ciudad / país / ubicación temporal del usuario
    """
    CREATE TABLE IF NOT EXISTS usuario_ubicacion (
        telefono               VARCHAR(50) PRIMARY KEY,
        ciudad                 VARCHAR(100),
        pais                   VARCHAR(100),
        industria              VARCHAR(100),
        ciudad_actual          VARCHAR(100),
        ciudad_actual_expira   TIMESTAMP,
        actualizado            TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,

    # Registro de noticias enviadas (para no repetir)
    """
    CREATE TABLE IF NOT EXISTS noticias_enviadas (
        id          SERIAL PRIMARY KEY,
        telefono    VARCHAR(50)  NOT NULL,
        url_hash    VARCHAR(32)  NOT NULL,
        enviada_en  TIMESTAMP    NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_noticias_enviadas_telefono ON noticias_enviadas (telefono)",

    # Estado emocional actual por usuario
    """
    CREATE TABLE IF NOT EXISTS usuario_estado_emocional (
        telefono                VARCHAR(50) PRIMARY KEY,
        estado                  VARCHAR(20)  NOT NULL DEFAULT 'neutral',
        intensidad              INTEGER      NOT NULL DEFAULT 1,
        actualizado             TIMESTAMP,
        ultimo_aviso_sobrecarga TIMESTAMP
    )
    """,

    # Historial de eventos emocionales
    """
    CREATE TABLE IF NOT EXISTS eventos_emocionales (
        id          SERIAL PRIMARY KEY,
        telefono    VARCHAR(50) NOT NULL,
        estado      VARCHAR(20) NOT NULL,
        intensidad  INTEGER     NOT NULL DEFAULT 1,
        timestamp   TIMESTAMP   NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_eventos_emocionales_telefono  ON eventos_emocionales (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_eventos_emocionales_timestamp ON eventos_emocionales (timestamp)",

    # Estado del onboarding conversacional
    """
    CREATE TABLE IF NOT EXISTS usuario_onboarding (
        telefono        VARCHAR(50) PRIMARY KEY,
        nombre          VARCHAR(100) NOT NULL DEFAULT '',
        fase            INTEGER      NOT NULL DEFAULT 0,
        paso            INTEGER      NOT NULL DEFAULT 0,
        contexto        TEXT         NOT NULL DEFAULT '',
        actualizado     TIMESTAMP    NOT NULL DEFAULT NOW(),
        completado_en   TIMESTAMP,
        registrado_en   TIMESTAMP    NOT NULL DEFAULT NOW()
    )
    """,

    # Configuración de proactividad por usuario
    """
    CREATE TABLE IF NOT EXISTS usuario_proactividad (
        telefono                    VARCHAR(50) PRIMARY KEY,
        proactive_enabled           BOOLEAN   NOT NULL DEFAULT TRUE,
        morning_brief_hour          INTEGER   NOT NULL DEFAULT 8,
        mensajes_hoy                INTEGER   NOT NULL DEFAULT 0,
        ultimo_reset                TIMESTAMP,
        ultimo_morning_brief        TIMESTAMP,
        ultimo_weekly_review        TIMESTAMP,
        ultimo_conflict_check       TIMESTAMP,
        ultimo_consejo_estrategico  TIMESTAMP
    )
    """,

    # Eventos de comportamiento para análisis de patrones
    """
    CREATE TABLE IF NOT EXISTS eventos_comportamiento (
        id            SERIAL PRIMARY KEY,
        telefono      VARCHAR(50) NOT NULL,
        tipo          VARCHAR(50) NOT NULL,
        hora_dia      INTEGER     NOT NULL,
        dia_semana    INTEGER     NOT NULL,
        metadata_json TEXT,
        timestamp     TIMESTAMP   NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_eventos_comportamiento_telefono  ON eventos_comportamiento (telefono)",
    "CREATE INDEX IF NOT EXISTS ix_eventos_comportamiento_timestamp ON eventos_comportamiento (timestamp)",

    # Perfil de aprendizaje semanal
    """
    CREATE TABLE IF NOT EXISTS perfil_aprendizaje (
        telefono            VARCHAR(50) PRIMARY KEY,
        perfil              TEXT        NOT NULL DEFAULT '',
        actualizado         TIMESTAMP   NOT NULL DEFAULT NOW(),
        eventos_analizados  INTEGER     NOT NULL DEFAULT 0
    )
    """,

    # Estado MiroFish (grafo de conocimiento)
    """
    CREATE TABLE IF NOT EXISTS usuario_mirofish (
        telefono            VARCHAR(50) PRIMARY KEY,
        project_id          VARCHAR(100),
        graph_id            VARCHAR(100),
        actualizado         TIMESTAMP   NOT NULL DEFAULT NOW(),
        contexto_pendiente  TEXT        NOT NULL DEFAULT '',
        mensajes_desde_sync INTEGER     NOT NULL DEFAULT 0
    )
    """,

    # ── Migraciones incrementales (ALTER TABLE) ──────────────────────────────
    # Estas se ejecutan después de los CREATE TABLE para agregar columnas nuevas
    # a tablas que ya existían. Son idempotentes gracias al IF NOT EXISTS implícito
    # (PostgreSQL lanza error si la columna ya existe, que se captura abajo).
    "ALTER TABLE usuario_mirofish ADD COLUMN contexto_pendiente TEXT DEFAULT ''",
    "ALTER TABLE usuario_mirofish ADD COLUMN mensajes_desde_sync INTEGER DEFAULT 0",
    "ALTER TABLE usuario_proactividad ADD COLUMN ultimo_consejo_estrategico TIMESTAMP",
    "ALTER TABLE timezone_usuarios ADD COLUMN timezone_nombre VARCHAR(60)",
]


def main():
    url = obtener_url()
    # Ocultar contraseña en los logs
    url_log = url.split("@")[-1] if "@" in url else url
    print(f"Conectando a: {url_log}")

    try:
        # psycopg2 usa sslmode=require para Supabase
        if "sslmode" not in url:
            sep = "&" if "?" in url else "?"
            url_conn = f"{url}{sep}sslmode=require"
        else:
            url_conn = url

        conn = psycopg2.connect(url_conn)
        conn.autocommit = True
        cur = conn.cursor()
        print("Conexión establecida ✓\n")
    except Exception as e:
        print(f"ERROR al conectar: {e}")
        sys.exit(1)

    errores = 0
    for i, ddl in enumerate(TABLAS, 1):
        ddl_strip = ddl.strip()
        nombre = ddl_strip.split("\n")[0][:60].strip()
        try:
            cur.execute(ddl_strip)
            print(f"  [{i:02d}] OK  — {nombre}")
        except Exception as e:
            print(f"  [{i:02d}] ERR — {nombre}")
            print(f"         {e}")
            errores += 1

    cur.close()
    conn.close()

    print(f"\n{'='*50}")
    if errores == 0:
        print(f"Migración completa. {len(TABLAS)} sentencias ejecutadas sin errores.")
        print("Ya puedes hacer deploy en Render y Dona usará estas tablas.")
    else:
        print(f"Migración completada con {errores} error(es). Revisa los mensajes de arriba.")
    print('='*50)


if __name__ == "__main__":
    main()
