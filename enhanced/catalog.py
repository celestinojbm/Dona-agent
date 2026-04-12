# enhanced/catalog.py — Catálogo de sistemas predefinidos para Dona 2.0

"""
Habilidad 3: Catálogo de Sistemas a Demanda.

Define los sistemas predefinidos que cualquier usuario puede activar.
Cada sistema tiene una plantilla JSONB que se instancia en user_systems.

Categorías:
  - habitos       — tracking de hábitos diarios
  - finanzas      — control de gastos, presupuesto
  - salud         — agua, ejercicio, sueño, medicamentos
  - productividad — pomodoro, metas semanales, proyectos
  - aprendizaje   — lectura, cursos, vocabulario
  - social        — contactos, cumpleaños, networking
  - hogar         — compras, limpieza, mantenimiento
  - negocio       — CRM simple, inventario, ventas
"""

import json
import logging
from enhanced.models import SystemCatalog, async_session_enhanced
from sqlalchemy import select

logger = logging.getLogger("dona.enhanced")

# ── Definiciones de sistemas ─────────────────────────────────────────────────

CATALOGO_INICIAL: list[dict] = [
    # ── Hábitos ──
    {
        "nombre": "Tracker de Hábitos",
        "categoria": "habitos",
        "descripcion": "Registra y da seguimiento a hábitos diarios. Define qué hábitos quieres trackear y marca cada día si los cumpliste.",
        "plantilla": {
            "habitos": [],
            "registro": {},
            "instrucciones": "Agrega hábitos con 'agregar hábito [nombre]'. Marca con 'hice [hábito]'. Ve tu progreso con 'mis hábitos'.",
        },
    },
    {
        "nombre": "Rutina Matutina",
        "categoria": "habitos",
        "descripcion": "Define y sigue tu rutina matutina paso a paso. Dona te recuerda cada paso y trackea tu consistencia.",
        "plantilla": {
            "pasos": [],
            "hora_inicio": "06:00",
            "registro": {},
            "instrucciones": "Define tu rutina con 'mi rutina matutina es: [pasos]'. Cada mañana di 'empiezo rutina' para activarla.",
        },
    },
    # ── Finanzas ──
    {
        "nombre": "Control de Gastos",
        "categoria": "finanzas",
        "descripcion": "Registra gastos diarios por categoría. Ve resúmenes semanales y mensuales de en qué gastas.",
        "plantilla": {
            "categorias": ["comida", "transporte", "entretenimiento", "servicios", "otros"],
            "gastos": [],
            "presupuesto_mensual": None,
            "instrucciones": "Registra con 'gasté $X en [categoría]'. Ve resumen con 'mis gastos' o 'gastos de la semana'.",
        },
    },
    {
        "nombre": "Presupuesto Mensual",
        "categoria": "finanzas",
        "descripcion": "Define un presupuesto por categoría y trackea cuánto llevas gastado vs. tu límite.",
        "plantilla": {
            "limites": {},
            "periodo_actual": None,
            "gastado": {},
            "instrucciones": "Define con 'presupuesto de [categoría]: $X'. Registra gastos normal. Di 'cómo voy de presupuesto' para ver estado.",
        },
    },
    # ── Salud ──
    {
        "nombre": "Hidratación",
        "categoria": "salud",
        "descripcion": "Trackea cuánta agua tomas al día. Dona te recuerda beber agua periódicamente.",
        "plantilla": {
            "meta_ml": 2000,
            "registro": {},
            "instrucciones": "Di 'tomé agua' o 'tomé X ml'. Ve tu progreso con 'cuánta agua llevo'. Cambia meta con 'mi meta de agua es X litros'.",
        },
    },
    {
        "nombre": "Registro de Ejercicio",
        "categoria": "salud",
        "descripcion": "Registra tus sesiones de ejercicio: tipo, duración e intensidad.",
        "plantilla": {
            "sesiones": [],
            "meta_semanal": 3,
            "instrucciones": "Registra con 'hice ejercicio: [tipo] [duración]'. Ve tu semana con 'mi ejercicio'.",
        },
    },
    {
        "nombre": "Tracker de Sueño",
        "categoria": "salud",
        "descripcion": "Registra a qué hora te duermes y despiertas. Ve patrones y promedio de horas.",
        "plantilla": {
            "registros": [],
            "meta_horas": 8,
            "instrucciones": "Di 'me dormí a las X' y 'me desperté a las X'. Ve patrones con 'mi sueño'.",
        },
    },
    # ── Productividad ──
    {
        "nombre": "Metas Semanales",
        "categoria": "productividad",
        "descripcion": "Define 3-5 metas clave cada semana y trackea tu avance diario.",
        "plantilla": {
            "metas_actuales": [],
            "historial_semanas": [],
            "instrucciones": "Define con 'mis metas de esta semana: [lista]'. Actualiza con 'avancé en [meta]'. Revisa con 'mis metas'.",
        },
    },
    {
        "nombre": "Diario / Journal",
        "categoria": "productividad",
        "descripcion": "Escribe entradas de diario. Dona guarda la fecha y puedes buscar por temas después.",
        "plantilla": {
            "entradas": [],
            "instrucciones": "Di 'diario: [tu entrada]' para escribir. Di 'mi diario' para ver entradas recientes.",
        },
    },
    # ── Aprendizaje ──
    {
        "nombre": "Lista de Lectura",
        "categoria": "aprendizaje",
        "descripcion": "Organiza libros que quieres leer, estás leyendo o ya terminaste.",
        "plantilla": {
            "por_leer": [],
            "leyendo": [],
            "terminados": [],
            "instrucciones": "Agrega con 'quiero leer [libro]'. Mueve con 'empecé [libro]' o 'terminé [libro]'. Ve con 'mis libros'.",
        },
    },
    {
        "nombre": "Notas de Aprendizaje",
        "categoria": "aprendizaje",
        "descripcion": "Guarda notas rápidas de cosas que aprendes. Organizado por tema.",
        "plantilla": {
            "notas": {},
            "instrucciones": "Di 'nota sobre [tema]: [contenido]'. Busca con 'notas de [tema]' o 'mis notas'.",
        },
    },
    # ── Social ──
    {
        "nombre": "Cumpleaños",
        "categoria": "social",
        "descripcion": "Registra cumpleaños de personas importantes. Dona te avisa un día antes.",
        "plantilla": {
            "personas": [],
            "instrucciones": "Agrega con 'cumpleaños de [nombre]: [fecha]'. Ve próximos con 'cumpleaños'.",
        },
    },
    # ── Hogar ──
    {
        "nombre": "Lista de Compras",
        "categoria": "hogar",
        "descripcion": "Lista de compras inteligente. Agrega, tacha y organiza por categoría.",
        "plantilla": {
            "items": [],
            "frecuentes": [],
            "instrucciones": "Agrega con 'comprar [item]'. Tacha con 'ya compré [item]'. Ve con 'lista de compras'.",
        },
    },
    {
        "nombre": "Mantenimiento del Hogar",
        "categoria": "hogar",
        "descripcion": "Trackea tareas de mantenimiento periódico: limpieza, revisiones, reparaciones.",
        "plantilla": {
            "tareas": [],
            "instrucciones": "Agrega con 'mantenimiento: [tarea] cada [frecuencia]'. Ve pendientes con 'mantenimiento del hogar'.",
        },
    },
    # ── Negocio ──
    {
        "nombre": "CRM Simple",
        "categoria": "negocio",
        "descripcion": "Gestión básica de contactos de negocio: clientes, prospectos, seguimiento.",
        "plantilla": {
            "contactos": [],
            "seguimientos_pendientes": [],
            "instrucciones": "Agrega con 'cliente: [nombre] [teléfono] [nota]'. Ve con 'mis clientes'. Programa seguimiento con 'dar seguimiento a [nombre] el [fecha]'.",
        },
    },
    {
        "nombre": "Registro de Ventas",
        "categoria": "negocio",
        "descripcion": "Registra ventas con monto, cliente y producto. Ve resúmenes por periodo.",
        "plantilla": {
            "ventas": [],
            "instrucciones": "Registra con 'venta: $X a [cliente] por [producto]'. Ve con 'mis ventas' o 'ventas de la semana'.",
        },
    },
]


