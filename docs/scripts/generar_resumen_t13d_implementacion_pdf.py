"""
Genera Resumen_T13D_Implementacion_2026-05-02.pdf con el resumen del PR
T1.3.D endpoint /internal/stripe-event con HMAC
(commit 4f5c9ef, rama pr/t1.3.d-internal-stripe-event).

No toca archivos del proyecto. No envia datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_T13D_Implementacion_2026-05-02.pdf"

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

story.append(Paragraph("T1.3.D — endpoint /internal/stripe-event con HMAC", styles["TitleBig"]))
story.append(Paragraph(
    "Implementación · Rama <b>pr/t1.3.d-internal-stripe-event</b> · "
    "Commit <b>4f5c9ef</b> · 2026-05-02",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheado a GitHub. Tests verdes "
    "(26 nuevos · 554 totales). <b>NO mergeado a main.</b> "
    "Owner aprueba via PR en GitHub UI."
))

story.append(WARN(
    "<b>Antes de mergear:</b> generar valor de INTERNAL_BRIDGE_SECRET "
    "y configurar la <b>misma</b> variable en Vercel (landing) y Render "
    "(backend). Sin esto, el deploy a producción aborta por fail-fast "
    "al import de agent.main."
))

# ── 1. Archivos cambiados ──────────────────────────────────────────────────

story.append(H1("1. Archivos cambiados"))
story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo", "Rol"],
    ["agent/main.py", "+131 / -0", "M", "fail-fast + helper + endpoint"],
    [".env.example", "+21 / -0", "M", "doc INTERNAL_BRIDGE_SECRET"],
    ["tests/test_main_internal_stripe.py", "+558 / -0", "A", "26 tests"],
    ["", "", "", ""],
    ["TOTAL T1.3.D", "+710 / -0", "3 archivos", ""],
], col_widths=[2.4*inch, 1.0*inch, 0.6*inch, 2.5*inch]))

# ── 2. Resumen del diff ────────────────────────────────────────────────────

story.append(H1("2. Resumen del diff"))

story.append(H2("agent/main.py — 3 bloques nuevos"))

story.append(P("<b>(a) Imports añadidos:</b>"))
story.append(CODE("import json\nimport hashlib"))

story.append(P("<b>(b) Fail-fast al import (línea ~38):</b>"))
story.append(CODE(
    "def _check_internal_bridge_secret() -> None:\n"
    "    env = os.getenv(\"ENVIRONMENT\", \"development\").lower()\n"
    "    if env == \"production\" and not os.getenv(\n"
    "        \"INTERNAL_BRIDGE_SECRET\", \"\").strip():\n"
    "        raise RuntimeError(...)\n"
    "\n"
    "_check_internal_bridge_secret()  # se ejecuta al import"
))

story.append(P("<b>(c) Helper HMAC (compare_digest):</b>"))
story.append(CODE(
    "def _verificar_firma_interna(body: bytes, sig_header: str) -> bool:\n"
    "    secret = os.getenv(\"INTERNAL_BRIDGE_SECRET\", \"\").strip()\n"
    "    if not secret or not sig_header:\n"
    "        return False\n"
    "    esperado = hmac.new(\n"
    "        secret.encode(\"utf-8\"), body, hashlib.sha256\n"
    "    ).hexdigest()\n"
    "    return hmac.compare_digest(esperado, sig_header.strip())"
))

story.append(P("<b>(d) Endpoint POST /internal/stripe-event:</b>"))
story.append(CODE(
    "@app.post(\"/internal/stripe-event\")\n"
    "async def internal_stripe_event(request: Request):\n"
    "    body = await request.body()\n"
    "    sig = request.headers.get(\"X-Internal-Signature\", \"\")\n"
    "    if not _verificar_firma_interna(body, sig):\n"
    "        raise HTTPException(401, \"signature_invalid\")\n"
    "    try:\n"
    "        evento = json.loads(body.decode(\"utf-8\"))\n"
    "    except (UnicodeDecodeError, json.JSONDecodeError):\n"
    "        raise HTTPException(400, \"json_invalid\")\n"
    "    if not isinstance(evento, dict):\n"
    "        raise HTTPException(400, \"json_not_object\")\n"
    "    try:\n"
    "        resultado = await procesar_evento_suscripcion(evento)\n"
    "    except Exception:\n"
    "        raise HTTPException(500, \"processing_error\")\n"
    "    # Solo race invoice→checkout amerita 500 retryable.\n"
    "    if not resultado.get(\"handled\"):\n"
    "        if (evento_tipo == \"invoice.payment_succeeded\" and\n"
    "            razon == \"subscription_no_persistida\"):\n"
    "            raise HTTPException(500, \"...retry\")\n"
    "    return {\"status\": \"ok\", **resultado}"
))

story.append(P("<b>NO modificado:</b> /webhook/stripe legacy queda intacto."))

# ── 3. Clasificación HTTP ──────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Clasificación de respuestas HTTP"))
story.append(P(
    "Decisión de diseño: <b>la mayoría de los handled=False son 200, "
    "no 500</b>. Solo casos genuinamente retryable devuelven 500 — "
    "evita que Stripe (vía bridge) reentregue eventos rotos eternamente."
))

story.append(make_table([
    ["Status", "Cuándo", "Razón"],
    ["200", "handled=True", "Procesado OK"],
    ["200", "duplicate_event", "Ya procesado (idempotencia general)"],
    ["200", "invoice_ya_acreditado", "Ya acreditado (idempotencia invoice)"],
    ["200", "missing_telefono", "Evento incompleto, retry no ayuda"],
    ["200", "missing_event_id", "Evento incompleto, retry no ayuda"],
    ["200", "missing_subscription_id (checkout)", "Evento incompleto"],
    ["200", "missing_invoice_id", "Evento incompleto"],
    ["200", "plan_invalido", "Config faltante; retry tras arreglar"],
    ["200", "tipo no soportado", "Fuera de scope"],
    ["200", "checkout mode=payment", "Lo maneja /webhook/stripe legacy"],
    ["200", "subscription_no_persistida (updated/deleted)",
     "No es race; sub realmente no existe"],
    ["500", "subscription_no_persistida (invoice)",
     "Race con checkout; pedir retry"],
    ["500", "Excepción inesperada", "Bug; retry da una segunda chance"],
    ["400", "JSON inválido (tras HMAC válido)",
     "Bug en bridge; alertar"],
    ["400", "JSON no objeto", "Bug en bridge; alertar"],
    ["401", "Sin firma o firma inválida",
     "Atacante o secret desincronizado"],
], col_widths=[0.7*inch, 2.7*inch, 3.0*inch]))

# ── 4. Tests ───────────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Tests ejecutados"))

story.append(P(
    "Archivo nuevo: <b>tests/test_main_internal_stripe.py</b> (558 líneas, "
    "26 tests). Patrón: TestClient de FastAPI con monkeypatch.setenv para "
    "inyectar INTERNAL_BRIDGE_SECRET=\"test-secret-not-real\" y un DB "
    "SQLite en tmp_path."
))

story.append(make_table([
    ["Clase de tests", "N°", "Cubre"],
    ["TestFirmaInvalida", "5",
     "Sin header, header vacío, firma inválida, firma de otro secret, "
     "body modificado tras firmar"],
    ["TestFirmaValidaProcesa", "2",
     "Checkout válido crea suscripción; invoice acredita via endpoint"],
    ["TestJsonInvalido", "3",
     "Body no JSON, body es array no objeto, body vacío"],
    ["TestDuplicateEvent", "1",
     "Mismo event.id reentregado → 200 no 500"],
    ["TestInvoiceYaAcreditado", "1",
     "Mismo invoice_id distinto event_id → 200 no 500"],
    ["TestRaceInvoiceCheckout", "3",
     "Invoice sin sub → 500; updated/deleted sin sub → 200 (no race)"],
    ["TestNoRetryable", "5",
     "missing_telefono, plan_invalido, missing_event_id, "
     "tipo no soportado, mode=payment"],
    ["TestFailFastProduccion", "4",
     "Production sin secret → RuntimeError; whitespace → falla; "
     "con secret no falla; dev sin secret no falla pero rechaza 401"],
    ["TestLegacyWebhookIntacto", "2",
     "/webhook/stripe sigue registrado y la función no cambió"],
], col_widths=[2.2*inch, 0.5*inch, 3.8*inch]))

story.append(H2("Resultado"))
story.append(CODE(
    "$ pytest tests/test_main_internal_stripe.py -x --tb=short\n"
    "============================= 26 passed in 27.42s =============================\n"
    "\n"
    "$ pytest --tb=short -q\n"
    "554 passed in 171.09s (0:02:51)\n"
    "\n"
    "Baseline pre-T1.3.D: 528 tests\n"
    "Δ = +26 tests T1.3.D"
))

# ── 5. Blockers ────────────────────────────────────────────────────────────

story.append(H1("5. Blockers"))
story.append(P(
    "<b>Ninguno.</b> Tests verdes, branch pusheado a remote. Listo para "
    "PR review en GitHub."
))

# ── 6. Próximos pasos ──────────────────────────────────────────────────────

story.append(H1("6. Próximos pasos para el owner"))

story.append(H2("a) Generar INTERNAL_BRIDGE_SECRET"))
story.append(CODE(
    "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
))

story.append(H2("b) Configurar el MISMO valor en dos lugares"))
story.extend(bullets([
    "<b>Render</b> (backend): variable de entorno <i>INTERNAL_BRIDGE_SECRET</i>.",
    "<b>Vercel</b> (landing): variable de entorno <i>INTERNAL_BRIDGE_SECRET</i>.",
    "Ambos deben ser idénticos byte a byte (sin espacios, sin saltos).",
    "Si los valores difieren, el endpoint rechaza con 401 todos los eventos.",
]))

story.append(H2("c) Mergear T1.3.D"))
story.extend(bullets([
    "PR T1.3.D: https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/t1.3.d-internal-stripe-event",
    "El endpoint queda <b>desplegado pero sin tráfico</b> hasta T1.3.E.",
    "Stripe Dashboard sigue apuntando a la landing.",
]))

story.append(H2("d) Continuar con T1.3.E"))
story.append(P(
    "T1.3.E = bridge en <b>landing/app/api/webhook/route.ts</b>: tras "
    "verificar la firma de Stripe, computa HMAC-SHA256 sobre el body "
    "crudo con INTERNAL_BRIDGE_SECRET y POSTea a "
    "<i>{BACKEND_URL}/internal/stripe-event</i>. Si el backend devuelve "
    "500, devuelve 500 a Stripe para que reintente. Si devuelve 200, "
    "responde 200 a Stripe."
))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-02 · "
    "Repo: Dona-agent · Branch: pr/t1.3.d-internal-stripe-event · "
    "HEAD: 4f5c9ef"
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.3.D — endpoint /internal/stripe-event",
    author="Claude Code", subject="Resumen de implementación T1.3.D",
)
doc.build(story)
print(f"OK: {OUTPUT}")
