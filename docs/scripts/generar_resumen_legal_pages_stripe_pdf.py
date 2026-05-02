"""
Genera Resumen_Legal_Pages_Stripe_2026-05-02.pdf con el resumen del PR
páginas legales /soporte /politica-de-privacidad /terminos-y-condiciones
(commit 50b9cbf, rama pr/legal-pages-stripe).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_Legal_Pages_Stripe_2026-05-02.pdf"

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

story.append(Paragraph("Páginas legales para Stripe", styles["TitleBig"]))
story.append(Paragraph(
    "Implementación · Rama <b>pr/legal-pages-stripe</b> · "
    "Commit <b>50b9cbf</b> · 2026-05-02",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheado a GitHub. Build OK (15/15 static pages). "
    "<b>NO mergeado a main.</b> Tras el merge Vercel redespliega "
    "automáticamente y las URLs estarán vivas para configurar Stripe."
))

# ── 1. Archivos creados/modificados ────────────────────────────────────────

story.append(H1("1. Archivos creados / modificados"))
story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo", "Rol"],
    ["landing/app/soporte/page.tsx", "+95 / -0", "A",
     "Página de soporte con email de contacto"],
    ["landing/app/politica-de-privacidad/page.tsx", "+204 / -0", "A",
     "Política de privacidad en español"],
    ["landing/app/terminos-y-condiciones/page.tsx", "+214 / -0", "A",
     "Términos de servicio en español"],
    ["landing/app/page.tsx", "+5 / -5", "M",
     "Footer apunta a las nuevas rutas (antes #)"],
    ["", "", "", ""],
    ["TOTAL", "+518 / -5", "4 archivos", ""],
], col_widths=[2.6*inch, 0.9*inch, 0.6*inch, 2.4*inch]))

# ── 2. URLs finales para Stripe ────────────────────────────────────────────

story.append(H1("2. URLs finales para Stripe"))
story.append(P(
    "Una vez mergeado el PR a main y redesplegado Vercel, configurar "
    "estas URLs en Stripe Dashboard → Settings → Public business "
    "details / Branding:"
))

story.append(make_table([
    ["Campo Stripe", "URL"],
    ["URL de soporte para clientes",
     "https://www.usadona.com/soporte"],
    ["URL de política de privacidad",
     "https://www.usadona.com/politica-de-privacidad"],
    ["URL de condiciones de servicio",
     "https://www.usadona.com/terminos-y-condiciones"],
], col_widths=[2.5*inch, 4.0*inch]))

# ── 3. Comandos ejecutados ─────────────────────────────────────────────────

story.append(H1("3. Comandos ejecutados y resultados"))
story.append(make_table([
    ["Comando", "Resultado"],
    ["npx tsc --noEmit",
     "0 errores en archivos nuevos/modificados"],
    ["npm run lint",
     "16 problemas (13 errores, 3 warnings) — todos preexistentes en "
     "otros archivos (any en auth.ts, route.ts, dashboard-client.tsx; "
     "<img> en layout.tsx; unused Send en page.tsx). 0 nuevos por "
     "este cambio."],
    ["npm run build",
     "✓ Compiled successfully · 15/15 static pages generadas. Las "
     "3 nuevas rutas aparecen como estáticas (○ prerendered)."],
], col_widths=[1.5*inch, 5.0*inch]))

story.append(H2("Output relevante de npm run build"))
story.append(CODE(
    "Route (app)\n"
    "├ ○ /\n"
    "├ ○ /cancel\n"
    "├ ƒ /dashboard\n"
    "├ ○ /login\n"
    "├ ○ /politica-de-privacidad     ← nuevo (estático)\n"
    "├ ○ /soporte                    ← nuevo (estático)\n"
    "├ ○ /success\n"
    "└ ○ /terminos-y-condiciones     ← nuevo (estático)"
))

# ── 4. Decisiones de contenido ─────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Decisiones de contenido"))

story.append(H2("Email de soporte"))
story.append(P(
    "Se usa <b>hola@usadona.com</b> en las tres páginas, no "
    "soporte@usadona.com. Razón: <b>hola@usadona.com</b> ya figura "
    "públicamente en el footer del landing actual (<i>page.tsx</i> línea ~785) "
    "y en el contenido del README, lo que indica que es el email operativo "
    "actual de Dona. Reusarlo evita inventar una dirección que pueda no "
    "existir."
))
story.append(WARN(
    "<b>Pendiente de confirmar:</b> que <b>hola@usadona.com</b> "
    "esté efectivamente monitoreado para temas de soporte (facturación, "
    "cancelación, dudas técnicas) y no solo para contacto general. "
    "Si no, considerar configurar <i>soporte@usadona.com</i> y actualizar "
    "las 3 páginas (cambio chico)."
))

story.append(H2("Política de privacidad — qué cubre"))
story.extend(bullets([
    "Datos: nombre, email, teléfono, mensajes, tokens OAuth, "
    "datos técnicos básicos.",
    "Usos: prestar el servicio, procesar pagos, soporte, "
    "seguridad, mejora del producto.",
    "Proveedores: Stripe (pagos), mensajería WhatsApp, "
    "infraestructura cloud, modelos de IA. Sin nombres específicos "
    "de proveedores de IA o cloud para no encadenarse a uno en particular.",
    "<b>No vendemos</b> datos. <b>No entrenamos</b> modelos propios "
    "públicos con datos de usuario.",
    "Seguridad: TLS en tránsito, cifrado en reposo de credenciales.",
    "Derechos: acceso, corrección, eliminación vía email.",
    "Fecha de última actualización: 2 de mayo de 2026.",
]))

story.append(H2("Términos y condiciones — qué cubre"))
story.extend(bullets([
    "Qué es Dona, descripción funcional sin promesas absolutas.",
    "Uso permitido: no fraude, no spam, no abusos.",
    "Suscripciones: Stripe procesa pagos; planes pueden cambiar; "
    "cancelaciones aplican hacia adelante; sin reembolsos parciales "
    "salvo ley aplicable.",
    "Créditos: pueden tener límites; no son canjeables ni transferibles.",
    "Disponibilidad: el servicio puede cambiar o tener interrupciones; "
    "no garantizamos uptime.",
    "Responsabilidad del usuario: revisar decisiones importantes antes "
    "de ejecutarlas. Las respuestas de IA pueden contener errores.",
    "Limitación de responsabilidad: máximo el monto pagado en últimos 12 "
    "meses. Sin daños indirectos.",
    "Fecha de última actualización: 2 de mayo de 2026.",
]))

story.append(H2("Estilo visual"))
story.extend(bullets([
    "Mismo color scheme oscuro del landing (text-white/45, font-light).",
    "Componentes <i>glass-card</i>, <i>btn-primary</i>, <i>nav-link</i> "
    "del CSS existente — no se agregaron estilos nuevos.",
    "Layout limpio: max-w-3xl para textos legales, max-w-2xl para soporte.",
    "Botón <b>Volver al inicio</b> en cada página con icon ArrowLeft.",
    "Todas son páginas <b>server-side</b> (sin <i>use client</i>) — más "
    "rápidas que las páginas client del resto del landing y mejor para SEO.",
    "Cada página exporta <i>metadata</i> con title y description para "
    "que Google/Stripe vean lo correcto al rastrear.",
]))

story.append(H2("Footer del landing"))
story.append(P(
    "<b>Antes:</b> 3 links \"Términos\", \"Privacidad\", \"Aviso legal\" "
    "todos apuntando a <i>#</i>. <b>Ahora:</b> los mismos 2 primeros "
    "apuntan a las rutas reales, y \"Aviso legal\" se reemplazó por "
    "\"Soporte\" (más útil para el usuario y alineado con lo que pide "
    "Stripe). i18n actualizado en ES y EN."
))

# ── 5. Pendientes ──────────────────────────────────────────────────────────

story.append(H1("5. Pendientes / Notas"))

story.extend(bullets([
    "<b>Confirmar email de soporte:</b> hola@usadona.com debe estar "
    "monitoreado para temas de soporte (facturación, cancelación, etc.). "
    "Si actualmente solo es un email de contacto general, considerar "
    "configurar soporte@usadona.com.",
    "<b>Revisión legal:</b> el contenido es prudente y profesional pero "
    "<i>no</i> sustituye una revisión por un abogado. Cuando Dona crezca "
    "o agregue funcionalidad sensible (datos de salud, menores, etc.), "
    "considerar review legal formal.",
    "<b>EN versions:</b> no se crearon versiones en inglés de las páginas "
    "legales. Para cuando se requiera bilingüe, replicar las 3 páginas "
    "bajo <i>/en/support</i>, <i>/en/privacy</i>, <i>/en/terms</i>.",
    "<b>Fecha hardcoded:</b> la \"última actualización\" está como "
    "constante en cada archivo. Cuando se actualice el contenido, "
    "tocar manualmente la fecha.",
]))

# ── 6. Próximos pasos ──────────────────────────────────────────────────────

story.append(H1("6. Próximos pasos para el owner"))

story.append(H2("a) Mergear el PR"))
story.extend(bullets([
    "PR: https://github.com/celestinojbm/Dona-agent/compare/"
    "main...pr/legal-pages-stripe",
    "Vercel redespliega automáticamente al merge. Las 3 URLs "
    "https://www.usadona.com/soporte, /politica-de-privacidad y "
    "/terminos-y-condiciones quedarán activas en pocos minutos.",
]))

story.append(H2("b) Configurar Stripe"))
story.extend(bullets([
    "Stripe Dashboard → Settings → Public business details (o Branding):",
    "<b>Support URL:</b> https://www.usadona.com/soporte",
    "<b>Privacy policy URL:</b> https://www.usadona.com/politica-de-privacidad",
    "<b>Terms of service URL:</b> https://www.usadona.com/terminos-y-condiciones",
]))

story.append(H2("c) Verificación rápida post-deploy"))
story.extend(bullets([
    "Abrir cada URL en navegador y confirmar que carga sin 404.",
    "Confirmar que el footer del landing tiene los 3 links activos.",
    "Confirmar que se ve bien en mobile (las páginas usan responsive).",
]))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-02 · "
    "Repo: Dona-agent · Branch: pr/legal-pages-stripe · "
    "HEAD: 50b9cbf"
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="Páginas legales para Stripe",
    author="Claude Code", subject="Resumen de implementación páginas legales",
)
doc.build(story)
print(f"OK: {OUTPUT}")
