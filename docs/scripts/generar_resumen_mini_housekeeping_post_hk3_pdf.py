"""
Genera Resumen_Mini_Housekeeping_Post_HK3_2026-05-01.pdf con el resumen del
mini-housekeeping post-PR #12 docs-housekeeping-3.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_Mini_Housekeeping_Post_HK3_2026-05-01.pdf"

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

    s.append(Paragraph("Dona — Mini-housekeeping post-HK3 ejecutado", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de operaciones &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin deploy, sin cambios de codigo.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Mini-housekeeping completado.</b> main local sincronizado con origin/main en d397b8f. "
        "pr/docs-housekeeping-3 borrada local y remota tras el merge de PR #12. "
        "Cero ramas pr/* en el repositorio. 2 untracked nuevos en raiz (el resumen de HK3 + su script)."
    ))

    s.append(H1("Acciones realizadas"))
    acciones_rows = [
        ["#", "Accion", "Resultado"],
        ["1", "git checkout main",
         "OK &mdash; switched to main (estaba ya en sync; el pull lo confirma)"],
        ["2", "git pull --ff-only origin main",
         "OK &mdash; fast-forward al merge commit del PR #12 (d397b8f). 18 archivos integrados a main bajo docs/."],
        ["3", "git branch -d pr/docs-housekeeping-3",
         "OK &mdash; Deleted branch pr/docs-housekeeping-3 (was 330df3b). El delete con -d funciono limpio porque la rama era ancestro de origin/main (merge commit, no squash)."],
        ["4", "git fetch origin --prune",
         "OK &mdash; '[deleted] (none) -> origin/pr/docs-housekeeping-3' confirmado por GitHub al mergear con 'Delete branch' activado."],
    ]
    s.append(small_table(para_rows(acciones_rows),
                         col_widths=[0.7*cm, 6.5*cm, 9.8*cm]))

    s.append(H1("Verificaciones finales"))
    verif_rows = [
        ["Check", "Resultado"],
        ["git status -sb",
         "## main...origin/main (en sync, sin ahead/behind, 2 untracked en raiz)"],
        ["git branch", "Solo * main (cero ramas pr/* locales)"],
        ["git branch -r | grep 'origin/pr/'", "(ninguna) &mdash; cero ramas pr/* remotas"],
        ["git log -1 --oneline main",
         "d397b8f Merge pull request #12 from celestinojbm/pr/docs-housekeeping-3"],
        ["main vs origin/main", "Ambos en d397b8f &mdash; <b>IGUALES</b>"],
        ["Untracked en raiz", "2 archivos (Resumen_Docs_Housekeeping_3_*.pdf y su script)"],
    ]
    s.append(small_table(para_rows(verif_rows),
                         col_widths=[5.5*cm, 11.5*cm]))

    s.append(H1("Untracked actuales (2)"))
    s.append(P("Generados durante el housekeeping anterior, no se tocaron:"))
    untracked = (
        "Resumen_Docs_Housekeeping_3_2026-05-01.pdf\n"
        "generar_resumen_docs_housekeeping_3_pdf.py\n"
    )
    s.append(CODE(untracked))
    s.append(P(
        "Esta corrida agrega 2 mas (resumen del mini-housekeeping post-HK3 + su script). "
        "Pueden esperar al proximo housekeeping documental o moverse manualmente."
    ))

    s.append(H1("Lo que NO toque"))
    s.extend(bullets([
        "<b>Untracked existentes</b> &mdash; los 2 siguen en raiz tal cual.",
        "<b>Codigo productivo</b> &mdash; sin cambios.",
        "<b>Commits</b> &mdash; ninguno (solo checkout, pull --ff-only, branch -d, fetch --prune).",
        "<b>Deploy</b> &mdash; no ejecutado. PR #12 fue 100% documental; sync local no afecta produccion.",
        "<b>Render / Vercel / secretos</b> &mdash; sin cambios.",
    ]))

    s.append(H1("Estado actual del repo"))
    s.extend(bullets([
        "<b>main local</b> en d397b8f, igual a origin/main.",
        "<b>Cero ramas pr/*</b> en local o remoto.",
        "<b>docs/auditorias/</b>: 21 PDFs (12 historicos + 9 del PR #12).",
        "<b>docs/scripts/</b>: 24 scripts generadores.",
        "<b>2 untracked</b> en raiz (residuo de la sesion).",
        "Phase 0 (3 P0 originales) + T0.10 cerrados. PR #11 + PR #12 mergeados y limpiados.",
    ]))

    s.append(H1("Proximos pasos sugeridos"))
    s.extend(bullets([
        "<b>Verificacion operativa Stripe Dashboard</b> (Bloque 1 del Diagnostico T0.2 corregido). Sin codigo, ~5 min en el panel de Stripe. Es prerrequisito de T1.3.",
        "<b>T1.3 &mdash; Migrar billing a fuente unica backend Python</b>. PR mediano (~100-200 lineas). Cierra el gap funcional Stripe -> backend de creditos.",
        "<b>Borrar WHAPI_API_URL de Render</b> (vestigio sin uso, ya documentado).",
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
        title="Dona — Mini-housekeeping post-HK3 ejecutado",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Mini-housekeeping post-HK3 · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
