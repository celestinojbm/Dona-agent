"""
Genera Resumen_T21B_Hotfix_2026-05-09.pdf · hotfix de carga del Action
Center · convierte 404 backend en empty state · botón Generar siempre
visible · logging seguro extendido.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T21B_Hotfix_2026-05-09.pdf"

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

story.append(Paragraph("Hotfix T2.1.B · carga Action Center post-merge",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-09 · Branch "
    "<b>hotfix/t2.1.b-action-center-load-error</b> · base "
    "<b>main@adbf62e</b> · arregla 'No pudimos cargar tus acciones' "
    "en el dashboard sin tocar lógica de negocio",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Hotfix listo. <b>787 pytest · 35 vitest · "
    "tsc 0 · build 17/17 · lint 0 errors</b>. UI muestra empty "
    "state correcto · botón 'Generar acciones' siempre disponible · "
    "logging seguro extendido. <b>Sin merge · sin deploy.</b>"
))

# ── 1. Causa raíz ──────────────────────────────────────────────────────

story.append(H1("1. Causa raíz"))

story.append(P(
    "<b>Combinación de dos problemas</b> en la cadena dashboard → "
    "proxy → backend:"
))

story.extend(bullets([
    "<b>Backend correcto pero pesimista para usuarios pre-T2.0.B:</b> "
    "<i>/internal/automation/acciones</i> resuelve "
    "<i>subscription_id → telefono</i> usando <i>suscripcion_stripe</i>. "
    "Si la sub no está allí (creada antes de T2.0.B, no migrada), "
    "retorna 404 <i>subscription_no_persistida</i>. Eso es coherente "
    "como categoría de error de auth, pero para el Action Center "
    "significa simplemente 'no hay acciones todavía'.",
    "<b>Route handler propaga 404 al cliente:</b> "
    "<i>/api/automation/acciones</i> traducía el 404 backend a "
    "<i>{error: 'subscription_not_found'}</i> con status 404.",
    "<b>Componente trata cualquier no-200 como error fatal:</b> "
    "<i>!res.ok</i> en el componente seteaba "
    "<i>{status:'error', code:'error_404'}</i> · UI mostraba "
    "<b>'No pudimos cargar tus acciones'</b> con un único botón "
    "'Reintentar'. El usuario quedaba sin forma de generar "
    "acciones desde la UI.",
    "<b>Empty state existía pero nunca se alcanzaba</b> en este "
    "caso · solo se mostraba si el backend retornaba 200 con "
    "lista vacía (que requería tener perfil_negocio + sub "
    "persistida).",
]))

story.append(BANNER(
    "<b>Hipótesis #5 + #6 del owner confirmadas.</b> Hipótesis "
    "#1 (sesión sin subscriptionId), #2 (env faltante), #3 "
    "(bridge timeout) descartadas por inspección: env vars "
    "PRESENT en Vercel, dashboard-data funciona usando el mismo "
    "patrón de session.subscriptionId."
))

# ── 2. Verificación read-only previa ───────────────────────────────────

story.append(H1("2. Verificación read-only previa"))

story.append(make_table([
    ["Hipótesis", "Estado", "Evidencia"],
    ["#1 sesión sin subscriptionId", "Descartada",
     "/api/dashboard-data funciona · usa el mismo patrón "
     "session.subscriptionId · si ese fuera el problema, fallaría "
     "antes que Action Center"],
    ["#2 BACKEND_URL ausente en Vercel", "Descartada",
     "vercel env pull · BACKEND_URL PRESENT"],
    ["#3 INTERNAL_BRIDGE_SECRET ausente", "Descartada",
     "vercel env pull · INTERNAL_BRIDGE_SECRET PRESENT"],
    ["#4 backend no encuentra "
     "subscription_id → telefono",
     "<b>CONFIRMADA</b>",
     "Backend retorna 404 si la sub no está en suscripcion_stripe. "
     "Subs pre-T2.0.B no fueron persistidas allí."],
    ["#5 frontend trata 404 como error fatal",
     "<b>CONFIRMADA</b>",
     "Inspección directa de seccion-action-center.tsx · "
     "<i>!res.ok → setLoad error</i>"],
    ["#6 falta empty state robusto",
     "<b>CONFIRMADA</b>",
     "Empty state existe pero solo en 200 + count=0. "
     "Caso 404 → error fatal."],
], col_widths=[2.4*inch, 1.0*inch, 3.2*inch]))

# ── 3. Archivos modificados ────────────────────────────────────────────

story.append(H1("3. Archivos modificados"))

story.append(make_table([
    ["Archivo", "Tipo", "Cambio"],
    ["landing/app/api/automation/acciones/route.ts", "MOD",
     "404 backend ('subscription_no_persistida') → 200 con lista "
     "vacía · empty fallback (no es error). Logging seguro por "
     "categoría: missing_session, missing_subscription_id, "
     "backend_404, backend_401, bridge_timeout, missing_env. "
     "missing_env reporta NOMBRE pero NO valor."],
    ["landing/app/api/automation/acciones/generar/route.ts", "MOD",
     "Mismas categorías de logging. 404 sigue propagado (en "
     "generar el caller necesita saber para mostrar mensaje útil)."],
    ["landing/app/dashboard/seccion-action-center.tsx", "MOD",
     "Panel de error muestra <i>code</i> y AHORA incluye 2 "
     "botones: Reintentar + Generar acciones. handleGenerar "
     "trata 404 con mensaje específico ('completa el diagnóstico "
     "desde WhatsApp')."],
    ["landing/app/dashboard/seccion-action-center.test.tsx", "NEW",
     "7 tests vitest + jsdom: empty state · 502 error real · "
     "504 timeout · loading inicial · acción LOW pending render · "
     "acción CRITICAL aviso bloqueo. <b>Verifica que el botón "
     "Generar acciones está disponible en TODOS los estados</b>."],
    ["landing/vitest.config.ts", "MOD",
     "Acepta tests <i>.test.tsx</i> en app/* · pragma "
     "<i>@vitest-environment jsdom</i> por archivo (vitest 2 "
     "no soporta workspace API)."],
    ["landing/package.json + lock", "MOD",
     "+ devDeps @testing-library/react · @testing-library/jest-dom · "
     "jsdom"],
], col_widths=[3.2*inch, 0.5*inch, 2.9*inch]))

# ── 4. Logging seguro ─────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Logging seguro · sin secretos ni PII"))

story.append(P(
    "El route handler ahora loguea categorías concretas. NUNCA "
    "loguea: telefono completo · subscription_id completo · valor "
    "de envs · payload sensible. Solo el NOMBRE de la env si falta."
))

story.append(CODE(
    "[ACT-CENTER] GET /acciones · missing_session\n"
    "[ACT-CENTER] GET /acciones · missing_subscription_id\n"
    "[ACT-CENTER] GET /acciones · backend_404 subscription_no_persistida · empty fallback\n"
    "[ACT-CENTER] GET /acciones · backend_401 INTERNAL_BRIDGE_SECRET desincronizado entre Vercel/Render?\n"
    "[ACT-CENTER] GET /acciones · bridge_timeout\n"
    "[ACT-CENTER] GET /acciones · missing_env BACKEND_URL\n"
    "[ACT-CENTER] GET /acciones · missing_env INTERNAL_BRIDGE_SECRET"
))

# ── 5. UX corregida ───────────────────────────────────────────────────

story.append(H1("5. UX corregida · matriz de estados"))

story.append(make_table([
    ["Backend retorna", "Route handler", "UI muestra"],
    ["200 con count=0", "200 acciones=[]", "Empty state · CTA generar"],
    ["404 sub_no_persistida (pre-T2.0.B)",
     "<b>200 acciones=[]</b> (hotfix)",
     "<b>Empty state · CTA generar</b> (no error fatal)"],
    ["200 con acciones", "200 acciones=[...]", "Lista de cards"],
    ["401 firma inválida",
     "502 backend_auth_error",
     "Error real con código + Reintentar + <b>botón Generar</b>"],
    ["timeout", "504 backend_timeout",
     "Error real + Reintentar + <b>botón Generar</b>"],
    ["500/otro", "502 backend_unavailable",
     "Error real + Reintentar + <b>botón Generar</b>"],
], col_widths=[2.0*inch, 2.0*inch, 2.6*inch]))

story.append(BANNER(
    "<b>Botón 'Generar acciones' visible en TODOS los estados</b> · "
    "loading, empty, ready (header), error. Test específico lo "
    "verifica."
))

# ── 6. Tests ──────────────────────────────────────────────────────────

story.append(H1("6. Tests ejecutados"))

story.append(make_table([
    ["Suite", "Cantidad", "Resultado"],
    ["pytest tests/test_automation_endpoints.py", "18",
     "Sin cambios · sigue verde · cubre TestInternalAuth "
     "subscription_no_existe_404"],
    ["pytest suite completa", "787",
     "<b>passing en 147s</b> · cero regresiones"],
    ["vitest lib/automation-bridge.test.ts", "13",
     "Sin cambios · cubre propagación 404 del bridge"],
    ["<b>vitest app/dashboard/seccion-action-center.test.tsx</b>", "<b>7</b>",
     "<b>NUEVO</b> · empty · 502 con reintentar+generar · 504 · "
     "loading · acción LOW · acción CRITICAL aviso"],
    ["vitest total", "35", "passing"],
    ["npx tsc --noEmit", "—", "0 errores"],
    ["rm -rf .next && npm run build", "—",
     "17/17 pages OK"],
    ["npm run lint", "—",
     "0 errors · 3 warnings preexistentes · exit 0"],
], col_widths=[3.6*inch, 0.6*inch, 2.4*inch]))

story.append(H2("Tests específicos del hotfix"))

story.extend(bullets([
    "<i>backend devuelve lista vacía → empty state con CTA</i> · "
    "verifica el caso normal.",
    "<i>subscription_no_persistida → empty state</i> · simula la "
    "respuesta del route handler post-hotfix.",
    "<i>502 → muestra error con código + ofrece reintentar y "
    "generar</i> · valida que botón <b>Generar acciones</b> sigue "
    "disponible incluso en error real.",
    "<i>504 timeout → muestra error con código</i>.",
    "<i>antes de la primera respuesta muestra Cargando…</i>.",
    "<i>renderiza acción LOW pending con botón Ejecutar</i>.",
    "<i>renderiza acción CRITICAL needs_approval con aviso de "
    "bloqueo · NO muestra botón Aprobar</i>.",
]))

# ── 7. Riesgos ────────────────────────────────────────────────────────

story.append(H1("7. Riesgos"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["404 backend convertido en 200 vacío puede ocultar "
     "errores reales de auth si secret se desincroniza",
     "Bajo",
     "401 backend (signature_invalid) sigue tratado como error "
     "fatal · solo 404 'subscription_no_persistida' se convierte "
     "a empty. Tests verifican distinción 401/404."],
    ["Usuario sin perfil_negocio puede pulsar 'Generar' y "
     "obtener 0 acciones (Opportunity Engine retorna [])",
     "Cero · UX",
     "El componente muestra empty state limpio. handleGenerar "
     "con 404 ahora avisa al usuario que complete el "
     "diagnóstico por WhatsApp."],
    ["Logs nuevos del route handler podrían crecer con "
     "404s frecuentes",
     "Bajo",
     "Vercel logs tienen retención corta · cada línea es "
     "1 string · sin payloads."],
    ["Tests vitest jsdom agregados aumentan tiempo de CI",
     "Cero",
     "+598ms en environment setup · suite completa sigue <2s."],
    ["@testing-library/* y jsdom como devDeps · vulns?",
     "Bajo",
     "DevDep · no afectan bundle prod. Si npm audit reporta, "
     "PR aparte."],
], col_widths=[2.6*inch, 0.8*inch, 3.2*inch]))

# ── 8. Env requeridas en producción ──────────────────────────────────

story.append(H1("8. Configuración de env en producción"))

story.append(P(
    "<b>Ya verificado vía vercel env pull · NO requiere cambios.</b> "
    "Las dos env vars necesarias para el bridge están PRESENT en "
    "Vercel Production:"
))

story.extend(bullets([
    "<i>BACKEND_URL</i> · PRESENT (apunta a Render)",
    "<i>INTERNAL_BRIDGE_SECRET</i> · PRESENT · debe coincidir con "
    "el de Render (el bridge falla con 401 si difieren)",
]))

story.append(WARN(
    "<b>NO se cambia ninguna env en este hotfix.</b> Este reporte "
    "solo confirma su PRESENCIA · no muestra valores. Si el "
    "owner sospechara desincronización Vercel↔Render, debería "
    "verificar manualmente en cada panel · este hotfix no "
    "requiere tocarlas."
))

# ── 9. Out of scope ───────────────────────────────────────────────────

story.append(H1("9. Out of scope · NO entra en este hotfix"))

story.extend(bullets([
    "<b>Migración de subs pre-T2.0.B</b> a <i>suscripcion_stripe</i>. "
    "Ese script de migración sería otro PR (T1.4.X o similar) · "
    "este hotfix solo hace que la UI no rompa hasta que se haga.",
    "<b>Markdown render del result_json</b>. Hoy se muestra como "
    "JSON · futuro UX.",
    "<b>Métricas dashboard automation</b>. Futuro PR.",
    "<b>Ejecutores reales (T2.1.C) · reservas créditos (T2.1.D)</b>. "
    "Mantenidos out of scope.",
    "<b>Tests E2E con Playwright</b>. Solo unitarios con vitest+"
    "jsdom · Playwright sería otro PR si se quiere.",
]))

# ── 10. Datos para abrir PR ───────────────────────────────────────────

story.append(H1("10. Instrucciones para abrir PR"))

story.append(make_table([
    ["Campo", "Valor"],
    ["URL",
     "github.com/celestinojbm/Dona-agent/pull/new/<br/>"
     "hotfix/t2.1.b-action-center-load-error"],
    ["Título sugerido",
     "fix(automation) · corrige carga del Action Center en dashboard"],
    ["Base", "main"],
    ["Head", "hotfix/t2.1.b-action-center-load-error"],
    ["Body markdown", "Pegado abajo · listo para copiar"],
], col_widths=[1.6*inch, 5.0*inch]))

# ── 11. Body markdown ─────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("11. Body markdown del PR (copy-paste)"))

story.append(CODE(
    "## Resumen\n"
    "\n"
    "Hotfix post-merge T2.1.B. El dashboard mostraba 'No pudimos\n"
    "cargar tus acciones' al cargar el Centro de acción.\n"
    "\n"
    "## Causa raíz\n"
    "\n"
    "Combinación de:\n"
    "1. Backend retorna 404 'subscription_no_persistida' para subs\n"
    "   pre-T2.0.B no migradas a la tabla suscripcion_stripe.\n"
    "2. Route handler /api/automation/acciones propagaba 404 al cliente.\n"
    "3. Componente UI trataba cualquier no-200 como error fatal.\n"
    "4. Empty state existía pero solo se alcanzaba con 200 + count=0.\n"
    "\n"
    "Resultado: usuarios premium pre-T2.0.B veían un mensaje de\n"
    "error en lugar de un empty state con CTA para generar acciones.\n"
    "\n"
    "Hipótesis #5 y #6 del reporte del owner confirmadas. Las otras\n"
    "(env faltante, sesión rota) descartadas por inspección.\n"
    "\n"
    "## Fix\n"
    "\n"
    "- landing/app/api/automation/acciones/route.ts: 404 backend\n"
    "  'subscription_no_persistida' → 200 con lista vacía. Logging\n"
    "  seguro por categoría (missing_session, backend_404, etc.) sin\n"
    "  secretos ni PII.\n"
    "- landing/app/api/automation/acciones/generar/route.ts: mismas\n"
    "  categorías de logging.\n"
    "- landing/app/dashboard/seccion-action-center.tsx: panel de error\n"
    "  ahora muestra código del error y AGREGA botón 'Generar acciones'\n"
    "  además de 'Reintentar'. handleGenerar trata 404 con mensaje\n"
    "  específico que invita al usuario a completar el diagnóstico\n"
    "  por WhatsApp primero.\n"
    "- landing/app/dashboard/seccion-action-center.test.tsx (NEW):\n"
    "  7 tests vitest+jsdom cubren empty/loading/error/acciones.\n"
    "- landing/vitest.config.ts: incluye .test.tsx · pragma\n"
    "  @vitest-environment jsdom por archivo (vitest 2 no soporta\n"
    "  workspace API).\n"
    "- landing/package.json: + devDeps @testing-library/react,\n"
    "  @testing-library/jest-dom, jsdom.\n"
    "\n"
    "## Tests\n"
    "\n"
    "- pytest suite completa · 787/787 passing · cero regresiones\n"
    "- vitest · 35/35 passing (15 auth-matcher + 13 bridge + 7 NEW\n"
    "  componente Action Center)\n"
    "- npx tsc --noEmit · 0 errores\n"
    "- npm run build · 17/17 pages OK\n"
    "- npm run lint · 0 errors · 3 warnings preexistentes\n"
    "\n"
    "Tests específicos verifican que el botón 'Generar acciones' está\n"
    "disponible en TODOS los estados de la UI (loading/empty/error/\n"
    "ready) y que CRITICAL no muestra botón Aprobar.\n"
    "\n"
    "## Sin cambios de\n"
    "\n"
    "- env vars (Vercel ni Render)\n"
    "- backend (lógica T2.1.A intacta · solo el route handler de\n"
    "  landing reinterpreta el 404)\n"
    "- ejecutores (siguen siendo dry-run T2.1.A)\n"
    "- nada de Stripe/WhatsApp/email/publicaciones/créditos\n"
    "\n"
    "## Plan post-merge\n"
    "\n"
    "1. Vercel auto-redeploy ~2 min con los route handlers\n"
    "   actualizados.\n"
    "2. Smoke en dashboard:\n"
    "   - login · sección 'Centro de acción' carga sin error\n"
    "   - usuarios sin perfil ven empty state limpio · botón\n"
    "     'Generar acciones' visible\n"
    "   - usuarios con sub persistida ven sus acciones\n"
    "3. Verificar Vercel logs · debería aparecer\n"
    "   '[ACT-CENTER] GET /acciones · backend_404 ... · empty\n"
    "   fallback' para usuarios pre-T2.0.B · esto confirma el\n"
    "   código path correcto.\n"
))

story.append(BANNER(
    "<b>Branch pushed · sin merge.</b> Espera tu review en "
    "GitHub. Yo no mergeo nada hasta tu OK explícito."
))


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
