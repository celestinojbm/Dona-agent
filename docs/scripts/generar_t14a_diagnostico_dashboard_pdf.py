"""
Genera T1.4.A-Diagnostico-Dashboard-2026-05-02.pdf en docs/auditorias/.
Diagnóstico read-only del dashboard de usuario.

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

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\T1.4.A-Diagnostico-Dashboard-2026-05-02.pdf"

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
    "T1.4.A — Diagnóstico Dashboard usuario", styles["TitleBig"]))
story.append(Paragraph(
    "Conexión con backend · propuesta técnica + plan por PRs",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-02 · Tipo: <b>read-only</b>, sin cambios de código",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Salida:</b> diagnóstico completo + plan por 5 PRs pequeños "
    "(T1.4.A→E). El endpoint backend (T1.4.B) reusa el patrón HMAC de "
    "T1.3.D. La sesión NextAuth ya tiene <i>subscription_id</i> que es "
    "la llave natural para identificar al usuario."
))

story.append(DANGER(
    "<b>Bug P0 detectado:</b> en landing/auth.ts línea 13–48, el "
    "<i>password</i> se recibe pero <b>nunca se valida</b>. Cualquier "
    "persona que conozca un email de subscriber activo puede entrar al "
    "dashboard y cancelar la suscripción. Tratar como bloqueador antes "
    "de exponer datos en T1.4.D."
))

# ── 1. Cómo funciona hoy el dashboard ─────────────────────────────────────

story.append(H1("1. Cómo funciona hoy el dashboard"))

story.append(H2("Ruta y autenticación"))
story.extend(bullets([
    "<b>landing/app/dashboard/page.tsx</b>: server component, llama "
    "auth(), redirige a /login si no hay sesión, monta DashboardClient.",
    "<b>landing/auth.ts</b>: NextAuth Credentials provider. authorize() "
    "lookup Stripe Customer por email + verifica subscription active. "
    "Retorna {email, stripeCustomerId, subscriptionId, plan: priceId}.",
    "<b>landing/app/login/page.tsx</b>: form email/password → "
    "signIn('credentials').",
]))

story.append(H2("UI actual (dashboard-client.tsx)"))
story.append(P("Dos secciones únicamente:"))
story.extend(bullets([
    "<b>Suscripción:</b> 'Plan activo' hardcoded. Nombre del plan "
    "computa cliente comparando session.plan con "
    "NEXT_PUBLIC_STRIPE_PRICE_PRO; si no match siempre muestra "
    "'Premium'. Texto fijo 'se renueva mensualmente' (sin fecha).",
    "<b>Conexiones:</b> 3 items hardcoded (Gmail, Calendar, WhatsApp) "
    "con connected hardcoded. Botones sin handler.",
]))

story.append(P(
    "<b>NO se muestran:</b> créditos disponibles, créditos mensuales del "
    "plan, historial de transacciones, próxima renovación, fecha de "
    "cancelación si aplica, número de teléfono."
))

story.append(H2("Cancel flow actual"))
story.append(P(
    "<b>landing/app/api/cancel-subscription/route.ts</b> llama directo a "
    "<i>stripe.subscriptions.cancel(subscriptionId)</i>. NO notifica al "
    "backend. El backend se entera vía webhook "
    "<i>customer.subscription.deleted</i> (delay segundos a minutos)."
))

# ── 2. Datos en backend ────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("2. Qué datos reales ya existen en backend"))

story.append(H2("Tablas relevantes"))
story.append(make_table([
    ["Tabla", "PK / Index", "Datos clave"],
    ["saldo_creditos", "PK telefono",
     "saldo, total_comprado, total_consumido, actualizado"],
    ["transacciones_credito", "PK id, idx telefono",
     "delta, razon, stripe_session_id, saldo_resultante, creado"],
    ["suscripcion_stripe", "PK subscription_id",
     "telefono, customer_id, plan_codigo, price_id, status, "
     "creditos_mensuales, ultimo_invoice_acreditado"],
    ["evento_stripe_procesado", "PK event_id",
     "(no relevante para dashboard)"],
], col_widths=[2.0*inch, 1.5*inch, 3.0*inch]))

story.append(H2("Funciones backend disponibles"))
story.extend(bullets([
    "<b>obtener_saldo(telefono) → int</b>: saldo actual.",
    "<b>obtener_resumen(telefono) → dict</b>: saldo + total_comprado + "
    "total_consumido + últimas 5 transacciones. <b>Cubre prácticamente "
    "todo lo que necesita el dashboard.</b>",
]))

# ── 3. Datos faltantes ─────────────────────────────────────────────────────

story.append(H1("3. Qué datos faltan o no están vinculados"))

story.append(make_table([
    ["Dato", "En backend", "En dashboard hoy"],
    ["Saldo de créditos", "saldo_creditos.saldo", "No mostrado"],
    ["Créditos mensuales del plan",
     "suscripcion_stripe.creditos_mensuales", "No mostrado"],
    ["Plan código (premium/pro)", "suscripcion_stripe.plan_codigo",
     "Solo deduce de priceId vía env público"],
    ["Status de suscripción", "suscripcion_stripe.status",
     "Hardcoded 'activa'"],
    ["Total comprado / consumido", "saldo_creditos.total_*",
     "No mostrado"],
    ["Últimas transacciones", "transacciones_credito",
     "No mostrado"],
    ["Próxima renovación",
     "(no en DB) — Stripe current_period_end", "No mostrado"],
    ["Método de pago",
     "(no en DB) — Stripe customer.invoice_settings", "No mostrado"],
], col_widths=[2.0*inch, 2.5*inch, 2.0*inch]))

story.append(P(
    "Las fechas Stripe (próxima renovación, cancelación) se obtienen "
    "vía Stripe SDK desde el server route — más fresh que cachear en DB. "
    "Los conexión Gmail/Calendar requieren consultar UsuarioGoogleAuth "
    "en backend (out of scope para T1.4)."
))

# ── 4. Identificación del usuario ──────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Cómo identificar al usuario"))

story.append(make_table([
    ["Identificador", "Donde vive", "Set por"],
    ["email", "session.user.email", "Usuario lo tipea en /login"],
    ["stripeCustomerId", "session.stripeCustomerId",
     "NextAuth lookup Stripe por email"],
    ["subscriptionId", "session.subscriptionId",
     "NextAuth: primera sub active del customer"],
    ["plan (priceId)", "session.plan",
     "NextAuth: primer item de la sub"],
    ["telefono", "NO está en sesión", "—"],
], col_widths=[1.5*inch, 2.5*inch, 2.5*inch]))

story.append(H2("El gap clave: email → telefono"))
story.append(P(
    "El backend opera por <b>telefono</b>. La sesión solo tiene email. "
    "La única tabla que une los dos es <b>suscripcion_stripe</b>:"
))
story.append(CODE(
    "session.email\n"
    "    ↓ Stripe customer.email lookup\n"
    "session.stripeCustomerId  (cus_xxx)\n"
    "    ↓ JOIN suscripcion_stripe.customer_id = cus_xxx\n"
    "suscripcion_stripe.telefono\n"
    "    ↓ usar como llave en saldo_creditos / transacciones_credito\n"
    "saldo, transacciones, etc."
))

story.append(H2("Recomendación: usar subscription_id como llave"))
story.extend(bullets([
    "Es la PK natural de suscripcion_stripe — lookup O(1).",
    "La sesión NextAuth ya lo tiene; sin round-trip extra.",
    "No filtra el teléfono al cliente (nunca cruza red pública si no "
    "hace falta).",
    "El HMAC del endpoint impide forjar IDs de otros usuarios.",
]))

# ── 5. Riesgos de seguridad ────────────────────────────────────────────────

story.append(H1("5. Riesgos de seguridad"))

story.append(H2("P0 (crítico) — Bug actual de auth"))
story.append(DANGER(
    "<b>landing/auth.ts línea 13–48:</b> authorize recibe email + "
    "password pero <b>el password nunca se valida</b>. Solo verifica "
    "que exista Stripe Customer con ese email + suscripción activa. "
    "Bug REAL. Quien conozca el email puede ver datos y cancelar."
))

story.append(H2("Otros riesgos"))
story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["/api/cancel-subscription sin CSRF explícita",
     "Media", "Origin header check o CSRF token"],
    ["Sin rate limiting en /login",
     "Media", "Rate limit por IP (brute force de emails)"],
    ["subscription_id filtrable en logs", "Baja",
     "Hoy ok, no loguearlo en errores client-side"],
    ["NO reusar ADMIN_TOKEN para dashboard endpoint",
     "Info", "Usar HMAC dedicado (INTERNAL_BRIDGE_SECRET)"],
], col_widths=[3.0*inch, 0.8*inch, 2.7*inch]))

# ── 6. Arquitectura propuesta ──────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("6. Propuesta de arquitectura mínima"))

story.append(CODE(
    "Browser\n"
    "    │ cookies (NextAuth JWT)\n"
    "    ▼\n"
    "Vercel · landing\n"
    "    /dashboard (server component)\n"
    "      auth() → session {subscriptionId, ...}\n"
    "      validar password (P0 fix)\n"
    "    /api/dashboard-data (T1.4.C, server-only)\n"
    "      auth() → tomar subscriptionId\n"
    "      POST BACKEND_URL/internal/usuario-resumen con HMAC\n"
    "      merge con datos Stripe (current_period_end, etc.)\n"
    "      retorna JSON al cliente\n"
    "        │ POST con HMAC\n"
    "        ▼\n"
    "Render · backend\n"
    "    POST /internal/usuario-resumen (T1.4.B, HMAC)\n"
    "      body {subscription_id: 'sub_xxx'}\n"
    "      1. _verificar_firma_interna() (helper de T1.3.D)\n"
    "      2. SELECT FROM suscripcion_stripe\n"
    "      3. SELECT FROM saldo_creditos\n"
    "      4. SELECT FROM transacciones_credito (últimas 10)\n"
    "      5. JSON read-only"
))

story.append(H2("Decisiones de diseño"))
story.extend(bullets([
    "<b>subscription_id</b> como llave del endpoint (no email ni "
    "teléfono).",
    "<b>HMAC reusa INTERNAL_BRIDGE_SECRET</b> — ya existe, ya está "
    "sincronizado en Vercel/Render. Reduce superficie de configuración.",
    "<b>Read-only</b>: solo SELECTs. Ningún path puede mover dinero, "
    "créditos o suscripciones desde T1.4.B.",
    "<b>Sin teléfono en la respuesta</b>: el dashboard no lo necesita "
    "mostrar, no viaja por red pública.",
    "<b>Stripe data desde server route</b>: claves Stripe nunca llegan "
    "al cliente.",
    "<b>Cancelación recomendada</b>: <i>cancel_at_period_end=true</i> en "
    "vez de <i>cancel()</i> immediate (preserva créditos pagados).",
]))

# ── 7. Plan por PRs ────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("7. Plan por PRs pequeños"))

story.append(make_table([
    ["PR", "Alcance", "Riesgo"],
    ["T1.4.A (este)",
     "Diagnóstico (este documento). Sin código.", "Cero"],
    ["T1.4.B",
     "Endpoint backend POST /internal/usuario-resumen, HMAC, read-only. "
     "Tests 8–10 casos.",
     "Bajo (solo SELECTs)"],
    ["T1.4.C",
     "API route landing /api/dashboard-data, proxy server-side al "
     "backend con HMAC + merge con Stripe data.",
     "Bajo"],
    ["T1.4.D",
     "UI dashboard con datos reales (saldo, plan, próxima renovación, "
     "historial). Bloqueado por fix P0 de auth.",
     "Medio (UX visible, requiere fix auth)"],
    ["T1.4.E",
     "Cancelación: cambiar cancel() por cancel_at_period_end. "
     "Refactor pequeño.",
     "Bajo"],
], col_widths=[1.0*inch, 4.5*inch, 1.0*inch]))

story.append(H2("T1.4.B: estructura de la respuesta"))
story.append(CODE(
    "{\n"
    "  \"subscription\": {\n"
    "    \"subscription_id\": \"sub_xxx\",\n"
    "    \"plan_codigo\": \"premium\",\n"
    "    \"status\": \"active\",\n"
    "    \"creditos_mensuales\": 100,\n"
    "    \"ultimo_invoice_acreditado\": \"in_xxx\",\n"
    "    \"creado\": \"2026-04-15T...\",\n"
    "    \"actualizado\": \"2026-05-01T...\"\n"
    "  },\n"
    "  \"saldo\": {\n"
    "    \"actual\": 170,\n"
    "    \"total_comprado\": 200,\n"
    "    \"total_consumido\": 30\n"
    "  },\n"
    "  \"ultimas_transacciones\": [\n"
    "    {\"delta\": 100, \"razon\": \"Renovación premium...\",\n"
    "     \"saldo_resultante\": 170, \"creado\": \"...\"},\n"
    "    {\"delta\": -2, \"razon\": \"generar_imagen\",\n"
    "     \"saldo_resultante\": 70, \"creado\": \"...\"}\n"
    "  ]\n"
    "}"
))

# ── 8. Tests recomendados ──────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("8. Tests recomendados por PR"))

story.append(H2("T1.4.B (backend, 8–10 tests)"))
story.append(make_table([
    ["#", "Test", "Esperado"],
    ["1", "Firma inválida", "401"],
    ["2", "Header X-Internal-Signature faltante", "401"],
    ["3", "JSON malformado", "400"],
    ["4", "Body sin subscription_id", "400"],
    ["5", "subscription_id no existe", "404"],
    ["6", "Sub existente, sin saldo", "200 con saldo=0"],
    ["7", "Sub existente con saldo + transacciones",
     "200 estructura completa"],
    ["8", "Sub canceled — devuelve igual",
     "200 con status=canceled"],
    ["9", "/admin/seed-creditos legacy intacto", "smoke"],
    ["10", "telefono NO aparece en respuesta", "assert"],
], col_widths=[0.4*inch, 3.5*inch, 2.6*inch]))

story.append(H2("T1.4.C / T1.4.D / T1.4.E"))
story.extend(bullets([
    "<b>T1.4.C:</b> npm run build pasa, sin sesión → 401, con "
    "subscriptionId inexistente → maneja graciosamente.",
    "<b>T1.4.D:</b> sin framework de tests en landing — solo build + "
    "smoke manual visual.",
    "<b>T1.4.E:</b> tests integracionales backend al recibir "
    "customer.subscription.updated con cancel_at_period_end=true. "
    "Verificar que saldo NO se borra (regresión).",
    "<b>Auth fix P0</b>: password incorrecto → 401, password correcto "
    "+ sub activa → ok, password correcto sin sub → mensaje específico.",
]))

# ── Restricciones respetadas ──────────────────────────────────────────────

story.append(H1("9. Restricciones respetadas"))
story.extend(bullets([
    "✓ No se tocó producción.",
    "✓ No se ejecutó deploy.",
    "✓ No se cambiaron env vars.",
    "✓ No se tocó Stripe Dashboard.",
    "✓ No se expusieron secretos (solo se mencionan por nombre).",
    "✓ No se implementó código.",
    "✓ Reporte en Markdown + PDF en docs/auditorias/ y docs/scripts/.",
]))

# ── Recomendación al owner ────────────────────────────────────────────────

story.append(H1("10. Recomendación al owner"))
story.extend(bullets([
    "<b>Aprobar plan T1.4.A → T1.4.E</b> o pedir ajustes (HMAC, "
    "estructura de respuesta, etc.).",
    "<b>Decidir prioridad del fix de password</b>: tratarlo como P0 "
    "antes de exponer datos en T1.4.D. Si se prefiere shipping rápido, "
    "T1.4.B + T1.4.C pueden ir antes (no afectan auth) pero T1.4.D "
    "espera fix.",
    "<b>Autorizar T1.4.B</b> cuando estés listo: solo SELECTs, "
    "idempotente, HMAC ya validado en T1.3.",
]))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Reporte generado el 2026-05-02 por Claude Code (Opus 4.7) en "
    "sesión con el owner. Read-only · sin cambios de código · sin deploy."
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.4.A — Diagnóstico Dashboard usuario",
    author="Claude Code", subject="Diagnóstico T1.4.A",
)
doc.build(story)
print(f"OK: {OUTPUT}")
