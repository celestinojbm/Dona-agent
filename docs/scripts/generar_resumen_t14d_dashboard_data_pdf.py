"""
Genera Resumen_T14D_Dashboard_Data_2026-05-03.pdf en docs/auditorias/.
Resumen del proxy /api/dashboard-data server-side (T1.4.D, commit 732f247).

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

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T14D_Dashboard_Data_2026-05-03.pdf"

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="TitleBig", parent=styles["Title"], fontSize=22, leading=26,
    spaceAfter=8, textColor=colors.HexColor("#111111"),
))
styles.add(ParagraphStyle(
    name="Subtitle", parent=styles["Normal"], fontSize=11, leading=15,
    textColor=colors.HexColor("#374151"), spaceAfter=4,
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
    name="DangerBanner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#991b1b"), backColor=colors.HexColor("#fef2f2"),
    borderPadding=8, borderColor=colors.HexColor("#dc2626"), borderWidth=0.8,
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
def DANGER(t): return Paragraph(t, styles["DangerBanner"])


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

story.append(Paragraph(
    "T1.4.D — /api/dashboard-data server-side", styles["TitleBig"]))
story.append(Paragraph(
    "Proxy landing → backend con merge Stripe SDK · ningún ID del cliente",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-03 · Branch <b>pr/t1.4.d-dashboard-data</b> · "
    "Commit <b>732f247</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheado a GitHub. Build OK · 16/16 static "
    "pages · /api/dashboard-data registrado como ƒ (server-rendered). "
    "tsc 0 errores · lint sin nuevos. Secrets no aparecen en bundle "
    "estático del cliente. <b>NO mergeado a main.</b>"
))

# ── 1. Archivos modificados ────────────────────────────────────────────────

story.append(H1("1. Archivos modificados"))
story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo", "Rol"],
    ["landing/lib/internal-bridge.ts", "+141 / -0", "M",
     "fetchUsuarioResumen() + tipos + shortId() helper"],
    ["landing/app/api/dashboard-data/route.ts", "+150 / -0", "A",
     "GET handler server-only"],
    ["", "", "", ""],
    ["TOTAL", "+291 / -0", "2 archivos", ""],
], col_widths=[2.7*inch, 0.8*inch, 0.5*inch, 2.5*inch]))

# ── 2. Endpoint creado ─────────────────────────────────────────────────────

story.append(H1("2. Formato final del endpoint"))

story.append(H2("Ruta"))
story.append(CODE(
    "GET /api/dashboard-data\n"
    "(no acepta body ni query params para identificar usuario)"
))

story.append(H2("Códigos HTTP"))
story.append(make_table([
    ["Status", "Cuándo"],
    ["401", "Sin sesión NextAuth (auth() retornó null)"],
    ["403", "Sesión sin subscriptionId (caso raro: sub canceled hace mucho)"],
    ["404", "Backend respondió 404 — subscription_not_found"],
    ["502", "Backend respondió 401 (secret desincronizado) o cualquier otro no-2xx"],
    ["504", "Timeout llamando al backend (>8s)"],
    ["200", "Caso feliz: JSON con datos del backend + overrides Stripe + email"],
], col_widths=[0.7*inch, 5.5*inch]))

story.append(H2("Body response (200)"))
story.append(CODE(
    "{\n"
    "  \"usuario\": {\n"
    "    \"id\": \"sub_xxx\",\n"
    "    \"email\": \"user@example.com\",  // de session.user.email\n"
    "    \"telefono\": \"14076936023\"\n"
    "  },\n"
    "  \"creditos\": {\n"
    "    \"saldo_actual\": 170,\n"
    "    \"creditos_mensuales\": 100,\n"
    "    \"ultimo_movimiento\": {...}\n"
    "  },\n"
    "  \"suscripcion\": {\n"
    "    \"estado\": \"active\",            // del backend\n"
    "    \"plan\": \"premium\",             // del backend\n"
    "    \"stripe_customer_id\": \"cus_xxx\",\n"
    "    \"stripe_subscription_id\": \"sub_xxx\",\n"
    "    \"current_period_end\": 1717545600,  // de Stripe SDK\n"
    "    \"cancel_at_period_end\": false,     // de Stripe SDK\n"
    "    \"actualizado\": \"2026-05-02T...\"\n"
    "  },\n"
    "  \"transacciones_recientes\": [...],   // del backend\n"
    "  \"resumen\": {\n"
    "    \"puede_cancelar\": true,\n"
    "    \"dashboard_ready\": true\n"
    "  }\n"
    "}"
))

# ── 3. Cómo se obtiene subscriptionId ──────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Cómo se obtiene subscriptionId"))

story.append(DANGER(
    "<b>Guardrail #1 (server-side identifiers):</b> el subscriptionId "
    "se toma <b>únicamente</b> de la sesión NextAuth server-side. "
    "<b>NUNCA</b> del request del cliente (ni body, ni query, ni headers)."
))

story.append(CODE(
    "export async function GET() {\n"
    "  const session = await auth();\n"
    "  if (!session) {\n"
    "    return NextResponse.json({error: \"unauthenticated\"}, {status: 401});\n"
    "  }\n"
    "\n"
    "  // 2. Tomar subscriptionId SOLO de la sesión server-side.\n"
    "  // Guardrail T1.4.D: NUNCA del request del cliente.\n"
    "  const subscriptionId = (session as {subscriptionId?: string})\n"
    "    .subscriptionId;\n"
    "  const sessionEmail = session.user?.email ?? null;\n"
    "\n"
    "  if (!subscriptionId) {\n"
    "    return NextResponse.json(\n"
    "      {error: \"no_subscription_in_session\"},\n"
    "      {status: 403},\n"
    "    );\n"
    "  }\n"
    "  // ...\n"
    "}"
))

story.append(P(
    "El handler es <b>GET</b>, no acepta JSON body. Aunque el cliente "
    "intentara mandar un subscription_id en query string o headers, el "
    "código no los lee. La sesión NextAuth se lee con <i>auth()</i> "
    "que valida la cookie JWT firmada del usuario."
))

# ── 4. Cómo se firma HMAC ──────────────────────────────────────────────────

story.append(H1("4. Cómo se firma HMAC"))

story.append(P(
    "Reusa el patrón de T1.3.E: HMAC-SHA256 del body crudo con "
    "INTERNAL_BRIDGE_SECRET, header <i>X-Internal-Signature</i>. La "
    "lógica está en <i>fetchUsuarioResumen</i> de internal-bridge.ts:"
))

story.append(CODE(
    "export async function fetchUsuarioResumen(\n"
    "  subscriptionId: string,\n"
    "): Promise<FetchUsuarioResumenResult> {\n"
    "  const backendUrl = process.env.BACKEND_URL?.trim();\n"
    "  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();\n"
    "\n"
    "  if (!backendUrl) return {ok: false, error: \"backend_url_missing\"};\n"
    "  if (!secret) return {ok: false, error: \"internal_bridge_secret_missing\"};\n"
    "\n"
    "  const body = JSON.stringify({subscription_id: subscriptionId});\n"
    "  const signature = crypto\n"
    "    .createHmac(\"sha256\", secret)\n"
    "    .update(body, \"utf8\")\n"
    "    .digest(\"hex\");\n"
    "\n"
    "  const url = `${backendUrl.replace(/\\/+$/, \"\")}/internal/usuario-resumen`;\n"
    "  const res = await fetch(url, {\n"
    "    method: \"POST\",\n"
    "    headers: {\n"
    "      \"Content-Type\": \"application/json\",\n"
    "      \"X-Internal-Signature\": signature,\n"
    "    },\n"
    "    body, signal: controller.signal,\n"
    "  });\n"
    "  // ... mapping de res.status a {ok, status, error}\n"
    "}"
))

story.append(P(
    "El body que firmamos es <b>exactamente el body que enviamos</b> "
    "(misma referencia de string). Timeout 8s vía AbortController."
))

# ── 5. Cómo se consulta Stripe ─────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("5. Cómo se consulta Stripe"))

story.append(P(
    "<i>fetchStripeOverrides</i> en route.ts hace "
    "<i>subscriptions.retrieve(subscriptionId)</i>. En <b>stripe@22</b> "
    "el campo <i>current_period_end</i> se movió del root del "
    "Subscription al primer subscription item."
))

story.append(CODE(
    "async function fetchStripeOverrides(subscriptionId: string) {\n"
    "  if (!process.env.STRIPE_SECRET_KEY) return DEFAULT;\n"
    "  try {\n"
    "    const sub = await getStripe().subscriptions.retrieve(\n"
    "      subscriptionId,\n"
    "    );\n"
    "    // current_period_end vive en items.data[0] en stripe@22.\n"
    "    const firstItem = sub.items?.data?.[0];\n"
    "    return {\n"
    "      current_period_end: typeof firstItem?.current_period_end === \"number\"\n"
    "        ? firstItem.current_period_end : null,\n"
    "      cancel_at_period_end: Boolean(sub.cancel_at_period_end),\n"
    "      status_stripe: sub.status ?? null,\n"
    "    };\n"
    "  } catch (err) {\n"
    "    // Log con shortId(); no propagar el error al cliente.\n"
    "    return DEFAULT;\n"
    "  }\n"
    "}"
))

story.append(P(
    "Si Stripe falla (red, no configurado en dev, etc.), devolvemos "
    "defaults <i>(period_end=null, cancel=false)</i>. El backend response "
    "queda válido, solo el dashboard no mostrará la fecha de renovación."
))

story.append(H2("Paralelización"))
story.append(P(
    "Backend y Stripe se llaman en paralelo con <i>Promise.all</i> para "
    "no apilar latencias. La total esperada es max(backend, stripe), no "
    "su suma."
))

# ── 6. Guardrails respetadas ───────────────────────────────────────────────

story.append(H1("6. Guardrails respetadas (Dona Control review T1.4.C)"))

story.append(make_table([
    ["Guardrail", "Cómo se cumple"],
    ["#1: subscriptionId server-side only",
     "Se lee SOLO de session.subscriptionId. El handler es GET sin body, "
     "no lee query params para id de usuario."],
    ["#2: no loguear subscription_id completo",
     "Helper shortId() trunca a 'sub_xxxxxxxx...abcd' antes de pasar a "
     "console.error. Aplicado en fetchUsuarioResumen y fetchStripeOverrides."],
    ["No exponer INTERNAL_BRIDGE_SECRET",
     "Solo se lee dentro de fetchUsuarioResumen (server-only). "
     "Verificado: ausente en .next/static/."],
    ["No exponer STRIPE_SECRET_KEY",
     "Solo en getStripe() (server-only). Misma verificación."],
    ["No filtrar errores crudos del backend",
     "Códigos semánticos: subscription_not_found, backend_auth_error, "
     "backend_timeout, backend_unavailable. El cliente nunca ve el body "
     "de error del backend."],
], col_widths=[2.5*inch, 4.0*inch]))

# ── 7. Comandos ejecutados ─────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("7. Comandos ejecutados y resultado"))

story.append(make_table([
    ["Comando", "Resultado"],
    ["npx tsc --noEmit",
     "0 errores tras ajustar current_period_end → items.data[0]"],
    ["npm run lint",
     "16 problems · todos preexistentes (any types en otros archivos). "
     "0 nuevos por T1.4.D."],
    ["npm run build",
     "✓ Compiled successfully · 16/16 static pages · /api/dashboard-data "
     "registrado como ƒ (dynamic, server-rendered on demand)"],
    ["grep secrets en .next/static/",
     "0 matches · INTERNAL_BRIDGE_SECRET y STRIPE_SECRET_KEY no aparecen "
     "en bundle del cliente"],
    ["grep secrets en .next/server/",
     "Sí aparecen (esperado: el código server-side lee process.env)"],
], col_widths=[2.0*inch, 4.5*inch]))

# ── 8. Riesgos abiertos ────────────────────────────────────────────────────

story.append(H1("8. Riesgos abiertos"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Sesión NextAuth comprometida → atacante consume su propio "
     "dashboard-data",
     "Bajo", "Solo accede a SU PROPIO data. Mitigación primaria es "
     "T1.4.B (password validation). T1.4.D no agrega superficie."],
    ["INTERNAL_BRIDGE_SECRET filtrado",
     "Alta", "Rotar en Vercel y Render simultáneamente (mismo riesgo "
     "que T1.3.D/E)."],
    ["STRIPE_SECRET_KEY filtrado",
     "Alta", "Rotar en Vercel + Render. Stripe permite revocación "
     "inmediata."],
    ["Stripe SDK retrieve falla (red, rate-limit)",
     "Bajo", "Manejado: devolvemos defaults. Dashboard se renderiza "
     "sin period_end pero no rompe."],
    ["Backend timeout > 8s",
     "Bajo", "Devolvemos 504 al cliente; el dashboard puede reintentar."],
    ["Sin rate limiting en /api/dashboard-data",
     "Bajo", "Solo accesible con sesión válida. Sesión sirve como "
     "rate limit indirecto. Mitigable en T1.4.E si se detecta abuso."],
], col_widths=[2.7*inch, 0.8*inch, 3.0*inch]))

# ── 9. Próximos pasos T1.4.E ──────────────────────────────────────────────

story.append(H1("9. Próximos pasos para T1.4.E (UI dashboard)"))

story.append(P(
    "T1.4.E es la UI: <b>landing/app/dashboard/dashboard-client.tsx</b> "
    "consume <i>/api/dashboard-data</i> y muestra:"
))

story.extend(bullets([
    "<b>Saldo actual</b> grande (ej. \"170 créditos\") + indicador de "
    "créditos mensuales del plan.",
    "<b>Plan activo</b> real desde backend (premium / pro), no más "
    "comparación con priceId del env.",
    "<b>Próxima renovación</b> formateada (current_period_end → fecha "
    "humana).",
    "<b>cancel_at_period_end</b> visible si aplica con texto tipo "
    "\"Se cancela el DD/MM\".",
    "<b>Historial</b>: tabla con últimas 10 transacciones (delta, "
    "razón, saldo resultante, fecha).",
    "<b>Estados de carga</b>: skeleton mientras carga, mensaje de "
    "error legible si dashboard-data falla.",
]))

story.append(WARN(
    "<b>Importante para T1.4.E:</b> el cliente solo conoce los datos "
    "que aparecen en el response de /api/dashboard-data. NO añadir "
    "fetches a Stripe SDK ni al backend desde el browser. Si T1.4.E "
    "necesita más datos, extender T1.4.D."
))

story.append(H2("T1.4.F (después de T1.4.E)"))
story.append(P(
    "Cancelación segura: cambiar "
    "<i>stripe.subscriptions.cancel()</i> por "
    "<i>stripe.subscriptions.update({cancel_at_period_end: true})</i> "
    "en /api/cancel-subscription. UX: \"se cancela el DD/MM, hasta "
    "esa fecha podés seguir usando los créditos\"."
))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-03 · "
    "Repo: Dona-agent · Branch: pr/t1.4.d-dashboard-data · HEAD: 732f247"
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.4.D — /api/dashboard-data",
    author="Claude Code", subject="Resumen de implementación T1.4.D",
)
doc.build(story)
print(f"OK: {OUTPUT}")
