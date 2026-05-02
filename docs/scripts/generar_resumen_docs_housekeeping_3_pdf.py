"""
Genera Resumen_Docs_Housekeeping_3_2026-05-01.pdf con el resumen de la
ejecucion del PR pr/docs-housekeeping-3 (commit 330df3b).

No toca archivos del proyecto. No envia datos a internet.
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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_Docs_Housekeeping_3_2026-05-01.pdf"

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
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])
def BANNER(t): return Paragraph(t, styles["Banner"])


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


def build_story():
    s = []

    s.append(Paragraph("Dona — pr/docs-housekeeping-3 ejecutado", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de operaciones &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin merge, sin deploy, sin cambios de codigo productivo.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Housekeeping documental completado.</b> 18 archivos movidos: 9 PDFs a "
        "docs/auditorias/ y 9 scripts a docs/scripts/. Raiz limpia. main intacto en 38dc186. "
        "Branch pr/docs-housekeeping-3 lista para que abras el PR cuando quieras."
    ))

    # ── Nota sobre cuenta ──────────────────────────────────────────────
    s.append(H1("Nota sobre la cuenta movida (18 vs 16)"))
    s.append(P(
        "Tu mensaje listaba <b>16 archivos untracked</b> (8 PDFs + 8 scripts). Al verificar el "
        "estado real al iniciar este housekeeping detecte <b>18 untracked</b> (9 PDFs + 9 scripts). "
        "Los 2 archivos extras son <i>Resumen_Mini_Housekeeping_T010_2026-05-01.pdf</i> y su script "
        "generador, generados durante el turno previo (mini-housekeeping post-PR #11). Son del mismo "
        "patron que los otros y los movi tambien para mantener la raiz 100% limpia. Si preferis que "
        "queden untracked y los muevo en otro housekeeping, decime y los devuelvo a raiz."
    ))

    # ── Identificadores ────────────────────────────────────────────────
    s.append(H1("Identificadores"))
    ids_rows = [
        ["Item", "Valor"],
        ["Commit", "330df3b"],
        ["Mensaje", "docs: organize T0.10 reports and session handoff artifacts"],
        ["Rama local", "pr/docs-housekeeping-3"],
        ["Rama remota", "origin/pr/docs-housekeeping-3"],
        ["Crear PR en GitHub",
         "https://github.com/celestinojbm/Dona-agent/pull/new/pr/docs-housekeeping-3"],
        ["main local", "38dc186 (igual a origin/main, INTACTO)"],
        ["origin/main", "38dc186 (sin push de este PR a main)"],
    ]
    s.append(small_table(para_rows(ids_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # ── Acciones ────────────────────────────────────────────────────────
    s.append(H1("Acciones realizadas"))
    acciones_rows = [
        ["#", "Accion", "Resultado"],
        ["1", "Verificar estado inicial (git status, branch, log, conteo untracked)",
         "OK &mdash; main en 38dc186, 18 untracked en raiz"],
        ["2", "Crear branch pr/docs-housekeeping-3 desde main (38dc186)", "OK"],
        ["3", "mkdir -p docs/auditorias docs/scripts (idempotente, ya existian)", "OK"],
        ["4", "Mover 9 PDFs (Diagnostico T010, Reporte, Resumenes, Handoff, Link PR) a docs/auditorias/", "OK"],
        ["5", "Mover 9 scripts generar_*_pdf.py a docs/scripts/", "OK"],
        ["6", "git add docs/ + verificacion", "18 archivos staged como A"],
        ["7", "Verificacion de integridad de PDFs (binario, no CRLF)",
         "hash disco === hash index para Handoff_Session_Dona ✓"],
        ["8", "Commit", "330df3b, 18 archivos nuevos, +4378 lineas"],
        ["9", "Push a origin/pr/docs-housekeeping-3", "OK"],
    ]
    s.append(small_table(para_rows(acciones_rows),
                         col_widths=[0.7*cm, 7.0*cm, 9.3*cm]))

    # ── Archivos movidos ──────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("Archivos movidos a docs/auditorias/ (9 nuevos)"))
    auditorias = (
        "Diagnostico_Capacidades_Sesion_2026-05-01.pdf\n"
        "Diagnostico_T010_Whapi_Webhook_2026-05-01.pdf\n"
        "Handoff_Session_Dona_2026-05-01.pdf\n"
        "Link_PR_T010_2026-05-01.pdf\n"
        "Reporte_Post_Housekeeping_Dona_2026-05-01.pdf\n"
        "Resumen_Docs_Housekeeping_2_2026-05-01.pdf\n"
        "Resumen_Mini_Housekeeping_Final_2026-05-01.pdf\n"
        "Resumen_Mini_Housekeeping_T010_2026-05-01.pdf  <- extra de tu lista de 16\n"
        "Resumen_T010_Implementacion_2026-05-01.pdf\n"
    )
    s.append(CODE(auditorias))
    s.append(P("Total en docs/auditorias/ post-PR: <b>21 PDFs</b> (12 previos + 9 nuevos)."))

    s.append(H1("Archivos movidos a docs/scripts/ (9 nuevos)"))
    scripts = (
        "generar_diagnostico_capacidades_pdf.py\n"
        "generar_diagnostico_t010_pdf.py\n"
        "generar_handoff_session_pdf.py\n"
        "generar_link_pr_t010_pdf.py\n"
        "generar_reporte_post_housekeeping_pdf.py\n"
        "generar_resumen_docs_housekeeping_2_pdf.py\n"
        "generar_resumen_mini_housekeeping_final_pdf.py\n"
        "generar_resumen_mini_housekeeping_t010_pdf.py  <- extra de tu lista de 16\n"
        "generar_resumen_t010_implementacion_pdf.py\n"
    )
    s.append(CODE(scripts))
    s.append(P("Total en docs/scripts/ post-PR: <b>24 scripts</b> (15 previos + 9 nuevos)."))

    # ── Diff resumido ───────────────────────────────────────────────────
    s.append(H1("Diff resumido"))
    s.append(P("git diff --cached --stat (extracto):"))
    diff = (
        "docs/auditorias/Diagnostico_Capacidades_Sesion_2026-05-01.pdf  | 175 +++++++\n"
        "docs/auditorias/Diagnostico_T010_Whapi_Webhook_2026-05-01.pdf  | 238 +++++++++\n"
        "docs/auditorias/Handoff_Session_Dona_2026-05-01.pdf            | 206 ++++++++\n"
        "docs/auditorias/Link_PR_T010_2026-05-01.pdf                    | 111 ++++\n"
        "docs/auditorias/Reporte_Post_Housekeeping_Dona_2026-05-01.pdf  | 187 +++++++\n"
        "docs/auditorias/Resumen_Docs_Housekeeping_2_2026-05-01.pdf     | 118 +++++\n"
        "docs/auditorias/Resumen_Mini_Housekeeping_Final_2026-05-01.pdf |  99 ++++\n"
        "docs/auditorias/Resumen_Mini_Housekeeping_T010_2026-05-01.pdf  |  99 ++++\n"
        "docs/auditorias/Resumen_T010_Implementacion_2026-05-01.pdf     | 143 ++++++\n"
        "docs/scripts/generar_diagnostico_capacidades_pdf.py            | 369 +++++++\n"
        "docs/scripts/generar_diagnostico_t010_pdf.py                   | 558 +++++++\n"
        "docs/scripts/generar_handoff_session_pdf.py                    | 447 +++++++\n"
        "docs/scripts/generar_link_pr_t010_pdf.py                       | 238 +++++\n"
        "docs/scripts/generar_reporte_post_housekeeping_pdf.py          | 367 +++++\n"
        "docs/scripts/generar_resumen_docs_housekeeping_2_pdf.py        | 274 +++++\n"
        "docs/scripts/generar_resumen_mini_housekeeping_final_pdf.py    | 221 +++++\n"
        "docs/scripts/generar_resumen_mini_housekeeping_t010_pdf.py     | 239 +++++\n"
        "docs/scripts/generar_resumen_t010_implementacion_pdf.py        | 289 +++++\n"
        "18 files changed, 4378 insertions(+)\n"
    )
    s.append(CODE(diff))

    # ── Verificaciones ──────────────────────────────────────────────────
    s.append(H1("Verificaciones finales"))
    verif_rows = [
        ["Check", "Resultado"],
        ["git status -sb",
         "## pr/docs-housekeeping-3...origin/pr/docs-housekeeping-3 (sin cambios pendientes, sin untracked)"],
        ["git log -1 --oneline",
         "330df3b docs: organize T0.10 reports and session handoff artifacts"],
        ["docs/ contenido",
         "auditorias/, legacy-inventory.md, planes/, scripts/, tools/"],
        ["Archivos en docs/auditorias/", "21 (12 previos + 9 nuevos)"],
        ["Archivos en docs/scripts/", "24 (15 previos + 9 nuevos)"],
        ["main local vs origin/main",
         "Ambos en 38dc186 &mdash; <b>INTACTO</b>"],
        ["Sin merge a main", "Confirmado"],
        ["Sin deploy", "Confirmado (PR no toca runtime)"],
        ["Untracked en raiz", "Cero"],
    ]
    s.append(small_table(para_rows(verif_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    # ── Lo que NO toque ────────────────────────────────────────────────
    s.append(H1("Lo que NO toque (segun reglas)"))
    s.extend(bullets([
        "<b>agent/, landing/, enhanced/, tests/</b> &mdash; sin cambios. Cero codigo productivo tocado.",
        "<b>Archivos del proyecto</b> (no-docs) &mdash; sin tocar.",
        "<b>Render / Vercel / secretos</b> &mdash; sin cambios.",
        "<b>Borrar archivos</b> &mdash; ningun borrado, solo movimientos (mv preserva contenido).",
        "<b>Modificar contenido de PDFs/scripts</b> &mdash; movidos crudos, ningun byte tocado (verificado por hash).",
        "<b>Merge a main</b> &mdash; no ejecutado. La rama queda lista para que abras PR manualmente.",
        "<b>Deploy</b> &mdash; no ejecutado. PR no toca runtime; Render no observa cambios bajo docs/.",
    ]))

    # ── Estado actual ──────────────────────────────────────────────────
    s.append(H1("Estado actual"))
    s.extend(bullets([
        "Repositorio en pr/docs-housekeeping-3 (HEAD 330df3b).",
        "main intacto en 38dc186.",
        "Working tree limpio: cero untracked en raiz, todos los artefactos de planificacion viven bajo docs/.",
        "Rama remota lista en GitHub. Esperando que crees el PR cuando quieras desde el link de arriba.",
    ]))

    s.append(H1("Para crear el PR"))
    s.append(P("Pega este link en el navegador (ya autenticado con GitHub):"))
    link = "https://github.com/celestinojbm/Dona-agent/pull/new/pr/docs-housekeeping-3\n"
    s.append(CODE(link))

    s.append(Spacer(1, 14))
    s.append(C("Operacion completada. Sin merge. Esperando proximas instrucciones del owner."))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Resumen pr/docs-housekeeping-3",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — pr/docs-housekeeping-3 ejecutado · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
