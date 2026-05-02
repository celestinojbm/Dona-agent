"""
Genera Resumen_Docs_Housekeeping_2_2026-05-01.pdf con el resumen de la
ejecucion del PR pr/docs-housekeeping-2 (commit cc96ccb).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_Docs_Housekeeping_2_2026-05-01.pdf"

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

    # Portada
    s.append(Paragraph("Dona — pr/docs-housekeeping-2 ejecutado", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de operaciones &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin merge, sin deploy, sin cambios de codigo productivo.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Housekeeping documental completado.</b> 22 archivos movidos: 11 PDFs a "
        "docs/auditorias/ y 11 scripts a docs/scripts/. Raiz limpia. main intacto en 32da747. "
        "Branch pr/docs-housekeeping-2 lista para que abras el PR cuando quieras."
    ))

    # ── Identificadores ────────────────────────────────────────────────
    s.append(H1("Identificadores"))
    ids_rows = [
        ["Item", "Valor"],
        ["Commit", "cc96ccb"],
        ["Mensaje", "docs: organize Phase 0 audits, reports and scripts"],
        ["Rama local", "pr/docs-housekeeping-2"],
        ["Rama remota", "origin/pr/docs-housekeeping-2"],
        ["Crear PR en GitHub",
         "https://github.com/celestinojbm/Dona-agent/pull/new/pr/docs-housekeeping-2"],
        ["main local", "32da747 (igual a origin/main, INTACTO)"],
        ["origin/main", "32da747 (sin push de este PR a main)"],
    ]
    s.append(small_table(para_rows(ids_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # ── Acciones ────────────────────────────────────────────────────────
    s.append(H1("Acciones realizadas"))
    acciones_rows = [
        ["#", "Accion", "Resultado"],
        ["1", "Crear rama pr/docs-housekeeping-2 desde main (32da747)", "OK"],
        ["2", "Crear docs/auditorias/ y docs/scripts/ (idempotente, ya existian)", "OK"],
        ["3", "Mover 11 PDFs (Diagnostico/Reporte/Resumen Phase 0) a docs/auditorias/", "OK"],
        ["4", "Mover 11 scripts generar_*_pdf.py a docs/scripts/", "OK"],
        ["5", "git add docs/ + verificacion", "22 archivos staged como A"],
        ["6", "Verificacion de integridad de PDFs (binario, no CRLF)", "hash disco === hash index"],
        ["7", "Commit", "cc96ccb, 22 archivos nuevos"],
        ["8", "Push a origin/pr/docs-housekeeping-2", "OK"],
    ]
    s.append(small_table(para_rows(acciones_rows),
                         col_widths=[0.7*cm, 7.0*cm, 9.3*cm]))

    # ── Archivos movidos ───────────────────────────────────────────────
    s.append(H1("Archivos movidos a docs/auditorias/ (11 nuevos)"))
    auditorias = (
        "Diagnostico_T02_Stripe_Webhook_2026-05-01.pdf\n"
        "Diagnostico_T02_Corregido_2026-05-01.pdf\n"
        "Diagnostico_T03_Meta_Webhook_2026-05-01.pdf\n"
        "Diagnostico_T04_Inbound_Webhook_2026-05-01.pdf\n"
        "Reporte_PostMerge_Dona_2026-05-01.pdf\n"
        "Reporte_Post_Phase0_Dona_2026-05-01.pdf\n"
        "Reporte_Housekeeping_Post_Phase0_Dona_2026-05-01.pdf\n"
        "Resumen_T02_Implementacion_2026-05-01.pdf\n"
        "Resumen_T03_Implementacion_2026-05-01.pdf\n"
        "Resumen_T04_Implementacion_2026-05-01.pdf\n"
        "Resumen_Housekeeping_Ramas_Ejecutado_2026-05-01.pdf\n"
    )
    s.append(CODE(auditorias))
    s.append(P("Total en docs/auditorias/ post-PR: <b>12 PDFs</b> (1 previo + 11 nuevos)."))

    s.append(H1("Archivos movidos a docs/scripts/ (11 nuevos)"))
    scripts = (
        "generar_diagnostico_t02_pdf.py\n"
        "generar_diagnostico_t02_corregido_pdf.py\n"
        "generar_diagnostico_t03_pdf.py\n"
        "generar_diagnostico_t04_pdf.py\n"
        "generar_reporte_postmerge_pdf.py\n"
        "generar_reporte_post_phase0_pdf.py\n"
        "generar_reporte_housekeeping_post_phase0_pdf.py\n"
        "generar_resumen_t02_implementacion_pdf.py\n"
        "generar_resumen_t03_implementacion_pdf.py\n"
        "generar_resumen_t04_implementacion_pdf.py\n"
        "generar_resumen_housekeeping_ejecutado_pdf.py\n"
    )
    s.append(CODE(scripts))
    s.append(P("Total en docs/scripts/ post-PR: <b>15 scripts</b> (4 previos + 11 nuevos)."))

    # ── Verificaciones ──────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("Verificaciones finales"))
    verif_rows = [
        ["Check", "Resultado"],
        ["git status -sb",
         "## pr/docs-housekeeping-2...origin/pr/docs-housekeeping-2 (sin cambios pendientes, sin untracked)"],
        ["git log -1 --oneline",
         "cc96ccb docs: organize Phase 0 audits, reports and scripts"],
        ["docs/ contenido",
         "auditorias/, legacy-inventory.md, planes/, scripts/, tools/"],
        ["Archivos en docs/auditorias/",
         "12 (1 previo + 11 nuevos)"],
        ["Archivos en docs/scripts/",
         "15 (4 previos + 11 nuevos)"],
        ["main local vs origin/main",
         "Ambos en 32da747 &mdash; <b>INTACTO</b>"],
        ["Sin merge a main", "Confirmado"],
        ["Untracked en raiz", "Cero"],
    ]
    s.append(small_table(para_rows(verif_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    # ── Lo que NO toque ────────────────────────────────────────────────
    s.append(H1("Lo que NO toque (segun reglas)"))
    s.extend(bullets([
        "<b>Codigo productivo</b> &mdash; sin cambios.",
        "<b>Archivos del proyecto</b> (no-docs) &mdash; sin tocar.",
        "<b>Render / Vercel / secretos</b> &mdash; sin cambios.",
        "<b>Borrar archivos</b> &mdash; ningun borrado, solo movimientos (mv preserva contenido).",
        "<b>Merge a main</b> &mdash; no ejecutado. La rama queda lista para que abras PR manualmente.",
        "<b>Deploy</b> &mdash; no ejecutado.",
    ]))

    # ── Estado actual ───────────────────────────────────────────────────
    s.append(H1("Estado actual"))
    s.extend(bullets([
        "Repositorio en pr/docs-housekeeping-2 (HEAD cc96ccb).",
        "main intacto en 32da747.",
        "Working tree limpio: cero untracked en raiz, todos los artefactos de planificacion viven bajo docs/.",
        "Rama remota lista en GitHub. Esperando que crees el PR cuando quieras desde el link de arriba.",
    ]))

    s.append(H1("Para crear el PR"))
    s.append(P("Pega este link en el navegador (ya autenticado con GitHub):"))
    link = "https://github.com/celestinojbm/Dona-agent/pull/new/pr/docs-housekeeping-2\n"
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
        title="Dona — Resumen pr/docs-housekeeping-2",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — pr/docs-housekeeping-2 ejecutado · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
