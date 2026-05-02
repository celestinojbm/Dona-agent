"""
Genera Diagnostico_T010_Whapi_Webhook_2026-05-01.pdf con el diagnostico
de solo lectura de T0.10 Whapi webhook signature validation.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Diagnostico_T010_Whapi_Webhook_2026-05-01.pdf"

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

    s.append(Paragraph("T0.10 — Whapi webhook signature validation", styles["TitleBig"]))
    s.append(Paragraph(
        "Diagnostico de solo lectura &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin cambios, sin commits, sin push.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Hallazgo clave:</b> Whapi <b>no usa HMAC signature</b>. Su modelo de seguridad oficial "
        "es <b>shared secret en custom header</b> configurado via PATCH /settings. T0.10 implementa "
        "ese modelo. Como WHATSAPP_PROVIDER=meta hoy, el PR es preventivo &mdash; blinda codigo antes "
        "de cualquier cambio futuro de provider, sin riesgo de romper el deploy actual."
    ))

    # ── 1. Flujo actual ────────────────────────────────────────────────
    s.append(H1("1. Flujo actual cuando WHATSAPP_PROVIDER=whapi"))
    flujo = (
        "Whapi.cloud  -> POST https://<dona>/webhook   (con headers configurados en su panel)\n"
        "                          |\n"
        "               agent/main.py:2154  webhook_handler(request)\n"
        "                          |\n"
        "               agent/main.py:771  procesar_webhook(request)\n"
        "                          |\n"
        "               proveedor.parsear_webhook(request)\n"
        "                          |\n"
        "                          +-- WHATSAPP_PROVIDER=whapi -> ProveedorWhapi.parsear_webhook\n"
        "                          v\n"
        "               agent/providers/whapi.py:23  parsear_webhook\n"
        "                          |\n"
        "               body = await request.json()        <- !SIN VALIDAR FIRMA NI HEADER!\n"
        "                          |\n"
        "               procesa mensajes y los devuelve a brain.py / Claude\n"
    )
    s.append(CODE(flujo))
    s.append(P(
        "<b>Hoy no se ejecuta</b> porque WHATSAPP_PROVIDER=meta. Pero el endpoint /webhook sigue "
        "publico &mdash; si alguien cambia la variable a whapi, la linea anterior (request.json()) "
        "procesa cualquier payload sin filtro."
    ))

    # ── 2. Que soporta Whapi ───────────────────────────────────────────
    s.append(H1("2. Que soporta Whapi para validar webhooks"))
    s.append(P("Despues de revisar la documentacion oficial:"))
    soporte_rows = [
        ["Mecanismo", "Soportado por Whapi", "Detalle"],
        ["HMAC signature (estilo Stripe / Meta)", "<b>No</b>",
         "No hay firma criptografica del body. No hay header X-Whapi-Signature ni equivalente."],
        ["Custom headers", "<b>Si</b>",
         "Endpoint PATCH /settings con parametro 'headers'. Cualquier header con cualquier valor que el owner configure se incluye en cada webhook saliente desde Whapi."],
        ["IP allowlist", "No documentado",
         "Whapi no publica rangos oficiales."],
        ["Bearer token", "Disponible via custom header",
         "El owner puede agregar Authorization: Bearer <secret> como custom header."],
    ]
    s.append(small_table(para_rows(soporte_rows),
                         col_widths=[5.5*cm, 3.5*cm, 8.0*cm]))
    s.append(P(
        "<b>Modelo de seguridad oficial = shared secret en custom header.</b> El owner configura en "
        "el panel Whapi un header arbitrario (ej. X-Webhook-Token: &lt;random&gt;) y el backend valida "
        "que el header llegue con el valor esperado."
    ))
    s.append(P(
        "Esto es <b>distinto</b> a T0.2/T0.3/T0.4: no se firma el body, solo se valida un secreto "
        "compartido en un header. Replay attacks son posibles si el secret se filtra (no hay timestamp "
        "ni nonce signados)."
    ))

    # ── 3. Estado actual del codigo ────────────────────────────────────
    s.append(H1("3. Estado actual del codigo"))
    s.append(P("agent/providers/whapi.py:23-32:"))
    codigo_actual = (
        'async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:\n'
        '    body = await request.json()\n'
        '    logger.debug(f"Payload Whapi recibido: {body}")\n'
        '    # ... procesa directo ...\n'
    )
    s.append(CODE(codigo_actual))
    s.append(P(
        "<b>No hay validacion de firma, header ni token.</b> Cualquier POST a /webhook con un JSON "
        "tipo {'messages': [{'chat_id': 'X', 'type': 'text', 'text': {'body': 'Hola'}}]} seria "
        "procesado como mensaje real si WHATSAPP_PROVIDER=whapi."
    ))
    s.append(P("Adicionalmente:"))
    s.extend(bullets([
        "<b>No hay rate limiting</b> especifico del endpoint (el rate limit en _dentro_de_limite se aplica por telefono, despues de parsear).",
        "<b>No hay replay protection</b> (no se valida timestamp ni mensaje_id contra ventana temporal &mdash; solo deduplicacion por mensaje_id, que el atacante elige).",
    ]))

    # ── 4. Riesgo real ─────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("4. Riesgo real"))

    s.append(H2("4.1 Hoy (WHATSAPP_PROVIDER=meta)"))
    s.extend(bullets([
        "Provider Whapi <b>no se instancia</b>. parsear_webhook de Whapi nunca se ejecuta.",
        "El endpoint /webhook esta corriendo el parser Meta (con HMAC obligatorio desde T0.3).",
        "<b>Riesgo activo: cero.</b>",
    ]))

    s.append(H2("4.2 Si alguien cambiara WHATSAPP_PROVIDER=whapi"))
    s.extend(bullets([
        "Inmediatamente todo POST a /webhook se procesaria como Whapi.",
        "Atacante envia: POST /webhook con {'messages': [{'chat_id': '<telefono_victima>', 'type': 'text', 'text': {'body': 'Mensaje malicioso'}}]}",
        "Dona invoca a Claude con ese texto, ejecuta tools, gasta creditos del workspace de la victima, y responde por WhatsApp.",
        "Bypass del flujo legitimo: <b>inyeccion de mensajes falsos</b>, <b>gasto de creditos forjado</b>, posible <b>acceso a datos</b> del workspace si el texto induce comandos sensibles.",
    ]))

    s.append(H2("4.3 Variables legacy en Render"))
    s.extend(bullets([
        "<b>WHAPI_TOKEN</b> &mdash; sigue usandose en agent/providers/whapi.py:20, agent/main.py:314,814 y agent/transcriber.py:68. Si bien hoy WHATSAPP_PROVIDER=meta, el token se usa tambien para diagnostico admin (/diagnostico) y para transcribir audios entrantes (legacy de cuando Whapi era default). Mantenerla <b>si tiene sentido</b>, pero queda como codigo sin trafico.",
        "<b>WHAPI_API_URL</b> &mdash; <b>no se lee en ningun lugar del codigo</b> (verificado con grep). Es var dormida 100%. Puede <b>borrarse de Render</b> sin impacto. Las URLs de Whapi estan hardcodeadas a https://gate.whapi.cloud/...",
    ]))

    # ── 5. Variable propuesta ──────────────────────────────────────────
    s.append(H1("5. Variable propuesta para validar firma"))
    s.append(P(
        "Como Whapi no tiene HMAC, el modelo es shared-secret-in-header. Recomiendo:"
    ))
    var_rows = [
        ["Variable", "Funcion", "Valor sugerido"],
        ["WHAPI_WEBHOOK_TOKEN",
         "El secreto que Whapi inyectara como custom header en cada webhook entrante.",
         "string aleatorio largo (secrets.token_urlsafe(32))"],
        ["WHAPI_WEBHOOK_HEADER (opcional)",
         "Nombre del header donde Whapi envia el token. Default sugerido: X-Webhook-Token. Si lo dejamos default, no necesita ser configurable.",
         "default X-Webhook-Token"],
    ]
    s.append(small_table(para_rows(var_rows),
                         col_widths=[5.0*cm, 8.0*cm, 4.0*cm]))
    s.append(P(
        "El owner debe configurar en el panel de Whapi (via PATCH /settings) que el header "
        "X-Webhook-Token con valor WHAPI_WEBHOOK_TOKEN se envie en cada webhook. Eso conecta los dos lados."
    ))
    s.append(P(
        "<b>No necesitamos WHAPI_WEBHOOK_SECRET con sufijo _SECRET</b> porque no es secreto criptografico "
        "(no se usa para firmar HMAC). Es un shared token."
    ))

    # ── 6. Cambio minimo ───────────────────────────────────────────────
    s.append(H1("6. Cambio minimo recomendado"))

    s.append(H2("6.1 agent/providers/whapi.py"))
    s.append(P("Agregar al __init__ (mismo patron que T0.3 Meta):"))
    init_code = (
        'def __init__(self):\n'
        '    self.token = os.getenv("WHAPI_TOKEN")\n'
        '    self.url_envio = "https://gate.whapi.cloud/messages/text"\n'
        '    self.webhook_token = os.getenv("WHAPI_WEBHOOK_TOKEN", "").strip()\n'
        '    self.webhook_header = os.getenv("WHAPI_WEBHOOK_HEADER", "X-Webhook-Token").strip()\n'
        '\n'
        '    environment = os.getenv("ENVIRONMENT", "development").lower()\n'
        '    if environment == "production" and not self.webhook_token:\n'
        '        raise RuntimeError(\n'
        '            "[WHAPI] WHAPI_WEBHOOK_TOKEN no configurado en produccion — "\n'
        '            "los webhooks aceptarian payloads forjados, lo que permite a "\n'
        '            "un atacante inyectar mensajes WhatsApp falsos. Configura la "\n'
        '            "variable o cambia WHATSAPP_PROVIDER antes del deploy."\n'
        '        )\n'
    )
    s.append(CODE(init_code))

    s.append(P("Agregar metodo _verificar_firma (en realidad 'verificar header'):"))
    verify_code = (
        'def _verificar_firma(self, request: Request) -> bool:\n'
        '    """Valida que el request incluye el custom header con el valor esperado.\n'
        '    Whapi no firma HMAC; el modelo es shared secret en custom header.\n'
        '    """\n'
        '    import hmac\n'
        '    environment = os.getenv("ENVIRONMENT", "development").lower()\n'
        '    if not self.webhook_token:\n'
        '        if environment == "production":\n'
        '            logger.error("[WHAPI] WHAPI_WEBHOOK_TOKEN no configurado en produccion ...")\n'
        '            return False\n'
        '        logger.warning("[WHAPI] sin token, aceptando sin verificar (solo dev/test)")\n'
        '        return True\n'
        '    received = request.headers.get(self.webhook_header, "")\n'
        '    if not hmac.compare_digest(received, self.webhook_token):\n'
        '        logger.warning(f"[WHAPI] Header {self.webhook_header} ausente o no coincide")\n'
        '        return False\n'
        '    return True\n'
    )
    s.append(CODE(verify_code))

    s.append(P("Llamar al check al inicio de parsear_webhook:"))
    parse_code = (
        'async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:\n'
        '    if not self._verificar_firma(request):\n'
        '        return []  # Rechazo silencioso — no procesar payload\n'
        '    body = await request.json()\n'
        '    # ... resto sin cambios ...\n'
    )
    s.append(CODE(parse_code))

    s.append(H2("6.2 .env.example"))
    s.append(P("Reformular el bloque Whapi (sin valores reales):"))
    env_block = (
        "# == Whapi.cloud (si WHATSAPP_PROVIDER=whapi) ==\n"
        "WHAPI_TOKEN=\n"
        "#\n"
        "# WHAPI_WEBHOOK_TOKEN: OBLIGATORIA en produccion cuando WHATSAPP_PROVIDER=whapi.\n"
        "# Es un shared secret que Whapi enviara como custom header en cada webhook\n"
        "# entrante (Whapi no usa HMAC; usa custom headers via PATCH /settings).\n"
        "# El owner debe configurar en el panel de Whapi:\n"
        '#   "headers": {"X-Webhook-Token": "<el-mismo-valor-que-aqui>"}\n'
        "# Generar con:\n"
        '#   python -c "import secrets; print(secrets.token_urlsafe(32))"\n'
        "# WHAPI_WEBHOOK_TOKEN=\n"
        "# WHAPI_WEBHOOK_HEADER=X-Webhook-Token   # opcional, default X-Webhook-Token\n"
    )
    s.append(CODE(env_block))

    s.append(H2("6.3 Total del cambio"))
    s.extend(bullets([
        "agent/providers/whapi.py: +25-30 lineas (init check + _verificar_firma).",
        ".env.example: +10 lineas documentales.",
        "tests/test_providers.py: +5-6 tests nuevos.",
        "<b>PR pequeno, ~40 lineas netas.</b>",
    ]))

    # ── 7. Fail-fast en startup ────────────────────────────────────────
    s.append(H1("7. Conviene fail-fast en startup?"))
    s.append(P("<b>Si</b>, mismo patron que T0.3 Meta:"))
    s.extend(bullets([
        "El check vive en __init__ de ProveedorWhapi.",
        "Solo se ejecuta si obtener_proveedor() instancia Whapi (WHATSAPP_PROVIDER=whapi).",
        "Si esta en meta o twilio, el modulo Whapi ni se carga al startup, asi que el check no se dispara.",
        "<b>Hoy con WHATSAPP_PROVIDER=meta el check no se ejecuta</b>, asi que no afecta el deploy actual.",
    ]))
    s.append(P(
        "Esto es <b>clave</b>: T0.10 puede mergearse hoy sin riesgo de romper Render &mdash; porque el "
        "provider activo sigue siendo Meta. La proteccion queda armada para el dia que se cambie a Whapi."
    ))
    s.append(P(
        "<b>Defensa en profundidad</b> via _verificar_firma tambien se activa solo al primer webhook entrante "
        "con WHATSAPP_PROVIDER=whapi."
    ))

    # ── 8. Tests ───────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("8. Tests a agregar"))
    s.append(P(
        "tests/test_providers.py hoy tiene tests de Meta pero <b>ninguno de Whapi para webhook validation</b>. "
        "Hay que agregar una clase nueva."
    ))
    tests_code = (
        'class TestWhapiWebhookValidation:\n'
        '    """T0.10: validacion de header personalizado en webhooks Whapi."""\n'
        '\n'
        '    def test_dev_sin_token_acepta_payload(self, monkeypatch)\n'
        '    def test_production_sin_token_levanta_runtime_error(self, monkeypatch)\n'
        '    def test_production_con_token_no_levanta(self, monkeypatch)\n'
        '    def test_production_token_valido_acepta(self, monkeypatch)\n'
        '    def test_production_token_invalido_rechaza(self, monkeypatch)\n'
        '    def test_production_sin_header_rechaza(self, monkeypatch)\n'
    )
    s.append(CODE(tests_code))
    s.append(P(
        "<b>Total: 6 tests nuevos</b> + 1 fixture _make_whapi_text_msg. Cero tests existentes a actualizar "
        "(no habia tests de webhook Whapi)."
    ))

    # ── 9. WHAPI_TOKEN y WHAPI_API_URL ─────────────────────────────────
    s.append(H1("9. Limpiar o mantener WHAPI_TOKEN y WHAPI_API_URL en Render?"))
    legacy_rows = [
        ["Variable", "Estado actual", "Recomendacion"],
        ["WHAPI_TOKEN",
         "Se usa en agent/providers/whapi.py:20, agent/main.py:314,814, agent/transcriber.py:68. Hoy con provider=meta el codigo del provider no se ejecuta, pero agent/transcriber.py llama https://gate.whapi.cloud/media/{audio_id} con WHAPI_TOKEN para descargar audios &mdash; verificar si eso sigue corriendo o quedo vestigial al pasar a Meta.",
         "<b>Mantener</b> hasta confirmar que el transcriber usa Meta directo. T0.10 no la toca."],
        ["WHAPI_API_URL",
         "<b>No se lee en ningun archivo del codigo.</b> Unicamente aparece como mencion en un script de docs. URLs Whapi estan hardcodeadas.",
         "<b>Borrar de Render con seguridad.</b> Operacion trivial, sin impacto. (Recomendado para una limpieza separada de housekeeping de env vars.)"],
    ]
    s.append(small_table(para_rows(legacy_rows),
                         col_widths=[3.5*cm, 8.5*cm, 5.0*cm]))
    s.append(P(
        "Importante: este PR T0.10 <b>no toca WHAPI_TOKEN ni WHAPI_API_URL</b>. Solo agrega "
        "WHAPI_WEBHOOK_TOKEN. La limpieza de WHAPI_API_URL es un housekeeping de env vars aparte "
        "(5 segundos en el Render dashboard, sin codigo)."
    ))

    # ── 10. Archivos ───────────────────────────────────────────────────
    s.append(H1("10. Archivos que tocaria"))
    archivos_rows = [
        ["Archivo", "Tipo de cambio"],
        ["agent/providers/whapi.py",
         "Agregar check fail-fast en __init__ + agregar metodo _verificar_firma + invocarlo al inicio de parsear_webhook."],
        [".env.example",
         "Reformular bloque Whapi para documentar WHAPI_WEBHOOK_TOKEN (obligatorio en produccion si provider=whapi) y WHAPI_WEBHOOK_HEADER (opcional)."],
        ["tests/test_providers.py",
         "Agregar TestWhapiWebhookValidation con 6 tests."],
    ]
    s.append(small_table(para_rows(archivos_rows),
                         col_widths=[4.5*cm, 12.5*cm]))
    s.append(P("<b>Lo que NO toco:</b>"))
    s.extend(bullets([
        "agent/main.py &mdash; sin cambios. Igual que en T0.3, el check vive en __init__ del provider.",
        "agent/providers/whapi.py:enviar_* &mdash; los metodos de envio no requieren cambios.",
        "WHAPI_TOKEN (env var) &mdash; sin tocar.",
        "Comportamiento de parser de mensajes &mdash; sin cambios.",
        "Endpoint /webhook (handler en main) &mdash; sin cambios.",
    ]))

    # ── 11. Riesgos ────────────────────────────────────────────────────
    s.append(H1("11. Riesgos de compatibilidad y deploy"))
    riesgos_rows = [
        ["Riesgo", "Probabilidad", "Mitigacion"],
        ["Render aborta deploy si hoy provider=whapi y falta WHAPI_WEBHOOK_TOKEN",
         "<b>Cero hoy</b> (provider=meta)",
         "El check vive en init del provider Whapi, que no se instancia con provider=meta"],
        ["Webhook real de Whapi sin custom header configurado en su panel",
         "Solo si en algun momento se cambia a whapi sin coordinar Whapi panel",
         "Documentar en .env.example los pasos de configuracion"],
        ["Tests existentes rompen", "<b>Cero</b>",
         "No hay tests de webhook Whapi previos; solo agregamos."],
        ["Replay attacks (Whapi no firma timestamp)",
         "Igual que hoy",
         "Fuera del alcance de T0.10. Mitigable con dedup por mensaje_id (ya hay) y/o agregar TTL de tokens (separado)."],
    ]
    s.append(small_table(para_rows(riesgos_rows),
                         col_widths=[6.0*cm, 4.0*cm, 7.0*cm]))

    s.append(P("<b>Compatibilidad con Whapi:</b>"))
    s.extend(bullets([
        "El cambio es 100% compatible. Solo agrega validacion; no altera URL ni formato de payload.",
        "Si Whapi cambia su API en el futuro (improbable a corto plazo), no afecta la firma.",
    ]))

    # ── 12. Checklist ──────────────────────────────────────────────────
    s.append(H1("12. Checklist antes de mergear"))

    s.append(H2("12.1 Pre-PR"))
    s.extend(checklist([
        "Confirmar que WHATSAPP_PROVIDER=meta sigue en Render (no se planea cambio inmediato).",
        "Decidir si setear WHAPI_WEBHOOK_TOKEN ahora en Render preventivamente, o solo cuando se planee rotar provider.",
        "Decidir nombre de branch: sugiero <b>pr/whapi-webhook-token-obligatorio</b>.",
    ]))

    s.append(H2("12.2 Durante el PR"))
    s.extend(checklist([
        "Implementar cambio en agent/providers/whapi.py.",
        "Reformular .env.example.",
        "Agregar TestWhapiWebhookValidation (6 tests).",
        "<i>pytest -q</i> localmente &mdash; 100% verde.",
    ]))

    s.append(H2("12.3 Pre-push"))
    s.extend(checklist([
        "Diff toca solo los 3 archivos previstos.",
        "Ningun secret real en codigo, comentarios ni tests.",
        "Commit: <i>fix(seguridad): WHAPI_WEBHOOK_TOKEN obligatorio en produccion (T0.10)</i>.",
    ]))

    s.append(H2("12.4 Post-push, pre-merge"))
    s.extend(checklist([
        "Push a origin/pr/whapi-webhook-token-obligatorio.",
        "Confirmar que con WHATSAPP_PROVIDER=meta, el deploy de Render no se ve afectado.",
    ]))

    s.append(H2("12.5 Post-merge"))
    s.extend(checklist([
        "Render deploy debe completar sin errores. Provider Meta sigue funcionando.",
        "<b>Si en algun momento futuro</b> se decide rotar a WHATSAPP_PROVIDER=whapi: setear WHAPI_WEBHOOK_TOKEN en Render, configurar el header en panel Whapi via PATCH /settings, verificar con un mensaje de prueba.",
    ]))

    # ── 13. Resumen ejecutivo ──────────────────────────────────────────
    s.append(H1("13. Resumen ejecutivo"))
    resumen_rows = [
        ["Aspecto", "Detalle"],
        ["Riesgo que cierra",
         "P0 latente &mdash; inyeccion de mensajes WhatsApp falsos via /webhook cuando provider sea Whapi sin token."],
        ["Hoy activo",
         "<b>No</b> (provider=meta). PR es preventivo, blinda codigo antes de futuro cambio de provider."],
        ["Patron",
         "Identico a T0.3 Meta: check en __init__ del provider + defensa en profundidad en _verificar_firma."],
        ["Modelo de seguridad",
         "<b>Custom header con shared secret</b> (Whapi no usa HMAC). Distinto a T0.2/T0.3/T0.4."],
        ["Variable nueva",
         "WHAPI_WEBHOOK_TOKEN + opcional WHAPI_WEBHOOK_HEADER (default X-Webhook-Token)."],
        ["Archivos", "3 (1 codigo, 1 docs, 1 tests)."],
        ["Tamano", "~40 lineas netas."],
        ["Tests", "0 actualizados + 6 nuevos."],
        ["Riesgo de deploy",
         "<b>Cero hoy</b> &mdash; check no se ejecuta con provider=meta."],
        ["Variables legacy",
         "WHAPI_API_URL puede borrarse de Render (sin uso en codigo). WHAPI_TOKEN mantener (sigue usandose en transcriber)."],
        ["Configuracion Whapi panel",
         "Fuera del PR &mdash; solo se hace cuando se rote provider a whapi."],
    ]
    s.append(small_table(para_rows(resumen_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(Spacer(1, 14))
    s.append(P("<b>Estado:</b> no implementado todavia. Esperando OK del owner con confirmacion de:"))
    s.extend(bullets([
        "Nombre del header default (X-Webhook-Token) o si preferis otro.",
        "Si autorizas documentar WHAPI_WEBHOOK_TOKEN aunque hoy no este en Render.",
        "Si queres que en este PR tambien agregue una nota en .env.example sobre WHAPI_API_URL siendo legacy/borrable.",
    ]))

    # ── Sources ────────────────────────────────────────────────────────
    s.append(H1("Sources"))
    s.extend(bullets([
        "Whapi.cloud API Documentation. https://whapi.cloud/docs",
        "Whapi-Cloud/whatsapp-api-docs &mdash; GitHub. https://github.com/Whapi-Cloud/whatsapp-api-docs",
        "Customizable Webhook Headers &mdash; Whapi Help Desk. https://support.whapi.cloud/help-desk/account/customizable-webhook-headers",
        "Set the webhook link to the channel &mdash; Whapi Help Desk. https://support.whapi.cloud/help-desk/receiving/webhooks/set-the-webhook-link-to-the-channel",
        "Webhooks &mdash; Whapi Help Desk. https://support.whapi.cloud/help-desk/receiving/webhooks",
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
        title="Dona — Diagnostico T0.10 Whapi webhook",
        author="Diagnostico generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T0.10 Whapi webhook signature validation · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
