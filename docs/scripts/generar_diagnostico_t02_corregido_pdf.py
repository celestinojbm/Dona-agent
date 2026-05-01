"""
Genera Diagnostico_T02_Corregido_2026-05-01.pdf con el diagnostico
corregido tras descubrir que el webhook Stripe configurado apunta a
landing/api/stripe/webhook (ruta que no existe en el repo) y que el
backend /webhook/stripe esta sin trafico.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Diagnostico_T02_Corregido_2026-05-01.pdf"

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


def checklist(items):
    return [Paragraph(
        '<font face="Helvetica-Bold">[ ]</font> ' + it,
        styles["BulletDona"],
    ) for it in items]


def build_story():
    s = []

    # Portada
    s.append(Paragraph("T0.2 — Diagnostico corregido", styles["TitleBig"]))
    s.append(Paragraph(
        "Revision post-hallazgo &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin cambios, sin commits, sin push.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Hallazgo nuevo del owner:</b> en Stripe Dashboard solo hay un webhook activo apuntando "
        "a <i>https://www.usadona.com/api/stripe/webhook</i>. No hay webhook configurado al backend "
        "Render. Esto cambia varios supuestos del diagnostico anterior."
    ))

    # ── 1. Backend /webhook/stripe ──────────────────────────────────────
    s.append(H1("1. Backend /webhook/stripe esta siendo usado hoy?"))
    s.append(P("<b>No.</b> Tres evidencias:"))
    s.extend(bullets([
        "Stripe Dashboard apunta a https://www.usadona.com/..., no a Render. El backend en Render no recibe webhooks de Stripe hoy.",
        "Stripe NO permite enviar el mismo evento a dos endpoints simultaneos desde un solo webhook configurado. Si solo hay un webhook listado y va al landing, el backend esta sin trafico.",
        "El endpoint backend esta vivo en codigo (agent/main.py:2112-2151) y es <b>publico</b>. No requiere autenticacion HTTP. El fallback de firma sigue activo.",
    ]))
    s.append(P(
        "<b>Conclusion:</b> /webhook/stripe en backend es <b>dead code en trafico real</b>, pero "
        "<b>superficie de ataque publica</b> abierta."
    ))

    # ── 2. Flujo actual depende del webhook de la landing? ──────────────
    s.append(H1("2. El flujo actual depende del webhook de la landing?"))
    s.append(P("Si — y el flujo actual es <b>muy delgado</b>:"))
    s.append(P("landing/app/api/webhook/route.ts &mdash; recibe checkout.session.completed:"))
    s.extend(bullets([
        "Loguea 'Payment successful for &lt;customer_email&gt; — plan: &lt;plan&gt;'.",
        "Si hay metadata.phone o customer_details.phone, manda un unico mensaje WhatsApp via Whapi: 'Hola! Soy Dona, tu nueva asistente. Tu suscripcion esta activa...'.",
        "<b>NO acredita creditos.</b> No llama al backend Python. No persiste la suscripcion.",
    ]))
    s.append(P(
        "landing/app/api/webhook/route.ts:20 ya tiene STRIPE_WEBHOOK_SECRET! (non-null assertion: throw "
        "si no esta) y rechaza con 400 si falta firma o si constructEvent falla. <b>A nivel codigo del "
        "landing, T0.2 ya esta implementado funcionalmente.</b>"
    ))

    # ── 3. Conexion landing -> backend para acreditar ───────────────────
    s.append(H1("3. Hay conexion landing -> backend para acreditar creditos?"))
    s.append(P("<b>No.</b> Verifique tres caminos posibles:"))
    s.extend(bullets([
        "landing/lib/whatsapp.ts &mdash; solo Whapi directo, no llama al backend.",
        "landing/app/api/webhook/route.ts &mdash; no hace fetch al backend.",
        "landing/app/api/checkout/route.ts &mdash; crea Checkout Session en Stripe; metadata {plan, phone}. No notifica al backend.",
        "No hay landing/middleware.ts ni vercel.json con rewrites a dona-agent.onrender.com.",
    ]))

    s.append(H3("Realidad operativa actual"))
    realidad_rows = [
        ["Cliente paga $20/$40 mensual en Stripe", "Resultado"],
        ["Stripe cobra al cliente", "OK"],
        ["Stripe envia checkout.session.completed a webhook configurado", "depende de la URL real"],
        ["Welcome WhatsApp (si webhook llega)", "OK (via Whapi en landing)"],
        ["Creditos acreditados en backend", "<b>ninguno</b>"],
        ["Suscripcion persistida en DB del backend", "<b>ninguno</b>"],
        ["Plan/tier sincronizado en backend", "<b>ninguno</b>"],
    ]
    s.append(small_table(para_rows(realidad_rows),
                         col_widths=[10.0*cm, 7.0*cm]))
    s.append(P(
        "<b>El backend Python no se entera de los pagos.</b> El cliente paga la suscripcion pero el "
        "sistema de creditos sigue en cero hasta que alguien hace /admin/seed-creditos manual."
    ))

    # ── 4. Que endpoint deberia recibir los eventos? ────────────────────
    s.append(PageBreak())
    s.append(H1("4. Que endpoint deberia recibir los eventos en la arquitectura actual?"))

    s.append(H3("Hoy en codigo existen dos handlers de Stripe:"))
    s.extend(bullets([
        "landing/app/api/webhook/route.ts &rarr; ruta publica https://www.usadona.com/api/webhook. Funcional pero solo manda welcome.",
        "agent/main.py:/webhook/stripe &rarr; ruta publica https://&lt;render&gt;/webhook/stripe. Funcional con fallback inseguro; sin trafico.",
    ]))

    s.append(H3("Lo que dijiste:"))
    s.append(P(
        "Stripe Dashboard apunta a https://www.usadona.com/api/stripe/webhook."
    ))

    s.append(H3("Realidad del repo:"))
    s.append(P(
        "<b>NO existe landing/app/api/stripe/webhook/route.ts.</b> El unico webhook handler en la "
        "landing esta en landing/app/api/webhook/."
    ))

    s.append(H3("Tres escenarios posibles (necesitan tu confirmacion):"))
    escenarios_rows = [
        ["Escenario", "Que pasa hoy", "Probabilidad"],
        ["A. La URL en Stripe Dashboard es /api/stripe/webhook literal",
         "Stripe entrega a una ruta que <b>devuelve 404</b>. Ningun evento se procesa. Welcome WhatsApp NO se envia.",
         "Alta si copiaste la URL textual del Dashboard."],
        ["B. La URL en Stripe Dashboard es /api/webhook y mencionaste /api/stripe/webhook por confusion visual",
         "El landing recibe el evento y manda el welcome.",
         "Media."],
        ["C. Hay un rewrite Vercel server-side (no en este repo) que mapea /api/stripe/webhook -> /api/webhook",
         "Funciona como B.",
         "Baja. No hay next.config.ts/middleware.ts/vercel.json con rewrites en el repo."],
    ]
    s.append(small_table(para_rows(escenarios_rows),
                         col_widths=[5.5*cm, 7.5*cm, 4.0*cm]))

    s.append(P(
        "<b>Recomendacion inmediata:</b> verificar tres cosas en Stripe Dashboard antes de cualquier "
        "cambio de codigo:"
    ))
    s.extend(bullets([
        "La URL exacta del endpoint (copy-paste, no a vista).",
        "La pestana 'Events' / 'Webhook attempts' del endpoint &mdash; ahi ves si los ultimos eventos respondieron 200 (OK) o 404 (URL muerta).",
        "Si los ultimos welcome WhatsApp post-pago efectivamente llegaron a los compradores. Si no, escenario A confirmado.",
    ]))

    # ── 5. T0.2 al backend, landing o ambos? ────────────────────────────
    s.append(H1("5. T0.2 al backend, al landing, o a ambos?"))
    aplica_rows = [
        ["Componente", "Estado de T0.2", "Accion"],
        ["Landing /api/webhook",
         "<b>Ya implementado</b> funcionalmente. STRIPE_WEBHOOK_SECRET! con non-null assertion + constructEvent que rechaza firma invalida.",
         "Nada de codigo. Solo verificar que la env var este en Vercel (no en Render)."],
        ["Backend /webhook/stripe",
         "<b>No implementado.</b> Fallback inseguro presente. Endpoint publico sin trafico.",
         "T0.2 sigue aplicando. La justificacion cambia: no es para 'blindar webhook activo' sino para <b>cerrar superficie de ataque publica</b>."],
    ]
    s.append(small_table(para_rows(aplica_rows),
                         col_widths=[3.5*cm, 7.5*cm, 6.0*cm]))

    s.append(P("<b>T0.2 sigue valiendo la pena en el backend</b> porque:"))
    s.extend(bullets([
        "El endpoint /webhook/stripe esta publicamente expuesto en Render.",
        "agent/billing.py:procesar_evento_stripe esta conectado al sistema real de creditos (acreditar() y cobrar() siguen vivos).",
        "Un atacante que descubra la URL puede acreditar creditos forjados a su telefono y luego usar tools creativas (imagen/video/voz) que si funcionan en produccion.",
    ]))
    s.append(P(
        "<b>Riesgo P0 sigue abierto</b> aunque el webhook de Stripe no este apuntando ahi."
    ))

    # ── 6. Riesgo real actual ───────────────────────────────────────────
    s.append(H1("6. Riesgo real actual si solo existe webhook en usadona.com/api/stripe/webhook"))

    s.append(H3("Riesgos operativos (no de seguridad)"))
    s.extend(bullets([
        "<b>Si la URL es 404 (escenario A):</b> el negocio cobra suscripciones pero nadie procesa el checkout.session.completed &rarr; <b>ningun cliente recibe el welcome WhatsApp</b>, y como el backend tampoco acredita creditos, el cliente paga y queda sin nada visible. <b>Riesgo de churn / chargebacks / soporte.</b>",
        "<b>Si la URL es correcta (B/C):</b> welcome funciona. Pero los creditos siguen sin acreditarse en backend (no hay nadie que llame a acreditar).",
    ]))

    s.append(H3("Riesgos de seguridad (independientes de la URL del Dashboard)"))
    s.extend(bullets([
        "<b>/webhook/stripe en Render con fallback inseguro:</b> P0 abierto. Cualquiera que descubra https://&lt;render&gt;/webhook/stripe puede mandar payload forjado y le acreditan creditos.",
        "<b>/api/webhook en Vercel:</b> P0 cerrado funcionalmente (firma obligatoria por non-null assertion + constructEvent).",
    ]))

    s.append(H3("Riesgo combinado"))
    s.extend(bullets([
        "<b>Ya existe un cliente que pago.</b> Si ningun sistema acredita creditos, la 'compra' en terminos de producto no se materializa. Independiente de T0.2, hay un <b>gap funcional</b> entre 'Stripe cobro' y 'Dona entrego'.",
    ]))

    # ── 7. Plan corregido ──────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("7. Plan corregido minimo y seguro"))
    s.append(P(
        "Lo divido en cuatro bloques con prioridades distintas. <b>No mezclar</b> en un solo PR."
    ))

    s.append(H2("Bloque 1 — Verificacion operativa (sin codigo, prioridad alta)"))
    s.append(P("Antes de cualquier PR:"))
    s.extend(checklist([
        "Confirmar URL exacta del webhook en Stripe Dashboard (copy-paste). Es /api/stripe/webhook o /api/webhook?",
        "Revisar en Stripe Dashboard -> Webhook -> 'Events' los ultimos 5 intentos: respondieron 200 o 404?",
        "Verificar con un cliente real reciente si el welcome WhatsApp llego.",
        "Confirmar STRIPE_WEBHOOK_SECRET esta seteada en <b>Vercel</b> (no en Render) y matchea con el 'Signing secret' del endpoint configurado.",
    ]))
    s.append(C(
        "Sin estas respuestas, no se puede decidir si el escenario es A, B o C. El resto del trabajo depende."
    ))

    s.append(H2("Bloque 2 — T0.2 backend (PR de seguridad, prioridad alta)"))
    s.append(P("<b>Sigue siendo valido y necesario.</b> Cierra el riesgo P0 del endpoint publico backend."))
    s.append(P("Cambios minimos (los del diagnostico anterior):"))
    s.extend(bullets([
        "agent/billing.py: top-level RuntimeError si ENVIRONMENT=production y no hay STRIPE_WEBHOOK_SECRET. Modifica verificar_firma_stripe para retornar None en produccion sin secret.",
        "agent/main.py: import top-level de agent.billing para forzar el check al startup.",
        ".env.example: documentar la variable.",
        "tests/test_billing.py: actualizar/extender.",
    ]))

    s.append(H3("Cambio respecto al diagnostico anterior:"))
    s.extend(bullets([
        "La env var STRIPE_WEBHOOK_SECRET debe estar en <b>Render</b> (backend), pero el valor puede ser <b>el mismo que esta en Vercel</b> (mismo Signing secret de Stripe). No hace falta crear un segundo webhook en Stripe &mdash; el backend simplemente queda blindado para cuando se decida T1.3 (mover el webhook al backend).",
        "Si queres que sea un placeholder distinto y no compartir el secret real entre Vercel y Render, podes setear en Render un valor distinto (cualquier string whsec_* placeholder). El endpoint queda blindado (rechaza todo en produccion) hasta que T1.3 cree un webhook real apuntando a Render.",
        "<b>Recomendacion:</b> compartir el mismo secret. Es mas simple y el dia que migremos el webhook a Render, ya esta listo.",
    ]))

    s.append(H2("Bloque 3 — Routing landing (operativo, prioridad alta-media)"))
    s.append(P("Independiente de T0.2. Accion depende del escenario:"))
    s.extend(bullets([
        "<b>Si A (404):</b> elegir entre:",
    ]))
    s.extend([Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&bull; 3a. Cambiar la URL en Stripe Dashboard a /api/webhook. <b>Cero codigo.</b>", styles["BulletDona"]),
              Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&bull; 3b. Crear landing/app/api/stripe/webhook/route.ts (identico al actual /api/webhook o reutilizando el handler). <b>PR de landing pequeno.</b>", styles["BulletDona"])])
    s.extend(bullets([
        "<b>Si B/C:</b> ninguna accion.",
    ]))

    s.append(H2("Bloque 4 — Decision arquitectonica (T1.3 del Plan v2.1)"))
    s.append(P("Despues de B2 + B3, la decision que sigue es:"))
    s.extend(bullets([
        "<b>Quien acredita creditos al pagar la suscripcion?</b> Hoy nadie. Hay que conectar el webhook con agent/billing.py:acreditar().",
        "<b>Backend Python como fuente unica (Plan v2.1 §A.2.2)?</b> Mover el webhook de Stripe del landing al backend, deprecar el welcome del landing, y procesar todo en backend (acreditar + welcome).",
    ]))
    s.append(P(
        "Eso ya <b>no es T0.2 ni Phase 0</b>. Es Phase 1 (T1.3 + T1.4). Sale fuera del alcance de "
        "este reporte."
    ))

    # ── 8. Diferencia con el diagnostico anterior ───────────────────────
    s.append(H1("8. Diferencia con el diagnostico anterior"))
    diff_rows = [
        ["Aspecto", "Diagnostico anterior", "Diagnostico corregido"],
        ["Webhook backend /webhook/stripe", "Asumido activo", "<b>Confirmado dead code en trafico</b>, pero superficie de ataque publica"],
        ["Webhook landing /api/webhook", "Mencionado como 'independiente'", "<b>T0.2 ya implementado funcionalmente</b>; sin cambios de codigo"],
        ["URL en Stripe Dashboard", "No verificada", "<b>Reportada como /api/stripe/webhook</b> &mdash; no matchea con codigo"],
        ["Conexion landing -> backend para acreditar", "Implicito", "<b>Confirmado: no existe</b>"],
        ["Justificacion de T0.2 backend", "'Blindar webhook activo'", "'Cerrar superficie de ataque del endpoint publico sin trafico'"],
        ["Variable a configurar", "STRIPE_WEBHOOK_SECRET en Render", "<b>Igual.</b> Recomendacion nueva: mismo valor que Vercel, o placeholder."],
        ["Bloques del trabajo", "1 (T0.2 backend)", "3 (verificacion + T0.2 backend + routing landing) + Bloque 4 fuera de scope"],
    ]
    s.append(small_table(para_rows(diff_rows),
                         col_widths=[4.0*cm, 5.5*cm, 7.5*cm]))

    # ── 9. Recomendacion de orden ───────────────────────────────────────
    s.append(H1("9. Recomendacion de orden"))
    s.extend(bullets([
        "<b>Bloque 1 ahora</b>: investigacion operativa en Stripe Dashboard (5 min, sin codigo). Sin esto, no podes saber si los pagos estan entregando welcome WhatsApp.",
        "<b>Bloque 2</b> despues: T0.2 backend (PR pequeno, riesgo bajo). Cierra P0 sin necesitar Stripe operativo.",
        "<b>Bloque 3</b> en paralelo o despues: si A se confirma, decidir 3a vs 3b. Es 5 min de Dashboard o un PR de landing pequeno.",
        "<b>Bloque 4</b> despues de Phase 0: decision de arquitectura T1.3 (acreditacion de creditos por suscripcion).",
    ]))

    # ── 10. Resumen ejecutivo ───────────────────────────────────────────
    s.append(H1("10. Resumen ejecutivo"))
    s.extend(bullets([
        "<b>Backend /webhook/stripe no recibe trafico hoy</b> (Stripe no apunta ahi), pero esta publicamente expuesto con fallback inseguro &rarr; <b>P0 vigente</b>.",
        "<b>Landing /api/webhook ya tiene firma obligatoria por codigo.</b> T0.2 a nivel codigo del landing no requiere PR.",
        "<b>Stripe Dashboard apunta a usadona.com/api/stripe/webhook</b> &mdash; esa ruta <b>no existe en el repo</b>. Hay alta probabilidad de que los webhooks esten fallando con 404 silenciosamente.",
        "<b>El sistema de creditos del backend no se acredita al cobrar suscripciones</b>: gap funcional independiente de T0.2.",
        "<b>T0.2 backend sigue siendo PR valido y necesario</b>, con justificacion corregida: cerrar superficie de ataque publica.",
    ]))

    s.append(Spacer(1, 14))
    s.append(P(
        "<b>Estado:</b> no implementado todavia. Esperando confirmacion del owner de:"
    ))
    s.extend(bullets([
        "(1) URL exacta del webhook en Stripe Dashboard.",
        "(2) Decision sobre Bloque 3 (arreglar routing) y si avanzo con Bloque 2 (PR backend) en paralelo.",
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
        title="Dona — Diagnostico T0.2 corregido",
        author="Diagnostico generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T0.2 Diagnostico corregido · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
