"""
Genera Reporte_Post_Phase0_Dona_2026-05-01.pdf con el reporte final
post-Phase 0 tras los merges de T0.2, T0.3 y T0.4.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Reporte_Post_Phase0_Dona_2026-05-01.pdf"

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
styles.add(ParagraphStyle(
    name="BulletSub", parent=styles["Body"], leftIndent=28, bulletIndent=14,
    spaceAfter=2, fontSize=9,
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


def sub_bullets(items):
    return [Paragraph("&ndash; " + it, styles["BulletSub"]) for it in items]


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
    s.append(Paragraph("Dona — Reporte final post-Phase 0", styles["TitleBig"]))
    s.append(Paragraph(
        "Fecha: 2026-05-01 &nbsp;·&nbsp; HEAD origin/main: 32da747 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin acciones realizadas en este reporte.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Phase 0 cerrada.</b> Los 3 P0 originales del Plan v2.1 estan mergeados y desplegados: "
        "STRIPE_WEBHOOK_SECRET (T0.2, commit 58c806b), META_APP_SECRET (T0.3, f79b069), "
        "INBOUND_WEBHOOK_SECRET (T0.4, 32da747). Render verde, WhatsApp/Meta activo, "
        "landing carga. Pendientes: T0.10 Whapi sin firma + gap funcional Stripe/backend de creditos."
    ))

    # ── 1. Estado git ───────────────────────────────────────────────────
    s.append(H1("1. Estado actual de git"))
    s.extend(bullets([
        "<b>Rama actual local</b>: pr/inbound-webhook-secret-obligatorio (HEAD c76219d).",
        "<b>Ultimo commit en origin/main</b>: 32da747 &mdash; Merge pull request #9 from celestinojbm/pr/inbound-webhook-secret-obligatorio.",
        "<b>git status -sb</b>: ## pr/inbound-webhook-secret-obligatorio...origin/pr/inbound-webhook-secret-obligatorio (sin cambios pendientes; los untracked son los PDFs/scripts de planificacion generados durante la conversacion).",
        "<b>main local</b>: sigue en f79b069 (post-T0.3) &mdash; desincronizado respecto a origin/main (32da747). Los merges de T0.4 ocurrieron en GitHub. No es problema; se alinea con <i>git checkout main &amp;&amp; git pull --ff-only origin main</i> cuando lo decidas.",
    ]))

    s.append(H3("Ramas PR locales (9)"))
    ramas_locales = (
        "pr/disclaimer-responsable\n"
        "pr/docs-housekeeping\n"
        "pr/inbound-webhook-secret-obligatorio  <- rama actual\n"
        "pr/legacy-inventory\n"
        "pr/log-sanitization-json\n"
        "pr/meta-webhook-firma-obligatoria\n"
        "pr/stripe-webhook-firma-obligatoria\n"
        "pr/tools-docs-firefly-higgsfield\n"
        "pr/voice-forward-env\n"
    )
    s.append(CODE(ramas_locales))

    s.append(H3("Ramas PR remotas (9, mismas)"))
    s.append(P(
        "Las 9 ramas siguen en origin. Todas ya mergeadas en main (cada una corresponde a un PR cerrado en GitHub, "
        "no eliminado automaticamente al mergear)."
    ))

    # ── 2. Confirmacion de los 3 P0 ────────────────────────────────────
    s.append(H1("2. Confirmacion de los 3 P0 mergeados"))
    s.append(P("Los 3 fixes estan presentes en origin/main:"))
    p0_rows = [
        ["PR", "Merge commit", "Verificacion en origin/main"],
        ["T0.2 Stripe", "58c806b",
         "agent/billing.py:34 'Fail-fast: STRIPE_WEBHOOK_SECRET obligatorio en produccion' + RuntimeError linea 44"],
        ["T0.3 Meta", "f79b069",
         "agent/providers/meta.py:107 'Fail-fast: META_APP_SECRET obligatorio en produccion' + RuntimeError linea 116"],
        ["T0.4 Inbound", "32da747",
         "agent/inbound_tokens.py:32 'Fail-fast: INBOUND_WEBHOOK_SECRET obligatorio en produccion' + RuntimeError linea 41"],
    ]
    s.append(small_table(para_rows(p0_rows),
                         col_widths=[2.5*cm, 2.0*cm, 12.5*cm]))

    s.append(P("<b>Imports top-level</b> en agent/main.py (forzar checks al startup):"))
    imports_block = (
        "agent/main.py:30  import agent.billing            # noqa: F401  (T0.2)\n"
        "agent/main.py:35  import agent.inbound_tokens     # noqa: F401  (T0.4)\n"
    )
    s.append(CODE(imports_block))
    s.append(P(
        "<i>(T0.3 no requirio import top-level &mdash; el check vive en el __init__ de ProveedorMeta, que se "
        "instancia ya en main.py:54 cuando obtener_proveedor() se invoca.)</i>"
    ))

    # ── 3. Resumen de seguridad ────────────────────────────────────────
    s.append(H1("3. Resumen de seguridad"))

    s.append(H2("3.1 Riesgos P0 cerrados"))
    riesgos_rows = [
        ["Riesgo", "Antes", "Ahora"],
        ["Acreditacion forjable de creditos via Stripe webhook",
         "Backend /webhook/stripe aceptaba payloads sin firma con warning",
         "Produccion aborta deploy si falta STRIPE_WEBHOOK_SECRET; runtime rechaza igual (defensa en profundidad)"],
        ["Inyeccion de mensajes WhatsApp falsos via webhook Meta",
         "_verificar_firma retornaba True sin app_secret",
         "Produccion aborta deploy si falta META_APP_SECRET; runtime rechaza igual"],
        ["Tokens inbound forjados (Zapier/Make/n8n) -> mensajes WhatsApp arbitrarios",
         "Fallback derivado de ADMIN_TOKEN o literal publico del repo",
         "Produccion aborta deploy si falta INBOUND_WEBHOOK_SECRET; _secreto() rechaza con RuntimeError igual"],
    ]
    s.append(small_table(para_rows(riesgos_rows),
                         col_widths=[5.5*cm, 5.5*cm, 6.0*cm]))

    s.append(H2("3.2 Endpoints protegidos"))
    endpoints_rows = [
        ["Endpoint", "Pre-Phase 0", "Post-Phase 0"],
        ["POST /webhook/stripe (backend)",
         "Acepta sin firma con warning",
         "Firma obligatoria en prod"],
        ["POST /webhook (backend, Meta)",
         "Acepta sin firma con warning",
         "Firma obligatoria en prod"],
        ["POST /webhook/inbound/{token} (backend)",
         "Token forjable con secret derivado/literal",
         "Token solo verificable con secret real"],
        ["POST /api/webhook (landing Stripe)",
         "Ya tenia firma obligatoria (! non-null)",
         "Sin cambios &mdash; fuera de alcance"],
    ]
    s.append(small_table(para_rows(endpoints_rows),
                         col_widths=[5.5*cm, 5.5*cm, 6.0*cm]))

    s.append(H2("3.3 Variables ahora obligatorias en produccion"))
    s.append(P(
        "Tres env vars criticas. Si falta alguna en ENVIRONMENT=production, el deploy aborta con RuntimeError "
        "antes de servir trafico:"
    ))
    vars_rows = [
        ["Variable", "Plataforma", "Modulo que la valida"],
        ["STRIPE_WEBHOOK_SECRET", "Render", "agent/billing.py"],
        ["META_APP_SECRET", "Render (solo si WHATSAPP_PROVIDER=meta)", "agent/providers/meta.py"],
        ["INBOUND_WEBHOOK_SECRET", "Render", "agent/inbound_tokens.py"],
    ]
    s.append(small_table(para_rows(vars_rows),
                         col_widths=[5.5*cm, 6.0*cm, 5.5*cm]))
    s.append(P("Ya confirmaste las tres seteadas en Render."))

    # ── 4. Estado operativo ────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("4. Estado operativo"))

    s.append(H2("4.1 Render"))
    s.extend(bullets([
        "Ultimo deploy verificado tras merge de pr/inbound-webhook-secret-obligatorio (32da747).",
        "Las 3 env vars criticas presentes. Sin RuntimeError al startup.",
        "Web service con Gunicorn 1 worker (ver Dockerfile:12 &mdash; sin cambios; pendiente para T4.2 si se escala).",
    ]))

    s.append(H2("4.2 WhatsApp / Meta"))
    s.extend(bullets([
        "Provider activo: WHATSAPP_PROVIDER=meta confirmado por vos en T0.3.",
        "Validacion HMAC X-Hub-Signature-256 ahora obligatoria.",
        "Replay protection (timestamp window 600 s) ya estaba activa, sigue funcionando.",
        "Mensajes del owner llegan correctamente (verificado manualmente por vos).",
    ]))

    s.append(H2("4.3 Stripe landing webhook"))
    s.extend(bullets([
        "URL configurada en Stripe Dashboard: https://www.usadona.com/api/stripe/webhook segun tu reporte previo.",
        "<b>Recordatorio del Diagnostico T0.2 corregido</b>: esa ruta no existe en el repo (existe /api/webhook solo). Si los webhooks estan dando 404 silencioso, el welcome WhatsApp post-pago no se entrega. <b>No verificado en este reporte</b> &mdash; pendiente operativo (Bloque 1 del Diagnostico T0.2 corregido).",
    ]))

    s.append(H2("4.4 usadona.com (landing)"))
    s.extend(bullets([
        "Carga correctamente (verificado por vos).",
        "Disclaimer responsable (PR4) ya en produccion desde el merge de Phase 0 inicial.",
        "TS check sin errores nuevos al cierre del ultimo PR.",
    ]))

    # ── 5. Pendientes restantes ────────────────────────────────────────
    s.append(H1("5. Pendientes restantes"))

    s.append(H2("5.1 Seguridad — P0 nuevo (descubierto en T0.3)"))
    s.append(P(
        "<b>T0.10 &mdash; Whapi sin firma de webhook.</b> agent/providers/whapi.py no implementa validacion. "
        "Si en algun momento WHATSAPP_PROVIDER se cambia a whapi, el endpoint /webhook aceptaria payloads "
        "forjados desde cualquier IP. <b>Hoy no es activo</b> (provider es Meta), pero queda como deuda P0 "
        "para no olvidar al rotar provider o ante un cambio no planificado."
    ))

    s.append(H2("5.2 Housekeeping git"))
    s.extend(bullets([
        "<b>9 ramas remotas pr/*</b> siguen en origin sin borrar despues del merge. No es funcional, pero limpia historia. Borrarlas via UI de cada PR cerrado o <i>git push origin --delete pr/&lt;nombre&gt;</i> (uno por uno).",
        "<b>9 ramas locales pr/*</b> tambien siguen. <i>git branch -d pr/&lt;nombre&gt;</i> cuando esten mergeadas.",
        "<b>main local desincronizado</b> respecto a origin/main (f79b069 -> 32da747). <i>git checkout main &amp;&amp; git pull --ff-only</i> para alinear.",
    ]))

    s.append(H2("5.3 Housekeeping documental"))
    s.append(P(
        "Untracked en working tree (todos artefactos de planificacion generados durante la conversacion, "
        "ninguno en codigo productivo):"
    ))
    s.extend(bullets([
        "4 PDFs Diagnostico_T0X_*.pdf",
        "1 PDF Reporte_PostMerge_*.pdf",
        "3 PDFs Resumen_T0X_Implementacion_*.pdf",
        "6 scripts generar_*_pdf.py",
    ]))
    s.append(P(
        "Convendria un PR pr/docs-housekeeping-2 siguiendo el patron anterior: mover PDFs a docs/auditorias/ o "
        "docs/planes/ y scripts a docs/scripts/."
    ))

    s.append(H2("5.4 Gap funcional critico — Stripe / backend de creditos"))
    s.append(P("<b>Identificado en el Diagnostico T0.2 corregido (§3) y aun sin resolver:</b>"))
    gap_rows = [
        ["Cliente paga $20/$40 mensual en Stripe", "Estado actual"],
        ["Stripe cobra al cliente", "OK"],
        ["Welcome WhatsApp se envia",
         "depende de si la URL /api/stripe/webhook resuelve a 404 o a /api/webhook"],
        ["Creditos acreditados en backend Dona", "<b>ninguno</b>"],
        ["Suscripcion persistida en DB del backend", "<b>ninguno</b>"],
        ["Plan/tier sincronizado en backend", "<b>ninguno</b>"],
    ]
    s.append(small_table(para_rows(gap_rows),
                         col_widths=[10.0*cm, 7.0*cm]))
    s.append(P(
        "El backend Python procesa creditos (agent/billing.py:procesar_evento_stripe) pero <b>nadie le manda "
        "webhooks</b> porque Stripe esta apuntado al landing. Como el landing tampoco acredita, <b>los pagos "
        "quedan sin contraparte funcional en Dona</b>."
    ))
    s.append(P(
        "Esto <b>no es</b> un riesgo de seguridad &mdash; es un <b>gap operativo</b> que afecta la promesa del "
        "producto. Es <b>T1.3</b> del Plan v2.1 ('Migrar billing a fuente unica backend Python'). Cierre P0 "
        "tecnico OK pero gap funcional sigue abierto."
    ))

    s.append(H2("5.5 Phase 1 pendiente del Plan v2.1"))
    s.append(P("Tareas que <b>no son P0</b> pero ya estan planificadas:"))
    s.extend(bullets([
        "<b>T1.1 / T1.2</b> &mdash; Workspace + resolver telefono -> workspace_id (migracion progresiva).",
        "<b>T1.3</b> &mdash; Migrar billing a fuente unica backend (resuelve §5.4).",
        "<b>T1.4</b> &mdash; Plan + creditos incluidos + top-ups + Customer Portal.",
        "<b>T1.5</b> &mdash; Cifrado A.3 (mensajes, business tables).",
        "<b>T1.6</b> &mdash; Audit log append-only.",
        "<b>T1.8</b> &mdash; System prompt premium ('lider de operaciones').",
    ]))

    s.append(H2("5.6 Operativos pendientes (no P0)"))
    s.extend(bullets([
        "<b>Verificacion operativa</b> del Bloque 1 del Diagnostico T0.2 corregido: confirmar URL exacta del webhook Stripe en Dashboard y si los welcome WhatsApp llegan a clientes recientes.",
        "<b>Sentry / Variante B de PR1</b> &mdash; observabilidad activa pendiente para T4.4.",
        "<b>CI</b> &mdash; GitHub Actions con pytest + lint + typecheck (T4.5).",
    ]))

    # ── 6. Proximo orden recomendado ───────────────────────────────────
    s.append(PageBreak())
    s.append(H1("6. Proximo orden recomendado (sin implementar)"))

    s.append(H2("Prioridad inmediata (housekeeping, riesgo cero)"))
    s.extend(bullets([
        "<b>Borrar las 9 ramas remotas pr/* mergeadas</b> desde GitHub UI (cada PR cerrado tiene boton 'Delete branch').",
        "<b>Borrar las 9 ramas locales pr/*</b> y volver main local a origin/main (32da747).",
        "<b>Smoke check operacional</b>: un mensaje WhatsApp de ida-vuelta, una carga de usadona.com, una llamada a /voice/reenviar, una invocacion a GET /admin/inbound/token con generacion de token + POST de prueba al endpoint inbound. Tres minutos.",
    ]))

    s.append(H2("Prioridad alta (cerrar gap funcional + ultimo P0)"))
    s.extend(bullets([
        "<b>Verificar URL del webhook Stripe en Dashboard</b> (Bloque 1 del Diagnostico T0.2 corregido). Si es /api/stripe/webhook y no existe -> arreglar o cambiar a /api/webhook. <b>Decision operativa, sin codigo.</b>",
        "<b>T1.3 &mdash; Migrar billing a fuente unica backend Python.</b> Cierra el gap §5.4. Un cliente que paga $20/$40 deberia recibir creditos en el backend. PR de tamano medio (~100-200 lineas).",
        "<b>T0.10 &mdash; Whapi firma de webhook.</b> Hoy no es activo pero deja la deuda cerrada antes de cualquier cambio futuro de provider. PR pequeno (~30 lineas).",
    ]))

    s.append(H2("Prioridad media (housekeeping documental + Phase 1)"))
    s.extend(bullets([
        "<b>PR de housekeeping documental</b> (pr/docs-housekeeping-2): mover los 8 PDFs y 6 scripts untracked a docs/. Mismo patron que el primer housekeeping.",
        "<b>T1.1 / T1.2</b> &mdash; Empezar Workspace + resolver progresivo. Bloqueante para T1.3+ a futuro pero T1.3 puede hacerse antes con telefono directo y migrar despues.",
        "<b>Decidir matriz plan ↔ creditos ↔ tools</b> (T1.4) &mdash; bloqueador previo a Phase 1.",
    ]))

    s.append(H2("Prioridad baja (Phase 4)"))
    s.extend(bullets([
        "<b>T4.4</b> &mdash; Sentry + alertas (Variante B del PR1 original).",
        "<b>T4.5</b> &mdash; CI GitHub Actions.",
    ]))

    # Cierre
    s.append(H1("Cierre"))
    s.extend(bullets([
        "Phase 0 (3 P0 originales) <b>cerrada</b> en produccion: STRIPE_WEBHOOK_SECRET, META_APP_SECRET, INBOUND_WEBHOOK_SECRET obligatorios y verificados.",
        "Render verde, WhatsApp activo, landing carga.",
        "Proximo bloque critico: gap funcional de creditos (T1.3) + housekeeping de ramas.",
        "T0.10 Whapi queda como deuda P0 conocida pero no activa hoy.",
    ]))
    s.append(Spacer(1, 8))
    s.append(C("Sin acciones realizadas en este reporte."))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Reporte final post-Phase 0",
        author="Reporte generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch, "Dona — Reporte final post-Phase 0 · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
