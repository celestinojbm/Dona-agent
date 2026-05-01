"""
Genera Diagnostico_T02_Stripe_Webhook_2026-05-01.pdf con el diagnostico
de solo lectura del bloque P0 Stripe webhook signature obligatorio (T0.2).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Diagnostico_T02_Stripe_Webhook_2026-05-01.pdf"

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


def H1(t): return Paragraph(t, styles["H1"])
def H2(t): return Paragraph(t, styles["H2"])
def H3(t): return Paragraph(t, styles["H3"])
def P(t): return Paragraph(t, styles["Body"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])


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


def checklist(items):
    out = []
    for it in items:
        out.append(Paragraph(
            '<font face="Helvetica-Bold">[ ]</font> ' + it,
            styles["BulletDona"],
        ))
    return out


def build_story():
    s = []

    # Portada
    s.append(Paragraph("T0.2 — Stripe webhook signature obligatorio", styles["TitleBig"]))
    s.append(Paragraph(
        "Diagnostico de solo lectura &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin cambios, sin commits, sin push.",
        styles["MetaTop"],
    ))
    s.append(P(
        "Reporte de revision previa al PR para hacer obligatoria la verificacion de firma de "
        "Stripe en el endpoint /webhook/stripe en produccion. Cierra el riesgo P0 de "
        "acreditacion forjable de creditos."
    ))

    # ── 1. Diagnostico actual ───────────────────────────────────────────
    s.append(H1("1. Diagnostico actual"))

    s.append(H2("1.1 Flujo Stripe webhook hoy"))
    flujo = (
        "Stripe -> POST https://<dona>/webhook/stripe\n"
        "            |\n"
        "    agent/main.py:2112  webhook_stripe(request)\n"
        "            | lee body + header 'stripe-signature'\n"
        "            v\n"
        "    agent/billing.py:366  verificar_firma_stripe(body, sig)\n"
        "            | hay STRIPE_WEBHOOK_SECRET?\n"
        "            +-- NO  -> json.loads(body) -> retorna evento 'verificado' (warning)  [INSEGURO]\n"
        "            +-- SI  -> stripe.Webhook.construct_event(body, sig, secret)\n"
        "                       |\n"
        "                       +-- firma valida   -> retorna evento\n"
        "                       +-- firma invalida -> retorna None\n"
        "            v\n"
        "    Si evento es None -> 400 'signature_invalid'\n"
        "    Si evento OK      -> procesar_evento_stripe(evento)\n"
        "            v\n"
        "        checkout.session.completed -> acreditar(telefono, creditos, session_id)\n"
        "            v\n"
        "        Notificacion WhatsApp al usuario 'Gracias por tu compra'\n"
    )
    s.append(CODE(flujo))

    s.append(H2("1.2 Comportamiento actual sin STRIPE_WEBHOOK_SECRET"))
    s.append(P("agent/billing.py:371-377:"))
    codigo_actual = (
        'secret = webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET", "")\n'
        'if not secret:\n'
        '    logger.warning("[BILLING] STRIPE_WEBHOOK_SECRET no configurada — '
        'aceptando sin verificar (INSEGURO)")\n'
        '    try:\n'
        '        return json.loads(payload.decode("utf-8"))\n'
        '    except Exception:\n'
        '        return None\n'
    )
    s.append(CODE(codigo_actual))
    s.append(P("<b>Riesgo P0 confirmado.</b> Un atacante que conoce la URL /webhook/stripe puede:"))
    s.extend(bullets([
        "Enviar un POST con JSON forjado: {'type': 'checkout.session.completed', 'data': {'object': {'id': 'atk_001', 'client_reference_id': '&lt;telefono_victima&gt;', 'metadata': {'telefono': '&lt;tel&gt;', 'creditos': '10000'}}}}",
        "El handler acredita 10000 creditos al telefono atacante.",
        "El atacante puede generar imagen/video/voz sin pagar nunca.",
        "stripe_session_id actua como dedupe, pero el atacante puede generar IDs arbitrarios para acreditar repetidamente.",
    ]))

    s.append(H2("1.3 Usos de STRIPE_WEBHOOK_SECRET en el repo"))
    usos_rows = [
        ["Archivo", "Linea", "Uso"],
        ["agent/billing.py", "371", "os.getenv('STRIPE_WEBHOOK_SECRET', '') con fallback inseguro"],
        ["agent/billing.py", "373", "log warning"],
        ["landing/app/api/webhook/route.ts", "20",
         "process.env.STRIPE_WEBHOOK_SECRET! (non-null assertion). Si falta, lanza error en runtime al primer webhook. <b>Independiente</b> del backend Python."],
        ["tests/test_billing.py", "197, 204",
         "dos tests TestVerificarFirma que verifican el comportamiento permisivo actual"],
    ]
    s.append(small_table(para_rows(usos_rows),
                         col_widths=[5.0*cm, 1.5*cm, 10.5*cm]))

    s.append(H2("1.4 Tests existentes que cambiaran de comportamiento"))
    s.append(P("tests/test_billing.py:195-207:"))
    test_actual = (
        'class TestVerificarFirma:\n'
        '    def test_sin_secret_configurado_acepta_payload(self, monkeypatch):\n'
        '        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)\n'
        '        ...\n'
        '        ev = agent.billing.verificar_firma_stripe(payload, "no-sig")\n'
        '        assert ev is not None  # <- esto codifica el bug\n'
    )
    s.append(CODE(test_actual))
    s.append(P(
        "Estos tests asumen el path inseguro como contrato. <b>Hay que reescribirlos</b> para:"
    ))
    s.extend(bullets([
        "Mantener el path permisivo solo en ENVIRONMENT=development|test (no production).",
        "Agregar tests especificos para ENVIRONMENT=production.",
    ]))
    s.append(P(
        "Como tests/conftest.py setea ENVIRONMENT=test por default, los tests existentes seguiran "
        "pasando si dejamos permisivo en environments no-production. Solo hace falta <b>agregar</b> "
        "los nuevos."
    ))

    s.append(H2("1.5 .env.example actual"))
    s.append(P(
        "STRIPE_WEBHOOK_SECRET <b>no aparece documentado</b>. Hay bloques para Stripe price IDs en "
        "otras zonas pero el secret no esta explicito. Hay que agregar el bloque."
    ))

    s.append(H2("1.6 Precedente util: agent/crypto.py:18-46"))
    s.append(P("Patron ya implementado para ENCRYPTION_KEY:"))
    s.extend(bullets([
        "En production sin clave -> RuntimeError al import del modulo, aborta deploy.",
        "En development -> logger.warning y sigue.",
    ]))
    s.append(P(
        "Es exactamente el patron que conviene replicar para STRIPE_WEBHOOK_SECRET."
    ))

    # ── 2. Plan de implementacion minimo ────────────────────────────────
    s.append(PageBreak())
    s.append(H1("2. Plan de implementacion minimo"))

    s.append(H2("2.1 Cambio puntual en agent/billing.py"))
    s.append(P("Agregar al <b>top del modulo</b> (igual que crypto.py):"))
    bloque_propuesto = (
        '_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()\n'
        '_STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")\n'
        '\n'
        'if _ENVIRONMENT == "production" and not _STRIPE_WEBHOOK_SECRET:\n'
        '    raise RuntimeError(\n'
        '        "[BILLING] STRIPE_WEBHOOK_SECRET no configurada en produccion — "\n'
        '        "los webhooks de Stripe podrian aceptar payloads forjados, lo que "\n'
        '        "permitiria a un atacante acreditar creditos arbitrarios. "\n'
        '        "Configura la variable antes de reintentar el deploy."\n'
        '    )\n'
    )
    s.append(CODE(bloque_propuesto))
    s.append(P("Y modificar verificar_firma_stripe para:"))
    s.extend(bullets([
        "Usar _STRIPE_WEBHOOK_SECRET como default si no se pasa explicito.",
        "Si _ENVIRONMENT == 'production' y no hay secret -> retornar None (defensa adicional).",
        "Mantener path permisivo solo en non-production.",
    ]))

    s.append(H2("2.2 Forzar fail-fast al startup (no en el primer webhook)"))
    s.append(P(
        "Hoy <i>from agent.billing import ...</i> se hace lazy dentro del handler webhook_stripe. "
        "Si dejamos solo el RuntimeError al import del modulo, recien falla cuando llega el primer "
        "webhook Stripe (no al boot)."
    ))
    s.append(P("Para <b>abortar el deploy</b> si falta el secret:"))
    s.extend(bullets([
        "Opcion minima: agregar <i>import agent.billing  # noqa: F401  # forzar check de STRIPE_WEBHOOK_SECRET al startup</i> cerca del top de agent/main.py.",
        "O agregar el check explicito en lifespan() de agent/main.py.",
    ]))
    s.append(P(
        "<b>Recomendacion</b>: opcion minima (import top-level). Es 1 linea, replica el patron de "
        "agent.crypto que ya se importa al top."
    ))

    s.append(H2("2.3 .env.example"))
    bloque_env = (
        '# == Stripe webhook (acreditacion de creditos en /webhook/stripe) ==\n'
        '# Obligatoria en produccion. Sin ella, el endpoint rechaza todos los\n'
        '# webhooks (no acredita creditos). Obtener desde:\n'
        '#   Stripe Dashboard -> Developers -> Webhooks -> tu endpoint -> Signing secret\n'
        '# Empieza con "whsec_".\n'
        '# STRIPE_WEBHOOK_SECRET=whsec_...\n'
    )
    s.append(CODE(bloque_env))

    s.append(H2("2.4 Total de cambio"))
    s.extend(bullets([
        "1 archivo modificado en codigo (agent/billing.py): ~10 lineas nuevas + ajuste de verificar_firma_stripe.",
        "1 linea agregada a agent/main.py (import explicito).",
        "1 bloque de comentario agregado a .env.example.",
        "1 archivo de tests modificado / extendido (tests/test_billing.py): ~3 tests nuevos.",
        "<b>PR pequeno, ~30-40 lineas netas.</b>",
    ]))

    # ── 3. Archivos que tocaria ─────────────────────────────────────────
    s.append(H1("3. Archivos que tocaria (alcance preciso)"))
    archivos_rows = [
        ["Archivo", "Tipo de cambio"],
        ["agent/billing.py",
         "Agregar top-level: _ENVIRONMENT, _STRIPE_WEBHOOK_SECRET, RuntimeError si production sin secret. Modificar verificar_firma_stripe."],
        ["agent/main.py",
         "Agregar 'import agent.billing  # noqa: F401' al top para forzar el check al startup."],
        [".env.example",
         "Agregar bloque documental para STRIPE_WEBHOOK_SECRET."],
        ["tests/test_billing.py",
         "Reescribir/extender TestVerificarFirma con casos de ENVIRONMENT=production."],
    ]
    s.append(small_table(para_rows(archivos_rows),
                         col_widths=[4.5*cm, 12.5*cm]))
    s.append(P("<b>Lo que NO toco:</b>"))
    s.extend(bullets([
        "agent/main.py:webhook_stripe (handler) — su logica ya rechaza con 400 si verificar_firma_stripe retorna None. No requiere cambios.",
        "landing/app/api/webhook/route.ts — independiente; ya falla con '!' si STRIPE_WEBHOOK_SECRET no esta. No es alcance de este PR.",
        "agent/billing.py:procesar_evento_stripe — no hace falta tocarlo.",
    ]))

    # ── 4. Tests ────────────────────────────────────────────────────────
    s.append(H1("4. Tests que correria"))

    s.append(H2("4.1 Tests existentes a actualizar"))
    s.append(P("tests/test_billing.py:195-207 (TestVerificarFirma):"))
    s.extend(bullets([
        "Renombrar test_sin_secret_configurado_acepta_payload -> test_sin_secret_en_dev_acepta_payload. Setear explicitamente ENVIRONMENT=development con monkeypatch para que sea robusto al default.",
        "Mantener test_payload_invalido_retorna_none igual.",
    ]))

    s.append(H2("4.2 Tests nuevos a agregar"))
    tests_nuevos = (
        'class TestVerificarFirmaProduction:\n'
        '    def test_production_sin_secret_levanta_runtime_error_al_reload\n'
        '    def test_production_con_secret_y_firma_invalida_retorna_none\n'
        '    def test_production_con_secret_y_firma_valida_retorna_evento\n'
        '        (mock de stripe.Webhook.construct_event)\n'
        '    def test_dev_sin_secret_loguea_warning_y_acepta\n'
        '        (regresion del path actual)\n'
    )
    s.append(CODE(tests_nuevos))
    s.append(P(
        "Total: 1 actualizado + 3-4 nuevos. Reload de agent.billing con importlib.reload "
        "(patron ya usado en el repo, ver tests/test_billing.py fixture db)."
    ))

    s.append(H2("4.3 Suite completa"))
    s.append(P(
        "<i>pytest -q</i> debe quedar verde. Estimado: ~445 tests (los 419 actuales + nuevos), "
        "~3 minutos."
    ))

    # ── 5. Variables en Render ──────────────────────────────────────────
    s.append(H1("5. Variables que deben estar en Render antes del merge"))
    s.append(P("Solo una:"))
    var_rows = [
        ["Variable", "Origen", "Formato esperado"],
        ["STRIPE_WEBHOOK_SECRET",
         "Stripe Dashboard -> Developers -> Webhooks -> tu endpoint /webhook/stripe -> 'Signing secret' -> 'Reveal'",
         "empieza con 'whsec_' (~38 chars)"],
    ]
    s.append(small_table(para_rows(var_rows),
                         col_widths=[5.0*cm, 8.0*cm, 4.0*cm]))
    s.append(P(
        "<b>No solicito ver el valor.</b> Solo confirmacion de que esta seteado en Render."
    ))
    s.append(P("Verificacion segura del owner sin exponer el valor:"))
    s.extend(bullets([
        "En Render Dashboard -> tu servicio -> Environment -> confirmar visualmente que la fila STRIPE_WEBHOOK_SECRET existe.",
        "Opcionalmente: probar que coincide con el del Dashboard de Stripe (si Stripe lo regenero recientemente, podria haber drift).",
    ]))

    # ── 6. Riesgos ──────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("6. Riesgos de compatibilidad y deploy"))
    riesgos_rows = [
        ["Riesgo", "Probabilidad", "Mitigacion"],
        ["Render no tiene la env var -> deploy aborta con RuntimeError al startup",
         "Baja (ya confirmado en J.2 del Plan v2.1 que 'se pueden setear sin downtime'; verificar antes del merge)",
         "Setear primero, mergear despues"],
        ["La env var en Render esta pero con un valor incorrecto / desactualizado",
         "Baja-media",
         "Verificar en Stripe Dashboard que el secret coincide con el del endpoint configurado"],
        ["Hay otro endpoint Stripe en la landing usando el mismo secret pero con ruta distinta",
         "Confirmado existente",
         "Este PR no toca el landing. La var en Vercel debe seguir igual."],
        ["Falsos rechazos de Stripe en produccion primer dia",
         "Baja si secret es correcto",
         "Monitorear logs Render por '[BILLING] Firma Stripe invalida'; si aparece, validar secret"],
        ["Tests existentes rompen por cambio de comportamiento",
         "Confirmado: 1 test cambia de contrato",
         "Plan: actualizar el test (seccion 4.1), no eliminarlo"],
        ["Deploy revierte (rollback) si algo falla",
         "Bajo",
         "Render permite redeploy de commit anterior; el cambio es localizado a billing.py"],
    ]
    s.append(small_table(para_rows(riesgos_rows),
                         col_widths=[5.0*cm, 4.5*cm, 7.5*cm]))
    s.append(P(
        "<b>Riesgo P0 que cierra este PR</b>: acreditacion forjable de creditos. "
        "Eliminado en produccion."
    ))

    # ── 7. Checklist pre-merge ──────────────────────────────────────────
    s.append(H1("7. Checklist antes de mergear"))

    s.append(H2("7.1 Pre-PR (antes de empezar)"))
    s.extend(checklist([
        "Confirmar STRIPE_WEBHOOK_SECRET esta seteada en Render con valor whsec_* correcto.",
        "Confirmar que el secret en Render coincide con el 'Signing secret' del endpoint en Stripe Dashboard (no se ha regenerado).",
        "Confirmar que la env var del landing (en Vercel, STRIPE_WEBHOOK_SECRET) sigue intacta — no la tocamos pero conviene saber que sigue ahi.",
        "Decidir nombre de branch: sugiero <b>pr/stripe-webhook-firma-obligatoria</b>.",
    ]))

    s.append(H2("7.2 Durante el PR (local)"))
    s.extend(checklist([
        "Implementar el cambio minimo de agent/billing.py (seccion 2.1).",
        "Agregar import top-level en agent/main.py (seccion 2.2).",
        "Agregar bloque en .env.example (seccion 2.3).",
        "Actualizar/extender tests (seccion 4).",
        "Correr <i>pytest -q</i> localmente — 100% verde.",
    ]))

    s.append(H2("7.3 Pre-push"))
    s.extend(checklist([
        "Verificar que el diff toca solo los 4 archivos previstos.",
        "Verificar que no se filtro el secret real en codigo, comentarios, ni tests.",
        "Commit con mensaje descriptivo: <i>fix(seguridad): STRIPE_WEBHOOK_SECRET obligatorio en produccion (T0.2)</i>.",
    ]))

    s.append(H2("7.4 Post-push, pre-merge"))
    s.extend(checklist([
        "Push a origin/pr/stripe-webhook-firma-obligatoria.",
        "Abrir PR contra main en GitHub.",
        "<b>NO mergear</b> hasta confirmar visualmente que la env var en Render existe.",
    ]))

    s.append(H2("7.5 Post-merge"))
    s.extend(checklist([
        "Ver Render dashboard: deploy debe iniciar y completar sin RuntimeError al startup.",
        "Si Render falla con 'RuntimeError: STRIPE_WEBHOOK_SECRET', revertir el merge inmediatamente y diagnosticar la env var antes de re-mergear.",
        "Hacer una compra de prueba en Stripe (modo test) y verificar que llega el webhook y acredita correctamente.",
        "Verificar logs Render por '[BILLING] Firma Stripe invalida' los primeros 30 minutos.",
    ]))

    # ── 8. Resumen ejecutivo ────────────────────────────────────────────
    s.append(H1("8. Resumen ejecutivo"))
    resumen_rows = [
        ["Aspecto", "Detalle"],
        ["Riesgo que cierra", "P0 — acreditacion de creditos forjable"],
        ["Patron", "Replica agent/crypto.py (RuntimeError en production sin secret)"],
        ["Archivos", "4 (1 codigo nuevo, 1 import 1 linea, 1 docs, 1 tests)"],
        ["Tamano", "~30-40 lineas netas"],
        ["Tests", "1 actualizado + 3-4 nuevos"],
        ["Env var", "STRIPE_WEBHOOK_SECRET debe estar en Render antes del merge"],
        ["Compatibilidad",
         "Path permisivo se mantiene en development|test. Tests existentes se actualizan, no se rompen"],
        ["Riesgo de deploy", "Bajo si la env var esta correcta en Render"],
        ["Reversible", "Si, redeploy del commit anterior en Render"],
    ]
    s.append(small_table(para_rows(resumen_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(Spacer(1, 14))
    s.append(P(
        "<b>Estado:</b> no implementado todavia. Esperando OK del owner para preparar el branch "
        "<i>pr/stripe-webhook-firma-obligatoria</i> con el cambio minimo descrito."
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
        title="Dona — Diagnostico T0.2 Stripe webhook",
        author="Diagnostico generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T0.2 Stripe webhook signature obligatorio · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
