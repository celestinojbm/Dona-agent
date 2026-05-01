"""
Genera Resumen_Housekeeping_Ramas_Ejecutado_2026-05-01.pdf con el resumen
del housekeeping de ramas post-Phase 0 ya ejecutado.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_Housekeeping_Ramas_Ejecutado_2026-05-01.pdf"

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
    s.append(Paragraph("Dona — Housekeeping de ramas post-Phase 0", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de operaciones ejecutadas &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin deploy, sin cambios de codigo, sin docs-housekeeping-2.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Housekeeping completado.</b> 9 ramas locales + 9 ramas remotas pr/* mergeadas borradas. "
        "main local sincronizado con origin/main en 32da747. Repositorio limpio: una sola rama (main) "
        "local y la misma main remota. Cero impacto en produccion."
    ))

    # ── Acciones realizadas ────────────────────────────────────────────
    s.append(H1("Acciones realizadas"))
    acciones_rows = [
        ["#", "Accion", "Resultado"],
        ["1", "git checkout main",
         "OK &mdash; switched to main (estaba 2 commits detras de origin)"],
        ["2", "git pull --ff-only origin main",
         "OK &mdash; fast-forward de f79b069 a 32da747 (2 commits, 4 archivos, +133/-10 lineas)"],
        ["3", "Borrar 9 ramas locales pr/*",
         "OK &mdash; todas borradas con git branch -d (verificacion de mergeada paso)"],
        ["4", "Borrar 9 ramas remotas pr/*",
         "OK &mdash; todas borradas con git push origin --delete"],
        ["5", "git fetch origin --prune",
         "OK &mdash; sin output (los refs locales origin/pr/* ya estaban limpios desde el delete remoto)"],
    ]
    s.append(small_table(para_rows(acciones_rows),
                         col_widths=[0.7*cm, 5.0*cm, 11.3*cm]))

    # ── Ramas locales borradas ─────────────────────────────────────────
    s.append(H1("Ramas locales borradas (9)"))
    locales = (
        "pr/disclaimer-responsable                  was 568ab1f\n"
        "pr/docs-housekeeping                       was aceeef1\n"
        "pr/inbound-webhook-secret-obligatorio      was c76219d\n"
        "pr/legacy-inventory                        was 1282d92\n"
        "pr/log-sanitization-json                   was a5e338c\n"
        "pr/meta-webhook-firma-obligatoria          was 807a676\n"
        "pr/stripe-webhook-firma-obligatoria        was e880192\n"
        "pr/tools-docs-firefly-higgsfield           was 75a3065\n"
        "pr/voice-forward-env                       was c0b5149\n"
    )
    s.append(CODE(locales))

    # ── Ramas remotas borradas ─────────────────────────────────────────
    s.append(H1("Ramas remotas borradas (9)"))
    remotas = (
        "- [deleted]  pr/disclaimer-responsable\n"
        "- [deleted]  pr/docs-housekeeping\n"
        "- [deleted]  pr/inbound-webhook-secret-obligatorio\n"
        "- [deleted]  pr/legacy-inventory\n"
        "- [deleted]  pr/log-sanitization-json\n"
        "- [deleted]  pr/meta-webhook-firma-obligatoria\n"
        "- [deleted]  pr/stripe-webhook-firma-obligatoria\n"
        "- [deleted]  pr/tools-docs-firefly-higgsfield\n"
        "- [deleted]  pr/voice-forward-env\n"
    )
    s.append(CODE(remotas))

    # ── Verificaciones finales ─────────────────────────────────────────
    s.append(H1("Verificaciones finales"))
    verif_rows = [
        ["Check", "Resultado"],
        ["git status -sb",
         "## main...origin/main (sin ahead/behind, untracked iguales que antes)"],
        ["git branch",
         "Solo * main (cero ramas pr/* locales)"],
        ["git branch -r | grep 'origin/pr/'",
         "(ninguna) &mdash; cero ramas pr/* remotas"],
        ["git log -1 --oneline main",
         "32da747 Merge pull request #9 from celestinojbm/pr/inbound-webhook-secret-obligatorio"],
        ["main vs origin/main",
         "Ambos en 32da747 &mdash; <b>IGUALES</b>"],
    ]
    s.append(small_table(para_rows(verif_rows),
                         col_widths=[5.5*cm, 11.5*cm]))

    # ── Lo que NO toque ─────────────────────────────────────────────────
    s.append(H1("Lo que NO toque (segun reglas)"))
    s.extend(bullets([
        "<b>Archivos de codigo</b> &mdash; sin cambios.",
        "<b>Archivos untracked</b> &mdash; los 20 PDFs/scripts siguen en su lugar (esperando pr/docs-housekeeping-2).",
        "<b>Deploy</b> &mdash; no ejecutado.",
        "<b>Render / Vercel / secretos</b> &mdash; sin cambios.",
        "<b>Otros archivos del repo</b> &mdash; sin tocar.",
    ]))

    # ── Estado actual ───────────────────────────────────────────────────
    s.append(H1("Estado actual"))
    s.extend(bullets([
        "Repositorio limpio: una sola rama (main) local y la misma main remota.",
        "main en <b>32da747</b>, sincronizado con origin/main.",
        "20 archivos untracked (10 PDFs + 10 scripts de planificacion) listos para el proximo pr/docs-housekeeping-2 cuando lo autorices.",
        "Nada en produccion se vio afectado por estas operaciones.",
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
        title="Dona — Housekeeping de ramas ejecutado",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Housekeeping de ramas ejecutado · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
