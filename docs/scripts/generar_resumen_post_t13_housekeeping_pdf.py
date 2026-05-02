"""
Genera Resumen_Post_T13_Housekeeping_2026-05-02.pdf — mini-housekeeping
post T1.3 (commit f265325, rama pr/post-t1.3-housekeeping).

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

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_Post_T13_Housekeeping_2026-05-02.pdf"

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

story.append(Paragraph("Mini-housekeeping post T1.3", styles["TitleBig"]))
story.append(Paragraph(
    "Rama <b>pr/post-t1.3-housekeeping</b> · Commit <b>f265325</b> · "
    "2026-05-02",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Resultado:</b> Working tree limpio. 6 ramas locales obsoletas "
    "borradas. 21 artefactos movidos a docs/auditorias/ y docs/scripts/. "
    "Branch pusheado a GitHub para PR del owner. Sin cambios de código "
    "productivo."
))

# ── 1. Estado git ──────────────────────────────────────────────────────────

story.append(H1("Estado git"))

story.append(make_table([
    ["Item", "Valor"],
    ["main local", "c46987c (alineado con origin/main)"],
    ["HEAD branch", "pr/post-t1.3-housekeeping"],
    ["HEAD commit", "f265325 docs: housekeeping post T1.3"],
    ["Working tree", "limpio (todo committeado)"],
    ["origin/pr/* T1.3 + legal", "borradas tras merge (verificado en fetch --prune)"],
], col_widths=[1.8*inch, 4.5*inch]))

# ── 2. Ramas borradas ──────────────────────────────────────────────────────

story.append(H1("Ramas borradas"))
story.append(P(
    "Las 6 ramas que componen T1.3 ya fueron mergeadas a main vía PRs "
    "#13–#18 y se eliminaron tanto en remoto (durante el merge) como "
    "en local (este housekeeping):"
))
story.extend(bullets([
    "pr/t1.3.a-suscripcion-stripe-modelos (was 83a5cda)",
    "pr/t1.3.b-creditos-de-plan-helper (was e4e39f1)",
    "pr/t1.3.c-procesar-evento-suscripcion (was 5e00393)",
    "pr/t1.3.d-internal-stripe-event (was 4f5c9ef)",
    "pr/t1.3.e-bridge-landing-backend (was 45da6a1)",
    "pr/legal-pages-stripe (was 50b9cbf)",
]))

# ── 3. Artefactos movidos ──────────────────────────────────────────────────

story.append(H1("Artefactos movidos"))

story.append(H2("docs/auditorias/ (11 archivos)"))
story.append(make_table([
    ["Archivo", "Origen / Tipo"],
    ["T1.3-Cierre-Formal-2026-05-02.md", "Reporte de cierre (Markdown)"],
    ["Reporte_Cierre_T13_2026-05-02.pdf", "Reporte de cierre (PDF)"],
    ["Diagnostico_T13_Stripe_Backend_2026-05-01.pdf", "Diagnóstico inicial"],
    ["Resumen_T13A_Implementacion_2026-05-02.pdf", "PR #13 modelos"],
    ["Resumen_T13B_Implementacion_2026-05-02.pdf", "PR #14 helper"],
    ["Resumen_T13C_Implementacion_2026-05-02.pdf", "PR #15 dispatcher"],
    ["Resumen_T13D_Implementacion_2026-05-02.pdf", "PR #16 endpoint HMAC"],
    ["Resumen_T13E_Implementacion_2026-05-02.pdf", "PR #17 bridge landing"],
    ["Resumen_Legal_Pages_Stripe_2026-05-02.pdf", "PR #18 páginas legales"],
    ["Resumen_Docs_Housekeeping_3_2026-05-01.pdf", "Housekeeping previo"],
    ["Resumen_Mini_Housekeeping_Post_HK3_2026-05-01.pdf", "Mini housekeeping previo"],
], col_widths=[3.4*inch, 3.0*inch]))

story.append(H2("docs/scripts/ (10 archivos generadores de PDF)"))
story.append(P(
    "Mismo patrón que <i>docs/scripts/generar_auditoria.py</i>, "
    "<i>generar_diagnostico_*</i>, etc. Cada generar_*.py construye su "
    "PDF correspondiente en docs/auditorias/ usando reportlab."
))

# ── 4. Verificación de integridad ──────────────────────────────────────────

story.append(H1("Verificación de integridad"))
story.append(P(
    "Las warnings <i>LF will be replaced by CRLF</i> en los PDFs son "
    "informativas (false-positive de Git en Windows). Verificación con "
    "<i>git hash-object</i> confirma que el contenido binario en disco "
    "es idéntico al contenido en index:"
))
story.append(CODE(
    "Reporte_Cierre_T13_2026-05-02.pdf:\n"
    "    disk  = 1899302153c68ddfd816676f1f45fb7261cbc589\n"
    "    index = 1899302153c68ddfd816676f1f45fb7261cbc589  → OK\n"
    "\n"
    "Resumen_T13A_Implementacion_2026-05-02.pdf:\n"
    "    disk  = d81d79c3a9b655c9b41a22efe21b638dcb75ff59\n"
    "    index = d81d79c3a9b655c9b41a22efe21b638dcb75ff59  → OK"
))

# ── 5. Lo que NO se hizo ───────────────────────────────────────────────────

story.append(H1("Lo que NO se hizo (por diseño)"))
story.extend(bullets([
    "<b>No</b> se modificó código productivo (agent/, landing/lib/, "
    "landing/app/api/, etc.).",
    "<b>No</b> se cambiaron env vars en Render ni Vercel.",
    "<b>No</b> se hizo deploy.",
    "<b>No</b> se tocó Stripe Dashboard.",
    "<b>No</b> se mergeó a main automáticamente — espera PR review del "
    "owner.",
    "<b>No</b> se ejecutó T1.3.F (mover Stripe URL al backend); "
    "decisión registrada: aplazar hasta varias semanas de soak con el "
    "bridge actual.",
]))

# ── 6. Próximos pasos ──────────────────────────────────────────────────────

story.append(H1("Próximos pasos / Recomendación"))

story.append(H2("Para el owner ahora"))
story.extend(bullets([
    "Mergear este PR de housekeeping en GitHub: "
    "https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/post-t1.3-housekeeping",
    "Tras merge, opcionalmente borrar la rama local "
    "<i>pr/post-t1.3-housekeeping</i>.",
]))

story.append(H2("Recomendación de próximo bloque"))
story.append(P(
    "Antes de tocar más código, <b>24–48h de soak</b> monitoreando: "
    "Stripe Webhooks Dashboard (status del endpoint del landing), "
    "Vercel logs (filtrar [BRIDGE] / bridge_failed) y Render logs "
    "(/internal/stripe-event). Si no hay alertas:"
))
story.extend(bullets([
    "<b>Prueba Pro +500</b> con compra real o Stripe test mode.",
    "<b>Observar primer ciclo de renovación</b> en ~30 días para "
    "validar invoice.payment_succeeded mensual.",
    "Avanzar al siguiente bloque de <b>Phase 1</b> del plan v2.1.",
]))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-02 · "
    "Repo: Dona-agent · Branch: pr/post-t1.3-housekeeping · "
    "HEAD: f265325"
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="Mini-housekeeping post T1.3",
    author="Claude Code",
    subject="Resumen de housekeeping post T1.3",
)
doc.build(story)
print(f"OK: {OUTPUT}")
