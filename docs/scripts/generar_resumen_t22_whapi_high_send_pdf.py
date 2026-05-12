"""
Genera Resumen_T22_Whapi_High_Send_2026-05-11.pdf · entrega del bloque
T2.2 · primera acción HIGH real (enviar mensaje WhatsApp) con
preparar/aprobar/confirmar, idempotencia, cobro seguro y Whapi
mockeado en tests · sin enviar nada en prod.
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
    r"\Resumen_T22_Whapi_High_Send_2026-05-11.pdf"
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
    "T2.2 · Primera acción HIGH real · enviar mensaje WhatsApp",
    styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-11 · branch "
    "<i>pr/t2.2-whapi-high-send-action</i> · "
    "<b>commit local · sin push · sin PR · sin deploy · sin tocar "
    "Render</b>.",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Resumen ejecutivo:</b> el Action Center pasa a tener su "
    "primer ejecutor HIGH real. <i>preparar_enviar_mensaje_whatsapp</i> "
    "crea una acción en <i>needs_approval</i> guardando "
    "<i>numero_destino + mensaje</i> en payload · NUNCA envía al "
    "crearse. Solo tras aprobación humana explícita "
    "<i>ejecutar_accion</i> invoca al proveedor de WhatsApp existente. "
    "Idempotencia anti doble envío via <i>result_json.estado_envio='sent'</i> "
    "persistido inline antes de retornar. Cobro vía T2.1.D · "
    "reserva confirma si éxito, libera/reembolsa si falla. Whapi "
    "MOCKEADO en tests · ninguna llamada real. <b>18 tests nuevos · "
    "237 automation total · 0 regresión (la única flake "
    "test_listar_jobs_usuario es pre-existente, depende de "
    "asyncio.sleep y pasa en aislamiento).</b>"
))

# ── 1. Diseño y patrón ───────────────────────────────────────────────

story.append(H1("1. Diseño · preparar → aprobar → confirmar"))

story.append(H2("1.1 Reuso del modelo existente"))
story.append(P(
    "El tipo de acción <i>enviar_mensaje_whatsapp</i> ya existía en "
    "<i>permissions.py</i> como HIGH y en <i>costos.py</i> como 6 "
    "créditos. T2.1.A lo dejó intencionalmente SIN ejecutor: "
    "<i>EJECUTORES_T21A</i> no tenía entrada y "
    "<i>ejecutar_accion</i> lo rechazaba liberando la reserva. T2.2 "
    "agrega el ejecutor faltante sin cambiar riesgo ni costo."))

story.append(H2("1.2 API pública del nuevo módulo"))

story.append(make_table([
    ["Función", "Rol", "Notas"],
    ["preparar_enviar_mensaje_whatsapp(telefono, "
     "numero_destino, mensaje, ...)",
     "PREPARAR · crear acción",
     "Valida payload, llama <i>crear_accion</i> · acción queda en "
     "<i>needs_approval</i> · NUNCA envía. <i>created=False</i> si "
     "ya había una con misma idempotency_key."],
    ["aprobar_accion(accion_id) · existente",
     "APROBAR · humano",
     "Mismo paso que MEDIUM · transición "
     "<i>needs_approval → approved</i>."],
    ["ejecutar_accion(accion) · existente",
     "CONFIRMAR · disparar envío",
     "Llama el ejecutor mapeado · T2.2 mapea "
     "<i>enviar_mensaje_whatsapp → ejecutor_enviar_mensaje_whatsapp</i>."],
    ["confirmar_enviar_mensaje_whatsapp(accion_id)",
     "Atajo end-to-end",
     "Aprueba (si needs_approval) y ejecuta. Idempotente si la "
     "acción ya está <i>completed</i>: devuelve el resultado "
     "previo con <i>idempotent=True</i> sin re-invocar provider."],
], col_widths=[2.7*inch, 1.5*inch, 2.6*inch]))

story.append(H2("1.3 Flujo del ejecutor real"))

story.append(CODE(
    "ejecutor_enviar_mensaje_whatsapp(accion, perfil):\n"
    "  1. parsear payload_json → (numero_destino, mensaje)\n"
    "     · valida obligatorios · si inválidos → raise ValueError\n"
    "  2. _leer_result_actual(accion_id)   ← lee DB fresca\n"
    "     · si estado_envio=='sent' AND mensaje_id existe →\n"
    "       return {**prev, idempotent: True}  ← NO invoca provider\n"
    "  3. _obtener_proveedor()               ← override-able en tests\n"
    "  4. await proveedor.enviar_mensaje(numero_destino, mensaje)\n"
    "     · si False o lanza → raise RuntimeError\n"
    "       (ejecutar_accion atrapará y liberará reserva)\n"
    "  5. resultado = { estado_envio: 'sent', mensaje_id,\n"
    "                   destino_short, longitud_mensaje, provider, ... }\n"
    "  6. _persistir_result_inline(accion_id, resultado)\n"
    "     ← UPDATE result_json antes de retornar  ← dedupe en retry\n"
    "  7. return resultado"
))

story.append(P(
    "El paso 6 es el invariante crítico de T2.2: si un crash ocurre "
    "DESPUÉS del envío pero ANTES de "
    "<i>marcar_completada</i>, cualquier retry verá "
    "<i>result_json.estado_envio='sent'</i> en el paso 2 y NO "
    "re-enviará."))

# ── 2. Archivos modificados ──────────────────────────────────────────

story.append(H1("2. Archivos creados / modificados"))

story.append(make_table([
    ["Archivo", "Tipo", "Resumen"],
    ["agent/automation/executors/__init__.py", "NUEVO",
     "Paquete nuevo · agrupa ejecutores HIGH."],
    ["agent/automation/executors/send_message.py", "NUEVO ~250 ln",
     "<i>preparar_enviar_mensaje_whatsapp</i>, "
     "<i>confirmar_enviar_mensaje_whatsapp</i>, "
     "<i>ejecutor_enviar_mensaje_whatsapp</i>, validaciones, "
     "helpers de persistencia/idempotencia."],
    ["agent/automation/execution.py", "MOD ~10 ln",
     "Import del nuevo ejecutor + entrada en "
     "<i>EJECUTORES_T21A</i> para "
     "<i>enviar_mensaje_whatsapp</i>."],
    ["tests/test_automation_send_message_high.py",
     "NUEVO 18 tests",
     "Preparar · ejecutar sin aprobación · con aprobación · "
     "idempotencia en retry · provider False · provider raise · "
     "audit sin PII · confirmar shortcut · CRITICAL no mezcla."],
    ["tests/test_automation_execution.py", "MOD 1 test",
     "<i>TestEjecutarHighSinEjecutorReal</i> ahora usa "
     "<i>contactar_lead</i> (que sigue sin ejecutor) en lugar de "
     "<i>enviar_mensaje_whatsapp</i> · invariante actualizado."],
    ["tests/test_automation_creditos_reservas.py", "MOD 1 test",
     "<i>test_high_sin_ejecutor_libera_reserva</i> idem."],
    ["tests/test_automation_executors_real.py", "MOD 1 test",
     "<i>test_high_aprobado_sigue_sin_ejecutor</i> idem."],
], col_widths=[2.7*inch, 1.0*inch, 3.3*inch]))

story.append(P(
    "<b>Sin nuevas migraciones de schema.</b> Se reutilizan campos "
    "existentes: <i>payload_json</i>, <i>result_json</i>, "
    "<i>estado</i>, <i>idempotency_key</i>. Sin nuevos endpoints "
    "admin. Sin tocar <i>permissions.py</i> ni <i>costos.py</i>."))

# ── 3. Variables de entorno ──────────────────────────────────────────

story.append(H1("3. Variables de entorno"))

story.append(BANNER(
    "<b>Cero variables de entorno nuevas.</b> El módulo usa "
    "<i>agent.providers.obtener_proveedor()</i> que ya lee "
    "<i>WHATSAPP_PROVIDER</i> y <i>WHAPI_TOKEN</i> · NO se tocaron. "
    "Tests monkeypatchean <i>_obtener_proveedor</i> dentro del módulo "
    "send_message · ningún test toca <i>os.environ</i> de Whapi ni "
    "Render."
))

# ── 4. Riesgos y mitigaciones ────────────────────────────────────────

story.append(PageBreak())
story.append(H1("4. Riesgos y mitigaciones"))

story.append(make_table([
    ["Riesgo", "Sev", "Mitigación"],
    ["Doble envío en retry de worker",
     "Bajo",
     "<i>result_json.estado_envio='sent'</i> persistido inline "
     "antes de retornar. Cualquier 2da invocación al ejecutor lo "
     "detecta y retorna sin tocar provider. Test "
     "<i>test_executor_directo_con_result_previo_es_idempotente</i> "
     "lo prueba sin pasar por ejecutar_accion."],
    ["Envío sin aprobación humana (auto)",
     "Bajo",
     "<i>enviar_mensaje_whatsapp</i> es HIGH · "
     "<i>estado_inicial_para_riesgo</i> retorna "
     "<i>needs_approval</i>. <i>ejecutar_accion</i> sólo procede "
     "si <i>estado==approved</i>. Test "
     "<i>test_ejecutar_needs_approval_no_envia</i>."],
    ["Provider falla con saldo descontado",
     "Bajo",
     "T2.1.D ya cubre · <i>ejecutar_accion</i> atrapa la excepción "
     "del ejecutor y llama <i>liberar_creditos</i>. Tests "
     "<i>test_provider_devuelve_false_libera_reserva</i> y "
     "<i>test_provider_lanza_excepcion_libera_reserva</i>."],
    ["Crash entre <i>enviar_mensaje</i> OK y "
     "<i>marcar_completada</i>",
     "Medio",
     "Mitigado parcialmente: <i>_persistir_result_inline</i> graba "
     "<i>result_json</i> antes de retornar al ejecutor → retry "
     "detectará y será no-op. <b>NO mitigado</b>: la acción "
     "queda en estado <i>running</i> permanentemente si "
     "<i>marcar_completada</i> nunca corre · requiere reset manual "
     "vía admin endpoint (futuro)."],
    ["Adversario inyecta números falsos por payload",
     "Bajo",
     "<i>preparar_enviar_mensaje_whatsapp</i> valida formato: "
     "longitud 6..32 chars · solo dígitos con '+' opcional. Mensaje "
     "≤ 4000 chars. Test "
     "<i>test_preparar_rechaza_numero_no_numerico</i>."],
    ["PII filtrada en logs / audit",
     "Bajo",
     "Logs usan <i>_short_num</i> (prefijo+sufijo). Audit "
     "(<i>action_completed</i>) no recibe <i>numero_destino</i> ni "
     "<i>mensaje</i> · sólo metadata. Test "
     "<i>test_audit_no_incluye_numero_destino_ni_cuerpo</i> "
     "verifica que ni teléfono ni cuerpo aparezcan en "
     "<i>payload_summary</i>."],
    ["Activación accidental en producción",
     "Muy bajo",
     "T2.2 NO añade triggers ni endpoints externos · sólo conecta "
     "el ejecutor a un tipo de acción HIGH preexistente. Una "
     "acción solo se crea si Dona o un admin la solicita "
     "explícitamente, y aún así requiere aprobación humana antes "
     "de ejecutarse. <b>Sin deploy + sin uso por LLM hasta que se "
     "decida exponerlo</b>."],
    ["CRITICAL confundido con HIGH",
     "Muy bajo",
     "<i>envio_masivo_clientes</i> sigue siendo CRITICAL · "
     "<i>esta_bloqueado_t21</i> retorna True · bloqueo defensivo "
     "en <i>ejecutar_accion</i> libera la reserva sin invocar al "
     "ejecutor. Test "
     "<i>test_envio_masivo_clientes_sigue_bloqueado</i>."],
], col_widths=[2.6*inch, 0.6*inch, 3.8*inch]))

# ── 5. Tests ─────────────────────────────────────────────────────────

story.append(H1("5. Tests ejecutados"))

story.append(make_table([
    ["Suite", "Resultado"],
    ["<i>pytest tests/test_automation_send_message_high.py</i>",
     "<b>18 passed</b> in 13.51s"],
    ["<i>pytest tests/test_automation_*.py</i>",
     "<b>237 passed</b> in 133.57s · +18 vs main"],
    ["<i>pytest</i> (suite completa, primera corrida)",
     "899 passed · 0 failed"],
    ["<i>pytest</i> (suite completa, segunda corrida)",
     "1 failed (test_jobs · pre-existente · pasa en aislamiento)"],
    ["<i>pytest tests/test_jobs.py::TestEncolarInproc::"
     "test_listar_jobs_usuario</i> en aislamiento",
     "<b>1 passed</b> in 1.15s"],
], col_widths=[4.0*inch, 3.0*inch]))

story.append(WARN(
    "<b>Nota sobre la flake:</b> <i>test_listar_jobs_usuario</i> "
    "depende de <i>asyncio.sleep(0.1)</i> y bajo la carga de la "
    "suite completa a veces falla. <b>No es introducida por "
    "T2.2</b> · existe en main desde antes y no toca nada del "
    "Automation Core. La suite específica de T2.2 (18 tests) y la "
    "suite de automation (237 tests) son completamente "
    "deterministas."
))

# ── 6. Cómo validar localmente ───────────────────────────────────────

story.append(H1("6. Cómo validar localmente"))

story.append(CODE(
    "git checkout pr/t2.2-whapi-high-send-action\n\n"
    "# Tests específicos · todos mockean Whapi · no toca red\n"
    "pytest tests/test_automation_send_message_high.py -v\n\n"
    "# Suite completa de automation\n"
    "pytest tests/test_automation_*.py\n\n"
    "# Smoke en REPL (opcional · usa FakeProveedor para no enviar)\n"
    "python -c \"\\\n"
    "import asyncio, agent.memory as m, agent.automation as a;\\\n"
    "from agent.automation.executors.send_message import \\\n"
    "  preparar_enviar_mensaje_whatsapp, confirmar_enviar_mensaje_whatsapp\\\n"
    "\""
))

story.append(H2("6.1 Cómo NO validar"))
story.append(P(
    "<b>No envíes mensajes reales para validar T2.2 todavía.</b> "
    "El ejecutor está cableado pero la decisión de exponerlo al LLM "
    "(via brain tool) o a admin endpoints externos es un paso "
    "separado. Sin un trigger explícito, el ejecutor no se invoca "
    "en producción, aunque la branch esté mergeada."))

# ── 7. Estado git ────────────────────────────────────────────────────

story.append(H1("7. Estado git"))

story.append(make_table([
    ["Item", "Valor"],
    ["Branch local", "<i>pr/t2.2-whapi-high-send-action</i>"],
    ["Base", "<i>main</i> · sincronizada antes del branch "
     "(commit <i>4633289</i>)"],
    ["Commit en branch", "Por crear · "
     "<i>feat(automation): primer ejecutor HIGH real · "
     "enviar mensaje WhatsApp (T2.2)</i>"],
    ["Push", "<b>NO realizado</b> · per instrucción"],
    ["PR", "<b>NO abierto</b> · per instrucción"],
    ["Merge", "<b>NO realizado</b>"],
    ["Deploy", "<b>NO realizado</b>"],
    ["Variables de entorno Render", "<b>NO tocadas</b>"],
    ["AUTOMATION_SCHEDULER_ENABLED",
     "<b>NO activado</b> (sigue ausente · OFF)"],
], col_widths=[2.5*inch, 4.4*inch]))

# ── 8. Siguiente paso recomendado ────────────────────────────────────

story.append(H1("8. Siguiente paso recomendado"))

story.append(P(
    "Antes de mergear T2.2 hay que decidir cómo se va a invocar "
    "<i>preparar_enviar_mensaje_whatsapp</i> en producción. Cuatro "
    "caminos posibles:"))

story.append(make_table([
    ["Opción", "Mecanismo", "Cuándo"],
    ["A",
     "<b>Brain tool</b> · agregar herramienta "
     "<i>preparar_enviar_mensaje_whatsapp</i> / "
     "<i>confirmar_enviar_mensaje_whatsapp</i> en <i>brain.py</i> "
     "siguiendo el patrón CLAUDE.md (preparar=preview, "
     "confirmar=materializa).",
     "Si el plan es que Dona ofrezca enviar mensajes "
     "automáticamente al dueño · más natural via WhatsApp."],
    ["B",
     "<b>Admin endpoint</b> · "
     "<i>POST /admin/automation/preparar-envio</i> + "
     "<i>POST /admin/automation/confirmar-envio</i> · "
     "Bearer auth. Para testing supervisado.",
     "Si quieres operar manual sin exponer a usuarios todavía."],
    ["C",
     "<b>Dashboard del Action Center</b> · botón \"Enviar mensaje\" "
     "en la UI · llama landing/api proxy autenticado.",
     "Si la UI sigue siendo el canal principal de aprobación."],
    ["D",
     "<b>Solo merge sin trigger</b> · dejar el ejecutor disponible "
     "para llamadas internas (playbooks futuros) sin exponerlo aún.",
     "Camino más seguro · ningún cambio en superficie de usuario."],
], col_widths=[0.5*inch, 3.5*inch, 2.9*inch]))

story.append(BANNER(
    "<b>Recomendación del agente:</b> opción <b>D + smoke test "
    "pendiente de T2.1.D</b>. T2.2 mergea con superficie cero "
    "(solo conecta el plumbing) · 0 riesgo de envío accidental. "
    "Después, en un PR separado (T2.2.A o T2.3), elegir A/B/C "
    "según prioridad de producto. Esto permite hacer el smoke "
    "pendiente de T2.1.D y validar las reservas + reconciliación "
    "en prod sin agregar otra superficie de cambio simultánea."
))

story.append(WARN(
    "<b>Recordatorios de seguridad:</b> branch local lista · sin "
    "push · sin PR · sin deploy · sin tocar Render · "
    "<i>AUTOMATION_SCHEDULER_ENABLED</i> sigue ausente (OFF) · "
    "ninguna llamada real a Whapi · ningún mensaje enviado."
))

doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
)
doc.build(story)
print(f"OK · escrito {OUTPUT}")
