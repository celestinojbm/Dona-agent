"""
Genera Link_PR_T010_2026-05-01.pdf con el link prearmado para crear el PR
de pr/whapi-webhook-token-obligatorio en GitHub (titulo + descripcion ya
incluidos en la URL).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Link_PR_T010_2026-05-01.pdf"

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
    textColor=colors.HexColor("#7c2d12"), backColor=colors.HexColor("#fff7ed"),
    borderPadding=8, borderColor=colors.HexColor("#fb923c"), borderWidth=0.6,
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
    name="CodeBox", parent=styles["Code"], fontSize=7.5, leading=10,
    textColor=colors.HexColor("#111111"),
    backColor=colors.HexColor("#f5f5f5"),
    borderPadding=6, borderColor=colors.HexColor("#e5e7eb"), borderWidth=0.4,
    leftIndent=4, rightIndent=4, spaceBefore=6, spaceAfter=10,
    wordWrap="CJK",  # forzar wrap aunque no haya espacios (URL larga)
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

    s.append(Paragraph("Crear PR T0.10 — Link prearmado", styles["TitleBig"]))
    s.append(Paragraph(
        "Resumen de paso &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Sin merge, sin deploy, sin instalar dependencias.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>gh CLI no esta instalado</b> en el entorno y la regla 'no instalar dependencias' lo "
        "deja fuera. Solucion: link de GitHub con titulo y descripcion ya pre-cargados en la URL. "
        "Un solo click + Create pull request y queda creado el PR."
    ))

    # ── Por que no programatico ──────────────────────────────────────
    s.append(H1("Por que no se creo programaticamente"))
    s.extend(bullets([
        "<b>gh CLI no encontrado</b>: <i>which gh</i> retorno error; tampoco esta en /c/Program Files/GitHub CLI/, en %LOCALAPPDATA%/Programs/GitHub CLI/, ni en scoop.",
        "<b>Instalar gh requeriria modificar dependencias del sistema</b>, que excede la regla 'no instalar dependencias'.",
        "<b>Alternativa segura</b>: GitHub soporta query params <i>?title=...&amp;body=...</i> en la URL de Compare, asi se puede prearmar el formulario de crear PR sin tocar el sistema.",
    ]))

    # ── Link prearmado ───────────────────────────────────────────────
    s.append(H1("Link prearmado (un solo click)"))
    s.append(P(
        "Pegar en cualquier navegador autenticado en GitHub. Se abre el formulario de Compare con "
        "titulo y body ya cargados; solo hay que apretar <b>Create pull request</b>."
    ))

    url_full = (
        "https://github.com/celestinojbm/Dona-agent/compare/main...pr/whapi-webhook-token-obligatorio?"
        "quick_pull=1"
        "&title=fix%28security%29%3A%20require%20WHAPI_WEBHOOK_TOKEN%20in%20production"
        "&body=-%20Adds%20preventive%20webhook%20validation%20for%20Whapi%20provider.%0A"
        "-%20Requires%20WHAPI_WEBHOOK_TOKEN%20in%20production%20when%20WHATSAPP_PROVIDER%3Dwhapi.%0A"
        "-%20Validates%20custom%20header%20X-Webhook-Token%20with%20hmac.compare_digest.%0A"
        "-%20Keeps%20dev/test%20permissive.%0A"
        "-%20Does%20not%20affect%20current%20production%20because%20WHATSAPP_PROVIDER%3Dmeta.%0A"
        "-%20Tests%3A%20pytest%20tests/test_providers.py%20-x%20-q%20%3D%3E%2037%20passed%3B"
        "%20pytest%20-q%20%3D%3E%20468%20passed."
    )
    s.append(CODE(url_full))

    # ── Lo que se vera en GitHub ──────────────────────────────────────
    s.append(H1("Lo que veras en GitHub al abrir el link"))
    campos_rows = [
        ["Campo", "Valor pre-cargado"],
        ["Base", "main"],
        ["Compare", "pr/whapi-webhook-token-obligatorio"],
        ["Title", "fix(security): require WHAPI_WEBHOOK_TOKEN in production"],
        ["Body", "(los 6 bullets exactos que pediste)"],
        ["Diff visible", "3 archivos, +242 lineas (los del commit 57584d4)"],
    ]
    s.append(small_table(para_rows(campos_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    s.append(H2("Pasos en el navegador (3 clicks)"))
    s.extend(bullets([
        "Pegar el link en cualquier navegador autenticado en GitHub.",
        "Verificar que el titulo y descripcion estan como pediste.",
        "Click en <b>Create pull request</b> (no 'Create draft' ni 'Auto-merge').",
    ]))
    s.append(P("El PR queda abierto. <b>No se mergea automaticamente.</b>"))

    # ── Alternativa simple ────────────────────────────────────────────
    s.append(H1("Alternativa simple (sin URL prearmada)"))
    s.append(P("Si preferis el link simple y pegar titulo + descripcion a mano:"))
    s.append(CODE("https://github.com/celestinojbm/Dona-agent/pull/new/pr/whapi-webhook-token-obligatorio"))

    s.append(H3("Title"))
    s.append(CODE("fix(security): require WHAPI_WEBHOOK_TOKEN in production"))

    s.append(H3("Description"))
    body_md = (
        "- Adds preventive webhook validation for Whapi provider.\n"
        "- Requires WHAPI_WEBHOOK_TOKEN in production when WHATSAPP_PROVIDER=whapi.\n"
        "- Validates custom header X-Webhook-Token with hmac.compare_digest.\n"
        "- Keeps dev/test permissive.\n"
        "- Does not affect current production because WHATSAPP_PROVIDER=meta.\n"
        "- Tests: pytest tests/test_providers.py -x -q => 37 passed; pytest -q => 468 passed.\n"
    )
    s.append(CODE(body_md))

    # ── Confirmaciones ───────────────────────────────────────────────
    s.append(H1("Confirmaciones"))
    s.extend(bullets([
        "<b>Sin merge</b> &mdash; solo creo el link de creacion; el merge sigue siendo decision tuya en GitHub.",
        "<b>Sin deploy</b> &mdash; la rama no toca main, Render no observa branches pr/*.",
        "<b>Sin instalar gh CLI</b> &mdash; respete la regla de no instalar dependencias.",
        "<b>Sin tocar archivos del proyecto</b> &mdash; este paso es 100% generacion de URL.",
    ]))

    s.append(Spacer(1, 14))
    s.append(C("Esperando proximas instrucciones del owner."))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Link PR T0.10",
        author="Generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Link PR T0.10 · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
