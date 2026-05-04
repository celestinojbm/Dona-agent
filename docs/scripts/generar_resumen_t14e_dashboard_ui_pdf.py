"""
Genera Resumen_T14E_Dashboard_UI_2026-05-04.pdf en docs/auditorias/.
Resumen de la UI del dashboard consumiendo /api/dashboard-data
(T1.4.E, commit 15dc518).

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

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T14E_Dashboard_UI_2026-05-04.pdf"

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

story.append(Paragraph("T1.4.E — UI dashboard con datos reales",
                       styles["TitleBig"]))
story.append(Paragraph(
    "dashboard-client.tsx consume /api/dashboard-data · diseño oscuro premium preservado",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-04 · Branch <b>pr/t1.4.e-dashboard-ui</b> · "
    "Commit <b>15dc518</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheada. tsc 0 errores · build OK · "
    "16/16 static pages. Lint 14 (todos preexistentes en otros archivos; "
    "Δ -2 vs baseline 16 porque se eliminaron `as any` del cliente "
    "original). <b>NO mergeado a main.</b>"
))

# ── 1. Rama y archivos ────────────────────────────────────────────────────

story.append(H1("1. Rama y archivos modificados"))

story.append(P("<b>Rama:</b> pr/t1.4.e-dashboard-ui (desde main @ cf7be91)"))

story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo", "Rol"],
    ["landing/app/dashboard/dashboard-client.tsx", "+475 / -95", "M",
     "Reescritura: fetch a /api/dashboard-data, secciones de Créditos, "
     "Suscripción, Historial, estados loading/error/empty"],
    ["landing/lib/dashboard-types.ts", "+49 / -0", "A",
     "Tipos UsuarioResumen, TransaccionResumen, FetchUsuarioResumenResult "
     "extraídos de internal-bridge.ts (que tiene server-only)"],
    ["landing/lib/internal-bridge.ts", "+10 / -53", "M",
     "Reexporta tipos desde dashboard-types; sin cambios funcionales"],
    ["", "", "", ""],
    ["TOTAL", "+534 / -148", "3 archivos", ""],
], col_widths=[3.0*inch, 0.9*inch, 0.5*inch, 2.1*inch]))

# ── 2. Campos de /api/dashboard-data usados ────────────────────────────────

story.append(H1("2. Campos de /api/dashboard-data usados en la UI"))

story.append(make_table([
    ["Campo del response", "Dónde se usa"],
    ["creditos.saldo_actual",
     "Saldo grande en hero de la tarjeta Créditos"],
    ["creditos.creditos_mensuales",
     "Sub-info \"+N cada renovación\""],
    ["suscripcion.plan",
     "Título \"Plan Premium\" / \"Plan Pro\" (vía planNombre helper)"],
    ["suscripcion.estado",
     "Chip de estado con color: active=verde, past_due=amber, canceled=rosa"],
    ["suscripcion.current_period_end",
     "Fecha de próxima renovación o \"Se cancela el DD/MM/YYYY\""],
    ["suscripcion.cancel_at_period_end",
     "Texto amber \"Se cancela el DD/MM\" + botón cancel deshabilitado"],
    ["resumen.puede_cancelar",
     "Habilita / deshabilita el botón Cancelar suscripción"],
    ["transacciones_recientes[].razon",
     "Texto principal de cada fila del historial"],
    ["transacciones_recientes[].delta",
     "Monto +verde / -blanco a la derecha"],
    ["transacciones_recientes[].saldo_resultante",
     "Texto pequeño \"saldo N\" debajo del delta"],
    ["transacciones_recientes[].creado",
     "Fecha formateada (es-MX, día mes corto año)"],
], col_widths=[2.7*inch, 3.7*inch]))

story.append(H2("Datos del response que la UI NO renderiza"))
story.extend(bullets([
    "<b>usuario.telefono</b>: la API lo retorna pero la UI no lo muestra "
    "(regla del owner: no exponer datos internos innecesarios).",
    "<b>usuario.id, suscripcion.stripe_customer_id, "
    "stripe_subscription_id</b>: datos internos, no se renderizan.",
    "<b>suscripcion.actualizado, ultimo_movimiento</b>: redundantes con "
    "transacciones_recientes[0]; no agregan valor visual.",
    "<b>resumen.dashboard_ready</b>: implícito si llegamos al estado "
    "ready del componente.",
]))

# ── 3. Estados UI ──────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Estados de la UI"))

story.append(make_table([
    ["Estado", "Trigger", "Visual"],
    ["loading",
     "Inicial mientras corre fetchDashboard()",
     "Skeleton glass-card con animate-pulse en cada sección"],
    ["error",
     "Backend respondió no-2xx o fetch falló",
     "Card con AlertCircle rosa + mensaje + botón Reintentar"],
    ["ready (con datos)",
     "/api/dashboard-data 200",
     "3 secciones: Créditos, Suscripción, Movimientos"],
    ["ready (sin transacciones)",
     "transacciones_recientes vacío",
     "Card neutral 'Todavía no hay movimientos...'"],
    ["sub canceled",
     "suscripcion.estado === 'canceled'",
     "Mensaje + link 'Reactivar plan' en lugar del botón cancelar"],
    ["cancelación pendiente",
     "cancel_at_period_end === true",
     "Texto amber 'Se cancela el DD/MM/YYYY' + botón cancel deshabilitado"],
], col_widths=[1.7*inch, 2.0*inch, 2.7*inch]))

story.append(H2("Mensajes de error por código"))
story.append(CODE(
    "subscription_not_found → 'No encontramos tu suscripción.'\n"
    "backend_timeout        → 'El backend no respondió a tiempo.'\n"
    "backend_auth_error     → 'Hay un problema de configuración...'\n"
    "network_error          → 'Sin conexión.'\n"
    "(otro)                 → 'No pudimos cargar tus datos.'\n"
    "\n"
    "El código técnico se muestra en font-mono pequeño debajo, útil para\n"
    "soporte si el usuario reporta el error."
))

# ── 4. Pruebas ejecutadas ──────────────────────────────────────────────────

story.append(H1("4. Pruebas ejecutadas"))

story.append(make_table([
    ["Comando", "Resultado"],
    ["npx tsc --noEmit",
     "0 errores en archivos T1.4.E"],
    ["npm run lint",
     "14 problems (11 errors, 3 warnings) · todos preexistentes en "
     "auth.ts / app/page.tsx / app/layout.tsx · 0 en archivos T1.4.E"],
    ["Baseline lint",
     "Δ -2 vs 16 anteriores: eliminé `session: any` y `(session as any).plan` "
     "del cliente original"],
    ["npm run build",
     "✓ Compiled successfully · 16/16 static pages · /dashboard como ƒ "
     "· /api/dashboard-data como ƒ"],
    ["grep secrets/telefono en .next/static/",
     "0 matches · cliente sin INTERNAL_BRIDGE_SECRET, STRIPE_SECRET_KEY "
     "ni 'telefono' literal"],
], col_widths=[2.5*inch, 4.0*inch]))

story.append(H2("Sobre la regla react-hooks/set-state-in-effect"))
story.append(P(
    "Next 16 introdujo esta regla nueva que desaconseja todo setState "
    "en useEffect. La forma idiomática moderna es Suspense + "
    "<i>use(promise)</i> con Server Components. Refactor fuera de "
    "scope T1.4.E (impactaría también el patrón de auth via session "
    "client-side). Suprimida en una línea con comentario explicativo. "
    "El patrón fetch-on-mount con setState tras await es seguro: el "
    "setState ocurre asincrónicamente, no causa cascade render."
))

# ── 5. Diseño preservado ───────────────────────────────────────────────────

story.append(H1("5. Diseño oscuro premium — preservado"))

story.extend(bullets([
    "Sin rediseño grande, solo se reorganizaron secciones existentes "
    "y se añadieron las nuevas con el mismo lenguaje visual.",
    "<b>glass-card rounded-2xl p-8</b> sigue siendo el contenedor base.",
    "<b>btn-primary / btn-secondary</b> existentes para acciones.",
    "Tipografía: text-white/35 / text-white/60 / text-white/70 según "
    "jerarquía. font-light / font-normal / font-extralight.",
    "Chips de estado con colores tonales (emerald-300/80, amber-300/80, "
    "rose-300/80) sobre fondos translúcidos /[0.08].",
    "<b>animate-pulse</b> de Tailwind para skeletons; consistencia con "
    "el resto del landing.",
    "Numbers tabular-nums + font-extralight + tracking-tighter (saldo "
    "grande sigue el mismo language del hero).",
]))

# ── 6. Lo que NO se hizo ───────────────────────────────────────────────────

story.append(H1("6. Confirmaciones (lo que NO se hizo)"))
story.extend(bullets([
    "✓ <b>NO se hizo deploy.</b>",
    "✓ <b>NO se mergeó a main.</b>",
    "✓ <b>NO se cambiaron env vars.</b>",
    "✓ <b>NO se escribió en DB</b> (la UI solo lee /api/dashboard-data).",
    "✓ <b>NO se modificó backend.</b>",
    "✓ <b>NO se modificó /api/cancel-subscription</b> (T1.4.F).",
    "✓ <b>NO se expusieron secretos</b>: bundle del cliente verificado limpio.",
    "✓ <b>NO se renderiza teléfono</b> en la UI (la API lo retorna pero "
    "la UI lo ignora).",
    "✓ <b>NO se renderizan IDs Stripe internos</b> "
    "(stripe_customer_id, stripe_subscription_id) — datos internos.",
]))

# ── 7. Riesgos / pendientes ────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("7. Riesgos y pendientes"))

story.append(make_table([
    ["Riesgo / Pendiente", "Severidad", "Plan"],
    ["Cancelación llama /api/cancel-subscription legacy "
     "(stripe.subscriptions.cancel — immediate)",
     "Funcional",
     "T1.4.F lo cambia a cancel_at_period_end=true"],
    ["Re-fetch tras cancelar puede llegar antes que webhook backend "
     "actualice la sub",
     "Bajo",
     "Stripe override en T1.4.D ya muestra cancel_at_period_end correcto"],
    ["Conexiones (Gmail/Calendar/WhatsApp) siguen hardcoded",
     "Info",
     "Out of scope T1.4 según diagnóstico T1.4.A"],
    ["Sin auto-refresh — el usuario debe recargar para ver cambios",
     "Bajo",
     "Aceptable; el dashboard no es real-time. Polling agregable en futuro"],
    ["Suprimida regla react-hooks/set-state-in-effect (Next 16)",
     "Info",
     "Refactor a Suspense + use(promise) requiere Server Component "
     "y replantear la auth client-side; programar cuando haya bandwidth"],
    ["UI muestra 'saldo {N}' tras cada movimiento; podría confundir si "
     "no es el saldo actual sino el resultante en el momento de la trans",
     "UX",
     "Texto explícito 'saldo N' es claro, pero podemos mejorar copy en "
     "T1.4.F si hace falta"],
], col_widths=[3.0*inch, 0.9*inch, 2.5*inch]))

# ── 8. Próximo paso ────────────────────────────────────────────────────────

story.append(H1("8. Próximo paso: T1.4.F — cancelación segura"))

story.append(P(
    "T1.4.F cambia <b>landing/app/api/cancel-subscription/route.ts</b>:"
))
story.extend(bullets([
    "Reemplazar <i>stripe.subscriptions.cancel(id)</i> (immediate) por "
    "<i>stripe.subscriptions.update(id, {cancel_at_period_end: true})</i>.",
    "El usuario sigue usando los créditos hasta el final del período.",
    "El backend ya preserva el saldo en customer.subscription.deleted "
    "(T1.3.C), así que esto es coherente con la decisión owner.",
    "UX en dashboard ya está lista: la sección Suscripción muestra "
    "cancel_at_period_end y deshabilita el botón si ya hay cancelación "
    "pendiente."
]))

# ── Footer ────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-04 · "
    "Repo: Dona-agent · Branch: pr/t1.4.e-dashboard-ui · HEAD: 15dc518"
))


# ── Build ─────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.4.E — UI dashboard con datos reales",
    author="Claude Code", subject="Resumen de implementación T1.4.E",
)
doc.build(story)
print(f"OK: {OUTPUT}")
