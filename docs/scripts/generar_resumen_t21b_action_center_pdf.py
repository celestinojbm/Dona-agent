"""
Genera Resumen_T21B_Action_Center_2026-05-09.pdf · resumen del PR
backend endpoints + landing proxy + UI Action Center (T2.1.B).
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T21B_Action_Center_2026-05-09.pdf"

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

# ── Portada ────────────────────────────────────────────────────────────

story.append(Paragraph("T2.1.B · Action Center dashboard + endpoints HTTP",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · Branch <b>pr/t2.1.b-action-center-dashboard</b> · "
    "base <b>main@daf3bf1</b> · hace visible y usable T2.1.A en el "
    "dashboard sin ejecutar acciones externas reales",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> PR listo para revisión. <b>787/787 pytest · "
    "28/28 vitest · tsc 0 errores · build 17/17 · lint 0 errors</b>. "
    "Backend: 12 endpoints HTTP nuevos (admin + internal). Landing: "
    "5 route handlers + bridge HMAC + componente UI con 8 estados "
    "visuales. <b>Sin merge · sin deploy.</b>"
))

# ── 1. Resumen ejecutivo ──────────────────────────────────────────────

story.append(H1("1. Resumen ejecutivo"))

story.append(P(
    "T2.1.B conecta el Automation Core (T2.1.A) al dashboard. El "
    "usuario premium ahora ve <b>oportunidades detectadas + acciones "
    "recomendadas con riesgo, costo, estado y razón</b>. Puede "
    "<i>generar acciones</i>, <i>aprobar</i>, <i>rechazar</i> y "
    "<i>ejecutar (dry-run)</i> · todo respetando los guardrails de "
    "T2.1.A: LOW auto · MEDIUM/HIGH requieren aprobación · CRITICAL "
    "bloqueado."
))

story.extend(bullets([
    "Cero acciones externas reales · todos los ejecutores siguen "
    "siendo dry-run de T2.1.A.",
    "Doble esquema de auth: <i>/admin/automation/*</i> con ADMIN_TOKEN "
    "(uso operativo) e <i>/internal/automation/*</i> con HMAC bridge "
    "(landing → backend, server-to-server) · ADMIN_TOKEN nunca llega "
    "al cliente.",
    "Anti-IDOR: el backend resuelve <i>telefono</i> desde "
    "<i>subscription_id</i> y verifica ownership de la "
    "<i>accion_id</i>. Un usuario no puede aprobar/ejecutar acciones "
    "de otro usuario · test específico lo verifica.",
    "Sanitización de respuesta: el backend filtra <i>idempotency_key</i> "
    "(interno), <i>payload_json</i> crudo y telefono completo antes "
    "de enviar al frontend.",
]))

# ── 2. Endpoints creados ──────────────────────────────────────────────

story.append(H1("2. Endpoints creados (12 nuevos)"))

story.append(H2("Backend FastAPI · /admin/automation/* (ADMIN_TOKEN)"))

story.append(make_table([
    ["Método", "Path", "Función"],
    ["GET", "/admin/automation/oportunidades?telefono=...",
     "Lista oportunidades detectadas para un telefono"],
    ["GET", "/admin/automation/acciones?telefono=...&estado=...",
     "Lista acciones (filtrable por estado)"],
    ["POST", "/admin/automation/acciones/generar",
     "Body: {telefono} · genera 1 acción por paso de cada playbook "
     "sugerido por el Opportunity Engine · idempotente"],
    ["POST", "/admin/automation/acciones/{id}/aprobar",
     "Cambia needs_approval → approved"],
    ["POST", "/admin/automation/acciones/{id}/rechazar",
     "Cambia → rejected"],
    ["POST", "/admin/automation/acciones/{id}/ejecutar",
     "Ejecuta dry-run · respeta guardrails T2.1.A"],
], col_widths=[0.6*inch, 3.2*inch, 3.0*inch]))

story.append(H2("Backend FastAPI · /internal/automation/* (HMAC bridge)"))

story.append(make_table([
    ["Método", "Path", "Body request"],
    ["POST", "/internal/automation/oportunidades", "{subscription_id}"],
    ["POST", "/internal/automation/acciones", "{subscription_id, estado?}"],
    ["POST", "/internal/automation/acciones/generar", "{subscription_id}"],
    ["POST", "/internal/automation/acciones/aprobar",
     "{subscription_id, accion_id}"],
    ["POST", "/internal/automation/acciones/rechazar",
     "{subscription_id, accion_id}"],
    ["POST", "/internal/automation/acciones/ejecutar",
     "{subscription_id, accion_id}"],
], col_widths=[0.6*inch, 3.4*inch, 2.8*inch]))

story.append(C(
    "Auth: header <i>X-Internal-Signature</i> = HMAC-SHA256(body, "
    "INTERNAL_BRIDGE_SECRET). Mismo patrón que <i>/internal/usuario-resumen</i> "
    "(T1.4.D). El backend resuelve <i>telefono</i> desde "
    "<i>subscription_id</i> · NUNCA acepta <i>telefono</i> ni "
    "<i>accion_id</i> sin verificar ownership."
))

story.append(H2("Landing Next · /api/automation/* (auth() server-side)"))

story.append(make_table([
    ["Método", "Path", "Función"],
    ["GET", "/api/automation/acciones",
     "Lista del usuario autenticado · query <i>estado</i> opcional"],
    ["POST", "/api/automation/acciones/generar",
     "Genera desde Opportunity Engine"],
    ["POST", "/api/automation/acciones/[id]/aprobar", "—"],
    ["POST", "/api/automation/acciones/[id]/rechazar", "—"],
    ["POST", "/api/automation/acciones/[id]/ejecutar",
     "Dry-run · respeta guardrails"],
], col_widths=[0.6*inch, 3.4*inch, 2.8*inch]))

# ── 3. Componentes UI ─────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Componentes UI"))

story.append(make_table([
    ["Archivo", "Tipo", "Resumen"],
    ["landing/lib/automation-types.ts", "NEW",
     "Tipos compartidos client+server · "
     "<i>AccionAutomatizacion</i>, <i>EstadoAccion</i>, "
     "<i>NivelRiesgo</i>, response types"],
    ["landing/lib/automation-bridge.ts", "NEW",
     "<i>server-only</i> · 6 funciones HMAC + manejo de "
     "timeout/auth/errores. <i>fetchOportunidades</i>, "
     "<i>fetchAcciones</i>, <i>generarAcciones</i>, "
     "<i>aprobarAccion</i>, <i>rechazarAccion</i>, "
     "<i>ejecutarAccion</i>"],
    ["landing/lib/__mocks__/server-only.ts", "NEW",
     "Stub para vitest · permite testear el bridge en Node"],
    ["landing/app/api/automation/acciones/route.ts", "NEW", "GET"],
    ["landing/app/api/automation/acciones/generar/route.ts", "NEW",
     "POST"],
    ["landing/app/api/automation/acciones/[id]/aprobar/route.ts",
     "NEW", "POST"],
    ["landing/app/api/automation/acciones/[id]/rechazar/route.ts",
     "NEW", "POST"],
    ["landing/app/api/automation/acciones/[id]/ejecutar/route.ts",
     "NEW", "POST"],
    ["landing/app/dashboard/seccion-action-center.tsx", "NEW",
     "Componente React del Action Center · 8 estados visuales · "
     "iconos lucide · banners por riesgo · resultado dry-run "
     "renderizado · botones aprobar/rechazar/ejecutar contextuales"],
    ["landing/app/dashboard/dashboard-client.tsx", "MOD",
     "Importa <i>SeccionActionCenter</i> y lo renderiza después de "
     "<i>SeccionHistorial</i> si la sub no está canceled (+9 líneas)"],
    ["landing/vitest.config.ts", "MOD",
     "Alias <i>server-only</i> al mock para tests de bridge"],
], col_widths=[3.2*inch, 0.5*inch, 2.9*inch]))

# ── 4. Flujo end-to-end ───────────────────────────────────────────────

story.append(H1("4. Flujo dashboard → proxy → backend → automation core"))

story.append(CODE(
    "Cliente (browser)\n"
    "  └─ React: SeccionActionCenter\n"
    "      ├─ useEffect → fetch('/api/automation/acciones')\n"
    "      └─ click 'Aprobar' → POST '/api/automation/acciones/123/aprobar'\n"
    "\n"
    "Landing (Vercel · Next route handler · server-only)\n"
    "  └─ auth() → session.subscriptionId  (T1.4.D guardrail)\n"
    "      └─ aprobarAccion(subscriptionId, 123)  ← automation-bridge.ts\n"
    "          ├─ HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET)\n"
    "          └─ POST backend/internal/automation/acciones/aprobar\n"
    "             headers: X-Internal-Signature, X-Request-ID\n"
    "             body: {subscription_id, accion_id: 123}\n"
    "\n"
    "Backend (Render · FastAPI)\n"
    "  └─ _verificar_firma_interna(body, sig)\n"
    "      └─ subscription_id → telefono (suscripcion_stripe)\n"
    "          └─ _accion_pertenece_a_telefono(accion_id, telefono)\n"
    "              └─ action_center.aprobar_accion(accion_id)\n"
    "                  ├─ permissions.transicion_valida(...)\n"
    "                  ├─ DB UPDATE estado='approved'\n"
    "                  └─ audit.registrar_evento('action_approved')\n"
    "\n"
    "Respuesta sanitizada → landing → cliente → re-fetch lista"
))

# ── 5. Seguridad ──────────────────────────────────────────────────────

story.append(H1("5. Seguridad aplicada"))

story.append(make_table([
    ["Capa", "Mecanismo"],
    ["Cliente",
     "NextAuth session · <i>subscriptionId</i> server-side via "
     "<i>auth()</i>. Cliente NUNCA envía <i>telefono</i> ni "
     "<i>accion_id</i> arbitrario."],
    ["Landing → Backend",
     "HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET). Mismo patrón "
     "que <i>/internal/stripe-event</i> y "
     "<i>/internal/usuario-resumen</i>."],
    ["Backend ownership",
     "Resuelve <i>telefono</i> desde <i>subscription_id</i> · "
     "para acciones, verifica que <i>row.telefono == telefono</i>. "
     "Test <b>TestInternalIDOR</b> confirma 404 si se intenta "
     "aprobar acción de otro usuario."],
    ["Sanitización response",
     "<i>_filtrar_accion_para_dashboard</i> excluye "
     "<i>idempotency_key</i>, <i>payload_json</i> crudo, "
     "<i>telefono</i>. Test <b>TestRespuestasNoExponenSensibles</b> "
     "lo valida."],
    ["Errores",
     "<i>error_message</i> max 500 chars · sin stack traces · "
     "agente sanitizado en <i>marcar_fallida</i>."],
    ["Logs",
     "Bridge logs muestran <i>shortId(subscription_id)</i> · "
     "backend audit log usa <i>telefono_short</i> (sin completo)."],
    ["CRITICAL bloqueado",
     "Auncon aprobación, <i>execution.ejecutar_accion</i> bloquea "
     "y emite audit <i>action_blocked_critical</i>. Test "
     "<b>TestEjecutarCriticalBloqueado</b>."],
    ["HIGH sin ejecutor",
     "Falla con mensaje claro apuntando a T2.1.C. No envía nada."],
], col_widths=[1.6*inch, 5.0*inch]))

# ── 6. Tests ──────────────────────────────────────────────────────────

story.append(H1("6. Tests ejecutados y resultado"))

story.append(BANNER(
    "<b>pytest · 787/787 passing</b> (769 base T2.1.A + 18 nuevos "
    "T2.1.B endpoints) · 172s.<br/>"
    "<b>vitest · 28/28 passing</b> (15 auth-matcher + 13 "
    "automation-bridge) · 417ms.<br/>"
    "<b>tsc · 0 errores · build 17/17 · lint 0 errors · 3 warnings "
    "preexistentes.</b>"
))

story.append(H2("Tests pytest nuevos · tests/test_automation_endpoints.py"))

story.append(make_table([
    ["Clase", "Tests", "Cubre"],
    ["TestAdminAuth", "3",
     "Sin token → 403 · token inválido → 403 · valido → 200"],
    ["TestAdminGenerarAcciones", "2",
     "Genera ≥4 acciones desde perfil completo · telefono "
     "requerido"],
    ["TestAdminListarAcciones", "1",
     "Filtro por estado funciona"],
    ["TestAdminAprobarRechazar", "3",
     "Aprobar cambia estado · rechazar cambia estado · "
     "inexistente → 404"],
    ["TestAdminEjecutar", "1",
     "LOW pending → completed con result_json"],
    ["TestInternalAuth", "4",
     "Sin firma → 401 · firma inválida → 401 · firma OK → 200 · "
     "subscription_id inexistente → 404"],
    ["TestInternalGenerarAprobar", "1",
     "Flow completo internal: generar → listar → aprobar"],
    ["<b>TestInternalIDOR</b>", "<b>1</b>",
     "<b>Aprobar accion_id de otro usuario → 404 · anti-IDOR</b>"],
    ["<b>TestRespuestasNoExponenSensibles</b>", "<b>1</b>",
     "<b>Response NO contiene idempotency_key · payload_json · "
     "telefono completo</b>"],
    ["<b>TestEjecutarCriticalBloqueado</b>", "<b>1</b>",
     "<b>Critical aprobado → bloqueado · audit "
     "action_blocked_critical</b>"],
], col_widths=[3.0*inch, 0.4*inch, 3.2*inch]))

story.append(H2("Tests vitest nuevos · landing/lib/automation-bridge.test.ts"))

story.append(make_table([
    ["Grupo", "Tests", "Cubre"],
    ["validación inputs", "3",
     "Sin sub_id · sin accion_id · accion_id no entero → ok=false"],
    ["env vars faltantes", "2",
     "Sin BACKEND_URL → ok=false · sin INTERNAL_BRIDGE_SECRET → "
     "ok=false (sin red)"],
    ["firma HMAC y respuestas", "7",
     "X-Internal-Signature 64 hex · 200 → data · 404/401 → status "
     "propagado · accion_id en body · URL correcta · ejecutar URL"],
    ["seguridad", "1",
     "Respuesta NO contiene INTERNAL_BRIDGE_SECRET en serialización "
     "ni en error"],
], col_widths=[2.0*inch, 0.4*inch, 4.2*inch]))

# ── 7. Riesgos ────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("7. Riesgos"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["ADMIN_TOKEN expuesto vía /admin/automation/*",
     "Bajo",
     "Solo el owner conoce ADMIN_TOKEN · landing usa la ruta "
     "/internal/* · si alguien con token admin lo filtra es "
     "responsabilidad operativa. Compare con /admin/jobs-recientes "
     "que ya existe."],
    ["Race condition aiosqlite en pytest workers",
     "Cero · solo dev",
     "El primer run reportó 1 falla intermitente con "
     "'Event loop is closed' (issue conocido de aiosqlite con "
     "concurrencia thread). Re-run consistente passes 787/787."],
    ["Ejecución pesada · si el usuario hace clic 'Ejecutar' "
     "en cada acción LOW · genera N llamadas",
     "Bajo · UX",
     "Las acciones LOW son funciones puras dry-run (esqueletos). "
     "No hay rate limit aún · futuro PR si se conecta LLM real "
     "(T2.1.C)."],
    ["Telefono SÍ está en payload_summary del audit log "
     "(truncado · telefono_short)",
     "Cero · CCPA",
     "Solo prefijo+sufijo · principio de minimización. Audit log "
     "queda accesible solo a backend ops."],
    ["Si el usuario aprueba una acción HIGH, se queda en "
     "'approved' indefinida en T2.1.A/B",
     "Bajo · UX",
     "El componente muestra aviso claro: 'Esta acción es de alto "
     "impacto · está aprobada pero todavía requiere ejecutor con "
     "guardrails reforzados (próximo PR)'. T2.1.C la ejecutará."],
    ["Backend no rate-limit a /admin/automation/acciones/generar",
     "Bajo",
     "Generar es idempotente · re-llamar no duplica acciones "
     "(idempotency_key). Si crece, futuro PR puede agregar "
     "throttle."],
], col_widths=[2.4*inch, 1.0*inch, 3.2*inch]))

# ── 8. Out of scope ───────────────────────────────────────────────────

story.append(H1("8. Out of scope · NO entra en T2.1.B"))

story.extend(bullets([
    "<b>Ejecutores reales</b> (envío WhatsApp, publicación, "
    "Stripe writes) · sigue siendo T2.1.C.",
    "<b>Reservas/descuento de créditos</b> · T2.1.D.",
    "<b>Pruning del audit log</b> · futuro PR.",
    "<b>Métricas / dashboard de KPIs del Action Center</b>.",
    "<b>Notificaciones</b> (email/push) cuando una acción cambia "
    "de estado.",
    "<b>Re-generación inteligente</b> (LLM-as-judge) que prioriza "
    "oportunidades · hoy es determinístico.",
    "<b>UX avanzada</b>: drag-and-drop priorización · markdown "
    "renderer del result · vista de calendario · filtros visuales.",
]))

# ── 9. Siguiente PR ───────────────────────────────────────────────────

story.append(H1("9. Siguiente PR recomendado · T2.1.C"))

story.append(P(
    "<b>T2.1.C · Ejecutores reales con guardrails</b>:"
))

story.extend(bullets([
    "Conectar LLM (Anthropic Claude) a los ejecutores LOW para "
    "que <i>generar_plan_semanal</i>, "
    "<i>generar_calendario_contenido</i>, "
    "<i>generar_idea_oferta</i> produzcan output de calidad real "
    "(no esqueletos).",
    "Conectar ejecutor real para MEDIUM <i>preparar_mensaje_*</i> "
    "y <i>borrador_copy_*</i> · sigue siendo dry-run hasta el "
    "envío explícito.",
    "Conectar HIGH <i>enviar_mensaje_whatsapp</i> con guardrails "
    "extra: TCPA verificado · opt-in del cliente · rate-limit · "
    "reembolso si falla.",
    "<b>NO desbloquear CRITICAL</b> en T2.1.C · queda para futuro "
    "PR con confirmación reforzada (2FA owner · timer cooldown · "
    "etc).",
    "Reservas de créditos: descontar al iniciar ejecución · "
    "reembolsar si falla. Llega T2.1.D.",
]))

# ── 10. Datos para abrir el PR ────────────────────────────────────────

story.append(H1("10. Instrucciones para abrir PR"))

story.append(make_table([
    ["Campo", "Valor"],
    ["URL",
     "github.com/celestinojbm/Dona-agent/pull/new/<br/>"
     "pr/t2.1.b-action-center-dashboard"],
    ["Título sugerido",
     "feat(automation): Action Center dashboard + endpoints HTTP "
     "(T2.1.B)"],
    ["Base", "main"],
    ["Head", "pr/t2.1.b-action-center-dashboard"],
    ["Body markdown",
     "Generado abajo · listo para copiar/pegar"],
], col_widths=[1.6*inch, 5.0*inch]))

# ── 11. Body markdown ────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("11. Body markdown del PR (copy-paste)"))

story.append(CODE(
    "## Resumen\n"
    "\n"
    "Conecta el Automation Core (T2.1.A) al dashboard. Premium ve\n"
    "oportunidades + acciones recomendadas con riesgo, costo, estado\n"
    "y razón. Puede generar, aprobar, rechazar y ejecutar (dry-run)\n"
    "respetando guardrails: LOW auto · MEDIUM/HIGH requieren\n"
    "aprobación · CRITICAL bloqueado.\n"
    "\n"
    "Cero acciones externas reales · todos los ejecutores siguen\n"
    "siendo dry-run de T2.1.A.\n"
    "\n"
    "## Cambios\n"
    "\n"
    "Backend (agent/main.py):\n"
    "  - 6 endpoints /admin/automation/* (ADMIN_TOKEN)\n"
    "  - 6 endpoints /internal/automation/* (HMAC bridge)\n"
    "  - Helpers _filtrar_accion_para_dashboard (anti-leak),\n"
    "    _resolver_telefono_desde_subscription, _accion_pertenece_\n"
    "    a_telefono (anti-IDOR)\n"
    "  - Generar crea 1 acción por paso del playbook · idempotente\n"
    "\n"
    "Backend (agent/automation/execution.py):\n"
    "  - Ajuste de orden: marcar_running antes del bloqueo CRITICAL\n"
    "    para que la transición running→failed sea válida según el\n"
    "    lifecycle. Tests T2.1.A siguen verdes.\n"
    "\n"
    "Landing:\n"
    "  - automation-types.ts (tipos compartidos)\n"
    "  - automation-bridge.ts (server-only · 6 funciones HMAC)\n"
    "  - 5 route handlers en /api/automation/*\n"
    "  - seccion-action-center.tsx (componente Action Center)\n"
    "  - dashboard-client.tsx · render del componente\n"
    "  - vitest.config.ts · alias para server-only\n"
    "  - __mocks__/server-only.ts (stub Node)\n"
    "\n"
    "Tests:\n"
    "  - tests/test_automation_endpoints.py · 18 tests pytest\n"
    "    cubre admin auth, generar, listar, aprobar, rechazar,\n"
    "    ejecutar, internal auth, IDOR, sanitización response,\n"
    "    CRITICAL bloqueado\n"
    "  - landing/lib/automation-bridge.test.ts · 13 tests vitest\n"
    "    cubre validación inputs, env vars, firma HMAC, status\n"
    "    propagation, no-leak de secrets\n"
    "\n"
    "## Tests · 787/787 pytest · 28/28 vitest · build verde\n"
    "\n"
    "- pytest tests/test_automation_endpoints.py · 18/18 · 41s\n"
    "- pytest suite completa · 787/787 · 172s\n"
    "- npm test (vitest) · 28/28 · 417ms\n"
    "- npx tsc --noEmit · 0 errores\n"
    "- npm run build · 17/17 pages OK\n"
    "- npm run lint · 0 errors · 3 warnings preexistentes\n"
    "\n"
    "## Seguridad\n"
    "\n"
    "- subscription_id viene SIEMPRE de auth() server-side (T1.4.D)\n"
    "- Backend resuelve telefono y verifica ownership de accion_id\n"
    "  (anti-IDOR · TestInternalIDOR)\n"
    "- Response sanitizada · sin idempotency_key / payload_json /\n"
    "  telefono completo (TestRespuestasNoExponenSensibles)\n"
    "- HMAC-SHA256 sobre body exacto · mismo patrón que\n"
    "  /internal/usuario-resumen\n"
    "- ADMIN_TOKEN nunca llega al cliente · landing usa /internal/*\n"
    "- CRITICAL siempre bloqueado · audit action_blocked_critical\n"
    "  (TestEjecutarCriticalBloqueado)\n"
    "- HIGH sin ejecutor T2.1.A → falla con mensaje claro\n"
    "\n"
    "## Cero writes / efectos externos\n"
    "\n"
    "- Sin Stripe writes / DB writes prod / env changes / deploys\n"
    "- Sin envíos reales WhatsApp / email / publicaciones redes\n"
    "- Sin gasto de créditos reales\n"
    "- Sin merge a main\n"
    "\n"
    "## Out of scope\n"
    "\n"
    "- Ejecutores reales LLM/WhatsApp (T2.1.C)\n"
    "- Reservas/reembolsos créditos (T2.1.D)\n"
    "- Métricas dashboard automation\n"
    "- Notificaciones / re-generación con LLM-as-judge\n"
    "- Markdown renderer fancy del result_json\n"
    "\n"
    "## Plan post-merge\n"
    "\n"
    "1. Render auto-redeploy ~2 min · 12 endpoints HTTP nuevos vivos.\n"
    "2. Vercel auto-redeploy · landing con nuevos route handlers +\n"
    "   componente Action Center.\n"
    "3. Smoke en producción:\n"
    "   - login dashboard · verificar que aparece sección 'Centro\n"
    "     de acción'\n"
    "   - botón 'Generar acciones' · debería listar acciones\n"
    "   - aprobar una MEDIUM → verificar cambio de estado\n"
    "   - ejecutar una LOW pending → ver result dry-run\n"
    "4. (Opcional) test con curl:\n"
    "   curl -H 'Authorization: Bearer $ADMIN_TOKEN' \\\n"
    "     'https://dona-agent.onrender.com/admin/automation/acciones?\n"
    "      telefono=$TEL'\n"
))

story.append(BANNER(
    "<b>Branch pushed · sin merge.</b> Espera tu review en GitHub. "
    "Yo no mergeo nada hasta tu OK explícito."
))


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch,
)
doc.build(story)
print(f"OK · {OUTPUT}")
