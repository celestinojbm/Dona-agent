"""
Genera Resumen_T14F_Cancel_At_Period_End_2026-05-04.pdf en docs/auditorias/.
Resumen de la cancelación al final de período (T1.4.F, commit a15652f).

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

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T14F_Cancel_At_Period_End_2026-05-04.pdf"

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

story.append(Paragraph("T1.4.F — Cancelación al final de período",
                       styles["TitleBig"]))
story.append(Paragraph(
    "stripe.subscriptions.update(cancel_at_period_end=true) · acceso "
    "preservado hasta period_end",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-04 · Branch <b>pr/t1.4.f-cancel-at-period-end</b> · "
    "Commit <b>a15652f</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheada desde main. tsc 0 errores · build "
    "OK · 16/16 static pages. Lint 14 (Δ -2 vs baseline). <b>Bloqueador "
    "de Dona Control resuelto:</b> T1.4.E queda libre para mergear "
    "después de este PR. NO mergeado a main."
))

# ── 1. Archivos modificados ────────────────────────────────────────────────

story.append(H1("1. Archivos modificados"))
story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo", "Rol"],
    ["landing/app/api/cancel-subscription/route.ts", "+56 / -11", "M",
     "subscriptions.cancel() → subscriptions.update(cancel_at_period_end) "
     "+ respuesta extendida + mejoras de tipado y logs"],
    ["", "", "", ""],
    ["TOTAL", "+56 / -11", "1 archivo", ""],
], col_widths=[3.4*inch, 0.9*inch, 0.5*inch, 1.7*inch]))

# ── 2. Cambio principal ────────────────────────────────────────────────────

story.append(H1("2. Cambio principal"))

story.append(H2("Antes (T1.3 / pre-T1.4.F)"))
story.append(CODE(
    "const canceled = await getStripe().subscriptions.cancel(subscriptionId);\n"
    "return NextResponse.json({\n"
    "  status: canceled.status,\n"
    "  message: \"Subscription canceled successfully\",\n"
    "});"
))
story.append(P(
    "<b>Comportamiento:</b> cancela la suscripción de inmediato. Stripe "
    "revoca el acceso al instante, los créditos del período actual se "
    "pierden si el flujo upstream no los respeta."
))

story.append(H2("Después (T1.4.F)"))
story.append(CODE(
    "const updated = await getStripe().subscriptions.update(\n"
    "  subscriptionId,\n"
    "  { cancel_at_period_end: true },\n"
    ");\n"
    "\n"
    "// current_period_end vive en items.data[0] en stripe@22.\n"
    "const firstItem = updated.items?.data?.[0];\n"
    "const periodEnd = typeof firstItem?.current_period_end === \"number\"\n"
    "  ? firstItem.current_period_end : null;\n"
    "\n"
    "return NextResponse.json({\n"
    "  ok: true,\n"
    "  cancel_at_period_end: Boolean(updated.cancel_at_period_end),\n"
    "  current_period_end: periodEnd,\n"
    "  status: updated.status,\n"
    "  message:\n"
    "    \"Cancelación programada al final del período actual. \"\n"
    "    + \"Mantienes acceso hasta esa fecha.\",\n"
    "});"
))
story.append(P(
    "<b>Comportamiento:</b> la suscripción queda marcada para no "
    "renovar. Stripe emite <i>customer.subscription.updated</i> "
    "(cap=true) inmediatamente y <i>customer.subscription.deleted</i> "
    "al llegar period_end. El usuario mantiene acceso y créditos "
    "hasta esa fecha."
))

# ── 3. Flujo end-to-end ────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Flujo end-to-end resultante"))

story.append(CODE(
    "1. Usuario clic \"Cancelar suscripción\" en el dashboard\n"
    "       │\n"
    "       ▼\n"
    "2. POST /api/cancel-subscription (landing, server-side)\n"
    "       │ auth() obtiene subscriptionId de la sesión\n"
    "       │ (NO acepta IDs del cliente)\n"
    "       ▼\n"
    "3. stripe.subscriptions.update(id, {cancel_at_period_end: true})\n"
    "       │\n"
    "       ▼\n"
    "4. Stripe emite customer.subscription.updated (cap=true)\n"
    "       │\n"
    "       ▼\n"
    "5. Stripe webhook → landing /api/webhook → bridge HMAC\n"
    "       → backend /internal/stripe-event\n"
    "       → procesar_evento_suscripcion (T1.3.C)\n"
    "       → SuscripcionStripe queda marked\n"
    "       │\n"
    "       │  [HASTA period_end: usuario sigue con acceso, créditos\n"
    "       │   intactos, dashboard muestra \"Se cancela el DD/MM\"\n"
    "       │   en amber con botón deshabilitado (T1.4.E)]\n"
    "       │\n"
    "       ▼\n"
    "6. Al period_end: Stripe emite customer.subscription.deleted\n"
    "       → bridge → backend → _procesar_subscription_deleted\n"
    "       → status='canceled' · saldo de créditos PRESERVADO\n"
    "         (decisión owner T1.3.C: lo que pagó es suyo)"
))

# ── 4. Respuesta extendida ─────────────────────────────────────────────────

story.append(H1("4. Respuesta del endpoint"))

story.append(P(
    "Extendida para que el dashboard refresque y la UI muestre "
    "inmediatamente el estado nuevo (T1.4.E sabe leer estos campos):"
))

story.append(CODE(
    "{\n"
    "  \"ok\": true,\n"
    "  \"cancel_at_period_end\": true,    // → UI muestra texto amber\n"
    "  \"current_period_end\": 1717545600,// timestamp Unix de Stripe items[0]\n"
    "  \"status\": \"active\",              // sigue active hasta period_end\n"
    "  \"message\": \"Cancelación programada al final del período\n"
    "              actual. Mantienes acceso hasta esa fecha.\"\n"
    "}"
))

story.append(H2("Códigos HTTP"))
story.append(make_table([
    ["Status", "Cuándo"],
    ["401", "Sin sesión NextAuth"],
    ["400", "Sesión sin subscriptionId"],
    ["500", "Stripe SDK falla — error genérico 'cancel_failed'"],
    ["200", "Cancelación programada exitosamente"],
], col_widths=[0.7*inch, 5.5*inch]))

# ── 5. Mejoras paralelas ───────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("5. Mejoras paralelas (sin cambiar la intención)"))

story.extend(bullets([
    "<b>subscriptionId tipado</b>: <i>(session as { subscriptionId?: string })</i> "
    "en vez de <i>as any</i>. Confirmando guardrail T1.4.D #1: el ID "
    "viene exclusivamente de la sesión server-side.",
    "<b>shortId() para logs</b>: trunca el subscription_id en logs a "
    "'sub_xxxxxxxx...abcd' (guardrail #2 sobre IDs Stripe en producción).",
    "<b>Error genérico al cliente</b>: 'cancel_failed' en vez de "
    "propagar <i>err.message</i> de Stripe — no filtra mensajes "
    "internos del SDK al frontend.",
    "<b>Códigos estables</b>: 'unauthenticated', 'no_subscription_in_session', "
    "'cancel_failed'. Coherentes con los códigos que devuelve "
    "/api/dashboard-data (T1.4.D).",
    "<b>Try/catch con unknown</b>: <i>catch (err: unknown)</i> en lugar "
    "de <i>any</i>; uso <i>err instanceof Error</i> para extraer mensaje.",
]))

# ── 6. Pruebas ejecutadas ──────────────────────────────────────────────────

story.append(H1("6. Pruebas ejecutadas"))

story.append(make_table([
    ["Comando", "Resultado"],
    ["npx tsc --noEmit", "0 errores"],
    ["npm run lint",
     "14 problems (11 errors, 3 warnings) · todos preexistentes en "
     "auth.ts / app/page.tsx / app/layout.tsx · 0 en el archivo T1.4.F"],
    ["Δ vs baseline 16",
     "−2 errores: eliminé `(session as any).subscriptionId` y "
     "`catch (err: any)` que estaban en el archivo original"],
    ["npm run build",
     "✓ Compiled successfully · 16/16 static pages · "
     "/api/cancel-subscription sigue como ƒ (dynamic, server-rendered)"],
], col_widths=[2.0*inch, 4.5*inch]))

# ── 7. Confirmaciones ──────────────────────────────────────────────────────

story.append(H1("7. Confirmaciones (lo que NO se hizo)"))
story.extend(bullets([
    "✓ <b>NO deploy.</b>",
    "✓ <b>NO merge.</b>",
    "✓ <b>NO env changes.</b>",
    "✓ <b>NO se modificó backend</b> (la lógica de preservar saldo en "
    "subscription.deleted ya estaba en T1.3.C).",
    "✓ <b>NO se escribe en DB.</b>",
    "✓ <b>NO se modificó UI</b> (T1.4.E ya soporta el flow visual).",
    "✓ <b>Sin secrets filtrados</b> (logs truncan IDs; errores genéricos "
    "al cliente).",
    "✓ <b>Stripe Dashboard</b> intacto.",
]))

# ── 8. Riesgos ─────────────────────────────────────────────────────────────

story.append(H1("8. Riesgos"))

story.append(make_table([
    ["Riesgo", "Severidad", "Notas"],
    ["Cliente cancela y compra créditos paquete one-time antes "
     "de period_end",
     "Info",
     "Sin impacto: flujos paralelos, los paquetes one-time no usan "
     "este endpoint"],
    ["Webhook subscription.updated cap=true se demora",
     "Bajo",
     "Stripe override en T1.4.D consulta directo a Stripe SDK, "
     "muestra cancel_at_period_end correcto aunque backend esté stale"],
    ["Stripe falla al update por estado inválido (sub ya canceled)",
     "Bajo",
     "Cae al catch → cancel_failed 500 al cliente; UX degrada limpio"],
    ["Comportamiento distinto vs cancelaciones inmediatas previas",
     "Funcional/UX",
     "Es el cambio deseado. Si hay usuarios en producción, el message "
     "del response les da claridad. Comunicar al primer usuario por "
     "WhatsApp si aplica"],
    ["current_period_end null si Stripe no lo devuelve",
     "Muy bajo",
     "El dashboard maneja null y oculta la fecha; backend usa el "
     "webhook real para timing"],
], col_widths=[2.7*inch, 0.9*inch, 2.9*inch]))

# ── 9. Próximos pasos ──────────────────────────────────────────────────────

story.append(H1("9. Próximos pasos · orden de merge sugerido"))

story.extend(bullets([
    "<b>1. Mergear T1.4.F</b> primero "
    "(<i>pr/t1.4.f-cancel-at-period-end</i> @ a15652f). Desbloquea "
    "T1.4.E según Dona Control.",
    "<b>2. Mergear T1.4.E</b> después "
    "(<i>pr/t1.4.e-dashboard-ui</i> @ 15dc518). UI ya lista para el "
    "nuevo flow de cancelación.",
    "Ambas branches partieron de main; sin conflictos esperables.",
]))

story.append(P("<b>PR links:</b>"))
story.extend(bullets([
    "T1.4.F: https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/t1.4.f-cancel-at-period-end",
    "T1.4.E: https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/t1.4.e-dashboard-ui",
]))

story.append(WARN(
    "<b>Tras mergear ambos:</b> tarde o temprano hará falta un "
    "housekeeping de los ~15 archivos untracked acumulados en "
    "docs/auditorias/ y docs/scripts/ desde T1.4.A. Cuando T1.4 cierre, "
    "branch <i>pr/post-t1.4-housekeeping</i>."
))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-04 · "
    "Repo: Dona-agent · Branch: pr/t1.4.f-cancel-at-period-end · "
    "HEAD: a15652f"
))


# ── Build ─────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.4.F — Cancelación al final de período",
    author="Claude Code", subject="Resumen de implementación T1.4.F",
)
doc.build(story)
print(f"OK: {OUTPUT}")
