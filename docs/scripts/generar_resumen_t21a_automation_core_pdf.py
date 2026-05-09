"""
Genera Resumen_T21A_Automation_Core_2026-05-09.pdf · resumen del PR
backend del Automation Core (T2.1.A).
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T21A_Automation_Core_2026-05-09.pdf"

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

story.append(Paragraph("T2.1.A · Dona Automation Core (backend)",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · Branch <b>pr/t2.1-automation-core</b> · base "
    "<b>main@43aceef</b> · pipeline: diagnóstico → oportunidades → "
    "playbooks → acciones → permisos → ejecución controlada → audit",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> PR backend listo para revisión. <b>107/107 "
    "tests T2.1.A · 769/769 suite completa</b> (cero regresiones). "
    "Pipeline completo end-to-end demostrado · ejecutores internos "
    "dry-run · CRITICAL bloqueado · MEDIUM/HIGH requieren aprobación · "
    "audit log sin PII. <b>Sin merge · sin deploy.</b>"
))

# ── 1. Resumen ejecutivo ──────────────────────────────────────────────

story.append(H1("1. Resumen ejecutivo"))

story.append(P(
    "T2.1.A entrega el núcleo backend del sistema completo de "
    "automatización de Dona. NO es un MVP débil: incluye los 7 "
    "componentes fundacionales del pipeline real, con permisos por "
    "riesgo, idempotencia, audit log sanitizado y bloqueo estricto "
    "de acciones CRITICAL. La interfaz de ejecutores está lista para "
    "que T2.1.C conecte ejecutores reales (LLM, WhatsApp envío, etc.) "
    "respetando los guardrails establecidos aquí."
))

story.extend(bullets([
    "Pipeline funcional: el demo end-to-end procesa un perfil "
    "completo, detecta 6 oportunidades, genera acciones, ejecuta "
    "automáticamente las LOW, bloquea CRITICAL y deja audit trail.",
    "Cero efecto externo: los ejecutores T2.1.A son funciones puras · "
    "test específico verifica que NO contienen referencias a Whapi, "
    "Twilio, Stripe, providers, ni publicaciones reales.",
    "Cero PII en logs: test específico verifica que el sanitizador "
    "elimina telefono, email, password, customer_id, secrets y los 6 "
    "campos del onboarding extendido.",
]))

# ── 2. Arquitectura implementada ──────────────────────────────────────

story.append(H1("2. Arquitectura implementada"))

story.append(CODE(
    "agent/automation/\n"
    "├── __init__.py        — descripción del pipeline\n"
    "├── permissions.py     — NivelRiesgo + reglas de auto-ejecución\n"
    "├── costos.py          — estimación de créditos por acción/playbook\n"
    "├── playbooks.py       — catálogo de 6 playbooks fundacionales\n"
    "├── opportunities.py   — Opportunity Engine determinístico\n"
    "├── audit.py           — audit log + sanitizador anti-PII\n"
    "├── action_center.py   — CRUD acciones + lifecycle estados\n"
    "├── execution.py       — ejecutores internos (dry-run)\n"
    "└── models.py          — AccionAutomatizacion + AuditLog +\n"
    "                         MIGRACIONES_AUTOMATION (PostgreSQL)\n"
    "\n"
    "Pipeline completo:\n"
    "  perfil_negocio (T2.0.E.1)\n"
    "    → opportunities.detectar_oportunidades(perfil)\n"
    "    → playbooks.obtener_playbook(opp.playbook_sugerido)\n"
    "    → action_center.crear_accion(...)  [idempotente]\n"
    "    → permissions.estado_inicial_para_riesgo(riesgo)\n"
    "    → execution.ejecutar_accion(accion)\n"
    "    → audit.registrar_evento(...) en cada paso\n"
    "    → AuditLogAutomatizacion + AccionAutomatizacion en DB"
))

# ── 3. Archivos modificados/nuevos ─────────────────────────────────────

story.append(H1("3. Archivos modificados / nuevos"))

story.append(make_table([
    ["Archivo", "Tipo", "Resumen"],
    ["agent/automation/__init__.py", "NEW",
     "Doc del pipeline · descripción de submódulos"],
    ["agent/automation/permissions.py", "NEW",
     "NivelRiesgo enum · clasificar_riesgo · "
     "requiere_aprobacion · puede_auto_ejecutar · esta_bloqueado_t21 · "
     "estado_inicial · transicion_valida"],
    ["agent/automation/costos.py", "NEW",
     "COSTO_POR_TIPO_ACCION + helpers"],
    ["agent/automation/playbooks.py", "NEW",
     "6 playbooks fundacionales · listar/obtener · riesgo y costo "
     "calculados desde pasos"],
    ["agent/automation/opportunities.py", "NEW",
     "Opportunity Engine · 6 reglas determinísticas · ID idempotente · "
     "sync + async (lee perfil_negocio)"],
    ["agent/automation/audit.py", "NEW",
     "registrar_evento · sanitizar_payload (whitelist eventos · "
     "blacklist claves PII)"],
    ["agent/automation/action_center.py", "NEW",
     "crear_accion idempotente · listar · aprobar/rechazar/cancelar · "
     "marcar running/completada/fallida · audit en cada cambio"],
    ["agent/automation/execution.py", "NEW",
     "10 ejecutores internos dry-run · validación de estado · bloqueo "
     "CRITICAL · sanitización de errores"],
    ["agent/automation/models.py", "NEW",
     "AccionAutomatizacion · AuditLogAutomatizacion · "
     "MIGRACIONES_AUTOMATION (PostgreSQL · idempotente)"],
    ["agent/memory.py", "MOD",
     "Concatena MIGRACIONES_AUTOMATION en _migrar_columnas() · "
     "+5 líneas"],
    ["tests/test_automation_*.py", "NEW · 7 archivos",
     "107 tests cubren todos los componentes"],
], col_widths=[3.0*inch, 0.7*inch, 2.9*inch]))

# ── 4. Modelos / tablas nuevas ────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Tablas nuevas"))

story.append(H2("acciones_automatizacion"))

story.append(make_table([
    ["Columna", "Tipo", "Default", "Notas"],
    ["id", "SERIAL PK", "—", ""],
    ["telefono", "VARCHAR(50)", "—",
     "Owner · index · matching contra perfil_negocio.telefono"],
    ["opportunity_id", "VARCHAR(100)", "''", "Opcional"],
    ["playbook_id", "VARCHAR(100)", "''", "Opcional"],
    ["tipo_accion", "VARCHAR(80)", "—",
     "Index · gobierna riesgo y ejecutor"],
    ["titulo", "VARCHAR(200)", "—", ""],
    ["descripcion", "TEXT", "''", ""],
    ["razon_recomendacion", "TEXT", "''", ""],
    ["estado", "VARCHAR(20)", "'pending'",
     "Index · pending|needs_approval|approved|running|completed|"
     "rejected|failed|cancelled"],
    ["riesgo", "VARCHAR(20)", "'medium'", "low|medium|high|critical"],
    ["costo_creditos_estimado", "INTEGER", "0",
     "Estimación · NO se descuenta hoy"],
    ["requires_approval", "BOOLEAN", "TRUE", ""],
    ["payload_json", "TEXT", "'{}'", "Input"],
    ["result_json", "TEXT", "'{}'", "Output"],
    ["error_message", "TEXT", "''", "Sanitizado · max 500 chars"],
    ["idempotency_key", "VARCHAR(120)", "''",
     "<b>Index · sha256 de (tel|tipo|playbook|opp|fecha) · evita "
     "duplicar misma acción el mismo día</b>"],
    ["created_at / updated_at", "TIMESTAMP", "NOW()", ""],
    ["approved_at / rejected_at / completed_at", "TIMESTAMP", "NULL",
     "Auditoría temporal por estado"],
], col_widths=[2.0*inch, 1.2*inch, 0.8*inch, 2.6*inch]))

story.append(H2("audit_log_automatizacion"))

story.append(make_table([
    ["Columna", "Tipo", "Notas"],
    ["id", "SERIAL PK", ""],
    ["telefono_short", "VARCHAR(20)",
     "<b>Truncado</b> · NUNCA el completo"],
    ["evento", "VARCHAR(60)",
     "Whitelist · 10 eventos válidos"],
    ["accion_id", "INTEGER NULL", "FK conceptual"],
    ["riesgo", "VARCHAR(20)", "low|medium|high|critical"],
    ["payload_summary", "TEXT", "JSON sanitizado"],
    ["created_at", "TIMESTAMP", "Index"],
], col_widths=[2.0*inch, 1.4*inch, 3.2*inch]))

# ── 5. Componentes / endpoints / helpers ──────────────────────────────

story.append(H1("5. APIs públicas creadas (Python)"))

story.append(make_table([
    ["Módulo", "Funciones"],
    ["permissions",
     "<i>NivelRiesgo</i> enum · <i>clasificar_riesgo(tipo)</i> · "
     "<i>requiere_aprobacion(r)</i> · <i>puede_auto_ejecutar(r)</i> · "
     "<i>esta_bloqueado_t21(r)</i> · <i>estado_inicial_para_riesgo(r)</i> · "
     "<i>transicion_valida(actual, destino)</i>"],
    ["costos",
     "<i>estimar_costo_accion(tipo)</i> · "
     "<i>estimar_costo_playbook(pasos)</i>"],
    ["playbooks",
     "<i>listar_playbooks()</i> · <i>obtener_playbook(id)</i> · "
     "<i>existe_playbook(id)</i>"],
    ["opportunities",
     "<i>detectar_oportunidades(perfil, telefono)</i> · "
     "<i>detectar_oportunidades_para_telefono(telefono)</i> async"],
    ["audit",
     "<i>registrar_evento(evento, telefono, ...)</i> async · "
     "<i>sanitizar_payload(d)</i>"],
    ["action_center",
     "<i>crear_accion(...)</i> idempotente · <i>listar_acciones(...)</i> · "
     "<i>aprobar/rechazar/cancelar(id)</i> · "
     "<i>marcar_running/completada/fallida(id)</i>"],
    ["execution",
     "<i>ejecutar_accion(accion)</i> · 10 ejecutores internos dry-run "
     "(EJECUTORES_T21A)"],
], col_widths=[1.4*inch, 5.2*inch]))

story.append(C(
    "Estos son APIs internas Python. T2.1.B agregará endpoints HTTP "
    "(landing route + admin endpoint backend) para que el dashboard "
    "pueda consumirlos."
))

# ── 6. Playbooks incluidos ────────────────────────────────────────────

story.append(H1("6. Playbooks fundacionales (6)"))

story.append(make_table([
    ["ID", "Objetivo", "Riesgo", "Costo"],
    ["diagnostico_a_plan_semanal",
     "Convertir el diagnóstico en un plan de la semana",
     "low", "14"],
    ["calendario_contenido_7d",
     "Plan de contenido 7 días alineado al cliente ideal",
     "medium", "26"],
    ["reactivacion_clientes",
     "Recuperar clientes que dejaron de comprar",
     "<b>high</b>", "26"],
    ["mejora_oferta",
     "Iterar la oferta principal del negocio",
     "medium", "22"],
    ["campana_whatsapp_simple",
     "Campaña corta (3 mensajes) sobre la oferta",
     "<b>high</b>", "71"],
    ["checklist_ventas",
     "Checklist comercial para destrabar ventas",
     "low", "11"],
], col_widths=[2.4*inch, 2.6*inch, 0.7*inch, 0.6*inch]))

story.append(C(
    "Los pasos HIGH (enviar_mensaje_whatsapp, enviar_campana_masiva) "
    "están definidos en los playbooks pero T2.1.A NO los ejecuta · "
    "esperan ejecutores reales en T2.1.C."
))

# ── 7. Reglas de riesgo / permisos ────────────────────────────────────

story.append(H1("7. Reglas de riesgo y permisos"))

story.append(make_table([
    ["Nivel", "Ejemplos", "Estado inicial", "Auto-ejecuta", "T2.1.A"],
    ["LOW", "generar_plan / analizar_diagnostico / "
     "checklist_ventas",
     "pending", "<b>SÍ</b>", "Ejecuta dry-run"],
    ["MEDIUM", "preparar_mensaje_whatsapp / "
     "preparar_publicacion_redes / borrador_copy_oferta",
     "needs_approval", "NO · aprobación simple", "Ejecuta tras aprobar"],
    ["HIGH", "enviar_mensaje_whatsapp / publicar_red_social / "
     "contactar_lead",
     "needs_approval", "NO · aprobación explícita",
     "<b>BLOQUEADO</b> · sin ejecutor T2.1.A"],
    ["CRITICAL", "envio_masivo_clientes / borrar_datos_negocio / "
     "cambiar_config_cuenta",
     "needs_approval", "NO · confirmación fuerte",
     "<b>BLOQUEADO ESTRICTAMENTE</b> · audit log "
     "<i>action_blocked_critical</i>"],
], col_widths=[0.6*inch, 2.0*inch, 1.2*inch, 1.1*inch, 1.7*inch]))

# ── 8. Tests ────────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("8. Tests · 107 nuevos · 769/769 suite completa"))

story.append(make_table([
    ["Archivo", "Tests", "Cubre"],
    ["test_automation_permissions.py", "35",
     "Clasificación · transiciones · estado inicial · "
     "default seguro (medium para tipo desconocido)"],
    ["test_automation_playbooks.py", "14",
     "Catálogo · estructura completa · riesgo máximo de los pasos · "
     "costo suma de pasos"],
    ["test_automation_opportunities.py", "16",
     "ID determinístico sin filtrar telefono · 6 reglas individuales · "
     "perfil vacío vs completo · orden por prioridad · idempotencia"],
    ["test_automation_action_center.py", "14",
     "LOW estado pending · MEDIUM/HIGH/CRITICAL needs_approval · "
     "idempotencia · listar por estado · transiciones · "
     "result/error persisten"],
    ["test_automation_execution.py", "11",
     "<b>LOW pending → ejecuta · MEDIUM sin aprobación falla · "
     "MEDIUM aprobado ejecuta · HIGH sin ejecutor falla · "
     "CRITICAL bloqueado emite audit</b> · ejecutores internos "
     "no tienen referencias a providers"],
    ["test_automation_audit.py", "11",
     "<b>Sanitiza claves PII · descarta campos onboarding extendido · "
     "trunca strings · telefono se trunca en DB · NO loguea PII en "
     "stdout</b>"],
    ["test_automation_models.py", "6",
     "Migración runtime · todas las columnas · MIGRACIONES_AUTOMATION "
     "concatenado en memory.py"],
], col_widths=[2.6*inch, 0.4*inch, 3.6*inch]))

story.append(BANNER(
    "<b>pytest tests/test_automation_*.py · 107/107 passing en 52s.</b> "
    "<b>pytest suite completa · 769/769 passing en 296s · cero "
    "regresiones</b> sobre los 662 tests previos (T2.0.E.1 incluido)."
))

# ── 9. Riesgos ────────────────────────────────────────────────────────

story.append(H1("9. Riesgos"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Acciones HIGH/CRITICAL podrían ejecutarse si alguien "
     "agrega ejecutor sin guardrails",
     "Bajo · futuro PR",
     "T2.1.C debe respetar el contrato: <i>esta_bloqueado_t21</i> "
     "y validación de estado en <i>execution.ejecutar_accion</i>. "
     "Tests de execution lo enforced."],
    ["Detector de oportunidades es determinístico · puede no "
     "coincidir con la mejor sugerencia humana",
     "Bajo · UX",
     "T2.1.A es la base · futuro PR puede agregar LLM-as-judge "
     "para reordenar prioridades. Las reglas actuales son "
     "conservadoras."],
    ["Idempotency key incluye fecha · misma acción al día "
     "siguiente regenera",
     "Cero · es intencional",
     "Permite que Dona vuelva a sugerir lo mismo si el contexto "
     "cambia. Si el usuario quiere bloquear permanentemente, "
     "rechaza la acción."],
    ["Cap 500 chars en error_message podría truncar info útil",
     "Bajo",
     "Suficiente para diagnóstico · stack traces NUNCA van al "
     "campo · solo type+mensaje genérico."],
    ["MIGRACIONES_AUTOMATION fallan en SQLite (Postgres syntax)",
     "Cero · esperado",
     "_migrar_columnas tolera 'syntax error'. SQLite usa "
     "Base.metadata.create_all() que sí entiende los modelos. "
     "Tests confirman que las tablas/columnas están en SQLite."],
    ["Audit log puede crecer mucho",
     "Bajo · futuro",
     "Indexes por (telefono_short, evento, accion_id, created_at) · "
     "queries rápidas. Pruning futuro · otro PR."],
], col_widths=[2.4*inch, 1.0*inch, 3.2*inch]))

# ── 10. Out of scope ──────────────────────────────────────────────────

story.append(H1("10. Out of scope · NO entra en T2.1.A"))

story.extend(bullets([
    "<b>Dashboard / Action Center UI</b> · será T2.1.B (PR ortogonal "
    "frontend + endpoints HTTP).",
    "<b>Ejecutores reales</b> (envío real WhatsApp / publicación / "
    "contacto leads) · será T2.1.C con guardrails extra (TCPA, "
    "rate limiting, opt-in).",
    "<b>Reservas/reembolsos de créditos</b> · T2.1.A solo estima · "
    "el descuento real será T2.1.D cuando se conecten ejecutores "
    "que cuestan tokens LLM.",
    "<b>LLM real</b> en ejecutores · T2.1.A entrega esqueletos "
    "placeholder. T2.1.C conectará Anthropic/DeepSeek/etc.",
    "<b>Integraciones externas</b>: Whapi, Twilio, Stripe writes, "
    "Google Calendar, Gmail · todos quedan para T2.1.C+.",
    "<b>Browser Operator · Playbook Engine v2 · automatizaciones "
    "externas</b> · explícitamente excluidos por el spec.",
    "<b>Endpoint admin HTTP</b> para listar/crear acciones · "
    "T2.1.B incluye <i>/admin/automation/*</i>.",
]))

# ── 11. Siguiente PR recomendado ──────────────────────────────────────

story.append(H1("11. Siguiente PR recomendado · T2.1.B"))

story.append(P(
    "<b>T2.1.B · Action Center dashboard + endpoints HTTP</b>:"
))

story.extend(bullets([
    "Backend: endpoints admin <i>/admin/automation/oportunidades · "
    "/admin/automation/acciones · POST aprobar/rechazar</i> "
    "(autenticados con ADMIN_TOKEN existente).",
    "Landing: endpoint proxy <i>/api/automation/acciones</i> con "
    "auth() server-side y bridge HMAC al backend (patrón T1.4.D).",
    "Frontend: componente <i>SeccionActionCenter</i> en el dashboard "
    "(estados pending/needs_approval/completed) · botones "
    "aprobar/rechazar para MEDIUM · estado en vivo · resultados "
    "renderizados (markdown cuando aplique).",
    "Tests: vitest del componente · pytest del endpoint admin · "
    "regresión.",
]))

story.append(P(
    "Después: T2.1.C (ejecutores reales con guardrails) y T2.1.D "
    "(reservas créditos · pruning audit · métricas)."
))

# ── 12. Datos para abrir el PR ────────────────────────────────────────

story.append(H1("12. Datos para abrir el PR"))

story.append(make_table([
    ["Campo", "Valor"],
    ["URL",
     "github.com/celestinojbm/Dona-agent/pull/new/<br/>"
     "pr/t2.1-automation-core"],
    ["Título sugerido",
     "feat(automation) · Dona Automation Core · T2.1.A backend"],
    ["Base", "main"],
    ["Head", "pr/t2.1-automation-core"],
    ["Body markdown",
     "Generado abajo · listo para copiar/pegar"],
], col_widths=[1.6*inch, 5.0*inch]))

# ── 13. Body markdown ────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("13. Body markdown del PR (copy-paste)"))

story.append(CODE(
    "## Resumen\n"
    "\n"
    "Núcleo backend del sistema completo de automatización de Dona\n"
    "(T2.1.A). Implementa el pipeline real diagnóstico → oportunidades\n"
    "→ playbooks → acciones → permisos → ejecución controlada → audit.\n"
    "Cero MVP débil: 7 componentes fundacionales, idempotencia, audit\n"
    "log sanitizado, bloqueo estricto de CRITICAL, ejecutores internos\n"
    "dry-run sin efecto externo. Lista para que T2.1.B agregue UI y\n"
    "T2.1.C conecte ejecutores reales.\n"
    "\n"
    "## Cambios\n"
    "\n"
    "Nuevos:\n"
    "- agent/automation/__init__.py + 8 submódulos\n"
    "- 2 modelos DB: AccionAutomatizacion + AuditLogAutomatizacion\n"
    "- MIGRACIONES_AUTOMATION (PostgreSQL idempotente)\n"
    "- 7 archivos de tests (107 tests pytest)\n"
    "Modificado:\n"
    "- agent/memory.py · concatena MIGRACIONES_AUTOMATION en\n"
    "  _migrar_columnas() (5 líneas)\n"
    "\n"
    "## Componentes\n"
    "\n"
    "1. Permission & Risk · NivelRiesgo (low/medium/high/critical) +\n"
    "   reglas de auto-ejecución + transiciones de estado + bloqueo\n"
    "   estricto CRITICAL en T2.1.A.\n"
    "2. Costos · estimación determinística por tipo · suma de pasos\n"
    "   por playbook · NO descuenta.\n"
    "3. Playbooks · 6 fundacionales: diagnostico_a_plan_semanal,\n"
    "   calendario_contenido_7d, reactivacion_clientes, mejora_oferta,\n"
    "   campana_whatsapp_simple, checklist_ventas.\n"
    "4. Opportunity Engine · 6 reglas determinísticas que leen\n"
    "   perfil_negocio (T2.0.E.1). Cada oportunidad incluye razón,\n"
    "   prioridad, impacto, riesgo, fuente_datos, playbook_sugerido.\n"
    "5. Audit log · whitelist de eventos + sanitizador anti-PII\n"
    "   (descarta telefono, email, password, secrets, customer_id\n"
    "   completos, y los 6 campos de texto libre del onboarding\n"
    "   extendido).\n"
    "6. Action Center · CRUD con idempotency_key sha256(tel|tipo|\n"
    "   playbook|opp|fecha) · transiciones validadas · audit en cada\n"
    "   cambio.\n"
    "7. Execution · 10 ejecutores internos dry-run · CRITICAL siempre\n"
    "   bloqueado · MEDIUM/HIGH requieren aprobación · LOW auto-\n"
    "   ejecuta · errores sanitizados (sin stack traces).\n"
    "\n"
    "## Tests\n"
    "\n"
    "- pytest tests/test_automation_*.py · 107/107 passing · 52s\n"
    "- pytest suite completa · 769/769 passing · 296s · cero\n"
    "  regresiones sobre los 662 tests previos\n"
    "\n"
    "Tests específicos verifican:\n"
    "- LOW pending ejecuta automático\n"
    "- MEDIUM/HIGH sin aprobación fallan con error claro\n"
    "- CRITICAL siempre bloqueado · genera audit\n"
    "  action_blocked_critical\n"
    "- HIGH aprobado pero sin ejecutor T2.1.A falla con mensaje\n"
    "  apuntando a futuro PR\n"
    "- Ejecutores internos NO contienen referencias a Whapi/Twilio/\n"
    "  Stripe/providers\n"
    "- Sanitizador NO deja PII en payload_summary\n"
    "- registrar_evento NO loguea PII en stdout\n"
    "- Idempotency key evita duplicar misma acción del día\n"
    "\n"
    "## Cero writes\n"
    "\n"
    "- Sin Stripe writes · sin DB writes prod · sin env changes\n"
    "- Sin deploys · sin envíos reales WhatsApp/email\n"
    "- Sin publicaciones reales · sin mensajes masivos\n"
    "- Sin secretos en chat · sin PII en logs\n"
    "\n"
    "## Out of scope\n"
    "\n"
    "- Dashboard UI (T2.1.B)\n"
    "- Endpoints HTTP (T2.1.B)\n"
    "- Ejecutores reales (T2.1.C)\n"
    "- Reservas/reembolsos créditos (T2.1.D)\n"
    "- Browser Operator · Playbook Engine v2 · automatizaciones\n"
    "  externas (excluidos por spec)\n"
    "\n"
    "## Plan post-merge\n"
    "\n"
    "1. Render auto-redeploy ~2 min · _migrar_columnas crea las 2\n"
    "   tablas nuevas en Postgres prod.\n"
    "2. Smoke admin · ningún endpoint HTTP nuevo expuesto en T2.1.A.\n"
    "3. Las APIs Python están listas para que T2.1.B las conecte a\n"
    "   endpoints + UI.\n"
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
