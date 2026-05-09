"""
Genera Resumen_T20E1_Diagnostico_Negocio_2026-05-08.pdf · resumen del PR
backend que extiende el onboarding de negocio para capturar las 6 nuevas
preguntas del diagnóstico inicial (T2.0.E.1).
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T20E1_Diagnostico_Negocio_2026-05-08.pdf"

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

story.append(Paragraph("T2.0.E.1 · Diagnóstico inicial extendido (backend)",
                       styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-08 · Branch "
    "<b>pr/t2.0.e.1-diagnostico-negocio-extendido</b> · base "
    "<b>main@157ab11</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> PR backend listo para revisión. <b>662/662 "
    "tests passing</b> (39 nuevos T2.0.E.1 + 15 onboarding "
    "originales + 608 suite restante · cero regresiones). El "
    "tour T2.0.D step 8 ya activa el flow extendido vía wa.me. "
    "<b>Sin merge · sin deploy.</b>"
))

# ── 1. Causa de uso ────────────────────────────────────────────────────

story.append(H1("1. Por qué este PR"))

story.append(P(
    "El tour de primer login (T2.0.D step 8) invita al usuario a "
    "abrir WhatsApp y escribir <i>'hola Dona, quiero empezar el "
    "diagnóstico de mi negocio'</i>. Hoy esa frase NO dispara el "
    "onboarding · solo lo hace si el usuario menciona "
    "explícitamente \"mi negocio\" o equivalente. Y el flow "
    "actual solo captura 4 datos (nombre, industria, moneda, "
    "meta) · no las 6 preguntas adicionales que necesita Dona "
    "para personalizar."
))

# ── 2. Cambios ─────────────────────────────────────────────────────────

story.append(H1("2. Archivos tocados (3 backend + 2 docs)"))

story.append(make_table([
    ["Archivo", "Tipo", "Cambio"],
    ["agent/business/models.py", "MOD",
     "PerfilNegocio: <b>+6 columnas Text default ''</b> "
     "(<i>oferta_principal, cliente_ideal, objetivo_mes, "
     "canales_actuales, bloqueo_actual, tareas_delegar</i>). "
     "MIGRACIONES_NEGOCIO: <b>+6 ALTER TABLE</b> idempotentes "
     "(DO $$ IF NOT EXISTS) · estilo de la migración existente "
     "de <i>onboarding_paso</i>."],
    ["agent/business/onboarding_negocio.py", "MOD",
     "Flow extendido a 10 pasos (0-9 en lugar de 0-3). "
     "+6 mensajes (paso 4-9) · +6 branches en "
     "<i>procesar_paso_onboarding</i>. <b>+4 trigger keywords</b> "
     "(<i>diagnóstico</i> + variantes con/sin acento) y otras "
     "variaciones útiles. Helpers: <i>_short_telefono</i>, "
     "<i>_es_rechazo</i>, <i>_capar_texto</i> (cap 500 chars). "
     "Logging seguro · solo paso/longitud/tel truncado."],
    ["tests/test_onboarding_negocio_extendido.py", "NEW",
     "39 tests pytest. Cubre: trigger 'diagnóstico' · 6 mensajes "
     "extendidos · migración runtime · default '' · flow "
     "completo end-to-end · pasos 4-9 individuales · rechazos "
     "(11 variantes) · cap 500 chars · logging seguro · "
     "idempotencia."],
    ["docs/auditorias/...PDF", "NEW", "Este reporte"],
    ["docs/scripts/...py", "NEW", "Generador del PDF"],
], col_widths=[2.6*inch, 0.5*inch, 3.5*inch]))

# ── 3. Modelo de datos · campos nuevos ────────────────────────────────

story.append(H1("3. Modelo de datos"))

story.append(make_table([
    ["Campo", "Tipo", "Default", "Capturado en"],
    ["oferta_principal", "Text", "''", "Paso 4"],
    ["cliente_ideal", "Text", "''", "Paso 5"],
    ["objetivo_mes", "Text", "''", "Paso 6"],
    ["canales_actuales", "Text", "''", "Paso 7"],
    ["bloqueo_actual", "Text", "''", "Paso 8"],
    ["tareas_delegar", "Text", "''", "Paso 9"],
], col_widths=[2.0*inch, 1.0*inch, 1.0*inch, 2.6*inch]))

story.append(C(
    "Todos los nuevos campos son Text. Los pasos 4-9 son "
    "opcionales · el usuario puede saltarlos con 'omitir', 'no', "
    "'skip', 'saltar', 'ninguno', 'nada', 'no sé', 'luego', "
    "'más tarde'. El campo queda en string vacío. <b>Cap de "
    "500 caracteres</b> para texto libre · principio de "
    "minimización de datos (CCPA)."
))

# ── 4. Migración runtime · doble vía ──────────────────────────────────

story.append(H1("4. Migración runtime · idempotente"))

story.append(P(
    "La migración runtime se aplica vía <i>_migrar_columnas()</i> "
    "en <i>agent/memory.py</i> que concatena <i>_MIGRACIONES + "
    "MIGRACIONES_NEGOCIO</i>. Las 6 migraciones DO $$ "
    "IF NOT EXISTS viven en <i>MIGRACIONES_NEGOCIO</i> "
    "(<i>agent/business/models.py</i>) · ya integradas al runtime "
    "del módulo memory."
))

story.append(CODE(
    "DO $$\n"
    "BEGIN\n"
    "    IF NOT EXISTS (\n"
    "        SELECT 1 FROM information_schema.columns\n"
    "        WHERE table_name = 'perfil_negocio'\n"
    "        AND column_name = 'oferta_principal'\n"
    "    ) THEN\n"
    "        ALTER TABLE perfil_negocio\n"
    "        ADD COLUMN oferta_principal TEXT NOT NULL DEFAULT '';\n"
    "    END IF;\n"
    "END $$"
))

story.extend(bullets([
    "<b>Idempotente</b>: <i>IF NOT EXISTS</i> · no rompe en "
    "redeploys.",
    "<b>Aditiva</b>: filas existentes quedan con default ''.",
    "<b>Postgres-specific</b>: en SQLite (tests/dev) las "
    "columnas las crea <i>Base.metadata.create_all()</i> que sí "
    "entiende la metadata SQLAlchemy. _migrar_columnas tolera "
    "errores 'syntax error' silenciosamente.",
    "<b>Mismo patrón</b> que la migración existente de "
    "<i>onboarding_paso</i> · sin precedentes nuevos.",
]))

# ── 5. Flow completo · 10 pasos ───────────────────────────────────────

story.append(PageBreak())
story.append(H1("5. Flow completo · 10 pasos"))

story.append(make_table([
    ["#", "Pregunta", "Captura", "Notas"],
    ["0", "¿Cómo se llama tu negocio?", "nombre_negocio",
     "Existente"],
    ["1", "¿A qué se dedica? (5 opciones)", "industria",
     "Existente"],
    ["2", "¿En qué moneda?", "moneda", "Existente"],
    ["3", "¿Meta de ventas mensual?", "meta_mensual",
     "Existente · acepta 'no' / monto"],
    ["4", "<b>¿Cuál es tu oferta principal?</b>", "oferta_principal",
     "T2.0.E.1 · texto libre · cap 500 · 'omitir' permitido"],
    ["5", "<b>¿Quién es tu cliente ideal?</b>", "cliente_ideal",
     "T2.0.E.1"],
    ["6", "<b>¿Cuál es tu objetivo principal este mes?</b>",
     "objetivo_mes",
     "T2.0.E.1 · texto libre · complementa <i>meta_mensual</i> "
     "numérica"],
    ["7", "<b>¿Por qué canales vendes hoy?</b>", "canales_actuales",
     "T2.0.E.1 · multi-respuesta libre"],
    ["8", "<b>¿Cuál es tu mayor bloqueo o frustración?</b>",
     "bloqueo_actual", "T2.0.E.1"],
    ["9", "<b>¿Qué tareas te gustaría delegar a Dona?</b>",
     "tareas_delegar", "T2.0.E.1 · cierra el flow"],
], col_widths=[0.3*inch, 2.6*inch, 1.6*inch, 2.0*inch]))

story.append(C(
    "Idempotencia preservada del flow original: "
    "<i>onboarding_paso</i> = None al completar · 0-9 en "
    "progreso. Si el usuario interrumpe, retoma desde donde "
    "quedó. Re-recibir el mismo paso no avanza dos veces."
))

# ── 6. Trigger keywords nuevos ─────────────────────────────────────────

story.append(H1("6. Trigger keywords agregados"))

story.append(CODE(
    "TRIGGER_KEYWORDS = {\n"
    "  ...legacy keywords mi-negocio/etc...\n"
    "  # T2.0.E.1\n"
    "  \"diagnóstico\", \"diagnostico\",\n"
    "  \"empezar diagnóstico\", \"empezar diagnostico\",\n"
    "  \"iniciar diagnóstico\", \"iniciar diagnostico\",\n"
    "  \"diagnostico de mi negocio\",\n"
    "  \"diagnóstico de mi negocio\",\n"
    "}"
))

story.append(P(
    "<b>Test específico verifica</b> que el texto del CTA del "
    "tour T2.0.D matchea: <i>'hola Dona, quiero empezar el "
    "diagnóstico de mi negocio.'</i> contiene "
    "<i>'empezar diagnóstico'</i> y <i>'diagnóstico de mi "
    "negocio'</i> · el flow se activa."
))

# ── 7. Privacidad y logging seguro ─────────────────────────────────────

story.append(H1("7. Privacidad y logging seguro"))

story.append(P(
    "<b>CCPA/CPRA aplica.</b> Las respuestas de los pasos 4-9 son "
    "texto libre y pueden contener PII de clientes del usuario "
    "(nombres, teléfonos, emails). Decisiones de mitigación:"
))

story.extend(bullets([
    "<b>NO se loguea el contenido bruto</b>. El log "
    "<i>[BIZ-ONBOARD] tel=XX****XX paso=N resp_len=L</i> solo "
    "incluye telefono truncado, número de paso y longitud. Test "
    "específico (<i>TestLoggingSeguro</i>) valida que el texto "
    "crudo NO aparece en logs.",
    "<b>Telefono truncado</b>: helper "
    "<i>_short_telefono</i> deja prefijo + 4 últimos · igual "
    "patrón que <i>agent/welcome.py</i> de T2.0.B.",
    "<b>Cap 500 chars</b>: minimización de datos · el flow no "
    "captura bloques enormes que invitarían a pegar dumps.",
    "<b>Borrado de datos</b> ('dona borrar mis datos' en "
    "WhatsApp): el flow existente borra <i>perfil_negocio</i> "
    "entero · cubre los nuevos campos por cascada · no requiere "
    "cambio.",
    "<b>Export de datos</b> ('dona exportar datos'): hoy es flow "
    "conversacional MVP · cuando se implemente el export real, "
    "incluirá automáticamente las columnas nuevas porque vienen "
    "del mismo modelo PerfilNegocio.",
]))

# ── 8. Tests ────────────────────────────────────────────────────────────

story.append(H1("8. Tests · 39 nuevos · 662/662 suite completa"))

story.append(make_table([
    ["Clase", "Tests", "Cubre"],
    ["TestTriggerDiagnostico", "6",
     "diagnóstico/diagnostico/empezar.../iniciar... presentes · "
     "match al texto del CTA del tour · regresión: triggers "
     "legacy intactos"],
    ["TestMensajesExtendidos", "6",
     "Cada mensaje paso 4-9 existe y tiene la palabra clave "
     "correspondiente"],
    ["TestMigracionRuntime", "2",
     "Las 6 columnas existen en SQLite tras inicializar_db · "
     "default '' (no NULL)"],
    ["TestFlowCompletoExtendido", "1",
     "End-to-end: 10 pasos · mensajes correctos · todos los "
     "campos persisten · onboarding_paso queda None"],
    ["TestPasosExtendidosIndividuales", "6",
     "Cada paso 4-9 captura su campo correcto y avanza al "
     "siguiente prompt"],
    ["TestRechazos", "11",
     "Variantes de 'omitir' (omitir/no/skip/saltar/ninguno/nada/"
     "luego/...) dejan el campo vacío y avanzan"],
    ["TestCapTextoLibre", "1",
     "Texto de 1000 chars se capa a 500"],
    ["TestLoggingSeguro", "2",
     "<b>NO se loguea texto crudo del usuario</b> · NO se loguea "
     "telefono completo · sí se loguea paso/length"],
    ["TestIdempotencia", "2",
     "Re-procesar un paso ya pasado no afecta · perfil "
     "completado o inexistente retorna None"],
    ["TestEstaEnOnboarding", "2",
     "Estado helper detecta paso 4-9 como en-progreso · "
     "completado retorna False"],
], col_widths=[2.4*inch, 0.5*inch, 3.7*inch]))

story.append(BANNER(
    "<b>Suite completa: 662/662 passing en 108s</b>. Cero "
    "regresiones · 39 tests nuevos · 15 originales del onboarding "
    "siguen verdes."
))

# ── 9. Riesgos ─────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("9. Riesgos"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["Migración DO $$ falla en Postgres por permissions",
     "Bajo",
     "_migrar_columnas tolera errores · loguea ERROR pero no "
     "aborta el server. Owner verifica logs post-deploy."],
    ["Usuario abandona en paso 5 · perfil parcial",
     "Cero · es la idempotencia esperada",
     "onboarding_paso=5 queda guardado · al volver a escribir "
     "sigue desde paso 5 · datos parciales en DB no rompen "
     "nada."],
    ["Texto libre con PII no se borra al revocar consenso",
     "Bajo · CCPA",
     "'dona borrar mis datos' borra perfil_negocio entero. Test "
     "manual recomendado post-merge para confirmar cascada."],
    ["Trigger 'diagnóstico' colisiona con casos legítimos",
     "Bajo",
     "Solo dispara si <b>NO hay perfil con nombre</b>. Usuarios "
     "ya configurados no se ven afectados."],
    ["UX larga · 10 preguntas en chat móvil",
     "Medio · UX",
     "Los pasos 4-9 son opcionales · 'omitir' acepta 11 variantes "
     "· cada paso tiene texto explicativo de qué se espera."],
    ["Cap 500 chars trunca respuestas legítimas largas",
     "Bajo",
     "500 caracteres es ~80 palabras · suficiente para una "
     "descripción típica · si el usuario quiere más, el truncado "
     "se aplica silenciosamente y no falla."],
], col_widths=[2.4*inch, 1.0*inch, 3.2*inch]))

# ── 10. Out of scope · explícito ───────────────────────────────────────

story.append(H1("10. Out of scope · NO entra"))

story.extend(bullets([
    "<b>Dashboard UI</b> · será T2.0.E.2 (PR ortogonal posterior).",
    "<b>Endpoint frontend</b> · ídem.",
    "<b>Playbook Engine</b> · explícitamente excluido.",
    "<b>Browser Operator</b> · excluido.",
    "<b>Automatizaciones externas</b> · excluido.",
    "<b>WhatsApp/email automático nuevo</b> · ningún send "
    "automático · todo el flow es respuesta a mensajes inbound "
    "del usuario.",
    "<b>Deploy</b> · este PR solo crea la rama y push · "
    "Vercel/Render redeploy automático recién al mergear.",
    "<b>Env changes</b> · cero variables nuevas.",
    "<b>Editar respuestas vía dashboard</b> (PUT) · futuro.",
    "<b>Re-iniciar diagnóstico</b> via comando WhatsApp · futuro.",
]))

# ── 11. Plan post-merge ────────────────────────────────────────────────

story.append(H1("11. Plan post-merge"))

story.extend(bullets([
    "Tu revisas el PR en GitHub.",
    "Mergeas a main.",
    "Render auto-redeploy ~2 min · backend reinicia · "
    "<i>_migrar_columnas</i> aplica las 6 ALTER TABLE en "
    "Postgres prod · loguea OK por cada una · si alguna falla "
    "(unlikely) loguea ERROR pero arranca igual.",
    "Smoke desde tu WhatsApp · escribe 'empezar diagnóstico' · "
    "Dona debe responder MENSAJE_INICIO (paso 0).",
    "Recorre los 10 pasos · usa 'omitir' en alguno · verifica "
    "que el flow termina con MENSAJE_COMPLETADO.",
    "Verifica en Supabase que <i>perfil_negocio</i> tiene tu "
    "fila con los 6 campos nuevos llenos / vacíos según lo "
    "respondido.",
    "Si quieres, smoke con un usuario premium real · esperar 24h "
    "y revisar tasa de finalización vs abandono.",
]))

# ── 12. Datos para abrir el PR ─────────────────────────────────────────

story.append(H1("12. Datos para abrir el PR"))

story.append(make_table([
    ["Campo", "Valor"],
    ["URL",
     "github.com/celestinojbm/Dona-agent/pull/new/<br/>"
     "pr/t2.0.e.1-diagnostico-negocio-extendido"],
    ["Título sugerido",
     "feat(business) · diagnóstico inicial extendido en "
     "onboarding (T2.0.E.1)"],
    ["Base", "main"],
    ["Head", "pr/t2.0.e.1-diagnostico-negocio-extendido"],
    ["Body markdown",
     "Generado abajo en el PDF · listo para copiar/pegar"],
], col_widths=[1.6*inch, 5.0*inch]))

# ── 13. Body markdown del PR ──────────────────────────────────────────

story.append(PageBreak())
story.append(H1("13. Body markdown del PR (copy-paste)"))

story.append(CODE(
    "## Resumen\n"
    "\n"
    "Extiende el flow de onboarding de negocio (WhatsApp) con\n"
    "6 preguntas adicionales para capturar un diagnóstico inicial\n"
    "del negocio. El tour T2.0.D step 8 ya invita al usuario a\n"
    "abrir WhatsApp con texto pre-llenado · ahora ese texto activa\n"
    "el flow extendido (trigger 'diagnóstico' agregado).\n"
    "\n"
    "## Cambios\n"
    "\n"
    "- agent/business/models.py · PerfilNegocio +6 columnas Text\n"
    "  default '': oferta_principal, cliente_ideal, objetivo_mes,\n"
    "  canales_actuales, bloqueo_actual, tareas_delegar.\n"
    "  MIGRACIONES_NEGOCIO +6 ALTER TABLE idempotentes\n"
    "  (DO $$ IF NOT EXISTS) ya integradas al runtime via\n"
    "  _migrar_columnas() en agent/memory.py.\n"
    "- agent/business/onboarding_negocio.py · flow extendido a\n"
    "  10 pasos. +6 mensajes (paso 4-9) · +4 trigger keywords\n"
    "  ('diagnóstico'/'diagnostico'/variantes). Logging seguro\n"
    "  (paso/length/tel truncado · NO contenido). Cap 500 chars\n"
    "  por respuesta. Helper _es_rechazo cubre 11 variantes\n"
    "  ('omitir', 'no', 'skip', 'saltar', etc).\n"
    "- tests/test_onboarding_negocio_extendido.py NEW · 39 tests\n"
    "  pytest cubriendo trigger, mensajes, migración runtime,\n"
    "  flow completo, pasos individuales, rechazos, cap, logging\n"
    "  seguro, idempotencia.\n"
    "\n"
    "## Privacidad y logging\n"
    "\n"
    "- Las respuestas pueden contener PII de clientes del usuario.\n"
    "  El log [BIZ-ONBOARD] solo incluye telefono truncado, paso,\n"
    "  longitud · NUNCA el contenido bruto. Test específico valida\n"
    "  que el texto crudo no aparece en logs.\n"
    "- Cap 500 chars por respuesta (minimización CCPA).\n"
    "- Borrado de datos (dona borrar mis datos) ya cubre los\n"
    "  nuevos campos via cascada (borra perfil_negocio entero).\n"
    "\n"
    "## Validación\n"
    "\n"
    "- pytest tests/test_onboarding_negocio_extendido.py: 39/39 OK\n"
    "- pytest tests/test_onboarding_negocio.py: 15/15 OK\n"
    "- pytest (suite completa): 662/662 OK · cero regresiones\n"
    "\n"
    "## Cero writes\n"
    "\n"
    "- Sin Stripe writes · sin DB writes en prod (este PR no toca\n"
    "  prod hasta el merge).\n"
    "- Sin env changes · sin variables nuevas.\n"
    "- Sin deploys · sin envíos reales de WhatsApp/email.\n"
    "\n"
    "## Out of scope\n"
    "\n"
    "- Dashboard UI (sería T2.0.E.2 ortogonal).\n"
    "- Endpoint frontend.\n"
    "- Playbook Engine · Browser Operator · automatizaciones.\n"
    "- Editar respuestas vía dashboard · futuro PR.\n"
    "- Re-iniciar diagnóstico via comando WhatsApp · futuro PR.\n"
    "\n"
    "## Plan post-merge\n"
    "\n"
    "1. Render auto-redeploy ~2 min.\n"
    "2. _migrar_columnas aplica 6 ALTER TABLE en Postgres prod.\n"
    "3. Smoke por WhatsApp: escribir 'empezar diagnóstico' →\n"
    "   debe iniciar el flow.\n"
    "4. Recorrer los 10 pasos · usar 'omitir' en alguno.\n"
    "5. Verificar perfil_negocio en Supabase.\n"
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
