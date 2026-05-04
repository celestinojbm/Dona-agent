"""
Genera Resumen_T14C_Usuario_Resumen_2026-05-03.pdf en docs/auditorias/.
Resumen del endpoint backend /internal/usuario-resumen (T1.4.C, commit 9030bec).

No toca archivos del proyecto. No envia datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

OUTPUT = r"C:\Users\celes\Dona-agent\docs\auditorias\Resumen_T14C_Usuario_Resumen_2026-05-03.pdf"

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
    "T1.4.C — Endpoint /internal/usuario-resumen", styles["TitleBig"]))
story.append(Paragraph(
    "Backend read-only para datos del dashboard · HMAC interno",
    styles["Subtitle"],
))
story.append(Paragraph(
    "Owner: Celestino · 2026-05-03 · Branch <b>pr/t1.4.c-usuario-resumen</b> · "
    "Commit <b>9030bec</b>",
    styles["MetaTop"],
))

story.append(BANNER(
    "<b>Status:</b> Branch pusheado a GitHub. 21 tests nuevos verdes. "
    "Suite total <b>575 passed</b> (554 → 575). Read-only verificado por "
    "test que cuenta filas antes/después. <b>NO mergeado a main.</b>"
))

# ── 1. Archivos modificados ────────────────────────────────────────────────

story.append(H1("1. Archivos modificados / creados"))
story.append(make_table([
    ["Archivo", "Δ líneas", "Tipo", "Rol"],
    ["agent/main.py", "+151 / -0", "M",
     "Endpoint POST /internal/usuario-resumen + comentario de diseño"],
    ["tests/test_main_internal_usuario_resumen.py", "+479 / -0", "A",
     "21 tests cubriendo auth, JSON, payload, 404, casos felices, "
     "estados, read-only, regresión"],
    ["", "", "", ""],
    ["TOTAL", "+630 / -0", "2 archivos", ""],
], col_widths=[2.7*inch, 0.8*inch, 0.5*inch, 2.5*inch]))

# ── 2. Endpoint creado ─────────────────────────────────────────────────────

story.append(H1("2. Endpoint creado"))

story.append(H2("Ruta y firma"))
story.append(CODE(
    "POST /internal/usuario-resumen\n"
    "Headers:\n"
    "  Content-Type: application/json\n"
    "  X-Internal-Signature: <hex(HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET))>\n"
    "Body: {\"subscription_id\": \"sub_xxx\"}"
))

story.append(H2("Códigos HTTP"))
story.append(make_table([
    ["Status", "Cuándo"],
    ["401", "Header X-Internal-Signature ausente o firma inválida"],
    ["400", "JSON malformado, no es objeto, o falta subscription_id"],
    ["404", "subscription_id no existe en suscripcion_stripe"],
    ["200", "Caso feliz: JSON con la estructura del response"],
], col_widths=[0.7*inch, 5.5*inch]))

# ── 3. Formato input/output ────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("3. Formato input / output"))

story.append(H2("Input"))
story.append(CODE(
    "{\n"
    "  \"subscription_id\": \"sub_xxx\"\n"
    "}"
))

story.append(H2("Output (200)"))
story.append(CODE(
    "{\n"
    "  \"usuario\": {\n"
    "    \"id\": \"sub_xxx\",            // = subscription_id\n"
    "    \"email\": null,              // backend no lo persiste; landing\n"
    "                                  //   merge con session.user.email\n"
    "    \"telefono\": \"14076936023\"\n"
    "  },\n"
    "  \"creditos\": {\n"
    "    \"saldo_actual\": 170,\n"
    "    \"creditos_mensuales\": 100,  // del plan vigente\n"
    "    \"ultimo_movimiento\": {       // null si no hay transacciones\n"
    "      \"delta\": 100,\n"
    "      \"razon\": \"Renovación premium (100 créditos)\",\n"
    "      \"saldo_resultante\": 170,\n"
    "      \"creado\": \"2026-05-02T...\"\n"
    "    }\n"
    "  },\n"
    "  \"suscripcion\": {\n"
    "    \"estado\": \"active\",          // active / past_due / canceled\n"
    "    \"plan\": \"premium\",           // premium / pro\n"
    "    \"stripe_customer_id\": \"cus_xxx\",\n"
    "    \"stripe_subscription_id\": \"sub_xxx\",\n"
    "    \"current_period_end\": null,    // Stripe SDK desde landing\n"
    "    \"cancel_at_period_end\": false, // Stripe SDK desde landing\n"
    "    \"actualizado\": \"2026-05-02T...\"\n"
    "  },\n"
    "  \"transacciones_recientes\": [   // hasta 10, más reciente primero\n"
    "    {\"delta\": 100, \"razon\": \"...\",\n"
    "     \"saldo_resultante\": 170, \"creado\": \"...\"}\n"
    "  ],\n"
    "  \"resumen\": {\n"
    "    \"puede_cancelar\": true,      // (estado == active)\n"
    "    \"dashboard_ready\": true\n"
    "  }\n"
    "}"
))

# ── 4. Cómo se valida HMAC ─────────────────────────────────────────────────

story.append(H1("4. Cómo se valida HMAC"))

story.append(P(
    "Reusa la función <b>_verificar_firma_interna(body, sig_header)</b> de "
    "agent/main.py (creada en T1.3.D para /internal/stripe-event). El "
    "patrón es idéntico:"
))

story.append(CODE(
    "def _verificar_firma_interna(body: bytes, sig_header: str) -> bool:\n"
    "    secret = os.getenv(\"INTERNAL_BRIDGE_SECRET\", \"\").strip()\n"
    "    if not secret or not sig_header:\n"
    "        return False\n"
    "    esperado = hmac.new(\n"
    "        secret.encode(\"utf-8\"), body, hashlib.sha256\n"
    "    ).hexdigest()\n"
    "    return hmac.compare_digest(esperado, sig_header.strip())"
))

story.append(P(
    "Se firma el <b>body crudo exacto</b> antes de parsear JSON. Si la "
    "firma falla, el endpoint responde 401 sin tocar el body. "
    "<i>compare_digest</i> evita timing oracles."
))

story.append(H2("Decisión: reusar INTERNAL_BRIDGE_SECRET"))
story.extend(bullets([
    "Ya existe en Vercel y Render (mismo valor, validado en T1.3.E).",
    "Ya está documentada en .env.example.",
    "Reduce superficie de configuración.",
    "El endpoint de T1.4.C tiene el mismo perfil de riesgo que "
    "/internal/stripe-event (interno, sin acceso público), justifica "
    "compartir secret.",
]))

# ── 5. Identificador elegido ──────────────────────────────────────────────

story.append(H1("5. Identificador elegido: subscription_id"))

story.append(make_table([
    ["Opción", "Decisión"],
    ["stripe_customer_id (cus_xxx)",
     "Rechazada · 1 customer puede tener varias subs históricas, ambigua"],
    ["email", "Rechazada · backend no persiste email del Stripe customer; "
     "habría que aceptar email + hacer lookup costoso vía Stripe SDK"],
    ["telefono", "Rechazada · expondría el teléfono en el caller; "
     "el landing no lo conoce sin un round-trip extra"],
    ["user_id", "N/A · no existe tabla 'usuarios' en backend"],
    ["<b>subscription_id (sub_xxx)</b>",
     "<b>ELEGIDA</b> · PK de SuscripcionStripe (lookup O(1)). La sesión "
     "NextAuth ya lo tiene tras T1.4.B. Forjar IDs falla el HMAC."],
], col_widths=[1.8*inch, 4.7*inch]))

# ── 6. Comandos ejecutados ─────────────────────────────────────────────────

story.append(PageBreak())
story.append(H1("6. Comandos ejecutados y resultado"))

story.append(make_table([
    ["Comando", "Resultado"],
    ["pytest tests/test_main_internal_usuario_resumen.py -x",
     "21 passed in 39.19s"],
    ["pytest --tb=short -q (suite completa)",
     "575 passed in 305.63s · Δ +21 vs baseline 554"],
], col_widths=[3.0*inch, 3.5*inch]))

story.append(H2("Cobertura de tests (21 nuevos)"))

story.append(make_table([
    ["Clase", "N°", "Cubre"],
    ["TestAuth", "5",
     "Sin header, header vacío, firma inválida, secret distinto, "
     "body modificado tras firmar"],
    ["TestJsonInvalido", "3", "Body no JSON, array, vacío"],
    ["TestPayloadInvalido", "3",
     "Sin subscription_id, vacío, whitespace"],
    ["TestSubInexistente", "1", "404 con subscription_id desconocido"],
    ["TestRespuestaCompleta", "3",
     "Sin saldo, con saldo+transacciones, límite de 10"],
    ["TestEstadosSuscripcion", "2",
     "canceled / past_due → puede_cancelar=false"],
    ["TestReadOnly", "1",
     "Contar filas antes/después → cero escrituras"],
    ["TestLegacyEndpointsIntactos", "2",
     "/internal/stripe-event y /webhook/stripe siguen registrados"],
    ["TestEstructuraEsperada", "1",
     "telefono presente en respuesta"],
], col_widths=[2.3*inch, 0.4*inch, 3.8*inch]))

# ── 7. Read-only confirmado ────────────────────────────────────────────────

story.append(H1("7. Read-only confirmado"))

story.append(P(
    "Test <b>TestReadOnly::test_endpoint_no_modifica_db</b> cuenta filas "
    "en las 4 tablas relevantes (suscripcion_stripe, saldo_creditos, "
    "transacciones_credito, evento_stripe_procesado) <b>antes</b> y "
    "<b>después</b> de 3 invocaciones consecutivas del endpoint. Assert "
    "antes == después."
))

story.append(P(
    "Implementación: el endpoint solo ejecuta <b>SELECT</b> queries dentro "
    "de un <i>async with async_session()</i>. No hay <i>session.add()</i>, "
    "<i>session.commit()</i> con cambios, <i>update()</i>, <i>insert()</i> "
    "ni <i>delete()</i>."
))

# ── 8. Riesgos abiertos ────────────────────────────────────────────────────

story.append(H1("8. Riesgos abiertos"))

story.append(make_table([
    ["Riesgo", "Severidad", "Mitigación"],
    ["INTERNAL_BRIDGE_SECRET filtrado",
     "Alta", "Rotar en Vercel y Render simultáneamente"],
    ["current_period_end / cancel_at_period_end no en backend",
     "Info", "El landing los obtiene de Stripe SDK en T1.4.D"],
    ["email=null en respuesta requiere merge en landing",
     "Info", "Documentado; el landing tiene session.user.email"],
    ["Sin rate limiting al endpoint",
     "Bajo", "Solo accesible internamente con HMAC; brute force "
     "del HMAC es computacionalmente infactible"],
    ["DB query sin límite global de tiempo",
     "Bajo", "Las queries son lookups por PK (saldo, sub) o LIMIT 10 "
     "(transacciones); riesgo bajo de timeout"],
], col_widths=[2.7*inch, 0.9*inch, 2.9*inch]))

# ── 9. Próximos pasos T1.4.D ──────────────────────────────────────────────

story.append(H1("9. Próximos pasos para T1.4.D"))

story.append(P(
    "T1.4.D crea el proxy en el landing: "
    "<i>landing/app/api/dashboard-data/route.ts</i>."
))

story.extend(bullets([
    "Tomar <i>subscriptionId</i> de la sesión NextAuth (server-side).",
    "Reutilizar el helper de T1.3.E <i>landing/lib/internal-bridge.ts</i> "
    "extendido con un método <i>fetchUsuarioResumen(subscriptionId)</i> "
    "que firma con HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET) y POSTea a "
    "<i>BACKEND_URL/internal/usuario-resumen</i>.",
    "Recibir el JSON del backend.",
    "Hacer fetch en paralelo a Stripe SDK desde el landing para obtener "
    "<i>current_period_end</i> y <i>cancel_at_period_end</i>.",
    "Mergear ambas fuentes (backend + Stripe + session.email).",
    "Retornar al cliente.",
]))

story.append(WARN(
    "<b>Importante para T1.4.D:</b> el landing nunca debe exponer "
    "INTERNAL_BRIDGE_SECRET ni STRIPE_SECRET_KEY al cliente. Toda esta "
    "lógica corre <b>server-side</b> en route.ts."
))

story.append(H2("Restricciones respetadas"))
story.extend(bullets([
    "✓ NO se hizo deploy.",
    "✓ NO se mergeó a main.",
    "✓ NO se modificó producción.",
    "✓ NO se expusieron secretos.",
    "✓ NO se creó endpoint público (es /internal/, requiere HMAC).",
    "✓ NO se escribió en la base.",
    "✓ Tests cubren auth, validación, casos felices y read-only.",
    "✓ NO requiere env var nueva (reusa INTERNAL_BRIDGE_SECRET).",
]))

# ── Footer ─────────────────────────────────────────────────────────────────

story.append(Spacer(1, 0.3 * inch))
story.append(C(
    "Generado por Claude Code · Modelo Opus 4.7 · Sesión 2026-05-03 · "
    "Repo: Dona-agent · Branch: pr/t1.4.c-usuario-resumen · HEAD: 9030bec"
))


# ── Build ──────────────────────────────────────────────────────────────────


doc = SimpleDocTemplate(
    OUTPUT, pagesize=LETTER,
    leftMargin=0.7*inch, rightMargin=0.7*inch,
    topMargin=0.6*inch, bottomMargin=0.6*inch,
    title="T1.4.C — Endpoint /internal/usuario-resumen",
    author="Claude Code", subject="Resumen de implementación T1.4.C",
)
doc.build(story)
print(f"OK: {OUTPUT}")
