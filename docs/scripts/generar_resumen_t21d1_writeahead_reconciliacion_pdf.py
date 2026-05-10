"""
Genera Resumen_T21D1_WriteAhead_Reconciliacion_2026-05-06.pdf · cierre
del fix T2.1.D.1 sobre el riesgo residual de doble registro de cobro
sin reserva. Cambios mínimos sobre T2.1.D.
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
    r"\Resumen_T21D1_WriteAhead_Reconciliacion_2026-05-06.pdf"
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
    "T2.1.D.1 · Write-ahead reservation + reconciliación post-crash",
    styles["TitleBig"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-06 · branch "
    "<i>pr/t2.1.d-credit-reservations-audit-pruning</i> · fix mínimo "
    "sobre T2.1.D · sin deploy · sin migraciones en prod · sin "
    "borrado de datos.",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Mitigación del riesgo residual del PR T2.1.D:</b> el "
    "<i>crash entre billing.cobrar() y el INSERT en "
    "automation_reservas_credito</i> ya no puede dejar saldo "
    "descontado sin reserva visible. Se invirtió el orden (la fila "
    "ahora se persiste como <i>'preparing'</i> ANTES del cobro) y "
    "se sumó una función de reconciliación que repara cualquier "
    "fila <i>preparing</i> orfana en base a la huella "
    "<i>TransaccionCredito.job_id=accion_id</i>. Cubierto por 8 "
    "tests nuevos."
))

# ── 1. Origen del riesgo y opciones evaluadas ─────────────────────────

story.append(H1("1. Origen del riesgo y opciones evaluadas"))

story.append(P(
    "El PR T2.1.D dejó documentado un riesgo residual catalogado "
    "como <b>severidad Baja</b>: si la app crashea entre "
    "<i>billing.cobrar()</i> (sesión A, ya commitada) y "
    "<i>_persistir_reserva_nueva()</i> (sesión B), el saldo queda "
    "descontado y la <i>TransaccionCredito</i> persistida, pero la "
    "fila en <i>automation_reservas_credito</i> no existe."))

story.append(P(
    "El usuario pidió formalmente resolverlo y propuso tres "
    "opciones:"))

story.append(make_table([
    ["Opción", "Idea", "Decisión"],
    ["1", "Crear reserva en <i>'preparing'</i> ANTES de cobrar y "
     "completarla a <i>'pending'</i> después del cobro.",
     "<b>Elegida</b> · combinada con (2)."],
    ["2", "Reconciliar a posteriori detectando "
     "<i>TransaccionCredito</i> sin reserva asociada.",
     "<b>Elegida</b> · como safety net del happy path."],
    ["3", "Demostrar que cobrar + crear reserva es una transacción "
     "atómica.",
     "<b>Descartada</b>: <i>cobrar()</i> abre su propia sesión y "
     "commitea antes de retornar · NO comparte transacción con la "
     "sesión que inserta la reserva."],
], col_widths=[0.6*inch, 4.2*inch, 2.0*inch]))

# ── 2. Diseño del fix ────────────────────────────────────────────────

story.append(H1("2. Diseño del fix"))

story.append(H2("2.1 Nuevo flujo de reservar()"))

story.append(CODE(
    "async def reservar(accion_id, telefono, creditos, razon):\n"
    "    # 1. Lookup idempotente · si existe pending/confirmed\n"
    "    #    devolver tal cual.  Si existe 'preparing' → reconciliar\n"
    "    #    inline antes de decidir (auto-reparación del reintento\n"
    "    #    del worker).\n"
    "    existing = await obtener_reserva(accion_id)\n"
    "    if existing and existing['estado'] == 'preparing':\n"
    "        existing = await reconciliar_accion(accion_id,\n"
    "                                            max_edad_segundos=0)\n"
    "    if existing and existing['estado'] in ('pending','confirmed'):\n"
    "        return existing\n"
    "\n"
    "    if creditos == 0:\n"
    "        return _persistir_reserva(..., estado='pending')\n"
    "\n"
    "    # 2. Write-ahead · fila 'preparing' antes de tocar saldo\n"
    "    await _persistir_reserva(..., estado='preparing')\n"
    "\n"
    "    # 3. Cobro real · atómico en sesión propia de billing\n"
    "    try:\n"
    "        await billing.cobrar(..., job_id=accion_id)\n"
    "    except SaldoInsuficienteError:\n"
    "        await _actualizar_estado(accion_id, 'failed')\n"
    "        await registrar_evento('credits_reservation_failed', ...)\n"
    "        raise CreditosInsuficientesError(...)\n"
    "\n"
    "    # 4. Buscar la tx que acabamos de crear y completar reserva\n"
    "    tx_id = await _ultima_tx_id_para_accion(accion_id, ...)\n"
    "    final = await _actualizar_estado(accion_id, 'pending',\n"
    "                                     transaccion_credito_id=tx_id)\n"
    "    await registrar_evento('credits_reserved', ...)\n"
    "    return final"
))

story.append(H2("2.2 Función de reconciliación"))

story.append(P(
    "<i>reconciliar_accion(accion_id)</i> repara una fila "
    "<i>'preparing'</i> que quedó huérfana tras un crash. La "
    "decisión depende de si existe una <i>TransaccionCredito</i> "
    "asociada por <i>(job_id=accion_id, telefono, delta=-creditos)</i>:"))

story.append(make_table([
    ["Escenario detectado", "Acción de reconciliación",
     "Audit emitido"],
    ["Existe tx de cobro (crash post-cobro)",
     "Avanza fila a <i>'pending'</i> + linkea "
     "<i>transaccion_credito_id</i>",
     "<i>credits_reservation_reconciled</i> con resultado "
     "<i>promoted_to_pending</i>"],
    ["No existe tx y la fila tiene edad ≥ <i>max_edad_segundos</i>",
     "Marca <i>'failed'</i> (saldo nunca se movió)",
     "<i>credits_reservation_reconciled</i> con resultado "
     "<i>marked_failed</i>"],
    ["No existe tx pero la fila es reciente (&lt; "
     "<i>max_edad_segundos</i>)",
     "No toca · la operación puede estar legítimamente en vuelo "
     "en otro worker",
     "(ninguno)"],
], col_widths=[2.2*inch, 2.7*inch, 1.9*inch]))

story.append(P(
    "<i>reconciliar_reservas()</i> hace el mismo trabajo en batch · "
    "soporta <i>dry_run</i> para previsualizar conteos sin tocar "
    "estado ni emitir audit. <i>limit</i> tope (1..5000) y "
    "<i>max_edad_segundos</i> default 120s."))

story.append(H2("2.3 Por qué la huella es deterministic"))

story.append(P(
    "<i>billing.cobrar()</i> inserta la fila en "
    "<i>transacciones_credito</i> con <i>job_id</i>, <i>telefono</i> "
    "y <i>delta=-creditos</i>. T2.1.D ya pasa "
    "<i>job_id=accion_id</i>. La combinación <i>(job_id, telefono, "
    "delta)</i> es única para esta acción (y, en el caso "
    "extremo de duplicidad, la consulta toma la <b>más reciente por "
    "id descendente</b>, que es exactamente la del cobro previo al "
    "crash). El test "
    "<i>test_reserva_exitosa_link_transaccion_credito_id</i> "
    "valida el link en el happy path."))

# ── 3. Archivos modificados ──────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Archivos modificados"))

story.append(make_table([
    ["Archivo", "Cambio"],
    ["agent/automation/credits.py",
     "Reescrito: write-ahead (<i>preparing</i> antes del cobro), "
     "<i>reconciliar_accion()</i> y <i>reconciliar_reservas()</i>, "
     "helper <i>_ultima_tx_id_para_accion()</i>, "
     "<i>_actualizar_estado_y_tx()</i>. Sin cambios en la API "
     "pública: <i>reservar / confirmar / liberar / obtener_reserva</i> "
     "conservan su firma."],
    ["agent/automation/audit.py",
     "<i>EVENTOS_VALIDOS</i> + <i>credits_reservation_reconciled</i>."],
    ["agent/main.py",
     "GET <i>/admin/automation/credits/reconciliar/preview</i> · "
     "POST <i>/admin/automation/credits/reconciliar</i> (dry-run y "
     "ejecución · sin requerir confirm porque NO borra)."],
    ["tests/test_automation_creditos_reservas.py",
     "+ 8 tests: <i>TestReconciliacionCrashEntreCobroYReserva</i> "
     "(6) y <i>TestWriteAheadOrden</i> (2). Total ahora 27 tests."],
], col_widths=[2.4*inch, 4.4*inch]))

story.append(H2("3.1 Migraciones de schema"))
story.append(P(
    "<b>Ninguna nueva.</b> El estado <i>'preparing'</i> reutiliza la "
    "columna <i>estado VARCHAR(20)</i> existente. La columna "
    "<i>transaccion_credito_id</i> existente acepta el link. No hay "
    "<i>ALTER TABLE</i> ni nueva fila en <i>MIGRACIONES_AUTOMATION</i>. "
    "Compatible 100% con datos existentes."))

# ── 4. Cobertura nueva de tests ──────────────────────────────────────

story.append(H1("4. Cobertura de tests del fix"))

story.append(make_table([
    ["Test", "Caso simulado", "Aserción clave"],
    ["test_reconcilia_promueve_preparing_a_pending",
     "Crash post-cobro · fila preparing + tx existente",
     "estado → pending · transaccion_credito_id linkeada · "
     "saldo NO se vuelve a tocar"],
    ["test_reconcilia_marca_failed_si_no_hay_tx_y_es_vieja",
     "Crash pre-cobro · fila preparing vieja · sin tx",
     "estado → failed · saldo intacto"],
    ["test_reconcilia_no_toca_preparing_reciente",
     "Worker en vuelo · fila preparing joven",
     "estado → preparing (no se toca)"],
    ["test_reservar_post_crash_auto_reconcilia",
     "Worker reintenta ejecutar_accion tras crash",
     "reservar() devuelve pending sin re-cobrar"],
    ["test_reconciliar_emite_audit",
     "Reconciliación exitosa",
     "audit 'credits_reservation_reconciled' con "
     "resultado=promoted_to_pending"],
    ["test_reconciliar_reservas_batch_promueve_y_falla",
     "Mezcla de 3 filas: tx+preparing, vieja sin tx, joven sin tx",
     "preview cuenta correctamente · ejecución produce el estado "
     "correcto en cada una"],
    ["test_si_cobro_falla_la_fila_existe_como_failed",
     "Saldo insuficiente",
     "Existe fila (failed), no inexistente"],
    ["test_reserva_exitosa_link_transaccion_credito_id",
     "Happy path",
     "transaccion_credito_id apunta a la tx real con "
     "delta=-creditos y job_id=accion_id"],
], col_widths=[2.5*inch, 2.5*inch, 1.8*inch]))

# ── 5. Verificaciones ───────────────────────────────────────────────

story.append(H1("5. Verificaciones · comandos y resultados"))

story.append(CODE(
    "pytest tests/test_automation_creditos_reservas.py\n"
    "→ 27 passed in 20.23s · 19 previos + 8 nuevos\n\n"
    "pytest tests/test_automation_*.py\n"
    "→ 205 passed in 110.88s · 197 previos + 8 nuevos\n\n"
    "pytest\n"
    "→ 867 passed in 224.63s · 859 previos + 8 nuevos\n"
    "  0 failed · 0 regresión"
))

# ── 6. Riesgo residual final ────────────────────────────────────────

story.append(H1("6. Riesgo residual final"))

story.append(make_table([
    ["Escenario", "Estado post-fix"],
    ["Crash entre _persistir(preparing) y cobrar()",
     "fila preparing sin tx · reconciliar la marca failed (saldo "
     "intacto) · reintento natural del worker funciona"],
    ["Crash entre cobrar() y _actualizar(pending)",
     "<b>cubierto</b> · fila preparing + tx · reconciliar la "
     "promueve a pending · saldo correcto"],
    ["Crash dentro de cobrar() (commit a medias)",
     "Imposible · cobrar() usa transacción única SQL "
     "(UPDATE saldo + INSERT tx en una sesión)"],
    ["Doble cobro por reintento del worker",
     "Imposible · UNIQUE(accion_id) + auto-reconcile inline en "
     "reservar() devuelve la fila pending existente sin re-cobrar"],
    ["Reconciliar promueve fila a pending pero no hay realmente tx",
     "Imposible · la búsqueda exige tx con "
     "(job_id, telefono, delta=-creditos)"],
    ["Adversario inyecta tx con job_id falso",
     "Solo cuentas admin con acceso DB pueden insertar en "
     "transacciones_credito · fuera del modelo de amenaza"],
], col_widths=[3.6*inch, 3.4*inch]))

# ── 7. Operación · endpoints admin ──────────────────────────────────

story.append(H1("7. Operación · endpoints admin"))

story.append(CODE(
    "# Preview (dry-run · NO toca estado)\n"
    "curl -s -H \"Authorization: Bearer $ADMIN_TOKEN\" \\\n"
    "     \"$URL/admin/automation/credits/reconciliar/preview\\\n"
    "?max_edad_segundos=120&limit=500\"\n"
    "→ { dry_run: true, total_preparing, promoted_estimado,\n"
    "    marked_failed_estimado, intactas_estimado }\n\n"
    "# Ejecutar reconciliación\n"
    "curl -s -X POST -H \"Authorization: Bearer $ADMIN_TOKEN\" \\\n"
    "     \"$URL/admin/automation/credits/reconciliar\\\n"
    "?max_edad_segundos=120&limit=500\"\n"
    "→ { dry_run: false, total_preparing_inicial, promoted,\n"
    "    marked_failed, intactas }"
))

story.append(P(
    "Recomendación operativa: ejecutar reconciliación periódica "
    "(cada 5-15 min) vía cron externo o vía un job de "
    "<i>arq</i> en el worker de Render. Sin embargo, el "
    "auto-reconcile inline al inicio de <i>reservar()</i> hace que "
    "la reconciliación programada sea opcional para el happy path "
    "del reintento del worker."))

# ── 8. PR ───────────────────────────────────────────────────────────

story.append(H1("8. PR · cómo se anexa al PR T2.1.D"))

story.append(P(
    "<b>Branch:</b> "
    "<i>pr/t2.1.d-credit-reservations-audit-pruning</i> · ya "
    "pusheada · este commit se suma como <i>follow-up</i> en la "
    "misma branch antes de mergear."))

story.append(P(
    "<b>Mensaje de commit propuesto:</b>"))

story.append(CODE(
    "fix(automation): write-ahead reservation + reconciliacion\n"
    "post-crash (T2.1.D.1)\n\n"
    "Mitiga el riesgo residual de T2.1.D: crash entre billing.cobrar\n"
    "y el INSERT de la reserva podia dejar saldo descontado sin\n"
    "reserva visible.\n\n"
    "- Estado 'preparing' como write-ahead antes del cobro\n"
    "- reconciliar_accion / reconciliar_reservas (dry-run + ejecucion)\n"
    "- Audit credits_reservation_reconciled\n"
    "- 2 endpoints admin GET/POST /admin/automation/credits/reconciliar\n"
    "- 8 tests nuevos (27 total · suite completa 867 passed · 0 fail)\n\n"
    "Sin nuevas migraciones · usa columna estado VARCHAR(20)\n"
    "existente."
))

# ── 9. Próximo paso ─────────────────────────────────────────────────

story.append(H1("9. Próximo paso"))

story.append(P(
    "Con T2.1.D + T2.1.D.1 cerrados, el ciclo billing del Action "
    "Center es seguro contra reintento, crash y saldo insuficiente. "
    "El siguiente bloque natural es <b>T2.1.E</b> (scheduler "
    "periódico para detectar oportunidades) o <b>T2.2</b> (primera "
    "acción HIGH real con preview-then-commit conectado a Whapi). "
    "Recomendación: cerrar PR T2.1.D, hacer redeploy a Render y "
    "monitorear logs por ~24h antes de avanzar."))

doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
)
doc.build(story)
print(f"OK · escrito {OUTPUT}")
