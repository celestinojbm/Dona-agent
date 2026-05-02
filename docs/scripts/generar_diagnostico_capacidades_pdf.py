"""
Genera Diagnostico_Capacidades_Sesion_2026-05-01.pdf con el diagnostico
de herramientas/conectores/CLIs disponibles en esta sesion Claude Code.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Diagnostico_Capacidades_Sesion_2026-05-01.pdf"

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

    s.append(Paragraph("Dona — Capacidades de la sesion Claude Code", styles["TitleBig"]))
    s.append(Paragraph(
        "Diagnostico de herramientas / conectores / CLIs &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin acciones realizadas.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Modelo de operacion efectivo:</b> par de manos para edicion local + git + tests + "
        "generacion de PDFs. Cualquier interaccion con servicios externos (Render, Stripe Dashboard, "
        "Whapi panel, GitHub UI para mergear) la hace el owner. Yo preparo, propongo, valido localmente "
        "y empujo branches. <b>Sin gh / stripe / render / supabase CLIs</b>; <b>vercel</b> instalado pero "
        "sin autenticar en sesion."
    ))

    # ── 1. MCP servers ─────────────────────────────────────────────────
    s.append(H1("1. MCP servers visibles en esta sesion"))
    mcp_rows = [
        ["MCP server", "Estado", "Notas"],
        ["claude_ai_Google_Drive",
         "<b>Disponible pero no autenticado</b>",
         "Aparece en deferred tools (mcp__claude_ai_Google_Drive__authenticate, mcp__claude_ai_Google_Drive__complete_authentication). Para usarlo habria que cargar las herramientas con ToolSearch y luego correr el flujo de autenticacion. No lo he activado en esta sesion."],
        ["Otros MCP servers",
         "<b>Ninguno</b>",
         "No veo conectores de Adobe Creative Cloud, Higgsfield, Stripe, GitHub, Notion, Linear, Slack, etc. en el listado de deferred tools de mi sesion."],
    ]
    s.append(small_table(para_rows(mcp_rows),
                         col_widths=[4.5*cm, 4.0*cm, 8.5*cm]))
    s.append(P(
        "<b>Implicacion practica:</b> los conectores de claude.ai (Adobe, Higgsfield, Stripe, etc. "
        "mencionados en T0.10) son del lado del cliente del owner, no de esta sesion Claude Code. "
        "Cualquier integracion tecnica con esos servicios desde Dona requiere su REST API directa, "
        "no MCP."
    ))

    # ── 2. Herramientas integradas ─────────────────────────────────────
    s.append(H1("2. Herramientas integradas activas"))

    s.append(H2("2.1 File / shell (cargadas por default)"))
    s.extend(bullets([
        "<b>Read, Write, Edit</b> &mdash; leer/escribir/editar archivos locales.",
        "<b>Glob, Grep</b> &mdash; busqueda por patron y contenido (ripgrep).",
        "<b>Bash</b> &mdash; shell Unix (Git Bash / MinGW). Es la que vengo usando.",
        "<b>PowerShell</b> &mdash; Windows PowerShell 5.1, disponible.",
        "<b>ToolSearch</b> &mdash; para cargar deferred tools por demanda.",
        "<b>ScheduleWakeup</b> &mdash; para self-pacing en /loop dynamic mode.",
        "<b>Skill</b> &mdash; invocador de skills (slash commands).",
    ]))

    s.append(H2("2.2 Skills disponibles (via Skill)"))
    s.append(P("Muchas, las relevantes:"))
    s.extend(bullets([
        "update-config &mdash; config de Claude Code (settings.json, hooks, permisos).",
        "keybindings-help &mdash; atajos de teclado.",
        "simplify &mdash; review de codigo cambiado.",
        "fewer-permission-prompts &mdash; autoallowlist de comandos read-only.",
        "loop, schedule &mdash; para tareas recurrentes / agendar agentes.",
        "claude-api &mdash; construir/debuggear apps Anthropic SDK.",
        "ads (+ familia ads-*) &mdash; auditorias de Google/Meta/LinkedIn/TikTok/Microsoft Ads, Apple Search Ads, etc.",
        "ui-ux-pro-max &mdash; diseno UI/UX, integraciones shadcn/ui MCP.",
        "last-30-days &mdash; research multi-fuente ultimos 30 dias.",
        "init, review, security-review &mdash; comandos comunes Claude Code.",
        "build-agent &mdash; referencia al CLAUDE.md (legacy de la era AgentKit).",
    ]))

    s.append(H2("2.3 Subagentes (via Agent)"))
    s.extend(bullets([
        "general-purpose, Explore, Plan &mdash; proposito general / busqueda / planeacion.",
        "audit-budget, audit-compliance, audit-creative, audit-google, audit-meta, audit-tracking &mdash; auditorias paid ads especializadas.",
        "claude-code-guide, copy-writer, creative-strategist, format-adapter, statusline-setup, visual-designer &mdash; flujos creativos paid ads.",
    ]))

    s.append(H2("2.4 Deferred (cargables on-demand via ToolSearch)"))
    s.append(P(
        "He cargado en esta sesion: <b>WebSearch</b>, <b>WebFetch</b>. Otros deferred sin cargar: "
        "AskUserQuestion, CronCreate/Delete/List, EnterPlanMode, EnterWorktree, Monitor, NotebookEdit, "
        "PushNotification, RemoteTrigger, TaskCreate/Get/List/Output/Stop/Update, los dos de "
        "mcp__claude_ai_Google_Drive__*."
    ))

    # ── 3. CLIs disponibles ────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("3. CLIs disponibles relevantes"))

    s.append(H2("3.1 Resultado del survey"))
    cli_rows = [
        ["CLI", "Estado", "Version / ubicacion"],
        ["gh (GitHub CLI)", "<b>No instalado</b>",
         "requeriria instalar (regla 'no instalar dependencias' lo bloquea)"],
        ["render (Render CLI)", "<b>No instalado</b>", "—"],
        ["stripe (Stripe CLI)", "<b>No instalado</b>", "—"],
        ["vercel (Vercel CLI)", "<b>Disponible</b>",
         "Vercel CLI 50.42.0 en ~/AppData/Roaming/npm/vercel"],
        ["supabase (Supabase CLI)", "<b>No instalado</b>", "—"],
        ["docker", "<b>No instalado</b>", "—"],
        ["git", "<b>Disponible</b>", "2.53.0.windows.2"],
        ["python / python3", "<b>Disponible</b>", "3.12.10"],
        ["node / npm", "<b>Disponible</b>", "node 24.14.0, npm 11.9.0"],
        ["pytest", "<b>Disponible</b>", "usado durante toda la sesion"],
        ["alembic", "<b>Disponible</b>", "listo para T4.3 cuando llegue"],
        ["curl", "<b>Disponible</b>", "8.18.0"],
        ["jq", "<b>No instalado</b>", "—"],
    ]
    s.append(small_table(para_rows(cli_rows),
                         col_widths=[4.5*cm, 3.5*cm, 9.0*cm]))

    s.append(H2("3.2 Lectura practica"))
    s.extend(bullets([
        "<b>gh ausente</b> -> PRs se crean con URL prearmada (?title=...&amp;body=...&amp;quick_pull=1), no programaticamente.",
        "<b>stripe ausente</b> -> no puedo invocar Stripe CLI para verificar webhooks. Cualquier verificacion de Stripe Dashboard es manual del owner.",
        "<b>render y supabase ausentes</b> -> no puedo gestionar deploys ni env vars desde CLI. Todo cambio en Render lo hace el owner por dashboard.",
        "<b>vercel presente pero sin autenticar en esta sesion</b> -> tecnicamente podria correr vercel env ls o vercel deploy si autoriza, pero no hay token activo y no ejecutaria sin autorizacion explicita por turno.",
        "<b>docker ausente</b> -> no puedo correr docker-compose up localmente. La verificacion del Dockerfile requiere otro entorno o desde Render.",
        "<b>jq ausente</b> -> manipulo JSON con Python en lugar de jq cuando hace falta.",
    ]))

    # ── 4. Acceso al repo ──────────────────────────────────────────────
    s.append(H1("4. Acceso al repo actual"))
    repo_rows = [
        ["Aspecto", "Estado"],
        ["Working tree local", "C:\\Users\\celes\\Dona-agent ✓"],
        ["Remoto configurado", "https://github.com/celestinojbm/Dona-agent.git ✓"],
        ["Branch actual", "pr/whapi-webhook-token-obligatorio (HEAD 57584d4)"],
        ["git fetch", "Funciona ✓"],
        ["git push",
         "Funciona (verificado en sesion: 11 PRs pushados con exito) ✓"],
        ["git pull --ff-only", "Funciona ✓"],
        ["Crear ramas / commits", "Funciona ✓ con autorizacion del owner"],
        ["Crear PRs en GitHub", "<b>Solo manual</b> (sin gh); ofrezco URL prearmada"],
        ["Mergear PRs", "<b>Solo manual</b> desde GitHub UI"],
        ["Ejecutar tests", "pytest -q corre limpio (468 tests post-T0.10) ✓"],
    ]
    s.append(small_table(para_rows(repo_rows),
                         col_widths=[5.5*cm, 11.5*cm]))
    s.append(P(
        "Las credenciales de GitHub estan en git config del usuario; no las veo, pero git push esta "
        "funcionando sin pedirme login en esta sesion."
    ))

    # ── 5. Limitaciones vs Claude Web ──────────────────────────────────
    s.append(PageBreak())
    s.append(H1("5. Limitaciones frente a Claude Web (claude.ai)"))
    web_rows = [
        ["Capacidad", "Claude Web (claude.ai)", "Esta sesion Claude Code"],
        ["Conectores MCP custom (Adobe, Higgsfield, Notion, Linear)",
         "Configurables via Settings -> Connectors",
         "<b>Solo Google Drive deferred</b> (no autenticado)"],
        ["APIs externas autenticadas (Stripe, GitHub, Slack)",
         "Via conectores",
         "<b>Solo via REST con curl/Python</b> si tengo credentials del owner"],
        ["Gemini deep search / Sora / Adobe AI Assistant",
         "Disponibles si owner los conecta",
         "<b>No</b>"],
        ["Busqueda web", "Si",
         "<b>Si</b> (cargue WebSearch y WebFetch en esta sesion)"],
        ["Editar archivos locales", "No (sandbox)",
         "<b>Si</b> (Read, Write, Edit directos en disco del owner)"],
        ["Correr codigo (pytest, npm, etc.)", "No",
         "<b>Si</b> (Bash + PowerShell + Python)"],
        ["Git operations (push/pull/branch/commit)", "No", "<b>Si</b>"],
        ["Generar PDFs locales", "No", "<b>Si</b> (reportlab + Bash)"],
        ["Spawn de subagentes especializados", "Limitado",
         "<b>Si</b> via Agent"],
        ["Skills (slash commands)", "Si (configurables)",
         "<b>~20 skills cargadas</b>, varias especializadas en ads"],
        ["Tareas recurrentes / agendadas", "Limitado",
         "<b>Si</b> via skill schedule o CronCreate deferred"],
        ["Windowing / IDE integration", "Limitado",
         "<b>Si</b> esta sesion es CLI directa con Git Bash"],
    ]
    s.append(small_table(para_rows(web_rows),
                         col_widths=[5.0*cm, 5.5*cm, 6.5*cm]))

    s.append(H2("5.1 Diferencias clave para Dona"))
    diff_rows = [
        ["Caso", "Lado donde se hace"],
        ["Diagnostico Adobe Firefly / Higgsfield (T0.10)",
         "Yo investigue con WebFetch contra docs publicas, sin conectores. La integracion tecnica para Dona <b>no usa</b> los connectors de claude.ai &mdash; usa REST APIs de cada proveedor."],
        ["Verificar webhook Stripe Dashboard",
         "Manual del owner (yo no tengo stripe CLI ni Stripe MCP)."],
        ["Verificar deploy Render",
         "Manual del owner (yo no tengo render CLI ni Render MCP)."],
        ["Configurar Whapi panel (PATCH /settings)",
         "Manual del owner. Yo solo armo el shape del request."],
        ["Modificar env vars en Render / Vercel",
         "Manual del owner. Yo solo edito .env.example documental."],
        ["Autorizar / aprobar / mergear PRs",
         "Manual del owner en GitHub UI."],
    ]
    s.append(small_table(para_rows(diff_rows),
                         col_widths=[5.5*cm, 11.5*cm]))

    # ── 6. Resumen ejecutivo ──────────────────────────────────────────
    s.append(H1("6. Resumen ejecutivo"))
    resumen_rows = [
        ["Capacidad", "Estado"],
        ["<b>Lectura/escritura local</b>",
         "Total. Repo, archivos, tests, generacion de PDFs."],
        ["<b>Git operations</b>",
         "Total (push/pull/branch/commit con autorizacion)."],
        ["<b>Crear PRs en GitHub</b>",
         "Solo manual con URL prearmada (gh ausente)."],
        ["<b>MCP connectors</b>",
         "Solo claude_ai_Google_Drive deferred (no autenticado). Sin Adobe/Higgsfield/Stripe/Render/Slack/etc."],
        ["<b>CLIs de plataforma</b>",
         "Solo vercel (sin autenticar en sesion) entre las cinco solicitadas (gh/render/stripe/vercel/supabase)."],
        ["<b>Busqueda web / fetch</b>",
         "Si (WebSearch, WebFetch cargadas)."],
        ["<b>Subagentes especializados</b>",
         "Si, varios para auditorias paid ads y exploracion."],
        ["<b>Verificaciones contra produccion</b>",
         "Indirectas: ver codigo en origin/main, ver logs documentados; nunca hablo con Render/Vercel/Stripe directo."],
    ]
    s.append(small_table(para_rows(resumen_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(Spacer(1, 14))
    s.append(P(
        "<b>Modelo de operacion efectivo:</b> soy un par de manos para edicion local + git + tests + "
        "generacion de PDFs. Cualquier interaccion con servicios externos (Render, Stripe Dashboard, "
        "Whapi panel, GitHub UI para mergear) la hace el owner. Yo preparo, propongo, valido localmente "
        "y empujo branches."
    ))

    s.append(Spacer(1, 8))
    s.append(C("Sin acciones realizadas. Solo diagnostico."))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Capacidades de la sesion",
        author="Diagnostico generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Capacidades de la sesion · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
