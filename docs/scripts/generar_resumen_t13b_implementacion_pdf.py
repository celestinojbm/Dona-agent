"""
Genera Resumen_T13B_Implementacion_2026-05-02.pdf con el resumen del PR
T1.3.B helper creditos_de_plan + env vars STRIPE_CREDITOS_*
(commit e4e39f1, rama pr/t1.3.b-creditos-de-plan-helper).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_T13B_Implementacion_2026-05-02.pdf"

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

    s.append(Paragraph("T1.3.B — Helper creditos_de_plan + env vars", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de implementacion &nbsp;·&nbsp; Fecha: 2026-05-02 &nbsp;·&nbsp; "
        "Sin merge, sin deploy. &nbsp;·&nbsp; Rama lista para revision.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Implementado y testeado.</b> 3 archivos modificados, 488 tests verde, "
        "branch <i>pr/t1.3.b-creditos-de-plan-helper</i> en GitHub. "
        "Segundo paso del bloque T1.3. Helper que mapea plan_codigo Stripe a creditos mensuales "
        "via env vars, con fail-explicit en produccion y defaults conservadores en dev/test. "
        "Cero impacto operativo: nadie invoca el helper todavia (T1.3.C lo hara)."
    ))

    # ── Identificadores ────────────────────────────────────────────────
    s.append(H1("Identificadores"))
    ids_rows = [
        ["Item", "Valor"],
        ["Commit", "e4e39f1"],
        ["Mensaje",
         "feat(billing): helper creditos_de_plan + env vars STRIPE_CREDITOS_* (T1.3.B)"],
        ["Rama local", "pr/t1.3.b-creditos-de-plan-helper"],
        ["Rama remota", "origin/pr/t1.3.b-creditos-de-plan-helper"],
        ["Crear PR en GitHub",
         "https://github.com/celestinojbm/Dona-agent/pull/new/pr/t1.3.b-creditos-de-plan-helper"],
        ["main local", "d397b8f (igual a origin/main, INTACTO)"],
        ["origin/main", "d397b8f (sin push de este PR a main)"],
    ]
    s.append(small_table(para_rows(ids_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # Nota T1.3.A pendiente
    s.append(H1("Nota: T1.3.A sigue pendiente de merge"))
    s.append(P(
        "Sin gh CLI no puedo mergear programaticamente sin violar 'no push a main'. "
        "El PR T1.3.A queda en remoto pendiente de tu click en GitHub."
    ))
    s.append(P("<b>Link prearmado para crear el PR T1.3.A:</b>"))
    s.append(CODE(
        "https://github.com/celestinojbm/Dona-agent/compare/main...pr/t1.3.a-suscripcion-stripe-modelos?quick_pull=1"
    ))
    s.append(P(
        "<b>Importante:</b> T1.3.B parte de main directo (no de T1.3.A). El helper creditos_de_plan no "
        "necesita los modelos &mdash; solo lee env vars. Por eso ambos PRs son independientes y pueden "
        "mergearse en cualquier orden."
    ))

    # ── Archivos cambiados ─────────────────────────────────────────────
    s.append(H1("Archivos cambiados"))
    arch_rows = [
        ["Archivo", "Tipo", "Lineas"],
        ["agent/billing.py", "modificado",
         "+92 (constantes _CREDITOS_DEFAULT_DEV, _ENV_VAR_POR_PLAN + funcion creditos_de_plan)"],
        [".env.example", "modificado",
         "+17 (bloque documental para STRIPE_CREDITOS_PREMIUM y STRIPE_CREDITOS_PRO)"],
        ["tests/test_creditos_de_plan.py", "nuevo",
         "+165 (20 tests)"],
    ]
    s.append(small_table(para_rows(arch_rows),
                         col_widths=[5.5*cm, 2.5*cm, 9.0*cm]))
    s.append(P("<b>Total:</b> 3 archivos, +274 lineas, 0 deleciones."))

    # ── Comportamiento implementado ────────────────────────────────────
    s.append(H1("Comportamiento implementado"))
    comp_rows = [
        ["Escenario", "Resultado"],
        ["creditos_de_plan('premium') con STRIPE_CREDITOS_PREMIUM=100",
         "retorna 100"],
        ["creditos_de_plan('pro') con STRIPE_CREDITOS_PRO=500",
         "retorna 500"],
        ["creditos_de_plan('PREMIUM') / ' Premium ' (case + trim)",
         "normaliza"],
        ["creditos_de_plan('enterprise') (plan desconocido)",
         "None + warning"],
        ["<b>Produccion + env var faltante</b>",
         "<b>None + ERROR</b> (no acredita, no usa default silencioso)"],
        ["Dev/test + env var faltante",
         "default conservador (premium=100, pro=500) + warning"],
        ["env var no entero, &le; 0, decimal, whitespace",
         "None + ERROR"],
        ["creditos_de_plan(None) o ''",
         "None (sin crash)"],
    ]
    s.append(small_table(para_rows(comp_rows),
                         col_widths=[7.5*cm, 9.5*cm]))

    # ── Tests ──────────────────────────────────────────────────────────
    s.append(H1("Tests ejecutados y resultado"))
    tests_rows = [
        ["Suite", "Resultado"],
        ["pytest tests/test_creditos_de_plan.py -x -q",
         "<b>20 passed</b> en 0.05 s"],
        ["pytest tests/test_billing.py tests/test_billing_commands.py -x -q",
         "<b>36 passed</b> en 27 s (no-regresion)"],
        ["pytest -q (suite completa)",
         "<b>488 passed</b> en 111 s, exit 0"],
    ]
    s.append(small_table(para_rows(tests_rows),
                         col_widths=[7.5*cm, 9.5*cm]))
    s.append(P(
        "Sin regresiones. Suite paso de 468 (post-T0.10) a <b>488</b> &mdash; +20 nuevos del PR."
    ))

    s.append(H2("Tests por categoria (5 clases)"))
    s.extend(bullets([
        "<b>TestEnvSeteada</b> (4): premium/pro con env, valor configurable, case+trim.",
        "<b>TestPlanDesconocido</b> (3): vacio, None, planes random.",
        "<b>TestProduccionSinEnv</b> (4): premium/pro sin env, whitespace, log ERROR visible.",
        "<b>TestDevSinEnv</b> (4): defaults, environment=test, log WARNING (no ERROR).",
        "<b>TestEnvValorInvalido</b> (5): no-int, negativo, cero, decimal, log ERROR.",
    ]))

    # ── Estado git ─────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("Estado git"))
    git_rows = [
        ["Item", "Valor"],
        ["main local", "d397b8f (igual a origin/main, <b>INTACTO</b>)"],
        ["HEAD actual",
         "e4e39f1 en pr/t1.3.b-creditos-de-plan-helper"],
        ["Ramas pr/* en remoto",
         "T1.3.A + T1.3.B (ambas pendientes de merge)"],
    ]
    s.append(small_table(para_rows(git_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # ── Confirmaciones ─────────────────────────────────────────────────
    s.append(H1("Confirmaciones de no-accion"))
    s.extend(bullets([
        "Sin merge a main (T1.3.A queda esperando que vos cliquees el merge en GitHub).",
        "Sin push a main.",
        "Sin deploy.",
        "Sin tocar Stripe Dashboard.",
        "Sin tocar variables de entorno reales (en Render/Vercel).",
        "Sin endpoint /internal/stripe-event (T1.3.D).",
        "Sin modificar landing.",
        "Sin acreditar creditos (eso lo hace T1.3.C usando este helper).",
        "<b>Cero secretos</b> en codigo, comentarios o tests.",
    ]))

    # ── Proximo paso ───────────────────────────────────────────────────
    s.append(H1("Proximo paso recomendado"))
    s.extend(bullets([
        "<b>Mergear T1.3.A</b> desde GitHub (cero impacto &mdash; solo tablas vacias).",
        "<b>Mergear T1.3.B</b> desde GitHub. <b>Cero impacto en produccion</b> mientras STRIPE_CREDITOS_PREMIUM y STRIPE_CREDITOS_PRO no esten setadas &mdash; el helper existe pero nadie lo invoca todavia.",
        "Cuando estes listo, <b>setear las dos env vars en Render</b> (STRIPE_CREDITOS_PREMIUM=100, STRIPE_CREDITOS_PRO=500) &mdash; el helper las leera cuando T1.3.C lo invoque.",
        "Despues: arrancar <b>T1.3.C</b> (procesar_evento_suscripcion con los 4 handlers + idempotencia).",
    ]))

    s.append(Spacer(1, 14))
    s.append(C(
        "Branch lista para merge. La decision queda en manos del owner."
    ))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Resumen T1.3.B implementacion",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T1.3.B Resumen de implementacion · 2026-05-02")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
