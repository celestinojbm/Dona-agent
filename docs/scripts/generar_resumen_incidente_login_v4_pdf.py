"""
Genera Resumen_Incidente_Login_V4_2026-05-02.pdf · diagnóstico read-only
con Vercel logs reales del usuario afectado + propuesta de instrumentación
temporal sin PII en rama diag/auth-instrumentation.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_Incidente_Login_V4_2026-05-02.pdf"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleBig", parent=styles["Title"], fontSize=20, leading=24,
    spaceAfter=8, textColor=colors.HexColor("#111111")))
styles.add(ParagraphStyle(name="MetaTop", parent=styles["Normal"], fontSize=9, leading=12,
    textColor=colors.HexColor("#555555"), spaceAfter=18))
styles.add(ParagraphStyle(name="Banner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#065f46"), backColor=colors.HexColor("#ecfdf5"),
    borderPadding=8, borderColor=colors.HexColor("#10b981"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14))
styles.add(ParagraphStyle(name="WarnBanner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#7c2d12"), backColor=colors.HexColor("#fff7ed"),
    borderPadding=8, borderColor=colors.HexColor("#f97316"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14))
styles.add(ParagraphStyle(name="ErrBanner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#991b1b"), backColor=colors.HexColor("#fef2f2"),
    borderPadding=8, borderColor=colors.HexColor("#ef4444"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14))
styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"], fontSize=15, leading=19,
    spaceBefore=16, spaceAfter=6, textColor=colors.HexColor("#111111")))
styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], fontSize=12, leading=16,
    spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#1f2937")))
styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], fontSize=9.5, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=6, textColor=colors.HexColor("#222222")))
styles.add(ParagraphStyle(name="Caption", parent=styles["Body"], fontSize=8.5, leading=11,
    textColor=colors.HexColor("#6b7280"), spaceAfter=10))
styles.add(ParagraphStyle(name="CodeBox", parent=styles["Code"], fontSize=8, leading=10,
    textColor=colors.HexColor("#111111"),
    backColor=colors.HexColor("#f5f5f5"),
    borderPadding=6, borderColor=colors.HexColor("#e5e7eb"), borderWidth=0.4,
    leftIndent=4, rightIndent=4, spaceBefore=6, spaceAfter=10))
styles.add(ParagraphStyle(name="BulletDona", parent=styles["Body"], leftIndent=14, bulletIndent=2,
    spaceAfter=2))


def H1(t): return Paragraph(t, styles["H1"])
def H2(t): return Paragraph(t, styles["H2"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])
def BANNER(t): return Paragraph(t, styles["Banner"])
def WARN(t): return Paragraph(t, styles["WarnBanner"])
def ERR(t): return Paragraph(t, styles["ErrBanner"])


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


story = []

story.append(Paragraph("INCIDENTE LOGIN · v4 · evidencia desde Vercel logs",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-02 · DASHBOARD_PASSWORD_SECRET "
    "<b>confirmado igual</b> en Vercel y Render por owner · login "
    "sigue fallando · Vercel logs reales obtenidos de los intentos · "
    "rama de instrumentación lista en <b>diag/auth-instrumentation</b>",
    styles["MetaTop"],
))

story.append(WARN(
    "<b>Hallazgo crítico:</b> los logs de Vercel de los 2 últimos "
    "intentos del usuario muestran <i>CredentialsSignin</i> "
    "genérico de Auth.js · <b>NO aparece la línea "
    "<i>[AUTH] recovery cross-customer ...</i></b> que el v2 emite. "
    "Esto descarta que se haya activado Pass 2. El matcher "
    "retornó null en Pass 1 (sin ownership demostrado), o lanzó "
    "una excepción silenciosa antes de loguear. Necesitamos "
    "instrumentación para distinguir."
))

# ── 1. Deploy verificado vía Vercel CLI ────────────────────────────────

story.append(H1("1. Deploy de PR #33 confirmado activo"))

story.append(P(
    "<i>vercel</i> CLI tenía sesión local de <i>celestinojbm</i>. "
    "Diagnóstico read-only:"
))

story.append(make_table([
    ["Verificación", "Resultado"],
    ["vercel whoami",
     "celestinojbm · sesión activa, sin escribir nada"],
    ["vercel ls dona-agent",
     "3 deploys Production en ~40 min · todos <i>● Ready</i>"],
    ["vercel inspect (deploy current)",
     "<b>dpl_CvJgMg2T6BdojT8YfqQLTPdZR8AH</b> · target=production · "
     "status=Ready · alias <b>usadona.com</b>"],
    ["Branch del deploy", "main (último HEAD = a4320d4 = Merge PR #33)"],
    ["Funciones deployed",
     "<i>api/auth/[...nextauth]</i> presente · 1.05MB · region iad1"],
    ["Builds", "Ready · sin errores · 38s duración"],
], col_widths=[2.0*inch, 4.6*inch]))

story.append(BANNER(
    "<b>Conclusión sección 1:</b> el deploy del PR #33 está activo "
    "en producción y servido por usadona.com. Las hipótesis #6 "
    "('PR #33 no desplegado') queda <b>descartada</b>."
))

# ── 2. Logs reales del incidente ───────────────────────────────────────

story.append(H1("2. Logs Vercel · 2 intentos del usuario afectado"))

story.append(P(
    "Comando ejecutado (read-only):"
))

story.append(CODE(
    "vercel logs https://dona-agent-ilcbtq1cv-... \\\n"
    "  --no-follow --since 1h --json -n 100"
))

story.append(P(
    "Líneas relevantes encontradas (cita literal redactada):"
))

story.append(CODE(
    "// Intento 1 · POST /api/auth/callback/credentials\n"
    "{\n"
    "  level: 'error',\n"
    "  source: 'serverless',\n"
    "  domain: 'www.usadona.com',\n"
    "  responseStatusCode: 200,\n"
    "  message: '[auth][error] CredentialsSignin: Read more at\n"
    "            https://errors.authjs.dev#credentialssignin',\n"
    "  logs: [\n"
    "    { level: 'error', message: '[auth][error] CredentialsSignin' },\n"
    "    { level: 'error', message: 'at av (.../landing_xxx._.js:404:40971)\\n\n"
    "                                ... at async aC (...)\\n\n"
    "                                ... at async aU (...)' },\n"
    "  ],\n"
    "}\n"
    "\n"
    "// Intento 2 · POST /api/auth/callback/credentials\n"
    "// (idéntico al anterior · stack trace minificado)"
))

story.append(make_table([
    ["Pregunta del incidente", "Respuesta basada en logs"],
    ["¿Aparece <i>[AUTH] recovery cross-customer</i> en logs?",
     "<b>NO</b>. Esto significa que Pass 2 nunca se activó o que "
     "el matcher lanzó excepción antes."],
    ["¿Hay errores de Stripe (auth, rate limit)?",
     "<b>NO se observan</b> en los logs adyacentes. Pero el stack "
     "minificado podría ocultar una excepción interna del matcher."],
    ["¿Es null por password no match?",
     "<b>Posible</b>. Es la causa más común de "
     "<i>CredentialsSignin</i> sin warns adicionales."],
    ["¿Es null por sin valid sub?",
     "<b>Improbable</b>. Si fuera este caso, el password tendría "
     "que coincidir con un customer · el WARN de recovery se "
     "habría emitido si Pass 2 encontraba sub."],
    ["¿Es excepción interna?",
     "<b>Posible</b>. El stack trace tiene formato "
     "<i>at av (...) at async aC (...)</i> · funciones minificadas. "
     "Sin source maps no es decodificable desde fuera."],
], col_widths=[3.0*inch, 3.6*inch]))

# ── 3. Causa probable ──────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Causa probable · ranqueada"))

story.append(make_table([
    ["#", "Causa", "Prob.", "Razón"],
    ["1",
     "<b>Password no matchea ningún customer</b> del email",
     "<b>ALTA</b>",
     "Coherente con la ausencia del WARN. DASHBOARD_PASSWORD_SECRET "
     "está OK (owner confirmó). Significa que el password que el "
     "usuario tipea NO es el derivado real para ningún cus_."],
    ["2",
     "Email de cus_NEW difiere sutilmente · matcher case-sensitive",
     "MEDIA",
     "<i>raw.email !== email</i>. Si Stripe guardó "
     "<i>Celestinojbm@gmail.com</i> mientras el usuario teclea "
     "<i>celestinojbm@gmail.com</i>, candidatos = 0 y el matcher "
     "retorna null sin loguear nada."],
    ["3",
     "Sub no está en active/trialing/past_due",
     "MEDIA-BAJA",
     "Si fuera este caso Y el password matcheara, Pass 2 emitiría "
     "WARN al recuperar. Como no hay WARN, queda solo el "
     "sub-caso 'sub no válida + password no match' que es "
     "redundante con causa #1."],
    ["4",
     "Excepción silenciosa en customers.list / subscriptions.list "
     "antes de logear",
     "BAJA",
     "El stack trace existe pero es minificado. Posible si Stripe "
     "API throttling o auth issue. Improbable porque otras rutas "
     "que usan getStripe (/api/billing-portal etc) no muestran "
     "errores correlacionados."],
], col_widths=[0.3*inch, 2.6*inch, 0.8*inch, 2.9*inch]))

story.append(BANNER(
    "<b>Veredicto provisional:</b> el password que el usuario "
    "tipea no es un derivado válido para ninguno de los customers "
    "del email <b>celestinojbm@gmail.com</b>. Para confirmar entre "
    "causa #1 y #2 (que son distinguibles solo con instrumentación), "
    "preparé la rama <b>diag/auth-instrumentation</b>."
))

# ── 4. Rama de instrumentación · sin PII ───────────────────────────────

story.append(H1("4. Instrumentación temporal · diag/auth-instrumentation"))

story.append(P(
    "Branch <i>diag/auth-instrumentation</i> · <b>NO mergeada · "
    "NO desplegada</b>. HEAD basado en main@a4320d4."
))

story.append(H2("Cambio en lib/auth-matcher.ts"))

story.append(CODE(
    "// Nueva interfaz · solo contadores y booleanos · sin PII\n"
    "export interface AuthTelemetry {\n"
    "  customersCount: number;\n"
    "  candidatesCount: number;\n"
    "  passwordMatchedAnyCustomer: boolean;\n"
    "  validSubFoundOnOwner: boolean;\n"
    "  recoveryAttemptedAndFound: boolean;\n"
    "  nullReason: 'no_email_or_password' | 'no_candidates'\n"
    "    | 'no_password_match' | 'no_valid_sub' | null;\n"
    "}\n"
    "\n"
    "// El matcher acepta un onTelemetry opcional · si está,\n"
    "// emite el objeto al terminar (incluso si retorna null)."
))

story.append(H2("Cambio en auth.ts · activable por env var"))

story.append(CODE(
    "const diagOn = process.env.AUTH_DIAG === '1';\n"
    "const match = await encontrarCustomerConSub(email, password, {\n"
    "  customers: stripe.customers,\n"
    "  subscriptions: stripe.subscriptions,\n"
    "  derivePassword: deriveDashboardPassword,\n"
    "  passwordMatch: constantTimeEqual,\n"
    "  onTelemetry: diagOn\n"
    "    ? (m) =&gt; console.warn(\n"
    "        '[AUTH_DIAG] ' + JSON.stringify({...m})\n"
    "      )\n"
    "    : undefined,\n"
    "});"
))

story.append(P(
    "<b>Garantías de seguridad:</b>"
))

story.extend(bullets([
    "<b>Default OFF</b>. Solo emite logs si "
    "<i>AUTH_DIAG=1</i> está seteada en Vercel.",
    "<b>Cero PII</b>. La telemetría tiene solo contadores y "
    "booleanos · sin email, password, customer.id ni "
    "subscription.id.",
    "<b>Test específico</b> verifica que el JSON serializado de "
    "la telemetría no contiene email, password ni IDs de Stripe "
    "(test 21 de los 22).",
    "<b>Reversible en 1 paso</b>: borrar la env var en Vercel · "
    "los logs vuelven al baseline. Eliminación final del código "
    "en otro PR cuando se confirme el diagnóstico.",
]))

# ── 5. Tests ────────────────────────────────────────────────────────────

story.append(H1("5. Tests · 22/22 passing"))

story.append(BANNER(
    "<b>npm test</b> · 22 passing · vitest@2.1.9 · 311ms · 15 "
    "previos + 7 nuevos de telemetría"
))

story.append(make_table([
    ["#", "Test nuevo de telemetría", "Cubre"],
    ["16",
     "Email no existe · emite customersCount=0 · "
     "nullReason='no_candidates'",
     "Caso baseline"],
    ["17",
     "Hay candidatos pero password no matchea · "
     "nullReason='no_password_match'",
     "<b>Hipótesis principal del incidente actual</b>"],
    ["18",
     "Ownership demostrado pero ningún customer tiene sub válida "
     "· nullReason='no_valid_sub'",
     "Distingue de #17"],
    ["19",
     "validSubFoundOnOwner=true cuando Pass 1 encuentra match",
     "Happy path baseline"],
    ["20",
     "recoveryAttemptedAndFound=true cuando Pass 2 autoriza",
     "Happy path recovery"],
    ["21",
     "<b>Telemetría serializada NO contiene email, password, "
     "customer.id ni subscription.id</b>",
     "<b>Test de no-PII</b>"],
    ["22",
     "Sin onTelemetry el matcher funciona normal y no emite nada",
     "Default OFF respetado"],
], col_widths=[0.3*inch, 3.5*inch, 2.8*inch]))

# ── 6. Validación ──────────────────────────────────────────────────────

story.append(H1("6. Validación local"))

story.append(make_table([
    ["Comando (cwd landing/)", "Resultado"],
    ["npm test", "<b>22/22 passing</b>"],
    ["npx tsc --noEmit", "0 errores"],
    ["rm -rf .next && npm run build", "OK · 17/17 pages"],
    ["npm run lint", "0 errors · 3 warnings preexistentes · exit 0"],
], col_widths=[3.0*inch, 3.6*inch]))

# ── 7. Próxima acción mínima ───────────────────────────────────────────

story.append(H1("7. Próxima acción mínima · espera tu OK"))

story.append(BANNER(
    "<b>Plan ordenado · cada paso espera aprobación explícita.</b>"
))

story.append(make_table([
    ["#", "Acción", "Quién", "Riesgo", "Estado"],
    ["1",
     "Mergear <i>diag/auth-instrumentation</i> a main",
     "Owner",
     "Bajo · cambios cubiertos por 22 tests · default OFF",
     "<b>Espera tu OK</b>"],
    ["2",
     "Setear <i>AUTH_DIAG=1</i> en Vercel · Production scope",
     "Owner (Vercel UI)",
     "Cero · solo activa logs, no toca lógica",
     "Espera"],
    ["3",
     "Trigger redeploy o esperar autodeploy del merge",
     "Vercel auto / Owner",
     "Cero",
     "Espera"],
    ["4",
     "Usuario afectado intenta login una vez",
     "Owner coordina",
     "Cero",
     "Espera"],
    ["5",
     "Yo (Claude) leo los nuevos logs <i>[AUTH_DIAG] {...}</i> "
     "via vercel CLI · doy veredicto: causa #1, #2 o #3",
     "Yo",
     "Cero · solo lectura",
     "Espera"],
    ["6",
     "Quitar <i>AUTH_DIAG</i> de Vercel + PR de cleanup que borre "
     "la instrumentación temporal",
     "Owner + Yo",
     "Cero",
     "Espera"],
], col_widths=[0.3*inch, 3.0*inch, 1.0*inch, 1.5*inch, 0.8*inch]))

# ── 8. Cero writes ─────────────────────────────────────────────────────

story.append(H1("8. Confirmaciones de esta sesión"))

story.append(BANNER(
    "<b>NO se ejecutó:</b><br/>"
    "&bull; Stripe writes <br/>"
    "&bull; DB writes <br/>"
    "&bull; Cambios de variables de entorno (Vercel ni Render) <br/>"
    "&bull; Deploys manuales <br/>"
    "&bull; Envíos reales de WhatsApp ni email <br/>"
    "&bull; Stripe API queries <br/>"
    "&bull; Recovery manual con scripts/derive-dashboard-password.ts <br/>"
    "&bull; Merge a main <br/>"
    "&bull; <i>vercel redeploy</i> ni cualquier comando vercel "
    "que escriba en proyecto"
))

story.append(P(
    "<b>SÍ ejecuté</b>: <i>vercel whoami</i>, <i>vercel ls</i>, "
    "<i>vercel inspect</i>, <i>vercel logs --no-follow</i>. "
    "Todos read-only · ninguno modifica el proyecto."
))


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