async def sembrar_catalogo():
    """
    Inserta los sistemas predefinidos si la tabla está vacía.
    Idempotente: no duplica si ya existen.
    """
    async with async_session_enhanced() as session:
        result = await session.execute(select(SystemCatalog).limit(1))
        if result.scalar():
            logger.debug("[CATALOG] Catálogo ya tiene datos, saltando seed")
            return

        count = 0
        for sistema in CATALOGO_INICIAL:
            entry = SystemCatalog(
                nombre=sistema["nombre"],
                categoria=sistema["categoria"],
                descripcion=sistema["descripcion"],
                plantilla_json=json.dumps(sistema["plantilla"], ensure_ascii=False),
            )
            session.add(entry)
            count += 1

        await session.commit()
        logger.info(f"[CATALOG] Catálogo sembrado con {count} sistemas")


async def obtener_catalogo_activo() -> list[dict]:
    """Retorna todos los sistemas activos del catálogo."""
    async with async_session_enhanced() as session:
        result = await session.execute(
            select(SystemCatalog).where(SystemCatalog.activo == True)
        )
        sistemas = result.scalars().all()
        return [
            {
                "id": s.id,
                "nombre": s.nombre,
                "categoria": s.categoria,
                "descripcion": s.descripcion,
            }
            for s in sistemas
        ]


async def obtener_sistema_por_id(catalog_id: int) -> dict | None:
    """Retorna un sistema del catálogo por su ID, incluyendo la plantilla."""
    async with async_session_enhanced() as session:
        result = await session.execute(
            select(SystemCatalog).where(SystemCatalog.id == catalog_id)
        )
        s = result.scalar()
        if not s:
            return None
        return {
            "id": s.id,
            "nombre": s.nombre,
            "categoria": s.categoria,
            "descripcion": s.descripcion,
            "plantilla": json.loads(s.plantilla_json),
        }


async def obtener_sistema_por_nombre(nombre: str) -> dict | None:
    """Retorna un sistema del catálogo por nombre exacto."""
    async with async_session_enhanced() as session:
        result = await session.execute(
            select(SystemCatalog).where(SystemCatalog.nombre == nombre)
        )
        s = result.scalar()
        if not s:
            return None
        return {
            "id": s.id,
            "nombre": s.nombre,
            "categoria": s.categoria,
            "descripcion": s.descripcion,
            "plantilla": json.loads(s.plantilla_json),
        }
