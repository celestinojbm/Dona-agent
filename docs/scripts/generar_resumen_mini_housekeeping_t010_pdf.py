"""
Genera Resumen_Mini_Housekeeping_T010_2026-05-01.pdf con el resumen del
mini-housekeeping post-PR #11 (sync main + borrar pr/whapi-webhook-token-obligatorio).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_Mini_Housekeeping_T010_2026-05-01.pdf"

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

    s.append(Paragraph("Dona — Mini-housekeeping post-PR #11 ejecutado", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de operaciones &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin deploy, sin cambios de codigo, sin tocar untracked.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Mini-housekeeping completado.</b> main local sincronizado con origin/main en 38dc186. "
        "pr/whapi-webhook-token-obligatorio borrada local (su upstream remoto ya estaba [gone] tras "
        "el merge de PR #11). Cero ramas pr/* en el repositorio. 16 archivos untracked preservados "
        "en raiz."
    ))

    # Acciones
    s.append(H1("Acciones realizadas"))
    acciones_rows = [
        ["#", "Accion", "Resultado"],
        ["1", "git checkout main",
         "OK &mdash; switched to main (estaba 2 commits detras)"],
        ["2", "git pull --ff-only origin main",
         "OK &mdash; fast-forward de 49978a9 a 38dc186 (PR #11, +242 lineas en 3 archivos)"],
        ["3", "git branch -D pr/whapi-webhook-token-obligatorio",
         "OK &mdash; Deleted branch pr/whapi-webhook-token-obligatorio (was 57584d4). Se uso -D porque el upstream remoto ya estaba [gone]; la rama estaba mergeada en origin/main asi que no se perdio trabajo."],
        ["4", "git fetch origin --prune",
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
         "38dc186 Merge pull request #11 from celestinojbm/pr/whapi-webhook-token-obligatorio"],
        ["main vs origin/main", "Ambos en 38dc186 &mdash; <b>IGUALES</b>"],
        ["Untracked en raiz", "16 archivos preservados (no se tocaron)"],
    ]
    s.append(small_table(para_rows(verif_rows),
                         col_widths=[5.5*cm, 11.5*cm]))

    # Untracked preservados
    s.append(H1("Untracked preservados (16)"))
    s.append(P("Los 16 archivos untracked siguen intactos en raiz, segun la regla de no tocarlos:"))

    s.append(H2("PDFs (8)"))
    pdfs_block = (
        "Diagnostico_Capacidades_Sesion_2026-05-01.pdf\n"
        "Diagnostico_T010_Whapi_Webhook_2026-05-01.pdf\n"
        "Handoff_Session_Dona_2026-05-01.pdf\n"
        "Link_PR_T010_2026-05-01.pdf\n"
        "Reporte_Post_Housekeeping_Dona_2026-05-01.pdf\n"
        "Resumen_Docs_Housekeeping_2_2026-05-01.pdf\n"
        "Resumen_Mini_Housekeeping_Final_2026-05-01.pdf\n"
        "Resumen_T010_Implementacion_2026-05-01.pdf\n"
    )
    s.append(CODE(pdfs_block))

    s.append(H2("Scripts generadores (8)"))
    scripts_block = (
        "generar_diagnostico_capacidades_pdf.py\n"
        "generar_diagnostico_t010_pdf.py\n"
        "generar_handoff_session_pdf.py\n"
        "generar_link_pr_t010_pdf.py\n"
        "generar_reporte_post_housekeeping_pdf.py\n"
        "generar_resumen_docs_housekeeping_2_pdf.py\n"
        "generar_resumen_mini_housekeeping_final_pdf.py\n"
        "generar_resumen_t010_implementacion_pdf.py\n"
    )
    s.append(CODE(scripts_block))
    s.append(P(
        "Volumen pequeno-mediano. Pueden vivir untracked hasta el proximo housekeeping documental, "
        "o moverse a docs/auditorias/ y docs/scripts/ en un eventual pr/docs-housekeeping-3."
    ))

    # Lo que NO toque
    s.append(H1("Lo que NO toque (segun reglas)"))
    s.extend(bullets([
        "<b>Archivos untracked</b> &mdash; los 16 siguen en raiz tal cual.",
        "<b>Codigo productivo</b> &mdash; sin cambios.",
        "<b>Commits</b> &mdash; ninguno (solo checkout, pull --ff-only, branch -D, fetch --prune).",
        "<b>Deploy</b> &mdash; no ejecutado. PR #11 no toca runtime con WHATSAPP_PROVIDER=meta; sync local no afecta produccion.",
        "<b>Render / Vercel / secretos</b> &mdash; sin cambios.",
    ]))

    # Estado final
    s.append(H1("Estado actual"))
    s.extend(bullets([
        "Repositorio en main local en sync con origin/main (38dc186).",
        "Cero ramas pr/* en local o remoto.",
        "16 archivos untracked en raiz preservados (8 PDFs + 8 scripts).",
        "Phase 0 (3 P0 originales) + T0.10 cerrados y consolidados. PR #11 mergeado y limpiado.",
        "<b>Listos para los siguientes pasos:</b> verificacion operativa Stripe Dashboard -> T1.3 (gap funcional Stripe/backend de creditos). T0.10 ya cerrada.",
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
        title="Dona — Mini-housekeeping post-PR #11 ejecutado",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Mini-housekeeping post-PR #11 · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
