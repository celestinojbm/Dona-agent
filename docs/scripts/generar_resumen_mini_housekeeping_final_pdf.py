"""
Genera Resumen_Mini_Housekeeping_Final_2026-05-01.pdf con el resumen del
mini-housekeeping post-PR #10 (sync main + borrar pr/docs-housekeeping-2).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_Mini_Housekeeping_Final_2026-05-01.pdf"

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

    s.append(Paragraph("Dona — Mini-housekeeping final ejecutado", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de operaciones &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin deploy, sin cambios de codigo, sin tocar untracked.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Mini-housekeeping completado.</b> main local sincronizado con origin/main en 49978a9. "
        "pr/docs-housekeeping-2 borrada local y remota. Cero ramas pr/* en el repositorio. "
        "4 archivos untracked preservados en raiz."
    ))

    # Acciones
    s.append(H1("Acciones realizadas"))
    acciones_rows = [
        ["#", "Accion", "Resultado"],
        ["1", "git checkout main",
         "OK &mdash; switched to main (estaba 2 commits detras)"],
        ["2", "git pull --ff-only origin main",
         "OK &mdash; fast-forward de 32da747 a 49978a9 (PR #10 docs-housekeeping-2)"],
        ["3", "git branch -d pr/docs-housekeeping-2",
         "OK &mdash; Deleted branch pr/docs-housekeeping-2 (was cc96ccb)"],
        ["4", "git push origin --delete pr/docs-housekeeping-2",
         "OK &mdash; - [deleted]  pr/docs-housekeeping-2"],
        ["5", "git fetch origin --prune",
         "OK &mdash; sin output (refs locales ya estaban limpios)"],
    ]
    s.append(small_table(para_rows(acciones_rows),
                         col_widths=[0.7*cm, 6.5*cm, 9.8*cm]))

    # Verificaciones
    s.append(H1("Verificaciones finales"))
    verif_rows = [
        ["Check", "Resultado"],
        ["git status -sb", "## main...origin/main (en sync, sin ahead/behind)"],
        ["git branch", "Solo * main (cero ramas pr/* locales)"],
        ["git branch -r | grep 'origin/pr/'", "(ninguna) &mdash; cero ramas pr/* remotas"],
        ["git log -1 --oneline main",
         "49978a9 Merge pull request #10 from celestinojbm/pr/docs-housekeeping-2"],
        ["main vs origin/main", "Ambos en 49978a9 &mdash; <b>IGUALES</b>"],
        ["Untracked en raiz", "4 archivos preservados (no se tocaron)"],
    ]
    s.append(small_table(para_rows(verif_rows),
                         col_widths=[5.5*cm, 11.5*cm]))

    # Untracked preservados
    s.append(H1("Untracked preservados (4)"))
    s.append(P("Los 4 archivos untracked siguen intactos en raiz, segun la regla de no tocarlos:"))
    untracked = (
        "Reporte_Post_Housekeeping_Dona_2026-05-01.pdf\n"
        "Resumen_Docs_Housekeeping_2_2026-05-01.pdf\n"
        "generar_reporte_post_housekeeping_pdf.py\n"
        "generar_resumen_docs_housekeeping_2_pdf.py\n"
    )
    s.append(CODE(untracked))
    s.append(P(
        "Volumen pequeno. Pueden vivir untracked hasta el proximo housekeeping documental, "
        "o moverse manualmente a docs/auditorias/ y docs/scripts/."
    ))

    # Lo que NO toque
    s.append(H1("Lo que NO toque (segun reglas)"))
    s.extend(bullets([
        "<b>Archivos untracked</b> &mdash; los 4 siguen en raiz tal cual.",
        "<b>Codigo productivo</b> &mdash; sin cambios.",
        "<b>Commits</b> &mdash; ninguno (solo checkout, pull --ff-only, borrar ramas, fetch --prune).",
        "<b>Deploy</b> &mdash; no ejecutado. PR #10 no toca runtime; sync local no afecta produccion.",
        "<b>Render / Vercel / secretos</b> &mdash; sin cambios.",
    ]))

    # Estado final
    s.append(H1("Estado actual"))
    s.extend(bullets([
        "Repositorio en main local en sync con origin/main (49978a9).",
        "Cero ramas pr/* en local o remoto.",
        "4 archivos untracked en raiz preservados.",
        "Phase 0 cerrada y consolidada. PR #10 mergeado y limpiado.",
        "Listos para los siguientes pasos: verificacion operativa Stripe Dashboard -> T0.10 (Whapi) -> T1.3 (gap funcional Stripe/backend de creditos).",
    ]))

    s.append(Spacer(1, 14))
    s.append(C("Operacion completada. Esperando proximas instrucciones del owner."))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Mini-housekeeping final ejecutado",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Mini-housekeeping final · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
