"""
Genera Resumen_T010_Implementacion_2026-05-01.pdf con el resumen del PR
T0.10 Whapi webhook token obligatorio (commit 57584d4, rama
pr/whapi-webhook-token-obligatorio).

No toca archivos del proyecto. No envia datos a internet.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether,
)

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_T010_Implementacion_2026-05-01.pdf"

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="TitleBig", parent=styles["Title"], fontSize=22, leading=26,
    spaceAfter=8, textColor=colors.HexColor("#111111"),
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
    name="H1", parent=styles["Heading1"], fontSize=16, leading=20,
    spaceBefore=18, spaceAfter=8, textColor=colors.HexColor("#111111"),
))
styles.add(ParagraphStyle(
    name="H2", parent=styles["Heading2"], fontSize=13, leading=17,
    spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1f2937"),
))
styles.add(ParagraphStyle(
    name="H3", parent=styles["Heading3"], fontSize=11, leading=14,
    spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#374151"),
))
styles.add(ParagraphStyle(
    name="Body", parent=styles["BodyText"], fontSize=9.5, leading=13,
    alignment=TA_JUSTIFY, spaceAfter=6, textColor=colors.HexColor("#222222"),
))
styles.add(ParagraphStyle(
    name="BodyTight", parent=styles["BodyText"], fontSize=9, leading=12,
    alignment=TA_LEFT, spaceAfter=2, textColor=colors.HexColor("#222222"),
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
def H3(t): return Paragraph(t, styles["H3"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])
def BANNER(t): return Paragraph(t, styles["Banner"])


def bullets(items):
    return [Paragraph("&bull; " + it, styles["BulletDona"]) for it in items]


def small_table(rows, col_widths, header=True, font_size=8.5):
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", font_size),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#9ca3af")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", font_size),
    ]
    t.setStyle(TableStyle(style))
    return t


def para_rows(rows):
    return [[Paragraph(c, styles["BodyTight"]) for c in r] for r in rows]


def build_story():
    s = []

    s.append(Paragraph("T0.10 — WHAPI_WEBHOOK_TOKEN obligatorio", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de implementacion &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin merge, sin deploy. &nbsp;·&nbsp; Rama lista para revision.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Implementado y testeado.</b> 3 archivos modificados, 468 tests verde, "
        "branch <i>pr/whapi-webhook-token-obligatorio</i> en GitHub. "
        "Cierra deuda P0 latente: el endpoint /webhook con WHATSAPP_PROVIDER=whapi ya no "
        "aceptaria payloads forjados sin custom header. PR preventivo &mdash; provider activo "
        "sigue siendo Meta, asi que el deploy actual no se ve afectado."
    ))

    # ── Identificadores ────────────────────────────────────────────────
    s.append(H1("Identificadores"))
    ids_rows = [
        ["Item", "Valor"],
        ["Commit", "57584d4"],
        ["Mensaje", "fix(seguridad): WHAPI_WEBHOOK_TOKEN obligatorio en produccion (T0.10)"],
        ["Rama local", "pr/whapi-webhook-token-obligatorio"],
        ["Rama remota", "origin/pr/whapi-webhook-token-obligatorio"],
        ["Crear PR en GitHub",
         "https://github.com/celestinojbm/Dona-agent/pull/new/pr/whapi-webhook-token-obligatorio"],
        ["main local", "49978a9 (igual a origin/main, INTACTO)"],
        ["origin/main", "49978a9 (sin push de este PR a main)"],
    ]
    s.append(small_table(para_rows(ids_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # ── Archivos tocados ───────────────────────────────────────────────
    s.append(H1("Archivos tocados (los 3 autorizados)"))
    arch_rows = [
        ["Archivo", "Cambio"],
        ["agent/providers/whapi.py",
         "+ check fail-fast en ProveedorWhapi.__init__: si ENVIRONMENT=production y WHAPI_WEBHOOK_TOKEN vacio (post-.strip()) -> RuntimeError. + metodo _verificar_firma con hmac.compare_digest (timing-safe). + invocacion al inicio de parsear_webhook (rechaza con [] si firma falla). + import hmac. Lee ENVIRONMENT en cada llamada para tests con monkeypatch."],
        [".env.example",
         "+ bloque documental para WHAPI_WEBHOOK_TOKEN (obligatoria en produccion si provider=whapi). + WHAPI_WEBHOOK_HEADER opcional (default X-Webhook-Token). + nota legacy sobre WHAPI_API_URL (no usada en codigo, vestigio borrable). Sin valores reales."],
        ["tests/test_providers.py",
         "+ TestWhapiWebhookValidation con 8 tests (incluye 1 extra de header personalizable via env). + helpers _make_whapi_text_msg y _make_whapi_request."],
    ]
    s.append(small_table(para_rows(arch_rows),
                         col_widths=[4.0*cm, 13.0*cm]))
    s.append(P("<b>Total:</b> 3 archivos, +242 lineas, -0 lineas."))

    # ── Diff resumido ──────────────────────────────────────────────────
    s.append(H1("Diff resumido"))
    diff = (
        ".env.example             |  23 ++++++++\n"
        "agent/providers/whapi.py |  81 ++++++++++++++++++++++++++++\n"
        "tests/test_providers.py  | 138 +++++++++++++++++++++++++++++++++++++++++++++++\n"
        "3 files changed, 242 insertions(+)\n"
    )
    s.append(CODE(diff))

    # ── Tests corridos ────────────────────────────────────────────────
    s.append(H1("Tests ejecutados y resultado"))
    tests_rows = [
        ["Suite", "Resultado"],
        ["pytest tests/test_providers.py -x -q",
         "<b>37 passed</b> en 0.58 s (29 previos + 8 nuevos en TestWhapiWebhookValidation)"],
        ["pytest -q (suite completa)",
         "<b>468 passed</b> en 54.69 s, exit 0"],
    ]
    s.append(small_table(para_rows(tests_rows),
                         col_widths=[6.0*cm, 11.0*cm]))
    s.append(P(
        "Sin regresiones. Suite paso de 460 (post-T0.4) a 468 &mdash; +8 tests netos del PR."
    ))

    s.append(H2("Tests nuevos en TestWhapiWebhookValidation"))
    s.extend(bullets([
        "test_dev_sin_token_acepta_payload &mdash; en development sin token, _verificar_firma retorna True.",
        "test_production_sin_token_levanta_runtime_error &mdash; al instanciar ProveedorWhapi en prod sin token, RuntimeError.",
        "test_production_secret_solo_whitespace_levanta &mdash; '   ' cuenta como vacio (.strip()).",
        "test_production_con_token_no_levanta_en_init &mdash; con token valido, __init__ pasa.",
        "test_production_token_valido_acepta &mdash; con header correcto, parsear_webhook procesa mensajes.",
        "test_production_token_invalido_rechaza &mdash; con valor incorrecto en header, parsear retorna [].",
        "test_production_sin_header_rechaza &mdash; sin header configurado, parsear retorna [].",
        "test_header_personalizable_via_env &mdash; WHAPI_WEBHOOK_HEADER permite cambiar el nombre del header.",
    ]))

    # ── Comportamiento implementado ──────────────────────────────────
    s.append(PageBreak())
    s.append(H1("Comportamiento implementado"))
    comp_rows = [
        ["Escenario", "Antes (P0 latente)", "Ahora"],
        ["WHATSAPP_PROVIDER=whapi + ENVIRONMENT=production + WHAPI_WEBHOOK_TOKEN vacio",
         "Webhook /webhook acepta cualquier payload sin filtro. Atacante inyecta mensajes WhatsApp falsos.",
         "<b>RuntimeError al instanciar ProveedorWhapi</b> -> obtener_proveedor() falla -> deploy aborta."],
        ["WHATSAPP_PROVIDER=whapi + production + token configurado + header valido",
         "Acepta cualquier payload",
         "Acepta solo si X-Webhook-Token coincide (hmac.compare_digest, timing-safe)."],
        ["WHATSAPP_PROVIDER=whapi + production + token configurado + header invalido o ausente",
         "Acepta cualquier payload",
         "<b>Rechaza con [] silenciosamente.</b> Log warning."],
        ["WHATSAPP_PROVIDER=meta/twilio en produccion (caso actual)",
         "ProveedorWhapi ni se importa",
         "Sin cambios &mdash; el check no afecta. <b>Cero impacto en deploy actual.</b>"],
        ["Dev/test sin token",
         "Aceptaba sin warning",
         "Permisivo con warning explicito (solo dev/test)."],
        ["Path runtime: provider creado en dev y luego ENVIRONMENT cambia a production",
         "No protege",
         "<b>Defensa en profundidad: _verificar_firma rechaza igual.</b>"],
    ]
    s.append(small_table(para_rows(comp_rows),
                         col_widths=[5.5*cm, 5.0*cm, 6.5*cm]))

    # ── Estado git ────────────────────────────────────────────────────
    s.append(H1("Estado git"))
    s.extend(bullets([
        "<b>main local</b> en 49978a9, igual a origin/main. <b>Intacto.</b>",
        "<b>HEAD</b> en pr/whapi-webhook-token-obligatorio con 57584d4.",
        "<b>Sin push a main. Sin merge. Sin deploy.</b>",
    ]))

    # ── Lo que NO toque ──────────────────────────────────────────────
    s.append(H1("Lo que NO toque (segun reglas)"))
    s.extend(bullets([
        "<b>agent/main.py</b> &mdash; sin cambios. El check vive en __init__ del provider, igual que en T0.3.",
        "<b>WHAPI_TOKEN</b> &mdash; sin tocar (sigue usandose en transcriber y diagnostico admin).",
        "<b>WHATSAPP_PROVIDER</b> &mdash; sigue siendo meta en Render.",
        "<b>Variables de Render</b> &mdash; ningun cambio.",
        "<b>Endpoints / parser</b> &mdash; sin cambios salvo el check al inicio de parsear_webhook.",
        "<b>Render / Vercel / secretos reales</b> &mdash; sin cambios. Tests usan dummies como 'shared_token_xyz', 'test_token_dummy'.",
        "<b>Merge a main</b> &mdash; no ejecutado.",
        "<b>Deploy</b> &mdash; no ejecutado.",
    ]))

    # ── Proximo paso ──────────────────────────────────────────────────
    s.append(H1("Proximo paso recomendado (no implemento sin OK)"))
    s.extend(bullets([
        "<b>Revisar el PR en GitHub</b> desde el link de la portada.",
        "<b>Mergear cuando quieras</b>: con WHATSAPP_PROVIDER=meta el deploy de Render no se ve afectado (ProveedorWhapi ni se instancia).",
        "<b>Si en algun momento futuro</b> rotas a WHATSAPP_PROVIDER=whapi: setear WHAPI_WEBHOOK_TOKEN en Render con string aleatorio + configurar el header en panel Whapi via PATCH /settings con 'headers': {'X-Webhook-Token': '<mismo valor>'}.",
        "<b>Housekeeping menor pendiente:</b> WHAPI_API_URL puede borrarse de Render (no se lee en codigo, ya documentado en .env.example).",
        "<b>Siguiente bloque grande:</b> verificacion operativa Stripe Dashboard -> T1.3 (gap funcional Stripe/backend de creditos).",
    ]))

    s.append(Spacer(1, 14))
    s.append(C(
        "Branch lista para merge. La decision queda en manos del owner."
    ))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Resumen T0.10 implementacion",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T0.10 Resumen de implementacion · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
