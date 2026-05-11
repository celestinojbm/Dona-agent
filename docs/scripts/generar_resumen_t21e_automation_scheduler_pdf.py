"""
Genera Resumen_T21E_Automation_Scheduler_2026-05-11.pdf · entrega del
bloque T2.1.E · scheduler periódico de mantenimiento que reconcilia
reservas de créditos en estado 'preparing' como safety net.
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
    r"\Resumen_T21E_Automation_Scheduler_2026-05-11.pdf"
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
    "T2.1.E · Scheduler periódico de reconciliación de reservas",
    styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-11 · branch "
    "<i>pr/t2.1.e-automation-scheduler-reconciliation</i> · "
    "<b>commit local · sin push · sin PR · sin deploy</b>.",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Resumen ejecutivo:</b> el Automation Core ya cuenta con un "
    "scheduler periódico opt-in que llama <i>reconciliar_reservas()</i> "
    "cada <i>N</i> segundos (default 300). Por default está "
    "<b>deshabilitado</b> (requiere "
    "<i>AUTOMATION_SCHEDULER_ENABLED=true</i>). Se monta sobre el "
    "AsyncIOScheduler ya existente · no introduce nueva "
    "dependencia. Tiene anti-concurrencia doble (lock + "
    "<i>max_instances=1</i>) y manejo de excepciones que no rompe el "
    "loop. <b>Suite completa 881 tests OK · +14 nuevos · 0 "
    "regresión.</b>"
))

# ── 1. Diseño ────────────────────────────────────────────────────────

story.append(H1("1. Diseño · qué hace y cómo"))

story.append(H2("1.1 Misión del scheduler"))
story.append(P(
    "El fix T2.1.D.1 mitigó el riesgo de saldo descontado sin "
    "reserva visible mediante write-ahead + reconciliación inline en "
    "<i>reservar()</i>. El caso residual era: <b>worker que NO "
    "reintenta la acción</b> tras un crash. Hasta T2.1.E la "
    "reconciliación quedaba dependiendo de un admin manual. Ahora "
    "corre sola en intervalos configurables."))

story.append(H2("1.2 Componentes"))

story.append(make_table([
    ["Componente", "Responsabilidad"],
    ["agent/automation/scheduler.py",
     "Helpers de env, tick de trabajo con lock + try/except, "
     "<i>registrar_automation_jobs()</i> para montar el job sobre "
     "APScheduler, <i>obtener_estado()</i> para diagnóstico."],
    ["agent/scheduler.py",
     "Llama <i>registrar_automation_jobs(scheduler)</i> antes de "
     "<i>scheduler.start()</i>. Si la llamada lanza, se loguea y se "
     "sigue (el resto del scheduler no se ve afectado)."],
    ["agent/main.py",
     "Expone <i>GET /admin/automation/scheduler/status</i> · solo "
     "lectura · <i>_verificar_admin</i> con HMAC."],
    ["tests/test_automation_scheduler.py",
     "14 tests · cubren env vars, parámetros del tick, manejo de "
     "excepciones, lock anti-concurrencia, registro condicional y "
     "smoke end-to-end."],
], col_widths=[2.3*inch, 4.7*inch]))

story.append(H2("1.3 Flujo de un tick"))

story.append(CODE(
    "async def tick_reconciliacion_reservas():\n"
    "    if _lock.locked():                 # ← anti-concurrencia\n"
    "        _estado['corridas_saltadas_por_lock'] += 1\n"
    "        return {'status': 'skipped_lock'}\n"
    "    async with _lock:\n"
    "        try:\n"
    "            resultado = await reconciliar_reservas(\n"
    "                max_edad_segundos=edad_min_segundos(),\n"
    "                limit=limit_corrida(),\n"
    "                dry_run=False,\n"
    "            )\n"
    "            _estado['corridas_totales'] += 1\n"
    "            _estado['ultimo_resultado'] = resultado\n"
    "            return {'status': 'ok', 'resultado': resultado}\n"
    "        except Exception as e:         # ← nunca propaga\n"
    "            _estado['corridas_fallidas'] += 1\n"
    "            logger.error(...)\n"
    "            return {'status': 'error', 'error': type(e).__name__}"
))

# ── 2. Variables de entorno ──────────────────────────────────────────

story.append(H1("2. Variables de entorno"))

story.append(make_table([
    ["Variable", "Default", "Rango", "Significado"],
    ["AUTOMATION_SCHEDULER_ENABLED", "<b>false</b>",
     "1/true/yes/on (case-insensitive)",
     "Master switch · OFF por default · prod opta in explícito."],
    ["AUTOMATION_SCHEDULER_INTERVAL_SECONDS", "300",
     "30 ≤ N ≤ 3600 · clamped",
     "Frecuencia del tick."],
    ["AUTOMATION_SCHEDULER_RECONCILE_EDAD_SEGUNDOS", "120",
     "N ≥ 30",
     "Edad mínima para marcar <i>preparing</i> como <i>failed</i>."],
    ["AUTOMATION_SCHEDULER_RECONCILE_LIMIT", "500",
     "1 ≤ N ≤ 5000 · clamped",
     "Tope de filas procesadas por tick."],
], col_widths=[2.7*inch, 0.7*inch, 1.5*inch, 2.1*inch]))

story.append(BANNER(
    "<b>No se tocaron variables de entorno en Render.</b> Producción "
    "sigue con default OFF hasta que el owner agregue la env var. El "
    "checklist de smoke test producción (T2.1.D verificación post-"
    "merge §7) sigue siendo el siguiente paso obligatorio antes de "
    "activarlo en prod."
))

# ── 3. Archivos modificados ──────────────────────────────────────────

story.append(H1("3. Archivos modificados / creados"))

story.append(make_table([
    ["Archivo", "Tipo", "Resumen"],
    ["agent/automation/scheduler.py", "NUEVO ~190 ln",
     "Módulo completo · helpers de env, tick, registro, estado."],
    ["agent/scheduler.py", "MOD ~12 ln",
     "Bloque <i>try/except</i> dentro de <i>iniciar_scheduler()</i> "
     "que llama <i>registrar_automation_jobs(scheduler)</i> antes de "
     "<i>scheduler.start()</i>. Aislado · no toca jobs existentes."],
    ["agent/main.py", "MOD ~15 ln",
     "Endpoint <i>GET /admin/automation/scheduler/status</i> · "
     "protegido con <i>_verificar_admin</i> · solo lectura."],
    ["tests/test_automation_scheduler.py", "NUEVO 14 tests",
     "<i>TestEnvConfig</i> (5) · <i>TestTickLlamaReconciliar</i> (2) "
     "· <i>TestTickManejoDeExcepcion</i> (2) · "
     "<i>TestLockNoConcurrencia</i> (1) · "
     "<i>TestRegistrarAutomationJobs</i> (3) · "
     "<i>TestIntegracionTickRealReconciliar</i> (1)."],
], col_widths=[2.5*inch, 1.1*inch, 3.4*inch]))

story.append(P(
    "<b>Sin nuevas migraciones de schema.</b> El scheduler no "
    "introduce tablas ni columnas · sólo consume "
    "<i>reconciliar_reservas()</i> ya disponible desde T2.1.D.1."))

# ── 4. Riesgos y mitigaciones ────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Riesgos y mitigaciones"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Activar el scheduler en prod sin verificar el smoke",
     "Bajo",
     "Default OFF. El owner debe agregar la env var en Render para "
     "encenderlo · cambio reversible sin código."],
    ["Tick toma demasiado y se bloquean otros jobs",
     "Bajo",
     "<i>reconciliar_reservas()</i> respeta <i>limit</i> (default "
     "500) · cada operación es lectura + UPDATE puntual · no "
     "compite por locks. Si tarda más que el intervalo, APScheduler "
     "lo coalesce y un solo tick siguiente cubre el backlog."],
    ["Dos ticks simultáneos (replicas o reintento de APS)",
     "Bajo",
     "Doble defensa: APScheduler <i>max_instances=1</i> + "
     "<i>asyncio.Lock</i> en proceso. Test "
     "<i>test_segundo_tick_concurrente_se_salta</i> lo valida."],
    ["Excepción del tick rompe el scheduler",
     "Muy bajo",
     "Todo el cuerpo del tick está en <i>try/except Exception</i>. "
     "Test <i>test_excepcion_no_propaga_y_cuenta_fallidas</i> + "
     "<i>test_tick_siguiente_corre_tras_fallo</i> lo validan."],
    ["Registro del job tumba el startup del web service",
     "Muy bajo",
     "<i>registrar_automation_jobs()</i> está envuelto en "
     "<i>try/except</i>. Si la env var es inválida o APScheduler "
     "rechaza el job, se loguea y retorna False · el resto del "
     "scheduler arranca normal. Test "
     "<i>test_no_propaga_excepcion_si_add_job_falla</i> lo valida."],
    ["Logs filtran PII (teléfonos, ids)",
     "Muy bajo",
     "El tick solo loguea conteos (<i>promoted</i>, "
     "<i>marked_failed</i>, <i>intactas</i>). Los audit events de "
     "<i>reconciliar_accion()</i> ya pasan por "
     "<i>sanitizar_payload</i> y trunca el teléfono."],
], col_widths=[2.4*inch, 0.8*inch, 3.8*inch]))

# ── 5. Verificaciones · comandos y resultado ─────────────────────────

story.append(H1("5. Verificaciones · comandos y resultado"))

story.append(CODE(
    "pytest tests/test_automation_scheduler.py -v\n"
    "→ 14 passed in 10.14s\n\n"
    "pytest tests/test_automation_*.py\n"
    "→ 219 passed in (suite automation, incluye 14 nuevos)\n\n"
    "pytest\n"
    "→ 881 passed in 237.12s · +14 vs main · 0 failed · 0 regresión"
))

# ── 6. Cómo validar localmente ───────────────────────────────────────

story.append(H1("6. Cómo validar localmente"))

story.append(H2("6.1 Sin tocar prod · ejecutar la suite"))
story.append(CODE(
    "git checkout pr/t2.1.e-automation-scheduler-reconciliation\n"
    "pytest tests/test_automation_scheduler.py -v\n"
    "pytest                                # suite completa"
))

story.append(H2("6.2 Smoke manual del scheduler en dev (opt-in)"))
story.append(P(
    "Solo si quieres ver el scheduler corriendo realmente · "
    "<b>en local · NO en prod</b>:"))
story.append(CODE(
    "# Terminal · arrancar Dona con el scheduler activo\n"
    "set AUTOMATION_SCHEDULER_ENABLED=true\n"
    "set AUTOMATION_SCHEDULER_INTERVAL_SECONDS=30\n"
    "uvicorn agent.main:app --reload --port 8080\n\n"
    "# En otro terminal · esperar 1 minuto · luego consultar estado\n"
    "curl -s -H \"Authorization: Bearer $ADMIN_TOKEN\" \\\n"
    "     http://localhost:8080/admin/automation/scheduler/status\n"
    "→ {\n"
    "    \"habilitado\": true,\n"
    "    \"intervalo_segundos\": 30,\n"
    "    \"corridas_totales\": 2,\n"
    "    \"corridas_saltadas_por_lock\": 0,\n"
    "    \"corridas_fallidas\": 0,\n"
    "    \"ultima_corrida_inicio\": \"2026-05-11T...\",\n"
    "    \"ultimo_resultado\": {\n"
    "        \"dry_run\": false,\n"
    "        \"total_preparing_inicial\": 0,\n"
    "        \"promoted\": 0,\n"
    "        \"marked_failed\": 0,\n"
    "        \"intactas\": 0\n"
    "    }\n"
    "  }"
))

story.append(H2("6.3 Verificar logs"))
story.append(CODE(
    "# Esperado en stdout del uvicorn:\n"
    "[AUT-SCHED] reconciliación registrada · intervalo=30s · "
    "max_edad=120s · limit=500\n"
    "[AUT-SCHED] reconciliación OK · intactas=0     # cada tick"
))

# ── 7. Estado git ────────────────────────────────────────────────────

story.append(H1("7. Estado git"))

story.append(make_table([
    ["Item", "Valor"],
    ["Branch", "<i>pr/t2.1.e-automation-scheduler-reconciliation</i>"],
    ["Base", "<i>main</i> · sincronizada antes del branch "
     "(commit <i>f4f258e</i>)"],
    ["Commit en branch", "Por crear · "
     "<i>feat(automation): scheduler periódico de reconciliación "
     "de reservas (T2.1.E)</i>"],
    ["Push", "<b>No realizado</b> · esperando aprobación"],
    ["PR", "<b>No abierto</b> · per instrucción"],
    ["Deploy", "<b>No realizado</b>"],
], col_widths=[1.6*inch, 5.0*inch]))

# ── 8. Siguiente paso recomendado ────────────────────────────────────

story.append(H1("8. Siguiente paso recomendado"))

story.append(P(
    "Cuando estés listo para mover T2.1.E adelante:"))

story.append(make_table([
    ["#", "Acción", "Riesgo"],
    ["1", "Revisar el diff local · "
     "<i>git diff main..HEAD</i>",
     "Cero"],
    ["2", "Push de la branch: "
     "<i>git push -u origin "
     "pr/t2.1.e-automation-scheduler-reconciliation</i>",
     "Cero (branch nueva, sin afectar main)"],
    ["3", "Abrir PR con título: "
     "<i>feat(automation): periodic scheduler for "
     "reservations reconciliation (T2.1.E)</i>",
     "Cero hasta el merge"],
    ["4", "Mergear vía PR cuando el smoke test producción de "
     "T2.1.D pase (ver Resumen_T21D_Verificacion_Post_Merge_2026-"
     "05-11.pdf §7)",
     "Bajo · default OFF · cero impacto funcional sin env var"],
    ["5", "<b>Decidir cuándo activar en prod:</b> agregar "
     "<i>AUTOMATION_SCHEDULER_ENABLED=true</i> en Render. "
     "Recomendación: dejar el scheduler activo por 24h en "
     "<i>preview</i> (deshabilitado) y monitorear el endpoint "
     "<i>/admin/automation/credits/reconciliar/preview</i> · si "
     "<i>total_preparing &lt; 5</i> consistentemente, entonces "
     "habilitar.",
     "Bajo"],
    ["6", "<b>NO ahora:</b> T2.2 (acción HIGH real con Whapi). "
     "Esperar a que T2.1.E haya corrido 1 semana en prod sin "
     "<i>corridas_fallidas &gt; 0</i>.",
     "—"],
], col_widths=[0.3*inch, 4.4*inch, 2.3*inch]))

story.append(BANNER(
    "<b>Sin acciones automáticas pendientes.</b> El scheduler está "
    "implementado, testeado y listo en una branch local. Producción "
    "no se ve afectada hasta que (a) el PR se mergee y (b) la env "
    "var se active explícitamente."
))

doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
)
doc.build(story)
print(f"OK · escrito {OUTPUT}")
