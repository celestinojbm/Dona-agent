"""
Genera Addendum_Manus_Integration_2026-05-05.pdf en docs/planes/.
Addendum estratégico que integra la referencia Manus en la visión
y roadmap de Dona. NO reemplaza el Plan v2.1; lo extiende.

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

OUTPUT = r"C:\Users\celes\Dona-agent\docs\planes\Addendum_Manus_Integration_2026-05-05.pdf"

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
    name="Quote", parent=styles["Normal"], fontSize=12, leading=18,
    textColor=colors.HexColor("#1f2937"),
    backColor=colors.HexColor("#f9fafb"),
    borderPadding=12, borderColor=colors.HexColor("#9ca3af"),
    borderWidth=0.4, leftIndent=8, rightIndent=8,
    spaceBefore=8, spaceAfter=14,
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
    name="BulletDona", parent=styles["Body"], leftIndent=14, bulletIndent=2,
    spaceAfter=2,
))


def H1(t): return Paragraph(t, styles["H1"])
def H2(t): return Paragraph(t, styles["H2"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def QUOTE(t): return Paragraph(t, styles["Quote"])
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

story.append(Paragraph(
    "Addendum — Integración Manus en Dona", styles["TitleBig"]))
story.append(Paragraph(
    "Capacidad de ejecución de Manus dentro del ADN de Dona · "
    "no copia · no reemplaza el Plan v2.1",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-05 · Vigente con "
    "Plan_Dona_v2_1_2026-04-30.pdf · NO sustituye nada del backlog T.x",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Decisión:</b> tomar la capacidad de ejecución de Manus y "
    "adaptarla al ADN de Dona (WhatsApp, diagnóstico, permisos, "
    "créditos operativos, Tool Intelligence Layer, Action Center). "
    "<b>NO copiar Manus</b> ni convertir Dona en agente generalista. "
    "Las ideas Manus se agregan como prefijo M (M0..M4); el backlog T.x "
    "del Plan v2.1 no se toca."
))

story.append(QUOTE(
    "<i>\"Manus convierte prompts en entregables. Dona debe convertir "
    "situaciones, recursos y objetivos en sistemas activos, "
    "autorizados y medibles de crecimiento.\"</i>"
))

# ── 2. Continuidad ────────────────────────────────────────────────────────

story.append(H1("1. Continuidad con lo planificado"))

story.extend(bullets([
    "✓ Plan v2.1 sigue activo.",
    "✓ Phase 0 cerrada.",
    "✓ Phase 1 en curso: T1.3 / T1.4 / T1.5 desplegados; "
    "T1.6 / T1.7 / T2.0 pendientes.",
    "✓ Tool Intelligence Layer y Action Center ya estaban en Plan v2.1.",
]))

# ── 3. Conceptos integrados ────────────────────────────────────────────────

story.append(H1("2. 7 conceptos integrados"))

story.append(make_table([
    ["#", "Concepto", "Diferencia con Manus"],
    ["3.1", "Dona Playbooks",
     "Usuario describe una situación, no un prompt · pasos guiados desde "
     "WhatsApp · costo en créditos visible antes de ejecutar"],
    ["3.2", "Execution Sandbox",
     "Cada acción pasa por cobrar_o_rechazar() (T1.3) + permisos por "
     "categoría + audit_log; no es VM aislada genérica"],
    ["3.3", "Browser Operator por niveles",
     "L1 read-only · L2 form fill con preview · L3 transactional con "
     "doble confirmación. Manus no diferencia."],
    ["3.4", "Builder orientado a crecimiento",
     "Cada activo nace dentro de una iniciativa con KPI. Manus genera "
     "artifacts terminales."],
    ["3.5", "Wide Research → Motor de Oportunidades",
     "Output rankeado y accionable con columna 'siguiente acción + "
     "costo'. Manus produce respuestas enciclopédicas."],
    ["3.6", "Documentos accionables",
     "PDF/slide/propuesta = nodo de iniciativa con tracker de "
     "envío/lectura/respuesta."],
    ["3.7", "Workspace vivo + Action Center",
     "Workspace es el negocio del usuario, persistente. Action Center "
     "= cola priorizada con costos y autorización requerida."],
], col_widths=[0.4*inch, 2.2*inch, 4.0*inch]))

# ── 4. Browser Operator detalle ───────────────────────────────────────────

story.append(H2("Browser Operator — 3 niveles de riesgo"))
story.append(make_table([
    ["Nivel", "Permite", "Ejemplo", "Autorización"],
    ["L1 read-only", "Scraping info pública",
     "Ver precios competencia",
     "Implícita por playbook activo"],
    ["L2 form fill", "Llenar forms sin pago",
     "Responder lead en form de contacto",
     "Preview + confirmación humana por WhatsApp"],
    ["L3 transactional", "Comprar / pagar / login con credenciales",
     "Reservar dominio en Namecheap",
     "Doble confirmación + permiso guardado + límite de gasto"],
], col_widths=[1.2*inch, 1.8*inch, 1.7*inch, 1.9*inch]))

# ── 5. Mapping ────────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Mapping con planificación existente"))

story.append(make_table([
    ["Concepto Manus", "Pieza Dona", "Estado", "Relación"],
    ["Agent Skills", "Playbooks", "Concepto nuevo", "M1 backlog"],
    ["Sandbox sin créditos", "cobrar_o_rechazar() + audit log",
     "✅ producción", "Reusa"],
    ["Browser sin niveles", "preparar_X / confirmar_X (CLAUDE.md)",
     "✅ patrón existente", "Extender con niveles"],
    ["Web builder genérico", "Builder orientado a iniciativas",
     "Concepto nuevo", "M3 backlog"],
    ["Wide Research", "Motor de Oportunidades",
     "Concepto nuevo", "M3 backlog"],
    ["Documentos artifacts", "Documentos accionables (PDF + tracker)",
     "Parcial · ya hay PDFs admin", "Extender"],
    ["Workspace efímero", "Dashboard T1.4 + Workspace vivo",
     "T1.4 base · T2 extensión", "Extender"],
    ["Action Center", "Action Center",
     "Concepto nuevo", "M4 backlog"],
], col_widths=[1.7*inch, 1.9*inch, 1.5*inch, 1.5*inch]))

# ── 6. Backlog priorizado ────────────────────────────────────────────────

story.append(H1("4. Backlog priorizado · prefijo M"))
story.append(P(
    "Convención: <b>M0 → M4</b>, paralelo o posterior a T1.x / T2.x del "
    "Plan v2.1. <b>NO sustituye</b> nada del backlog T.x existente."
))

story.append(H2("M0 — Foundations (puede solaparse con T1.6)"))
story.append(make_table([
    ["Ticket", "Título", "Encaja con", "Sizing"],
    ["M0.1", "Catálogo de tools con nivel de riesgo declarado",
     "Tool Intelligence Layer", "S"],
    ["M0.2", "Permisos por categoría guardados en backend",
     "Approval gates", "M"],
    ["M0.3", "Métricas y costos por tool en /admin/metrics",
     "T1.6 observabilidad", "S"],
], col_widths=[0.6*inch, 3.4*inch, 1.7*inch, 0.5*inch]))

story.append(H2("M1 — Playbooks v1 (después de T1.6 / T2.0)"))
story.append(make_table([
    ["Ticket", "Título", "Sizing"],
    ["M1.1", "Playbook engine — estado persistente + "
     "preparar_X/confirmar_X", "L"],
    ["M1.2", "Playbook Diagnóstico de negocio por WhatsApp "
     "(end-to-end)", "M"],
    ["M1.3", "Playbook Mapa de oportunidades", "M"],
    ["M1.4", "Playbook Plan de contenido 7 días", "S"],
], col_widths=[0.6*inch, 5.0*inch, 0.5*inch]))

story.append(H2("M2 — Browser Operator"))
story.append(make_table([
    ["Ticket", "Título", "Sizing"],
    ["M2.1", "Browser L1 read-only — scraper headless", "M"],
    ["M2.2", "Browser L2 form fill — preview + confirmación humana",
     "L"],
    ["M2.3", "Browser L3 transactional — vault + doble confirmación + "
     "límite gasto", "XL"],
], col_widths=[0.6*inch, 5.0*inch, 0.5*inch]))

story.append(H2("M3 — Builder + Wide Research"))
story.append(make_table([
    ["Ticket", "Título", "Sizing"],
    ["M3.1", "Builder activo: landing simple + formulario atado a KPI",
     "L"],
    ["M3.2", "Wide Research → tabla rankeada (competencia / leads / "
     "keywords)", "L"],
    ["M3.3", "Documentos accionables: PDFs con tracker de "
     "envío/lectura/respuesta", "M"],
], col_widths=[0.6*inch, 5.0*inch, 0.5*inch]))

story.append(H2("M4 — Action Center + Workspace vivo"))
story.append(make_table([
    ["Ticket", "Título", "Sizing"],
    ["M4.1", "Action Center: cola priorizada con costo + "
     "autorización", "M"],
    ["M4.2", "Workspace vivo: KPIs + iniciativas + oportunidades",
     "L"],
    ["M4.3", "Playbook Reactivación de clientes", "M"],
    ["M4.4", "Playbook Reporte semanal de métricas (automático)",
     "S"],
], col_widths=[0.6*inch, 5.0*inch, 0.5*inch]))

# ── 7. Riesgos ────────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("5. Riesgos / conflictos detectados"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Scope creep · Dona vuelve generalista por error",
     "Alta",
     "Anti-patterns de §6 son vinculantes. Cada ticket M se valida "
     "contra ellos antes de entrar a backlog activo."],
    ["M2 Browser Operator se acerca a Manus genérico",
     "Media",
     "3 niveles de riesgo + integración obligatoria con un playbook "
     "activo. Sin browser standalone."],
    ["Costos · cada módulo M necesita pricing/créditos definido",
     "Funcional",
     "Definir matriz tool×créditos en M0.3 antes de M1+."],
    ["Sobrecarga del usuario · demasiados playbooks",
     "Media",
     "Empezar con 1 playbook completo (M1.2 Diagnóstico) antes de "
     "sumar 6."],
    ["Carga operativa · primer usuario en producción",
     "Media",
     "Cada M se valida con prueba real antes del siguiente. Sin "
     "batch deploys."],
    ["M0.3 podría duplicar trabajo de T1.6",
     "Bajo",
     "M0.3 = parte de T1.6, mismo PR."],
    ["Comunicación pública: 'Manus para negocios' suena a copy",
     "Baja",
     "Hablar de capacidades, no de competidores."],
], col_widths=[2.7*inch, 0.8*inch, 3.0*inch]))

# ── 8. Anti-patterns ──────────────────────────────────────────────────────

story.append(H1("6. Qué NO copiar de Manus (vinculante)"))

story.append(DANGER(
    "<b>Estas 6 reglas son bloqueadoras</b> para cualquier ticket M. "
    "Si un PR M las contradice, no se mergea aunque pase tests."
))

story.append(make_table([
    ["#", "Anti-pattern", "Razón"],
    ["1", "Exigir prompt-engineering al usuario",
     "Emprendedores WhatsApp no son power-users. Dona detecta la "
     "situación y propone el playbook."],
    ["2", "Prometer autonomía total sin permisos fuertes",
     "Cada acción irreversible exige autorización explícita. Sin "
     "excepciones."],
    ["3", "Lanzar herramientas por moda sin métrica",
     "Cada tool nueva declara costo, nivel de riesgo y al menos un "
     "playbook que la consume."],
    ["4", "Vender resultados financieros garantizados",
     "Dona acelera y mide; no garantiza ROI. Comunicación honesta."],
    ["5", "Crear assets desconectados de iniciativa medible",
     "Ningún activo sin KPI conectado."],
    ["6", "Ocultar costos al usuario",
     "Cada paso de playbook declara créditos antes de ejecutar. "
     "Transparencia es feature."],
], col_widths=[0.3*inch, 2.6*inch, 3.5*inch]))

# ── 9. Playbooks recomendados ─────────────────────────────────────────────

story.append(H1("7. Playbooks iniciales recomendados"))

story.append(make_table([
    ["#", "Playbook", "Cuándo aplica", "Ticket", "Créditos est."],
    ["1", "Diagnóstico de negocio por WhatsApp",
     "Onboarding · primer mes", "M1.2", "30–80"],
    ["2", "Mapa de oportunidades",
     "Tras diagnóstico · mensual", "M1.3", "50–120"],
    ["3", "Oferta inicial vendible",
     "Negocios sin oferta clara", "(M3 dep.)", "80–150"],
    ["4", "Landing simple + formulario",
     "Tras oferta vendible", "M3.1", "100–200"],
    ["5", "Reactivación de clientes",
     "Mensual · base de clientes", "M4.3", "60–120"],
    ["6", "Plan de contenido 7 días",
     "Semanal", "M1.4", "30–60"],
    ["7", "Reporte semanal de métricas",
     "Semanal · automático tras opt-in", "M4.4", "10–20"],
], col_widths=[0.3*inch, 2.4*inch, 1.8*inch, 0.7*inch, 0.8*inch]))

story.append(P(
    "<i>Cifras de créditos son estimaciones para sizing; se calibran "
    "en M0.3 cuando haya métricas reales de costo de cada tool.</i>"
))

# ── 10. Lo que NO se hizo + siguiente paso ───────────────────────────────

story.append(H1("8. Lo que NO se implementó en este turno"))

story.extend(bullets([
    "✓ <b>Cero código</b> nuevo en agent/ · landing/ · tests/ · alembic/.",
    "✓ <b>Cero env vars</b> tocadas (Render · Vercel · locales).",
    "✓ <b>Cero modificaciones</b> a Stripe Dashboard · DB · servicios externos.",
    "✓ <b>Cero deploys.</b>",
    "✓ <b>Cero merges</b> automáticos.",
    "✓ Cambios locales no relacionados (T1.5 PDFs untracked) <b>no fueron tocados</b>.",
    "Solo se creó este addendum + una entry en docs/planes/README.md.",
]))

story.append(H1("9. Siguiente paso recomendado"))

story.extend(bullets([
    "<b>1. Owner revisa y aprueba</b> el addendum (o sugiere ajustes).",
    "<b>2.</b> Si aprueba: M0.1 / M0.2 / M0.3 entran <b>dentro de "
    "T1.6</b> (observabilidad mínima) con scope ampliado, sin sumar "
    "PR aparte. Esto deja listo el catálogo + permisos antes de M1.",
    "<b>3.</b> M1 (Playbooks engine + Diagnóstico) entra <b>después de "
    "T1.7 (top-ups) o T2.0 (onboarding premium)</b>, decisión owner "
    "según qué bloquee más al primer usuario.",
    "<b>4.</b> M2–M4 quedan en backlog estratégico, sin compromiso de "
    "fecha hasta tener M1 funcionando con un playbook real en "
    "producción.",
]))

story.append(WARN(
    "<b>Cuándo mergear este addendum:</b> si el owner lo aprueba, va "
    "como PR pequeño <i>pr/addendum-manus-integration</i> agregando "
    "Addendum_Manus_Integration_2026-05-05.md (+ PDF) y la entry en "
    "docs/planes/README.md. No requiere Stripe Dashboard, env vars, "
    "deploy ni cambios de código."
))

# ── Footer ────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-05 · "
    "Repo: Dona-agent · Addendum estratégico · sin código · sin deploy · "
    "sin modificaciones a infraestructura externa. Vigente con "
    "Plan_Dona_v2_1_2026-04-30.pdf."
))


# ── Build ─────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="Addendum — Integración Manus en Dona",
    author="Claude Code",
    subject="Addendum estratégico Manus / Dona · 2026-05-05",
)
doc.build(story)
print(f"OK: {OUTPUT}")
