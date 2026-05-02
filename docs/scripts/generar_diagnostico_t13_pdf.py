"""
Genera Diagnostico_T13_Stripe_Backend_2026-05-01.pdf con el diagnostico
de solo lectura de T1.3 Stripe / backend de creditos como fuente unica.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Diagnostico_T13_Stripe_Backend_2026-05-01.pdf"

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

    s.append(Paragraph("T1.3 — Stripe / backend de creditos como fuente unica", styles["TitleBig"]))
    s.append(Paragraph(
        "Diagnostico de solo lectura &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin cambios, sin commits, sin push.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Gap operativo critico:</b> el cliente paga $20/$40 mensual via Stripe -> Stripe entrega "
        "webhook al landing -> landing manda welcome WhatsApp -> <b>el backend Dona nunca se entera</b>. "
        "Resultado: el sistema cobra pero no acredita creditos. T1.3 cierra el gap con un bridge "
        "landing -> backend autenticado por HMAC, sin cambiar Stripe Dashboard."
    ))

    # ── 1. Diagnostico actual ──────────────────────────────────────────
    s.append(H1("1. Diagnostico actual"))

    s.append(H2("1.1 Mapa de flujo actual"))
    flujo = (
        "Cliente en usadona.com -> click 'Comenzar ahora' -> POST /api/checkout\n"
        "                                                        |\n"
        "                              Stripe Checkout (mode=subscription, $20 o $40/mes)\n"
        "                                                        |\n"
        "                              Cliente paga\n"
        "                                                        |\n"
        "        Stripe -> POST https://www.usadona.com/api/webhook (verificado, 200 OK hoy)\n"
        "                                                        |\n"
        "                                landing/app/api/webhook/route.ts\n"
        "                                                        |\n"
        "                +-- checkout.session.completed -> log + welcome WhatsApp via Whapi\n"
        "                +-- payment_intent.payment_failed -> log only\n"
        "                                                        |\n"
        "                                        return 200 {received:true}\n"
        "                                                        |\n"
        "                                        FIN -- no contacta backend\n"
        "                                        NO acredita creditos\n"
        "                                        NO persiste suscripcion\n"
    )
    s.append(CODE(flujo))
    s.append(P(
        "<b>Backend /webhook/stripe</b>: existe en agent/main.py:2122 con firma obligatoria (T0.2 mergeado), "
        "pero <b>no recibe trafico</b> porque Stripe Dashboard apunta al landing."
    ))

    s.append(H2("1.2 Estado del backend para creditos"))
    estado_rows = [
        ["Aspecto", "Estado"],
        ["agent/billing.py",
         "Implementado para <b>paquetes prepagos one-time</b> (100/500/2000 creditos) con env vars STRIPE_PRICE_PAQUETE_*."],
        ["agent/billing.py:procesar_evento_stripe",
         "Solo maneja checkout.session.completed y solo si metadata.creditos esta presente (formato paquete one-time)."],
        ["agent/memory.py:SaldoCreditos",
         "tabla simple con telefono (PK), saldo, total_comprado, total_consumido."],
        ["agent/memory.py:TransaccionCredito",
         "audit log con idempotencia por stripe_session_id."],
        ["Tabla suscripciones",
         "<b>No existe.</b> No hay SuscripcionStripe, Plan, customer_id ni subscription_id persistidos."],
        ["Manejo de invoice.* (renovaciones)", "<b>No implementado.</b>"],
        ["Manejo de subscription.{created,updated,deleted}", "<b>No implementado.</b>"],
    ]
    s.append(small_table(para_rows(estado_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(H2("1.3 Modelo de identidad usuario"))
    identidad_rows = [
        ["Lado", "Llave"],
        ["Backend", "telefono E.164 (PK universal en todas las tablas)."],
        ["Stripe", "customer.id + subscription.id."],
        ["Landing",
         "Sesion NextAuth amarrada al customer.id (no autenticada de verdad &mdash; tema separado de T0.1, no aplica aca)."],
        ["Webhook landing",
         "extrae phone desde session.metadata.phone o session.customer_details.phone."],
    ]
    s.append(small_table(para_rows(identidad_rows),
                         col_widths=[3.5*cm, 13.5*cm]))
    s.append(P(
        "<b>Coincidencia:</b> el phone del Stripe metadata es el mismo formato que el telefono del backend. "
        "Eso es bueno: misma llave, sin necesidad de tabla de mapping inicial."
    ))

    s.append(H2("1.4 Metadata de Stripe disponible hoy"))
    s.append(P("landing/app/api/checkout/route.ts:41-45 setea en cada Checkout Session:"))
    metadata_block = (
        "metadata: { plan, phone: phone || '' }\n"
        "phone_number_collection: { enabled: true }\n"
        "mode: 'subscription'\n"
    )
    s.append(CODE(metadata_block))
    s.append(P("Lo que llega en el webhook checkout.session.completed:"))
    md_rows = [
        ["Campo", "Valor"],
        ["session.metadata.plan", "'premium' o 'pro'"],
        ["session.metadata.phone", "E.164 que el cliente puso en el form"],
        ["session.customer_details.phone",
         "E.164 que Stripe recolecto (puede diferir del anterior)"],
        ["session.customer", "cus_xxx"],
        ["session.subscription", "sub_xxx"],
        ["session.id", "cs_xxx (idempotencia)"],
        ["session.metadata.creditos",
         "<b>NO existe</b> &mdash; el handler backend espera esto y por eso retorna {handled: false, reason: 'metadata faltante'}"],
    ]
    s.append(small_table(para_rows(md_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(H2("1.5 Backend recibe algun evento Stripe real hoy?"))
    s.append(P(
        "<b>No.</b> El webhook configurado en Stripe Dashboard es https://www.usadona.com/api/webhook "
        "(landing), no https://dona-agent.onrender.com/webhook/stripe (backend). El backend "
        "/webhook/stripe esta <b>listo y blindado pero sin trafico</b>."
    ))

    # ── 2. Gap exacto ──────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("2. Gap exacto"))
    gap_rows = [
        ["Capa", "Estado actual", "Lo que falta"],
        ["Recepcion del webhook", "Landing recibe Stripe ✓", "Bridge landing -> backend (no existe)"],
        ["Identificacion usuario", "phone viaja en metadata ✓", "Nada"],
        ["Mapping plan -> creditos", "No definido", "Decision owner: cuantos creditos por plan"],
        ["Persistencia suscripcion", "No hay tabla", "Crear tabla SuscripcionStripe"],
        ["Acreditacion primer pago",
         "Backend espera metadata.creditos (formato one-time)",
         "Extender para mode=subscription"],
        ["Renovaciones mensuales", "No implementado", "Manejar invoice.payment_succeeded"],
        ["Cambio/cancelacion de plan", "No implementado",
         "Manejar customer.subscription.{updated,deleted}"],
        ["Idempotencia eventos recurrentes",
         "Idempotencia por session_id (sirve solo primera vez)",
         "Idempotencia por event.id y/o invoice.id"],
        ["Welcome WhatsApp", "Landing lo manda ✓",
         "Decidir si se mantiene en landing o se mueve a backend"],
    ]
    s.append(small_table(para_rows(gap_rows),
                         col_widths=[4.5*cm, 5.5*cm, 7.0*cm]))
    s.append(P(
        "<b>El gap se resume asi:</b> <i>cliente paga $20/$40 mensual -> Stripe entrega webhook al landing -> "
        "landing manda welcome WhatsApp -> fin. El backend nunca se entera. El sistema de creditos sigue "
        "en cero hasta que alguien hace /admin/seed-creditos manual.</i>"
    ))

    # ── 3. Propuesta de arquitectura minima ────────────────────────────
    s.append(H1("3. Propuesta de arquitectura minima"))

    s.append(H2("3.1 Decision de ruteo del webhook Stripe"))
    s.append(P("Tres opciones evaluadas:"))
    opciones_rows = [
        ["Opcion", "Pro", "Contra", "Veredicto"],
        ["A. Mantener Stripe -> landing, agregar bridge landing -> backend (HMAC entre ellos)",
         "Cero cambio en Stripe Dashboard, transicion sin downtime",
         "Dos hops, mantenimiento doble",
         "<b>Recomendada para Phase 1</b>"],
        ["B. Mover Stripe -> backend directo, deprecar landing webhook",
         "Arquitectura limpia, una sola fuente",
         "Requiere cambio en Stripe Dashboard, ventana de retries delicados",
         "Recomendada para Phase 2 (despues de A)"],
        ["C. Stripe -> ambos endpoints simultaneos",
         "Cero downtime, ambos reciben",
         "Doble procesamiento, duplicacion si idempotencia falla",
         "<b>Descartada</b>"],
    ]
    s.append(small_table(para_rows(opciones_rows),
                         col_widths=[5.5*cm, 4.5*cm, 4.0*cm, 3.0*cm]))
    s.append(P("<b>Recomendacion: Opcion A en este PR, dejar la posibilidad de B para despues.</b>"))

    s.append(H2("3.2 Diagrama del flujo objetivo (Opcion A)"))
    diagrama = (
        "Cliente paga $20/$40\n"
        "        |\n"
        "Stripe Checkout\n"
        "        |\n"
        "Stripe -> POST https://www.usadona.com/api/webhook\n"
        "        |\n"
        "landing/app/api/webhook/route.ts\n"
        "        | verifica firma Stripe\n"
        "        +--> welcome WhatsApp via Whapi (sigue igual)\n"
        "        +--> POST https://dona-agent.onrender.com/internal/stripe-event   [NUEVO]\n"
        "              + Header X-Internal-Signature (HMAC del body con shared secret)\n"
        "              + Body: el evento Stripe verificado\n"
        "                            |\n"
        "                  agent/main.py:/internal/stripe-event   [NUEVO endpoint]\n"
        "                            | verifica HMAC del landing\n"
        "                            | deduplica por event.id\n"
        "                            v\n"
        "                  agent/billing.py:procesar_evento_suscripcion(evento)   [NUEVO]\n"
        "                            +- checkout.session.completed (mode=subscription)\n"
        "                            |    -> upsert SuscripcionStripe + acreditar creditos del mes\n"
        "                            +- invoice.payment_succeeded (renovacion)\n"
        "                            |    -> acreditar creditos del nuevo periodo (idempotente por invoice.id)\n"
        "                            +- customer.subscription.updated (cambio de plan)\n"
        "                            |    -> actualizar SuscripcionStripe (plan, status, creditos_mes)\n"
        "                            +- customer.subscription.deleted (cancelacion)\n"
        "                                 -> marcar SuscripcionStripe.status='canceled', no acreditar mas\n"
    )
    s.append(CODE(diagrama))

    s.append(H2("3.3 Por que un endpoint /internal/* y no reusar /webhook/stripe"))
    s.extend(bullets([
        "/webhook/stripe espera firma de Stripe directa. Si el landing reenvia, la firma original ya no aplica al body re-construido.",
        "/internal/stripe-event valida HMAC propio entre landing y backend con un secret nuevo (INTERNAL_BRIDGE_SECRET). El landing es el unico cliente legitimo.",
        "Mantener /webhook/stripe operativo permite migrar a Opcion B en el futuro sin tocar este endpoint.",
        "Sin doble proposito. Cada endpoint tiene una responsabilidad clara.",
    ]))

    s.append(H2("3.4 Idempotencia robusta"))
    idem_rows = [
        ["Capa", "Llave", "Proposito"],
        ["Landing recibe Stripe", "event.id",
         "Stripe puede reentregar; landing no debe procesar dos veces."],
        ["Bridge landing -> backend", "event.id",
         "Si landing reenvia retry, backend no procesa dos veces."],
        ["Backend acredita primer pago", "session.id (existente) o event.id",
         "Lo que ya hace, vale."],
        ["Backend acredita renovacion", "invoice.id",
         "Cada renovacion tiene invoice.id unico. <b>Nuevo</b>."],
        ["Backend persiste suscripcion", "subscription.id (PK)",
         "Una sola fila por suscripcion, upsert."],
    ]
    s.append(small_table(para_rows(idem_rows),
                         col_widths=[4.5*cm, 4.0*cm, 8.5*cm]))

    # ── 4. Archivos que tocaria ─────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("4. Archivos que tocaria"))

    s.append(H2("4.1 Backend (agent/)"))
    backend_rows = [
        ["Archivo", "Cambio"],
        ["agent/memory.py",
         "+ clase SuscripcionStripe con: telefono (FK logico), customer_id, subscription_id (PK), plan_codigo, price_id, status, creditos_mensuales, ultimo_invoice_acreditado, creado, actualizado. + clase EventoStripeProcesado con event_id (PK), tipo, recibido_en."],
        ["agent/billing.py",
         "+ procesar_evento_suscripcion(evento) con handlers para los 4 tipos. + helper creditos_de_plan(price_id) que mapea env vars STRIPE_CREDITOS_PREMIUM/PRO a int. + _evento_ya_procesado(event_id) para idempotencia."],
        ["agent/main.py",
         "+ endpoint POST /internal/stripe-event con verificacion HMAC del header X-Internal-Signature contra INTERNAL_BRIDGE_SECRET. + import top-level (mismo patron T0.2/T0.4)."],
        [".env.example",
         "+ INTERNAL_BRIDGE_SECRET (obligatorio en prod). + STRIPE_CREDITOS_PREMIUM y STRIPE_CREDITOS_PRO (default sugerido pendiente de decision owner)."],
        ["tests/test_billing.py",
         "+ tests para procesar_evento_suscripcion con cada uno de los 4 tipos + idempotencia + plan desconocido."],
        ["tests/test_main_internal_stripe.py (nuevo)",
         "+ tests del endpoint /internal/stripe-event: HMAC ausente/invalido/correcto, evento duplicado, evento bien procesado."],
        ["alembic/versions/00X_suscripcion_stripe.py (nuevo)",
         "migracion para crear suscripcion_stripe y evento_stripe_procesado."],
    ]
    s.append(small_table(para_rows(backend_rows),
                         col_widths=[5.5*cm, 11.5*cm]))

    s.append(H2("4.2 Landing (landing/)"))
    landing_rows = [
        ["Archivo", "Cambio"],
        ["landing/app/api/webhook/route.ts",
         "Despues del welcome WhatsApp, hacer fetch(BACKEND_URL + '/internal/stripe-event', {...}) con HMAC. Si falla, loguear pero no bloquear (Stripe ya considero el evento OK). Idealmente: queue de reintentos (Phase 2)."],
        ["landing/lib/internal-bridge.ts (nuevo)",
         "helper para firmar y enviar al backend, con timeout corto."],
        ["landing/.env (NO TOCAR DESDE CODIGO)",
         "Vercel env: INTERNAL_BRIDGE_SECRET (mismo valor que en Render) + BACKEND_URL=https://dona-agent.onrender.com."],
    ]
    s.append(small_table(para_rows(landing_rows),
                         col_widths=[5.5*cm, 11.5*cm]))
    s.append(P(
        "<b>Nota:</b> el landing existente no requiere cambios disruptivos. El welcome WhatsApp sigue donde "
        "esta. Solo se agrega un fetch al final del handler."
    ))

    s.append(H2("4.3 Lo que NO toco en este PR"))
    s.extend(bullets([
        "/webhook/stripe directo en backend -> queda como esta (blindado, sin trafico).",
        "Stripe Dashboard URL -> no se modifica.",
        "Tablas existentes (SaldoCreditos, TransaccionCredito) -> sin alteraciones.",
        "Modelo de paquetes one-time prepagos -> sigue funcional, complementario al de suscripciones.",
        "Welcome WhatsApp -> sigue en landing por ahora.",
    ]))

    # ── 5. Cambios DB / migraciones ────────────────────────────────────
    s.append(H1("5. Cambios de DB / migraciones"))

    s.append(H2("5.1 Tabla nueva suscripcion_stripe"))
    sub_class = (
        'class SuscripcionStripe(Base):\n'
        '    __tablename__ = "suscripcion_stripe"\n'
        '\n'
        '    subscription_id: Mapped[str] = mapped_column(String(200), primary_key=True)\n'
        '    telefono: Mapped[str] = mapped_column(String(50), index=True)\n'
        '    customer_id: Mapped[str] = mapped_column(String(200), index=True)\n'
        '    plan_codigo: Mapped[str] = mapped_column(String(50))   # "premium" | "pro"\n'
        '    price_id: Mapped[str] = mapped_column(String(200))\n'
        '    status: Mapped[str] = mapped_column(String(40))         # active | past_due | canceled | incomplete\n'
        '    creditos_mensuales: Mapped[int] = mapped_column(Integer)\n'
        '    ultimo_invoice_acreditado: Mapped[str] = mapped_column(String(200), default="")\n'
        '    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)\n'
        '    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)\n'
    )
    s.append(CODE(sub_class))

    s.append(H2("5.2 Tabla nueva evento_stripe_procesado"))
    evt_class = (
        'class EventoStripeProcesado(Base):\n'
        '    __tablename__ = "evento_stripe_procesado"\n'
        '\n'
        '    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)\n'
        '    tipo: Mapped[str] = mapped_column(String(80), index=True)\n'
        '    recibido_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)\n'
    )
    s.append(CODE(evt_class))

    s.append(H2("5.3 Migracion Alembic"))
    s.append(P(
        "alembic/versions/00X_suscripcion_stripe.py con upgrade() que crea ambas tablas y downgrade() "
        "que las dropea. Sin tocar 001_estado_inicial.py."
    ))
    s.append(P(
        "<b>Nota critica:</b> el repo aun usa metadata.create_all() en agent/main.py:lifespan (T4.3 esta "
        "pendiente). Eso significa que las tablas nuevas se crean automaticamente al arrancar si no "
        "existen &mdash; la migracion Alembic es idempotente y redundante con el create_all, pero conviene "
        "tenerla para tener un baseline registrado."
    ))

    # ── 6. Tests necesarios ────────────────────────────────────────────
    s.append(H1("6. Tests necesarios"))

    s.append(H2("6.1 Backend"))
    tests_block = (
        'class TestProcesarEventoSuscripcion:\n'
        '    def test_checkout_session_completed_subscription_acredita_y_persiste\n'
        '    def test_checkout_session_completed_payment_legacy_sigue_funcionando  # paquetes prepagos\n'
        '    def test_invoice_payment_succeeded_acredita_creditos_del_periodo\n'
        '    def test_invoice_payment_succeeded_idempotente_por_invoice_id\n'
        '    def test_subscription_updated_cambia_plan_y_creditos_mensuales\n'
        '    def test_subscription_deleted_marca_canceled_y_no_acredita_mas\n'
        '    def test_evento_duplicado_por_event_id_se_ignora\n'
        '    def test_plan_desconocido_no_acredita_y_loguea_warning\n'
        '    def test_telefono_faltante_loguea_y_no_acredita\n'
        '\n'
        'class TestInternalStripeEndpoint:\n'
        '    def test_hmac_ausente_responde_401\n'
        '    def test_hmac_invalido_responde_401\n'
        '    def test_hmac_valido_procesa_evento\n'
        '    def test_production_sin_INTERNAL_BRIDGE_SECRET_aborta_startup\n'
        '    def test_evento_duplicado_responde_200_idempotente\n'
    )
    s.append(CODE(tests_block))
    s.append(P("Total estimado: <b>~12-14 tests nuevos</b>."))

    s.append(H2("6.2 Landing"))
    s.append(P(
        "El landing hoy no tiene suite de tests visible &mdash; eso es deuda separada. Para este PR podemos "
        "limitarnos a tests manuales del lado landing."
    ))

    # ── 7. Riesgos ─────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("7. Riesgos"))
    riesgos_rows = [
        ["Riesgo", "Probabilidad", "Impacto", "Mitigacion"],
        ["<b>Doble acreditacion</b> si Stripe reentrega el webhook al landing",
         "Baja", "Alto",
         "Idempotencia por event.id en backend (evento_stripe_procesado)"],
        ["<b>Doble acreditacion</b> si landing reenvia al backend dos veces",
         "Baja-media", "Alto",
         "Misma idempotencia"],
        ["<b>Perdida de eventos</b> si fetch landing -> backend falla",
         "Media", "Medio",
         "Stripe reintenta 3 veces si landing responde no-200; si landing siempre responde 200, se pierde. <b>Mitigacion: landing responde 500 a Stripe si bridge falla</b> (Stripe reintenta) o <b>logea + responde 200</b> (cliente recibe welcome igual; bridge se completa por mecanismo manual). Decision owner."],
        ["<b>Plan desconocido</b> (price_id que no matchea Premium/Pro)",
         "Baja", "Medio",
         "Loguear warning + no acreditar; alerta al admin."],
        ["<b>Mismatch telefono</b> entre metadata.phone y customer_details.phone",
         "Media", "Bajo",
         "Preferir metadata.phone (form del cliente); fallback a customer_details.phone."],
        ["<b>Subscription cambia de plan</b> sin que recibamos el evento",
         "Baja", "Medio",
         "Si llega el siguiente invoice.payment_succeeded, leemos price_id actual del Stripe customer para reconciliar."],
        ["<b>Cliente paga pero no completa onboarding</b>",
         "Existente", "Bajo",
         "Welcome WhatsApp ya cubre eso. Backend acredita; cuando el cliente conecte por WhatsApp con el mismo numero, ve sus creditos."],
        ["<b>Race condition</b> entre primer checkout.session.completed y primer invoice.payment_succeeded (mismo periodo)",
         "Baja", "Medio",
         "Acreditar <b>solo</b> en invoice.payment_succeeded y dejar checkout.session.completed para crear/actualizar la suscripcion. Mi voto: simpler asi."],
        ["<b>Vercel env vars desincronizadas</b> con Render env vars (mismo INTERNAL_BRIDGE_SECRET)",
         "Media", "Alto",
         "Setear ambos juntos antes del merge. Documentar."],
    ]
    s.append(small_table(para_rows(riesgos_rows),
                         col_widths=[5.0*cm, 2.5*cm, 2.0*cm, 7.5*cm]))

    # ── 8. Plan por PRs ────────────────────────────────────────────────
    s.append(H1("8. Plan de implementacion por PRs pequenos"))

    s.append(H2("PR T1.3.A — Modelos + migracion (backend solo)"))
    s.extend(bullets([
        "agent/memory.py: clases SuscripcionStripe, EventoStripeProcesado.",
        "alembic/versions/00X_suscripcion_stripe.py.",
        "Tests de modelo simple (insert/query).",
        "<b>Cero impacto en produccion</b>: solo crea tablas vacias al deploy.",
        "~80 lineas.",
    ]))

    s.append(H2("PR T1.3.B — Helper creditos_de_plan + matrices (backend solo)"))
    s.extend(bullets([
        "agent/billing.py: helper que mapea price_id -> creditos mensuales segun env vars STRIPE_CREDITOS_PREMIUM / STRIPE_CREDITOS_PRO.",
        ".env.example: documentar las dos variables nuevas.",
        "Tests del helper.",
        "<b>Cero impacto en produccion</b> sin las env vars seteadas.",
        "~30 lineas. <b>Bloqueador: decision owner sobre cuantos creditos.</b>",
    ]))

    s.append(H2("PR T1.3.C — procesar_evento_suscripcion + idempotencia (backend solo)"))
    s.extend(bullets([
        "agent/billing.py: nueva funcion con los 4 handlers.",
        "agent/billing.py: helper _evento_ya_procesado(event_id).",
        "Tests exhaustivos.",
        "<b>Cero impacto en produccion</b> sin endpoint que la invoque.",
        "~150 lineas (incluyendo tests).",
    ]))

    s.append(H2("PR T1.3.D — Endpoint /internal/stripe-event con HMAC (backend solo)"))
    s.extend(bullets([
        "agent/main.py: endpoint nuevo + verificacion HMAC + import top-level fail-fast en prod sin INTERNAL_BRIDGE_SECRET.",
        ".env.example: documentar INTERNAL_BRIDGE_SECRET.",
        "Tests del endpoint.",
        "<b>Cero impacto en produccion</b> mientras nadie lo invoque (landing aun no lo usa).",
        "~100 lineas (incluyendo tests).",
    ]))

    s.append(H2("PR T1.3.E — Bridge landing -> backend (landing solo)"))
    s.extend(bullets([
        "landing/app/api/webhook/route.ts: agregar fetch al final del handler.",
        "landing/lib/internal-bridge.ts: helper de firma + envio.",
        "<b>Impacto en produccion</b>: ahora cada checkout.session.completed reenvia. Riesgo: si backend falla, decidir 200 o 500 a Stripe.",
        "<b>Pre-requisito</b>: setear INTERNAL_BRIDGE_SECRET en Vercel y Render con el mismo valor.",
        "~40 lineas.",
    ]))

    s.append(H2("PR T1.3.F (opcional) — Mover Stripe Dashboard a backend directo"))
    s.extend(bullets([
        "Solo cuando T1.3.E haya estado estable por una semana.",
        "Cambiar URL en Stripe Dashboard a https://dona-agent.onrender.com/webhook/stripe.",
        "Adaptar agent/billing.py:procesar_evento_stripe para invocar procesar_evento_suscripcion cuando sea de subscription.",
        "Landing webhook se vuelve dead code -> deprecar en housekeeping.",
    ]))

    # ── 9. Checklist ───────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("9. Checklist antes de merge / deploy"))

    s.append(H2("9.1 Pre-PR (decisiones bloqueantes del owner)"))
    s.extend(checklist([
        "<b>Cuantos creditos por plan</b>: Premium $20 -> ¿N creditos/mes? Pro $40 -> ¿M creditos/mes? Recomendacion tentativa: Premium 100, Pro 500 (para empezar conservador).",
        "<b>Comportamiento ante fallo del bridge</b>: si backend no responde, ¿landing devuelve 200 a Stripe (cliente queda sin creditos hasta reconcilio manual) o 500 (Stripe reintenta hasta 3 veces; tras eso cliente queda sin creditos)?",
        "<b>Renovaciones</b>: ¿creditos se acumulan mes a mes (cliente nunca pierde) o se resetean al inicio de cada periodo?",
        "<b>Cancelacion</b>: cuando subscription se cancela, ¿creditos restantes se mantienen hasta consumir, o se borran al final del periodo pago?",
        "<b>Generar INTERNAL_BRIDGE_SECRET</b> con <i>python -c \"import secrets; print(secrets.token_urlsafe(32))\"</i>.",
    ]))

    s.append(H2("9.2 Pre-merge (operativo)"))
    s.extend(checklist([
        "STRIPE_CREDITOS_PREMIUM y STRIPE_CREDITOS_PRO seteados en Render.",
        "INTERNAL_BRIDGE_SECRET seteado tanto en <b>Vercel (landing)</b> como en <b>Render (backend)</b> con el <b>mismo valor</b>.",
        "Confirmar que la URL del backend desde Vercel es accesible (sin firewall ni IP allowlist).",
        "Decidir si se mantiene welcome WhatsApp en landing o se mueve a backend (recomendacion: mantener en landing por ahora, mover en T1.3.F).",
    ]))

    s.append(H2("9.3 Durante el PR (local)"))
    s.extend(checklist([
        "Implementar PR T1.3.A -> D en orden, mergeando uno por uno.",
        "Despues del .D mergeado y desplegado: implementar T1.3.E.",
        "<i>pytest -q</i> localmente verde en cada PR.",
        "Tests manuales con Stripe Test Mode antes de mergear T1.3.E.",
    ]))

    s.append(H2("9.4 Post-merge (verificacion)"))
    s.extend(checklist([
        "Hacer una compra real en <b>modo test</b> desde la landing.",
        "Verificar Render logs: '[BILLING] Acreditado N cr -> +XXX...' y '[INTERNAL] Evento procesado: event_id=evt_...'.",
        "Verificar DB backend: fila en suscripcion_stripe + fila en transacciones_credito + saldo en saldo_creditos correcto.",
        "Verificar que el cliente recibe welcome WhatsApp Y que <i>dona saldo</i> por WhatsApp le devuelve los creditos correctos.",
        "Esperar primera renovacion real (siguiente mes) y verificar que invoice.payment_succeeded acredita el segundo periodo.",
    ]))

    # ── 10. Resumen ejecutivo ──────────────────────────────────────────
    s.append(H1("10. Resumen ejecutivo"))
    resumen_rows = [
        ["Aspecto", "Detalle"],
        ["<b>Gap operativo</b>",
         "Cliente paga $20/$40 mensual -> backend Dona no acredita creditos -> producto cobra pero no entrega"],
        ["<b>Causa raiz</b>",
         "Stripe webhook va al landing, landing solo manda welcome, backend nunca se entera"],
        ["<b>Solucion minima</b>",
         "Bridge landing -> backend con HMAC + nuevas tablas + handlers de subscription/invoice events"],
        ["<b>Patron</b>",
         "Opcion A (mantener Stripe en landing, agregar bridge interno). Opcion B (mover Stripe al backend) queda para Phase 2"],
        ["<b>Archivos</b>",
         "Backend: 4 archivos (memory.py, billing.py, main.py, .env.example) + 2 tests + 1 migracion Alembic. Landing: 2 archivos (webhook/route.ts, lib/internal-bridge.ts)"],
        ["<b>DB</b>",
         "2 tablas nuevas: suscripcion_stripe, evento_stripe_procesado"],
        ["<b>Tests</b>", "~12-14 nuevos en backend"],
        ["<b>PRs</b>", "5 pequenos (A->E) en orden, opcional F despues"],
        ["<b>Decisiones bloqueantes del owner</b>",
         "4 (creditos por plan, comportamiento ante fallo bridge, acumulacion renovaciones, cancelacion)"],
        ["<b>Riesgo de deploy</b>",
         "Bajo si las env vars estan seteadas y los PRs van en orden"],
        ["<b>Welcome WhatsApp actual</b>",
         "Se mantiene en landing por simplicidad; se mueve a backend en T1.3.F (opcional)"],
    ]
    s.append(small_table(para_rows(resumen_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(Spacer(1, 14))
    s.append(P(
        "<b>Estado:</b> no implementado todavia. Esperando OK del owner con respuesta a las 4 decisiones "
        "bloqueantes y autorizacion para arrancar con PR T1.3.A."
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
        title="Dona — Diagnostico T1.3 Stripe / backend creditos",
        author="Diagnostico generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T1.3 Stripe / backend creditos · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
