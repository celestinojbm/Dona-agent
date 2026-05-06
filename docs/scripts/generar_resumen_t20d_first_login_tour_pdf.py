"""
Genera Resumen_T20D_First_Login_Tour_2026-05-02.pdf en docs/auditorias/.
T2.0.D · first-login dashboard tour (rama pr/t2.0.d-first-login-tour).
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T20D_First_Login_Tour_2026-05-02.pdf"

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="TitleBig", parent=styles["Title"], fontSize=22, leading=26,
    spaceAfter=8, textColor=colors.HexColor("#111111"),
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

story.append(Paragraph("T2.0.D — First-login tour del dashboard",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-02 · Branch <b>pr/t2.0.d-first-login-tour</b> · "
    "PR pendiente de abrir contra <b>main</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch lista para PR. Tour modal client-side con "
    "8 pasos, persistencia localStorage, CTA WhatsApp sin envío "
    "automático. <b>tsc 0 errores · lint 9 = baseline · build verde</b>. "
    "Cero cambios en backend ni en DB. <b>NO mergeado a main.</b>"
))

# ── 1. Resumen ejecutivo ────────────────────────────────────────────────

story.append(H1("1. Resumen ejecutivo"))

story.append(P(
    "T2.0.D agrega un tour de primera visita al dashboard premium para "
    "que el usuario entienda en 30 segundos qué hay y por dónde "
    "empezar. Se dispara solo si la suscripción no está cancelada y se "
    "guarda con localStorage (clave <i>dona_tour_visto</i>); al cerrar "
    "no vuelve a aparecer en el mismo dispositivo."
))

story.extend(bullets([
    "<b>Componente nuevo</b>: <i>landing/app/dashboard/tour.tsx</i> "
    "(~270 líneas) · modal accesible (role=dialog, aria-modal, "
    "aria-labelledby) con 8 steps usando lucide-react.",
    "<b>Persistencia local</b>: solo localStorage. <b>Cero writes a "
    "DB</b>, cero migraciones, cero columnas nuevas. Si el usuario "
    "limpia caché o cambia de equipo, vuelve a verlo (aceptable para "
    "MVP).",
    "<b>CTA seguro</b>: el botón 'Empezar diagnóstico' abre "
    "<i>wa.me</i> con texto pre-llenado pero el usuario debe enviarlo "
    "manualmente. <b>NO hay envío server-side automático.</b>",
    "<b>Sin nuevas dependencias</b>: usa lucide-react ya presente.",
    "<b>Render condicional</b>: solo se monta si "
    "<i>suscripcion.estado !== 'canceled'</i>. Usuarios cancelados ven "
    "el CTA 'Reactivar plan' del dashboard, no el tour.",
]))

# ── 2. Archivos tocados ────────────────────────────────────────────────

story.append(H1("2. Archivos tocados (3 archivos)"))

story.append(make_table([
    ["Archivo", "Tipo", "Rol"],
    ["landing/app/dashboard/tour.tsx", "A",
     "Componente nuevo · TourDashboard + dashboardWhatsAppUrl + STEPS"],
    ["landing/app/dashboard/dashboard-client.tsx", "M",
     "Import TourDashboard + render dentro del bloque ready cuando "
     "estado != canceled"],
    [".env.example", "M",
     "Documenta NEXT_PUBLIC_DONA_WHATSAPP_NUMBER (público, opcional)"],
], col_widths=[3.2*inch, 0.5*inch, 2.8*inch]))

story.append(C(
    "Cero archivos backend tocados. Cero migraciones. Cero cambios en "
    ".env de Render que sean obligatorios para mergear."
))

# ── 3. Steps del tour ──────────────────────────────────────────────────

story.append(H1("3. Steps del tour (8)"))

story.append(make_table([
    ["#", "Icono", "Título", "Cubre"],
    ["1", "Wallet", "Bienvenido a tu dashboard",
     "Intro · 30 segundos"],
    ["2", "Wallet", "Saldo y créditos",
     "Renovación mensual + créditos no expiran"],
    ["3", "CreditCard", "Plan activo",
     "Próxima renovación + dónde gestionar"],
    ["4", "Zap", "Comprar créditos extra",
     "Top-ups one-time (T1.7)"],
    ["5", "Receipt", "Movimientos recientes",
     "Historial de cargos y consumos"],
    ["6", "Shield", "Gestionar facturación",
     "Customer Portal de Stripe (T1.5)"],
    ["7", "Mail", "¿Necesitas ayuda?",
     "hola@usadona.com + página de soporte"],
    ["8", "MessageSquare", "Próximo paso · diagnóstico",
     "CTA wa.me con texto pre-llenado (T2.0.A)"],
], col_widths=[0.3*inch, 0.9*inch, 2.2*inch, 3.1*inch]))

# ── 4. Helper dashboardWhatsAppUrl ─────────────────────────────────────

story.append(H1("4. Helper dashboardWhatsAppUrl()"))

story.append(P(
    "Construye URL <i>wa.me</i> con texto pre-llenado para el "
    "diagnóstico inicial. Comportamiento determinístico:"
))

story.append(CODE(
    "function dashboardWhatsAppUrl(): string {\n"
    "  const num =\n"
    "    process.env.NEXT_PUBLIC_DONA_WHATSAPP_NUMBER\n"
    "      ?.trim().replace(/^\\+/, \"\") || \"\";\n"
    "  const text = encodeURIComponent(DEFAULT_DIAGNOSTICO_TEXT);\n"
    "  if (num && /^\\d{10,15}$/.test(num)) {\n"
    "    return `https://wa.me/${num}?text=${text}`;\n"
    "  }\n"
    "  return `https://wa.me/?text=${text}`;\n"
    "}"
))

story.extend(bullets([
    "Si la env var falta o no pasa el regex de E.164 sin '+', cae a "
    "<i>wa.me/?text=...</i> que abre WhatsApp y deja al usuario "
    "elegir el contacto Dona ya guardado.",
    "Texto fijo: \"hola Dona, quiero empezar el diagnóstico de mi "
    "negocio.\" — alineado con T2.0.A que detecta 'hola' como inicio "
    "de onboarding.",
    "<b>Sin envío automático</b>: <i>wa.me</i> es un schema, no un "
    "endpoint. El usuario es el que toca 'Enviar'.",
]))

# ── 5. Persistencia y accesibilidad ────────────────────────────────────

story.append(H1("5. Persistencia y accesibilidad"))

story.append(make_table([
    ["Aspecto", "Implementación"],
    ["Persistencia",
     "localStorage · clave 'dona_tour_visto' · valor '1'. Catch "
     "silencioso para Safari modo privado."],
    ["Trigger",
     "Solo si la clave NO está. Cierre con 'Listo'/'Saltar'/X/ESC "
     "guarda la clave."],
    ["Accesibilidad",
     "role='dialog', aria-modal='true', aria-labelledby='tour-titulo'. "
     "Backdrop button con aria-label='Cerrar tour'. Botón X con "
     "aria-label='Saltar tour'."],
    ["Teclado",
     "ESC → cerrar · ArrowLeft/ArrowRight → navegar steps. Listener "
     "registrado/limpiado en useEffect."],
    ["Mobile",
     "Modal max-w-md w-full p-8, max-w-sm en smartphones por padding "
     "del wrapper. Glass-card y backdrop-blur de Tailwind."],
    ["SSR-safety",
     "Estado <i>montado</i> previene flash en hydration. Si "
     "habilitado=false, el componente devuelve null."],
], col_widths=[1.2*inch, 5.4*inch]))

# ── 6. Validaciones ejecutadas ─────────────────────────────────────────

story.append(PageBreak())
story.append(H1("6. Validaciones ejecutadas"))

story.append(make_table([
    ["Comando (cwd: landing/)", "Resultado"],
    ["npx tsc --noEmit", "<b>0 errores</b>"],
    ["npm run lint",
     "<b>9 problems (6 errors, 3 warnings) = baseline</b> "
     "post-T2.0.B · sin findings nuevos"],
    ["npm run build", "<b>Compiled OK</b> · static/dynamic generation "
     "completas"],
    ["grep secrets en .next/static",
     "0 hits para STRIPE_SECRET_KEY/INTERNAL_BRIDGE_SECRET/"
     "DASHBOARD_PASSWORD_SECRET"],
], col_widths=[3.0*inch, 3.5*inch]))

story.append(H2("Decisión sobre tests del lado landing"))

story.append(P(
    "El proyecto landing <b>no tiene framework de tests instalado</b> "
    "(ver <i>landing/package.json</i> · scripts: dev, build, "
    "vercel-build, start, lint). Los PRs previos T1.4 (dashboard), "
    "T1.5 (Customer Portal), T1.7 (top-ups) y T2.0.A (diagnóstico) "
    "siguieron el mismo patrón: <b>typecheck (tsc) + build + lint</b> "
    "como verificación oficial del client. Los 623 tests pytest "
    "cubren backend, no UI."
))

story.append(P(
    "T2.0.D es 100% client-side React (cero líneas backend). Para no "
    "expandir scope agregando un test runner nuevo (vitest, "
    "react-testing-library, jsdom), <b>se mantuvo el patrón "
    "establecido</b>. La lógica del tour está cubierta por:"
))

story.extend(bullets([
    "TypeScript estricto (tsc --noEmit 0 errores) sobre los tipos "
    "Step, TourDashboardProps y la firma de dashboardWhatsAppUrl.",
    "ESLint Next 16 con react-hooks rules (verifica deps de "
    "useEffect/useCallback).",
    "Build de producción ejerce el componente como Client Component.",
    "QA manual por el owner antes de mergear · 8 pasos × ESC × "
    "Saltar × Listo × CTA WhatsApp × persistencia localStorage.",
]))

story.append(P(
    "<b>Si se quisiera framework de tests para landing</b>, ése sería "
    "un PR aparte (T2.0.E o similar) que añade vitest/RTL y migra "
    "patrones de test base. No es scope de T2.0.D."
))

# ── 7. Riesgos restantes ───────────────────────────────────────────────

story.append(H1("7. Riesgos restantes"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Usuario limpia localStorage / cambia dispositivo · vuelve a "
     "ver el tour",
     "Cero · UX",
     "Aceptado: cambiar a flag en DB sería un PR aparte y agrega "
     "complejidad innecesaria para MVP. El tour es corto."],
    ["NEXT_PUBLIC_DONA_WHATSAPP_NUMBER no configurada en Vercel",
     "Cero · UX",
     "Helper cae a <i>wa.me/?text=...</i> y deja al usuario elegir "
     "el contacto Dona. Funciona aunque el owner no la configure."],
    ["Variable NEXT_PUBLIC_* expuesta al cliente",
     "Cero",
     "Es solo el número operativo de WhatsApp · ya público por "
     "definición (es el que aparece en marketing). Sin secret."],
    ["Lint react-hooks/set-state-in-effect en setMontado",
     "Suprimido",
     "Disable inline con justificación: localStorage solo "
     "client-side, alternativa server-side requiere refactor a "
     "Suspense + use(promise) fuera de scope."],
    ["Tour aparece a usuarios free / sin suscripción si entran al "
     "dashboard",
     "Cero",
     "Render condicional <i>habilitado={estado !== 'canceled'}</i>. "
     "Free no llega al dashboard premium."],
    ["CTA wa.me bloqueado por popup blocker en algunos navegadores",
     "Bajo",
     "&lt;a target='_blank' rel='noopener noreferrer'&gt; · "
     "click directo, no window.open · respeta política user-gesture."],
    ["Modal con backdrop button no es focus-trap completo",
     "Bajo · A11y",
     "ESC + click backdrop + botón X cierran. Focus trap real con "
     "focus-trap-react sería un refactor ortogonal · si necesario, "
     "PR aparte."],
], col_widths=[2.7*inch, 1.0*inch, 2.9*inch]))

# ── 8. Variables nuevas ────────────────────────────────────────────────

story.append(H1("8. Variables nuevas (opcionales)"))

story.append(make_table([
    ["Variable", "Scope", "Tipo", "Default"],
    ["NEXT_PUBLIC_DONA_WHATSAPP_NUMBER", "Vercel · landing",
     "Pública (NEXT_PUBLIC_*)",
     "Vacía → wa.me/?text=..."],
], col_widths=[2.6*inch, 1.4*inch, 1.5*inch, 1.1*inch]))

story.append(P(
    "<b>NO bloquea merge.</b> Sin la var, el CTA sigue funcionando "
    "(deja al usuario elegir contacto). Setear opcionalmente en "
    "Vercel después de mergear con el número operativo de Dona en "
    "formato sin '+': <i>5215555551234</i> por ejemplo."
))

# ── 9. Próximos pasos ──────────────────────────────────────────────────

story.append(H1("9. Próximos pasos"))

story.extend(bullets([
    "<b>Owner</b>: revisar el branch <i>pr/t2.0.d-first-login-tour</i> "
    "y abrir el PR contra main desde GitHub.",
    "<b>QA manual</b>: limpiar localStorage del dashboard, hacer "
    "login, verificar que aparece el tour, recorrer los 8 pasos, "
    "tocar CTA, confirmar que abre wa.me con texto pre-llenado, "
    "cerrar, refrescar, confirmar que NO vuelve a aparecer.",
    "<b>Opcional · post-merge</b>: setear "
    "NEXT_PUBLIC_DONA_WHATSAPP_NUMBER en Vercel para el chat "
    "directo con el contacto operativo de Dona.",
    "<b>Cero acciones requeridas en Render</b> (no hay cambios "
    "backend ni migraciones).",
]))

story.append(BANNER(
    "<b>PR listo · NO mergeado.</b> Próximo paso: abrir PR en GitHub "
    "con <i>gh pr create</i> contra <b>main</b>."
))


# ── Build ──────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
