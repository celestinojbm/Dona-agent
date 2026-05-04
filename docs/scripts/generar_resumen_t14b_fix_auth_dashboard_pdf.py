"""
Genera Resumen_T14B_Fix_Auth_Dashboard_2026-05-02.pdf en docs/auditorias/.
Resumen del fix P0 de auth del dashboard (T1.4.B, commit 2f8e43f).

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

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T14B_Fix_Auth_Dashboard_2026-05-02.pdf"

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

story.append(Paragraph("T1.4.B — Fix P0 Auth Dashboard", styles["TitleBig"]))
story.append(Paragraph(
    "Validación de password en NextAuth · cierra agujero crítico",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-02 · Branch <b>pr/t1.4.b-fix-auth-dashboard</b> · "
    "Commit <b>2f8e43f</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheado a GitHub. Build pasa. Determinismo "
    "del helper validado manualmente. <b>NO mergeado a main.</b> Owner "
    "configura DASHBOARD_PASSWORD_SECRET en Vercel y deriva el password "
    "para usuarios existentes ANTES de mergear."
))

story.append(DANGER(
    "<b>Bug que se cerró:</b> En landing/auth.ts línea 13–48, la función "
    "<i>authorize</i> recibía password pero NUNCA lo validaba. Cualquiera "
    "con un email de subscriber activo podía entrar al dashboard y "
    "cancelar la suscripción. Identificado en T1.4.A."
))

# ── 1. Archivos modificados ────────────────────────────────────────────────

story.append(H1("1. Archivos modificados / creados"))
story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo", "Rol"],
    ["landing/lib/dashboard-auth.ts", "+58 / -0", "A",
     "deriveDashboardPassword + constantTimeEqual"],
    ["landing/auth.ts", "+15 / -1", "M",
     "Validación de password antes del lookup de subscription"],
    ["landing/scripts/derive-dashboard-password.ts", "+43 / -0", "A",
     "CLI helper para derivar password de un customer"],
    [".env.example", "+23 / -0", "M",
     "Documenta DASHBOARD_PASSWORD_SECRET"],
    ["", "", "", ""],
    ["TOTAL", "+139 / -1", "4 archivos", ""],
], col_widths=[2.7*inch, 0.8*inch, 0.5*inch, 2.5*inch]))

# ── 2. Diff resumido ───────────────────────────────────────────────────────

story.append(H1("2. Diff resumido"))

story.append(H2("a) landing/lib/dashboard-auth.ts (nuevo)"))
story.append(CODE(
    "export function deriveDashboardPassword(\n"
    "  customerId: string,\n"
    "): string | null {\n"
    "  const secret = process.env.DASHBOARD_PASSWORD_SECRET?.trim();\n"
    "  if (!secret || !customerId) return null;\n"
    "  const digest = crypto\n"
    "    .createHmac(\"sha256\", secret)\n"
    "    .update(customerId, \"utf8\")\n"
    "    .digest(\"hex\");\n"
    "  return \"dona-\" + digest.slice(0, 12);\n"
    "}\n"
    "\n"
    "export function constantTimeEqual(a: string, b: string): boolean {\n"
    "  if (a.length !== b.length) return false;\n"
    "  const ab = Buffer.from(a, \"utf8\");\n"
    "  const bb = Buffer.from(b, \"utf8\");\n"
    "  return crypto.timingSafeEqual(ab, bb);\n"
    "}"
))

story.append(H2("b) landing/auth.ts — validación insertada"))
story.append(CODE(
    "// Lookup customer (sin cambios).\n"
    "const customers = await getStripe().customers.list({email, limit: 1});\n"
    "if (customers.data.length === 0) return null;\n"
    "const customer = customers.data[0];\n"
    "\n"
    "// T1.4.B — validar password ANTES de buscar la suscripción.\n"
    "const expected = deriveDashboardPassword(customer.id);\n"
    "if (!expected || !constantTimeEqual(password, expected)) {\n"
    "  return null;\n"
    "}\n"
    "\n"
    "// Lookup subscription (sin cambios).\n"
    "const subscriptions = await getStripe().subscriptions.list(...);\n"
    "if (subscriptions.data.length === 0) return null;"
))

story.append(H2("c) landing/scripts/derive-dashboard-password.ts (nuevo)"))
story.append(P(
    "CLI utility para que el owner derive el password de un usuario y "
    "se lo entregue por canal seguro. <b>No</b> se importa en el bundle "
    "de producción. Uso:"
))
story.append(CODE(
    "cd landing\n"
    "DASHBOARD_PASSWORD_SECRET=<valor-de-Vercel> \\\n"
    "  npx tsx scripts/derive-dashboard-password.ts cus_xxx\n"
    "\n"
    "→ stdout: dona-fc90aa9944c7  (ejemplo, no real)"
))

story.append(H2("d) .env.example — sección nueva"))
story.append(P(
    "23 líneas que documentan DASHBOARD_PASSWORD_SECRET, su propósito, "
    "cómo generarla, dónde configurarla (solo Vercel) y cómo derivar el "
    "password de un usuario existente."
))

# ── 3. Decisiones de diseño ────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Decisiones de diseño"))

story.append(make_table([
    ["Opción considerada", "Decisión"],
    ["Magic Link (email-only, sin password)",
     "Rechazada · requiere infra de envío de mail + tokens single-use; cambio mucho más grande que el fix mínimo"],
    ["Master password único compartido",
     "Rechazada · filtración total con un solo email"],
    ["Hash bcrypt en Stripe Customer metadata",
     "Rechazada · primer login requiere flow 'create password'"],
    ["Tabla nueva en backend con hashes",
     "Rechazada · requiere endpoint nuevo + Alembic + flow set-password"],
    ["<b>Password derivado HMAC + customer_id</b>",
     "<b>ELEGIDA</b> · sin storage, determinístico, único por usuario, reusa entropía del secret"],
], col_widths=[2.5*inch, 4.0*inch]))

story.append(H2("Por qué esta opción"))
story.extend(bullets([
    "<b>Mínima:</b> sin DB nueva, sin migración, sin endpoint nuevo, "
    "sin Alembic.",
    "<b>Sin path permisivo:</b> si la env var falta, todos los logins "
    "fallan. Mejor bloquear que aceptar.",
    "<b>Resistente a timing oracles:</b> compareDigest sobre buffers UTF-8.",
    "<b>Validar antes del lookup de subscription:</b> no revela si el "
    "customer existe en Stripe (mismo error para password incorrecto y "
    "customer inexistente).",
    "<b>Sin password reset complicado:</b> el password es derivable, no "
    "se pierde. Si el usuario lo olvida, el owner lo regenera con el "
    "helper.",
]))

# ── 4. Validación ──────────────────────────────────────────────────────────

story.append(H1("4. Comandos ejecutados y resultado"))

story.append(make_table([
    ["Comando", "Resultado"],
    ["npx tsc --noEmit", "0 errores"],
    ["npm run lint",
     "16 problems · todos preexistentes (any types en otros archivos, "
     "img tag, etc). 0 nuevos por T1.4.B."],
    ["npm run build",
     "✓ Compiled successfully · ✓ TypeScript pasa · 14 rutas registradas"],
    ["Test manual del helper",
     "Determinismo OK · sin secret → exit 2 · distinto secret/customer "
     "→ distinto password"],
], col_widths=[2.0*inch, 4.5*inch]))

story.append(H2("Test manual: outputs reales"))
story.append(CODE(
    "$ DASHBOARD_PASSWORD_SECRET=test-secret-not-real-12345 \\\n"
    "  npx tsx scripts/derive-dashboard-password.ts cus_TEST_001\n"
    "dona-fc90aa9944c7\n"
    "\n"
    "$ # mismo input → mismo password (determinismo)\n"
    "$ DASHBOARD_PASSWORD_SECRET=test-secret-not-real-12345 \\\n"
    "  npx tsx scripts/derive-dashboard-password.ts cus_TEST_001\n"
    "dona-fc90aa9944c7\n"
    "\n"
    "$ # distinto customer → distinto password\n"
    "$ DASHBOARD_PASSWORD_SECRET=test-secret-not-real-12345 \\\n"
    "  npx tsx scripts/derive-dashboard-password.ts cus_TEST_002\n"
    "dona-0bb38380f5d3\n"
    "\n"
    "$ # distinto secret → distinto password\n"
    "$ DASHBOARD_PASSWORD_SECRET=diferente-secret \\\n"
    "  npx tsx scripts/derive-dashboard-password.ts cus_TEST_001\n"
    "dona-1386e4148cd6\n"
    "\n"
    "$ # sin secret → exit 2\n"
    "$ npx tsx scripts/derive-dashboard-password.ts cus_TEST_001\n"
    "Error: DASHBOARD_PASSWORD_SECRET no configurada o customer_id vacío.\n"
    "exit=2"
))
story.append(P(
    "<b>Nota:</b> el secret 'test-secret-not-real-12345' es un valor "
    "ficticio usado solo para verificar la lógica. En Vercel se debe "
    "configurar uno de alta entropía generado con secrets.token_urlsafe(32)."
))

# ── 5. Criterios de aceptación ─────────────────────────────────────────────

story.append(H1("5. Criterios de aceptación"))

story.append(make_table([
    ["Criterio", "Cómo se cumple"],
    ["Password incorrecto → login rechazado",
     "constantTimeEqual retorna false → authorize devuelve null → "
     "NextAuth muestra error genérico"],
    ["Email sin sub activa → login rechazado",
     "subscriptions.list({status:'active'}) vacío → return null"],
    ["Email + sub activa + password correcto → login OK",
     "Path completo pasa, retorna user con stripeCustomerId, etc."],
    ["No filtrar secrets en logs ni errores",
     "El secret nunca se loguea. El password derivado solo viaja por "
     "stdout del CLI helper local. Errores de auth retornan null genérico."],
    ["Build/lint/test pasa",
     "tsc 0 errores, lint baseline igual, build OK, helper test OK"],
    ["Reportar archivos / diff / riesgos / próximos",
     "Este documento + resumen al final del turno"],
], col_widths=[3.0*inch, 3.5*inch]))

# ── 6. Riesgos y próximos pasos ────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("6. Riesgos y próximos pasos"))

story.append(H2("Riesgos abiertos"))
story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Si DASHBOARD_PASSWORD_SECRET se filtra, todos los passwords "
     "son derivables",
     "Alta", "Rotar el secret en Vercel; generar nuevos passwords "
     "para todos los usuarios"],
    ["Sin rate limiting en /login (brute force de emails)",
     "Media", "Pendiente — agregar middleware o turnstile en T1.4.E o "
     "antes si se detecta abuso"],
    ["Owner debe entregar el password al usuario por canal seguro",
     "Operativo", "Recomendado: por WhatsApp via Dona, no por email "
     "(Stripe customer email puede ser compartido o hackeado)"],
    ["Si el usuario olvida el password, regenerarlo deja el viejo "
     "operable hasta que el secret rote",
     "Baja", "El password es determinístico — mismo customer_id + "
     "mismo secret = mismo password. No hay 'olvido' real, solo entrega"],
    ["NextAuth muestra mismo mensaje para todos los fallos",
     "Bajo (es feature)", "Previene oracle de existencia de email/sub"],
], col_widths=[2.7*inch, 0.9*inch, 2.9*inch]))

story.append(H2("Próximos pasos para el owner"))

story.append(P("<b>Antes de mergear este PR:</b>"))
story.extend(bullets([
    "1. <b>Generar DASHBOARD_PASSWORD_SECRET</b>: "
    "<i>python -c \"import secrets; print(secrets.token_urlsafe(32))\"</i>",
    "2. <b>Configurarlo en Vercel</b> (Settings → Environment Variables, "
    "scope <b>Production</b>).",
    "3. <b>Para cada usuario activo existente</b> (Premium/Pro): "
    "buscar su <i>cus_xxx</i> en Stripe Dashboard y derivar el password "
    "con el helper local. Anotar el password.",
    "4. <b>Mergear el PR</b>: "
    "https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/t1.4.b-fix-auth-dashboard",
    "5. <b>Vercel redespliega</b> automáticamente. Inmediatamente "
    "después del redeploy, el login con el password viejo (o sin "
    "password) deja de funcionar.",
    "6. <b>Entregar el password al usuario</b> por WhatsApp via Dona.",
]))

story.append(WARN(
    "<b>Importante:</b> entre el merge y la entrega del password, los "
    "usuarios existentes <b>no podrán acceder al dashboard</b>. "
    "Coordinar con el primer usuario activo (vos mismo) para minimizar "
    "ventana. Si se quiere ventana cero, derivar password ANTES del "
    "merge y comunicar via WhatsApp justo después del merge."
))

story.append(H2("Próximos PRs en T1.4 (orden aprobado)"))
story.extend(bullets([
    "<b>T1.4.C</b>: Backend read-only POST /internal/usuario-resumen "
    "(HMAC). Sin riesgo (solo SELECTs).",
    "<b>T1.4.D</b>: Landing /api/dashboard-data, proxy server-side al "
    "backend.",
    "<b>T1.4.E</b>: Dashboard UI con datos reales — saldo, plan, "
    "historial, próxima renovación.",
    "<b>T1.4.F</b>: Cancelación segura — cancel_at_period_end en vez "
    "de cancel() inmediato.",
]))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-02 · "
    "Repo: Dona-agent · Branch: pr/t1.4.b-fix-auth-dashboard · "
    "HEAD: 2f8e43f"
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.4.B — Fix P0 Auth Dashboard",
    author="Claude Code", subject="Resumen de implementación T1.4.B",
)
doc.build(story)
print(f"OK: {OUTPUT}")
