"""
Genera Resumen_Post_T14_Housekeeping_2026-05-04.pdf — housekeeping
post T1.4 (commit 5731c9d, rama pr/post-t1.4-housekeeping).

No toca archivos del proyecto. No envia datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_Post_T14_Housekeeping_2026-05-04.pdf"

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
    name="Banner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#065f46"), backColor=colors.HexColor("#ecfdf5"),
    borderPadding=8, borderColor=colors.HexColor("#10b981"), borderWidth=0.6,
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

story.append(Paragraph("Mini-housekeeping post T1.4", styles["TitleBig"]))
story.append(Paragraph(
    "Rama <b>pr/post-t1.4-housekeeping</b> · Commit <b>5731c9d</b> · "
    "2026-05-04",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Resultado:</b> Working tree limpio. 6 ramas locales obsoletas "
    "borradas. 19 artefactos de T1.4.A–F + reporte de cierre formal "
    "ordenados en docs/auditorias/ y docs/scripts/. Branch pusheado "
    "a GitHub. Sin cambios de código productivo."
))

# ── 1. Rama y archivos ────────────────────────────────────────────────────

story.append(H1("1. Rama y estado git"))

story.append(make_table([
    ["Item", "Valor"],
    ["Rama usada", "pr/post-t1.4-housekeeping"],
    ["main local", "3504b1c (alineado con origin/main, PR #24 T1.4.E)"],
    ["HEAD del PR", "5731c9d docs: housekeeping post T1.4..."],
    ["Working tree", "limpio (todo committeado)"],
    ["Ramas remotas pr/t1.4.* + pr/post-t1.3", "borradas (verificado en fetch --prune)"],
], col_widths=[2.0*inch, 4.5*inch]))

# ── 2. Ramas locales borradas ─────────────────────────────────────────────

story.append(H1("2. Ramas locales borradas"))

story.append(P(
    "Las 6 ramas estaban [gone] respecto a su upstream "
    "(mergeadas a main en T1.4.B–F + post-T1.3):"
))
story.extend(bullets([
    "pr/post-t1.3-housekeeping (was a9ab359)",
    "pr/t1.4.b-fix-auth-dashboard (was 2f8e43f)",
    "pr/t1.4.c-usuario-resumen (was 9030bec)",
    "pr/t1.4.d-dashboard-data (was 93b9401)",
    "pr/t1.4.e-dashboard-ui (was 15dc518)",
    "pr/t1.4.f-cancel-at-period-end (was a15652f)",
]))

# ── 3. Artefactos movidos / creados ────────────────────────────────────────

story.append(H1("3. Artefactos movidos y creados"))

story.append(H2("docs/auditorias/ (11 archivos)"))
story.append(make_table([
    ["Archivo", "Origen / Tipo"],
    ["T1.4-Cierre-Formal-2026-05-04.md", "<b>NUEVO</b> · reporte de cierre formal de T1.4"],
    ["T1.4.A-Diagnostico-Dashboard-2026-05-02.md", "Diagnóstico T1.4.A (Markdown)"],
    ["T1.4.A-Diagnostico-Dashboard-2026-05-02.pdf", "Diagnóstico T1.4.A (PDF)"],
    ["T1.4.C-Aprobacion-y-Guardrails-T1.4.D-2026-05-03.md", "Aprobación T1.4.C + guardrails T1.4.D"],
    ["T1.4.C-Aprobacion-y-Guardrails-T1.4.D-2026-05-03.pdf", "PDF del anterior"],
    ["Resumen_T14B_Fix_Auth_Dashboard_2026-05-02.pdf", "PR T1.4.B (fix P0 auth)"],
    ["Resumen_T14C_Usuario_Resumen_2026-05-03.pdf", "PR T1.4.C (endpoint backend)"],
    ["Resumen_T14D_Dashboard_Data_2026-05-03.pdf", "PR T1.4.D (proxy landing)"],
    ["Resumen_T14D_Followup_Estado_Fresco_2026-05-03.pdf", "Follow-up T1.4.D"],
    ["Resumen_T14E_Dashboard_UI_2026-05-04.pdf", "PR T1.4.E (UI)"],
    ["Resumen_T14F_Cancel_At_Period_End_2026-05-04.pdf", "PR T1.4.F (cancel)"],
], col_widths=[3.4*inch, 3.0*inch]))

story.append(H2("docs/scripts/ (8 archivos)"))
story.extend(bullets([
    "generar_t14a_diagnostico_dashboard_pdf.py",
    "generar_resumen_t14b_fix_auth_dashboard_pdf.py",
    "generar_resumen_t14c_usuario_resumen_pdf.py",
    "generar_t14c_aprobacion_y_guardrails_t14d_pdf.py",
    "generar_resumen_t14d_dashboard_data_pdf.py",
    "generar_resumen_t14d_followup_estado_fresco_pdf.py",
    "generar_resumen_t14e_dashboard_ui_pdf.py",
    "generar_resumen_t14f_cancel_at_period_end_pdf.py",
]))
story.append(P(
    "Sigue el patrón establecido en <i>docs/scripts/generar_*_pdf.py</i> "
    "y <i>docs/auditorias/*.pdf</i>. Cada script construye su PDF "
    "correspondiente con reportlab; ninguno toca archivos del proyecto."
))

# ── 4. Verificación ───────────────────────────────────────────────────────

story.append(H1("4. Verificación"))

story.append(make_table([
    ["Check", "Resultado"],
    ["git status -sb (post-stage)",
     "Solo archivos en docs/ stageados"],
    ["git diff --cached --name-only | grep -v ^docs/",
     "0 matches · cero archivos fuera de docs/"],
    ["PDFs validados como binarios sanos",
     "git hash-object devolvió hash consistente para todos los PDFs"],
    ["CRLF warnings",
     "False-positive conocido de Git en Windows · binarios intactos"],
], col_widths=[3.0*inch, 3.5*inch]))

story.append(H2("Por qué no se corrió tests completos"))
story.append(P(
    "Este PR es exclusivamente documentación. <i>git diff --cached</i> "
    "confirma 0 archivos en agent/, landing/app/, landing/lib/, tests/, "
    "alembic/, ni en archivos de configuración. No hay ruta plausible "
    "por la que un cambio en docs/ rompa el build, los tests del "
    "backend, ni el bundle del landing. La verificación de path "
    "(<i>grep -v ^docs/</i>) es suficiente y barata."
))

# ── 5. Lo que NO se hizo ──────────────────────────────────────────────────

story.append(H1("5. Confirmaciones (lo que NO se hizo)"))
story.extend(bullets([
    "✓ <b>NO</b> se modificó código de aplicación "
    "(agent/, landing/app/, landing/lib/, tests/, alembic/).",
    "✓ <b>NO</b> se cambiaron env vars en Render ni Vercel.",
    "✓ <b>NO</b> se hizo deploy.",
    "✓ <b>NO</b> se tocó Stripe Dashboard.",
    "✓ <b>NO</b> se mergeó a main automáticamente — espera review del owner.",
    "✓ <b>NO</b> se borraron datos.",
    "✓ <b>NO</b> se creó endpoint nuevo ni se modificó uno existente.",
    "✓ <b>NO</b> se escribe en la base de datos (este PR no toca DB en absoluto).",
]))

# ── 6. Próximos pasos ─────────────────────────────────────────────────────

story.append(H1("6. Próximos pasos"))

story.append(H2("Para el owner ahora"))
story.extend(bullets([
    "Revisar y mergear el PR de housekeeping en GitHub: "
    "https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/post-t1.4-housekeeping",
    "Tras merge, opcionalmente borrar la branch local "
    "<i>pr/post-t1.4-housekeeping</i>.",
]))

story.append(H2("Recomendación de próximo bloque"))
story.append(P(
    "Según el reporte de cierre T1.4, el roadmap propuesto es:"
))
story.extend(bullets([
    "<b>T1.5</b> — Dashboard polish + safety UX: rate limiting "
    "(/login + /api/dashboard-data), aviso de cancelación pendiente "
    "más visible, mensajes de error en dev cuando "
    "DASHBOARD_PASSWORD_SECRET falta, refactor opcional a "
    "Suspense + use(promise).",
    "<b>T1.6</b> — Observabilidad mínima: contadores en "
    "/admin/metrics para /internal/usuario-resumen, logging "
    "estructurado con request id correlacionable, alerta si HMAC "
    "queda desincronizado entre Vercel y Render.",
    "<b>T2.0</b> — Onboarding premium: Dona envía proactivamente el "
    "password derivado por WhatsApp tras compra, tour guiado del "
    "dashboard, email de bienvenida desde dominio operativo.",
]))

# ── Footer ────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-04 · "
    "Repo: Dona-agent · Branch: pr/post-t1.4-housekeeping · "
    "HEAD: 5731c9d"
))


# ── Build ─────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="Mini-housekeeping post T1.4",
    author="Claude Code",
    subject="Resumen de housekeeping post T1.4",
)
doc.build(story)
print(f"OK: {OUTPUT}")
