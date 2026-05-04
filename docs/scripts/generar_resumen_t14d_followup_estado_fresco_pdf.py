"""
Genera Resumen_T14D_Followup_Estado_Fresco_2026-05-03.pdf en docs/auditorias/.
Follow-up de T1.4.D: estado fresco desde Stripe + server-only (commit 93b9401).

No toca archivos del proyecto. No envia datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T14D_Followup_Estado_Fresco_2026-05-03.pdf"

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
    "T1.4.D follow-up — estado fresco + server-only", styles["TitleBig"]))
story.append(Paragraph(
    "Stripe como fuente más fresca · server-only en internal-bridge",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-03 · Branch <b>pr/t1.4.d-dashboard-data</b> · "
    "Commit follow-up <b>93b9401</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Ajustes pedidos por Dona Control aplicados sobre el "
    "PR de T1.4.D. Branch repusheada. tsc 0 errores · build OK · "
    "/api/dashboard-data sigue como ƒ. Lint 16 = baseline."
))

# ── 1. Cambios aplicados ──────────────────────────────────────────────────

story.append(H1("1. Cambios aplicados"))

story.append(make_table([
    ["Archivo", "Δ líneas", "Cambio"],
    ["landing/app/api/dashboard-data/route.ts", "+13 / -0",
     "Merge ahora deriva estado y puede_cancelar desde Stripe overrides "
     "cuando están disponibles"],
    ["landing/lib/internal-bridge.ts", "+6 / -0",
     "Agregado <i>import \"server-only\"</i> + comentario explicando que "
     "evita uso accidental desde Client Components"],
    ["", "", ""],
    ["TOTAL follow-up", "+19 / -0", "2 archivos"],
], col_widths=[3.0*inch, 0.9*inch, 2.6*inch]))

# ── 2. Diff resumido ──────────────────────────────────────────────────────

story.append(H1("2. Diff resumido"))

story.append(H2("a) Merge actualizado en route.ts"))
story.append(P("Antes:"))
story.append(CODE(
    "// 5. Merge: datos del backend + Stripe + email de sesión.\n"
    "const merged = {\n"
    "  ...data,\n"
    "  usuario: { ...data.usuario, email: sessionEmail },\n"
    "  suscripcion: {\n"
    "    ...data.suscripcion,\n"
    "    current_period_end: stripeOverrides.current_period_end,\n"
    "    cancel_at_period_end: stripeOverrides.cancel_at_period_end,\n"
    "  },\n"
    "};"
))

story.append(P("Después:"))
story.append(CODE(
    "// 5. Merge: datos del backend + Stripe + email de sesión.\n"
    "// Para `estado` y `puede_cancelar` Stripe es fuente más fresca: si\n"
    "// el webhook al backend está retrasado, Stripe ya sabe si la sub fue\n"
    "// cancelada o quedó past_due. Si Stripe no está disponible\n"
    "// (defaults null), usamos lo que diga el backend.\n"
    "const data: UsuarioResumen = backendRes.data;\n"
    "const estadoFinal =\n"
    "  stripeOverrides.status_stripe ?? data.suscripcion.estado;\n"
    "const puedeCancelar =\n"
    "  estadoFinal === \"active\" && !stripeOverrides.cancel_at_period_end;\n"
    "\n"
    "const merged = {\n"
    "  ...data,\n"
    "  usuario: { ...data.usuario, email: sessionEmail },\n"
    "  suscripcion: {\n"
    "    ...data.suscripcion,\n"
    "    estado: estadoFinal,\n"
    "    current_period_end: stripeOverrides.current_period_end,\n"
    "    cancel_at_period_end: stripeOverrides.cancel_at_period_end,\n"
    "  },\n"
    "  resumen: {\n"
    "    ...data.resumen,\n"
    "    puede_cancelar: puedeCancelar,\n"
    "  },\n"
    "};"
))

story.append(H2("b) server-only en internal-bridge.ts"))
story.append(CODE(
    "// `server-only` evita que cualquier Client Component o código de\n"
    "// cliente lo importe accidentalmente: si pasa, el build de Next\n"
    "// falla con un error claro. Estas funciones leen\n"
    "// INTERNAL_BRIDGE_SECRET y nunca deben correr en el browser.\n"
    "import \"server-only\";\n"
    "\n"
    "import crypto from \"node:crypto\";"
))

# ── 3. Lógica de estado ───────────────────────────────────────────────────

story.append(H1("3. Lógica de estado y puede_cancelar"))

story.append(make_table([
    ["Caso", "estado_final", "puede_cancelar"],
    ["Stripe active + cancel_at_period_end=false",
     "active", "true"],
    ["Stripe active + cancel_at_period_end=true (cancelación pendiente)",
     "active", "false"],
    ["Stripe canceled (backend aún no procesó webhook)",
     "canceled", "false"],
    ["Stripe past_due",
     "past_due", "false"],
    ["Stripe falla / no configurado (status_stripe=null)",
     "del backend", "active && !backend_cancel_period (default false)"],
], col_widths=[2.7*inch, 1.5*inch, 2.3*inch]))

story.append(P(
    "<b>Implicación:</b> si el backend dice 'active' pero Stripe ya "
    "marcó 'canceled' (webhook retrasado), el dashboard mostrará "
    "'canceled' y el botón de cancelar quedará deshabilitado. Coherente "
    "con realidad."
))

# ── 4. Comandos ejecutados ────────────────────────────────────────────────

story.append(H1("4. Comandos ejecutados"))

story.append(make_table([
    ["Comando", "Resultado"],
    ["npx tsc --noEmit", "0 errores"],
    ["npm run lint", "16 problems · todos preexistentes · 0 nuevos"],
    ["npm run build", "✓ Compiled · 16/16 static pages · "
     "/api/dashboard-data sigue como ƒ"],
], col_widths=[2.0*inch, 4.5*inch]))

story.append(H2("Confirmación de server-rendered"))
story.append(CODE(
    "Route (app)\n"
    "├ ƒ /api/dashboard-data        ← sigue como ƒ (dynamic)\n"
    "├ ƒ /api/auth/[...nextauth]\n"
    "├ ƒ /api/cancel-subscription\n"
    "├ ƒ /api/checkout\n"
    "├ ƒ /api/webhook\n"
    "├ ƒ /api/whatsapp-webhook\n"
    "├ ƒ /dashboard\n"
    "└ ... 9 rutas estáticas"
))

# ── 5. Riesgos del cambio ─────────────────────────────────────────────────

story.append(H1("5. Riesgos del cambio"))

story.extend(bullets([
    "<b>Stripe SDK falla por rate-limit / red:</b> caemos al backend "
    "para estado y puede_cancelar. El usuario ve datos un poco más viejos "
    "pero coherentes con la última info que entró por webhook. Aceptable.",
    "<b>Backend reporta 'active' pero Stripe está canceled:</b> ahora "
    "respetamos Stripe — UX coherente.",
    "<b>Backend reporta 'canceled' pero Stripe no:</b> caso raro (backend "
    "marcaría canceled solo tras procesar webhook subscription.deleted). "
    "Si pasa, ahora el dashboard muestra el estado de Stripe (probablemente "
    "active) — podría confundir un instante. Mitigación: ese caso es muy "
    "improbable en práctica.",
    "<b>server-only no rompe build existente:</b> verificado · "
    "el route handler de webhook que lo importa también es server-side.",
]))

# ── 6. Próximo paso ───────────────────────────────────────────────────────

story.append(H1("6. Próximo paso"))

story.append(P(
    "Branch <b>pr/t1.4.d-dashboard-data</b> ya en remoto con los 2 commits:"
))
story.extend(bullets([
    "<b>732f247</b> feat(landing): proxy /api/dashboard-data server-side (T1.4.D)",
    "<b>93b9401</b> fix(landing): estado fresco de Stripe + server-only en bridge",
]))

story.append(P(
    "Esperando re-review de Dona Control. Si aprueba, mergear vía GitHub "
    "UI: <i>https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/t1.4.d-dashboard-data</i>"
))

story.append(P(
    "Después: T1.4.E (UI dashboard que consume /api/dashboard-data) y "
    "T1.4.F (cancelación segura con cancel_at_period_end)."
))

# ── Footer ────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-03 · "
    "Repo: Dona-agent · Branch: pr/t1.4.d-dashboard-data · HEAD: 93b9401"
))


# ── Build ─────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.4.D follow-up — estado fresco",
    author="Claude Code",
    subject="Follow-up T1.4.D: Stripe estado fresco + server-only",
)
doc.build(story)
print(f"OK: {OUTPUT}")
