"""
Genera Reporte_Cierre_T13_2026-05-02.pdf — reporte formal de cierre de T1.3.
No toca archivos del proyecto. No envia datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\Reporte_Cierre_T13_2026-05-02.pdf"

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="TitleBig", parent=styles["Title"], fontSize=22, leading=26,
    spaceAfter=8, textColor=colors.HexColor("#111111"),
))
styles.add(ParagraphStyle(
    name="Subtitle", parent=styles["Normal"], fontSize=11, leading=15,
    textColor=colors.HexColor("#374151"), spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="MetaTop", parent=styles["Normal"], fontSize=9, leading=12,
    textColor=colors.HexColor("#555555"), spaceAfter=18,
))
styles.add(ParagraphStyle(
    name="Banner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#065f46"), backColor=colors.HexColor("#ecfdf5"),
    borderPadding=8, borderColor=colors.HexColor("#10b981"), borderWidth=0.6,
    leftIndent=2, rightIndent=2, spaceBefore=4, spaceAfter=14,
))
styles.add(ParagraphStyle(
    name="WarnBanner", parent=styles["Normal"], fontSize=10, leading=14,
    textColor=colors.HexColor("#7c2d12"), backColor=colors.HexColor("#fff7ed"),
    borderPadding=8, borderColor=colors.HexColor("#f97316"), borderWidth=0.6,
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
    name="Body", parent=styles["BodyText"], fontSize=9.5, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=6, textColor=colors.HexColor("#222222"),
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


# ─────────────────────────────────────────────────────────────────────────────


story = []

story.append(Paragraph(
    "T1.3 — Stripe → backend de créditos", styles["TitleBig"]))
story.append(Paragraph(
    "Reporte de cierre formal", styles["Subtitle"]))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-02 · Status: <b>cerrado funcionalmente</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Conclusión:</b> T1.3 está cerrado funcionalmente. Premium +100 "
    "validado end-to-end con compra real (saldo 70 → 170). Stripe Webhooks "
    "entregando 200 OK al endpoint del landing. Páginas legales activas y "
    "configuradas en Stripe. Recomendación: 24–48h de soak antes de tocar "
    "más cosas; T1.3.F aplazado."
))

# ── 1. Resumen ejecutivo ───────────────────────────────────────────────────

story.append(H1("1. Resumen ejecutivo"))

story.append(H2("Gap que resolvió T1.3"))
story.append(P(
    "Antes de T1.3, el webhook de Stripe llegaba a la landing "
    "(<i>https://www.usadona.com/api/webhook</i>) y el landing solo "
    "verificaba la firma y enviaba el welcome WhatsApp. <b>No</b> contactaba "
    "al backend, así que las suscripciones que los usuarios pagaban no se "
    "reflejaban en la base de datos del backend ni acreditaban créditos. "
    "El usuario veía 'saldo: 0' después de pagar."
))

story.append(H2("Estado final"))
story.extend(bullets([
    "<b>Premium ($20/mes → 100 créditos):</b> validado end-to-end con "
    "compra real. Saldo 70 → 170, Δ = +100 exacto.",
    "Stripe Webhooks dashboard muestra el endpoint activo, "
    "checkout.session.completed entregado en HTTP 200 OK.",
    "Páginas legales /soporte, /politica-de-privacidad y "
    "/terminos-y-condiciones configuradas en Stripe.",
    "<b>Pro ($40/mes → 500 créditos):</b> implementado y testeado en "
    "suite, pendiente prueba real con compra.",
]))

# ── 2. PRs incluidos ───────────────────────────────────────────────────────

story.append(H1("2. PRs / commits incluidos"))

story.append(make_table([
    ["#", "Rama", "Commit feat", "Mergeado en"],
    ["#13", "pr/t1.3.a-suscripcion-stripe-modelos", "83a5cda", "5d41c1a"],
    ["#14", "pr/t1.3.b-creditos-de-plan-helper", "e4e39f1", "8b77b8c"],
    ["#15", "pr/t1.3.c-procesar-evento-suscripcion", "5e00393", "0088872"],
    ["#16", "pr/t1.3.d-internal-stripe-event", "4f5c9ef", "abf26b1"],
    ["#17", "pr/t1.3.e-bridge-landing-backend", "45da6a1", "3563c2c"],
    ["#18", "pr/legal-pages-stripe", "50b9cbf", "c46987c"],
], col_widths=[0.5*inch, 3.0*inch, 1.0*inch, 1.0*inch]))

story.append(H2("Alcance de cada PR"))
story.extend(bullets([
    "<b>T1.3.A — Modelos + migración</b>: tablas suscripcion_stripe y "
    "evento_stripe_procesado + Alembic 002. 7 tests.",
    "<b>T1.3.B — Helper creditos_de_plan + env vars</b>: "
    "STRIPE_CREDITOS_PREMIUM/PRO con fail-fast en producción. 20 tests.",
    "<b>T1.3.C — procesar_evento_suscripcion + idempotencia</b>: "
    "dispatcher de 4 tipos de evento Stripe con triple defensa de "
    "idempotencia. 33 tests.",
    "<b>T1.3.D — Endpoint /internal/stripe-event con HMAC</b>: validación "
    "HMAC-SHA256 + clasificación HTTP 200/400/401/500. 26 tests.",
    "<b>T1.3.E — Bridge landing → backend</b>: helper internal-bridge.ts "
    "+ integración en route.ts. Build OK.",
    "<b>Páginas legales</b>: /soporte, /politica-de-privacidad, "
    "/terminos-y-condiciones en español. Footer del landing actualizado.",
]))

# ── 3. Arquitectura final ──────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Arquitectura final"))

story.append(CODE(
    "Stripe Dashboard\n"
    "    │\n"
    "    │ POST {body, stripe-signature}\n"
    "    ▼\n"
    "Vercel · landing.usadona.com/api/webhook\n"
    "    1. constructEvent(body, sig, STRIPE_WEBHOOK_SECRET)\n"
    "    2. switch event.type → welcome WhatsApp\n"
    "    3. reenviarEventoStripeABackend(event):\n"
    "       body = JSON.stringify(event)\n"
    "       sig  = HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET).hex\n"
    "       POST {body, X-Internal-Signature: sig}\n"
    "    4. bridge.ok=true → 200 a Stripe\n"
    "       bridge.ok=false → 500 a Stripe (forzar retry)\n"
    "                                │\n"
    "                                ▼\n"
    "Render · dona-agent.onrender.com/internal/stripe-event\n"
    "    1. _verificar_firma_interna(body, sig) con compare_digest\n"
    "       → 401 si falla\n"
    "    2. json.loads(body) → evento dict\n"
    "       → 400 si malformado\n"
    "    3. procesar_evento_suscripcion(evento):\n"
    "       - dedupe por event.id (EventoStripeProcesado)\n"
    "       - dispatch a 1 de 4 handlers\n"
    "       - acreditar() en invoice.payment_succeeded\n"
    "    4. handled=True → 200\n"
    "       sub_no_persistida en invoice → 500 (race retryable)\n"
    "                                │\n"
    "                                ▼\n"
    "PostgreSQL\n"
    "    saldo_creditos.saldo            ← +creditos_mensuales\n"
    "    transacciones_credito           ← fila + stripe_session_id\n"
    "    suscripcion_stripe.ultimo_invoice_acreditado ← invoice.id\n"
    "    evento_stripe_procesado.event_id ← marca evento procesado"
))

# ── 4. Seguridad ───────────────────────────────────────────────────────────

story.append(H1("4. Seguridad"))

story.append(H2("Secretos y variables"))
story.append(make_table([
    ["Variable", "Función", "Donde"],
    ["STRIPE_WEBHOOK_SECRET", "Verificación de firma Stripe en landing",
     "Vercel + Render"],
    ["INTERNAL_BRIDGE_SECRET", "HMAC compartido landing↔backend",
     "Vercel + Render (mismo valor)"],
    ["STRIPE_CREDITOS_PREMIUM", "Créditos por plan Premium", "Render"],
    ["STRIPE_CREDITOS_PRO", "Créditos por plan Pro", "Render"],
    ["BACKEND_URL", "URL del backend para el bridge", "Vercel"],
], col_widths=[2.2*inch, 2.8*inch, 1.5*inch]))

story.append(H2("Validación criptográfica"))
story.extend(bullets([
    "<b>Stripe → Landing:</b> stripe.webhooks.constructEvent valida firma "
    "con STRIPE_WEBHOOK_SECRET (esquema oficial sobre body crudo + tolerancia "
    "de timestamp).",
    "<b>Landing → Backend:</b> HMAC-SHA256 sobre el body JSON exacto. Header "
    "X-Internal-Signature. Backend usa hmac.compare_digest (resistente a "
    "timing attacks).",
    "<b>Fail-fast al import:</b> agent.billing y agent.main levantan "
    "RuntimeError si las variables faltan en producción. El deploy aborta "
    "antes de servir tráfico.",
]))

story.append(H2("Idempotencia · 3 niveles"))
story.append(make_table([
    ["Nivel", "Llave", "Tabla"],
    ["1", "event.id", "evento_stripe_procesado"],
    ["2", "invoice.id (solo invoice.payment_succeeded)",
     "suscripcion_stripe.ultimo_invoice_acreditado"],
    ["3", "stripe_session_id (= invoice_id)", "transacciones_credito"],
], col_widths=[0.5*inch, 3.5*inch, 2.5*inch]))

story.append(H2("No secretos en repo"))
story.extend(bullets([
    ".env.example documenta nombres y descripciones; nunca valores.",
    "Las variables se configuraron directamente en Render y Vercel.",
    "Ningún PR de T1.3 contiene literales de secret.",
]))

# ── 5. DB / modelos ────────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("5. DB / modelos nuevos"))

story.append(H2("SuscripcionStripe (tabla suscripcion_stripe, PK subscription_id)"))
story.append(make_table([
    ["Columna", "Tipo", "Notas"],
    ["subscription_id", "String(200)", "PK · sub_xxx de Stripe"],
    ["telefono", "String(50)", "Indexado · sin '+'"],
    ["customer_id", "String(200)", "Indexado · cus_xxx"],
    ["plan_codigo", "String(50)", "premium o pro"],
    ["price_id", "String(200)", "price_xxx de Stripe"],
    ["status", "String(40)", "active / past_due / canceled"],
    ["creditos_mensuales", "Integer", "Snapshot al crear"],
    ["ultimo_invoice_acreditado", "String(200)", "Llave de idempotencia"],
    ["creado / actualizado", "DateTime", "Auto-poblados"],
], col_widths=[2.2*inch, 1.3*inch, 3.0*inch]))

story.append(H2("EventoStripeProcesado (tabla evento_stripe_procesado, PK event_id)"))
story.append(make_table([
    ["Columna", "Tipo", "Notas"],
    ["event_id", "String(200)", "PK · evt_xxx de Stripe"],
    ["tipo", "String(80)", "Indexado · checkout.session.completed, etc."],
    ["recibido_en", "DateTime", "Auto-poblado"],
], col_widths=[1.5*inch, 1.3*inch, 3.7*inch]))

story.append(H2("Relación con tablas existentes"))
story.extend(bullets([
    "<b>SaldoCreditos.saldo</b>: incrementado por acreditar() en cada "
    "invoice.payment_succeeded. Renovaciones suman, no resetean.",
    "<b>TransaccionCredito</b>: cada acreditación deja audit trail con "
    "delta=+N, razón y stripe_session_id=invoice.id.",
    "<b>Migración</b>: alembic/versions/002_suscripcion_stripe.py. "
    "Backup: inicializar_db() crea las tablas vía metadata.create_all().",
]))

# ── 6. Reglas de negocio ───────────────────────────────────────────────────

story.append(H1("6. Reglas de negocio confirmadas"))
story.append(make_table([
    ["Regla", "Implementación"],
    ["Premium = 100 créditos/mes",
     "STRIPE_CREDITOS_PREMIUM=100 en Render"],
    ["Pro = 500 créditos/mes",
     "STRIPE_CREDITOS_PRO=500 en Render"],
    ["Créditos acumulables (no resetean)",
     "acreditar() hace saldo += N"],
    ["Cancelación NO borra créditos",
     "_procesar_subscription_deleted solo cambia status='canceled'"],
    ["Bridge falla → 500 a Stripe (retry)",
     "route.ts retorna 500 si bridge.ok=false"],
    ["Race invoice/checkout → 500 retryable",
     "Solo en invoice.payment_succeeded"],
    ["Otros handled=False → 200",
     "Backend no fuerza retry de eventos no recuperables"],
    ["Stripe Dashboard apunta al landing",
     "T1.3.F NO ejecutado · landing es receptor canónico"],
], col_widths=[3.0*inch, 3.5*inch]))

# ── 7. Evidencia de tests ──────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("7. Evidencia de tests"))

story.append(H2("Tests automatizados (suite Python)"))
story.append(make_table([
    ["PR", "Tests nuevos", "Suite total tras merge"],
    ["T1.3.A", "7", "475"],
    ["T1.3.B", "20", "488"],
    ["T1.3.C", "33", "528"],
    ["T1.3.D", "26", "554"],
    ["T1.3.E", "0 (TS, sin suite)", "554"],
    ["Legal", "0 (UI estática)", "554"],
], col_widths=[1.0*inch, 2.5*inch, 3.0*inch]))

story.append(P(
    "<b>Total al cierre: 554 tests passing en agente (pytest).</b>"
))

story.append(H2("Validación landing"))
story.extend(bullets([
    "npx tsc --noEmit: 0 errores en archivos nuevos/modificados.",
    "npm run lint: 16 problemas preexistentes; 0 nuevos por T1.3.",
    "npm run build: ✓ Compiled successfully · 15/15 static pages.",
]))

story.append(H2("Prueba real end-to-end (la que cuenta)"))
story.extend(bullets([
    "Compra real Premium desde https://www.usadona.com#pricing",
    "Saldo del teléfono <b>antes</b>: 70 créditos.",
    "Saldo del teléfono <b>después</b> (dona saldo): <b>170 créditos</b>. "
    "Δ = +100, exacto.",
    "Stripe Webhooks Dashboard: checkout.session.completed entregado en "
    "HTTP <b>200 OK</b>.",
    "URL del webhook en Stripe: <i>https://www.usadona.com/api/webhook</i> "
    "(landing, no backend — esperado).",
]))

# ── 8. Riesgos y monitoreo ─────────────────────────────────────────────────

story.append(H1("8. Riesgos pendientes y monitoreo (24–48h)"))

story.append(H2("Monitoreo activo recomendado"))
story.extend(bullets([
    "<b>Stripe Webhooks Dashboard</b>: vigilar el endpoint del landing. "
    "Cualquier evento con status distinto a 200 (especialmente 500 "
    "sostenidos) es señal de alerta.",
    "<b>Vercel logs del landing</b>: filtrar por [BRIDGE] o "
    "bridge_failed.",
    "<b>Render logs del backend</b>: filtrar por /internal/stripe-event. "
    "Vigilar signature_invalid (401) y processing_error (500).",
]))

story.append(H2("Riesgos abiertos"))
story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación / Plan"],
    ["Welcome WhatsApp duplicado en retry", "Bajo",
     "Aceptable; user recibe 2-3 welcomes en minutos"],
    ["Pro +500 sin probar con compra real", "Medio",
     "Programar prueba con $40 (real o test mode)"],
    ["Renovación mensual no observada", "Medio",
     "Vigilar Render logs en ~30 días"],
    ["hola@usadona.com como soporte", "Bajo",
     "Confirmar que se monitorea"],
    ["creditos_mensuales es snapshot al crear", "Info",
     "Por diseño; suscripciones existentes mantienen valor"],
], col_widths=[2.5*inch, 0.9*inch, 3.0*inch]))

# ── 9. Recomendación ───────────────────────────────────────────────────────

story.append(H1("9. Recomendación"))

story.append(BANNER(
    "<b>T1.3 cerrado funcionalmente.</b> Implementación, tests, despliegue "
    "y validación end-to-end con tráfico real (Premium +100) completos. El "
    "gap inicial está resuelto."
))

story.append(WARN(
    "<b>NO ejecutar T1.3.F</b> (mover Stripe Dashboard URL al backend). "
    "Pros: elimina un hop. Contras: requiere cambio en Stripe Dashboard, "
    "retira el bridge HMAC ya validado, quita una capa de defensa en "
    "profundidad. Hacerlo solo después de <b>semanas</b> de operación "
    "estable del bridge actual."
))

story.append(H2("Próximos pasos sugeridos (en orden)"))
story.extend(bullets([
    "<b>24–48h de soak</b>: monitorear logs sin tocar código.",
    "<b>Prueba Pro +500</b> con compra real o Stripe test mode.",
    "<b>Observar primer ciclo de renovación</b> (~30 días) para confirmar "
    "que invoice.payment_succeeded acredita correctamente el segundo mes.",
    "Avanzar al siguiente bloque de Phase 1 del plan v2.1.",
]))

# ── 10. Checklist final ────────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("10. Checklist final"))

story.append(make_table([
    ["Item", "Status"],
    ["Legal URLs configuradas en Stripe Dashboard", "✓"],
    ["https://www.usadona.com/soporte carga 200", "✓"],
    ["https://www.usadona.com/politica-de-privacidad carga 200", "✓"],
    ["https://www.usadona.com/terminos-y-condiciones carga 200", "✓"],
    ["Premium +100 validado con compra real", "✓"],
    ["Webhook responde 200 OK en Stripe Dashboard", "✓"],
    ["dona saldo refleja saldo correcto post-compra (70→170)", "✓"],
    ["Branches pr/t1.3.* mergeadas a main (#13–#17)", "✓"],
    ["Branch pr/legal-pages-stripe mergeada a main (#18)", "✓"],
    ["Branches feature borradas (housekeeping local)",
     "Pendiente · owner decide"],
    ["STRIPE_WEBHOOK_SECRET en Render y Vercel", "✓"],
    ["INTERNAL_BRIDGE_SECRET en Render y Vercel (mismo valor)", "✓"],
    ["STRIPE_CREDITOS_PREMIUM=100 en Render", "✓"],
    ["STRIPE_CREDITOS_PRO=500 en Render", "✓"],
    ["BACKEND_URL en Vercel", "✓"],
    ["Sin secretos commiteados en el repo", "✓"],
    ["Pro +500 probado con compra real", "Pendiente"],
    ["Renovación de segundo periodo observada", "Pendiente (~30 días)"],
], col_widths=[5.0*inch, 1.5*inch]))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Reporte generado el 2026-05-02 por Claude Code (Opus 4.7) en sesión "
    "con el owner. No incluye cambios de código ni operaciones de "
    "despliegue. Solo documentación de cierre."
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.3 — Reporte de cierre formal",
    author="Claude Code", subject="Reporte de cierre formal de T1.3",
)
doc.build(story)
print(f"OK: {OUTPUT}")
