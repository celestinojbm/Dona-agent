"""
Genera Resumen_T13C_Implementacion_2026-05-02.pdf con el resumen del PR
T1.3.C procesar_evento_suscripcion + idempotencia
(commit 5e00393, rama pr/t1.3.c-procesar-evento-suscripcion).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_T13C_Implementacion_2026-05-02.pdf"

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
    name="WarnBanner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#7c2d12"), backColor=colors.HexColor("#fff7ed"),
    borderPadding=8, borderColor=colors.HexColor("#f97316"), borderWidth=0.6,
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
def WARN(t): return Paragraph(t, styles["WarnBanner"])


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

story.append(Paragraph("T1.3.C — procesar_evento_suscripcion + idempotencia", styles["TitleBig"]))
story.append(Paragraph(
    "Implementación · Rama <b>pr/t1.3.c-procesar-evento-suscripcion</b> · Commit <b>5e00393</b> · 2026-05-02",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheado a GitHub. Tests verdes (33 nuevos · 528 totales). "
    "<b>NO mergeado a main.</b> Owner aprueba via PR en GitHub UI."
))

story.append(WARN(
    "<b>Dependencia de orden:</b> Esta rama incluye los commits de T1.3.A "
    "(modelos) y T1.3.B (helper) además del de C. Se requiere mergear T1.3.A "
    "y T1.3.B a main <b>primero</b>; cuando eso pase, GitHub recalcula el diff "
    "del PR de C y solo mostrará los cambios netos de T1.3.C."
))

# ── Qué se implementó ──────────────────────────────────────────────────────

story.append(H1("Qué se implementó"))
story.append(P(
    "Se agregó el dispatcher <b>procesar_evento_suscripcion(evento)</b> en "
    "<b>agent/billing.py</b> que maneja los 4 tipos de evento del ciclo de "
    "vida de una suscripción Stripe en Dona, junto con 4 helpers privados "
    "(uno por tipo). El dispatcher implementa idempotencia a tres niveles."
))

story.append(H2("Función pública: procesar_evento_suscripcion"))
story.append(CODE(
    "async def procesar_evento_suscripcion(evento: dict) -> dict\n"
    "    Maneja:\n"
    "      checkout.session.completed (mode=subscription)\n"
    "      invoice.payment_succeeded\n"
    "      customer.subscription.updated\n"
    "      customer.subscription.deleted\n"
    "    Idempotencia general por evento.id antes de despachar.\n"
    "    Retorna dict {handled: bool, ...contexto}."
))

story.append(H2("Helpers privados"))
story.extend(bullets([
    "<b>_procesar_checkout_subscription(data)</b>: crea o actualiza fila "
    "SuscripcionStripe. <b>NO acredita</b> — espera invoice.payment_succeeded "
    "para evitar regalar créditos si el cobro nunca se concreta.",
    "<b>_procesar_invoice_payment_succeeded(data)</b>: acredita "
    "<i>creditos_mensuales</i> al telefono de la suscripción. "
    "Idempotente por <i>ultimo_invoice_acreditado</i> y por "
    "<i>TransaccionCredito.stripe_session_id</i>.",
    "<b>_procesar_subscription_updated(data)</b>: actualiza status / "
    "price_id / plan. Si cambia el plan_codigo, recalcula "
    "<i>creditos_mensuales</i>. NO toca saldo.",
    "<b>_procesar_subscription_deleted(data)</b>: marca status='canceled'. "
    "PRESERVA el saldo del usuario (decisión owner).",
]))

# ── Decisiones owner reflejadas ────────────────────────────────────────────

story.append(H1("Decisiones owner reflejadas en código"))
story.append(make_table([
    ["Decisión", "Implementación"],
    ["Premium=100, Pro=500", "Tomado de creditos_de_plan() (T1.3.B)"],
    ["Renovaciones acumulables",
     "acreditar() suma al saldo, no resetea"],
    ["Checkout no acredita",
     "Solo crea/actualiza fila, espera invoice"],
    ["Cancelar preserva saldo",
     "subscription.deleted no toca SaldoCreditos"],
    ["Upgrade/downgrade aplica al próximo periodo",
     "subscription.updated no toca saldo"],
    ["Eventos no manejados se reintentan",
     "Solo marcamos handled=True en EventoStripeProcesado"],
], col_widths=[2.5*inch, 4.0*inch]))

# ── Idempotencia ───────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("Idempotencia: 3 niveles de defensa"))
story.append(P(
    "Stripe reentrega webhooks tras cualquier respuesta no-2xx. Tres llaves "
    "diferentes nos protegen contra distintos modos de duplicación:"
))

story.append(make_table([
    ["Nivel", "Llave", "Tabla", "Cuándo aplica"],
    ["1", "event.id", "EventoStripeProcesado",
     "Cualquier evento ya procesado"],
    ["2", "invoice.id", "SuscripcionStripe.ultimo_invoice_acreditado",
     "Solo invoices (event_id distinto, mismo invoice)"],
    ["3", "stripe_session_id (=invoice_id)", "TransaccionCredito",
     "Última red de seguridad dentro de acreditar()"],
], col_widths=[0.4*inch, 1.7*inch, 2.4*inch, 2.0*inch]))

story.append(H2("Política: solo marcamos eventos exitosos"))
story.append(P(
    "Si un evento falla por config faltante (plan desconocido, env sin "
    "configurar, telefono ausente), <b>no</b> escribimos en EventoStripeProcesado. "
    "Razón: si después arreglas la config y haces 'replay' en Stripe Dashboard, "
    "el evento se vuelve a procesar y acredita correctamente. Si lo "
    "marcáramos como procesado, la corrección requeriría intervención manual."
))

# ── Tests ──────────────────────────────────────────────────────────────────

story.append(H1("Tests · 33 nuevos · 528 totales"))
story.append(P(
    "Archivo nuevo: <b>tests/test_procesar_evento_suscripcion.py</b> "
    "(641 líneas). Patrón fixture idéntico a test_billing.py: SQLite en "
    "tmp_path con monkeypatch.setenv + importlib.reload."
))

story.append(make_table([
    ["Clase de tests", "Cantidad", "Cubre"],
    ["TestCheckoutSessionCompleted", "9",
     "Crea/actualiza, no acredita aún, mode=payment ignorado, "
     "telefono fallback, plan desconocido, sin sub_id"],
    ["TestInvoicePaymentSucceeded", "8",
     "Acredita, invoice duplicado, event_id duplicado, "
     "renovaciones acumulables, race con checkout, "
     "past_due → active, canceled NO se reactiva"],
    ["TestSubscriptionUpdated", "5",
     "status/plan/price, recalc creditos_mensuales, "
     "no toca saldo, plan desconocido"],
    ["TestSubscriptionDeleted", "3",
     "Marca canceled, preserva saldo, sub_id desconocido"],
    ["TestIdempotenciaEventId", "4",
     "event.id duplicado skip, no-handled no se marca, "
     "handled sí se marca, sin id rechaza"],
    ["TestTipoNoSoportado", "2",
     "tipo random no revienta, payment_failed (T1.3.C scope)"],
    ["TestLegacyOneTimeIntacto", "1",
     "procesar_evento_stripe legacy paquetes one-time sigue OK"],
], col_widths=[2.0*inch, 0.7*inch, 3.8*inch]))

story.append(H2("Resultado"))
story.append(CODE(
    "$ pytest --tb=short -q\n"
    "...\n"
    "528 passed, 5 warnings in 152.05s (0:02:32)\n"
    "\n"
    "Baseline post-T1.3.B: 488 tests\n"
    "Δ = +40 tests (33 T1.3.C + 7 T1.3.A reactivados por cherry-pick)"
))

# ── Archivos modificados ───────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("Archivos modificados"))
story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo"],
    ["agent/billing.py", "+406 / -0", "M"],
    ["tests/test_procesar_evento_suscripcion.py", "+641 / -0", "A"],
    ["", "", ""],
    ["TOTAL T1.3.C", "+1047 / -0", "2 archivos"],
], col_widths=[3.5*inch, 1.5*inch, 1.5*inch]))

story.append(P(
    "Los archivos de T1.3.A (alembic/versions/002_suscripcion_stripe.py, "
    "agent/memory.py +46, tests/test_suscripcion_stripe_models.py) y T1.3.B "
    "(.env.example +17, tests/test_creditos_de_plan.py) figuran en commits "
    "previos del branch (cherry-picked desde sus PRs originales)."
))

# ── Próximos pasos ─────────────────────────────────────────────────────────

story.append(H1("Próximos pasos para el owner"))

story.append(H2("1. Mergear T1.3.A y T1.3.B primero (orden importa)"))
story.append(P(
    "El PR de C en GitHub mostrará un diff que incluye los 3 commits hasta "
    "que A y B estén en main. Una vez mergeados:"
))
story.extend(bullets([
    "<b>PR T1.3.A:</b> https://github.com/celestinojbm/Dona-agent/compare/main...pr/t1.3.a-suscripcion-stripe-modelos",
    "<b>PR T1.3.B:</b> https://github.com/celestinojbm/Dona-agent/compare/main...pr/t1.3.b-creditos-de-plan-helper",
]))

story.append(H2("2. Mergear T1.3.C (después de A y B)"))
story.append(P(
    "Una vez A y B estén en main, el diff del PR de C se reduce automáticamente "
    "a los 2 archivos de T1.3.C (+1047 líneas):"
))
story.extend(bullets([
    "<b>PR T1.3.C:</b> https://github.com/celestinojbm/Dona-agent/compare/main...pr/t1.3.c-procesar-evento-suscripcion",
]))

story.append(H2("3. Configurar env vars en Render (si no están)"))
story.extend(bullets([
    "<b>STRIPE_CREDITOS_PREMIUM=100</b>",
    "<b>STRIPE_CREDITOS_PRO=500</b>",
    "Sin estas, creditos_de_plan() retorna None en producción y los webhooks "
    "no acreditan (lo cual es preferible a acreditar mal).",
]))

story.append(H2("4. Continuar con T1.3.D (siguiente paso)"))
story.append(P(
    "T1.3.D = endpoint <b>/internal/stripe-event</b> con verificación HMAC. "
    "Es el que recibe los eventos del bridge y llama a "
    "procesar_evento_suscripcion. <i>No</i> se implementó en T1.3.C "
    "(scope explícito del owner)."
))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-02 · "
    "Repo: Dona-agent · Branch: pr/t1.3.c-procesar-evento-suscripcion · "
    "HEAD: 5e00393"
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.3.C — procesar_evento_suscripcion",
    author="Claude Code", subject="Resumen de implementación T1.3.C",
)
doc.build(story)
print(f"OK: {OUTPUT}")
