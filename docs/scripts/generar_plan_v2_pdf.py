"""
Genera Plan_Dona_Refinado_v2_2026-04-29.pdf con el plan refinado v2.

Solo se ejecuta una vez para producir el PDF descargable.
No toca ningún archivo del proyecto. No envía datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether,
)

OUTPUT = r"C:\Users\celes\Dona-agent\Plan_Dona_Refinado_v2_2026-04-29.pdf"

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="TitleBig", parent=styles["Title"], fontSize=22, leading=26,
    spaceAfter=8, textColor=colors.HexColor("#111111"),
))
styles.add(ParagraphStyle(
    name="MetaTop", parent=styles["Normal"], fontSize=9, leading=12,
    textColor=colors.HexColor("#555555"), spaceAfter=18,
))
styles.add(ParagraphStyle(
    name="H1", parent=styles["Heading1"], fontSize=16, leading=20,
    spaceBefore=18, spaceAfter=8, textColor=colors.HexColor("#111111"),
))
styles.add(ParagraphStyle(
    name="H2", parent=styles["Heading2"], fontSize=13, leading=17,
    spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1f2937"),
))
styles.add(ParagraphStyle(
    name="H3", parent=styles["Heading3"], fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#374151"),
))
styles.add(ParagraphStyle(
    name="Body", parent=styles["BodyText"], fontSize=9.5, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=6, textColor=colors.HexColor("#222222"),
))
styles.add(ParagraphStyle(
    name="BodyTight", parent=styles["BodyText"], fontSize=9, leading=12,
    alignment=TA_LEFT, spaceAfter=2, textColor=colors.HexColor("#222222"),
))
styles.add(ParagraphStyle(
    name="Caption", parent=styles["Body"], fontSize=8.5, leading=11,
    textColor=colors.HexColor("#6b7280"), spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="CodeBox", parent=styles["Code"], fontSize=8, leading=10,
    textColor=colors.HexColor("#111111"),
    backColor=colors.HexColor("#f5f5f5"),
    borderPadding=6, borderColor=colors.HexColor("#e5e7eb"), borderWidth=0.4,
    leftIndent=4, rightIndent=4, spaceBefore=6, spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="BulletDona", parent=styles["Body"], leftIndent=14, bulletIndent=2,
    spaceAfter=2,
))


def H1(t): return Paragraph(t, styles["H1"])
def H2(t): return Paragraph(t, styles["H2"])
def H3(t): return Paragraph(t, styles["H3"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])


def bullets(items):
    return [Paragraph("&bull; " + it, styles["BulletDona"]) for it in items]


def small_table(rows, col_widths, header=True, font_size=8.5):
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", font_size),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#9ca3af")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", font_size),
    ]
    t.setStyle(TableStyle(style))
    return t


def para_rows(rows):
    return [[Paragraph(c, styles["BodyTight"]) for c in r] for r in rows]


def task_block(titulo, objetivo, archivos, riesgo, tests, criterio, conf, capas=""):
    rows = [
        ["Objetivo", objetivo],
        ["Capas tocadas", capas] if capas else None,
        ["Archivos probables", archivos],
        ["Riesgo", riesgo],
        ["Tests requeridos", tests],
        ["Criterio de aceptación", criterio],
        ["Requiere confirmación", conf],
    ]
    rows = [r for r in rows if r is not None]
    rows_para = [[Paragraph("<b>" + r[0] + "</b>", styles["BodyTight"]),
                  Paragraph(r[1], styles["BodyTight"])] for r in rows]
    tbl = small_table(rows_para, col_widths=[3.8*cm, 13.2*cm], header=False)
    return KeepTogether([
        Paragraph("<b>" + titulo + "</b>", styles["H3"]),
        tbl,
        Spacer(1, 6),
    ])


# ── Contenido ──────────────────────────────────────────────────────────────

def build_story():
    s = []

    # Portada
    s.append(Paragraph("Dona — Plan Refinado v2", styles["TitleBig"]))
    s.append(Paragraph(
        "Fecha: 2026-04-29 &nbsp;·&nbsp; HEAD: 5b7d42d &nbsp;·&nbsp; "
        "Modo: planificación, no implementación &nbsp;·&nbsp; Estado: solo lectura.",
        styles["MetaTop"],
    ))

    # ─── A. Resumen ejecutivo ────────────────────────────────────────────
    s.append(H1("A. Resumen ejecutivo v2"))
    s.append(P(
        "Dona es un <b>acelerador / orquestador autónomo premium para negocios</b> que opera por WhatsApp + dashboard web. "
        "No es chatbot ni asistente personal. Internamente lo conceptualizamos como una <i>AI workforce / orchestration layer</i>; "
        "externamente nunca usamos la palabra “AGI”."
    ))
    s.append(P("v2 corrige tres riesgos de v1:"))
    s.extend(bullets([
        "<b>No habrá refactor big-bang de identidad.</b> La migración telefono → workspace_id se hace progresivamente con resolvers de compatibilidad y por módulo, sin romper WhatsApp en producción.",
        "<b>Calidad pareja.</b> Todo lo que ya funciona se eleva al mismo estándar premium que las features nuevas. No coexistirán “MVP viejo” y “feature nueva pulida”.",
        "<b>Checklist transversal de 18 capas.</b> Cada PR — viejo o nuevo — debe pasar por las 18 capas (sección C) antes de mergear; eso evita que Dona vuelva a parecer chatbot.",
    ]))
    s.append(P(
        "Decisiones tentativas confirmadas en v2: <b>Workspace</b> como raíz, <b>Resend</b> como SMTP inicial, suscripción mensual con créditos incluidos + top-ups, "
        "backend Python como única fuente Stripe, Customer Portal habilitado, audit log anonimizado tras delete, TCPA con responsabilidad primaria del negocio "
        "(Dona como proveedor con guardrails), Google scopes con consentimiento progresivo, copy externo “acelerador autónomo premium para negocios”."
    ))
    s.append(P(
        "Pendientes bloqueantes (sección L): matriz exacta plan↔créditos↔tools, formato del reporte de diagnóstico, sandbox de Meta/Google Ads, "
        "decisión sobre enhanced/ (inventario primero), copy ES/EN finales."
    ))

    # ─── B. Arquitectura objetivo v2 ─────────────────────────────────────
    s.append(H1("B. Arquitectura objetivo v2"))
    s.append(P(
        "Mismas capas que v1 — identity / workspace, subscription + credits, owner Dona, public sub-agent, orchestrator, approval layer, "
        "jobs/workers, audit log, dashboard — con tres adiciones explícitas:"
    ))
    s.extend(bullets([
        "<b>Tool Intelligence Layer</b> (sección H). Sistema de evaluación, integración y rotación de herramientas externas. No es código vivo; es proceso + registro + experimentos mínimos.",
        "<b>Channel Provisioning Layer</b> (sección I). Cada Workspace puede traer su propio número WhatsApp (Whapi/Meta) y vincularlo al sub-agente público. Validación de propiedad obligatoria.",
        "<b>Quality Gates</b> transversales: cada feature pasa por las 18 capas como checklist antes de merge.",
    ]))

    diagrama = (
        "Identity/Workspace ── Subscription+Credits ── Tool Intelligence\n"
        "        |                    |                        |\n"
        "        v                    v                        v\n"
        "   Owner Dona  ──────  Orchestrator  ────── Public Sub-Agent (N canales)\n"
        "        |                    |                        |\n"
        "        +────── Approval Layer (preparar_/confirmar_) ─+\n"
        "                            |\n"
        "                            v\n"
        "              Jobs/Workers ──── Audit Log ──── Dashboard\n"
    )
    s.append(CODE(diagrama))

    # ─── C. 18 capas de refinación ───────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("C. Las 18 capas de refinación"))
    s.append(P(
        "Checklist transversal. Cada feature, fix o refactor pasa por las 18 antes de cerrar PR. "
        "Cada capa tiene <b>dueño</b>, <b>estado actual</b> y <b>target premium</b>."
    ))

    capas_rows = [
        ["#", "Capa", "Dueño actual", "Estado hoy", "Target premium"],
        ["1", "Posicionamiento / visión",
         "agent/brain.py system prompt; landing/app/page.tsx; agent/legal_pages.py",
         "“Asistente personal en WhatsApp”",
         "“Acelerador autónomo premium para negocios”. Nunca “AGI” público."],
        ["2", "ICP / industrias objetivo", "Sin documento",
         "Implícito (pequeños negocios USA)",
         "ICP por sector (servicios profesionales, e-commerce, restaurantes, real estate, salud cash-pay) con docs de fit por vertical."],
        ["3", "Modelo de cuenta / Workspace", "telefono como PK universal",
         "Identidad cruda por número",
         "Workspace raíz, identidades vinculadas (email + telefono_owner + stripe + oauth)."],
        ["4", "Modelo económico", "agent/billing.py one-time + landing $20/$40",
         "Dividido", "Suscripción + créditos incluidos + top-ups, gates por plan, Customer Portal."],
        ["5", "Sistema de permisos / Approval", "Patrón preparar_/confirmar_ ya existe",
         "Bien para tools nuevas; no aplicado a flows existentes",
         "Approval Gate explícito + audit log + TTL + canal de aprobación."],
        ["6", "Owner Dona", "brain.py", "Tono “asistente útil”",
         "Persona “líder de operaciones”: directa, ejecutiva, sin emojis gratuitos."],
        ["7", "Public Sub-Agent", "No existe", "n/a",
         "Aislado, multi-canal, multi-Workspace, números del negocio."],
        ["8", "Orquestador autónomo", "No existe formalmente",
         "Flows manuales", "agent/orchestrator/ con state-machine de iniciativas."],
        ["9", "Tool Intelligence Layer", "requirements.txt + env vars",
         "Ad-hoc", "Proceso documentado + matriz comparativa + experimentos mínimos."],
        ["10", "Memoria / contexto", "agent/memory.py; memory_summary.py; vector_memory.py",
         "Mezcla short/long term, sin TTL claro",
         "Capas explícitas: efímero / corto / medio / largo. Cifrado A.3."],
        ["11", "Dashboard premium", "landing/app/dashboard/ solo cancelar",
         "Shell vacía", "Iniciativas, autorizaciones, conexiones, sub-agentes, plan, audit log, privacidad."],
        ["12", "WhatsApp UX", "agent/main.py + onboarding.py + comandos preLLM",
         "Funcional con tono “asistente”",
         "Onboarding premium, mensajes proactivos con valor, previews ricos, consistencia de tono."],
        ["13", "Creative Engine", "agent/creativos/ (imagen, video, voz, PDF, bg_remove)",
         "Bueno; cubre patrón preparar_/confirmar_",
         "Tool Intelligence aplicado, rotación por costo/calidad, fallbacks, gallery en dashboard."],
        ["14", "Business Operations Layer", "agent/business/ (CRM, finanzas, pedidos, cotizaciones, reportes)",
         "Sólido pero fragmentado",
         "Modelado por Workspace, vistas en dashboard, integración con Orquestador."],
        ["15", "Billing / créditos", "agent/billing.py; billing_commands.py",
         "Créditos OK; suscripciones desconectadas",
         "Plan + créditos incluidos + top-ups + Customer Portal + facturas + caps por sub-agente."],
        ["16", "Seguridad / compliance", "Parches dispersos",
         "Hallazgos P0 abiertos",
         "Phase 0 cierra; cifrado A.3; audit log; CCPA real; TCPA por canal."],
        ["17", "Observabilidad / calidad", "logging_config.py + /admin/metrics in-memory",
         "Logs no estructurados, sin Sentry, 1 worker",
         "Logs JSON, Sentry, métricas Render, alertas, CI con pytest+lint+typecheck."],
        ["18", "Go-to-market / marca", "landing/app/page.tsx + emails Stripe",
         "Landing actual + email genérico",
         "Marca consistente Linear/Stripe-grade, narrativa premium, casos de uso por vertical, social proof real."],
    ]
    s.append(small_table(para_rows(capas_rows),
                         col_widths=[0.6*cm, 3.4*cm, 4.2*cm, 4.0*cm, 5.0*cm]))
    s.append(C(
        "Regla: cada PR debe declarar en su descripción qué capas toca y cuáles deja en su estado actual."
    ))

    # ─── D. Principio: elevar lo existente ───────────────────────────────
    s.append(PageBreak())
    s.append(H1("D. Principio: elevar también lo existente"))
    s.append(P(
        "Todo lo que ya funciona en Dona se eleva al mismo estándar premium que las features nuevas. "
        "No coexisten “MVP” y “premium” en el mismo producto."
    ))

    elev_rows = [
        ["Bloque", "Archivos representativos", "Acción de elevación"],
        ["WhatsApp UX", "agent/main.py; agent/providers/*",
         "Tono uniforme; previews enriquecidos; reducir verbosidad de errores; mensajes proactivos con valor concreto."],
        ["Tareas / recordatorios", "agent/reminders_nl.py; agent/scheduler.py",
         "UX de confirmación premium; recurrencias visibles en dashboard; auditables."],
        ["Memoria", "agent/memory.py; memory_summary.py; vector_memory.py",
         "Capas explícitas + cifrado A.3 + visibilidad para owner (“¿qué sabes de mí?”)."],
        ["Onboarding owner", "agent/onboarding.py; agent/business/onboarding_negocio.py",
         "Reescritura del tono (líder de operaciones); reducción de fricción; checkpoints en dashboard."],
        ["CRM / business", "agent/business/*",
         "Vistas dashboard; integración con orquestador; reporting consistente."],
        ["Creativos", "agent/creativos/*",
         "Tool Intelligence; gallery; presets por marca; quality gate antes de mostrar al owner."],
        ["Google / Gmail / Calendar / Drive",
         "agent/gmail.py; agent/google_calendar.py; etc.",
         "Consentimiento progresivo; UI de gestión en dashboard; refresh-token rotation."],
        ["Billing / créditos", "agent/billing.py; billing_commands.py",
         "Suscripciones + Customer Portal; transparencia total."],
        ["Prompts", "agent/brain.py",
         "Reescritura completa para “líder de operaciones”; system prompt versionado; snapshot tests."],
        ["Tono de respuesta", "Transversal",
         "Guía de estilo en docs/; lint de strings prohibidas."],
        ["Dashboard", "landing/app/dashboard/", "Construido completo (no solo cancelar)."],
        ["Logs", "agent/logging_config.py", "JSON estructurado + Sentry + redaction de PII."],
        ["Tests", "tests/*", "CI verde obligatoria; cobertura mínima por módulo crítico."],
        ["Seguridad", "Transversal", "Phase 0 + cifrado + rotación de keys."],
        ["Documentación", "README.md; CLAUDE.md", "Docs internos por capa + runbooks."],
    ]
    s.append(small_table(para_rows(elev_rows),
                         col_widths=[3.8*cm, 5.4*cm, 8.0*cm]))

    # ─── E. Benchmarks ───────────────────────────────────────────────────
    s.append(H1("E. Benchmark por compañías / startups"))
    s.append(P("Referencias por capa. <b>Objetivo: aspirar al estándar; no copiar producto.</b>"))
    bench_rows = [
        ["Compañía", "Capas", "Lo que tomamos como vara"],
        ["OpenAI / ChatGPT", "6, 10, 12", "Memoria útil, conversación natural, UX de modelo."],
        ["Anthropic / Claude", "6, 16", "Seguridad, razonamiento, instrucciones explícitas, refusal patterns."],
        ["Perplexity", "8, 10", "Investigación, síntesis, citation-first."],
        ["Linear", "11, 18", "Claridad operativa, dark UI premium, keyboard-first, velocidad percibida."],
        ["Stripe", "4, 11, 15, 18", "Billing, dashboards, documentación de clase mundial, confianza."],
        ["Framer", "18", "Landing premium, motion, percepción de calidad."],
        ["Canva", "13, 11", "Creación visual accesible, plantillas que no se ven a plantilla."],
        ["Kittl", "13", "Assets creativos para negocios, calidad sin curva."],
        ["Runway", "13", "Video IA, control granular, timeline."],
        ["ElevenLabs", "13, 4", "Voz; modelo de créditos; pricing transparente."],
        ["Intercom / Sierra", "7, 12", "Agentes customer-facing con guardrails y handoff."],
        ["HubSpot", "14, 18", "CRM completo, marketing, ventas, datos accionables."],
        ["Shopify", "14, 4", "Operación de negocio end-to-end, app marketplace."],
        ["Zapier / Make", "8, 9", "Automatización e integraciones modulares."],
        ["Replit Agent", "8, 5", "Agente que ejecuta trabajo real con autorización humana."],
    ]
    s.append(small_table(para_rows(bench_rows),
                         col_widths=[4.0*cm, 2.4*cm, 10.8*cm]))
    s.append(C(
        "Aplicación: cada feature define en su PR qué benchmark le aplica y cómo se compara (en una línea). "
        "Si no se compara con nada, probablemente está fuera de scope."
    ))

    # ─── F. Backlog refinado ────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("F. Backlog refinado por fases"))
    s.append(C("Convención: <b>Conf</b> = requiere confirmación. Cada tarea declara las capas (1–18) que toca."))

    s.append(H2("Phase 0 — Security blockers"))
    s.append(C("No se construye feature hasta cerrar."))
    p0 = [
        ["ID", "Título", "Capas", "Conf"],
        ["T0.1", "Sustituir password fake por magic-link Resend", "1, 3, 11, 16, 18", "Sí"],
        ["T0.2", "Stripe webhook firma obligatoria en prod", "4, 15, 16", "No"],
        ["T0.3", "Meta webhook firma obligatoria en prod", "12, 16", "No"],
        ["T0.4", "INBOUND_WEBHOOK_SECRET sin fallback en prod", "16", "No"],
        ["T0.5", "Eliminar número personal hardcodeado en /voice/reenviar", "16", "No"],
        ["T0.6", "Disclaimer legal del landing alineado con realidad", "1, 16, 18", "Sí (wording)"],
        ["T0.7", "Inventario legacy (enhanced/, start.sh, mounts compose, migration.py)", "17", "Sí"],
        ["T0.8", "Quitar TwiML hardcoded; centralizar contactos del owner en env", "16", "No"],
        ["T0.9", "Sentry + log sanitization (redact PII) — base mínima", "17", "Sí (proveedor)"],
    ]
    s.append(small_table(para_rows(p0), col_widths=[1.4*cm, 9.0*cm, 4.0*cm, 2.6*cm]))

    s.append(H2("Phase 1 — Foundations (identidad, billing, audit, cifrado)"))
    s.append(C("Todas las tareas siguen migración progresiva (sección G)."))
    p1 = [
        ["ID", "Título", "Capas", "Conf"],
        ["T1.1", "Modelo Workspace + identidades vinculadas (sin tocar lookups existentes)", "3", "Sí (nombre)"],
        ["T1.2", "Resolver telefono → workspace_id (compat layer)", "3, 12", "No"],
        ["T1.3", "Magic-link Resend + OTP WhatsApp para vincular identidades", "3, 16", "Depende T0.1"],
        ["T1.4", "Migrar billing a fuente única backend Python", "4, 15", "Sí (Stripe Dashboard)"],
        ["T1.5", "Plan + créditos incluidos + top-ups + Customer Portal", "4, 15", "Sí (matriz)"],
        ["T1.6", "Cifrado campo-a-campo (A.3) — fase 1: tokens, cookies, mensajes owner", "10, 16", "Sí (matriz)"],
        ["T1.7", "Audit log append-only", "5, 16", "No"],
        ["T1.8", "Reescritura del system prompt (líder de operaciones) + snapshot tests", "1, 6", "Sí (copy)"],
    ]
    s.append(small_table(para_rows(p1), col_widths=[1.4*cm, 9.0*cm, 4.0*cm, 2.6*cm]))

    s.append(H2("Phase 2 — Premium product / Dashboard"))
    p2 = [
        ["ID", "Título", "Capas", "Conf"],
        ["T2.1", "Dashboard: shell premium (auth, navegación, branding Linear/Stripe-grade)", "11, 18", "No"],
        ["T2.2", "Dashboard: Plan + créditos + Customer Portal + facturas", "4, 11, 15", "No"],
        ["T2.3", "Dashboard: Conexiones OAuth con consentimiento progresivo", "11, 16", "No"],
        ["T2.4", "Dashboard: Iniciativas + Autorizaciones", "5, 8, 11", "No"],
        ["T2.5", "Dashboard: Privacidad (export real + delete real con OTP)", "11, 16", "Sí (retención)"],
        ["T2.6", "Reescritura copy landing (ES/EN)", "1, 18", "Sí"],
        ["T2.7", "Elevación tono UX en flows existentes (recordatorios, tareas, CRM, creativos)", "6, 12, 14", "Sí (guía estilo)"],
        ["T2.8", "Memoria por capas + UI “¿qué sabes de mí?”", "10, 11", "No"],
        ["T2.9", "Dashboard: Sub-agentes públicos (CRUD, métricas, caps)", "7, 11", "Sí (knowledge)"],
    ]
    s.append(small_table(para_rows(p2), col_widths=[1.4*cm, 9.0*cm, 4.0*cm, 2.6*cm]))

    s.append(H2("Phase 3 — Autonomous Orchestration + Public Sub-Agent"))
    p3 = [
        ["ID", "Título", "Capas", "Conf"],
        ["T3.1", "Módulo agent/orchestrator/ base", "8", "No"],
        ["T3.2", "Iniciativa: Diagnóstico de negocio", "8, 14", "Sí (formato)"],
        ["T3.3", "Iniciativa: Generación de assets de marca", "8, 13", "No"],
        ["T3.4", "Public Sub-Agent runtime (provisioning + isolation)", "7, 16", "Sí"],
        ["T3.5", "Iniciativa: Atención automatizada en sub-agente público", "7, 8", "Sí (escalation)"],
        ["T3.6", "Iniciativa: Campaña Meta Ads en sandbox", "8, 14", "Sí"],
        ["T3.7", "Tool Intelligence Layer: registro + matriz + primer experimento", "9, 13", "Sí"],
    ]
    s.append(small_table(para_rows(p3), col_widths=[1.4*cm, 9.0*cm, 4.0*cm, 2.6*cm]))

    s.append(H2("Phase 4 — Scale + Observability"))
    p4 = [
        ["ID", "Título", "Capas", "Conf"],
        ["T4.1", "Render: web + worker separados", "17", "Sí (costo)"],
        ["T4.2", "Multi-worker gunicorn (post-scheduler-extraction)", "17", "No"],
        ["T4.3", "Alembic real con autogenerate", "17", "Sí"],
        ["T4.4", "Observabilidad completa (logs JSON, Sentry, alertas, dashboards)", "17", "Sí"],
        ["T4.5", "CI GitHub Actions (pytest + lint + typecheck + landing build)", "17", "No"],
        ["T4.6", "Decisión + ejecución sobre legacy (basada en T0.7)", "17", "Sí (uno por uno)"],
        ["T4.7", "Benchmarks reales contra targets (Linear/Stripe/etc.) — UX review", "11, 18", "Sí"],
    ]
    s.append(small_table(para_rows(p4), col_widths=[1.4*cm, 9.0*cm, 4.0*cm, 2.6*cm]))

    s.append(H2("Phase 5 — GTM / Verticalización (post-producto)"))
    p5 = [
        ["ID", "Título", "Capas", "Conf"],
        ["T5.1", "ICP por vertical (servicios, e-commerce, restaurantes, real estate, salud cash-pay)", "2, 18", "Sí"],
        ["T5.2", "Casos de uso documentados por vertical", "2, 18", "Sí"],
        ["T5.3", "Onboarding por vertical (template inicial pre-cargado)", "2, 12, 14", "Sí"],
        ["T5.4", "Tool Intelligence rotation (revisión trimestral)", "9, 13", "No"],
    ]
    s.append(small_table(para_rows(p5), col_widths=[1.4*cm, 9.0*cm, 4.0*cm, 2.6*cm]))

    # ─── G. Migración progresiva ────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("G. Migración progresiva telefono → workspace_id"))
    s.append(P(
        "Reemplaza la línea de v1 “100% del código se sustituye”. <b>telefono</b> queda como <i>lookup compatibility key</i>; "
        "<b>workspace_id</b> es la nueva raíz. Ningún PR rompe queries existentes; cada PR introduce el resolver y migra un módulo."
    ))

    s.append(H2("G.1 — Crear estructura sin migrar nada"))
    s.extend(bullets([
        "Tablas nuevas: workspaces, workspace_identities, workspace_members.",
        "Resolver resolver_workspace(telefono | email | stripe_customer_id) → workspace_id con caché.",
        "<b>Cero cambios</b> en queries existentes. Tests existentes siguen pasando.",
        "<b>Backfill batch idempotente</b>: por cada telefono único en tablas vivas, crear Workspace si no existe, vincular identidad phone_owner. Job offline, no hot path.",
    ]))

    s.append(H2("G.2 — Capa de adaptadores"))
    s.extend(bullets([
        "Funciones helper en agent/identity/adapters.py: con_workspace(telefono) → (workspace_id, telefono); solo_telefono(workspace_id) → telefono_owner.",
        "Documentación clara: nuevos handlers usan con_workspace; los viejos siguen funcionando.",
    ]))

    s.append(H2("G.3 — Migración por módulo (orden de prioridad)"))
    s.append(P("Orden por riesgo + valor. Cada paso es un PR pequeño con migración Alembic puntual + tests."))
    s.extend(bullets([
        "<b>Billing</b> (agent/billing.py): añadir workspace_id a transacciones_credito, saldo_creditos (nullable, doble escritura). Tests por delta.",
        "<b>Audit log</b> (nuevo): nace ya con workspace_id. Sin migración.",
        "<b>Onboarding</b> (agent/onboarding.py): nuevos onboardings escriben workspace_id; existentes se backfillean.",
        "<b>Memoria</b> (agent/memory.py:Mensaje): añadir workspace_id indexado, doble escritura, lectura por cualquiera.",
        "<b>Recordatorios + Scheduler</b> (agent/scheduler.py): añadir workspace_id; scheduler resuelve por cualquiera.",
        "<b>CRM / business</b> (agent/business/*): mismo patrón.",
        "<b>Creativos / jobs</b> (agent/creativos/*, agent/jobs/*): pequeños, telefono solo para notificación.",
    ]))

    s.append(H2("G.4 — Cleanup (post-Phase 3)"))
    s.extend(bullets([
        "Tras validación en producción, marcar telefono como nullable en tablas migradas.",
        "En última fase (post-Phase 4), eliminar columnas telefono redundantes y dejar solo workspace_id.",
        "No se hace cleanup hasta que todos los módulos estén migrados.",
    ]))

    s.append(H2("G.5 — Reglas obligatorias"))
    s.extend(bullets([
        "Ningún PR fase G.x toca más de un módulo a la vez.",
        "Cada PR tiene rollback testeado (Alembic downgrade + flag USE_WORKSPACE_RESOLVER=false).",
        "Tests por módulo: existentes siguen pasando + nuevos prueban workspace_id.",
        "WhatsApp en producción no debe perder un mensaje durante la migración (E2E con doble identidad obligatorio).",
    ]))

    # ─── H. Tool Intelligence Layer ─────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("H. Tool Intelligence Layer"))
    s.append(H2("Propósito"))
    s.append(P(
        "Cada tool externa nueva (Higgsfield, Runway, Ideogram, ElevenLabs, Kittl, Canva, OpenAI, Claude, Perplexity, etc.) "
        "pasa por un proceso documentado antes de entrar al producto. Evita decisiones impulsivas y permite rotación racional cuando aparece "
        "un proveedor mejor o más barato."
    ))

    s.append(H2("Proceso (ficha por tool)"))
    s.append(P("Cada herramienta evaluada deja una ficha en docs/tools/&lt;slug&gt;.md (creación pendiente de autorización) con:"))
    proceso = [
        "Nombre y categoría (imagen, video, voz, LLM, research, automation, design).",
        "Qué hace — descripción breve.",
        "Qué problema resuelve en Dona.",
        "Módulo de aplicación (agent/creativos/, agent/orchestrator/, etc.) o “no aplica”.",
        "Reemplaza a — herramienta actual sustituida (si aplica).",
        "Complementa a — herramientas con las que coexiste.",
        "Costo aproximado (por unidad: imagen, segundo, 1k tokens, etc.).",
        "Calidad esperada — benchmark interno (escala 1–5 + ejemplos).",
        "Riesgos — TOS, dependencias, vendor lock-in, regional.",
        "Privacidad / compliance — qué datos viajan, retención, sub-procesamiento, BAA si aplica.",
        "Facilidad de integración (1–5).",
        "Prioridad (alta / media / baja / no integrar).",
        "Experimento mínimo — cuál PoC y con qué métricas se decide.",
        "Decisión — integrar / documentar / descartar (con fecha y autor).",
        "Revisión programada — fecha próxima evaluación (default: trimestral).",
    ]
    s.extend(bullets(proceso))

    s.append(H2("Matriz comparativa"))
    s.append(P(
        "docs/tools/matriz.md mantiene una tabla por categoría (imagen, video, voz, LLM) con todas las herramientas evaluadas y su decisión actual. "
        "Cuando hay rotación, se actualiza la matriz con un mini-changelog."
    ))

    s.append(H2("Reglas"))
    s.extend(bullets([
        "Ninguna herramienta entra a requirements.txt o env vars sin ficha aprobada.",
        "Cada ficha referencia las capas (1–18) que toca.",
        "Ficha rechazada también se conserva (decision log).",
        "Herramientas con costo unitario alto deben tener fallback documentado.",
    ]))

    s.append(H2("Tools ya en producción que necesitan ficha retroactiva"))
    s.append(P(
        "Anthropic Claude, OpenAI, Groq, Google Gemini Image, Replicate (video), HeyGen, ElevenLabs, Photoroom, Cloudflare R2, Stripe, Whapi, Meta Cloud API, "
        "Twilio, Zep, MiroFish. Son ~15 fichas; primer paquete documental."
    ))

    # ─── I. Public Sub-Agent ────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("I. Public Sub-Agent con números del negocio"))
    s.append(H2("Principio"))
    s.append(P(
        "El sub-agente público de cada Workspace puede operar desde <b>uno o varios números/canales que el negocio mismo provea</b>, vinculados al Workspace. "
        "No depende de un número compartido de Dona. Dona es la <b>plataforma</b>; el negocio trae el canal."
    ))

    s.append(H2("I.1 Channel Provisioning"))
    s.append(P("Tabla public_channels:"))
    s.append(CODE(
        "public_channels\n"
        "  id (PK)\n"
        "  workspace_id (FK)\n"
        "  provider              -- whapi | meta_cloud | twilio\n"
        "  phone_number          -- E.164\n"
        "  phone_number_id       -- ID interno del proveedor (Meta) o token (Whapi)\n"
        "  credenciales_cifradas -- Fernet random; tokens por canal\n"
        "  estado                -- pendiente_validacion | activo | suspendido | revocado\n"
        "  validacion_metodo     -- otp_sms | meta_ownership | whapi_qr\n"
        "  validado_en\n"
        "  desactivado_en\n"
        "  notas\n"
    ))

    s.append(H2("I.2 Validación de propiedad"))
    s.extend(bullets([
        "<b>Whapi</b>: subir token Whapi del negocio; Dona hace ping autenticado al endpoint y lee el phone_number activo, lo compara con el ingresado.",
        "<b>Meta Cloud</b>: el negocio agrega Dona como app a su WhatsApp Business Account vía OAuth de Meta, devolviendo phone_number_id. Validación por me/phone_numbers.",
        "<b>Twilio</b> (futuro): subir credentials + verificar SID.",
        "Sin validación, el canal queda en pendiente_validacion y no recibe ni envía nada.",
    ]))

    s.append(H2("I.3 Routing del webhook entrante"))
    s.append(CODE(
        "mensaje_entrante.numero_destino + provider\n"
        "  → public_channels (workspace_id, public_agent_id)\n"
        "  → si match: rutea al sub-agente público correspondiente\n"
        "  → si no match: rutea al canal owner (default privado)\n"
        "  → si pendiente_validacion: descartar con log\n"
    ))

    s.append(H2("I.4 Aislamiento estricto"))
    aisl_rows = [
        ["Recurso", "Owner Dona", "Public Sub-Agent"],
        ["Mensajes privados del owner", "Acceso total", "Sin acceso"],
        ["OAuth tokens (Gmail, Calendar, Drive)", "Acceso total", "Sin acceso"],
        ["Memoria privada del owner", "Acceso total", "Sin acceso"],
        ["business.cliente_publico, FAQ, productos, horarios", "Acceso total", "Acceso solo lectura"],
        ["Knowledge base del canal", "Configura", "Lee"],
        ["Capacidad de ejecutar confirmar_*", "Sí", "No — siempre escala"],
        ["Capacidad de envíos masivos", "No (sin opt-in)", "Bloqueado a nivel de tool"],
        ["Cap de créditos", "Cap general del workspace", "Cap propio (creditos_cap_mes)"],
    ]
    s.append(small_table(para_rows(aisl_rows), col_widths=[7.0*cm, 4.5*cm, 5.5*cm]))
    s.append(C(
        "Implementación: rol agente_publico con permisos restringidos a nivel de tool dispatcher en agent/brain.py. "
        "Cualquier tool no permitida lanza PermisoDenegado y escala al owner."
    ))

    s.append(H2("I.5 Persona, prompt y knowledge"))
    s.extend(bullets([
        "persona_prompt: text del system prompt del sub-agente. Editable desde dashboard.",
        "knowledge_ref: referencia a documentos del workspace (FAQ, productos, horarios, tono, idioma, restricciones).",
        "escalation_rules: cuándo escalar al owner (palabras clave, intent, monto, sentiment).",
    ]))

    s.append(H2("I.6 Cap de créditos por canal"))
    s.append(P(
        "Cada public_channel tiene creditos_cap_mes. Se descuenta del cap propio, no del cap general. Si se agota, el sub-agente solo responde con FAQ estática "
        "y deja mensaje “te contactamos en breve” (escalación al owner)."
    ))

    s.append(H2("I.7 Auditoría por canal"))
    s.extend(bullets([
        "actor_tipo = public_agent",
        "recurso_tipo = public_channel",
        "recurso_id = public_channel.id",
        "Conversación enmascarada (Fernet) + metadatos.",
        "Owner ve en dashboard: conversaciones por canal, leads capturados, escalaciones, créditos consumidos.",
    ]))

    s.append(H2("I.8 TCPA / STOP por canal"))
    s.append(P(
        "Tabla tcpa_optouts(workspace_id, public_channel_id, telefono_cliente, opted_out_at). STOP entrante a un canal aplica solo a ese canal. "
        "Cada negocio mantiene su propio registro."
    ))
    s.append(P(
        "<b>Responsabilidad legal</b>: el negocio dueño del Workspace es el responsable principal del cumplimiento TCPA hacia sus clientes finales. "
        "Dona actúa como <b>proveedor tecnológico con guardrails</b>: bloquea mass mailing sin opt-in, exige STOP/START, registra audit log, ofrece export. "
        "ToS/Privacy del Workspace lo refleja."
    ))

    s.append(H2("I.9 Multi-canal por Workspace"))
    s.append(P(
        "Un Workspace puede tener N canales (ej. número principal + soporte + ventas). Cada uno con persona y caps propios. Escalación va al owner único."
    ))

    # ─── J. Criterios para pasar a implementación ───────────────────────
    s.append(PageBreak())
    s.append(H1("J. Criterios para pasar de auditoría a implementación"))

    s.append(H2("J.1 Lo que debe estar definido antes de tocar código"))
    s.extend(bullets([
        "Nombre raíz del modelo de cuenta confirmado (<b>Workspace</b> tentativo).",
        "Proveedor SMTP confirmado (<b>Resend</b> tentativo).",
        "Stripe source of truth confirmado (<b>backend Python</b> tentativo).",
        "Customer Portal habilitado (<b>sí</b> tentativo).",
        "Wording del nuevo disclaimer legal aprobado.",
        "Inventario legacy entregado (T0.7).",
        "Acceso a paneles externos verificado (J.5).",
    ]))

    s.append(H2("J.2 Decisiones que bloquean Phase 0"))
    j2_rows = [
        ["Decisión", "Bloquea", "Estado"],
        ["Proveedor SMTP", "T0.1 (magic-link)", "tentativo: Resend"],
        ["Wording disclaimer", "T0.6", "pendiente"],
        ["Proveedor observabilidad", "T0.9 (Sentry/Datadog/Logtail)", "pendiente"],
        ["Autorización inventario legacy", "T0.7", "pendiente"],
        ["Confirmación de que STRIPE_WEBHOOK_SECRET, META_APP_SECRET, INBOUND_WEBHOOK_SECRET se pueden setear en Render sin downtime",
         "T0.2, T0.3, T0.4", "pendiente"],
    ]
    s.append(small_table(para_rows(j2_rows), col_widths=[5.5*cm, 5.0*cm, 6.5*cm]))

    s.append(H2("J.3 Tareas de bajo riesgo que pueden empezar primero"))
    s.append(P("Características: cambio local, test unitario suficiente, rollback trivial."))
    s.extend(bullets([
        "T0.5 (número personal a env var)",
        "T0.8 (TwiML hardcoded)",
        "T0.2, T0.3, T0.4 (firmas obligatorias en prod) — fail-fast en startup",
        "T0.7 (inventario legacy) — solo lectura + documento",
    ]))

    s.append(H2("J.4 Tareas que requieren diseño adicional antes de implementar"))
    s.extend(bullets([
        "T1.1 + T1.2 (Workspace + resolver) — requiere ADR de migración progresiva.",
        "T1.5 (plan + créditos) — requiere matriz exacta confirmada.",
        "T1.6 (cifrado A.3) — requiere matriz confirmada + plan de rotación de keys.",
        "T2.4 (iniciativas + autorizaciones UI) — requiere wireframes premium.",
        "T2.9 + T3.4 (Public Sub-Agent runtime) — requiere ADR de aislamiento + validación de canal.",
        "T3.2 (diagnóstico) — requiere formato del reporte.",
        "T3.6 (Meta Ads) — requiere acceso sandbox + cap policy.",
    ]))

    s.append(H2("J.5 Tareas que requieren acceso a paneles externos"))
    j5_rows = [
        ["Tarea", "Panel", "Acceso necesario"],
        ["T0.2", "Stripe Dashboard", "Webhook endpoint + secret rotation"],
        ["T0.3", "Meta Business", "App Secret visible al owner"],
        ["T0.6", "n/a", "Aprobación legal (puede ser self-review inicial)"],
        ["T0.9", "Sentry/Datadog", "Cuenta + DSN"],
        ["T1.3", "Resend", "API key + dominio verificado"],
        ["T1.4", "Stripe Dashboard", "Cambiar URL webhook + activar Customer Portal"],
        ["T1.5", "Stripe Dashboard", "Crear price IDs por plan"],
        ["T2.3", "Google Cloud Console", "OAuth client + scopes progresivos"],
        ["T2.3", "Meta Business", "App con permisos WhatsApp Business"],
        ["T3.4 / T3.5", "Whapi y/o Meta", "Validación de tokens del negocio"],
        ["T3.6", "Meta Ads sandbox", "Cuenta sandbox + token"],
        ["T4.1", "Render", "Crear servicio worker"],
        ["T4.4", "Sentry/Render", "Configurar alertas"],
        ["T4.5", "GitHub", "Permisos Actions + secrets"],
    ]
    s.append(small_table(para_rows(j5_rows), col_widths=[2.5*cm, 4.0*cm, 10.5*cm]))

    s.append(H2("J.6 Tareas que requieren confirmación explícita del owner"))
    s.append(P("Ver tabla de Conf en sección F."))

    # ─── K. Primer paquete recomendado ──────────────────────────────────
    s.append(PageBreak())
    s.append(H1("K. Primer paquete recomendado de implementación"))
    s.append(P(
        "Phase 0 dividido en PRs pequeños y secuenciales, cada uno mergeable independientemente. "
        "Total estimado: 7 PRs, ninguno toca > 5 archivos."
    ))

    pr_specs = [
        ("PR1 — Sentry + log sanitization base",
         "Que cualquier bug futuro de Phase 0 sea visible en Sentry; preparar el terreno.",
         "agent/logging_config.py; agent/main.py (init Sentry); requirements.txt (añadir sentry-sdk); .env.example.",
         "Bajo. Sentry sin DSN no rompe nada (no-op).",
         "tests/test_logging.py — verificar que mensajes con teléfono se redactan en INFO y se mantienen en DEBUG.",
         "En local sin DSN no hay overhead; en prod con DSN aparecen errores; PII redactada por default.",
         "Sí — confirmar Sentry como proveedor.",
         "17"),
        ("PR2 — Stripe webhook fail-fast en producción",
         "Bloquear path inseguro.",
         "agent/billing.py:366-384; agent/main.py:2112-2151; tests/test_billing.py.",
         "Medio. Requiere secret en Render antes del deploy.",
         "env=production sin secret → RuntimeError startup; con secret + firma inválida → 400; firma válida → 200.",
         "Zero path inseguro en prod; en dev sigue permisivo con warning.",
         "No (solo coordinar setting de env).",
         "4, 15, 16"),
        ("PR3 — Meta webhook fail-fast en producción",
         "Igual a PR2 para Meta.",
         "agent/providers/meta.py:131-150; tests/test_providers.py.",
         "Medio. Mismo patrón.",
         "Firma obligatoria en prod; permisivo en dev con warning.",
         "Zero path “permitir sin firma” en prod.",
         "No.",
         "12, 16"),
        ("PR4 — INBOUND_WEBHOOK_SECRET fail-fast en producción",
         "Cerrar el último fallback inseguro de webhook.",
         "agent/inbound_tokens.py:30-42; tests/test_inbound_tokens.py.",
         "Medio. Tokens previos generados con secret derivado quedan inválidos — coordinar rotación con notificación al owner antes del deploy.",
         "Prod sin secret → RuntimeError; secret válido → token verifica; rotación → tokens previos fallan.",
         "En prod siempre exige env var.",
         "Sí (rotación + comunicación al owner si hay tokens en uso).",
         "16"),
        ("PR5 — Centralizar contactos del owner en env var",
         "Eliminar PII personal del código (/voice/reenviar + TwiML).",
         "agent/main.py:2165-2172; .env.example.",
         "Bajo.",
         "Con env var → TwiML correcto; sin env var → 404.",
         "Ningún número personal aparece en grep del repo.",
         "No.",
         "16"),
        ("PR6 — Disclaimer legal del landing alineado con realidad",
         "Cerrar riesgo FTC §5.",
         "landing/app/page.tsx (i18n.ES y i18n.EN: whyDona.cards, faq.items, footer disclaimer).",
         "Bajo (texto). Marketing pierde un selling point hasta T1.6.",
         "Lint de strings prohibidas; visual review.",
         "Ninguna afirmación de seguridad sin sustento técnico.",
         "Sí — wording exacto.",
         "1, 16, 18"),
        ("PR7 — Inventario legacy",
         "Insumo para T4.6.",
         "docs/legacy-inventory.md (creación pendiente de autorización para escribir).",
         "Cero (solo lectura + documento).",
         "n/a.",
         "Cada item tiene: importadores, env vars, riesgo de remover, recomendación (mantener / mover / deprecar fase X).",
         "Sí — autorización para escribir el doc.",
         "17"),
    ]
    for titulo, obj, archivos, riesgo, tests, criterio, conf, capas in pr_specs:
        s.append(task_block(titulo, obj, archivos, riesgo, tests, criterio, conf, capas=capas))

    s.append(H2("Notas operativas del paquete"))
    s.extend(bullets([
        "Todos los PRs son rebaseable sobre main actual (5b7d42d).",
        "Orden recomendado: <b>K.1 → K.7 → K.5 → K.6 → K.2 → K.3 → K.4</b>. (Sentry primero para observar; inventario para informar; bajo riesgo para calentar; firmas al final con coordinación.)",
        "Cada PR tiene su propio test, su propio rollback, su propia descripción declarando capas tocadas.",
        "Ningún PR introduce dependencia que no exista ya o esté autorizada (Sentry es la única nueva).",
        "El paquete completo no toca arquitectura ni datos en producción; cierra solo riesgos de seguridad y prepara observabilidad.",
    ]))

    # ─── L. Decisiones bloqueantes restantes ────────────────────────────
    s.append(PageBreak())
    s.append(H1("L. Decisiones bloqueantes restantes"))

    s.append(H2("Decisiones tentativas confirmadas (ratificar o ajustar)"))
    s.extend(bullets([
        "Nombre raíz: <b>Workspace</b>.",
        "SMTP inicial: <b>Resend</b>.",
        "Stripe source of truth: <b>backend Python</b>.",
        "Customer Portal: <b>sí</b>.",
        "Modelo económico: <b>suscripción mensual con créditos incluidos + top-ups</b>.",
        "Audit log post-delete: <b>anonimizar</b> si justificado por seguridad/legal.",
        "TCPA: <b>negocio es responsable; Dona proveedor con guardrails</b>.",
        "Google scopes: <b>consentimiento progresivo</b>.",
        "Public copy: <b>acelerador / orquestador autónomo premium para negocios</b>; nunca AGI público.",
        "WhatsApp proxy: <b>backend directo inicialmente</b>; mantener proxy solo si aporta WAF/CDN/control real (post-Phase 4).",
    ]))

    s.append(H2("Decisiones aún pendientes"))
    s.extend(bullets([
        "<b>Proveedor de observabilidad</b>: Sentry vs Datadog vs Logtail. Recomendación: Sentry para errores + Render logs para métricas.",
        "<b>Wording exacto del disclaimer</b> del landing (T0.6 / PR6).",
        "<b>Matriz plan ↔ créditos ↔ tools</b>: precios, créditos incluidos por plan, qué desbloquea cada tier, cap de sub-agentes por plan, top-ups.",
        "<b>Matriz de cifrado A.3</b>: confirmar campos exactos por capa.",
        "<b>Política retención</b>: mensajes privados owner vs públicos sub-agente (mismos plazos? 90/180 días por canal?).",
        "<b>Knowledge base público</b>: pgvector interno vs externo (Zep/Pinecone).",
        "<b>Formato del reporte de diagnóstico</b> (T3.2).",
        "<b>Flujo de escalation</b> sub-agente público → owner (palabras clave, intent, monto).",
        "<b>Sandbox Meta Ads / Google Ads</b>: ¿tenemos cuentas listas?",
        "<b>Decisión sobre enhanced/, start.sh, mounts compose, migration.py</b>: tras inventario.",
        "<b>Copy ES/EN final</b> del landing reposicionado.",
        "<b>Guía de estilo</b> del tono “líder de operaciones” (T2.7) — un doc de 2-3 páginas.",
        "<b>ICP por vertical</b> (Phase 5) — qué verticales priorizamos primero.",
    ]))

    # ─── M. Riesgos si se implementa demasiado rápido ───────────────────
    s.append(H1("M. Riesgos si se implementa demasiado rápido"))
    riesgos_rows = [
        ["Riesgo", "Causa típica", "Mitigación"],
        ["Romper WhatsApp en producción",
         "Mega-refactor telefono → workspace_id en un solo PR",
         "Migración progresiva (sección G); E2E con doble identidad obligatorio."],
        ["Filtrar PII en logs", "Sentry sin redaction",
         "PR1 entrega redaction + Sentry juntos."],
        ["Doble webhook Stripe acreditando 2x",
         "Mover webhook sin coordinar Stripe Dashboard",
         "T1.4 explicita coordinación; landing devuelve 410 antes de mover Stripe."],
        ["Tokens OAuth perdidos al rotar ENCRYPTION_KEY",
         "Rotación sin esquema versionado",
         "T1.6 incluye versioning + descifrar acepta múltiples keys."],
        ["Sub-agente público filtra datos del owner",
         "Aislamiento mal implementado",
         "Tool dispatcher con rol estricto + tests específicos de cross-access."],
        ["Owner pierde acceso al login web",
         "T0.1 sin proveedor SMTP listo",
         "Resend confirmado + dominio verificado antes de mergear T0.1."],
        ["Plan upgrade/downgrade duplica créditos",
         "Sync Stripe sin idempotencia por periodo",
         "T1.5 con dedup por (workspace_id, periodo)."],
        ["Iniciativas de orquestador disparan gasto inesperado",
         "Confirmar_ sin cap",
         "Approval Layer obliga cap visible en preview."],
        ["Tool nueva entra sin ficha",
         "Decisión impulsiva",
         "Tool Intelligence Layer: requirement de ficha + decisión registrada."],
        ["Marketing falsea capacidades",
         "Reposicionamiento sin guardrails",
         "PR6 cierra disclaimer + lint de strings prohibidas."],
        ["Posicionamiento se diluye otra vez",
         "Falta de checklist transversal",
         "18 capas declaradas en cada PR."],
        ["Costos Render se duplican sin ROI",
         "T4.1 sin job real corriendo",
         "T4.1 después de tener al menos 1 iniciativa que use worker."],
        ["Sub-agente público envía spam masivo",
         "Falta cap + falta TCPA enforcement",
         "Cap de créditos + bloqueo de mass mailing a nivel de tool + TCPA por canal."],
    ]
    s.append(small_table(para_rows(riesgos_rows), col_widths=[5.5*cm, 5.5*cm, 6.0*cm]))

    s.append(Spacer(1, 16))
    s.append(H2("Próximo paso"))
    s.extend(bullets([
        "Confirmá las decisiones tentativas de la sección L (1–10) o ajustá las que quieras.",
        "Decidí proveedor de observabilidad y wording del disclaimer (bloquean K.1 y K.6).",
        "Autorizá la creación de docs/legacy-inventory.md y docs/tools/* (K.7 y Tool Intelligence).",
        "No habrá edits hasta autorización explícita por PR.",
    ]))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Plan Refinado v2",
        author="Plan generado a partir de la conversación con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch, "Dona — Plan Refinado v2 · 2026-04-29")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Página {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
