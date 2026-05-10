"""
Genera Resumen_Hotfix_Action_Center_Perfil_Insuficiente_2026-05-10.pdf ·
hotfix mínimo para que el Action Center explique al usuario por qué no
genera acciones cuando el perfil de negocio está vacío o incompleto.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_Hotfix_Action_Center_Perfil_Insuficiente_2026-05-10.pdf"

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

story.append(Paragraph("Hotfix · Action Center · perfil insuficiente",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · Branch <b>hotfix/action-center-perfil-insuficiente</b> "
    "· base <b>main@820af68</b> · cambios cirujanos · sin "
    "refactor · compatible con producción",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Hotfix listo. <b>827 pytest · 37 vitest · "
    "tsc 0 · build 17/17 · lint 0 errors</b>. El Action Center "
    "ahora explica al usuario por qué no genera acciones cuando "
    "el perfil de negocio está vacío o incompleto, con CTA "
    "explícito a WhatsApp. <b>Sin merge · sin deploy · sin env "
    "changes · sin acciones externas reales.</b>"
))

# ── 1. Resumen del problema ──────────────────────────────────────────

story.append(H1("1. Resumen del problema"))

story.append(P(
    "El Action Center carga correctamente, pero presionar 'Generar "
    "acciones' devuelve 0 resultados sin explicación. El usuario "
    "queda en un loop visual: empty state → click 'Generar' → "
    "vuelve al empty state. No hay forma desde la UI de descubrir "
    "que el problema es <b>perfil de negocio vacío o incompleto</b>."
))

# ── 2. Causa raíz ────────────────────────────────────────────────────

story.append(H1("2. Causa raíz"))

story.append(P(
    "<i>agent/automation/opportunities.py:detectar_oportunidades_para"
    "_telefono</i> retorna <b>lista vacía silenciosamente</b> en dos "
    "casos:"
))

story.append(CODE(
    "if not perfil or not perfil.nombre_negocio:\n"
    "    return []   # ← silencioso · sin razón ni siguiente_paso"
))

story.extend(bullets([
    "Caso A: el usuario no tiene fila en <i>perfil_negocio</i> "
    "(nunca pasó por el onboarding WhatsApp).",
    "Caso B: existe la fila pero <i>nombre_negocio</i> está vacío "
    "(onboarding interrumpido en el paso 0).",
    "Caso C (no detectado por el código actual): perfil con nombre "
    "pero <b>todos los campos del diagnóstico extendido (T2.0.E.1) "
    "vacíos</b>. Las 6 reglas del Opportunity Engine requieren "
    "información del diagnóstico · sin nada llenan, ninguna regla "
    "matchea.",
]))

story.append(P(
    "Los endpoints HTTP (<i>/admin/automation/oportunidades</i>, "
    "<i>/internal/automation/acciones/generar</i>) propagan "
    "<i>count=0</i> al frontend sin metadata adicional. El "
    "componente UI no tiene forma de distinguir 'perfil insuficiente' "
    "de 'ya generaste todas las acciones'."
))

# ── 3. Archivos modificados · 5 ──────────────────────────────────────

story.append(H1("3. Archivos modificados · 5"))

story.append(make_table([
    ["Archivo", "Tipo", "Cambio"],
    ["agent/automation/opportunities.py", "MOD",
     "+ <i>analizar_estado_perfil(perfil)</i> · función pura · "
     "devuelve <i>{estado, campos_llenos, campos_totales, razon, "
     "siguiente_paso}</i>. + <i>cargar_perfil_dict(telefono)</i>. "
     "+ <i>detectar_oportunidades_con_estado_para_telefono</i> "
     "(versión enriquecida). La función legacy "
     "<i>detectar_oportunidades_para_telefono</i> se mantiene para "
     "retrocompatibilidad."],
    ["agent/main.py", "MOD",
     "4 endpoints actualizados: <i>/admin/automation/oportunidades</i>, "
     "<i>/admin/automation/acciones/generar</i>, "
     "<i>/internal/automation/oportunidades</i>, "
     "<i>/internal/automation/acciones/generar</i>. Ahora incluyen "
     "<i>perfil_estado</i>, <i>perfil_campos_llenos</i>, "
     "<i>perfil_campos_totales</i>, <i>perfil_razon</i>, "
     "<i>perfil_siguiente_paso</i> en la respuesta."],
    ["landing/lib/automation-types.ts", "MOD",
     "+ tipo <i>PerfilEstado = 'missing' | 'incomplete' | 'ready'</i>. "
     "+ <i>PerfilEstadoInfo</i> interface. <i>GenerarResponse</i> "
     "extiende <i>PerfilEstadoInfo</i>."],
    ["landing/app/dashboard/seccion-action-center.tsx", "MOD",
     "Componente captura <i>perfil_estado</i> en la respuesta de "
     "'Generar acciones' y muestra <b>banner explicativo</b> en el "
     "empty state cuando no es 'ready'. Estados visuales: "
     "'Diagnóstico pendiente' (missing) · 'Diagnóstico incompleto' "
     "(incomplete) con contador X/6 · CTA 'Abrir WhatsApp' + "
     "'Reintentar generar'."],
    ["tests/test_automation_perfil_estado.py", "NEW",
     "12 tests pytest · función pura · función async · "
     "retrocompatibilidad."],
    ["tests/test_automation_endpoints.py", "MOD",
     "+ 3 tests · admin oportunidades sin perfil → missing · "
     "perfil completo → ready · internal generar sin perfil → "
     "incluye perfil_estado."],
    ["landing/app/dashboard/seccion-action-center.test.tsx", "MOD",
     "+ 2 tests vitest · banner missing tras Generar · "
     "contador X/6 en incomplete. + cleanup() entre tests para "
     "evitar 'Found multiple elements'."],
], col_widths=[3.0*inch, 0.5*inch, 3.1*inch]))

# ── 4. Explicación del fix ───────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Explicación del fix"))

story.append(H2("Backend · 3 estados explícitos"))

story.append(make_table([
    ["estado", "Cuándo", "siguiente_paso"],
    ["missing", "no hay perfil_negocio · o nombre_negocio vacío",
     "Escribe 'empezar diagnóstico' a Dona por WhatsApp"],
    ["incomplete", "perfil con nombre · &lt;2 de 6 campos del "
     "diagnóstico T2.0.E.1 llenos",
     "Continúa el diagnóstico con Dona por WhatsApp"],
    ["ready", "≥2 campos del diagnóstico llenos",
     "(vacío) · Opportunity Engine ya genera acciones"],
], col_widths=[1.4*inch, 2.6*inch, 2.6*inch]))

story.append(H2("UI · banner contextual en el empty state"))

story.append(P(
    "El componente captura <i>perfil_estado</i> tras 'Generar "
    "acciones'. Si != 'ready', muestra:"
))

story.extend(bullets([
    "Header: <b>'Diagnóstico pendiente'</b> (missing) o "
    "<b>'Diagnóstico incompleto'</b> (incomplete).",
    "Razón legible: <i>'Aún no encontramos tu perfil de negocio'</i> "
    "o <i>'Tienes 1 de 6 campos del diagnóstico llenos. Necesitamos "
    "al menos 2 para generar acciones útiles.'</i>",
    "Para incomplete: contador <b>X/6 campos del diagnóstico llenos</b>.",
    "Siguiente paso accionable.",
    "Botones: <b>'Abrir WhatsApp'</b> (link a wa.me con texto "
    "pre-llenado <i>'empezar diagnóstico'</i>) y <b>'Reintentar "
    "generar'</b> (en caso de que el usuario haya completado el "
    "diagnóstico mientras tanto)."
]))

story.append(WARN(
    "<b>Si el usuario no presiona 'Generar acciones' aún · </b> el "
    "empty state inicial sigue mostrando 'Aún no hay acciones "
    "generadas'. El banner aparece tras la primera invocación. "
    "Esto es intencional: hasta que no llamamos al backend, no "
    "sabemos el estado del perfil."
))

# ── 5. Comandos ejecutados y resultados ──────────────────────────────

story.append(H1("5. Comandos ejecutados y resultados"))

story.append(make_table([
    ["Comando", "Resultado"],
    ["<i>pytest tests/test_automation_perfil_estado.py "
     "tests/test_automation_endpoints.py</i>",
     "<b>33/33 passing</b> · 27.7s"],
    ["<i>pytest</i> (suite completa)",
     "<b>827/827 passing</b> · 184s · cero regresiones"],
    ["<i>cd landing && npm test -- --run</i>",
     "<b>37/37 passing</b> · vitest+jsdom · 1.58s "
     "(15 auth-matcher + 13 bridge + 9 componente)"],
    ["<i>npx tsc --noEmit</i>", "0 errores"],
    ["<i>rm -rf .next && npm run build</i>",
     "17/17 pages OK"],
    ["<i>npm run lint</i>",
     "0 errors · 3 warnings preexistentes · exit 0"],
], col_widths=[3.2*inch, 3.4*inch]))

# ── 6. Riesgos restantes ─────────────────────────────────────────────

story.append(H1("6. Riesgos restantes"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Usuario completa el diagnóstico pero no presiona "
     "'Reintentar generar' · sigue viendo el banner antiguo en "
     "el cliente",
     "Cero · UX",
     "El banner solo aparece tras invocar 'Generar acciones'. Si "
     "ya hay acciones en lista, el banner no se muestra. "
     "Solución natural: el usuario presiona Reintentar."],
    ["Threshold '≥2 campos' es arbitrario",
     "Cero",
     "Coincide con la regla más laxa del Opportunity Engine "
     "(<i>_detectar_calendario_contenido</i> requiere solo "
     "canales_actuales y opcionalmente objetivo). Ajustable en una "
     "constante si se decide otro umbral."],
     ["wa.me sin número específico abre WhatsApp Web sin pre-rellenar "
      "destinatario",
     "Bajo",
     "El usuario debe seleccionar manualmente a Dona desde sus "
     "contactos. Si quieren mejorar, pueden agregar "
     "NEXT_PUBLIC_DONA_WHATSAPP_NUMBER (ya implementado en T2.0.D)."],
    ["Race condition aiosqlite en pytest workers",
     "Cero · solo dev",
     "Issue conocido · re-run pasa consistente."],
    ["analizar_estado_perfil considera 'ready' con solo 2 campos · "
     "podría ser muy permisivo",
     "Bajo",
     "Si solo hay 2 campos y ningún Opportunity Engine los matchea, "
     "se devolverían 0 acciones igual · el banner volvería a "
     "aparecer."],
], col_widths=[2.4*inch, 0.8*inch, 3.2*inch]))

# ── 7. Pasos siguientes recomendados ─────────────────────────────────

story.append(H1("7. Pasos siguientes recomendados"))

story.extend(bullets([
    "<b>Mergear este hotfix</b> · auto-redeploy Vercel + Render · "
    "smoke en producción.",
    "<b>Considerar</b> agregar al endpoint <i>/api/automation/"
    "acciones</i> (GET) la respuesta <i>perfil_estado</i> también, "
    "para mostrar el banner en el primer load · no solo tras "
    "presionar 'Generar'. PR aparte si se quiere.",
    "<b>Agregar telemetría</b> (futuro) para medir cuántos "
    "usuarios entran al Action Center con perfil_estado='missing' "
    "o 'incomplete' · sirve para priorizar mejor el flow de "
    "diagnóstico WhatsApp.",
    "<b>T2.1.D</b> (próximo bloque planificado) · reservas y "
    "descuento real de créditos · audit log extendido · pruning. "
    "Independiente de este hotfix.",
]))

# ── 8. Datos para abrir el PR ────────────────────────────────────────

story.append(H1("8. Instrucciones para abrir PR"))

story.append(make_table([
    ["Campo", "Valor"],
    ["URL",
     "github.com/celestinojbm/Dona-agent/pull/new/<br/>"
     "hotfix/action-center-perfil-insuficiente"],
    ["Título sugerido",
     "fix(automation): Action Center explica por qué no genera "
     "acciones cuando el perfil está incompleto"],
    ["Base", "main"],
    ["Head", "hotfix/action-center-perfil-insuficiente"],
], col_widths=[1.6*inch, 5.0*inch]))

story.append(BANNER(
    "<b>Branch pushed · sin merge.</b> Hotfix mínimo · sin "
    "refactor · compatible con producción · cero env changes · "
    "cero deploys · cero acciones externas reales."
))


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
