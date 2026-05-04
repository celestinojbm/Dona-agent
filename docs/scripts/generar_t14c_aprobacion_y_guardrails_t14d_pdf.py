"""
Genera T1.4.C-Aprobacion-y-Guardrails-T1.4.D-2026-05-03.pdf en docs/auditorias/.
Aprobación formal de T1.4.C y captura de guardrails para T1.4.D.

No toca archivos del proyecto. No envia datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\T1.4.C-Aprobacion-y-Guardrails-T1.4.D-2026-05-03.pdf"

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="TitleBig", parent=styles["Title"], fontSize=22, leading=26,
    spaceAfter=8, textColor=colors.HexColor("#111111"),
))
styles.add(ParagraphStyle(
    name="Subtitle", parent=styles["Normal"], fontSize=11, leading=15,
    textColor=colors.HexColor("#374151"), spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="MetaTop", parent=styles["Normal"], fontSize=9, leading=12,
    textColor=colors.HexColor("#555555"), spaceAfter=18,
))
styles.add(ParagraphStyle(
    name="Banner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#065f46"), backColor=colors.HexColor("#ecfdf5"),
    borderPadding=8, borderColor=colors.HexColor("#10b981"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14,
))
styles.add(ParagraphStyle(
    name="WarnBanner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#7c2d12"), backColor=colors.HexColor("#fff7ed"),
    borderPadding=8, borderColor=colors.HexColor("#f97316"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14,
))
styles.add(ParagraphStyle(
    name="DangerBanner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#991b1b"), backColor=colors.HexColor("#fef2f2"),
    borderPadding=8, borderColor=colors.HexColor("#dc2626"), borderWidth=0.8,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14,
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
    name="Body", parent=styles["BodyText"], fontSize=9.5, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=6, textColor=colors.HexColor("#222222"),
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
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])
def BANNER(t): return Paragraph(t, styles["Banner"])
def WARN(t): return Paragraph(t, styles["WarnBanner"])
def DANGER(t): return Paragraph(t, styles["DangerBanner"])


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


# ─────────────────────────────────────────────────────────────────────────────


story = []

story.append(Paragraph("T1.4.C aprobado · Guardrails para T1.4.D",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Aprobación formal de T1.4.C + reglas vinculantes para T1.4.D",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-03 · Branch <b>pr/t1.4.c-usuario-resumen</b> "
    "@ commit <b>9030bec</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>T1.4.C aprobado por Dona Control para merge.</b> Branch limpia "
    "y sincronizada con remoto. PR listo para mergear vía GitHub UI. "
    "Guardrails T1.4.D persistidas en memoria de Claude para sesiones "
    "futuras."
))

# ── 1. Estado del PR T1.4.C ────────────────────────────────────────────────

story.append(H1("1. Estado del PR T1.4.C"))

story.append(make_table([
    ["Item", "Estado"],
    ["Endpoint POST /internal/usuario-resumen creado", "✓"],
    ["Auth via HMAC con INTERNAL_BRIDGE_SECRET", "✓"],
    ["Read-only (verificado con test antes/después)", "✓"],
    ["No toca producción (sin deploy, sin merge)", "✓"],
    ["21 tests nuevos verdes", "✓"],
    ["Suite completa: 575 passed (Δ +21 vs baseline)", "✓"],
    ["No requiere env var nueva (reusa INTERNAL_BRIDGE_SECRET)", "✓"],
    ["Aprobado por Dona Control", "✓"],
], col_widths=[5.2*inch, 1.0*inch]))

story.append(P(
    "<b>PR para mergear:</b> "
    "https://github.com/celestinojbm/Dona-agent/compare/main...pr/t1.4.c-usuario-resumen"
))

# ── 2. Guardrails T1.4.D ───────────────────────────────────────────────────

story.append(H1("2. Guardrails capturadas para T1.4.D"))
story.append(P(
    "Estas reglas vienen de la revisión del owner sobre T1.4.C. Cuando "
    "se inicie T1.4.D, <b>deben respetarse desde el primer commit</b>, "
    "no como follow-up."
))

# ── 2.1 server-side identifier ─────────────────────────────────────────────

story.append(H2("2.1 Identificador de usuario sólo desde la sesión server-side"))

story.append(DANGER(
    "<b>Regla:</b> landing/app/api/dashboard-data/route.ts (T1.4.D) "
    "<b>NO</b> debe aceptar subscription_id desde el cliente/browser. "
    "El identificador debe leerse <b>únicamente</b> desde la sesión "
    "server-side de NextAuth (ej. session.subscriptionId)."
))

story.append(P("<b>Patrón obligatorio:</b>"))
story.append(CODE(
    "import { auth } from \"@/auth\";\n"
    "\n"
    "export async function GET() {\n"
    "  const session = await auth();\n"
    "  if (!session) return new Response(null, { status: 401 });\n"
    "\n"
    "  const subscriptionId = (session as any).subscriptionId;\n"
    "  if (!subscriptionId) return new Response(null, { status: 403 });\n"
    "\n"
    "  // ... POST a backend con HMAC, usando subscriptionId\n"
    "  //     tomado de session, NO del request del cliente\n"
    "}"
))

story.append(P(
    "<b>Razón:</b> El HMAC protege la comunicación landing → backend "
    "contra manipulación en tránsito, pero NO impide que un usuario "
    "autenticado intente consultar la suscripción de OTRO usuario "
    "enviando un subscription_id ajeno desde el navegador. Confiar en "
    "session.* server-side es la única forma de garantizar que el dato "
    "pedido corresponde al usuario logueado."
))

story.append(P("<b>Aplica también a:</b>"))
story.extend(bullets([
    "/api/cancel-subscription (ya cumple — usa session.subscriptionId).",
    "Cualquier futuro proxy del landing al backend (T1.4.E, T1.4.F).",
    "Cualquier ruta que mande request firmado al /internal/* del backend.",
]))

# ── 2.2 No log full IDs ────────────────────────────────────────────────────

story.append(H2("2.2 No loguear subscription_id completo en producción"))

story.append(WARN(
    "<b>Regla:</b> En producción, los identificadores Stripe (sub_xxx, "
    "cus_xxx, in_xxx) se truncan o redactan en logs. No son secretos "
    "crudos pero correlacionan trivialmente con un usuario específico. "
    "<b>No es blocker para T1.4.C.</b> Aplica a código nuevo de T1.4.D "
    "en adelante."
))

story.append(P("<b>Patrones aceptables:</b>"))
story.append(CODE(
    "# Backend (Python):\n"
    "sub_short = sub_id[:8] + \"...\" + sub_id[-4:] \\\n"
    "    if len(sub_id) > 12 else sub_id\n"
    "logger.info(f\"[INTERNAL] usuario-resumen para sub={sub_short}\")\n"
    "\n"
    "// Landing (TypeScript):\n"
    "const subShort = subId.length > 12\n"
    "  ? `${subId.slice(0, 8)}...${subId.slice(-4)}`\n"
    "  : subId;\n"
    "console.log(`[BRIDGE] dashboard-data sub=${subShort}`);"
))

story.append(P(
    "Código existente de T1.3.* y T1.4.C ya quedó como está. No requiere "
    "refactor inmediato."
))

# ── 3. Diseño tentativo T1.4.D ─────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Diseño tentativo de T1.4.D (sin implementar)"))

story.append(H2("Archivo nuevo"))
story.append(P(
    "<b>landing/app/api/dashboard-data/route.ts</b> — handler GET."
))

story.append(H2("Flujo server-side"))
story.extend(bullets([
    "<b>1.</b> const session = await auth();",
    "<b>2.</b> Si no hay sesión → 401 unauthenticated.",
    "<b>3.</b> Tomar subscriptionId de session.subscriptionId. "
    "<b>NUNCA</b> del request. Si no está → 403 no_subscription.",
    "<b>4.</b> Llamar al backend en paralelo a Stripe SDK:",
    "&nbsp;&nbsp;&nbsp;<b>Backend</b>: POST /internal/usuario-resumen "
    "con HMAC reusando helper de T1.3.E (extender con "
    "fetchUsuarioResumen).",
    "&nbsp;&nbsp;&nbsp;<b>Stripe SDK</b>: subscriptions.retrieve para "
    "current_period_end y cancel_at_period_end.",
    "<b>5.</b> Mergear: backend JSON + Stripe data + session.user.email.",
    "<b>6.</b> Retornar al cliente.",
]))

story.append(H2("Manejo de errores del backend"))
story.append(make_table([
    ["Backend respondió", "Acción del landing"],
    ["401", "Log 'secret desincronizado' + 502 al cliente"],
    ["404", "404 al cliente con mensaje 'suscripción no encontrada'"],
    ["500", "502 al cliente, log para alerta"],
    ["timeout", "504 al cliente"],
    ["200 OK", "merge con Stripe data + 200 al cliente"],
], col_widths=[1.5*inch, 4.5*inch]))

story.append(H2("Validación a correr en T1.4.D"))
story.extend(bullets([
    "npx tsc --noEmit — 0 errores.",
    "npm run lint — sin nuevos.",
    "npm run build — pasa, ruta nueva registrada.",
    "Smoke manual: con sesión válida → 200 con datos.",
    "Smoke negativo: sesión sin subscriptionId → 401/403.",
]))

story.append(H2("Lo que NO hacer en T1.4.D"))
story.extend(bullets([
    "No modificar el endpoint backend (T1.4.C aprobado).",
    "No exponer INTERNAL_BRIDGE_SECRET ni STRIPE_SECRET_KEY al cliente.",
    "No aceptar subscription_id (ni cualquier otro id de usuario) del "
    "request del browser.",
    "No tocar UI del dashboard (T1.4.E).",
    "No tocar cancelación (T1.4.F).",
]))

# ── 4. Persistencia en memoria ─────────────────────────────────────────────

story.append(H1("4. Persistencia en memoria de Claude"))
story.append(P(
    "Las dos guardrails se guardaron en el sistema de memoria de Claude "
    "para que estén disponibles en futuras sesiones aunque cambie el "
    "contexto:"
))
story.append(CODE(
    "memory/feedback_landing_proxy_identifiers.md\n"
    "memory/feedback_no_log_full_subscription_id.md"
))
story.append(P(
    "Indexadas en <i>MEMORY.md</i>. Aplican a cualquier proxy nuevo del "
    "landing al backend, no solo T1.4.D."
))

# ── 5. Pendientes housekeeping ─────────────────────────────────────────────

story.append(H1("5. Pendientes housekeeping (acumulados desde T1.4.A)"))
story.append(P(
    "Tras mergear T1.4.C quedarán <b>10 archivos untracked</b> en "
    "docs/auditorias/ y docs/scripts/ (reportes T1.4.A, T1.4.B, T1.4.C "
    "y este mismo doc). Recomendación: housekeeping al cierre de T1.4 "
    "(después de mergear T1.4.D / E / F), siguiendo el patrón de "
    "<i>pr/post-t1.3-housekeeping</i>."
))

# ── 6. Próximos pasos del owner ────────────────────────────────────────────

story.append(H1("6. Próximos pasos del owner"))
story.extend(bullets([
    "1. <b>Mergear T1.4.C</b> vía GitHub UI: "
    "https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/t1.4.c-usuario-resumen",
    "2. Render redespliega automáticamente — el endpoint queda "
    "<b>desplegado pero sin tráfico</b> hasta T1.4.D.",
    "3. Cuando estés listo, autorizar T1.4.D — Claude implementará "
    "respetando las dos guardrails desde el primer commit.",
]))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Documento generado el 2026-05-03 por Claude Code (Opus 4.7) en "
    "sesión con el owner. Captura aprobación de T1.4.C y guardrails "
    "para T1.4.D. No incluye cambios de código ni operaciones de "
    "despliegue."
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.4.C aprobado · Guardrails T1.4.D",
    author="Claude Code",
    subject="Aprobación T1.4.C + guardrails T1.4.D",
)
doc.build(story)
print(f"OK: {OUTPUT}")
