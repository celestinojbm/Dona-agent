"""
Genera Resumen_T13A_Implementacion_2026-05-02.pdf con el resumen del PR
T1.3.A modelos SuscripcionStripe + EventoStripeProcesado (commit 83a5cda,
rama pr/t1.3.a-suscripcion-stripe-modelos).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_T13A_Implementacion_2026-05-02.pdf"

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

    s.append(Paragraph("T1.3.A — Modelos Stripe subscriptions", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de implementacion &nbsp;·&nbsp; Fecha: 2026-05-02 &nbsp;·&nbsp; "
        "Sin merge, sin deploy. &nbsp;·&nbsp; Rama lista para revision.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Implementado y testeado.</b> 3 archivos modificados, 475 tests verde, "
        "branch <i>pr/t1.3.a-suscripcion-stripe-modelos</i> en GitHub. "
        "Primer paso del bloque T1.3 (Stripe / backend de creditos como fuente unica). "
        "Solo prepara DB/modelos &mdash; cero impacto operativo, las tablas nuevas quedan vacias "
        "hasta que T1.3.C-E las populen."
    ))

    # ── Identificadores ────────────────────────────────────────────────
    s.append(H1("Identificadores"))
    ids_rows = [
        ["Item", "Valor"],
        ["Commit", "83a5cda"],
        ["Mensaje",
         "feat(billing): modelos SuscripcionStripe y EventoStripeProcesado (T1.3.A)"],
        ["Rama local", "pr/t1.3.a-suscripcion-stripe-modelos"],
        ["Rama remota", "origin/pr/t1.3.a-suscripcion-stripe-modelos"],
        ["Crear PR en GitHub",
         "https://github.com/celestinojbm/Dona-agent/pull/new/pr/t1.3.a-suscripcion-stripe-modelos"],
        ["main local", "d397b8f (igual a origin/main, INTACTO)"],
        ["origin/main", "d397b8f (sin push de este PR a main)"],
    ]
    s.append(small_table(para_rows(ids_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # ── 1. Archivos modificados / creados ──────────────────────────────
    s.append(H1("1. Archivos modificados / creados"))
    arch_rows = [
        ["Archivo", "Tipo", "Contenido"],
        ["agent/memory.py", "<b>modificado</b>",
         "+ clases SuscripcionStripe y EventoStripeProcesado insertadas justo despues de TransaccionCredito (linea ~404), antes del bloque SESION_TIMEOUT_MINUTOS. +46 lineas."],
        ["alembic/versions/002_suscripcion_stripe.py", "<b>nuevo</b>",
         "Migracion Alembic. down_revision = '001_estado_inicial'. upgrade() crea las dos tablas + 3 indices. downgrade() reversible. 114 lineas."],
        ["tests/test_suscripcion_stripe_models.py", "<b>nuevo</b>",
         "7 tests con fixture db(tmp_path, monkeypatch) (mismo patron que tests/test_billing.py). 229 lineas."],
    ]
    s.append(small_table(para_rows(arch_rows),
                         col_widths=[5.5*cm, 1.8*cm, 9.7*cm]))
    s.append(P("<b>Total:</b> 3 archivos, +389 lineas, 0 deleciones."))

    # ── 2. Resumen del diff ────────────────────────────────────────────
    s.append(H1("2. Resumen del diff"))
    diff = (
        "agent/memory.py                            |  46 ++++++\n"
        "alembic/versions/002_suscripcion_stripe.py | 114 ++++++++++++++\n"
        "tests/test_suscripcion_stripe_models.py    | 229 +++++++++++++++++++++++++++++\n"
        "3 files changed, 389 insertions(+)\n"
    )
    s.append(CODE(diff))

    s.append(H2("SuscripcionStripe (PK subscription_id, indices en telefono y customer_id)"))
    s.extend(bullets([
        "subscription_id String(200) PK",
        "telefono String(50) index",
        "customer_id String(200) index",
        "plan_codigo String(50)",
        "price_id String(200)",
        "status String(40)",
        "creditos_mensuales Integer",
        "ultimo_invoice_acreditado String(200) default ''",
        "creado / actualizado DateTime default datetime.utcnow",
    ]))

    s.append(H2("EventoStripeProcesado (PK event_id, indice en tipo)"))
    s.extend(bullets([
        "event_id String(200) PK",
        "tipo String(80) index",
        "recibido_en DateTime default datetime.utcnow",
    ]))

    s.append(P(
        "Sigue exactamente el patron existente (Mapped[...], mapped_column(...), __tablename__ snake_case, "
        "default=datetime.utcnow, indices con index=True). <b>Cero cambios disruptivos.</b>"
    ))

    # ── 3. Tests ───────────────────────────────────────────────────────
    s.append(H1("3. Tests ejecutados y resultado"))
    tests_rows = [
        ["Suite", "Resultado"],
        ["pytest tests/test_suscripcion_stripe_models.py -x -q",
         "<b>7 passed</b> en 6.3 s"],
        ["pytest tests/test_billing.py tests/test_billing_commands.py -x -q",
         "<b>36 passed</b> en 11.5 s (verificacion de no-regresion)"],
        ["pytest -q (suite completa)",
         "<b>475 passed</b> en 40.4 s, exit 0"],
    ]
    s.append(small_table(para_rows(tests_rows),
                         col_widths=[7.5*cm, 9.5*cm]))
    s.append(P(
        "Sin regresiones. Suite paso de 468 (post-T0.10) a <b>475</b> &mdash; +7 tests netos."
    ))

    s.append(H2("Tests nuevos en TestSuscripcionStripe"))
    s.extend(bullets([
        "test_insert_y_select_basico ✓",
        "test_defaults_se_aplican (ultimo_invoice_acreditado='', creado/actualizado autopobla) ✓",
        "test_pk_subscription_id_previene_duplicados (IntegrityError) ✓",
        "test_indexes_telefono_y_customer_funcionan ✓",
    ]))

    s.append(H2("Tests nuevos en TestEventoStripeProcesado"))
    s.extend(bullets([
        "test_insert_y_select_basico ✓",
        "test_pk_event_id_previene_duplicados (base de la idempotencia, IntegrityError) ✓",
        "test_index_tipo_funciona ✓",
    ]))

    # ── 4. Estado git ──────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("4. Estado git"))
    git_rows = [
        ["Item", "Valor"],
        ["main local", "d397b8f (igual a origin/main, <b>INTACTO</b>)"],
        ["origin/main", "d397b8f (sin push de este PR a main)"],
        ["HEAD actual",
         "83a5cda en pr/t1.3.a-suscripcion-stripe-modelos"],
        ["Rama remota",
         "origin/pr/t1.3.a-suscripcion-stripe-modelos ✓"],
    ]
    s.append(small_table(para_rows(git_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # ── 5. Confirmaciones ─────────────────────────────────────────────
    s.append(H1("5. Confirmaciones de no-accion"))
    s.extend(bullets([
        "<b>Sin merge a main.</b>",
        "<b>Sin push a main.</b>",
        "<b>Sin deploy.</b>",
        "<b>Sin tocar Stripe Dashboard.</b>",
        "<b>Sin tocar variables de entorno reales.</b>",
        "<b>Sin endpoint /internal/stripe-event</b> (eso es T1.3.D).",
        "<b>Sin modificar landing.</b>",
        "<b>Sin acreditar creditos</b> (eso es T1.3.B/C/D/E).",
        "<b>Sin tocar logica existente de paquetes one-time</b> (procesar_evento_stripe, acreditar, cobrar sin cambios).",
        "<b>Cero secretos</b> en codigo, comentarios o tests.",
        "<b>Tablas vacias al deploy</b> &mdash; los modelos existen pero ningun flujo las popula todavia.",
    ]))

    # ── 6. Blockers / decisiones pendientes ───────────────────────────
    s.append(H1("6. Blockers / decisiones pendientes"))
    s.append(P(
        "<b>Ninguno bloqueante para T1.3.A.</b> Las 4 decisiones del owner (creditos por plan, "
        "comportamiento bridge, acumulacion, cancelacion) <b>ya estan confirmadas</b> y se aplicaran "
        "en los siguientes PRs:"
    ))
    s.extend(bullets([
        "<b>T1.3.B</b>: hardcodea STRIPE_CREDITOS_PREMIUM=100 y STRIPE_CREDITOS_PRO=500 como defaults en .env.example y como fallback constante.",
        "<b>T1.3.C</b>: implementa 'creditos acumulables' (no resetea saldo al renovar) y 'cancelar mantiene creditos restantes' (subscription.deleted solo cambia status, no toca saldo).",
        "<b>T1.3.E</b>: landing devuelve 500 a Stripe si bridge falla (Stripe reintenta).",
    ]))

    # ── 7. Proximo paso ──────────────────────────────────────────────
    s.append(H1("7. Proximo paso recomendado (no implemento sin OK)"))
    s.extend(bullets([
        "<b>Mergear T1.3.A</b> cuando estes listo. Cero impacto en produccion al deploy: las tablas se crean automaticamente via metadata.create_all() en el lifespan, vacias, sin codigo que las popule.",
        "<b>Verificar post-merge en Render</b>: que el deploy completa sin error y que las tablas suscripcion_stripe y evento_stripe_procesado aparecen en la DB con cero filas.",
        "<b>Decidir si arrancamos T1.3.B</b> (helper creditos_de_plan + env vars) cuando quieras.",
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
        title="Dona — Resumen T1.3.A implementacion",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T1.3.A Resumen de implementacion · 2026-05-02")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
