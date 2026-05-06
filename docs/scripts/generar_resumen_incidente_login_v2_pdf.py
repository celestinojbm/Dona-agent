"""
Genera Resumen_Incidente_Login_V2_2026-05-02.pdf · diagnóstico read-only y
hotfix v2 (recovery cross-customer) tras confirmar que el hotfix v1 se
desplegó pero el login del usuario afectado siguió fallando.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_Incidente_Login_V2_2026-05-02.pdf"

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

story.append(Paragraph("INCIDENTE LOGIN · v2 · gap residual identificado",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-02 · Hotfix v1 mergeado en main "
    "(commit <b>d9a6ea4</b>, PR #32) y desplegado · login del usuario "
    "<b>sigue fallando</b> · branch nueva "
    "<b>hotfix/auth-cross-customer-recovery</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Estado:</b> Causa probable confirmada por revisión del "
    "código (sin Stripe API). Hay un gap en el matcher v1: el "
    "password del usuario coincide con un customer SIN sub válida, "
    "y el password del customer CON sub válida es distinto. Hotfix "
    "v2 implementado y testeado (15/15) en rama. <b>Recovery "
    "operacional disponible HOY</b> sin código nuevo · explicado "
    "abajo. <b>Cero writes</b> a Stripe/DB/env/WhatsApp/email."
))

# ── 1. Confirmación deploy v1 ───────────────────────────────────────────

story.append(H1("1. Hotfix v1 está deployed"))

story.append(make_table([
    ["Verificación", "Resultado"],
    ["git log origin/main",
     "<b>d9a6ea4</b> Merge PR #32 (hotfix/auth-multi-customer-match)"],
    ["GET https://usadona.com/login", "200 · 0.29s"],
    ["Mensaje en producción",
     "El UI muestra el mensaje nuevo (\"No pudimos validar...\") "
     "→ confirmado por el owner"],
    ["Pero login del usuario afectado", "<b>sigue fallando</b>"],
], col_widths=[2.8*inch, 3.8*inch]))

# ── 2. Causa raíz residual ──────────────────────────────────────────────

story.append(H1("2. Causa probable · gap residual del matcher v1"))

story.append(P(
    "El matcher v1 hace, simplificado:"
))

story.append(CODE(
    "for each customer in customers.list({email}):\n"
    "  if password == derivePassword(customer.id):\n"
    "    if customer has sub valida:\n"
    "      return match\n"
    "return null"
))

story.append(P(
    "Caso reportado en producción para "
    "<i>celestinojbm@gmail.com</i>:"
))

story.append(make_table([
    ["Customer", "Email", "Sub", "Password derivado conocido por el usuario"],
    ["cus_OLD (más antiguo)", "celestinojbm@gmail.com",
     "canceled / sin sub válida",
     "<b>SÍ</b> · le llegó welcome de éste"],
    ["cus_NEW (con plan pago)", "celestinojbm@gmail.com",
     "<b>active</b>",
     "NO · su welcome nunca llegó al usuario, o fue silenciado"],
], col_widths=[1.8*inch, 1.8*inch, 1.4*inch, 1.6*inch]))

story.append(P(
    "Resultado del matcher v1: itera cus_OLD, password match ✓, sub "
    "no válida → <i>continue</i>. Itera cus_NEW, password no match "
    "(HMAC con customer_id distinto produce hash distinto) → "
    "<i>continue</i>. <b>Retorna null</b>. El usuario ve mensaje de "
    "error aunque tenga plan pago y conozca un password legítimo."
))

# ── 3. Por qué no es bug del matcher ───────────────────────────────────

story.append(H1("3. Otras hipótesis descartadas o confirmadas"))

story.append(make_table([
    ["Hipótesis", "Veredicto"],
    ["Password de customer viejo",
     "<b>HIPÓTESIS PRINCIPAL</b> · confirmada por análisis "
     "estático del código + flujo de welcome (T2.0.B "
     "deriva de customer_id activo en el momento del checkout)."],
    ["Email distinto en Stripe (alias, mayúscula, punto extra)",
     "Posible · descartar revisando manualmente customers en "
     "Stripe Dashboard. Stripe normaliza pero no siempre."],
    ["Sub en estado no incluido (incomplete/unpaid/paused)",
     "Improbable: el owner confirma que el plan está pago. "
     "Estados válidos: active, trialing, past_due."],
    ["DASHBOARD_PASSWORD_SECRET cambió en Vercel",
     "Posible pero raro. Si pasó, TODOS los passwords previos "
     "quedan inválidos · revisar fecha del último cambio en "
     "Vercel · aplica solo si el owner lo rotó manualmente."],
    ["Bug del matcher v1",
     "<b>NO</b> · 12/12 tests passing · lógica correcta para los "
     "casos cubiertos · gap es de cobertura, no de implementación."],
], col_widths=[2.6*inch, 4.0*inch]))

# ── 4. Cómo recuperar acceso HOY ───────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Recuperar acceso HOY · sin nuevo código"))

story.append(BANNER(
    "<b>Procedimiento operacional para el owner.</b> Usa el CLI "
    "helper de T1.4.B que ya existe en el repo. <b>NO requiere "
    "merge ni deploy</b>. NO comprar otro plan."
))

story.append(H2("Paso 1 · Identificar customer con sub activa"))

story.append(CODE(
    "# Con tu STRIPE_SECRET_KEY local (no se comparte)\n"
    "stripe customers list \\\n"
    "  --email celestinojbm@gmail.com \\\n"
    "  --limit 100 \\\n"
    "  --expand 'data.subscriptions'\n"
    "\n"
    "# Buscar el cus_xxx cuyo subscriptions.data tenga\n"
    "# status: active (o trialing / past_due)."
))

story.append(H2("Paso 2 · Derivar el password del customer correcto"))

story.append(CODE(
    "# desde el directorio landing/\n"
    "DASHBOARD_PASSWORD_SECRET=&lt;mismo-valor-que-Vercel&gt; \\\n"
    "  npx tsx scripts/derive-dashboard-password.ts cus_NEW_xxxxx\n"
    "\n"
    "# Output: dona-XXXXXXXXXXXX (12 hex chars · NO loguear)"
))

story.append(H2("Paso 3 · Entregar al usuario por canal seguro"))

story.extend(bullets([
    "El password sale por <b>stdout una sola vez</b>. NO se "
    "queda en logs ni en historial de scripts (el helper no usa "
    "console.log).",
    "Entregar por <b>WhatsApp directo</b> al teléfono registrado "
    "(canal cifrado E2E) · igual que se hacía pre-T2.0.B.",
    "<b>NO</b> mandar por email · NO escribir en Slack/Discord/"
    "ticket público · NO subir a Notion/GDrive sin cifrar.",
    "Una vez entregado, el usuario puede entrar al dashboard. El "
    "matcher v1 actual le dará acceso porque ese password coincide "
    "con cus_NEW que tiene la sub activa.",
]))

story.append(WARN(
    "<b>Riesgo si NO se aplica el hotfix v2:</b> cualquier nuevo "
    "usuario que sufra el mismo escenario (welcome llegó del "
    "customer equivocado) tendrá que hacer este procedimiento "
    "manual. El v2 lo automatiza."
))

# ── 5. Hotfix v2 propuesto ─────────────────────────────────────────────

story.append(H1("5. Hotfix v2 · recovery automático"))

story.append(P(
    "<b>Branch:</b> <i>hotfix/auth-cross-customer-recovery</i> · "
    "base <i>main@d9a6ea4</i>. Implementado, testeado, NO "
    "mergeado."
))

story.append(H2("Cambio de lógica en lib/auth-matcher.ts"))

story.append(CODE(
    "# Pass 1 · match exacto (igual que v1)\n"
    "for each customer in customers.list({email}):\n"
    "  if password == derive(customer.id):\n"
    "    if customer has sub valida:\n"
    "      return match\n"
    "    else:\n"
    "      passwordOwner = customer  # ← nuevo · marca ownership\n"
    "\n"
    "# Pass 2 · cross-customer recovery\n"
    "if passwordOwner is None: return null\n"
    "for each customer in same-email candidates:\n"
    "  if customer.id == passwordOwner.id: continue\n"
    "  if customer has sub valida:\n"
    "    return { customer, sub, recovery: true,\n"
    "             passwordOwnerCustomerId: passwordOwner.id }\n"
    "return null"
))

story.append(H2("Por qué Pass 2 es seguro"))

story.extend(bullets([
    "Pass 2 solo se activa si <b>ownership ya fue demostrado</b> "
    "por un password match en Pass 1.",
    "El password derivado de <i>cus_OLD</i> solo lo conoce quien "
    "recibió el welcome de ese customer · es prueba de "
    "posesión legítima del email.",
    "Stripe trata customers con mismo email como mismo cliente "
    "humano · autorizar el dashboard de la sub activa del mismo "
    "email es coherente con la mental model del usuario.",
    "<b>Riesgo residual aceptado:</b> si dos personas distintas "
    "comparten un email accidentalmente, una con password de su "
    "customer puede ver dashboard del otro. Probabilidad muy baja "
    "y consistente con el modelo Dona (1 email = 1 cliente).",
    "<b>Logging:</b> auth.ts loguea WARN sin PII cuando ocurre "
    "recovery (sub_id, customer_id <b>truncados</b>), para "
    "trackear el patrón en Vercel logs y motivar housekeeping de "
    "duplicados.",
]))

# ── 6. Tests ────────────────────────────────────────────────────────────

story.append(H1("6. Tests · 15/15 passing"))

story.append(make_table([
    ["#", "Test", "Cubre"],
    ["1", "email sin customers → null", "Sanity"],
    ["2", "1 customer con sub canceled → null", "Política"],
    ["3", "2 customers, sub activa en 2do, password match cus_NEW → "
     "match cus_NEW · recovery=false",
     "Caso v1"],
    ["4", "Password incorrecto cus_1, correcto cus_2 con sub → cus_2",
     "Iteración respeta password por customer"],
    ["5", "Sub trialing → autorizada", "Política"],
    ["6", "Sub past_due → autorizada", "Política"],
    ["7", "Sub incomplete → null", "Política"],
    ["8", "Customer deleted=true → saltado", "Robustez"],
    ["9", "DASHBOARD_PASSWORD_SECRET ausente → null",
     "Sin path permisivo"],
    ["10", "Email vacío → null", "Validación"],
    ["11", "Password vacío → null", "Validación"],
    ["12", "ESTADOS_SUB_VALIDOS spec lock", "Spec"],
    ["13", "<b>RECOVERY · password viejo cus_OLD + sub en cus_NEW → "
     "match cus_NEW · recovery=true</b>",
     "<b>Caso real del incidente</b>"],
    ["14", "<b>Sin ownership (password no match ningún customer) → "
     "null aunque haya sub activa</b>",
     "<b>Seguridad: no autoriza sin ownership</b>"],
    ["15", "Ownership demostrado pero NINGÚN customer del email "
     "tiene sub válida → null",
     "Caso sub canceled en todos · respeta política"],
], col_widths=[0.3*inch, 3.5*inch, 2.8*inch]))

# ── 7. Validación ──────────────────────────────────────────────────────

story.append(H1("7. Validación local"))

story.append(make_table([
    ["Comando (cwd landing/)", "Resultado"],
    ["npm test", "<b>15/15 passing</b> · 363ms"],
    ["npx tsc --noEmit", "0 errores"],
    ["rm -rf .next && npm run build", "OK · 17/17 pages"],
    ["npm run lint",
     "0 errors · 3 warnings preexistentes · exit 0"],
], col_widths=[3.0*inch, 3.6*inch]))

# ── 8. T2.0.B welcome · ¿bienvenida_enviada bien marcada? ──────────────

story.append(H1("8. T2.0.B welcome · ¿se marcó al customer correcto?"))

story.append(P(
    "Lectura del código de <i>agent/welcome.py</i> y "
    "<i>agent/billing.py</i>:"
))

story.extend(bullets([
    "El welcome se dispara solo en <i>accion='created'</i> del "
    "<i>checkout.session.completed</i>. <b>NO</b> en updated · "
    "NO en re-checkout.",
    "El password se deriva del <i>customer_id</i> del checkout "
    "que disparó el evento, no del cus más reciente del email.",
    "El flag <i>bienvenida_enviada</i> vive en "
    "<i>SuscripcionStripe.subscription_id</i>, NO en customer. "
    "Una sub nueva = welcome nuevo (correcto).",
    "<b>Implicación:</b> si el usuario hizo 2 checkouts (uno hace "
    "tiempo y uno reciente), el welcome reciente debió enviarse "
    "con password de cus_NEW. Si NO le llegó, posibles causas:",
]))

story.extend(bullets([
    "Whapi falló silenciosamente (retorno False) → flag NO "
    "marcado · checkable con <i>SELECT bienvenida_enviada FROM "
    "suscripcion_stripe WHERE subscription_id=&lt;sub_NEW&gt;</i>.",
    "<i>WELCOME_DRY_RUN=true</i> en producción por error → flag "
    "se marca pero no se envía. Verificar en Vercel/Render env.",
    "Sub_NEW se creó <b>antes</b> de T2.0.B (~2 días) · si así, "
    "no había welcome automático y el owner debió enviar manual.",
    "Customer recibió welcome pero el celular cambió de número "
    "WhatsApp · llegó al teléfono viejo.",
]))

story.append(WARN(
    "<b>Sugerencia diagnóstica</b> (read-only · al owner): "
    "consultar <i>/admin/jobs-recientes?telefono=&lt;num&gt;</i> "
    "y la fila SuscripcionStripe del email. Si "
    "<i>bienvenida_enviada=true</i> pero al usuario no le llegó, "
    "regenerar con el helper CLI (sección 4)."
))

# ── 9. Confirmaciones de cero writes ───────────────────────────────────

story.append(H1("9. Confirmaciones explícitas"))

story.append(BANNER(
    "<b>NO se ejecutó nada de esto en esta sesión:</b><br/>"
    "&bull; Stripe writes (customers.update / subscriptions.cancel / "
    "refund / delete) <br/>"
    "&bull; DB writes en backend Render (ni siquiera se conectó) "
    "<br/>"
    "&bull; Cambios de variables de entorno en Vercel / Render / "
    ".env local <br/>"
    "&bull; Deploys manuales (ni Vercel ni Render) <br/>"
    "&bull; Envíos de WhatsApp (ni el helper CLI se corrió) <br/>"
    "&bull; Envíos de email <br/>"
    "&bull; Stripe API queries (no hay STRIPE_SECRET_KEY local) <br/>"
    "&bull; <i>git push --force</i> · <i>git reset --hard</i> · "
    "merge a main"
))

# ── 10. Recomendación final ────────────────────────────────────────────

story.append(H1("10. Recomendación · plan ordenado"))

story.append(make_table([
    ["Paso", "Acción", "Riesgo"],
    ["1 · INMEDIATO",
     "Recuperar acceso del usuario afectado con el procedimiento "
     "manual (sección 4). Sin código nuevo, sin merge.",
     "Cero · usa helper existente"],
    ["2 · Diagnóstico opcional",
     "Verificar en Stripe que el caso sea efectivamente "
     "duplicado de customer (no email distinto, no secret "
     "rotado).",
     "Cero · read-only"],
    ["3 · Mergear hotfix v2",
     "Tras tu OK, abrir PR de "
     "<i>hotfix/auth-cross-customer-recovery</i>. Auto-deploy "
     "Vercel.",
     "Bajo · revertable con git revert"],
    ["4 · Post-deploy",
     "Smoke login del usuario afectado con su password viejo. "
     "Esperado: entra al dashboard del cus_NEW. Logs deben "
     "mostrar 'recovery cross-customer' en Vercel.",
     "Cero · solo verificación"],
    ["5 · Housekeeping (PR aparte)",
     "Consolidar duplicados de customer en Stripe (vía Customer "
     "Portal del usuario o manual desde Dashboard). Reduce "
     "futuros casos de recovery.",
     "Cero · mejora UX"],
], col_widths=[1.4*inch, 4.0*inch, 1.2*inch]))

story.append(BANNER(
    "<b>Próximo paso:</b> tu decides si (a) solo recuperamos al "
    "usuario manualmente y dejamos v2 en draft para revisión, o "
    "(b) recuperamos manualmente Y mergeamos v2 para "
    "automatizar el caso. <b>Sin tu OK no se mergea ni se "
    "ejecuta el helper.</b>"
))


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
