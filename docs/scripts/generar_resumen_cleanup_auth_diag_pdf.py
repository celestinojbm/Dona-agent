"""
Genera Resumen_Cleanup_Auth_Diag_2026-05-08.pdf · resumen del PR de
cleanup que retira la instrumentación temporal AUTH_DIAG/[AUTH_DIAG] tras
resolución del incidente de login (causa: DASHBOARD_PASSWORD_SECRET en
Render tenía un valor placeholder en vez del secret largo).
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_Cleanup_Auth_Diag_2026-05-08.pdf"

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

story.append(Paragraph("Cleanup · retiro de instrumentación temporal AUTH_DIAG",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-08 · Branch "
    "<b>cleanup/auth-instrumentation-retiro</b> · base "
    "<b>main@9949da9</b> · login resuelto · "
    "<i>AUTH_DIAG ya removida del Vercel env</i>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> PR de cleanup listo para abrir. <b>15/15 tests "
    "passing · tsc 0 errores · build 17/17 OK · lint 0 errors</b>. "
    "Lógica de login (Pass 1 / Pass 2 cross-customer recovery) "
    "<b>intacta</b>. Solo se retira la telemetría temporal."
))

# ── 1. Causa raíz del incidente · resuelta ─────────────────────────────

story.append(H1("1. Causa raíz del incidente · resuelta"))

story.append(P(
    "Tras la activación de <i>AUTH_DIAG=1</i> y la lectura de "
    "telemetría con campos seguros, el diagnóstico llevó a:"
))

story.append(make_table([
    ["Hipótesis", "Veredicto"],
    ["v1 · password no matchea ningún customer",
     "Confirmada por <i>passwordMatchedAnyCustomer:false · "
     "nullReason:no_password_match</i>"],
    ["¿Por qué? wrong customer",
     "Descartada · ninguno de los 5 cus_xxx autorizó"],
    ["¿Por qué? secret_local ≠ secret_server",
     "Confirmada · pero el bug específico fue otro"],
    ["<b>Causa final</b>",
     "<b>Render tenía DASHBOARD_PASSWORD_SECRET con un valor "
     "placeholder <i>dona-...</i> (en vez del secret largo "
     "real)</b>. El welcome backend usaba ese placeholder para "
     "derivar passwords · Vercel usaba el secret correcto al "
     "validar · HMAC distinto · login rechazaba todo."],
    ["Fix aplicado por owner",
     "Igualó <i>DASHBOARD_PASSWORD_SECRET</i> en Render con el "
     "valor de Vercel · redeploy · <b>login funcionó</b>"],
], col_widths=[2.4*inch, 4.2*inch]))

# ── 2. Cambios del PR ──────────────────────────────────────────────────

story.append(H1("2. Cambios del PR de cleanup"))

story.append(make_table([
    ["Archivo", "Cambio"],
    ["landing/auth.ts",
     "Retira el bloque <i>diagOn</i> y el callback "
     "<i>onTelemetry</i>. La invocación al matcher queda con las "
     "4 dependencias originales. <b>Mantiene</b> el log "
     "operacional <i>[AUTH] recovery cross-customer</i> · ése es "
     "monitoring permanente, no instrumentación temporal."],
    ["landing/lib/auth-matcher.ts",
     "Retira: tipo <i>AuthTelemetry</i>, campo <i>onTelemetry</i> "
     "de <i>AuthMatcherDeps</i>, variable local <i>tel</i>, "
     "función <i>emit()</i>, todas las asignaciones a campos de "
     "telemetría y los <i>nullReason</i>. <b>Mantiene</b>: "
     "<i>ESTADOS_SUB_VALIDOS</i>, <i>AuthMatch</i>, "
     "<i>AuthMatcherDeps</i> (sin onTelemetry), <i>encontrar"
     "CustomerConSub</i> con su lógica Pass 1/Pass 2 inalterada."],
    ["landing/lib/auth-matcher.test.ts",
     "Retira el bloque <b>describe('encontrarCustomerConSub · "
     "telemetría')</b> con sus 7 tests. <b>Mantiene</b> los 15 "
     "tests originales que validan lógica Pass 1/Pass 2 + casos "
     "edge."],
], col_widths=[2.4*inch, 4.2*inch]))

# ── 3. Lo que NO se toca ───────────────────────────────────────────────

story.append(H1("3. Lo que el PR NO toca · invariantes preservadas"))

story.extend(bullets([
    "<b>Lógica del matcher</b>: las dos pasadas (Pass 1 match "
    "exacto, Pass 2 recovery cross-customer) y los retornos "
    "<i>{customer, subscription, recovery, "
    "passwordOwnerCustomerId}</i> son idénticos byte por byte "
    "respecto a la versión actual menos la telemetría.",
    "<b>Filtros</b>: <i>esCustomerActivo</i>, comparación "
    "case-sensitive de email, lista de estados válidos "
    "(<i>active/trialing/past_due</i>) sin cambios.",
    "<b>NextAuth · authorize</b>: mismo shape de retorno · "
    "callbacks <i>jwt</i> y <i>session</i> sin modificación · "
    "<i>session: { strategy: \"jwt\" }</i>.",
    "<b>Helper CLI</b> "
    "<i>landing/scripts/derive-dashboard-password.ts</i>: "
    "intacto · sigue disponible para futuros recoveries.",
    "<b>Log permanente</b> <i>[AUTH] recovery cross-customer</i> "
    "(en auth.ts cuando <i>match.recovery=true</i>) · es "
    "operacional · útil para detectar duplicados de customer · "
    "se conserva.",
    "<b>Variables de entorno</b>: el PR no toca env vars · "
    "<i>AUTH_DIAG</i> ya está removida de Vercel por el owner.",
]))

# ── 4. Validación local ────────────────────────────────────────────────

story.append(H1("4. Validación local"))

story.append(make_table([
    ["Comando (cwd landing/)", "Resultado"],
    ["npm test", "<b>15/15 passing</b> · vitest@2.1.9 · 423ms"],
    ["npx tsc --noEmit", "0 errores · exit 0"],
    ["rm -rf .next && npm run build",
     "OK · 17/17 pages · static + dynamic"],
    ["npm run lint",
     "<b>0 errors · 3 warnings preexistentes · exit 0</b>"],
], col_widths=[3.2*inch, 3.4*inch]))

# ── 5. Confirmaciones · cero side-effects ──────────────────────────────

story.append(H1("5. Confirmaciones · 100% cleanup local"))

story.append(BANNER(
    "<b>NO se ejecutó:</b><br/>"
    "&bull; Stripe writes / DB writes <br/>"
    "&bull; Cambios de variables de entorno (Vercel ni Render) <br/>"
    "&bull; Deploys ni redeploys <br/>"
    "&bull; Envíos reales de WhatsApp ni email <br/>"
    "&bull; Stripe API queries <br/>"
    "&bull; <i>derive-dashboard-password.ts</i> · NO ejecutado <br/>"
    "&bull; merge a main · sin <i>--force</i> · sin <i>reset --hard</i>"
))

# ── 6. Plan post-merge ─────────────────────────────────────────────────

story.append(H1("6. Plan post-merge"))

story.extend(bullets([
    "Revisas el PR en GitHub · confirmas que solo se retira "
    "instrumentación · la lógica Pass 1/Pass 2 está intacta.",
    "Mergeas a main · Vercel auto-redeploy en ~2 min.",
    "Smoke en producción: login con tu password actual debe "
    "seguir funcionando (no hay cambio funcional).",
    "Smoke logs Vercel · confirma que <b>no aparecen "
    "<i>[AUTH_DIAG]</i></b> tras el deploy del cleanup. La "
    "ausencia es la verificación · ya no debería emitirse incluso "
    "si alguien volviera a setear AUTH_DIAG=1 (el código que "
    "leía esa env ya no existe).",
    "Si quieres, en otro PR ortogonal: housekeeping de los 4 "
    "customers duplicados de tu cuenta · merge en Stripe vía "
    "Customer Portal o consolidación manual.",
]))

# ── 7. Datos para abrir el PR ──────────────────────────────────────────

story.append(H1("7. Datos para abrir el PR"))

story.append(make_table([
    ["Campo", "Valor"],
    ["URL",
     "github.com/celestinojbm/Dona-agent/pull/new/<br/>"
     "cleanup/auth-instrumentation-retiro"],
    ["Título sugerido",
     "cleanup(auth) · retira instrumentación temporal "
     "AUTH_DIAG/[AUTH_DIAG]"],
    ["Base", "main"],
    ["Head", "cleanup/auth-instrumentation-retiro"],
    ["Body markdown",
     "Generado abajo · listo para copiar/pegar"],
], col_widths=[1.6*inch, 5.0*inch]))

# ── 8. Body markdown del PR ────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("8. Body markdown del PR (copy-paste)"))

story.append(CODE(
    "## Resumen\n"
    "\n"
    "Retira la instrumentación temporal AUTH_DIAG/[AUTH_DIAG] que\n"
    "se introdujo en PR #34 para diagnosticar el incidente de\n"
    "login. La causa raíz fue identificada y resuelta:\n"
    "DASHBOARD_PASSWORD_SECRET en Render tenía un valor\n"
    "placeholder dona-... en vez del secret largo · una vez\n"
    "igualado con el de Vercel y redeploy, el login funcionó.\n"
    "AUTH_DIAG ya está removida del Vercel env por el owner.\n"
    "\n"
    "## Cambios\n"
    "\n"
    "- landing/auth.ts: retira el bloque diagOn y el callback\n"
    "  onTelemetry. Mantiene el log operacional permanente\n"
    "  [AUTH] recovery cross-customer.\n"
    "- landing/lib/auth-matcher.ts: retira tipo AuthTelemetry,\n"
    "  campo onTelemetry, asignaciones a tel y emit. La lógica\n"
    "  Pass 1/Pass 2 queda intacta.\n"
    "- landing/lib/auth-matcher.test.ts: retira los 7 tests del\n"
    "  bloque describe('encontrarCustomerConSub · telemetría').\n"
    "  Mantiene los 15 tests originales.\n"
    "\n"
    "## Lo que NO se toca\n"
    "\n"
    "- Lógica Pass 1 / Pass 2 cross-customer recovery.\n"
    "- ESTADOS_SUB_VALIDOS y filtros de candidatos.\n"
    "- Helper CLI scripts/derive-dashboard-password.ts.\n"
    "- Log permanente [AUTH] recovery cross-customer.\n"
    "- Variables de entorno (AUTH_DIAG ya removida por el owner).\n"
    "\n"
    "## Validación\n"
    "\n"
    "- npm test: 15/15 passing (vitest 2.1.9)\n"
    "- npx tsc --noEmit: 0 errores\n"
    "- rm -rf .next && npm run build: 17/17 pages OK\n"
    "- npm run lint: 0 errors · 3 warnings preexistentes · exit 0\n"
    "\n"
    "## Cero writes\n"
    "\n"
    "- Cero Stripe / DB / env edits / deploys / WhatsApp / email.\n"
    "- AUTH_DIAG en Vercel ya removida por el owner antes de este PR.\n"
    "- El PR es 100% cambio de código local.\n"
    "\n"
    "## Plan post-merge\n"
    "\n"
    "- Vercel auto-redeploy ~2 min tras merge.\n"
    "- Smoke login en producción: debe seguir funcionando\n"
    "  idéntico (no hay cambio funcional).\n"
    "- Smoke logs Vercel: confirma que [AUTH_DIAG] ya no aparece.\n"
    "\n"
    "## Out of scope\n"
    "\n"
    "- Housekeeping de customers duplicados en Stripe (otro PR).\n"
    "- Migración de derivación a email-based para evitar futuros\n"
    "  casos de duplicados que rompan recovery (otro PR si se\n"
    "  decide).\n"
))

story.append(BANNER(
    "<b>Branch pushed · sin merge.</b> Espera tu review en "
    "GitHub. Yo no mergeo nada hasta tu OK explícito."
))


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
