"""
Genera Reporte_Post_Housekeeping_Dona_2026-05-01.pdf con el reporte final
post-housekeeping (post merge PR #10 docs-housekeeping-2).

No toca archivos del proyecto. No envia datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether,
)

OUTPUT = r"C:\Users\celes\Dona-agent\Reporte_Post_Housekeeping_Dona_2026-05-01.pdf"

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
    name="H1", parent=styles["Heading1"], fontSize=16, leading=20,
    spaceBefore=18, spaceAfter=8, textColor=colors.HexColor("#111111"),
))
styles.add(ParagraphStyle(
    name="H2", parent=styles["Heading2"], fontSize=13, leading=17,
    spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1f2937"),
))
styles.add(ParagraphStyle(
    name="H3", parent=styles["Heading3"], fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#374151"),
))
styles.add(ParagraphStyle(
    name="Body", parent=styles["BodyText"], fontSize=9.5, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=6, textColor=colors.HexColor("#222222"),
))
styles.add(ParagraphStyle(
    name="BodyTight", parent=styles["BodyText"], fontSize=9, leading=12,
    alignment=TA_LEFT, spaceAfter=2, textColor=colors.HexColor("#222222"),
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
def H3(t): return Paragraph(t, styles["H3"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])
def BANNER(t): return Paragraph(t, styles["Banner"])


def bullets(items):
    return [Paragraph("&bull; " + it, styles["BulletDona"]) for it in items]


def small_table(rows, col_widths, header=True, font_size=8.5):
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", font_size),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#9ca3af")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", font_size),
    ]
    t.setStyle(TableStyle(style))
    return t


def para_rows(rows):
    return [[Paragraph(c, styles["BodyTight"]) for c in r] for r in rows]


def build_story():
    s = []

    # Portada
    s.append(Paragraph("Dona — Reporte final post-housekeeping", styles["TitleBig"]))
    s.append(Paragraph(
        "Fecha: 2026-05-01 &nbsp;·&nbsp; HEAD origin/main: 49978a9 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin acciones realizadas en este reporte.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>PR #10 docs-housekeeping-2 mergeado a main.</b> 22 archivos movidos a docs/auditorias/ "
        "y docs/scripts/. Phase 0 cerrada desde antes. Producto sin alteraciones funcionales en este "
        "PR (100% documental). Pendientes activos: T1.3 (gap funcional Stripe/backend), T0.10 (Whapi "
        "sin firma, no activo) y mini-housekeeping (sync main + borrar rama mergeada)."
    ))

    # ── 1. Estado git ───────────────────────────────────────────────────
    s.append(H1("1. Estado actual de git"))
    estado_rows = [
        ["Item", "Valor"],
        ["Rama actual local",
         "pr/docs-housekeeping-2 (HEAD cc96ccb &mdash; docs: organize Phase 0 audits, reports and scripts)"],
        ["main local",
         "32da747 &mdash; Merge pull request #9 from celestinojbm/pr/inbound-webhook-secret-obligatorio"],
        ["origin/main",
         "49978a9 &mdash; Merge pull request #10 from celestinojbm/pr/docs-housekeeping-2"],
        ["git status -sb",
         "## pr/docs-housekeeping-2...origin/pr/docs-housekeeping-2 (rama actual en sync con su upstream)"],
        ["Working tree", "limpio respecto a tracked files"],
        ["Untracked", "2 archivos generados durante el resumen del housekeeping-2"],
    ]
    s.append(small_table(para_rows(estado_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    s.append(P("<b>main local vs origin/main:</b>"))
    s.extend(bullets([
        "main local en 32da747, origin/main en 49978a9.",
        "<b>DIFIEREN: 2 commits detras</b> (le faltan cc96ccb y 49978a9, ambos del PR #10).",
        "Es <b>fast-forward simple</b>, no hay divergencia.",
    ]))

    # ── 2. Confirmaciones ──────────────────────────────────────────────
    s.append(H1("2. Confirmaciones"))

    s.append(H2("2.1 PR #10 esta en origin/main"))
    s.append(P("Confirmado:"))
    log_pr10 = (
        "49978a9 Merge pull request #10 from celestinojbm/pr/docs-housekeeping-2\n"
        "cc96ccb docs: organize Phase 0 audits, reports and scripts\n"
    )
    s.append(CODE(log_pr10))
    s.append(P("<b>Contenido en produccion</b> post-merge:"))
    s.extend(bullets([
        "docs/auditorias/ -> <b>12 archivos</b> (1 previo + 11 del housekeeping-2)",
        "docs/scripts/ -> <b>15 archivos</b> (4 previos + 11 del housekeeping-2)",
        "Total movido por el PR #10: 22 archivos nuevos.",
    ]))

    s.append(H2("2.2 Ramas pr/*"))
    ramas_rows = [
        ["Tipo", "Cantidad", "Detalle"],
        ["Locales", "1", "pr/docs-housekeeping-2 (rama actual, mergeada)"],
        ["Remotas", "1", "origin/pr/docs-housekeeping-2 (mergeada en GitHub via PR #10)"],
    ]
    s.append(small_table(para_rows(ramas_rows),
                         col_widths=[2.5*cm, 2.0*cm, 12.5*cm]))
    s.append(P(
        "<b>Las 9 ramas previas (pr/disclaimer-responsable, pr/legacy-inventory, etc.) ya fueron borradas "
        "en el housekeeping anterior.</b> Solo queda esta nueva, lista para limpiar."
    ))

    s.append(H2("2.3 Untracked en raiz"))
    s.append(P("2 archivos generados durante el resumen del housekeeping-2 anterior:"))
    untracked = (
        "Resumen_Docs_Housekeeping_2_2026-05-01.pdf\n"
        "generar_resumen_docs_housekeeping_2_pdf.py\n"
    )
    s.append(CODE(untracked))
    s.append(P(
        "Ambos son artefactos de planificacion. Coherente con el patron anterior, irian a docs/auditorias/ "
        "y docs/scripts/ en una iteracion futura. Cantidad muy pequena &mdash; no urgente."
    ))

    # ── 3. Estado operativo ────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("3. Estado operativo"))

    s.append(H2("3.1 Render / deploy"))
    s.extend(bullets([
        "Ultimo deploy verificado fue post-merge T0.4 (Phase 0 cerrada).",
        "<b>PR #10 NO desencadena deploy funcional</b>: solo movio archivos bajo docs/. Render redespliega ante cualquier push a main, pero el codigo de runtime no cambio, asi que el comportamiento es identico.",
        "Si Render redeployo automaticamente al merge de PR #10, deberia haber pasado el startup check (agent.billing y agent.inbound_tokens siguen igual; agent/providers/meta.py sin cambios).",
    ]))

    s.append(H2("3.2 WhatsApp / Meta"))
    s.extend(bullets([
        "Provider activo: WHATSAPP_PROVIDER=meta (confirmado en T0.3).",
        "Validacion HMAC X-Hub-Signature-256 obligatoria desde T0.3 mergeado.",
        "Sin cambios en este PR.",
    ]))

    s.append(H2("3.3 Landing usadona.com"))
    s.extend(bullets([
        "Disclaimer responsable mergeado en Phase 0 inicial.",
        "Sin cambios en este PR.",
    ]))

    s.append(P(
        "<b>Resumen operativo:</b> produccion <b>sin alteraciones funcionales</b> desde el cierre de Phase 0. "
        "PR #10 fue 100% documental."
    ))

    # ── 4. Pendientes ──────────────────────────────────────────────────
    s.append(H1("4. Pendientes restantes priorizados"))

    s.append(H2("4.1 Housekeeping menor (riesgo cero)"))
    hk_rows = [
        ["Item", "Detalle"],
        ["main local desactualizado",
         "2 commits detras de origin/main. Fix: <i>git checkout main &amp;&amp; git pull --ff-only origin main</i>."],
        ["Rama pr/docs-housekeeping-2 local",
         "Mergeada. Lista para borrar con <i>git branch -d pr/docs-housekeeping-2</i> (despues de cambiar a main)."],
        ["Rama origin/pr/docs-housekeeping-2",
         "Mergeada. Lista para borrar con <i>git push origin --delete pr/docs-housekeeping-2</i>."],
        ["2 untracked en raiz",
         "Resumen_Docs_Housekeeping_2_*.pdf y su script. Pequeno volumen &mdash; pueden vivir untracked hasta el proximo housekeeping documental, o moverse manualmente a docs/auditorias/ y docs/scripts/."],
    ]
    s.append(small_table(para_rows(hk_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(H2("4.2 Pendientes funcionales (de mayor a menor impacto)"))

    s.append(H3("T1.3 — Cerrar gap funcional Stripe / backend de creditos  (prioridad alta)"))
    s.extend(bullets([
        "<b>El gap mas critico del producto hoy.</b> Cliente paga $20/$40 mensual en Stripe, pero el backend Dona no acredita creditos ni persiste suscripcion.",
        "Identificado en el Diagnostico T0.2 corregido (§3) y el reporte post-Phase 0 (§5.4).",
        "PR de tamano medio (~100-200 lineas estimadas).",
        "<b>Bloqueador asociado:</b> confirmar URL exacta del webhook Stripe en Dashboard. Si esta apuntando a /api/stripe/webhook que no existe, los pagos estan dando 404 silencioso. Verificacion operativa de ~5 minutos sin codigo.",
    ]))

    s.append(H3("T0.10 — Whapi sin firma  (prioridad media, deuda conocida)"))
    s.extend(bullets([
        "agent/providers/whapi.py no implementa validacion de firma de webhook.",
        "<b>Hoy NO esta activo</b> porque WHATSAPP_PROVIDER=meta.",
        "Riesgo se materializaria si en algun momento se cambiara el provider a whapi. Mejor cerrarlo antes para que no quede deuda olvidada.",
        "PR pequeno (~30 lineas).",
    ]))

    s.append(H3("Phase 1 del Plan v2.1  (prioridad media-baja, despues de T1.3)"))
    s.extend(bullets([
        "<b>T1.1 / T1.2</b> &mdash; Workspace + resolver telefono -> workspace_id (migracion progresiva).",
        "<b>T1.4</b> &mdash; Plan + creditos incluidos + top-ups + Stripe Customer Portal.",
        "<b>T1.5</b> &mdash; Cifrado A.3 (mensajes, business tables).",
        "<b>T1.6</b> &mdash; Audit log append-only.",
        "<b>T1.8</b> &mdash; System prompt premium ('lider de operaciones').",
    ]))

    s.append(H3("Observabilidad / CI  (prioridad baja, Phase 4)"))
    s.extend(bullets([
        "<b>T4.4</b> &mdash; Sentry + alertas (Variante B del PR1 original).",
        "<b>T4.5</b> &mdash; CI GitHub Actions con pytest + lint + typecheck.",
    ]))

    s.append(H2("4.3 Operativos (sin codigo)"))
    s.extend(bullets([
        "Verificar <b>URL exacta del webhook Stripe en Dashboard</b> y revisar <b>Webhook attempts</b> (200 vs 404) en la pestana de eventos de Stripe. Bloque 1 del Diagnostico T0.2 corregido. Decision sin codigo de ~5 minutos. Es prerrequisito para T1.3.",
    ]))

    # ── 5. Proximo paso ────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("5. Proximo paso recomendado (sin implementar nada)"))

    s.append(H2("Orden sugerido"))

    s.append(P("<b>1. Mini-housekeeping post-PR #10</b> (3 minutos, riesgo cero):"))
    s.extend(bullets([
        "<i>git checkout main &amp;&amp; git pull --ff-only origin main</i> -> sincronizar main local a 49978a9.",
        "<i>git branch -d pr/docs-housekeeping-2</i> -> borrar rama local mergeada.",
        "<i>git push origin --delete pr/docs-housekeeping-2</i> -> borrar rama remota.",
        "Decidir que hacer con los 2 untracked nuevos (mover manualmente a docs/ o dejar para acumular hasta el proximo housekeeping).",
    ]))

    s.append(P("<b>2. Verificacion operativa Stripe Dashboard</b> (5 minutos, sin codigo):"))
    s.extend(bullets([
        "Confirmar URL exacta del webhook (/api/webhook o /api/stripe/webhook).",
        "Revisar ultimos 5 'Webhook attempts' en Stripe -> deberian responder 200.",
        "Validar con un cliente real reciente si recibio welcome WhatsApp post-pago.",
        "Si la URL es 404 -> ajustar Dashboard o crear landing/app/api/stripe/webhook/route.ts. Decision operativa, no PR todavia.",
    ]))

    s.append(P("<b>3. T0.10 Whapi sin firma</b> (PR pequeno, ~30 lineas):"))
    s.extend(bullets([
        "Cierra deuda P0 conocida antes de Phase 1.",
        "Bajo riesgo (provider no activo).",
        "Diagnostico previo ya hecho durante T0.3.",
    ]))

    s.append(P("<b>4. T1.3 Migrar billing a fuente unica backend Python</b> (PR de tamano medio):"))
    s.extend(bullets([
        "El gap mas impactante para el producto.",
        "Requiere primero la verificacion operativa del paso 2.",
        "Conecta el cobro de suscripcion con el sistema de creditos existente.",
        "Resuelve §5.4 del reporte post-Phase 0 ('cliente paga pero Dona no entrega').",
    ]))

    s.append(P("<b>5. Phase 1 (T1.1, T1.2, T1.4, T1.5, etc.)</b> &mdash; despues de cerrar el gap funcional."))

    s.append(H2("Lo que no recomiendo"))
    s.extend(bullets([
        "<b>No empezar Phase 1 hasta cerrar T1.3.</b> Workspace, identidad, dashboard premium son features grandes que tienen sentido cuando el flujo basico de cobro->entrega funciona. Hoy ese flujo esta roto en produccion.",
        "<b>No tocar T4.4 / T4.5</b> todavia. Sentry y CI son utiles pero no criticos. Mejor invertir tiempo en T1.3 + T0.10 primero.",
    ]))

    # ── 6. Resumen ejecutivo ───────────────────────────────────────────
    s.append(H1("6. Resumen ejecutivo"))
    s.extend(bullets([
        "<b>PR #10 housekeeping-2</b> esta en origin/main (49978a9). 22 archivos movidos a docs/auditorias/ y docs/scripts/.",
        "<b>Phase 0 cerrada</b> desde antes: 3 P0 originales (Stripe/Meta/Inbound) + housekeeping de ramas mergeadas.",
        "<b>Deuda activa visible:</b> 1 rama local + 1 remota (pr/docs-housekeeping-2) lista para limpiar, main local 2 commits detras, 2 untracked nuevos en raiz.",
        "<b>Pendiente critico funcional:</b> T1.3 (gap Stripe/backend de creditos) &mdash; afecta promesa del producto pero no la seguridad. Requiere verificacion operativa previa de la URL del webhook Stripe.",
        "<b>Deuda P0 dormida:</b> T0.10 (Whapi sin firma) &mdash; no activa hoy, conviene cerrar antes que se active.",
    ]))

    s.append(Spacer(1, 8))
    s.append(C("Sin acciones realizadas. Me detengo aqui."))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Reporte final post-housekeeping",
        author="Reporte generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Reporte final post-housekeeping · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
