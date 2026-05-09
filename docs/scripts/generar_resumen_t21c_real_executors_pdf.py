"""
Genera Resumen_T21C_Real_Executors_2026-05-09.pdf · ejecutores reales
con guardrails para el Action Center (T2.1.C).
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T21C_Real_Executors_2026-05-09.pdf"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleBig", parent=styles["Title"], fontSize=20, leading=24,
    spaceAfter=8, textColor=colors.HexColor("#111111")))
styles.add(ParagraphStyle(name="MetaTop", parent=styles["Normal"], fontSize=9, leading=12,
    textColor=colors.HexColor("#555555"), spaceAfter=18))
styles.add(ParagraphStyle(name="Banner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#065f46"), backColor=colors.HexColor("#ecfdf5"),
    borderPadding=8, borderColor=colors.HexColor("#10b981"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14))
styles.add(ParagraphStyle(name="WarnBanner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#7c2d12"), backColor=colors.HexColor("#fff7ed"),
    borderPadding=8, borderColor=colors.HexColor("#f97316"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14))
styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"], fontSize=15, leading=19,
    spaceBefore=16, spaceAfter=6, textColor=colors.HexColor("#111111")))
styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], fontSize=12, leading=16,
    spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#1f2937")))
styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], fontSize=9.5, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=6, textColor=colors.HexColor("#222222")))
styles.add(ParagraphStyle(name="Caption", parent=styles["Body"], fontSize=8.5, leading=11,
    textColor=colors.HexColor("#6b7280"), spaceAfter=10))
styles.add(ParagraphStyle(name="CodeBox", parent=styles["Code"], fontSize=8, leading=10,
    textColor=colors.HexColor("#111111"),
    backColor=colors.HexColor("#f5f5f5"),
    borderPadding=6, borderColor=colors.HexColor("#e5e7eb"), borderWidth=0.4,
    leftIndent=4, rightIndent=4, spaceBefore=6, spaceAfter=10))
styles.add(ParagraphStyle(name="BulletDona", parent=styles["Body"], leftIndent=14, bulletIndent=2,
    spaceAfter=2))


def H1(t): return Paragraph(t, styles["H1"])
def H2(t): return Paragraph(t, styles["H2"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])
def BANNER(t): return Paragraph(t, styles["Banner"])
def WARN(t): return Paragraph(t, styles["WarnBanner"])


def bullets(items):
    return [Paragraph("&bull; " + it, styles["BulletDona"]) for it in items]


def make_table(rows, col_widths=None, header=True):
    tbl = Table(rows, colWidths=col_widths, hAlign="LEFT")
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#d1d5db")),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.HexColor("#d1d5db")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.HexColor("#9ca3af")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")))
    tbl.setStyle(TableStyle(style))
    return tbl


story = []

story.append(Paragraph("T2.1.C · Ejecutores reales con guardrails",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · Branch <b>pr/t2.1.c-real-executors-guardrails</b> "
    "· base <b>main@019492c</b> · LLM real para LOW/MEDIUM internas · "
    "guardrails T2.1.A intactos",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> PR listo para revisión. <b>812/812 pytest · "
    "35/35 vitest · tsc 0 errores</b>. Los 10 ejecutores LOW/MEDIUM "
    "ahora producen output útil real (LLM via DeepSeek/Haiku) con "
    "fallback determinístico mejorado. <b>HIGH y CRITICAL siguen "
    "bloqueados</b> · ningún envío externo real ocurre. Sin merge · "
    "sin deploy."
))

# ── 1. Resumen ejecutivo ──────────────────────────────────────────────

story.append(H1("1. Resumen ejecutivo"))

story.append(P(
    "El Action Center pasaba listas vacías y esqueletos placeholder. "
    "T2.1.C conecta el cliente LLM existente del proyecto "
    "(<i>agent/llm.py</i> · DeepSeek con fallback Haiku) a los 10 "
    "ejecutores LOW y MEDIUM. Cada uno tiene system prompt versionado, "
    "validación estricta del output, truncado por formato y fallback "
    "determinístico mejorado si el LLM no está disponible."
))

story.extend(bullets([
    "<b>HIGH siguen sin ejecutor</b>: enviar_mensaje_whatsapp / "
    "enviar_campana_masiva / publicar_red_social / contactar_lead "
    "explícitamente NO se mapean en EJECUTORES_T21A. ejecutar_accion "
    "los rechaza con mensaje 'futuro PR'.",
    "<b>CRITICAL siguen bloqueados</b>: el flag esta_bloqueado_t21 "
    "intercepta antes de cualquier ejecutor · audit "
    "<i>action_blocked_critical</i>.",
    "<b>Sanitización doble</b>: el contexto del perfil pasa por "
    "<i>construir_contexto_perfil</i> que cap cada campo a 400 chars "
    "y omite vacíos · el output del LLM se valida (JSON shape · "
    "trunca por formato · longitud máxima por campo).",
    "<b>Audit log enriquecido</b>: cada ejecución registra "
    "<i>action_completed</i> con <i>modo</i> (llm|fallback) y "
    "<i>provider</i> (llm|fallback) sin filtrar el output crudo.",
    "<b>Sin gasto real de créditos</b>: T2.1.C usa el LLM directo "
    "vía agent/llm.py · sin reservas/descuentos. T2.1.D es el PR "
    "específico de billing.",
]))

# ── 2. Causa / objetivo ──────────────────────────────────────────────

story.append(H1("2. Causa / objetivo"))

story.append(P(
    "Tras T2.1.A + T2.1.B el Action Center funciona estructuralmente · "
    "lifecycle de acciones, permisos, audit log, dashboard. Pero los "
    "ejecutores entregaban placeholder strings · útiles para validar "
    "el flow, inútiles para el usuario final. El objetivo de T2.1.C "
    "es cerrar esa brecha sin abrir riesgo: dar valor real a las "
    "acciones LOW/MEDIUM internas (generación de texto), manteniendo "
    "los guardrails que ya nos hicieron rechazar HIGH/CRITICAL."
))

# ── 3. Archivos modificados ──────────────────────────────────────────

story.append(H1("3. Archivos modificados"))

story.append(make_table([
    ["Archivo", "Tipo", "Cambio"],
    ["agent/automation/prompts.py", "NEW",
     "10 system prompts versionados · 1 por ejecutor · "
     "<i>construir_contexto_perfil()</i> sanitiza y trunca a "
     "400 chars/campo · omite vacíos. MAX_CHARS_POR_CAMPO=400."],
    ["agent/automation/execution.py", "MOD",
     "10 ejecutores reescritos para usar agent/llm.py + fallback. "
     "Helpers <i>_llm_completar()</i>, <i>_parsear_json_seguro()</i> "
     "(tolera fences ```json), <i>_trunc()</i>. Audit log "
     "<i>action_completed</i> incluye modo y provider."],
    ["tests/test_automation_executors_real.py", "NEW",
     "<b>25 tests pytest</b> · LLM mocked · cubre cada ejecutor "
     "happy path · fallback · validación de output · guardrails "
     "HIGH/CRITICAL · audit con modo · NO referencias a "
     "providers reales en el source."],
    ["tests/test_automation_execution.py", "MOD",
     "Test T2.1.A actualizado: modo ahora es 'llm'|'fallback' "
     "(antes 'dry_run'). +1 línea."],
], col_widths=[2.6*inch, 0.5*inch, 3.5*inch]))

# ── 4. Ejecutores conectados ─────────────────────────────────────────

story.append(H1("4. Ejecutores conectados"))

story.append(H2("LOW (auto-ejecutables) · 5 ejecutores"))

story.append(make_table([
    ["tipo_accion", "Output del LLM", "Fallback"],
    ["generar_plan_semanal", "Markdown · 5-7 acciones por día",
     "Esqueleto basado en perfil · 5 días + Próximo paso"],
    ["generar_calendario_contenido", "JSON array 7 días · titulo · "
     "copy · formato · canal",
     "JSON 7 días con formatos rotados · canal del perfil"],
    ["generar_checklist_ventas", "Markdown checklist 8-12 items "
     "imperativos",
     "8 items predefinidos accionables esta semana"],
    ["analizar_diagnostico", "JSON · completitud · fortalezas · "
     "oportunidades · riesgos · recomendacion",
     "Cálculo local de completitud · recomendación según %"],
    ["generar_idea_oferta", "JSON 3 alternativas · titulo · "
     "descripcion · por_que_funciona · riesgo",
     "3 alternativas genéricas (paquete inicial · recurrente · "
     "bundle premium)"],
], col_widths=[2.0*inch, 2.6*inch, 2.0*inch]))

story.append(H2("MEDIUM (preparan · NO envían) · 5 ejecutores"))

story.append(make_table([
    ["tipo_accion", "Output del LLM", "Fallback"],
    ["preparar_mensaje_whatsapp", "Borrador texto · placeholder "
     "{NOMBRE} · max 600 chars",
     "Borrador genérico cálido · placeholder {NOMBRE}"],
    ["preparar_campana_whatsapp", "JSON 3 mensajes (anuncio · "
     "recordatorio · cierre)",
     "3 mensajes genéricos por día (1, 3, 5)"],
    ["preparar_publicacion_redes", "JSON copy · hashtags · formato "
     "· CTA",
     "Copy reflexivo · 2 hashtags · post · CTA pregunta"],
    ["preparar_email_seguimiento", "JSON asunto + cuerpo · max 800 "
     "chars",
     "Email cálido genérico · placeholder {NOMBRE}"],
    ["borrador_copy_oferta", "JSON titulo + copy_largo + 2 "
     "variantes A/B",
     "Copy genérico + 2 variantes simples"],
], col_widths=[2.0*inch, 2.6*inch, 2.0*inch]))

story.append(BANNER(
    "<b>Cada output MEDIUM incluye <i>estado_envio: "
    "'pending_user_review'</i></b> y un campo <i>aviso</i> que "
    "recuerda al usuario que es solo borrador. El componente UI "
    "ya muestra esos resultados en el Action Center."
))

# ── 5. Proveedor LLM ─────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("5. Proveedor LLM usado"))

story.append(P(
    "Reusa el cliente existente <i>agent/llm.py</i> que ya viene en el "
    "proyecto desde antes (lo usan emotion, learning, location, "
    "onboarding, contenido):"
))

story.extend(bullets([
    "<b>Primario · DeepSeek</b> (<i>deepseek-chat</i>) · barato y "
    "rápido para tareas de generación. API key en "
    "<i>DEEPSEEK_API_KEY</i>.",
    "<b>Fallback · Claude Haiku 4.5</b> (<i>claude-haiku-4-5-20251001</i>) "
    "· si DeepSeek falla. API key en <i>ANTHROPIC_API_KEY</i>.",
    "<b>Ambos con timeout corto y manejo de excepciones</b>. Si los "
    "dos fallan, <i>completar_con_sistema()</i> retorna None y el "
    "ejecutor cae a su fallback determinístico.",
    "<b>NO se introdujo un nuevo cliente LLM.</b> Esto evita "
    "duplicar config, env vars y fees · respeta la convención del "
    "proyecto.",
]))

story.append(C(
    "Si en el futuro se quisiera modelo distinto (Sonnet, Opus) "
    "para alguna acción específica, se haría en otro PR · agent/llm.py "
    "se extiende sin tocar T2.1.C."
))

# ── 6. Tests ejecutados ──────────────────────────────────────────────

story.append(H1("6. Tests ejecutados"))

story.append(BANNER(
    "<b>pytest · 812/812 passing</b> (787 base + 25 nuevos T2.1.C) "
    "· 173s.<br/>"
    "<b>vitest · 35/35 passing</b> (sin cambios desde T2.1.B "
    "hotfix).<br/>"
    "<b>tsc · 0 errores · build no necesita rebuild (solo backend "
    "cambió).</b>"
))

story.append(H2("Tests T2.1.C nuevos · 25"))

story.append(make_table([
    ["Clase", "Tests", "Cubre"],
    ["TestContextoSanitizado", "3",
     "Perfil vacío → placeholder · campos vacíos omitidos · "
     "trunca a 400 chars"],
    ["TestEjecutorPlanSemanal", "2",
     "LLM responde → modo=llm · LLM None → fallback útil "
     "(no placeholder)"],
    ["TestEjecutorCalendarioContenido", "3",
     "JSON array · JSON con fences ```json · JSON inválido → fallback"],
    ["TestEjecutorChecklistVentas", "2",
     "LLM markdown lista parsea · fallback ≥8 items"],
    ["TestEjecutorAnalizarDiagnostico", "2",
     "LLM JSON dict · fallback calcula completitud local"],
    ["TestEjecutorIdeaOferta", "1",
     "Fallback con 3 alternativas estructuradas"],
    ["TestEjecutorPreparMensajeWhatsApp", "2",
     "MEDIUM sin aprobar → falla · aprobado → completed con "
     "estado_envio=pending_user_review"],
    ["TestEjecutorPreparPublicacionRedes", "1",
     "Aprobado → estado_publicacion=pending_user_review"],
    ["TestEjecutorPreparEmailSeguimiento", "1",
     "Genera asunto + cuerpo · estado_envio=pending_user_review"],
    ["TestEjecutorPreparCampanaWhatsApp", "1",
     "3 mensajes · estado_envio=pending_user_review"],
    ["TestEjecutorBorradorCopyOferta", "1",
     "Copy + 2 variantes A/B"],
    ["<b>TestGuardrailsHigh</b>", "<b>3</b>",
     "<b>enviar_mensaje_whatsapp · publicar_red_social · "
     "contactar_lead aprobados → fallan</b> con mensaje 'futuro PR'"],
    ["<b>TestGuardrailsCritical</b>", "<b>1</b>",
     "<b>envio_masivo_clientes aprobado → bloqueado</b>"],
    ["<b>TestEjecutoresNoUsanProvidersReales</b>", "<b>1</b>",
     "<b>Inspecciona source de los 10 ejecutores · prohibido "
     "whapi/twilio/stripe./providers/send_message/enviar_mensaje/"
     "publish_/post_to_*</b>"],
    ["<b>TestAuditLogModoYProviderEnPayload</b>", "<b>1</b>",
     "<b>action_completed payload incluye modo=llm provider=llm · "
     "telefono completo NO en log ni summary</b>"],
], col_widths=[2.8*inch, 0.4*inch, 3.4*inch]))

# ── 7. Riesgos ───────────────────────────────────────────────────────

story.append(H1("7. Riesgos"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["LLM puede inventar datos del cliente",
     "Bajo · UX",
     "System prompts EXPLÍCITAMENTE prohíben inventar nombres "
     "propios · usan {NOMBRE} placeholder. Tests verifican que "
     "fallbacks no contienen 'placeholder T2.1.A'."],
    ["LLM puede generar texto en idioma incorrecto",
     "Bajo",
     "System prompts piden español explícito · perfil del usuario "
     "(MX/CO/AR/EU/US) ya define contexto regional."],
    ["JSON malformado del LLM",
     "Bajo",
     "<i>_parsear_json_seguro()</i> tolera fences ```json y prosa "
     "alrededor · si falla, cae a fallback determinístico. Test "
     "específico cubre 'esto no es JSON' → fallback."],
    ["Costo LLM si el usuario abusa de 'Generar acciones'",
     "Medio · billing",
     "Idempotencia ya existente (idempotency_key sha256(tel|tipo|"
     "playbook|opp|fecha)) evita duplicar ejecuciones del mismo "
     "día. T2.1.D agregará reservas/descuentos reales."],
    ["LLM filtra PII si el usuario la incluye en el perfil",
     "Bajo · CCPA",
     "<i>construir_contexto_perfil()</i> trunca a 400 chars/campo. "
     "El audit log NO loguea el output crudo · solo modo y provider. "
     "El output va a DB en <i>result_json</i> pero no a logs."],
    ["Race condition aiosqlite en pytest workers",
     "Cero · solo dev",
     "Issue conocido · re-run pasa consistente."],
], col_widths=[2.6*inch, 0.8*inch, 3.2*inch]))

# ── 8. Out of scope ───────────────────────────────────────────────────

story.append(H1("8. Out of scope · NO entra en T2.1.C"))

story.extend(bullets([
    "<b>Ejecutores HIGH reales</b> (envío real WhatsApp/Twilio/email/"
    "publicaciones redes) · explícitamente excluidos · esperan T2.1.D "
    "o futuro PR con guardrails reforzados (TCPA, opt-in, rate-limit, "
    "reembolso si falla).",
    "<b>Desbloquear CRITICAL</b> · explícitamente excluido. Requiere "
    "confirmación reforzada (2FA owner · cooldown timer · etc).",
    "<b>Reservas/descuento de créditos</b> · T2.1.D. T2.1.C estima "
    "costo en <i>costo_creditos_estimado</i> pero no descuenta nada.",
    "<b>Streaming de respuestas LLM</b> · respuestas son one-shot · "
    "el usuario espera ~3-10s y ve el resultado. Streaming sería "
    "futuro PR con SSE o websocket.",
    "<b>Caché de LLM</b> · cada 'Ejecutar' llama al LLM. Si la "
    "acción ya fue ejecutada, su result_json se conserva en DB · "
    "pero re-ejecutar pide al LLM de nuevo.",
    "<b>Métricas de calidad del LLM</b> (eval framework) · futuro.",
    "<b>Refinar prompts con feedback del usuario</b> (thumbs up/down) "
    "· futuro · T2.1.E quizás.",
]))

# ── 9. Siguiente PR recomendado ──────────────────────────────────────

story.append(H1("9. Siguiente PR recomendado · T2.1.D"))

story.append(P(
    "<b>T2.1.D · Reservas y descuento real de créditos · audit "
    "extendido</b>:"
))

story.extend(bullets([
    "Reservar créditos al iniciar ejecución (transaccional con la "
    "transición a 'running').",
    "Descontar al completar · reembolsar al fallar (transición → "
    "failed o → cancelled).",
    "Ajustar costo estimado vs real (tokens consumidos via LLM "
    "response.usage si el SDK lo expone).",
    "Pruning del audit log · retención configurable.",
    "Dashboard métrica: 'créditos consumidos por automation este "
    "mes'.",
    "<b>NO desbloquear CRITICAL ni HIGH reales en T2.1.D</b> · "
    "esos esperan PR específico de cada vertical (envío WhatsApp · "
    "publicación redes · etc) con sus guardrails dedicados.",
]))

# ── 10. Datos para abrir PR ──────────────────────────────────────────

story.append(H1("10. Instrucciones para abrir PR"))

story.append(make_table([
    ["Campo", "Valor"],
    ["URL",
     "github.com/celestinojbm/Dona-agent/pull/new/<br/>"
     "pr/t2.1.c-real-executors-guardrails"],
    ["Título sugerido",
     "feat(automation): ejecutores reales con guardrails (T2.1.C)"],
    ["Base", "main"],
    ["Head", "pr/t2.1.c-real-executors-guardrails"],
    ["Body markdown",
     "Generado abajo · listo para copiar/pegar"],
], col_widths=[1.6*inch, 5.0*inch]))

# ── 11. Body markdown ────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("11. Body markdown del PR (copy-paste)"))

story.append(CODE(
    "## Resumen\n"
    "\n"
    "Conecta los 10 ejecutores LOW/MEDIUM del Action Center al cliente\n"
    "LLM existente del proyecto (agent/llm.py · DeepSeek + fallback\n"
    "Claude Haiku). Los ejecutores ahora producen output útil real\n"
    "(plan semanal, calendario contenido, checklist, mensajes WA,\n"
    "borradores copy, etc.) en lugar de placeholders.\n"
    "\n"
    "Guardrails T2.1.A intactos:\n"
    "- LOW pending → ejecuta auto\n"
    "- MEDIUM/HIGH → requieren aprobación\n"
    "- HIGH (enviar_*, publicar_*, contactar_lead) → SIN ejecutor ·\n"
    "  ejecutar_accion los rechaza con mensaje 'futuro PR'\n"
    "- CRITICAL → bloqueado · audit action_blocked_critical\n"
    "\n"
    "Cero envíos externos reales. Cero gasto de créditos reales\n"
    "(T2.1.D agrega reservas).\n"
    "\n"
    "## Cambios\n"
    "\n"
    "- agent/automation/prompts.py (NEW) · 10 system prompts\n"
    "  versionados · construir_contexto_perfil() sanitiza y trunca\n"
    "  a 400 chars/campo · omite vacíos.\n"
    "- agent/automation/execution.py · 10 ejecutores reescritos.\n"
    "  Helpers _llm_completar(), _parsear_json_seguro() (tolera\n"
    "  fences ```json), _trunc(). Audit log action_completed\n"
    "  incluye modo y provider.\n"
    "- tests/test_automation_executors_real.py (NEW) · 25 tests\n"
    "  con LLM mocked.\n"
    "- tests/test_automation_execution.py · ajuste de assert\n"
    "  modo='dry_run' → 'llm'|'fallback' (+1 línea).\n"
    "\n"
    "## Provider LLM\n"
    "\n"
    "Reusa agent/llm.py existente · DeepSeek primario + Claude Haiku\n"
    "fallback. NO se introduce cliente nuevo. Si LLM no responde\n"
    "(env vars faltantes o errores), cada ejecutor cae a fallback\n"
    "determinístico mejorado (no placeholders inútiles).\n"
    "\n"
    "## Tests\n"
    "\n"
    "- pytest tests/test_automation_executors_real.py · 25/25\n"
    "  passing · 17s\n"
    "- pytest suite completa · 812/812 passing · 173s · cero\n"
    "  regresiones\n"
    "- vitest · 35/35 passing (sin cambios)\n"
    "- npx tsc --noEmit · 0 errores\n"
    "\n"
    "Tests específicos verifican:\n"
    "- Cada ejecutor LLM happy path → modo=llm\n"
    "- LLM None → fallback determinístico útil\n"
    "- JSON con fences ```json se parsea\n"
    "- HIGH (enviar_mensaje_whatsapp · publicar_red_social ·\n"
    "  contactar_lead) aprobados → failed con 'futuro PR'\n"
    "- CRITICAL aprobado → bloqueado · audit\n"
    "  action_blocked_critical\n"
    "- Source de los 10 ejecutores NO contiene whapi/twilio/\n"
    "  stripe./providers/send_message/enviar_mensaje/publish_/\n"
    "  post_to_*\n"
    "- Audit payload tiene modo+provider · sin telefono completo\n"
    "- construir_contexto_perfil omite vacíos y trunca a 400 chars\n"
    "\n"
    "## Sin cambios de\n"
    "\n"
    "- env vars · agent/llm.py ya leía DEEPSEEK_API_KEY y\n"
    "  ANTHROPIC_API_KEY (presentes en Render)\n"
    "- modelos DB · audit log usa columnas existentes\n"
    "- endpoints HTTP · /api/automation/* sin cambios\n"
    "- componente UI · seccion-action-center.tsx sin cambios\n"
    "  (renderiza el result_json más útil automáticamente)\n"
    "\n"
    "## Out of scope\n"
    "\n"
    "- Ejecutores HIGH reales (envío WhatsApp/email/posts) · futuros\n"
    "  PRs con guardrails dedicados (TCPA, opt-in, rate-limit)\n"
    "- Desbloquear CRITICAL · futuro · requiere 2FA + cooldown\n"
    "- Reservas/descuento real créditos · T2.1.D\n"
    "- Streaming respuestas · caché LLM · eval framework\n"
    "- Refinar prompts con feedback usuario\n"
    "\n"
    "## Plan post-merge\n"
    "\n"
    "1. Render auto-redeploy ~2 min · ejecutores ya activos.\n"
    "2. Smoke en dashboard:\n"
    "   - usuario premium con perfil completo · botón 'Generar\n"
    "     acciones' · ver acciones generadas\n"
    "   - 'Ejecutar' una LOW (generar_plan_semanal) · ver plan\n"
    "     real en markdown en la card 'Resultado'\n"
    "   - aprobar y ejecutar una MEDIUM (preparar_mensaje_whatsapp)\n"
    "     · ver borrador real\n"
    "3. Verificar Vercel/Render logs · debería aparecer\n"
    "   '[AUDIT-AUT] ... evento=action_completed riesgo=low ...'\n"
    "   con modo=llm en el payload sanitizado.\n"
))

story.append(BANNER(
    "<b>Branch pushed · sin merge.</b> Espera tu review en GitHub. "
    "Yo no mergeo nada hasta tu OK explícito."
))


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
