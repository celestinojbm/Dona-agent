"""
Genera Handoff_Session_Dona_2026-05-01.pdf con el handoff compacto para
que una nueva sesion Claude Code/ACP pueda continuar sin perder continuidad.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Handoff_Session_Dona_2026-05-01.pdf"

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
    textColor=colors.HexColor("#1e3a8a"), backColor=colors.HexColor("#dbeafe"),
    borderPadding=8, borderColor=colors.HexColor("#3b82f6"), borderWidth=0.6,
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

    s.append(Paragraph("Dona — Handoff de sesion", styles["TitleBig"]))
    s.append(Paragraph(
        "Para nueva sesion Claude Code/OpenClaw &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin acciones realizadas.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Phase 0 + T0.10 cerrados.</b> origin/main en 38dc186. main local 4 commits detras "
        "(fast-forward simple). 12 untracked documentales en raiz. Siguiente bloque grande: T1.3 "
        "(gap funcional Stripe/backend de creditos), que requiere primero verificacion operativa "
        "de la URL del webhook Stripe en Dashboard."
    ))

    # ── 1. Repo y branch actual ────────────────────────────────────────
    s.append(H1("1. Repo y branch actual"))
    repo_rows = [
        ["Item", "Valor"],
        ["Repo remoto", "https://github.com/celestinojbm/Dona-agent.git"],
        ["Ruta local", "C:\\Users\\celes\\Dona-agent"],
        ["Branch checkout actual", "pr/whapi-webhook-token-obligatorio"],
        ["Upstream de la branch actual",
         "<b>[gone]</b> — la rama remota fue borrada al mergear el PR #11 en GitHub"],
        ["HEAD local",
         "57584d4 fix(seguridad): WHAPI_WEBHOOK_TOKEN obligatorio en produccion (T0.10)"],
    ]
    s.append(small_table(para_rows(repo_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    # ── 2. git status -sb ──────────────────────────────────────────────
    s.append(H1("2. git status -sb"))
    status_block = (
        "## pr/whapi-webhook-token-obligatorio...origin/pr/whapi-webhook-token-obligatorio [gone]\n"
        "?? Diagnostico_T010_Whapi_Webhook_2026-05-01.pdf\n"
        "?? Link_PR_T010_2026-05-01.pdf\n"
        "?? Reporte_Post_Housekeeping_Dona_2026-05-01.pdf\n"
        "?? Resumen_Docs_Housekeeping_2_2026-05-01.pdf\n"
        "?? Resumen_Mini_Housekeeping_Final_2026-05-01.pdf\n"
        "?? Resumen_T010_Implementacion_2026-05-01.pdf\n"
        "?? generar_diagnostico_t010_pdf.py\n"
        "?? generar_link_pr_t010_pdf.py\n"
        "?? generar_reporte_post_housekeeping_pdf.py\n"
        "?? generar_resumen_docs_housekeeping_2_pdf.py\n"
        "?? generar_resumen_mini_housekeeping_final_pdf.py\n"
        "?? generar_resumen_t010_implementacion_pdf.py\n"
    )
    s.append(CODE(status_block))
    s.append(P("Working tree limpio respecto a tracked. 12 untracked (6 PDFs + 6 scripts), todos artefactos de planificacion."))

    # ── 3. main vs origin/main ─────────────────────────────────────────
    s.append(H1("3. Ultimo commit de main vs origin/main"))
    commits_rows = [
        ["Ref", "SHA", "Mensaje"],
        ["main local", "49978a9", "Merge pull request #10 from celestinojbm/pr/docs-housekeeping-2"],
        ["origin/main", "38dc186", "Merge pull request #11 from celestinojbm/pr/whapi-webhook-token-obligatorio"],
    ]
    s.append(small_table(para_rows(commits_rows),
                         col_widths=[3.0*cm, 2.0*cm, 12.0*cm]))
    s.append(P(
        "<b>main local esta 4 commits detras de origin/main</b> (le faltan: 57584d4, 38dc186 y los 2 commits "
        "intermedios del merge). Es fast-forward simple, no hay divergencia."
    ))

    # ── 4. PRs / branches recientes ─────────────────────────────────────
    s.append(H1("4. PRs / branches recientes"))

    s.append(H2("4.1 Ultimos 8 commits en origin/main"))
    log_block = (
        "38dc186  Merge pull request #11 from celestinojbm/pr/whapi-webhook-token-obligatorio\n"
        "57584d4  fix(seguridad): WHAPI_WEBHOOK_TOKEN obligatorio en produccion (T0.10)\n"
        "49978a9  Merge pull request #10 from celestinojbm/pr/docs-housekeeping-2\n"
        "cc96ccb  docs: organize Phase 0 audits, reports and scripts\n"
        "32da747  Merge pull request #9 from celestinojbm/pr/inbound-webhook-secret-obligatorio\n"
        "c76219d  fix(seguridad): INBOUND_WEBHOOK_SECRET obligatorio en produccion\n"
        "f79b069  Merge pull request #8 from celestinojbm/pr/meta-webhook-firma-obligatoria\n"
        "807a676  fix(seguridad): META_APP_SECRET obligatorio en produccion\n"
    )
    s.append(CODE(log_block))

    s.append(H2("4.2 PRs cerrados / mergeados (orden de merge)"))
    prs_rows = [
        ["#", "Tarea", "Merge commit"],
        ["#1", "docs-housekeeping (planning artifacts inicial)", "5d8dea1"],
        ["#2", "legacy-inventory", "c015aed"],
        ["#3", "tools-docs-firefly-higgsfield", "44706c7"],
        ["#4", "disclaimer-responsable", "5474ed2"],
        ["#5", "log-sanitization-json (Variante A)", "0834c31"],
        ["#6", "voice-forward-env (T0.5 fusionada)", "d7866eb"],
        ["#7", "stripe-webhook-firma-obligatoria (<b>T0.2</b>)", "58c806b"],
        ["#8", "meta-webhook-firma-obligatoria (<b>T0.3</b>)", "f79b069"],
        ["#9", "inbound-webhook-secret-obligatorio (<b>T0.4</b>)", "32da747"],
        ["#10", "docs-housekeeping-2", "49978a9"],
        ["#11", "whapi-webhook-token-obligatorio (<b>T0.10</b>)", "38dc186"],
    ]
    s.append(small_table(para_rows(prs_rows),
                         col_widths=[1.2*cm, 12.3*cm, 3.5*cm]))

    s.append(H2("4.3 Branches locales actuales"))
    locales_block = (
        "  main                                       (en 49978a9, behind 4)\n"
        "* pr/whapi-webhook-token-obligatorio         (en 57584d4, upstream gone, mergeada)\n"
    )
    s.append(CODE(locales_block))

    s.append(H2("4.4 Branches remotas pr/*"))
    s.append(P("<b>Ninguna.</b> GitHub borro la rama del PR #11 al mergear."))

    # ── 5. T0.10 ───────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("5. Estado de T0.10 (Whapi) — mergeado"))
    s.append(P("Confirmado en origin/main (Merge pull request #11, commit 38dc186)."))

    s.append(P("Verificacion de codigo en produccion:"))
    s.extend(bullets([
        "agent/providers/whapi.py:23 &mdash; self.webhook_token = os.getenv('WHAPI_WEBHOOK_TOKEN', '').strip()",
        "agent/providers/whapi.py:24 &mdash; self.webhook_header default 'X-Webhook-Token'",
        "agent/providers/whapi.py:28-44 &mdash; fail-fast RuntimeError si production + provider=whapi sin token",
        "agent/providers/whapi.py:48-93 &mdash; metodo _verificar_firma con hmac.compare_digest",
        "agent/providers/whapi.py:parsear_webhook &mdash; invoca _verificar_firma al inicio, retorna [] si falla",
    ]))

    s.append(P("Comportamiento operacional:"))
    s.extend(bullets([
        "<b>Hoy WHATSAPP_PROVIDER=meta</b> -> ProveedorWhapi ni se instancia -> check no se ejecuta -> cero impacto en deploy actual.",
        "Si en algun momento futuro se cambia a whapi sin setear WHAPI_WEBHOOK_TOKEN -> deploy aborta con RuntimeError claro.",
    ]))

    s.append(P(
        ".env.example post-merge documenta WHAPI_WEBHOOK_TOKEN, WHAPI_WEBHOOK_HEADER (opcional) y nota legacy "
        "sobre WHAPI_API_URL."
    ))

    # ── 6. Untracked ───────────────────────────────────────────────────
    s.append(H1("6. Untracked actuales (12 archivos)"))
    s.append(P("Todos artefactos de planificacion generados durante la sesion, ninguno critico:"))

    s.append(H3("PDFs (6):"))
    pdfs_block = (
        "Diagnostico_T010_Whapi_Webhook_2026-05-01.pdf\n"
        "Link_PR_T010_2026-05-01.pdf\n"
        "Reporte_Post_Housekeeping_Dona_2026-05-01.pdf\n"
        "Resumen_Docs_Housekeeping_2_2026-05-01.pdf\n"
        "Resumen_Mini_Housekeeping_Final_2026-05-01.pdf\n"
        "Resumen_T010_Implementacion_2026-05-01.pdf\n"
    )
    s.append(CODE(pdfs_block))

    s.append(H3("Scripts generadores (6):"))
    scripts_block = (
        "generar_diagnostico_t010_pdf.py\n"
        "generar_link_pr_t010_pdf.py\n"
        "generar_reporte_post_housekeeping_pdf.py\n"
        "generar_resumen_docs_housekeeping_2_pdf.py\n"
        "generar_resumen_mini_housekeeping_final_pdf.py\n"
        "generar_resumen_t010_implementacion_pdf.py\n"
    )
    s.append(CODE(scripts_block))
    s.append(P("Pueden vivir untracked o ir a pr/docs-housekeeping-3 (docs/auditorias/ + docs/scripts/) cuando se decida."))

    # ── 7. Pendientes ──────────────────────────────────────────────────
    s.append(H1("7. Pendientes inmediatos"))
    pend_rows = [
        ["#", "Pendiente", "Tipo", "Riesgo"],
        ["1",
         "<b>Mini-housekeeping post-PR #11</b>: git checkout main &amp;&amp; git pull --ff-only origin main + git branch -D pr/whapi-webhook-token-obligatorio (con -D porque su upstream ya no existe) + opcional git fetch origin --prune",
         "Operativo", "Cero"],
        ["2",
         "<b>Verificar deploy Render post-merge T0.10</b>: confirmar que el redeploy automatico tras 38dc186 completo sin errores (provider activo sigue siendo Meta, deberia pasar limpio)",
         "Operativo", "Bajo"],
        ["3",
         "<b>Verificacion operativa Stripe Dashboard</b> (Bloque 1 del Diagnostico T0.2 corregido): URL del webhook, 'Webhook attempts' recientes, verificar welcome WhatsApp post-pago",
         "Sin codigo", "Cero"],
        ["4",
         "<b>pr/docs-housekeeping-3</b>: mover los 12 untracked actuales a docs/auditorias/ y docs/scripts/",
         "PR pequeno", "Cero"],
        ["5",
         "<b>Borrar WHAPI_API_URL de Render</b> (vestigio sin uso en codigo, ya documentado en .env.example)",
         "Operativo", "Cero"],
        ["6",
         "<b>T1.3 &mdash; Gap funcional Stripe/backend de creditos</b>",
         "PR mediano", "Medio"],
    ]
    s.append(small_table(para_rows(pend_rows),
                         col_widths=[0.7*cm, 11.3*cm, 2.5*cm, 1.5*cm]))

    # ── 8. Riesgos y advertencias ─────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("8. Riesgos y advertencias"))

    s.append(H2("8.1 Criticos para una nueva sesion"))
    s.extend(bullets([
        "<b>No cambiar WHATSAPP_PROVIDER=meta sin setear WHAPI_WEBHOOK_TOKEN en Render.</b> Si alguien rota a whapi sin token, el deploy aborta con RuntimeError. Para activar Whapi: primero setear WHAPI_WEBHOOK_TOKEN en Render + configurar custom header en panel Whapi (PATCH /settings, headers: {'X-Webhook-Token': '&lt;mismo valor&gt;'}), despues cambiar WHATSAPP_PROVIDER.",
        "<b>Gap funcional Stripe/backend abierto</b>: el cliente paga $20/$40 de suscripcion pero el backend Dona no acredita creditos. Identificado en Diagnostico T0.2 corregido. T1.3 lo cierra. <b>No empezar Phase 1 (T1.1+) antes de cerrar T1.3.</b>",
        "<b>main local desactualizado</b> (4 commits behind). Cualquier commit nuevo antes de sync genera divergencia. Sincronizar primero siempre.",
    ]))

    s.append(H2("8.2 Operacionales (no urgentes)"))
    s.extend(bullets([
        "<b>enhanced/ NO es legacy AgentKit</b> &mdash; es codigo VIVO con 19 imports activos. Documentado en docs/legacy-inventory.md. No tocar sin re-leer ese inventario.",
        "<b>landing/AGENTS.md</b> advierte que esta version de Next.js puede tener breaking changes; consultar node_modules/next/dist/docs/ antes de tocar APIs de Next en landing/.",
        "<b>gh CLI no esta instalado</b> en este entorno; PRs se crean via URL prearmada con ?title=...&amp;body=...&amp;quick_pull=1.",
        "<b>Stripe webhook URL en Dashboard</b> posiblemente apunta a /api/stripe/webhook (ruta que no existe en el repo); URL real existente es /api/webhook. Verificacion operativa pendiente.",
    ]))

    s.append(H2("8.3 Reglas obligatorias del usuario (siempre vigentes)"))
    s.extend(bullets([
        "Modo solo lectura por default; cualquier accion destructiva (commit, push, merge, deploy, borrar archivos) requiere autorizacion explicita por turno.",
        "Nunca mostrar valores reales de secretos ni env vars.",
        "Nunca hacer push a main ni merge automatico.",
        "PRs siempre en branch nueva, nunca commit directo a main.",
        "Confirmacion previa del owner para mergear cualquier PR.",
        "Span de actuacion de cada autorizacion es estricto: una autorizacion para una operacion no autoriza otras.",
    ]))

    # ── 9. Contexto para nueva sesion ─────────────────────────────────
    s.append(H1("9. Contexto para una nueva sesion Claude Code"))

    s.append(H2("9.1 Archivos clave a leer al arrancar (en este orden)"))
    archivos_rows = [
        ["Archivo", "Por que"],
        ["CLAUDE.md", "Identidad del proyecto, convenciones, no hacer/si hacer"],
        ["docs/planes/Plan_Dona_v2_1_2026-04-30.pdf",
         "Plan vigente con backlog priorizado, 18 capas, Tool Intelligence Layer"],
        ["docs/legacy-inventory.md",
         "Inventario critico &mdash; confirma que enhanced/ es VIVO, no legacy"],
        ["docs/tools/README.md, matriz.md, adobe-firefly.md, higgsfield.md",
         "Tool Intelligence Layer &mdash; proceso de evaluacion de herramientas externas"],
        ["docs/auditorias/Reporte_Post_Phase0_Dona_2026-05-01.pdf",
         "Snapshot post-Phase 0"],
        ["landing/AGENTS.md", "Procedural para edits en landing"],
        ["agent/billing.py, agent/providers/meta.py, agent/providers/whapi.py, agent/inbound_tokens.py",
         "Implementacion de los 4 fail-fast checks de Phase 0 + T0.10"],
        ["tests/test_billing.py, tests/test_providers.py, tests/test_inbound_tokens.py",
         "Patron de tests con monkeypatch.setenv('ENVIRONMENT', 'production') + importlib.reload para checks de prod"],
    ]
    s.append(small_table(para_rows(archivos_rows),
                         col_widths=[6.5*cm, 10.5*cm]))

    s.append(H2("9.2 Estado de produccion (a fecha 2026-05-01)"))
    s.extend(bullets([
        "<b>Render web service</b>: deploy verde post-merge T0.10. Provider WHATSAPP_PROVIDER=meta. Las 3 env vars criticas (STRIPE_WEBHOOK_SECRET, META_APP_SECRET, INBOUND_WEBHOOK_SECRET) estan seteadas en Render. WHAPI_TOKEN tambien esta (legacy util para transcriber.py). WHAPI_API_URL legacy puede borrarse.",
        "<b>WhatsApp/Meta</b>: HMAC obligatoria, replay protection con ventana 600s, mensajes funcionando.",
        "<b>Landing usadona.com</b>: carga; disclaimer responsable mergeado; <b>PR4 falta verificar</b> que el welcome WhatsApp post-pago se entrega correctamente (Stripe webhook URL en Dashboard puede apuntar a 404).",
    ]))

    s.append(H2("9.3 Patron estandar de PRs (lo que se viene haciendo)"))
    s.extend(bullets([
        "Diagnostico solo lectura -> PDF entregado al owner.",
        "Owner autoriza con reglas estrictas.",
        "Branch nueva pr/&lt;slug&gt; desde main sincronizado.",
        "Cambios minimos, archivos autorizados solamente.",
        "pytest -q localmente, todos verde.",
        "Commit con mensaje en espanol/ingles segun convencion del modulo.",
        "Push de la branch (nunca a main).",
        "Resumen + link prearmado de 'Create PR' -> owner crea el PR.",
        "Owner mergea en GitHub UI (no merge automatico desde Claude).",
        "Mini-housekeeping post-merge: sync main + borrar branch.",
        "PDF de resumen + link de descarga local (file:///...) entregado al owner.",
    ]))

    s.append(H2("9.4 Decisiones tentativas confirmadas (no re-discutir)"))
    s.extend(bullets([
        "Workspace como nombre raiz (T1.1+).",
        "Resend como SMTP inicial (T1.3+).",
        "Stripe = backend Python como unica fuente de verdad (T1.3).",
        "Modelo: suscripcion mensual con creditos incluidos + top-ups.",
        "TCPA: negocio responsable, Dona proveedor con guardrails.",
        "Google scopes: consentimiento progresivo.",
        "Posicionamiento publico: 'acelerador autonomo premium para negocios'. Nunca 'AGI' externo.",
    ]))

    s.append(H2("9.5 Decisiones pendientes (bloquean Phase 1)"))
    s.extend(bullets([
        "Matriz exacta plan &harr; creditos &harr; tools (T1.5).",
        "Wording final del nuevo system prompt 'lider de operaciones' (T1.8).",
        "Sandbox Meta Ads / Google Ads para T3.6.",
        "Knowledge base del sub-agente publico: pgvector vs externo (T2.4 / T3.4).",
    ]))

    s.append(H2("9.6 Como continuar limpio (primera accion de la nueva sesion)"))
    cmd_block = (
        "git checkout main\n"
        "git pull --ff-only origin main          # main pasa a 38dc186\n"
        "git branch -D pr/whapi-webhook-token-obligatorio   # mergeada, upstream gone\n"
        "git fetch origin --prune\n"
        "git status -sb                          # ## main...origin/main + 12 untracked\n"
    )
    s.append(CODE(cmd_block))
    s.append(P(
        "Despues: decidir si hacer pr/docs-housekeeping-3 (mover 12 untracked) antes de empezar el "
        "siguiente bloque grande (T1.3)."
    ))

    # ── 10. Resumen ejecutivo ──────────────────────────────────────────
    s.append(H1("10. Resumen ejecutivo de una linea"))
    s.append(P(
        "Repo en 38dc186 con Phase 0 + T0.10 cerrados; main local 4 commits detras; branch local de "
        "T0.10 con upstream gone lista para borrar; 12 untracked documentales acumulados; siguiente "
        "bloque grande es T1.3 (gap funcional Stripe/backend de creditos), que requiere primero "
        "verificacion operativa de la URL del webhook Stripe en Dashboard."
    ))

    s.append(Spacer(1, 14))
    s.append(C("Sin acciones realizadas. Handoff completo."))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Handoff de sesion",
        author="Handoff generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Handoff de sesion · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
