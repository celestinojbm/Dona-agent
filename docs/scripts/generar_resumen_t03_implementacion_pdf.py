"""
Genera Resumen_T03_Implementacion_2026-05-01.pdf con el resumen del PR
T0.3 Meta webhook signature obligatorio (commit 807a676, rama
pr/meta-webhook-firma-obligatoria).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_T03_Implementacion_2026-05-01.pdf"

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

    # Portada
    s.append(Paragraph("T0.3 — Meta webhook signature obligatorio", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de implementacion &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin merge, sin deploy. &nbsp;·&nbsp; Rama lista para revision.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Implementado y testeado.</b> 3 archivos modificados, 455 tests verde, "
        "branch <i>pr/meta-webhook-firma-obligatoria</i> en GitHub. "
        "Riesgo P0 cerrado: con WHATSAPP_PROVIDER=meta en produccion ya no se "
        "aceptan webhooks sin firma HMAC valida. Queda T0.10 abierto (whapi sin firma)."
    ))

    # ── Identificadores ────────────────────────────────────────────────
    s.append(H1("Identificadores"))
    ids_rows = [
        ["Item", "Valor"],
        ["Commit", "807a676"],
        ["Mensaje", "fix(seguridad): META_APP_SECRET obligatorio en produccion"],
        ["Rama local", "pr/meta-webhook-firma-obligatoria"],
        ["Rama remota", "origin/pr/meta-webhook-firma-obligatoria"],
        ["Crear PR en GitHub",
         "https://github.com/celestinojbm/Dona-agent/pull/new/pr/meta-webhook-firma-obligatoria"],
        ["main local", "58c806b (post-merge T0.2; igual a origin/main, INTACTO)"],
        ["origin/main", "58c806b (sin push de este PR a main)"],
    ]
    s.append(small_table(para_rows(ids_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # ── Archivos tocados ───────────────────────────────────────────────
    s.append(H1("Archivos tocados (los 3 autorizados, ninguno fuera de alcance)"))
    arch_rows = [
        ["Archivo", "Cambio"],
        ["agent/providers/meta.py",
         "+ check en ProveedorMeta.__init__(): si ENVIRONMENT=production y app_secret vacio (post-.strip()) -> RuntimeError. Refactor de _verificar_firma: en produccion rechaza con False si no hay secret (defensa en profundidad); en dev/test mantiene path permisivo con warning. Lee ENVIRONMENT en cada llamada para tests con monkeypatch."],
        [".env.example",
         "+ bloque documental para META_APP_SECRET dentro del bloque Meta existente. Renombre META_VERIFY_TOKEN a META_WEBHOOK_VERIFY_TOKEN (la var real que lee el codigo en meta.py:99). Sin valores reales."],
        ["tests/test_providers.py",
         "TestVerificacionHMAC ampliado: test_sin_secret_permite_todo se reemplazo por dos tests explicitos (test_sin_secret_en_dev_permite y test_sin_secret_en_test_permite) con monkeypatch.setenv. Agregada clase nueva TestVerificacionHMACProduction con 5 tests: RuntimeError en init sin secret, RuntimeError con secret whitespace, no levanta con secret valido, defensa en profundidad runtime, firma valida en produccion."],
    ]
    s.append(small_table(para_rows(arch_rows),
                         col_widths=[4.0*cm, 13.0*cm]))
    s.append(P("<b>Total:</b> 3 archivos, +121 lineas, -9 lineas."))

    # ── Tests corridos ────────────────────────────────────────────────
    s.append(H1("Tests corridos"))
    tests_rows = [
        ["Suite", "Resultado"],
        ["pytest tests/test_providers.py -x -q",
         "<b>29 passed</b> en 0.71 s"],
        ["pytest -q (suite completa)",
         "<b>455 passed</b> en 92 s, exit 0"],
    ]
    s.append(small_table(para_rows(tests_rows),
                         col_widths=[6.0*cm, 11.0*cm]))
    s.append(P(
        "Sin regresiones. Suite paso de 449 (post-T0.2) a 455 &mdash; +6 tests netos del PR "
        "(5 nuevos en TestVerificacionHMACProduction + 1 nuevo en TestVerificacionHMAC por el split del antiguo)."
    ))

    # ── Comportamiento implementado ──────────────────────────────────
    s.append(H1("Comportamiento implementado"))
    comp_rows = [
        ["Escenario", "Antes (P0 abierto)", "Ahora"],
        ["WHATSAPP_PROVIDER=meta + ENVIRONMENT=production + META_APP_SECRET vacio",
         "Acepta sin firma -> atacante inyecta mensajes WhatsApp falsos",
         "<b>RuntimeError al instanciar ProveedorMeta</b> -> obtener_proveedor() falla -> agent/main.py:54 aborta startup -> deploy aborta."],
        ["WHATSAPP_PROVIDER=meta + produccion + secret seteado",
         "Validacion HMAC correcta", "Sin cambios"],
        ["WHATSAPP_PROVIDER=meta + produccion + firma invalida",
         "Rechaza con 200+[]", "Sin cambios"],
        ["WHATSAPP_PROVIDER=whapi/twilio en produccion",
         "ProveedorMeta ni se importa", "Sin cambios &mdash; el check no afecta."],
        ["Dev/test sin secret",
         "Permisivo con warning",
         "Permisivo con warning (mismo comportamiento, log mejorado)"],
        ["Path runtime: provider creado en dev y luego ENVIRONMENT cambia a production",
         "No protege",
         "<b>Defensa en profundidad: _verificar_firma rechaza igual</b>"],
    ]
    s.append(small_table(para_rows(comp_rows),
                         col_widths=[5.5*cm, 5.0*cm, 6.5*cm]))

    # ── Estado git ────────────────────────────────────────────────────
    s.append(H1("Estado git"))
    s.extend(bullets([
        "<b>main local</b> en 58c806b, igual a origin/main. Intacto.",
        "<b>HEAD</b> en pr/meta-webhook-firma-obligatoria con 807a676.",
        "Sin push a main. Sin merge. Sin deploy.",
    ]))

    # ── Lo que NO toque ──────────────────────────────────────────────
    s.append(H1("Lo que NO toque (segun reglas)"))
    s.extend(bullets([
        "<b>agent/providers/whapi.py</b> &mdash; sin cambios (T0.10 sigue siendo tarea separada).",
        "<b>WHAPI_TOKEN, WHAPI_API_URL</b> &mdash; sin tocar en .env.example.",
        "<b>agent/main.py</b> &mdash; sin cambios (a diferencia de T0.2; aqui no hace falta import top-level porque obtener_proveedor() ya instancia el provider en el startup).",
        "Base de datos &mdash; sin cambios.",
        "Render / Vercel / secretos &mdash; sin cambios. El valor real de META_APP_SECRET no aparece en codigo, comentarios ni tests (los tests usan dummies como 'test_app_secret_dummy' o 'production_secret_dummy').",
    ]))

    # ── Proximo paso ──────────────────────────────────────────────────
    s.append(H1("Proximo paso recomendado (no implemento sin OK)"))
    s.extend(bullets([
        "<b>Revisar el PR en GitHub</b> desde el link de la portada.",
        "<b>Antes de mergear</b>, doble-check rapido en Render: que WHATSAPP_PROVIDER=meta y META_APP_SECRET siguen presentes con el valor correcto. Ya confirmaste &mdash; esto es solo verificacion visual final.",
        "<b>Mergear</b> y observar Render logs en el primer deploy: si arranca normal, todo bien; si aparece 'RuntimeError: [META] META_APP_SECRET no configurado en produccion', revertir inmediatamente.",
        "<b>Enviar un mensaje de prueba</b> a Dona desde tu WhatsApp. Si llega, la firma es correcta. Si no, revisar logs por '[META] Firma HMAC del webhook NO coincide' (significaria mismatch entre el secret en Render y el de Meta Dashboard).",
        "<b>T0.10 (whapi sin firma) sigue abierto</b> &mdash; es tarea separada cuando lo decidas.",
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
        title="Dona — Resumen T0.3 implementacion",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T0.3 Resumen de implementacion · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
