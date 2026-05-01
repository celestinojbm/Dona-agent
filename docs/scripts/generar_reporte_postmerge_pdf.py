"""
Genera Reporte_PostMerge_Dona_2026-05-01.pdf con el reporte final post-merge:
- Estado actual de git tras los 6 merges.
- Resumen tecnico de lo integrado.
- Riesgos a monitorear.
- Pendientes no implementados.
- Proximo orden recomendado.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Reporte_PostMerge_Dona_2026-05-01.pdf"

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
styles.add(ParagraphStyle(
    name="BulletSub", parent=styles["Body"], leftIndent=28, bulletIndent=14,
    spaceAfter=2, fontSize=9,
))


def H1(t): return Paragraph(t, styles["H1"])
def H2(t): return Paragraph(t, styles["H2"])
def H3(t): return Paragraph(t, styles["H3"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])


def bullets(items):
    return [Paragraph("&bull; " + it, styles["BulletDona"]) for it in items]


def sub_bullets(items):
    return [Paragraph("&ndash; " + it, styles["BulletSub"]) for it in items]


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
    s.append(Paragraph("Dona — Reporte final post-merge", styles["TitleBig"]))
    s.append(Paragraph(
        "Fecha: 2026-05-01 &nbsp;·&nbsp; HEAD origin/main: d7866eb &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin acciones realizadas en este reporte.",
        styles["MetaTop"],
    ))
    s.append(P(
        "Reporte de cierre tras el merge a main de los 6 PRs preparados en sesiones previas. "
        "Producto verificado: usadona.com carga, WhatsApp manual OK, deploy de Render completo, "
        "VOICE_FORWARD_NUMBER configurada en Render."
    ))

    # ── 1. Estado actual de git ─────────────────────────────────────────
    s.append(H1("1. Estado actual de git"))
    s.extend(bullets([
        "<b>Rama actual local</b>: pr/docs-housekeeping (HEAD aceeef1).",
        "<b>Ultimo commit en origin/main</b>: d7866eb &mdash; Merge pull request #6 from celestinojbm/pr/voice-forward-env.",
        "<b>git status -sb</b>: ## pr/docs-housekeeping...origin/pr/docs-housekeeping (sin cambios pendientes, sin untracked).",
        "<b>Working tree</b>: limpio.",
        "<b>main local</b>: sigue en 5b7d42d. Desincronizado respecto a origin/main (d7866eb). No es problema; los merges ocurrieron en GitHub. Para alinear local con remote: <i>git checkout main &amp;&amp; git pull --ff-only origin main</i>. No es urgente y no afecta a produccion.",
        "<b>6 ramas locales pr/*</b>: todavia existen localmente.",
        "<b>6 ramas remotas pr/*</b>: todavia existen en origin. GitHub no las borro automaticamente al mergear.",
    ]))

    # ── 2. Confirmacion de los 6 PRs mergeados ──────────────────────────
    s.append(H1("2. Confirmacion de los 6 PRs mergeados"))
    s.append(P("Los 6 merge commits aparecen en origin/main en el orden esperado:"))
    pr_rows = [
        ["#", "PR", "Merge commit", "Commit del feature"],
        ["1", "pr/docs-housekeeping", "5d8dea1", "aceeef1 docs: organize Dona planning artifacts"],
        ["2", "pr/legacy-inventory", "c015aed", "1282d92 docs: inventario legacy (PR2)"],
        ["3", "pr/tools-docs-firefly-higgsfield", "44706c7", "75a3065 docs(tools): fichas Adobe Firefly y Higgsfield + matriz (PR5)"],
        ["4", "pr/disclaimer-responsable", "5474ed2", "568ab1f fix(landing): disclaimer responsable sin promesas falsas (PR4)"],
        ["5", "pr/log-sanitization-json", "0834c31", "a5e338c feat(logs): redaction de PII en logs de produccion (Variante A)"],
        ["6", "pr/voice-forward-env", "d7866eb", "c0b5149 fix(seguridad): VOICE_FORWARD_NUMBER en env var; sin var devuelve 404 (PR3)"],
    ]
    s.append(small_table(para_rows(pr_rows),
                         col_widths=[0.7*cm, 4.5*cm, 2.0*cm, 9.8*cm]))
    s.append(C(
        "Total: 6 merges + 6 commits de feature = 12 commits nuevos en origin/main desde 5b7d42d."
    ))

    # ── 3. Resumen tecnico ──────────────────────────────────────────────
    s.append(H1("3. Resumen tecnico de lo integrado"))

    s.append(H2("3.1 Documentacion (docs/) &mdash; verificado contra origin/main"))
    s.extend(bullets([
        "docs/auditorias/Auditoria_Dona_2026-04-27.pdf",
        "docs/planes/README.md, Plan_Dona_v2_1_2026-04-30.pdf (vigente), Plan_Dona_Refinado_v2, Plan_Dona_Refinado_v1, plan-maestro-dona-2026-04-21.{html,pdf}",
        "docs/scripts/generar_*.py (4 scripts reportlab)",
        "docs/legacy-inventory.md &mdash; inventario que confirma que enhanced/ esta VIVO (no es legacy AgentKit) y deja recomendaciones para start.sh, migration.py, mount knowledge/.",
        "docs/tools/README.md, matriz.md, adobe-firefly.md, higgsfield.md &mdash; Tool Intelligence Layer inicial.",
    ]))

    s.append(H2("3.2 Landing (disclaimer)"))
    s.extend(bullets([
        "landing/app/page.tsx &mdash; strings ES y EN actualizadas:",
    ]))
    s.extend(sub_bullets([
        "whyDona privacy: 'encriptacion end-to-end' + 'Nunca compartimos datos' &rarr; 'TLS + tokens OAuth cifrados en reposo, proveedores listados en politica de privacidad'.",
        "FAQ seguridad: alineada con realidad (TLS + cifrado de campos sensibles, reconoce subprocessors).",
        "painStat #4: '$2K/mes en empleados que Dona puede reemplazar' &rarr; '4x mas iniciativas en marcha cuando hay un sistema centralizado'.",
        "painStats #1, #2: agregado 'segun industria/research' para no presentar cifras como propias.",
    ]))
    s.extend(bullets([
        "Sin cambios en arquitectura del landing ni en APIs de Next.",
    ]))

    s.append(H2("3.3 Sanitizacion de logs"))
    s.extend(bullets([
        "agent/logging_config.py (97 &rarr; 175 lineas).",
        "Funciones nuevas / extendidas: redactar_pii() que aplica en orden: API keys &rarr; Bearer tokens &rarr; email &rarr; telefono.",
        "Patrones cubiertos:",
    ]))
    s.extend(sub_bullets([
        "Telefono E.164 con/sin '+' (preserva codigo de pais: +1407****6023).",
        "Email (fo***@bar.com).",
        "Bearer tokens HTTP.",
        "Claves API: sk-, sk-ant-, whsec_, cs_(live|test)_, cus_/sub_/pi_/in_/seti_/ch_/prod_/price_/evt_, Slack xox[abps]-, Resend re_, Brevo xkeysib-.",
    ]))
    s.extend(bullets([
        "<b>Solo aplica a nivel INFO+</b>; DEBUG queda intacto para diagnostico (se activa con LOG_LEVEL=DEBUG).",
        "JsonFormatter extendido para redactar tambien el campo extra 'telefono'.",
        "25 tests nuevos en tests/test_logging.py.",
    ]))

    s.append(H2("3.4 VOICE_FORWARD_NUMBER / /voice/reenviar"))
    s.extend(bullets([
        "agent/main.py (~lineas 2165-2185) &mdash; endpoint refactorizado:",
    ]))
    s.extend(sub_bullets([
        "Sin VOICE_FORWARD_NUMBER &rarr; 404 voice_forward_no_configurado.",
        "Con var pero formato invalido &rarr; 500 voice_forward_formato_invalido.",
        "Con var valida &rarr; TwiML normalizado con '+' agregado si falta.",
    ]))
    s.extend(bullets([
        ".env.example &mdash; anade bloque documental de VOICE_FORWARD_NUMBER.",
        "3 docstrings de agent/main.py (lineas 464, 488, 515) con numero personal sustituidos por 15551234567 placeholder.",
        "tests/test_voice_reenviar.py &mdash; 8 tests + smoke test que verifica que el cuerpo del handler voice_reenviar() no contiene literales E.164.",
    ]))

    # ── 4. Riesgos ──────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("4. Riesgos y puntos a monitorear"))

    s.append(H2("Render"))
    s.extend(bullets([
        "<b>Verificar que el ultimo deploy haya terminado en d7866eb</b> y no en un merge intermedio. Si usadona.com carga, indicio fuerte de exito; conviene corroborar el commit mostrado en el dashboard de Render.",
        "<b>Memoria/CPU del web service</b>: la redaccion de logs agrega regex passes en cada INFO+. Costo es minimo, pero si se ven spikes de latencia post-deploy, ahi mirar primero.",
    ]))

    s.append(H2("WhatsApp"))
    s.extend(bullets([
        "<b>Tono y latencia de respuestas</b>: sin cambios funcionales en el flujo de mensajes; deberia estar igual. Si algo cambio en logs por la redaccion, no afecta UX.",
        "<b>logger.info(... telefono ...)</b>: los logs de Render ahora muestran +1407****6023 en lugar del numero crudo. Si alguien hace debugging y necesita el numero, debe activar LOG_LEVEL=DEBUG temporalmente (ya documentado).",
    ]))

    s.append(H2("Landing"))
    s.extend(bullets([
        "<b>Cache de Vercel/CDN</b>: el cambio de strings es trivial pero el cache puede mostrar el texto viejo unos minutos. Verificacion manual: abrir usadona.com en incognito.",
        "<b>Lighthouse / SEO</b>: las pain stats cambiaron numeros (de '$2K/mes' a '4x mas'); si el SEO indexo la version anterior, tarda un par de dias en re-crawlear.",
        "<b>AGENTS.md de landing</b> advierte de breaking changes en Next: este PR solo toco strings i18n, sin tocar APIs, asi que esta dentro del lineamiento.",
    ]))

    s.append(H2("Logs"))
    s.extend(bullets([
        "<b>Falsos positivos en redaction</b>: la regex de Stripe ID ((cus|sub|pi|in|seti|ch|prod|price|evt)_[A-Za-z0-9]{14,}) podria enmascarar palabras inofensivas que casualmente coincidan. Improbable, pero vale revisar logs de prod los primeros dias buscando [REDACTED_KEY] que no deberia estar.",
        "<b>No hay Sentry todavia</b> (Variante A). Errores 500 viajan solo a Render logs. Para alertas activas hace falta T4.4 (Variante B).",
        "<b>Volumen de logs</b>: sin cambios significativos.",
    ]))

    s.append(H2("/voice/reenviar"))
    s.extend(bullets([
        "<b>Verificar 200 OK con TwiML correcto</b> desde Twilio: si Twilio esta configurado para hacer GET/POST a https://&lt;dona&gt;/voice/reenviar, deberia responder 200 con &lt;Response&gt;&lt;Dial&gt;+15551234567...&lt;/Dial&gt;&lt;/Response&gt;. Llamada de prueba al numero Twilio confirma end-to-end.",
        "<b>Si VOICE_FORWARD_NUMBER esta mal formada</b> en Render (espacios, caracteres invisibles, etc.) &rarr; 500. Endpoint loggea ERROR explicito.",
        "<b>Sin var configurada</b> &rarr; 404. Twilio devolveria al caller un fallback (depende de como este configurado alla).",
    ]))

    # ── 5. Pendientes ───────────────────────────────────────────────────
    s.append(H1("5. Pendientes NO implementados"))

    s.append(H2("Phase 0 restante (todavia abierto)"))
    s.extend(bullets([
        "<b>Stripe webhook firma obligatoria en produccion (T0.2)</b>.",
    ]))
    s.extend(sub_bullets([
        "Hoy agent/billing.py:366-384 acepta payload sin firma si STRIPE_WEBHOOK_SECRET no esta set, con warning.",
        "Requiere coordinacion: setear secret en Render antes de mergear el cambio.",
        "Riesgo abierto: <b>acreditacion de creditos forjable</b>.",
    ]))
    s.extend(bullets([
        "<b>Meta webhook firma obligatoria en produccion (T0.3)</b>.",
    ]))
    s.extend(sub_bullets([
        "agent/providers/meta.py:131-137 retorna True si META_APP_SECRET no esta configurado.",
        "Riesgo abierto: <b>inyeccion de mensajes WhatsApp falsos</b>.",
    ]))
    s.extend(bullets([
        "<b>INBOUND_WEBHOOK_SECRET sin fallback en produccion (T0.4)</b>.",
    ]))
    s.extend(sub_bullets([
        "agent/inbound_tokens.py:30-42 cae a derivado de ADMIN_TOKEN o literal de dev.",
        "Requiere comunicacion previa al owner: rotar el secret invalida tokens previos emitidos para Zapier/Make/n8n.",
    ]))

    s.append(H2("Phase 0 &mdash; observabilidad"))
    s.extend(bullets([
        "<b>Variante B (Sentry + dependencia sentry-sdk[fastapi])</b> queda para T4.4 con plan completo de observabilidad.",
    ]))

    s.append(H2("Pendientes detectados ahora durante esta revision"))
    s.extend(bullets([
        "<b>6 ramas remotas pr/*</b> siguen en origin sin borrar despues del merge. No es funcional, pero mantiene historia limpia borrarlas. GitHub permite hacerlo desde la UI de cada PR ya cerrado.",
        "<b>6 ramas locales pr/*</b> tambien siguen. Para limpiar local: <i>git branch -d pr/&lt;nombre&gt;</i> (cada una).",
        "<b>main local desincronizado</b> respecto a origin/main (no urgente; cuando trabajes desde local, <i>git checkout main &amp;&amp; git pull --ff-only</i>).",
    ]))

    s.append(H2("Pendientes legacy (ya documentados en docs/legacy-inventory.md)"))
    s.extend(bullets([
        "knowledge/ + mount &rarr; deprecar en Phase 4 (T4.6) tras confirmacion.",
        "start.sh &rarr; reescribir como scripts/dev.sh o eliminar en T4.6.",
        "migration.py &rarr; reemplazar por Alembic real en T4.3, luego archivar.",
    ]))

    s.append(H2("Pendientes de Plan v2.1 que no son Phase 0"))
    s.extend(bullets([
        "T1.x (Workspace, identidad, magic-link Resend, plan + creditos, cifrado A.3, audit log, system prompt premium).",
        "T2.x (Dashboard premium, conexiones OAuth, privacidad CCPA real, sub-agentes publicos en dashboard).",
        "T3.x (Orchestrator, iniciativas, Public Sub-Agent runtime).",
        "T4.x (web+worker Render, Alembic real, observabilidad, CI).",
        "T5.x (verticalizacion GTM).",
    ]))

    # ── 6. Proximo orden recomendado ────────────────────────────────────
    s.append(H1("6. Proximo orden recomendado"))
    s.append(P("Solo recomendacion. No implementa nada."))

    s.append(H2("Inmediato (housekeeping post-merge, riesgo cero)"))
    s.extend(bullets([
        "Borrar las 6 ramas remotas pr/* en GitHub (UI de cada PR cerrado).",
        "Borrar las 6 ramas locales pr/* y volver main local a origin/main (d7866eb).",
        "Smoke check operacional: una llamada de prueba a /voice/reenviar desde Twilio + un mensaje WhatsApp de ida-vuelta + carga de usadona.com en incognito. Tres minutos.",
    ]))

    s.append(H2("Cerrar Phase 0 (riesgo P0 todavia abierto)"))
    s.extend(bullets([
        "<b>PR Stripe firma obligatoria (T0.2)</b>. Necesita confirmacion previa de que STRIPE_WEBHOOK_SECRET ya esta seteado en Render. Es el riesgo P0 mas fuerte de los 3 pendientes (acreditacion forjable de creditos).",
        "<b>PR Meta firma obligatoria (T0.3)</b>. Mismo patron. Confirmar META_APP_SECRET en Render antes.",
        "<b>PR INBOUND_WEBHOOK_SECRET sin fallback (T0.4)</b>. Coordinar: si hay tokens emitidos a Zapier/Make/n8n, rotar el secret los invalida &mdash; necesita comunicacion previa.",
    ]))

    s.append(H2("Phase 1 (solo despues de cerrar Phase 0)"))
    s.extend(bullets([
        "Empezar identidad / Workspace progresivo (T1.1, T1.2) sin tocar lookups existentes.",
        "Decidir matriz plan &harr; creditos &harr; tools (T1.5) y proveedor SMTP final (Resend tentativo). Estos dos bloquean buena parte de Phase 1.",
    ]))

    s.append(H2("Mantener vivo"))
    s.extend(bullets([
        "docs/tools/matriz.md se actualiza cuando aparece una herramienta nueva.",
        "docs/legacy-inventory.md se revisa antes de tocar cualquier item legacy.",
    ]))

    # Cierre
    s.append(H1("Cierre"))
    s.extend(bullets([
        "origin/main esta en d7866eb con los 6 merges aplicados.",
        "usadona.com carga, WhatsApp verificado, deploy completo.",
        "3 P0 de seguridad siguen abiertos (Stripe / Meta / INBOUND firmas) &mdash; son los siguientes a atender.",
        "Working tree local limpio. Sin acciones realizadas en este reporte.",
    ]))

    return s


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Reporte final post-merge",
        author="Reporte generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch, "Dona — Reporte final post-merge · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
