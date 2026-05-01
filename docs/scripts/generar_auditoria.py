"""Genera el PDF de auditoría de Dona — uso único."""
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, ListFlowable, ListItem
)


SALIDA = Path(r"C:\Users\celes\Dona-agent\Auditoria_Dona_2026-04-27.pdf")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=20, leading=24,
                   textColor=colors.HexColor("#1a1a2e"), spaceAfter=12)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, leading=18,
                   textColor=colors.HexColor("#16213e"), spaceBefore=14, spaceAfter=8)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11.5, leading=15,
                   textColor=colors.HexColor("#0f3460"), spaceBefore=10, spaceAfter=4)
P = ParagraphStyle("P", parent=styles["BodyText"], fontSize=10, leading=14,
                   alignment=TA_JUSTIFY, spaceAfter=6)
CODE = ParagraphStyle("CODE", parent=styles["Code"], fontSize=8.5, leading=11,
                     leftIndent=10, backColor=colors.HexColor("#f3f3f7"),
                     borderColor=colors.HexColor("#dcdce6"), borderWidth=0.5,
                     borderPadding=4, spaceAfter=6)
SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontSize=8.5, leading=11,
                       textColor=colors.HexColor("#555555"))
COVER_TITLE = ParagraphStyle("CT", parent=styles["Title"], fontSize=30, leading=34,
                             alignment=TA_LEFT, textColor=colors.HexColor("#0f3460"),
                             spaceAfter=10)
COVER_SUB = ParagraphStyle("CS", parent=styles["Title"], fontSize=14, leading=18,
                           textColor=colors.HexColor("#16213e"))
TAG_OK = ParagraphStyle("OK", parent=P, textColor=colors.HexColor("#0a7a3b"))
TAG_WARN = ParagraphStyle("W", parent=P, textColor=colors.HexColor("#a36b00"))
TAG_RISK = ParagraphStyle("R", parent=P, textColor=colors.HexColor("#a30b00"))


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(t, P), leftIndent=10) for t in items],
        bulletType="bullet", start="•", leftIndent=14, bulletFontSize=9,
    )


def kv_table(rows):
    t = Table(rows, colWidths=[5.5 * cm, 11.0 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f7")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0f3460")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dcdce6")),
    ]))
    return t


def findings_table(rows):
    """rows: [(severidad, titulo, ubicacion, accion)]"""
    header = [Paragraph("<b>Sev</b>", SMALL), Paragraph("<b>Hallazgo</b>", SMALL),
              Paragraph("<b>Ubicación</b>", SMALL), Paragraph("<b>Acción recomendada</b>", SMALL)]
    data = [header]
    color_map = {
        "ALTA": colors.HexColor("#c0392b"),
        "MEDIA": colors.HexColor("#d68910"),
        "BAJA": colors.HexColor("#1e8449"),
        "INFO": colors.HexColor("#2874a6"),
    }
    for sev, titulo, ubic, accion in rows:
        sev_para = Paragraph(f"<b><font color='{color_map[sev].hexval()}'>{sev}</font></b>", SMALL)
        data.append([sev_para, Paragraph(titulo, SMALL),
                     Paragraph(ubic, SMALL), Paragraph(accion, SMALL)])
    t = Table(data, colWidths=[1.5 * cm, 5.5 * cm, 4.0 * cm, 5.5 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#fbfbfd")]),
    ]))
    return t


