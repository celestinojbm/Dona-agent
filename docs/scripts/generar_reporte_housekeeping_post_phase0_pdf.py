"""
Genera Reporte_Housekeeping_Post_Phase0_Dona_2026-05-01.pdf con el reporte
de solo lectura del housekeeping post-Phase 0.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Reporte_Housekeeping_Post_Phase0_Dona_2026-05-01.pdf"

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
    s.append(Paragraph("Dona — Housekeeping post-Phase 0", styles["TitleBig"]))
    s.append(Paragraph(
        "Reporte de solo lectura &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin acciones realizadas.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Listo para limpieza.</b> Las 9 ramas pr/* (locales y remotas) estan mergeadas en "
        "origin/main. main local esta 2 commits detras (fast-forward simple). Hay 18 archivos "
        "untracked (9 PDFs + 9 scripts) que conviene mover a docs/. Riesgo de las operaciones: cero."
    ))

    # ── 1. Estado actual de git ────────────────────────────────────────
    s.append(H1("1. Estado actual de git"))
    estado_rows = [
        ["Item", "Valor"],
        ["Rama actual local", "pr/inbound-webhook-secret-obligatorio"],
        ["HEAD local", "c76219d &mdash; fix(seguridad): INBOUND_WEBHOOK_SECRET obligatorio en produccion"],
        ["main local", "f79b069 &mdash; Merge pull request #8 from celestinojbm/pr/meta-webhook-firma-obligatoria"],
        ["origin/main", "32da747 &mdash; Merge pull request #9 from celestinojbm/pr/inbound-webhook-secret-obligatorio"],
        ["git status -sb",
         "## pr/inbound-webhook-secret-obligatorio...origin/pr/inbound-webhook-secret-obligatorio (sin ahead/behind, sin cambios staged ni unstaged)"],
        ["Working tree", "limpio respecto a tracked files"],
        ["Untracked", "18 archivos (9 PDFs + 9 scripts generar_*_pdf.py) &mdash; ver §5"],
    ]
    s.append(small_table(para_rows(estado_rows),
                         col_widths=[3.5*cm, 13.5*cm]))

    s.append(P("<b>Diferencia entre main local y origin/main:</b>"))
    s.extend(bullets([
        "main local esta <b>2 commits detras</b> de origin/main (le faltan c76219d y 32da747, ambos correspondientes al merge de T0.4).",
        "Es <b>fast-forward simple</b>, no hay divergencia.",
    ]))

    # ── 2. Ramas locales pr/* ──────────────────────────────────────────
    s.append(H1("2. Ramas locales pr/*"))

    s.append(H2("2.1 Las 9 que existen (todas)"))
    locales = (
        "pr/disclaimer-responsable\n"
        "pr/docs-housekeeping\n"
        "pr/inbound-webhook-secret-obligatorio   <- rama actual (checkout)\n"
        "pr/legacy-inventory\n"
        "pr/log-sanitization-json\n"
        "pr/meta-webhook-firma-obligatoria\n"
        "pr/stripe-webhook-firma-obligatoria\n"
        "pr/tools-docs-firefly-higgsfield\n"
        "pr/voice-forward-env\n"
    )
    s.append(CODE(locales))

    s.append(H2("2.2 Mergeadas en origin/main"))
    s.append(P(
        "<b>Las 9.</b> Todas son ancestros de origin/main (los merges en GitHub fueron con merge commit, "
        "no con squash, asi que <i>git branch --merged</i> las detecta correctamente)."
    ))

    s.append(H2("2.3 No mergeadas"))
    s.append(P(
        "<b>Ninguna.</b> Cero ramas locales con commits no presentes en origin/main."
    ))

    # ── 3. Ramas remotas origin/pr/* ───────────────────────────────────
    s.append(H1("3. Ramas remotas origin/pr/*"))

    s.append(H2("3.1 Las 9 que existen"))
    remotas = (
        "origin/pr/disclaimer-responsable\n"
        "origin/pr/docs-housekeeping\n"
        "origin/pr/inbound-webhook-secret-obligatorio\n"
        "origin/pr/legacy-inventory\n"
        "origin/pr/log-sanitization-json\n"
        "origin/pr/meta-webhook-firma-obligatoria\n"
        "origin/pr/stripe-webhook-firma-obligatoria\n"
        "origin/pr/tools-docs-firefly-higgsfield\n"
        "origin/pr/voice-forward-env\n"
    )
    s.append(CODE(remotas))

    s.append(H2("3.2 Mergeadas"))
    s.append(P("<b>Las 9.</b>"))

    s.append(H2("3.3 No mergeadas"))
    s.append(P("<b>Ninguna.</b>"))

    # ── 4. Seguridad de las operaciones ────────────────────────────────
    s.append(PageBreak())
    s.append(H1("4. Seguridad de las operaciones de housekeeping"))

    s.append(H2("4.1 Es seguro <i>git checkout main</i>?"))
    s.append(P("<b>Si.</b>"))
    s.extend(bullets([
        "No hay cambios staged ni unstaged en archivos tracked.",
        "Los 18 untracked son de raiz; checkout de main no los toca (siguen como untracked en main tambien).",
        "La rama actual (pr/inbound-webhook-secret-obligatorio) ya esta mergeada y empuja a su upstream en sync, asi que dejarla atras no pierde nada.",
    ]))

    s.append(H2("4.2 Es seguro <i>git pull --ff-only origin main</i>?"))
    s.append(P("<b>Si.</b>"))
    s.extend(bullets([
        "main local (f79b069) es ancestro estricto de origin/main (32da747).",
        "Es fast-forward, no hay merge commit ni conflicto.",
        "--ff-only aborta limpio si por alguna razon apareciera divergencia (defensa en profundidad).",
    ]))

    s.append(H2("4.3 Es seguro borrar las ramas locales mergeadas?"))
    s.append(P("<b>Si, con <i>git branch -d</i> (no -D).</b>"))
    s.extend(bullets([
        "-d solo borra ramas mergeadas &mdash; si una rama tuviera commits no mergeados, el comando aborta. Defensa automatica contra perdida de trabajo.",
        "<b>Excepcion critica:</b> la rama actual no se puede borrar mientras este checked out. Tenes que cambiar a main primero.",
    ]))

    s.append(H2("4.4 Es seguro borrar las ramas remotas mergeadas?"))
    s.append(P("<b>Si.</b>"))
    s.extend(bullets([
        "Borrar una rama remota (git push origin --delete pr/&lt;name&gt;) no toca main ni el contenido del repo.",
        "Los PRs cerrados en GitHub se mantienen como historial inmutable; perder la rama solo elimina el branch pointer, no los commits (siguen accesibles via SHA mientras existan refs que los alcancen, en este caso los merge commits de main).",
        "<b>Cero impacto en produccion.</b> Render no observa branches pr/*, solo main.",
    ]))

    # ── 5. Archivos untracked ──────────────────────────────────────────
    s.append(H1("5. Archivos untracked en working tree"))

    s.append(H2("5.1 PDFs de planificacion (9)"))
    pdfs = (
        "Diagnostico_T02_Stripe_Webhook_2026-05-01.pdf\n"
        "Diagnostico_T02_Corregido_2026-05-01.pdf\n"
        "Diagnostico_T03_Meta_Webhook_2026-05-01.pdf\n"
        "Diagnostico_T04_Inbound_Webhook_2026-05-01.pdf\n"
        "Reporte_PostMerge_Dona_2026-05-01.pdf\n"
        "Reporte_Post_Phase0_Dona_2026-05-01.pdf\n"
        "Resumen_T02_Implementacion_2026-05-01.pdf\n"
        "Resumen_T03_Implementacion_2026-05-01.pdf\n"
        "Resumen_T04_Implementacion_2026-05-01.pdf\n"
    )
    s.append(CODE(pdfs))

    s.append(H2("5.2 Scripts generadores (9)"))
    scripts = (
        "generar_diagnostico_t02_pdf.py\n"
        "generar_diagnostico_t02_corregido_pdf.py\n"
        "generar_diagnostico_t03_pdf.py\n"
        "generar_diagnostico_t04_pdf.py\n"
        "generar_reporte_postmerge_pdf.py\n"
        "generar_reporte_post_phase0_pdf.py\n"
        "generar_resumen_t02_implementacion_pdf.py\n"
        "generar_resumen_t03_implementacion_pdf.py\n"
        "generar_resumen_t04_implementacion_pdf.py\n"
    )
    s.append(CODE(scripts))

    s.append(H2("5.3 Otros"))
    s.append(P("<b>Ninguno.</b> Cero archivos untracked fuera de las dos categorias."))

    s.append(H2("5.4 Conviene pr/docs-housekeeping-2?"))
    s.append(P("<b>Si, mismo patron que el primer housekeeping.</b> Estructura sugerida:"))
    estructura = (
        "docs/auditorias/\n"
        "  +- (ya existe Auditoria_Dona_2026-04-27.pdf)\n"
        "\n"
        "docs/planes/\n"
        "  +- (ya hay 4 PDFs previos)\n"
        "\n"
        "docs/scripts/\n"
        "  +- (ya hay 4 scripts previos)\n"
    )
    s.append(CODE(estructura))

    s.append(P("<b>Movimientos sugeridos para el PR docs-housekeeping-2:</b>"))
    movs_rows = [
        ["Archivo origen (raiz)", "Destino propuesto"],
        ["Diagnostico_T02_Stripe_Webhook_2026-05-01.pdf", "docs/auditorias/"],
        ["Diagnostico_T02_Corregido_2026-05-01.pdf", "docs/auditorias/"],
        ["Diagnostico_T03_Meta_Webhook_2026-05-01.pdf", "docs/auditorias/"],
        ["Diagnostico_T04_Inbound_Webhook_2026-05-01.pdf", "docs/auditorias/"],
        ["Reporte_PostMerge_Dona_2026-05-01.pdf", "docs/auditorias/"],
        ["Reporte_Post_Phase0_Dona_2026-05-01.pdf", "docs/auditorias/"],
        ["Resumen_T02_Implementacion_2026-05-01.pdf", "docs/auditorias/"],
        ["Resumen_T03_Implementacion_2026-05-01.pdf", "docs/auditorias/"],
        ["Resumen_T04_Implementacion_2026-05-01.pdf", "docs/auditorias/"],
        ["generar_diagnostico_t02_pdf.py", "docs/scripts/"],
        ["generar_diagnostico_t02_corregido_pdf.py", "docs/scripts/"],
        ["generar_diagnostico_t03_pdf.py", "docs/scripts/"],
        ["generar_diagnostico_t04_pdf.py", "docs/scripts/"],
        ["generar_reporte_postmerge_pdf.py", "docs/scripts/"],
        ["generar_reporte_post_phase0_pdf.py", "docs/scripts/"],
        ["generar_resumen_t02_implementacion_pdf.py", "docs/scripts/"],
        ["generar_resumen_t03_implementacion_pdf.py", "docs/scripts/"],
        ["generar_resumen_t04_implementacion_pdf.py", "docs/scripts/"],
    ]
    s.append(small_table(para_rows(movs_rows),
                         col_widths=[10.0*cm, 7.0*cm]))
    s.append(P(
        "Nota: en el primer housekeeping algunos PDFs fueron a docs/planes/ (los planes maestro y los refinados "
        "v1/v2/v2.1). Estos nuevos no son planes maestros &mdash; son diagnosticos, resumenes y reportes &mdash; "
        "asi que docs/auditorias/ es la categoria correcta para todos."
    ))

    # ── 6. Comandos recomendados ───────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("6. Comandos recomendados (no ejecutados todavia)"))

    s.append(H2("6.1 Sincronizar main local"))
    cmd_61 = (
        "git checkout main\n"
        "git pull --ff-only origin main\n"
    )
    s.append(CODE(cmd_61))
    s.append(P("Resultado esperado: main local pasa de f79b069 a 32da747."))

    s.append(H2("6.2 Borrar ramas locales mergeadas (las 9)"))
    cmd_62a = (
        "git branch -d pr/disclaimer-responsable\n"
        "git branch -d pr/docs-housekeeping\n"
        "git branch -d pr/inbound-webhook-secret-obligatorio\n"
        "git branch -d pr/legacy-inventory\n"
        "git branch -d pr/log-sanitization-json\n"
        "git branch -d pr/meta-webhook-firma-obligatoria\n"
        "git branch -d pr/stripe-webhook-firma-obligatoria\n"
        "git branch -d pr/tools-docs-firefly-higgsfield\n"
        "git branch -d pr/voice-forward-env\n"
    )
    s.append(CODE(cmd_62a))
    s.append(P("O en una sola linea (mas practico):"))
    cmd_62b = (
        "git branch -d pr/disclaimer-responsable pr/docs-housekeeping \\\n"
        "  pr/inbound-webhook-secret-obligatorio pr/legacy-inventory \\\n"
        "  pr/log-sanitization-json pr/meta-webhook-firma-obligatoria \\\n"
        "  pr/stripe-webhook-firma-obligatoria pr/tools-docs-firefly-higgsfield \\\n"
        "  pr/voice-forward-env\n"
    )
    s.append(CODE(cmd_62b))
    s.append(P("<b>Pre-requisito:</b> estar parado en main (no en una rama pr/*)."))

    s.append(H2("6.3 Borrar ramas remotas mergeadas (las 9)"))
    cmd_63 = (
        "git push origin --delete pr/disclaimer-responsable pr/docs-housekeeping \\\n"
        "  pr/inbound-webhook-secret-obligatorio pr/legacy-inventory \\\n"
        "  pr/log-sanitization-json pr/meta-webhook-firma-obligatoria \\\n"
        "  pr/stripe-webhook-firma-obligatoria pr/tools-docs-firefly-higgsfield \\\n"
        "  pr/voice-forward-env\n"
    )
    s.append(CODE(cmd_63))
    s.append(P(
        "<b>Alternativa</b>: GitHub UI tiene un boton 'Delete branch' en cada PR cerrado. Mas visual pero "
        "9 clicks individuales."
    ))
    s.append(P(
        "<b>Despues</b> del delete remoto, conviene un <i>git fetch origin --prune</i> para que los refs "
        "locales origin/pr/* tambien desaparezcan del listado."
    ))

    s.append(H2("6.4 Crear PR de housekeeping documental"))
    cmd_64 = (
        "git checkout -b pr/docs-housekeeping-2\n"
        "mkdir -p docs/auditorias docs/scripts\n"
        "mv Diagnostico_*.pdf Reporte_*.pdf Resumen_*.pdf docs/auditorias/\n"
        "mv generar_*.py docs/scripts/\n"
        "git add docs/\n"
        'git commit -m "docs: organize Phase 0 audits, reports and scripts"\n'
        "git push -u origin pr/docs-housekeeping-2\n"
    )
    s.append(CODE(cmd_64))

    # ── 7. Resumen ejecutivo ───────────────────────────────────────────
    s.append(H1("7. Resumen ejecutivo"))
    resumen_rows = [
        ["Aspecto", "Estado"],
        ["Rama actual", "pr/inbound-webhook-secret-obligatorio (mergeada, en sync con su upstream)"],
        ["main local vs origin/main", "2 commits detras (fast-forward seguro)"],
        ["Ramas locales pr/*", "9 &mdash; <b>todas mergeadas</b>, todas seguras de borrar"],
        ["Ramas remotas pr/*", "9 &mdash; <b>todas mergeadas</b>, todas seguras de borrar"],
        ["Untracked", "18 (9 PDFs + 9 scripts) &mdash; todos artefactos de planificacion, ninguno critico"],
        ["Recomendacion general",
         "Ejecutar §6.1 (sync) -> §6.2 + §6.3 (borrar ramas) -> §6.4 (housekeeping documental). Total ~5 minutos."],
        ["Riesgo",
         "<b>Cero.</b> Cada operacion es reversible (commits siguen accesibles via SHA o via PRs cerrados en GitHub)."],
    ]
    s.append(small_table(para_rows(resumen_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(Spacer(1, 14))
    s.append(C("Sin acciones realizadas. Esperando OK del owner para ejecutar §6.1 a §6.4 (o un subconjunto)."))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Reporte Housekeeping post-Phase 0",
        author="Reporte generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — Housekeeping post-Phase 0 · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
