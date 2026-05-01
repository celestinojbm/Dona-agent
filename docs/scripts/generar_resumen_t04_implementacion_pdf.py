"""
Genera Resumen_T04_Implementacion_2026-05-01.pdf con el resumen del PR
T0.4 INBOUND_WEBHOOK_SECRET obligatorio en produccion (commit c76219d,
rama pr/inbound-webhook-secret-obligatorio).

Cierre de Phase 0 P0 originales del Plan v2.1.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Resumen_T04_Implementacion_2026-05-01.pdf"

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
    s.append(Paragraph("T0.4 — INBOUND_WEBHOOK_SECRET obligatorio", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de implementacion &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin merge, sin deploy. &nbsp;·&nbsp; Rama lista para revision.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Implementado y testeado.</b> 4 archivos modificados, 460 tests verde, "
        "branch <i>pr/inbound-webhook-secret-obligatorio</i> en GitHub. "
        "Cierra el ultimo P0 original del Plan v2.1: el endpoint /webhook/inbound/{token} "
        "ya no acepta tokens forjados con fallback derivado de ADMIN_TOKEN ni con literal "
        "publico del repo. <b>Phase 0 (3 P0 originales) cerrada.</b>"
    ))

    # ── Identificadores ────────────────────────────────────────────────
    s.append(H1("Identificadores"))
    ids_rows = [
        ["Item", "Valor"],
        ["Commit", "c76219d"],
        ["Mensaje", "fix(seguridad): INBOUND_WEBHOOK_SECRET obligatorio en produccion"],
        ["Rama local", "pr/inbound-webhook-secret-obligatorio"],
        ["Rama remota", "origin/pr/inbound-webhook-secret-obligatorio"],
        ["Crear PR en GitHub",
         "https://github.com/celestinojbm/Dona-agent/pull/new/pr/inbound-webhook-secret-obligatorio"],
        ["main local", "f79b069 (post-merge T0.3; igual a origin/main, INTACTO)"],
        ["origin/main", "f79b069 (sin push de este PR a main)"],
    ]
    s.append(small_table(para_rows(ids_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    # ── Archivos tocados ───────────────────────────────────────────────
    s.append(H1("Archivos tocados (los 4 autorizados, ninguno fuera de alcance)"))
    arch_rows = [
        ["Archivo", "Cambio"],
        ["agent/inbound_tokens.py",
         "+ check top-level: si ENVIRONMENT=production y INBOUND_WEBHOOK_SECRET vacio (post-.strip()) -> RuntimeError aborta el deploy. Refactor de _secreto(): en produccion levanta RuntimeError si la env var desaparece despues del startup (defensa en profundidad); en dev/test mantiene los dos fallbacks (derivado de ADMIN_TOKEN o literal de dev) con warning. Docstring del modulo actualizado."],
        ["agent/main.py",
         "+ import agent.inbound_tokens  # noqa: F401 despues del import agent.billing ya existente. Una linea para forzar el check al startup."],
        [".env.example",
         "Reformulado el bloque INBOUND_WEBHOOK_SECRET enfatizando obligatoriedad en produccion, con explicacion del riesgo de los fallbacks. Sin valores reales."],
        ["tests/test_inbound_tokens.py",
         "Agregada clase TestSecretoProduction con 5 tests: RuntimeError al reload sin secret, RuntimeError con whitespace, defensa en profundidad runtime, no levanta con secret valido, no cae a derivado de ADMIN_TOKEN en produccion."],
    ]
    s.append(small_table(para_rows(arch_rows),
                         col_widths=[4.0*cm, 13.0*cm]))
    s.append(P("<b>Total:</b> 4 archivos, +133 lineas, -10 lineas."))

    # ── Tests corridos ────────────────────────────────────────────────
    s.append(H1("Tests corridos"))
    tests_rows = [
        ["Suite", "Resultado"],
        ["pytest tests/test_inbound_tokens.py -x -q",
         "<b>13 passed</b> en 0.07 s (8 previos + 5 nuevos en TestSecretoProduction)"],
        ["pytest -q (suite completa)",
         "<b>460 passed</b> en 51 s, exit 0"],
    ]
    s.append(small_table(para_rows(tests_rows),
                         col_widths=[6.0*cm, 11.0*cm]))
    s.append(P(
        "Sin regresiones. Suite paso de 455 (post-T0.3) a 460 &mdash; +5 tests netos del PR."
    ))

    # ── Comportamiento implementado ──────────────────────────────────
    s.append(H1("Comportamiento implementado"))
    comp_rows = [
        ["Escenario", "Antes (P0 abierto)", "Ahora"],
        ["ENVIRONMENT=production + INBOUND_WEBHOOK_SECRET vacio",
         "Cae a derivado SHA256('inbound-webhook-derived|' + ADMIN_TOKEN) o literal 'dona-inbound-dev-secret-do-not-use-in-prod'. Atacante forja tokens -> mensajes WhatsApp arbitrarios.",
         "<b>RuntimeError al import de agent.inbound_tokens</b> -> deploy aborta antes de servir trafico."],
        ["Produccion + INBOUND_WEBHOOK_SECRET solo whitespace",
         "Mismo fallback inseguro",
         "RuntimeError (.strip() lo trata como vacio)."],
        ["Produccion + secret valido",
         "Funciona correctamente",
         "Sin cambios &mdash; _secreto() retorna los bytes correctos."],
        ["Produccion + ADMIN_TOKEN seteado, INBOUND vacio (escenario antes alto-riesgo)",
         "Cae al derivado de ADMIN_TOKEN",
         "<b>RuntimeError. ADMIN_TOKEN ya NO sirve como fallback.</b>"],
        ["Dev/test sin secret",
         "Permisivo con warning (dos fallbacks)",
         "Permisivo con warning (mismo comportamiento, log mejorado para dejar claro 'solo dev/test')."],
        ["Path runtime: secret existe al startup pero desaparece despues",
         "No protege",
         "<b>Defensa en profundidad: _secreto() rechaza con RuntimeError igual.</b>"],
    ]
    s.append(small_table(para_rows(comp_rows),
                         col_widths=[5.5*cm, 5.0*cm, 6.5*cm]))

    # ── Estado git ────────────────────────────────────────────────────
    s.append(H1("Estado git"))
    s.extend(bullets([
        "<b>main local</b> en f79b069, igual a origin/main. Intacto.",
        "<b>HEAD</b> en pr/inbound-webhook-secret-obligatorio con c76219d.",
        "Sin push a main. Sin merge. Sin deploy.",
    ]))

    # ── Lo que NO toque ──────────────────────────────────────────────
    s.append(H1("Lo que NO toque (segun reglas)"))
    s.extend(bullets([
        "<b>Formato de tokens</b> &mdash; generar_token y verificar_token sin cambios. Solo cambia de donde sale el secret.",
        "<b>Endpoints</b> /admin/inbound/token y /webhook/inbound/{token} &mdash; sin cambios.",
        "<b>Rate limiting / TTL</b> &mdash; fuera del alcance (tareas separadas).",
        "Base de datos &mdash; sin cambios.",
        "Render / Vercel / secretos reales &mdash; sin cambios. El valor real de INBOUND_WEBHOOK_SECRET no aparece en codigo, comentarios ni tests (los tests usan dummies como 'production_secret_dummy', 'test-secret-xyz', 'admin_token_dummy').",
    ]))

    # ── Proximo paso ──────────────────────────────────────────────────
    s.append(H1("Proximo paso recomendado (no implemento sin OK)"))
    s.extend(bullets([
        "<b>Revisar el PR en GitHub</b> desde el link de la portada.",
        "<b>Antes de mergear</b>, doble-check rapido en Render: que INBOUND_WEBHOOK_SECRET sigue presente con el valor correcto. Ya confirmaste &mdash; verificacion final.",
        "<b>Mergear</b> y observar Render logs en el primer deploy: si arranca normal, todo bien. Como dijiste que no hay tokens vivos conocidos, no hay riesgo de invalidacion masiva.",
        "Si aparece 'RuntimeError: [INBOUND] INBOUND_WEBHOOK_SECRET no configurado en produccion', revertir inmediatamente y diagnosticar la env var.",
        "<b>(Opcional, recomendado)</b> Probar GET /admin/inbound/token?telefono=&lt;E.164&gt; con tu Bearer admin -> te devuelve una URL -> hacer un POST de prueba con {'mensaje': 'test'} -> ver si llega el mensaje a WhatsApp. Si si, el flujo esta sano para futuras automatizaciones.",
    ]))

    # ── Cierre Phase 0 ────────────────────────────────────────────────
    s.append(H1("Cierre Phase 0 — security blockers"))
    s.append(P(
        "Con T0.4 mergeado, los <b>3 P0 originales</b> del Plan v2.1 quedan cerrados:"
    ))
    cierre_rows = [
        ["Tarea", "Estado", "Riesgo cerrado"],
        ["T0.2 STRIPE_WEBHOOK_SECRET",
         "Mergeado en main (commit 58c806b)",
         "Acreditacion forjable de creditos"],
        ["T0.3 META_APP_SECRET",
         "Mergeado en main (commit f79b069)",
         "Inyeccion de mensajes WhatsApp falsos via webhook Meta"],
        ["T0.4 INBOUND_WEBHOOK_SECRET",
         "<b>Listo para merge (commit c76219d, este PR)</b>",
         "Mensajes WhatsApp arbitrarios via webhook inbound forjado"],
    ]
    s.append(small_table(para_rows(cierre_rows),
                         col_widths=[5.0*cm, 5.0*cm, 7.0*cm]))

    s.append(H3("Pendiente nuevo (no original Phase 0)"))
    s.append(P(
        "<b>T0.10</b> &mdash; whapi sin firma. Hallazgo P0 nuevo descubierto durante el diagnostico de T0.3: "
        "agent/providers/whapi.py no implementa validacion de firma de webhooks Whapi. "
        "Si WHATSAPP_PROVIDER=whapi en produccion (no es el caso hoy &mdash; vos tenes meta), un atacante "
        "que conozca la URL /webhook puede inyectar mensajes forjados. <b>Es tarea separada cuando lo decidas.</b>"
    ))

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
        title="Dona — Resumen T0.4 implementacion",
        author="Resumen generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T0.4 Resumen de implementacion · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
