"""
Genera Resumen_Incidente_Login_Multi_Customer_2026-05-02.pdf · diagnóstico
read-only y hotfix propuesto para el incidente de login post-pago.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_Incidente_Login_Multi_Customer_2026-05-02.pdf"

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

story.append(Paragraph("INCIDENTE · Login muestra 'suscripción no activa' a usuarios con plan pago",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-02 · Severidad <b>P0/P1</b> · "
    "Branch <b>hotfix/auth-multi-customer-match</b> · Base "
    "<b>main@84466d9</b> · <b>Modo: read-only diagnóstico + hotfix "
    "en rama, sin merge</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Estado:</b> Causa raíz identificada en el código (sin "
    "necesidad de Stripe API porque el bug es estático). Hotfix "
    "implementado en rama, <b>12/12 tests passing</b>, tsc/build/"
    "lint verdes. <b>NO mergeado · NO desplegado · CERO writes</b> "
    "a Stripe/DB/env/WhatsApp/email."
))

# ── 1. Causa raíz ──────────────────────────────────────────────────────

story.append(H1("1. Causa raíz · DOS bugs combinados en landing/auth.ts"))

story.append(H2("Bug A · customers.list({ email, limit: 1 })"))

story.append(P(
    "Stripe permite tener <b>varios customers con el mismo email</b>. "
    "Esto pasa naturalmente cuando un usuario hace checkout sin estar "
    "logueado, lo que ocurre cada vez que vuelve al landing y paga "
    "de nuevo (Customer Portal de Stripe a veces crea uno nuevo si "
    "el flow lo permite). El código previo (<i>auth.ts:24</i>):"
))

story.append(CODE(
    "const customers = await getStripe().customers.list({\n"
    "  email,\n"
    "  limit: 1,\n"
    "});\n"
    "if (customers.data.length === 0) return null;\n"
    "const customer = customers.data[0];"
))

story.append(P(
    "<b>Solo mira el primer customer</b> que Stripe devuelve. Si la "
    "suscripción activa quedó en otro customer (más nuevo), el login "
    "rechaza al usuario aunque sí tenga plan pago."
))

story.append(H2("Bug B · subscriptions.list filtrando solo status='active'"))

story.append(CODE(
    "const subscriptions = await getStripe().subscriptions.list({\n"
    "  customer: customer.id,\n"
    "  status: 'active',\n"
    "  limit: 1,\n"
    "});\n"
    "if (subscriptions.data.length === 0) return null;"
))

story.append(P(
    "<b>Trialing</b> (trial vigente) y <b>past_due</b> (pago falló "
    "pero sub aún no cancelada) quedan fuera. Past_due es "
    "particularmente peligroso porque es el estado donde el "
    "Customer Portal sirve para que el usuario actualice su "
    "tarjeta — al cerrarles el dashboard, lo único que pueden hacer "
    "es escribir al soporte."
))

story.append(H2("Bug C · UX del mensaje de error"))

story.append(P(
    "<i>app/login/page.tsx</i> traducía CUALQUIER fallo del "
    "<i>authorize</i> (sin customer · password incorrecto · sub no "
    "encontrada · email vacío) al mismo mensaje:"
))

story.append(CODE(
    "Tu suscripción no está activa.\n"
    "Selecciona un plan para continuar.\n"
    "[Ver planes disponibles] → /#pricing"
))

story.append(P(
    "<b>Empuja a pagar de nuevo</b> a usuarios que YA pagaron. "
    "Doble cobro accidental como riesgo secundario."
))

# ── 2. Validación del password ─────────────────────────────────────────

story.append(H1("2. ¿El password se valida?"))

story.append(P(
    "<b>Sí.</b> En <i>auth.ts:38-41</i> previo al hotfix:"
))

story.append(CODE(
    "const expected = deriveDashboardPassword(customer.id);\n"
    "if (!expected || !constantTimeEqual(password, expected)) {\n"
    "  return null;\n"
    "}"
))

story.append(P(
    "Validación correcta y en tiempo constante (T1.4.B). El password "
    "se deriva con HMAC-SHA256(customer_id, "
    "DASHBOARD_PASSWORD_SECRET) → primer 12 chars hex con prefijo "
    "<i>dona-</i>. <b>El password NO se ignora.</b> Pero la "
    "validación ocurría sobre el customer EQUIVOCADO (el primero "
    "que Stripe devolvió)."
))

# ── 3. Diagnóstico Stripe API ─────────────────────────────────────────

story.append(H1("3. Diagnóstico Stripe API"))

story.append(WARN(
    "<b>No ejecutado:</b> <i>STRIPE_SECRET_KEY</i> no está disponible "
    "en el entorno local del verificador (las claves vivien en "
    "Vercel/Render, no en el repo). Esto es lo correcto · cumple la "
    "instrucción del incidente: no revelar tokens."
))

story.append(P(
    "Si quieres confirmar la cantidad real de customers para "
    "<i>celestinojbm@gmail.com</i>, ejecutar tú localmente con "
    "STRIPE_SECRET_KEY del dashboard de Stripe:"
))

story.append(CODE(
    "# Listar todos los customers con ese email (read-only)\n"
    "stripe customers list --email celestinojbm@gmail.com --limit 100\n"
    "\n"
    "# Para cada cus_XXX devuelto, listar TODAS sus subs\n"
    "stripe subscriptions list --customer cus_XXX --status all"
))

story.append(P(
    "Esperado según la hipótesis: ≥2 customers, donde la sub <i>active</i> "
    "está en uno distinto al que <i>customers.list({email,limit:1})</i> "
    "devolvía primero. <b>Importante: solo el owner debe correr esto · "
    "no compartir output con tokens/IDs completos.</b>"
))

# ── 4. Hotfix implementado ──────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Hotfix implementado en la rama"))

story.append(make_table([
    ["Archivo", "Cambio"],
    ["landing/lib/auth-matcher.ts", "<b>NUEVO</b> · función pura "
     "<i>encontrarCustomerConSub</i> con dependencias inyectables. "
     "Itera limit:100, valida password contra cada candidato, "
     "acepta active/trialing/past_due."],
    ["landing/lib/auth-matcher.test.ts", "<b>NUEVO</b> · 12 tests "
     "con stubs de Stripe (sin tocar API real)."],
    ["landing/auth.ts", "Reemplazado el authorize por una "
     "delegación al matcher. Side-effect positivo: limpiados los "
     "<i>(user as any)</i> de los callbacks JWT/session."],
    ["landing/app/login/page.tsx", "Mensaje neutral · CTA cambia "
     "de '/#pricing' a 'mailto:hola@usadona.com' (no empuja a "
     "pagar de nuevo)."],
    ["landing/package.json", "+ scripts <i>test</i> y "
     "<i>test:watch</i> · + devDep <i>vitest@^2.1.9</i>."],
    ["landing/vitest.config.ts", "<b>NUEVO</b> · resolve alias '@' "
     "para imports tipo '@/lib/...' · include lib/**/*.test.ts."],
], col_widths=[2.4*inch, 4.2*inch]))

story.append(H2("Diff conceptual del authorize"))

story.append(CODE(
    "# Antes\n"
    "customers.list({ email, limit: 1 })\n"
    "  → customer = data[0]\n"
    "validate password against customer\n"
    "subscriptions.list({ customer, status: 'active' })\n"
    "  → sub = data[0]\n"
    "\n"
    "# Después (hotfix)\n"
    "customers.list({ email, limit: 100 })\n"
    "for each customer in data:\n"
    "  if deleted or email mismatch: skip\n"
    "  expected = derivePassword(customer.id)\n"
    "  if password != expected: continue\n"
    "  subs = subscriptions.list({ customer, status: 'all' })\n"
    "  sub = first sub with status in {active, trialing, past_due}\n"
    "  if sub: return { customer, subscription: sub }\n"
    "return null"
))

# ── 5. Tests ────────────────────────────────────────────────────────────

story.append(H1("5. Tests ejecutados"))

story.append(BANNER(
    "<b>npm test</b> · <b>12/12 passing</b> · 336ms · vitest@2.1.9"
))

story.append(make_table([
    ["#", "Test", "Cubre"],
    ["1", "email sin customers → null", "Sanity baseline"],
    ["2", "1 customer con sub canceled → null",
     "Política · canceled NO autoriza"],
    ["3", "<b>2 customers, sub activa en el segundo → match</b>",
     "<b>Caso real del incidente</b>"],
    ["4", "password incorrecto en cus_1, correcto en cus_2 → match cus_2",
     "Iteración respeta password por customer"],
    ["5", "sub trialing → autorizada", "Política · trialing OK"],
    ["6", "sub past_due → autorizada",
     "Política · past_due OK · UX dashboard ofrece Customer Portal"],
    ["7", "sub incomplete → rechazada",
     "Política · incomplete NO autoriza"],
    ["8", "customer deleted → saltado",
     "No considera customers borrados"],
    ["9", "DASHBOARD_PASSWORD_SECRET ausente → null",
     "Sin secret no hay path permisivo"],
    ["10", "email vacío → null", "Validación de input"],
    ["11", "password vacío → null", "Validación de input"],
    ["12", "ESTADOS_SUB_VALIDOS = active+trialing+past_due",
     "Locked spec del set válido"],
], col_widths=[0.3*inch, 3.3*inch, 3.0*inch]))

# ── 6. Validaciones complementarias ────────────────────────────────────

story.append(H1("6. Validaciones complementarias"))

story.append(make_table([
    ["Comando (cwd: landing/)", "Resultado"],
    ["npx tsc --noEmit", "<b>0 errores</b> · exit 0"],
    ["rm -rf .next && npm run build", "<b>OK</b> · 17/17 pages · "
     "static + dynamic"],
    ["npm run lint", "<b>3 warnings · 0 errors · exit 0</b> "
     "(antes: 6 errors + 3 warnings · exit 1) · los 6 errors de "
     "<i>any</i> en auth.ts se limpiaron al refactorizar"],
    ["npm test", "<b>12/12 passing</b> · vitest@2.1.9"],
], col_widths=[3.4*inch, 3.2*inch]))

story.append(H2("Sobre las dependencias agregadas"))

story.append(P(
    "Solo <b>vitest@^2.1.9</b> como devDependency. <i>npm audit</i> "
    "reporta 6 moderate (esbuild/vite chain · solo dev server, no "
    "afecta bundle prod) y 1 high preexistente en Next.js 16.2.2 "
    "(no relacionado con el hotfix). <b>No se ejecutó "
    "<i>audit fix --force</i></b> para no introducir cambios "
    "ortogonales."
))

# ── 7. Confirmaciones de no-write ──────────────────────────────────────

story.append(H1("7. Confirmaciones explícitas (sin writes)"))

story.append(BANNER(
    "<b>NO se ejecutó nada de esto:</b><br/>"
    "&bull; Stripe writes (customers.update, subscriptions.cancel, refund, "
    "delete...) <br/>"
    "&bull; DB writes (Render Postgres / SQLite) · de hecho ni siquiera "
    "se conectó al backend Render <br/>"
    "&bull; Cambios de variables de entorno (Vercel / Render / "
    ".env local) <br/>"
    "&bull; Deploys manuales (Vercel / Render) <br/>"
    "&bull; Envíos de WhatsApp (Whapi / Meta / Twilio) <br/>"
    "&bull; Envíos de email <br/>"
    "&bull; <i>git push --force</i>, <i>git reset --hard</i>, ni merge "
    "a main"
))

# ── 8. Riesgos ─────────────────────────────────────────────────────────

story.append(H1("8. Riesgos del hotfix"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["customers.list devuelve N&gt;100 y el verdadero está en "
     "página 2",
     "Bajo",
     "Stripe rara vez tiene 100+ customers con el mismo email · "
     "si pasa el owner debe consolidar duplicados · podemos "
     "agregar paginación auto-iterada en otro PR si se necesita."],
    ["Iterar customers multiplica latencia del login · "
     "N llamadas a subscriptions.list",
     "Bajo · perf",
     "Promedio esperado N=1-3. Worst case con 100 customers: "
     "~100×0.2s ≈ 20s, pero solo ocurre una vez por sesión "
     "JWT · invocaciones siguientes leen del token."],
    ["Aceptar past_due abre login a usuarios cuyo pago falló",
     "Cero · es la política deseada",
     "El dashboard tiene banner 'Pago atrasado' y CTA "
     "'Gestionar facturación' que abre el portal de Stripe "
     "(T1.5) para que actualicen tarjeta. Cerrarles el "
     "dashboard era el bug, no la solución."],
    ["Side-effect: cambio del mensaje de error podría confundir a "
     "usuarios que NO pagaron",
     "Bajo · UX",
     "El mensaje sigue diciendo 'No pudimos validar tu acceso' y "
     "'si ya pagaste'. Usuarios que no pagaron al hacer login "
     "obtienen el mismo CTA a soporte y se les puede orientar."],
    ["Vulnerabilidades npm audit nuevas",
     "Cero",
     "Vitest se usa solo en CI/local · esbuild/vite "
     "vulnerabilities afectan dev server, no bundle de "
     "producción · no entran al artifact desplegado."],
    ["Refactor del any de callbacks rompe NextAuth",
     "Cero",
     "tsc 0 errores · build 17/17 OK · NextAuth strategy='jwt' "
     "sin cambios · tipos del token son los mismos."],
], col_widths=[2.8*inch, 1.1*inch, 2.7*inch]))

# ── 9. Próximos pasos ──────────────────────────────────────────────────

story.append(H1("9. Próximos pasos · pendientes de tu aprobación"))

story.extend(bullets([
    "<b>Tú</b>: revisar código de la rama "
    "<i>hotfix/auth-multi-customer-match</i> y ejecutar el "
    "comando <i>stripe</i> CLI de la sección 3 con tu "
    "STRIPE_SECRET_KEY <b>solo si quieres confirmar</b> que tu "
    "cuenta tiene 2+ customers (el fix es válido aunque no se "
    "confirme · el bug es estático).",
    "<b>Tú</b>: aprobar abrir PR contra main. La rama está "
    "pushed pero <b>no creé PR</b> (mismo issue de tokens "
    "vacíos que en T2.0.D · GH_TOKEN/GITHUB_TOKEN len=0).",
    "<b>Tú</b>: tras merge, redeploy automático Vercel y "
    "validar login con el usuario afectado en producción.",
    "<b>Tú</b>: si el hotfix funciona en prod, considerar PR "
    "follow-up para consolidar duplicados de customer en "
    "Stripe (tema de housekeeping, no funcional).",
]))

story.append(BANNER(
    "<b>Hotfix listo para review.</b> Cero merges, cero "
    "deploys. Tests verdes. Causa raíz documentada. UX "
    "mejorada. Side-effect: lint exit 0 (antes 1)."
))


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
