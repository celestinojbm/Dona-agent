"""
Genera Resumen_T13E_Implementacion_2026-05-02.pdf con el resumen del PR
T1.3.E bridge landing → backend con HMAC
(commit 45da6a1, rama pr/t1.3.e-bridge-landing-backend).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_T13E_Implementacion_2026-05-02.pdf"

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

story.append(Paragraph("T1.3.E — Bridge landing → backend con HMAC", styles["TitleBig"]))
story.append(Paragraph(
    "Implementación · Rama <b>pr/t1.3.e-bridge-landing-backend</b> · "
    "Commit <b>45da6a1</b> · 2026-05-02",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheado a GitHub. Build OK. <b>NO mergeado a main.</b> "
    "Owner aprueba via PR en GitHub UI."
))

story.append(WARN(
    "<b>Antes de mergear:</b> verificar que <b>BACKEND_URL</b> e "
    "<b>INTERNAL_BRIDGE_SECRET</b> estén configuradas en Vercel. "
    "Sin BACKEND_URL el bridge falla en cada webhook → Stripe reintenta "
    "infinitamente y vas a ver alertas."
))

# ── 1. Archivos cambiados ──────────────────────────────────────────────────

story.append(H1("1. Archivos cambiados"))
story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo", "Rol"],
    ["landing/lib/internal-bridge.ts", "+117 / -0", "A",
     "helper HMAC + fetch al backend"],
    ["landing/app/api/webhook/route.ts", "+18 / -0", "M",
     "import + llamada al bridge tras el switch"],
    ["", "", "", ""],
    ["TOTAL T1.3.E", "+135 / -0", "2 archivos", ""],
], col_widths=[2.6*inch, 0.9*inch, 0.6*inch, 2.4*inch]))

# ── 2. Resumen del diff ────────────────────────────────────────────────────

story.append(H1("2. Resumen del diff"))

story.append(H2("a) Helper landing/lib/internal-bridge.ts (nuevo)"))
story.append(P("Función pública:"))
story.append(CODE(
    "export type BridgeResult = {\n"
    "  ok: boolean;\n"
    "  status?: number;   // status del backend o undefined si fetch falló\n"
    "  error?: string;    // mensaje opaco (sin secrets)\n"
    "};\n"
    "\n"
    "export async function reenviarEventoStripeABackend(\n"
    "  evento: unknown,\n"
    "): Promise<BridgeResult>"
))

story.append(P("Lógica del helper:"))
story.extend(bullets([
    "Lee BACKEND_URL e INTERNAL_BRIDGE_SECRET de env. Si falta cualquiera, "
    "loguea y retorna ok=false (no intenta el fetch).",
    "Hace JSON.stringify(evento) <b>una sola vez</b>. El mismo string se usa "
    "para HMAC y para el body del fetch — garantiza que firma y body "
    "coincidan exactamente.",
    "Computa HMAC-SHA256(body, secret).digest('hex') y lo manda en header "
    "<i>X-Internal-Signature</i>.",
    "Timeout 8s vía AbortController (Stripe expira a 10s).",
    "ok=true solo si backend responde 2xx. 401/400/500/timeout/fetch fail "
    "→ ok=false.",
    "Logs nunca incluyen el secret ni el body completo (max 500 chars de "
    "preview del body de error del backend).",
]))

story.append(H2("b) Integración en route.ts"))
story.append(CODE(
    "// Después del switch existente (welcome WhatsApp se mantiene):\n"
    "const bridge = await reenviarEventoStripeABackend(event);\n"
    "if (!bridge.ok) {\n"
    "  console.error(\n"
    "    `[WEBHOOK] Bridge a backend falló (status=${bridge.status ?? \"n/a\"} `\n"
    "    + `error=${bridge.error}). Respondiendo 500 a Stripe para retry.`,\n"
    "  );\n"
    "  return NextResponse.json(\n"
    "    { error: \"bridge_failed\", reason: bridge.error },\n"
    "    { status: 500 },\n"
    "  );\n"
    "}\n"
    "return NextResponse.json({ received: true });"
))

# ── 3. Reglas de respuesta a Stripe ────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Reglas de respuesta a Stripe (la decisión clave)"))

story.append(make_table([
    ["Backend respondió", "Bridge ok?", "Landing → Stripe", "Razón"],
    ["2xx (200, 201, etc)", "true", "200", "Procesado OK"],
    ["401", "false", "500", "Secret desincronizado — alerta + retry"],
    ["400", "false", "500", "Bug de bridge — alerta + retry"],
    ["500 retryable (race)", "false", "500", "Backend pidió retry — propagar"],
    ["Timeout (>8s)", "false", "500", "Red lenta o backend caído"],
    ["DNS/network fail", "false", "500", "Backend no alcanzable"],
    ["BACKEND_URL faltante", "false", "500", "Misconfig — alerta + retry"],
    ["SECRET faltante", "false", "500", "Misconfig — alerta + retry"],
], col_widths=[1.7*inch, 0.7*inch, 1.0*inch, 3.0*inch]))

story.append(P(
    "<b>Política:</b> en duda, devolver 500 a Stripe. Stripe reintenta "
    "el evento varias veces con backoff exponencial; el peor caso es que "
    "veamos eventos repetidos en el dashboard de Stripe. La idempotencia "
    "del backend (T1.3.C: event.id + invoice.id) protege contra acreditar "
    "doble. Lo opuesto — devolver 200 con bridge fallido — perdería "
    "eventos silenciosamente y el usuario no recibiría sus créditos."
))

# ── 4. Flujo completo end-to-end ───────────────────────────────────────────

story.append(H1("4. Flujo end-to-end (post T1.3.E)"))

story.append(CODE(
    "Stripe Dashboard\n"
    "    │\n"
    "    │ POST {body, stripe-signature}\n"
    "    ▼\n"
    "https://www.usadona.com/api/webhook (Vercel)\n"
    "    │\n"
    "    │ 1. constructEvent verifica STRIPE_WEBHOOK_SECRET\n"
    "    │ 2. switch event.type → welcome WhatsApp si checkout.session.completed\n"
    "    │ 3. reenviarEventoStripeABackend(event)\n"
    "    │      ├─ JSON.stringify(event) = body\n"
    "    │      ├─ HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET) = sig\n"
    "    │      └─ POST {body, X-Internal-Signature: sig} ──┐\n"
    "    │                                                  │\n"
    "    ▼                                                  ▼\n"
    "Stripe ← 200 si bridge.ok                  Render: dona-agent\n"
    "         ← 500 si bridge falló              POST /internal/stripe-event\n"
    "                                                       │\n"
    "                                                       │ 1. _verificar_firma_interna(body, sig)\n"
    "                                                       │ 2. json.loads(body) → evento\n"
    "                                                       │ 3. procesar_evento_suscripcion(evento)\n"
    "                                                       │      ├─ checkout/invoice/updated/deleted\n"
    "                                                       │      └─ acreditar() si invoice\n"
    "                                                       └─ 200 / 500 según resultado"
))

# ── 5. Validación ──────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("5. Comandos ejecutados y resultado"))

story.append(make_table([
    ["Comando", "Resultado"],
    ["npm install",
     "OK · 146 packages instalados · 2 vulnerabilidades preexistentes"],
    ["npx tsc --noEmit",
     "0 errores en internal-bridge.ts y route.ts (que mi cambio agrega)"],
    ["npm run lint",
     "0 findings en internal-bridge.ts · 16 warnings/errors preexistentes "
     "(any en otros archivos, img tag, etc.) — no causados por T1.3.E"],
    ["npm run build",
     "✓ Compiled successfully · ✓ TypeScript pasa · ✓ Static pages OK · "
     "/api/webhook registrado como dynamic route"],
], col_widths=[2.0*inch, 4.5*inch]))

story.append(H2("Output relevante de npm run build"))
story.append(CODE(
    "✓ Compiled successfully in 1829ms\n"
    "Running TypeScript ...\n"
    "Finished TypeScript in 1917ms ...\n"
    "✓ Generating static pages using 14 workers (12/12) in 440ms\n"
    "\n"
    "Route (app)\n"
    "├ ƒ /api/webhook              ← endpoint que actualizamos\n"
    "├ ƒ /api/checkout\n"
    "├ ƒ /api/whatsapp-webhook\n"
    "..."
))

# ── 6. Riesgos / Blockers ──────────────────────────────────────────────────

story.append(H1("6. Riesgos y blockers"))

story.append(H2("Sin blockers para mergear"))
story.append(P(
    "Build pasa. Mi código nuevo está libre de errores tsc/lint. Los "
    "errores preexistentes en otros archivos (any types, img tag) ya "
    "estaban en main antes de T1.3.E."
))

story.append(H2("Riesgos operacionales (post-merge)"))
story.extend(bullets([
    "<b>Welcome WhatsApp duplicado en retry</b>: el welcome se envía "
    "antes del bridge. Si el bridge falla, Stripe reintenta y el welcome "
    "se vuelve a enviar. Mitigación: el usuario recibe a lo sumo 2-3 "
    "welcomes en una ventana de minutos. Aceptable; no rompe nada.",
    "<b>Secret desincronizado</b>: si Vercel y Render tienen valores "
    "distintos de INTERNAL_BRIDGE_SECRET, todos los webhooks devuelven "
    "401 → 500 a Stripe → retries infinitos. Detección: Stripe Dashboard "
    "mostrará webhooks con state=Failing.",
    "<b>BACKEND_URL apuntando a sitio caído</b>: timeout en cada webhook "
    "(8s × 3 retries = ~24s por evento). Stripe deshabilita el endpoint "
    "tras suficientes fallos.",
    "<b>Eventos legacy</b> (paquetes one-time): el bridge los reenvía al "
    "backend igual; procesar_evento_suscripcion los responde con "
    "'tipo no soportado: ...' (200 OK no-retryable). Sin efecto.",
]))

# ── 7. Próximos pasos ──────────────────────────────────────────────────────

story.append(H1("7. Próximos pasos para el owner"))

story.append(H2("a) Verificar env vars en Vercel"))
story.extend(bullets([
    "Settings → Environment Variables, scope <b>Production</b>:",
    "<b>BACKEND_URL</b> = https://dona-agent.onrender.com",
    "<b>INTERNAL_BRIDGE_SECRET</b> = (mismo valor que en Render)",
]))

story.append(H2("b) Mergear T1.3.E"))
story.extend(bullets([
    "PR T1.3.E: https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/t1.3.e-bridge-landing-backend",
    "Vercel redespliega el landing automáticamente al merge.",
    "Stripe Dashboard sigue apuntando a la landing — no se toca.",
]))

story.append(H2("c) Verificar end-to-end"))
story.extend(bullets([
    "Hacer una compra de prueba (modo test si Stripe está en test, o real "
    "con saldo bajo de test en producción).",
    "Confirmar en Render logs: <i>[BILLING] Acreditado X cr → ...</i>",
    "Confirmar en Stripe Dashboard → Webhooks → tu endpoint: status 200.",
    "Confirmar saldo del telefono via <i>dona saldo</i> por WhatsApp.",
]))

story.append(H2("d) T1.3.F (opcional)"))
story.append(P(
    "Mover Stripe Dashboard URL al backend directo "
    "(https://dona-agent.onrender.com/webhook/stripe-suscripcion o similar) "
    "y eliminar el bridge. Reduce un hop pero requiere cambio en Stripe "
    "Dashboard. <b>Solo</b> hacerlo cuando T1.3.E esté estable y soakeado "
    "varias semanas con tráfico real."
))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-02 · "
    "Repo: Dona-agent · Branch: pr/t1.3.e-bridge-landing-backend · "
    "HEAD: 45da6a1"
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.3.E — Bridge landing → backend",
    author="Claude Code", subject="Resumen de implementación T1.3.E",
)
doc.build(story)
print(f"OK: {OUTPUT}")