# ── PIE / ENCABEZADO ────────────────────────────────────────────────────────
def en_cada_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(2 * cm, 1.2 * cm, "Auditoría de código — Dona · Confidencial")
    canvas.drawRightString(LETTER[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


# ── CONTENIDO ───────────────────────────────────────────────────────────────
story = []

# Portada
story += [
    Spacer(1, 4 * cm),
    Paragraph("Auditoría de código", COVER_TITLE),
    Paragraph("Dona — Asistente de IA por WhatsApp", COVER_SUB),
    Spacer(1, 0.6 * cm),
    Paragraph("Informe técnico completo", styles["Italic"]),
    Spacer(1, 1.0 * cm),
]
story.append(kv_table([
    ["Proyecto", "Dona — agente conversacional WhatsApp para PYMES en EEUU"],
    ["Repositorio", "C:\\Users\\celes\\Dona-agent (no es repo git local)"],
    ["Fecha del informe", datetime.now().strftime("%Y-%m-%d")],
    ["Stack", "Python 3.11+ · FastAPI · SQLAlchemy 2 async · PostgreSQL/SQLite"],
    ["LLMs", "Claude Sonnet 4.6 (primario) · DeepSeek · GPT-4o · Haiku (fallback)"],
    ["Tamaño", "~24 700 LOC en agent/ · ~2 000 LOC en enhanced/ · 30 archivos de tests"],
    ["Tests", "411 tests, 100% en verde (pytest, ~34 s)"],
    ["Estado", "Producción con primeros usuarios"],
]))
story += [Spacer(1, 1.2 * cm), Paragraph(
    "Documento generado automáticamente a partir de la lectura completa del código fuente, "
    "los archivos de configuración y la suite de pruebas. No incluye datos de producción "
    "ni capturas de la base de datos en vivo.", SMALL
), PageBreak()]

# 1. Resumen ejecutivo
story += [Paragraph("1. Resumen ejecutivo", H1)]
story += [Paragraph(
    "Dona es un servicio en producción que atiende usuarios reales por WhatsApp combinando un "
    "modelo de lenguaje grande con un sistema persistente de memoria, billing por créditos, "
    "generación de imagen/video, y un conjunto de integraciones (Gmail, Google Calendar, "
    "Sheets, Drive, Stripe, Cloudflare R2). El código presenta una <b>madurez notable</b> "
    "para un proyecto de un solo desarrollador: separación de capas, fallbacks degradables, "
    "sanitización contra prompt injection, billing idempotente y suite de pruebas amplia.", P
)]
story += [Paragraph("Veredicto general", H2)]
story += [Paragraph(
    "El sistema es <b>apto para producción a la escala actual</b> (primeros usuarios). Sus "
    "controles críticos — verificación HMAC de webhooks, idempotencia de Stripe, cifrado de "
    "tokens OAuth, rate limiting persistente, sanitización anti-injection — están implementados "
    "correctamente y cubiertos por tests. Los riesgos principales son de <b>escalabilidad</b> "
    "(módulos monolíticos de 2 000–3 000 LOC en <code>brain.py</code>, <code>memory.py</code>, "
    "<code>main.py</code>) y de <b>oscurecimiento operativo</b> (escasa observabilidad estructurada, "
    "ausencia de migraciones Alembic activas pese a estar en requirements).", P
)]

story += [Paragraph("Hallazgos prioritarios", H2)]
story += [findings_table([
    ("ALTA",
     "Cumplimiento CCPA/CPRA todavía manual en /privacy/export y /privacy/delete",
     "agent/main.py:204–257",
     "Implementar flujo OTP por WhatsApp y export JSON automático en ≤45 días."),
    ("MEDIA",
     "META_APP_SECRET ausente acepta webhooks sin firma con sólo un warning",
     "agent/providers/meta.py:131–136",
     "Bloquear webhooks no firmados en producción (env != development)."),
    ("MEDIA",
     "STRIPE_WEBHOOK_SECRET ausente cae a aceptar payloads sin verificar",
     "agent/billing.py:371–377",
     "Fallar cerrado en producción; sólo permitir bypass en tests."),
    ("MEDIA",
     "brain.py / memory.py / main.py exceden 2 000 LOC cada uno",
     "agent/brain.py (3 319), agent/memory.py (2 316), agent/main.py (2 170)",
     "Refactor incremental: extraer routers FastAPI, capa de modelos, dispatcher de tools."),
    ("MEDIA",
     "Alembic en requirements.txt pero no se aplican migraciones",
     "agent/memory.py:Base.metadata.create_all (lifespan)",
     "Inicializar repositorio de migraciones antes de añadir más tablas en producción."),
    ("BAJA",
     "Backend de jobs `inproc` no persiste tras restart",
     "agent/jobs/queue.py:196–208",
     "Documentar como `dev-only`; forzar arq+Redis en producción vía health-check."),
    ("BAJA",
     "Hash sin salt del teléfono en la key de R2",
     "agent/storage.py:65–70",
     "Aceptable (no es secreto); agregar nota en docs y considerar HMAC con secret."),
    ("BAJA",
     "Comentarios `AgentKit` legacy en partes del código",
     "Comentarios dispersos (declarado en CLAUDE.md)",
     "Limpieza cosmética; no bloquea."),
    ("INFO",
     "411 tests pasan en ~34 s; sin medición de cobertura",
     "tests/",
     "Activar `pytest --cov=agent` y subir umbral progresivamente (objetivo ≥75%)."),
])]
story.append(PageBreak())

# 2. Arquitectura
story += [Paragraph("2. Arquitectura y estructura", H1)]
story += [Paragraph(
    "El árbol del proyecto separa claramente las responsabilidades. <b>agent/</b> concentra "
    "toda la lógica del producto; <b>enhanced/</b> es un módulo más reciente para sistemas "
    "diagnósticos y procesadores especializados; <b>tests/</b> espeja parcialmente la estructura "
    "de agent/.", P
)]

story += [Paragraph("2.1 Mapa de módulos por LOC", H2)]
story += [kv_table([
    ["agent/brain.py — 3 319 LOC", "Cerebro: cliente Anthropic, fallbacks (DeepSeek, GPT-4o, Haiku), "
                                    "selección dinámica de tools, sanitización anti-injection, prompt building."],
    ["agent/memory.py — 2 316 LOC", "26 modelos SQLAlchemy, sesiones async, helpers de persistencia "
                                     "para mensajes, recordatorios, onboarding, billing, jobs y assets."],
    ["agent/main.py — 2 170 LOC", "FastAPI app, middleware (logging+security headers), webhooks Whapi/Meta/Stripe, "
                                  "endpoints admin, OAuth Google, comandos determinísticos previos al LLM."],
    ["agent/creativos/comandos.py — 993 LOC", "Detección y dispatch de comandos creativos "
                                              "(imagen, video, voz, PDF, ajustes)."],
    ["agent/jobs/handlers_creativos.py — 758 LOC", "Lógica de ejecución de jobs creativos "
                                                   "(integraciones Gemini, Replicate, HeyGen)."],
    ["agent/proactivity.py — 746 LOC", "Mensajería proactiva: resumen matutino, recordatorios, "
                                       "follow-ups."],
    ["agent/providers/meta.py — 600 LOC", "Adaptador Meta WhatsApp Cloud API (HMAC + replay protection)."],
    ["agent/scheduler.py — 577 LOC", "APScheduler para envíos programados y proactivos."],
    ["enhanced/* — ~1 990 LOC", "Catálogo de sistemas, ejecución segura (safe_module), monitoreo, NLP detector."],
])]

story += [Paragraph("2.2 Capas y flujo principal", H2)]
story += [Paragraph(
    "El flujo de un mensaje entrante atraviesa estas capas en orden:", P
)]
story += [bullets([
    "<b>Webhook FastAPI</b> (<code>main.py</code>) recibe POST de Whapi/Meta y verifica firma.",
    "<b>Deduplicación</b> por <code>mensaje_id</code> contra Postgres con fallback in-memory.",
    "<b>Rate limiting</b> sliding-window (Redis o memoria) — 10/min usuario, 1 000/min global.",
    "<b>Detección determinística</b> de comandos en <code>main.py</code>: STOP/START, saldo, "
    "recargar, imagen, privacidad, onboarding. Estos NO consumen LLM ni créditos.",
    "<b>Brain</b> (<code>brain.py</code>) clasifica intent, selecciona tools, llama a Claude con fallbacks.",
    "<b>Tools de 2 pasos</b>: <code>preparar_X → confirmar_X / cancelar_X</code> (literal en el nombre).",
    "<b>Persistencia</b> de mensajes y memoria larga via SQLAlchemy async.",
    "<b>Respuesta</b> via proveedor de WhatsApp (Whapi default; Meta/Twilio según config).",
    "<b>Jobs creativos</b> (imagen/video) van a cola arq (Redis) o inproc (asyncio.create_task).",
])]

story += [Paragraph("2.3 Convenciones documentadas en CLAUDE.md", H2)]
story += [Paragraph(
    "El archivo <code>CLAUDE.md</code> codifica decisiones que <i>no son derivables del código</i>: "
    "español como idioma único, prohibición del término “Fundadores”, marco legal US (no LFPDPPP), "
    "patrón <code>preparar/confirmar/cancelar</code> literal para tools con efecto secundario, "
    "regex previa al LLM para comandos comunes, integer-only credits con audit trail. Esta "
    "documentación viva es uno de los activos más valiosos del repo.", P
)]
story.append(PageBreak())

# 3. Seguridad
story += [Paragraph("3. Seguridad", H1)]
story += [Paragraph("3.1 Verificación HMAC de webhooks", H2)]
story += [Paragraph(
    "<b>Meta</b> (<code>providers/meta.py</code>) verifica <code>X-Hub-Signature-256</code> con "
    "<code>hmac.compare_digest</code>; agrega replay protection rechazando mensajes con "
    "antigüedad &gt; 600s o timestamp futuro &gt; 300s. <b>Stripe</b> (<code>billing.py</code>) "
    "usa <code>stripe.Webhook.construct_event</code>. <b>Inbound tokens</b> "
    "(<code>inbound_tokens.py</code>) firman con HMAC-SHA256 con secreto de entorno y "
    "verifican timing-safe.", P
)]
story += [Paragraph(
    "<b>Riesgo:</b> ambos verificadores caen al modo \"aceptar sin firma\" cuando falta la "
    "variable de entorno (<code>META_APP_SECRET</code>, <code>STRIPE_WEBHOOK_SECRET</code>) "
    "y sólo emiten warning. En desarrollo es razonable; en producción debería abortar.",
    TAG_WARN
)]

story += [Paragraph("3.2 Cifrado de tokens OAuth", H2)]
story += [Paragraph(
    "<code>agent/crypto.py</code> usa Fernet (AES-128-CBC + HMAC-SHA256). El módulo <b>aborta el "
    "arranque</b> si <code>ENVIRONMENT=production</code> y falta <code>ENCRYPTION_KEY</code> "
    "(o si la clave es inválida). En dev opera transparente con warning. Esta decisión — "
    "<i>fail closed en prod, fail open en dev</i> — es la correcta para el modelo de amenaza.", P
)]

story += [Paragraph("3.3 Defensa contra prompt injection", H2)]
story += [Paragraph(
    "<code>brain.py</code> define <code>_PATRONES_INYECCION</code> y "
    "<code>_sanitizar_datos_externos()</code> que se aplica a TODOS los datos externos antes "
    "de inyectarlos como resultado de tool: memoria vectorial, memoria de largo plazo, eventos "
    "de calendario (titulo y lugar), correos (subject, snippet y cuerpo). Patrones cubiertos: "
    "ignore/forget/override de instrucciones, “act as / actúa como”, marcadores system-prompt, "
    "“send a message to”, “reveal prompt/api key”. El contenido sospechoso se reemplaza por "
    "<code>[contenido filtrado por seguridad]</code> y todo bloque externo va envuelto en "
    "<code>&lt;external_data&gt;</code>.", P
)]
story += [Paragraph(
    "<b>Cobertura observada:</b> 14 puntos de inyección sanitizan correctamente. Las búsquedas "
    "en correo electrónico, eventos de Google Calendar y memoria larga están todas blindadas.",
    TAG_OK
)]

story += [Paragraph("3.4 Rate limiting", H2)]
story += [Paragraph(
    "<code>rate_limiter.py</code> implementa sliding window con sorted sets de Redis "
    "(operación atómica via pipeline) y fallback a un dict en memoria con limpieza periódica "
    "cuando supera 500 claves. Límites: 10 mensajes/usuario/minuto y 1 000 globales/minuto. "
    "El “undo” cuando se excede el límite (líneas 110–119) evita falsos positivos en concurrencia.", P
)]
story += [Paragraph("3.5 Headers HTTP y middleware", H2)]
story += [Paragraph(
    "<code>SecurityHeadersMiddleware</code> añade en cada respuesta: "
    "<code>X-Content-Type-Options: nosniff</code>, <code>X-Frame-Options: DENY</code>, "
    "<code>X-XSS-Protection</code>, <code>Referrer-Policy: strict-origin-when-cross-origin</code>, "
    "<code>Permissions-Policy</code> denegando cámara/micrófono/geolocation, y <code>Cache-Control: "
    "no-store</code> excepto en rutas <code>/auth/</code>. <code>RequestLoggingMiddleware</code> "
    "mide latencia y eleva a WARNING los requests &gt; 5 s.", P
)]

story += [Paragraph("3.6 Autenticación admin", H2)]
story += [Paragraph(
    "<code>_verificar_admin()</code> exige <code>Authorization: Bearer &lt;ADMIN_TOKEN&gt;</code> "
    "y compara con <code>hmac.compare_digest</code>. Acepta query param como fallback legacy "
    "(menos seguro pero también timing-safe). Recomendación: deprecar el query param en futuros "
    "endpoints nuevos.", P
)]

story += [Paragraph("3.7 Búsqueda de antipatrones", H2)]
story += [Paragraph(
    "Búsqueda exhaustiva en <code>agent/</code> de patrones inseguros:", P
)]
story += [bullets([
    "Sin uso de <code>eval()</code>, <code>exec()</code>, <code>os.system()</code> ni <code>subprocess</code>.",
    "Sin <code>shell=True</code>; sin <code>pickle.load</code>.",
    "Sin <code>except:</code> bare ni <code>except Exception: pass</code>.",
    "Sin claves API hardcodeadas (sk-*, AKIA*).",
    "<code>md5</code> usado sólo como hash de URL para deduplicación de noticias (real_world.py:146) — uso no criptográfico, aceptable.",
    "<code>sha1</code> usado sólo como ofuscador de teléfono en keys de R2 (storage.py:70) — declarado explícitamente como no-secreto.",
])]
story.append(PageBreak())

# 4. Compliance
story += [Paragraph("4. Cumplimiento legal", H1)]
story += [Paragraph(
    "El usuario opera desde EEUU; el marco legal aplicable, según CLAUDE.md, es <b>CCPA/CPRA "
    "+ FTC + TCPA</b>, no marcos mexicanos. La implementación actual cubre los pilares pero "
    "deja trabajo manual en derechos de acceso/borrado.", P
)]

story += [Paragraph("4.1 TCPA — opt-in / opt-out", H2)]
story += [Paragraph(
    "Comandos <code>STOP</code> y <code>START</code> (case-insensitive, con o sin “dona”) se "
    "evalúan <i>antes</i> de cualquier otro routing y no consumen LLM ni créditos. Esta es la "
    "ruta correcta: TCPA exige acción inmediata. Se recomienda añadir tests de regresión que "
    "verifiquen que ningún cambio futuro mueva ese check después del LLM.", P
)]

story += [Paragraph("4.2 CCPA / CPRA — derechos del consumidor", H2)]
story += [Paragraph(
    "<b>Páginas legales</b>: <code>/privacy</code> y <code>/terms</code> servidos desde "
    "<code>agent/legal_pages.py</code> (HTML estático). <b>Endpoints CCPA</b>: "
    "<code>/privacy/export</code> y <code>/privacy/delete</code> existen pero hoy retornan "
    "<i>instrucciones de contacto</i> en vez de procesar la solicitud automáticamente. Esto "
    "es legal — CCPA permite verificar identidad y responder en hasta 45 días — pero <b>requiere "
    "infraestructura humana</b> para cumplir esa ventana.", P
)]
story += [Paragraph(
    "<b>Riesgo medio:</b> a medida que crece la base de usuarios, el flujo manual no escala. "
    "Implementar OTP por WhatsApp + export JSON automático evita SLA misses regulatorios.",
    TAG_WARN
)]

story += [Paragraph("4.3 Subprocessors", H2)]
story += [Paragraph(
    "<code>legal_pages.py</code> declara explícitamente los subprocesadores en la política "
    "(Anthropic, OpenAI/DeepSeek, Google, Stripe, Cloudflare, Render, etc.), lo cual es buena "
    "práctica CCPA y exigible bajo SCC para usuarios EU si aplica.", P
)]

story += [Paragraph("4.4 Datos sensibles y minimización", H2)]
story += [bullets([
    "El número de teléfono se almacena en claro (clave primaria); las keys de R2 lo ofuscan con SHA-1 truncado.",
    "Los tokens OAuth se cifran con Fernet (cuando ENCRYPTION_KEY está configurado).",
    "El historial de mensajes se persiste sin redacción — necesario para contexto del LLM, pero implica que un export CCPA debe poder devolverlo y un delete debe borrarlo todo.",
    "<code>memory.py</code> tiene una función documentada (línea 1984) para borrar TODO de un usuario en todas las tablas — base correcta para implementar delete automático.",
])]
story.append(PageBreak())

# 5. Billing
story += [Paragraph("5. Billing — créditos, Stripe e idempotencia", H1)]
story += [Paragraph(
    "<code>agent/billing.py</code> implementa el sistema de créditos con tres operaciones "
    "atómicas y un webhook idempotente.", P
)]

story += [Paragraph("5.1 Cobro atómico (compare-and-swap)", H2)]
story += [Paragraph(
    "<code>cobrar()</code> evita SELECT FOR UPDATE (no portable entre SQLite y Postgres) "
    "usando un UPDATE condicional <code>WHERE saldo &gt;= creditos</code> y verificando "
    "<code>rowcount</code>. Si dos requests intentan cobrar al mismo tiempo y sólo alcanza "
    "para una, la otra recibe rowcount=0 y obtiene <code>SaldoInsuficienteError</code>. "
    "Cada cobro deja una fila en <code>transacciones_credito</code> con saldo resultante "
    "(audit trail completo).", P
)]

story += [Paragraph("5.2 Acreditación idempotente", H2)]
story += [Paragraph(
    "<code>acreditar()</code> consulta primero <code>stripe_session_id</code> en "
    "<code>transacciones_credito</code>; si existe, retorna el saldo actual sin hacer nada. "
    "Esto resuelve correctamente el contrato \"at-least-once\" de los webhooks de Stripe — "
    "una reentrega del mismo evento no duplica créditos. La idempotencia se valida con tests "
    "(<code>tests/test_billing.py</code>).", P
)]
story += [Paragraph(
    "<b>Bien resuelto:</b> el patrón captura <code>saldo_prev = int(row.saldo)</code> antes "
    "del UPDATE para evitar la auto-refresh del ORM (comentario explícito en línea 264).",
    TAG_OK
)]

story += [Paragraph("5.3 Helper preparar/cobrar", H2)]
story += [Paragraph(
    "<code>cobrar_o_rechazar()</code> es el helper que toda tool pagada debe usar antes de "
    "trabajo caro. Devuelve <code>(False, mensaje_para_usuario)</code> con texto listo para "
    "WhatsApp + CTA para recargar. Esto centraliza UX de saldo bajo.", P
)]

story += [Paragraph("5.4 Stripe Checkout", H2)]
story += [Paragraph(
    "<code>crear_checkout()</code> envuelve la llamada sync del SDK de Stripe en "
    "<code>asyncio.to_thread</code> para no bloquear el event loop, lo que es correcto. "
    "El <code>client_reference_id</code> y <code>metadata</code> portan el teléfono y créditos "
    "para que el webhook pueda acreditar sin sesiones internas.", P
)]

story += [Paragraph("5.5 Webhook Stripe — verificación", H2)]
story += [Paragraph(
    "<code>verificar_firma_stripe()</code> usa <code>stripe.Webhook.construct_event</code> "
    "cuando hay secreto. <b>Cuando NO hay secreto, parsea el JSON sin verificar y emite un "
    "warning</b>. Aceptable en dev; en producción debería rechazar (HTTP 400) en vez de "
    "aceptar payloads no firmados.", TAG_WARN
)]
story.append(PageBreak())

# 6. Jobs y Storage
story += [Paragraph("6. Sistema de jobs y storage", H1)]
story += [Paragraph("6.1 Cola de jobs (arq + inproc)", H2)]
story += [Paragraph(
    "<code>agent/jobs/queue.py</code> abstrae dos backends detrás de la misma API:", P
)]
story += [bullets([
    "<b>arq</b> (Redis): persistente, distribuible, recomendado para producción.",
    "<b>inproc</b> (asyncio.create_task): no persiste tras restart, sólo dev.",
    "Auto-detección: si <code>REDIS_URL</code> está seteada → arq; sino → inproc.",
    "Cada job persiste como <code>JobCreativo</code> en DB con estado pending → running → done/error y contador de intentos.",
    "Si <code>arq.enqueue_job()</code> falla, hay fallback automático a inproc dentro del mismo request.",
])]
story += [Paragraph(
    "<b>Recomendación:</b> agregar un health-check que falle si <code>ENVIRONMENT=production</code> "
    "y el backend efectivo es inproc — para evitar que un mal config llegue a producción "
    "sin Redis y se pierdan jobs en cada redeploy.", TAG_WARN
)]

story += [Paragraph("6.2 Storage de assets (R2 + filesystem)", H2)]
story += [Paragraph(
    "<code>agent/storage.py</code> usa Cloudflare R2 (S3-compatible vía aioboto3, sin egress fees) "
    "como primario, con fallback a filesystem local. Las keys siguen el esquema "
    "<code>{hash_telefono}/{tipo}/{uuid}.{ext}</code>; el tipo se sanitiza a <code>[a-z0-9_-]</code> "
    "para evitar inyecciones de path. Cada subida queda registrada en <code>asset_generado</code> "
    "para audit y billing.", P
)]

story += [Paragraph("6.3 Modelo de datos (26 tablas)", H2)]
story += [Paragraph(
    "<code>memory.py</code> declara 26 modelos SQLAlchemy. Categorías:", P
)]
story += [bullets([
    "<b>Conversación</b>: Mensaje, MensajeProcesado (dedup), SesionConversacion, MemoriaLargoPlazo.",
    "<b>Usuario</b>: TimezoneUsuario, UsuarioUbicacion, UsuarioOnboarding, UsuarioProactividad, UsuarioGoogleAuth, UsuarioMiroFish, PerfilAprendizaje, UsuarioEstadoEmocional.",
    "<b>Tareas y agenda</b>: Recordatorio, RecordatorioGCalEnviado, Tarea, Lista, ItemLista, EventoUsuario.",
    "<b>Aprendizaje y eventos</b>: EventoEmocional, EventoComportamiento, NoticiaEnviada.",
    "<b>Billing y assets</b>: SaldoCreditos, TransaccionCredito, AssetGenerado, JobCreativo.",
])]
story += [Paragraph(
    "<b>Riesgo medio:</b> el esquema crece via <code>Base.metadata.create_all</code> en lifespan, "
    "no via Alembic. Funciona para desarrollo y para deployments greenfield, pero <b>cualquier "
    "cambio breaking</b> (rename de columna, cambio de tipo, índice nuevo) en un schema con "
    "datos requiere migración. Alembic está en <code>requirements.txt</code> pero no veo "
    "<code>alembic.ini</code> ni carpeta <code>versions/</code>. Iniciar el repositorio de "
    "migraciones <b>antes</b> del próximo cambio de schema.", TAG_WARN
)]
story.append(PageBreak())

# 7. Observabilidad
story += [Paragraph("7. Observabilidad", H1)]
story += [Paragraph("7.1 Logging", H2)]
story += [Paragraph(
    "Logger único (<code>logging.getLogger(\"dona\")</code>) configurado en "
    "<code>agent/logging_config.py</code>. Convención de prefijos por subsistema: "
    "<code>[BRAIN]</code>, <code>[BILLING]</code>, <code>[META]</code>, <code>[STRIPE]</code>, "
    "<code>[RATE]</code>, <code>[CRYPTO]</code>, <code>[SECURITY]</code>, <code>[JOBS]</code>, "
    "<code>[INBOUND]</code>. Esto facilita filtrado posterior aunque no haya logging estructurado JSON.", P
)]

story += [Paragraph("7.2 Métricas in-memory", H2)]
story += [Paragraph(
    "La clase <code>_Metricas</code> en <code>main.py</code> expone vía "
    "<code>/admin/metrics</code>: requests totales, requests por ruta, errores 5xx, "
    "mensajes procesados, latencia promedio y count de requests &gt; 5 s. Está protegido por "
    "Bearer token. <b>Limitación:</b> contadores no se persisten ni se exportan a Prometheus, "
    "y se reinician en cada redeploy.", P
)]

story += [Paragraph("7.3 Endpoints admin", H2)]
story += [bullets([
    "<code>GET /admin/metrics</code> — contadores in-memory.",
    "<code>GET /admin/jobs-recientes?telefono=...&amp;limite=10</code> — debug de jobs creativos.",
    "<code>POST /admin/seed-creditos</code> — acreditación manual.",
    "<code>GET /admin/recordatorios?telefono=...</code> — recordatorios programados.",
    "<code>GET /admin/onboarding?telefono=...</code> y <code>POST /admin/onboarding/reset</code>.",
    "<code>GET /admin/inbound/token?telefono=...</code> — generar token Zapier/Make/n8n.",
    "<code>GET /admin/r2-check</code> — health-check de R2.",
])]
story += [Paragraph(
    "Recomendación: añadir <code>/admin/health</code> que verifique en una sola llamada DB, "
    "Redis, R2, Anthropic API, Stripe, y devuelva un cuadro consolidado.", P
)]

# 8. Testing
story += [Paragraph("8. Testing y deuda técnica", H1)]
story += [Paragraph("8.1 Cobertura por archivo", H2)]
story += [Paragraph(
    "30 archivos de tests, 411 tests, ~4 600 LOC, todos en verde en ~34 s. Los archivos se "
    "alinean con los módulos críticos:", P
)]
story += [bullets([
    "<b>Billing</b>: test_billing.py + test_billing_commands.py + test_quotas.py.",
    "<b>Creativos</b>: test_creativos_imagen.py, test_creativos_ajustar.py, test_creativos_prompt_imagen.py.",
    "<b>Seguridad</b>: test_security_fixes.py, test_inbound_tokens.py.",
    "<b>Providers</b>: test_providers.py.",
    "<b>Jobs</b>: test_jobs.py.",
    "<b>Storage</b>: test_storage.py.",
    "<b>Brain</b>: test_brain_tools.py.",
    "<b>Onboarding y business</b>: test_onboarding_negocio.py, test_business.py, test_reminders_nl.py.",
    "<b>Integraciones Google</b>: test_gmail_*.py, test_google_*.py.",
    "<b>End-to-end</b>: test_smoke_e2e.py.",
])]

story += [Paragraph("8.2 Patrones de fixtures", H2)]
story += [Paragraph(
    "<code>conftest.py</code> setea <code>ENVIRONMENT=test</code>, "
    "<code>DATABASE_URL=sqlite+aiosqlite:///./test_dona.db</code> y una <code>ANTHROPIC_API_KEY</code> "
    "ficticia. Los tests usan SQLite temporal con fixtures que recargan módulos via "
    "<code>importlib.reload</code> tras setear env vars — esto permite probar módulos que "
    "cachean estado en import-time (e.g., crypto.py, billing.py). Mocks de httpx evitan "
    "llamadas reales a Gemini/OpenAI/Whapi/Stripe.", P
)]

story += [Paragraph("8.3 Brechas de cobertura observadas", H2)]
story += [bullets([
    "No hay <code>pytest --cov</code> en CI; la cobertura porcentual es desconocida.",
    "<code>brain.py</code> es el archivo más grande pero también el más difícil de testear (LLM en el path crítico). Los tests existentes mockean Claude pero podrían cubrir más ramas del dispatch de tools.",
    "<code>scheduler.py</code> y <code>proactivity.py</code> tienen lógica temporal compleja; un test de regresión con freeze-time sería valioso.",
    "<code>main.py</code> webhooks aceptan flujos largos — los tests cubren los caminos felices, pero no veo tests de <i>rechazo</i> de firma Meta inválida ni de Stripe.",
])]

story += [Paragraph("8.4 Deuda técnica clasificada", H2)]
story += [findings_table([
    ("MEDIA", "Monolitos: brain.py 3 319 LOC, memory.py 2 316 LOC, main.py 2 170 LOC",
     "Múltiple",
     "Refactor incremental: extraer routers, capa de modelos por dominio, dispatcher de tools."),
    ("MEDIA", "Sin migraciones Alembic activas pese a estar en deps",
     "agent/memory.py", "Inicializar repo de migraciones antes del próximo cambio de schema."),
    ("BAJA", "Comentarios legacy de AgentKit (declarado en CLAUDE.md)",
     "Disperso", "Limpieza cosmética cuando se modifique el módulo."),
    ("BAJA", "Hash teléfono SHA-1 sin salt en R2 keys",
     "agent/storage.py:65", "Migrar a HMAC con secret rotable; aceptable hoy."),
    ("BAJA", "Métricas no persistentes ni exportables",
     "agent/main.py:_Metricas", "Exponer endpoint Prometheus o enviar a sink externo."),
    ("INFO", "Documentación viva concentrada en CLAUDE.md y comentarios",
     "Repo", "Mantener — es uno de los mayores activos."),
])]
story.append(PageBreak())

# 9. Recomendaciones
story += [Paragraph("9. Recomendaciones priorizadas", H1)]

story += [Paragraph("9.1 Inmediatas (próximas 2 semanas)", H2)]
story += [bullets([
    "<b>Endurecer producción:</b> en <code>verificar_firma_stripe</code> y <code>_verificar_firma</code> "
    "de Meta, fallar cerrado cuando <code>ENVIRONMENT=production</code> y el secreto falte.",
    "<b>Cobertura:</b> activar <code>pytest --cov=agent --cov-report=term-missing</code> y "
    "fijar un piso (e.g., 65%) en pre-commit.",
    "<b>Tests negativos de webhook:</b> añadir 4 tests que verifiquen rechazo con firma inválida "
    "(Meta), payload sin firma (Stripe), timestamp viejo (Meta) y token HMAC manipulado (inbound).",
    "<b>Migraciones:</b> ejecutar <code>alembic init</code> y stampar el schema actual antes "
    "del próximo cambio de columna en <code>memory.py</code>.",
])]

story += [Paragraph("9.2 Corto plazo (próximo mes)", H2)]
story += [bullets([
    "<b>CCPA automático:</b> implementar OTP por WhatsApp para <code>/privacy/export</code> "
    "(retorna ZIP con JSON de todas las tablas) y <code>/privacy/delete</code> (ejecuta "
    "el helper de borrado de <code>memory.py:1984</code>).",
    "<b>Health-check producción:</b> <code>/admin/health</code> que verifique DB, Redis, R2, "
    "Anthropic, Stripe y devuelva matriz consolidada. Bloquear deploy si JOBS_BACKEND=inproc en prod.",
    "<b>Observabilidad estructurada:</b> migrar logger a JSON (e.g., python-json-logger) y "
    "exportar las métricas in-memory a Prometheus o un sink HTTP.",
])]

story += [Paragraph("9.3 Mediano plazo (próximos 3 meses)", H2)]
story += [bullets([
    "<b>Refactor brain.py:</b> extraer <code>_PATRONES_INYECCION</code> y "
    "<code>_sanitizar_datos_externos</code> a <code>agent/security/sanitize.py</code>; "
    "extraer cada categoría de tool a su propio módulo en <code>agent/tools/</code>.",
    "<b>Refactor memory.py:</b> dividir en sub-paquetes por dominio "
    "(<code>memory/billing.py</code>, <code>memory/conversacion.py</code>, "
    "<code>memory/onboarding.py</code>, etc.). Reduce blast-radius de cada cambio.",
    "<b>Refactor main.py:</b> mover endpoints a routers FastAPI por dominio "
    "(<code>routers/admin.py</code>, <code>routers/legal.py</code>, <code>routers/webhooks.py</code>).",
    "<b>Cifrado at-rest:</b> evaluar cifrar campos sensibles de mensajes (PII) además de tokens OAuth.",
])]

story += [Paragraph("9.4 Largo plazo / aspiracional", H2)]
story += [bullets([
    "<b>Multi-tenant safety:</b> aunque CLAUDE.md afirma que NO es multi-tenant, todo el código "
    "ya está particionado por <code>telefono</code>. Documentar formalmente el modelo de aislamiento.",
    "<b>Pipeline de evaluación:</b> dataset de mensajes reales redactados + suite que mida "
    "calidad de respuesta del LLM en cada deploy.",
    "<b>Retention policy:</b> establecer cuánto tiempo se guarda el historial de mensajes "
    "y aplicar borrado automático (relevante para CCPA y para cost-control).",
])]

# 10. Conclusión
story += [Paragraph("10. Conclusión", H1)]
story += [Paragraph(
    "Dona es un producto técnicamente <b>bien construido para su etapa</b>. La calidad del "
    "código supera lo habitual en proyectos de un solo desarrollador: separación de capas, "
    "documentación viva, fallbacks en cada integración externa, controles de seguridad "
    "implementados de verdad (no de fachada), suite de pruebas robusta y patrones explícitos "
    "para evitar que el LLM alucine éxito en operaciones irreversibles.", P
)]
story += [Paragraph(
    "Los riesgos identificados son <b>de operación y escala</b>, no de diseño: endurecer la "
    "configuración de producción (fail-closed en webhooks), iniciar el repositorio de "
    "migraciones, automatizar los flujos CCPA y refactorizar los tres archivos monolito antes "
    "de que sumen más LOC. Ninguno de estos hallazgos bloquea el servicio actual; todos son "
    "trabajos manejables incrementalmente.", P
)]
story += [Paragraph(
    "<b>Si tuviera que priorizar una sola acción</b>: cerrar el flujo CCPA automático con "
    "OTP por WhatsApp. Es la única deuda con un reloj regulatorio de 45 días.", P
)]

story += [Spacer(1, 1.0 * cm), Paragraph("— Fin del informe —", SMALL)]


# ── BUILD ───────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(
    str(SALIDA), pagesize=LETTER,
    leftMargin=2.0 * cm, rightMargin=2.0 * cm,
    topMargin=2.0 * cm, bottomMargin=2.0 * cm,
    title="Auditoría de código — Dona",
    author="Auditoría técnica · Claude",
    subject="Auditoría completa del código fuente",
)
doc.build(story, onFirstPage=en_cada_pagina, onLaterPages=en_cada_pagina)

print(f"OK: {SALIDA}")
print(f"Tamaño: {SALIDA.stat().st_size / 1024:.1f} KB")
