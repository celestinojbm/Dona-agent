"""
Genera Resumen_T21D_Creditos_Reservas_Pruning_2026-05-06.pdf · cierre
del bloque T2.1.D · reservas de créditos, descuento real, audit log
extendido y pruning seguro · sin deploy ni cambios externos.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = (
    r"C:\Users\celes\Dona-agent\docs\auditorias"
    r"\Resumen_T21D_Creditos_Reservas_Pruning_2026-05-06.pdf"
)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleBig", parent=styles["Title"],
    fontSize=20, leading=24, spaceAfter=8,
    textColor=colors.HexColor("#111111")))
styles.add(ParagraphStyle(name="MetaTop", parent=styles["Normal"],
    fontSize=9, leading=12, textColor=colors.HexColor("#555555"),
    spaceAfter=18))
styles.add(ParagraphStyle(name="Banner", parent=styles["Normal"],
    fontSize=10, leading=14, textColor=colors.HexColor("#065f46"),
    backColor=colors.HexColor("#ecfdf5"), borderPadding=8,
    borderColor=colors.HexColor("#10b981"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14))
styles.add(ParagraphStyle(name="WarnBanner", parent=styles["Normal"],
    fontSize=10, leading=14, textColor=colors.HexColor("#7c2d12"),
    backColor=colors.HexColor("#fff7ed"), borderPadding=8,
    borderColor=colors.HexColor("#f97316"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14))
styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"],
    fontSize=15, leading=19, spaceBefore=16, spaceAfter=6,
    textColor=colors.HexColor("#111111")))
styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"],
    fontSize=12, leading=16, spaceBefore=12, spaceAfter=4,
    textColor=colors.HexColor("#1f2937")))
styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"],
    fontSize=9.5, leading=13, alignment=TA_JUSTIFY, spaceAfter=6,
    textColor=colors.HexColor("#222222")))
styles.add(ParagraphStyle(name="Caption", parent=styles["Body"],
    fontSize=8.5, leading=11,
    textColor=colors.HexColor("#6b7280"), spaceAfter=10))
styles.add(ParagraphStyle(name="CodeBox", parent=styles["Code"],
    fontSize=8, leading=10, textColor=colors.HexColor("#111111"),
    backColor=colors.HexColor("#f5f5f5"), borderPadding=6,
    borderColor=colors.HexColor("#e5e7eb"), borderWidth=0.4,
    leftIndent=4, rightIndent=4, spaceBefore=6, spaceAfter=10))
styles.add(ParagraphStyle(name="BulletDona", parent=styles["Body"],
    leftIndent=14, bulletIndent=2, spaceAfter=2))


def H1(t): return Paragraph(t, styles["H1"])
def H2(t): return Paragraph(t, styles["H2"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(
    t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])
def BANNER(t): return Paragraph(t, styles["Banner"])
def WARN(t): return Paragraph(t, styles["WarnBanner"])


def bullets(items):
    return [Paragraph("&bull; " + it, styles["BulletDona"])
            for it in items]


def make_table(rows, col_widths=None, header=True):
    tbl = Table(rows, colWidths=col_widths, hAlign="LEFT")
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#d1d5db")),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6,
         colors.HexColor("#d1d5db")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4,
         colors.HexColor("#9ca3af")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
        style.append(("BACKGROUND", (0, 0), (-1, 0),
                      colors.HexColor("#f3f4f6")))
    tbl.setStyle(TableStyle(style))
    return tbl


story = []

story.append(Paragraph(
    "T2.1.D · Reservas de créditos, descuento real, audit log "
    "extendido y pruning seguro",
    styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-06 · branch "
    "<i>pr/t2.1.d-credit-reservations-audit-pruning</i> · cambios "
    "mínimos · sin deploy · sin cambios externos · sin borrado de "
    "datos productivos.",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Resumen ejecutivo:</b> el ejecutor de acciones del Action "
    "Center ahora reserva créditos al iniciar la ejecución, los "
    "descuenta del saldo del usuario, libera (reembolsa) si la "
    "ejecución falla y confirma si tiene éxito. Todo el flujo es "
    "idempotente: re-llamar <i>reservar()</i> para el mismo "
    "<i>accion_id</i> NO duplica el cobro. Se sumaron 6 eventos al "
    "audit log (whitelist) y se añadió un módulo de <i>pruning</i> "
    "con <b>dry-run por defecto</b>, <i>max_delete</i> tope y "
    "validación de antigüedad mínima (30 días acciones, 90 días "
    "audit). Endpoints admin: <i>GET&nbsp;/admin/automation/prune/"
    "preview</i> y <i>POST&nbsp;/admin/automation/prune</i> "
    "(requiere <i>confirm=BORRAR</i>)."
))

# ── 1. Causa y diseño ───────────────────────────────────────────────────

story.append(H1("1. Causa y diseño"))

story.append(H2("1.1 Problema que resuelve"))
story.append(P(
    "T2.1.A introdujo el motor de ejecución del Action Center. "
    "T2.1.B sumó dashboard y endpoints. T2.1.C conectó ejecutores "
    "reales con LLM y fallback determinístico. Pero hasta T2.1.C la "
    "ejecución NO descontaba créditos: el costo se estimaba "
    "(<i>agent.automation.costos.estimar_costo_accion</i>) pero "
    "nunca se cobraba. Además el audit log no registraba ni "
    "reservas ni bloqueos por saldo, y no había forma segura de "
    "limpiar tablas viejas. T2.1.D cierra estas tres brechas."))

story.append(H2("1.2 Decisión de diseño · cobrar al crear / reembolsar si falla"))
story.append(P(
    "Se evaluaron dos alternativas: <b>(a) lockear saldo</b> "
    "(crear una fila “hold” sin descontar y consolidar al final) "
    "vs <b>(b) cobrar y reembolsar</b>. Se eligió (b) porque "
    "<i>agent.billing.cobrar()</i> ya implementa el descuento "
    "atómico con CAS (compare-and-set) anti-race y "
    "<i>acreditar()</i> deja audit-trail en "
    "<i>transacciones_credito</i>. Lockear duplicaría lógica de "
    "concurrencia y rompería el invariante \"saldo entero "
    "consistente con suma de transacciones\". El reembolso queda "
    "registrado como <i>credit_reservation_release</i> en la misma "
    "tabla, manteniendo un único punto de verdad."))

story.append(H2("1.3 Idempotencia · estado-máquina + UNIQUE(accion_id)"))
story.append(P(
    "Cada ejecución tiene exactamente una fila en "
    "<i>automation_reservas_credito</i> con UNIQUE(accion_id). El "
    "estado es una máquina finita:"))

story.append(make_table([
    ["Estado", "Trigger", "Efecto en saldo", "Terminal"],
    ["pending", "reservar() exitoso", "descuenta créditos",
     "No"],
    ["confirmed", "confirmar() tras ejecución OK", "—", "Sí"],
    ["released", "liberar() tras error / bloqueo",
     "acredita créditos", "Sí"],
    ["failed", "reservar() con saldo insuficiente", "—", "Sí"],
], col_widths=[1.0*inch, 2.4*inch, 1.7*inch, 0.7*inch]))

story.append(P(
    "Re-llamar <i>reservar(accion_id=42)</i> con una fila "
    "<i>pending</i> existente retorna la fila tal cual, sin invocar "
    "<i>billing.cobrar()</i> de nuevo. Igual para <i>confirmar()</i> "
    "sobre una fila ya <i>confirmed</i>: noop. Por eso el reintento "
    "del worker (que es esperable) NO genera doble cobro."))

# ── 2. Archivos modificados ────────────────────────────────────────────

story.append(H1("2. Archivos modificados y creados"))

story.append(make_table([
    ["Archivo", "Tipo", "Resumen"],
    ["agent/automation/credits.py", "NUEVO ~280 ln",
     "API <i>reservar / confirmar / liberar / obtener_reserva</i>. "
     "Excepción <i>CreditosInsuficientesError</i>. Emite eventos "
     "<i>credits_reserved / confirmed / released / "
     "reservation_failed</i>."],
    ["agent/automation/models.py", "MODIFICADO",
     "Modelo <i>ReservaCreditoAutomation</i> + 4 entradas en "
     "<i>MIGRACIONES_AUTOMATION</i> (CREATE TABLE + 3 índices: "
     "accion_id UNIQUE, telefono, estado)."],
    ["agent/automation/audit.py", "MODIFICADO",
     "<i>EVENTOS_VALIDOS</i> extendido con 6 eventos: "
     "credits_reserved · credits_confirmed · credits_released · "
     "credits_reservation_failed · "
     "action_blocked_insufficient_credits · pruning_executed."],
    ["agent/automation/execution.py", "MODIFICADO",
     "<i>ejecutar_accion()</i> ahora: reserva → marca_running → "
     "ejecuta → confirma (éxito) o libera (CRITICAL bloqueado, "
     "HIGH sin ejecutor, excepción)."],
    ["agent/automation/pruning.py", "NUEVO ~250 ln",
     "<i>pruning_acciones · pruning_reservas · "
     "pruning_audit_log</i>. dry_run por defecto, "
     "<i>ejecutar_borrado=True</i> requerido, "
     "<i>max_delete</i> 1..10000, dias mínimo 30 (acciones / "
     "reservas) o 90 (audit). Sólo borra estados terminales."],
    ["agent/main.py", "MODIFICADO",
     "Endpoints admin: <b>GET /admin/automation/prune/preview</b> "
     "(dry-run counts) y <b>POST /admin/automation/prune</b> "
     "(requiere <i>confirm=BORRAR</i>, valida "
     "<i>tabla&isin;{all,acciones,reservas,audit_log}</i>)."],
    ["tests/test_automation_creditos_reservas.py", "NUEVO 19 tests",
     "Cobertura de reserva directa, idempotencia, "
     "confirmar/liberar, ejecución integrada (incl. CRITICAL "
     "bloqueado, HIGH sin ejecutor, excepción) y audit extendido."],
    ["tests/test_automation_pruning.py", "NUEVO 13 tests",
     "Cobertura de dry-run, ejecución, anti-borrado-corto, "
     "no borra in-flight ni recientes, emite "
     "<i>pruning_executed</i>."],
    ["tests/test_automation_execution.py", "MODIFICADO",
     "Fixture <i>monkeypatch</i> de "
     "<i>estimar_costo_accion → 0</i> antes y después del reload, "
     "para preservar el alcance de los tests legacy de T2.1.A "
     "(que no siembran saldo)."],
    ["tests/test_automation_executors_real.py", "MODIFICADO",
     "Mismo monkeypatch que arriba (T2.1.C legacy)."],
    ["tests/test_automation_endpoints.py", "MODIFICADO",
     "Mismo monkeypatch que arriba (T2.1.B legacy)."],
], col_widths=[2.5*inch, 1.0*inch, 3.3*inch]))

# ── 3. Migración de datos ──────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Migración de datos"))

story.append(P(
    "Se sumaron 4 entradas a <i>MIGRACIONES_AUTOMATION</i> en "
    "<i>agent/automation/models.py</i>. El motor de migraciones de "
    "Dona (lista <i>_MIGRACIONES</i> en runtime, no Alembic) "
    "evalúa cada sentencia con <i>IF NOT EXISTS</i>, lo que las "
    "hace idempotentes en reentrega y compatibles con SQLite "
    "(tests) y Postgres (prod)."))

story.append(CODE(
    "-- automation_reservas_credito\n"
    "CREATE TABLE IF NOT EXISTS automation_reservas_credito (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  accion_id INTEGER NOT NULL UNIQUE,\n"
    "  telefono VARCHAR(50) NOT NULL,\n"
    "  creditos INTEGER NOT NULL,\n"
    "  estado VARCHAR(20) NOT NULL DEFAULT 'pending',\n"
    "  razon TEXT NOT NULL DEFAULT '',\n"
    "  transaccion_credito_id INTEGER,\n"
    "  creado DATETIME NOT NULL,\n"
    "  actualizado DATETIME NOT NULL\n"
    ");\n"
    "CREATE UNIQUE INDEX IF NOT EXISTS\n"
    "  ix_automation_reservas_credito_accion_id\n"
    "  ON automation_reservas_credito(accion_id);\n"
    "CREATE INDEX IF NOT EXISTS\n"
    "  ix_automation_reservas_credito_telefono\n"
    "  ON automation_reservas_credito(telefono);\n"
    "CREATE INDEX IF NOT EXISTS\n"
    "  ix_automation_reservas_credito_estado\n"
    "  ON automation_reservas_credito(estado);"
))

# ── 4. Anti doble cobro ────────────────────────────────────────────────

story.append(H1("4. Anti doble cobro · evidencia"))

story.append(P(
    "Tres capas de defensa contra el doble cobro:"))

story.append(make_table([
    ["Capa", "Mecanismo", "Test que lo valida"],
    ["DB", "UNIQUE constraint sobre <i>accion_id</i>",
     "test_no_duplica_cobro_si_se_llama_dos_veces"],
    ["App", "reservar() chequea fila existente antes de cobrar",
     "test_re_ejecutar_no_doble_cobra"],
    ["Audit", "evento <i>credits_reserved</i> sólo se emite cuando "
     "el cobro ocurre realmente",
     "test_reserva_emite_eventos_audit"],
], col_widths=[0.8*inch, 3.2*inch, 2.8*inch]))

story.append(P(
    "Adicional: si la ejecución falla (excepción, CRITICAL "
    "bloqueado o HIGH sin ejecutor), <i>liberar()</i> reembolsa con "
    "<i>billing.acreditar()</i> y marca la fila como "
    "<i>released</i>. El reembolso emite "
    "<i>credits_released</i> en audit, dejando trazabilidad "
    "completa: cobro → reembolso, ambos vinculados al mismo "
    "<i>accion_id</i>."))

# ── 5. Audit log extendido ─────────────────────────────────────────────

story.append(H1("5. Audit log extendido"))

story.append(P(
    "Se añadieron 6 eventos a la whitelist <i>EVENTOS_VALIDOS</i>:"))

story.append(make_table([
    ["Evento", "Cuándo se emite", "Carga útil resumen"],
    ["credits_reserved", "reservar() exitoso",
     "tipo · creditos · accion_id"],
    ["credits_confirmed", "confirmar() tras ejecución OK",
     "tipo · creditos · accion_id"],
    ["credits_released", "liberar() tras error o bloqueo",
     "tipo · creditos · accion_id · razon"],
    ["credits_reservation_failed", "saldo insuficiente en reservar()",
     "tipo · requerido · saldo · accion_id"],
    ["action_blocked_insufficient_credits",
     "ejecutar_accion() abortado por reservar() fallida",
     "tipo · accion_id"],
    ["pruning_executed", "pruning ejecutado (no dry-run)",
     "tabla · borradas · dias · ts_inicio · ts_fin"],
], col_widths=[2.1*inch, 2.4*inch, 2.3*inch]))

story.append(P(
    "Todos los eventos pasan por <i>audit.registrar()</i> que "
    "trunca <i>telefono</i> a <i>***últimos4</i> y serializa "
    "<i>payload_summary</i> con saneado (sin secrets ni PII de "
    "contacto). Test <i>test_evento_no_filtra_pii</i> valida que "
    "no aparezca el teléfono completo en los payloads."))

# ── 6. Comandos ejecutados ─────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("6. Verificaciones · comandos y resultados"))

story.append(H2("6.1 Tests específicos T2.1.D"))
story.append(CODE(
    "pytest tests/test_automation_creditos_reservas.py -v\n"
    "→ 19 passed in 14.89s\n\n"
    "pytest tests/test_automation_pruning.py -v\n"
    "→ 13 passed in 9.53s"
))

story.append(H2("6.2 Tests automation completos (sin regresión)"))
story.append(CODE(
    "pytest tests/test_automation_*.py\n"
    "→ 197 passed in 107.51s"
))

story.append(H2("6.3 Suite completa del repo"))
story.append(CODE(
    "pytest\n"
    "→ 859 passed in 221.80s"
))

story.append(BANNER(
    "<b>0 failed · 0 regresión.</b> Los warnings restantes son "
    "<i>PytestUnhandledThreadExceptionWarning</i> del cleanup de "
    "aiosqlite (event-loop closed), ya presentes en main y "
    "ortogonales a T2.1.D."
))

# ── 7. Riesgos ─────────────────────────────────────────────────────────

story.append(H1("7. Riesgos residuales y mitigaciones"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Crash entre <i>billing.cobrar()</i> y INSERT en "
     "reservas_credito (descuento sin fila)",
     "Bajo",
     "Crash en ese microintervalo deja saldo descontado pero "
     "sin reserva visible. El admin puede acreditar manualmente "
     "via <i>/admin/seed-creditos</i>. Probabilidad real ≈ 0 en "
     "instancia única."],
    ["Worker reintenta ejecutar_accion() tras éxito ya confirmado",
     "Bajo",
     "<i>confirmar()</i> sobre fila <i>confirmed</i> es noop · no "
     "re-emite audit ni re-toca saldo."],
    ["Pruning borra más de lo esperado",
     "Medio",
     "dry-run por defecto, <i>ejecutar_borrado=True</i> requerido "
     "explícitamente, <i>max_delete</i> tope ≤ 10000, dias mínimo "
     "30 (acciones) y 90 (audit). Endpoint POST requiere "
     "<i>confirm=BORRAR</i> literal."],
    ["Cambios de schema en prod (PG) al primer redeploy",
     "Bajo",
     "<i>CREATE TABLE IF NOT EXISTS</i> idempotente. La tabla "
     "nueva no afecta a usuarios existentes."],
    ["Latencia adicional por <i>cobrar()</i> en cada ejecución",
     "Bajo",
     "Un INSERT + UPDATE atómicos (~5-10ms PG). Acciones del "
     "Action Center se procesan async, no bloquean WhatsApp."],
], col_widths=[2.7*inch, 0.8*inch, 3.3*inch]))

# ── 8. Instrucciones de PR ─────────────────────────────────────────────

story.append(H1("8. Instrucciones de PR"))

story.append(P(
    "<b>Branch:</b> <i>pr/t2.1.d-credit-reservations-audit-pruning</i>"))
story.append(P(
    "<b>Título:</b> <i>feat(automation): add credit reservations, "
    "real deduction, audit logs and pruning</i>"))

story.append(P("<b>Cuerpo sugerido:</b>"))

story.append(CODE(
    "## Resumen\n"
    "T2.1.D cierra el flujo de billing real para el Action Center:\n"
    "  · reserva atómica con cobro inmediato y refund automático\n"
    "  · 6 nuevos eventos en audit log (whitelist)\n"
    "  · módulo pruning seguro (dry-run default, dias min, max-cap)\n"
    "  · 2 endpoints admin (preview + execute con confirm=BORRAR)\n\n"
    "## Cambios\n"
    "  · NUEVO  agent/automation/credits.py (~280 ln)\n"
    "  · NUEVO  agent/automation/pruning.py (~250 ln)\n"
    "  · MOD    agent/automation/models.py (+modelo +4 migraciones)\n"
    "  · MOD    agent/automation/audit.py (+6 eventos)\n"
    "  · MOD    agent/automation/execution.py (reserva/confirma/libera)\n"
    "  · MOD    agent/main.py (+2 endpoints admin)\n"
    "  · NUEVO  tests/test_automation_creditos_reservas.py (19)\n"
    "  · NUEVO  tests/test_automation_pruning.py (13)\n"
    "  · MOD    3 fixtures de tests legacy con monkeypatch costo=0\n\n"
    "## Verificaciones\n"
    "  · pytest                          859 passed\n"
    "  · pytest tests/test_automation_*  197 passed\n"
    "  · sin deploy · sin cambios externos · sin borrado prod\n\n"
    "## Guardrails preservados\n"
    "  · CRITICAL sigue bloqueado y libera reserva\n"
    "  · MEDIUM/HIGH requieren aprobación\n"
    "  · anti-IDOR intacto en endpoints admin (Bearer token)\n"
    "  · audit log con telefono truncado y payload sanitizado\n"
))

# ── 9. Próximo paso ────────────────────────────────────────────────────

story.append(H1("9. Próximo paso recomendado"))

story.append(P(
    "Con T2.1.D cerrado, el motor de automation tiene billing "
    "real, audit completo y mantenimiento operativo. El siguiente "
    "bloque natural es <b>T2.1.E · scheduler periódico</b> "
    "(cron-like) para detectar oportunidades de "
    "acción de forma proactiva, o bien <b>T2.2 · primera acción "
    "HIGH real</b> (e.g. enviar_mensaje_whatsapp con conexión a "
    "Whapi en preview-then-commit). La decisión depende de cuánto "
    "tráfico orgánico estamos viendo en el Action Center vs cuánto "
    "necesitamos demostrar valor de envío real."))

doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
)
doc.build(story)
print(f"OK · escrito {OUTPUT}")
