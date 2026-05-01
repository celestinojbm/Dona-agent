"""
Genera Diagnostico_T03_Meta_Webhook_2026-05-01.pdf con el diagnostico
de solo lectura del bloque P0 Meta webhook signature obligatorio (T0.3).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Diagnostico_T03_Meta_Webhook_2026-05-01.pdf"

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
    s.append(Paragraph("T0.3 — Meta webhook signature obligatorio", styles["TitleBig"]))
    s.append(Paragraph(
        "Diagnostico de solo lectura &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin cambios, sin commits, sin push.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Hallazgo separado durante este diagnostico:</b> agent/providers/whapi.py no "
        "implementa validacion de firma. Si WHATSAPP_PROVIDER=whapi en produccion (default del repo), "
        "<b>existe un P0 abierto independiente de T0.3</b> que se anota como T0.10 nueva al final."
    ))

    # ── 1. Flujo ────────────────────────────────────────────────────────
    s.append(H1("1. Flujo actual del webhook de Meta/WhatsApp"))
    flujo = (
        "WhatsApp/Meta servers -> POST https://<dona>/webhook\n"
        "                          |\n"
        "               agent/main.py:2154  webhook_handler(request)\n"
        "                          |\n"
        "               agent/main.py:771  procesar_webhook(request)\n"
        "                          |\n"
        "               proveedor.parsear_webhook(request)\n"
        "                          |\n"
        "                          +-- WHATSAPP_PROVIDER=whapi  -> ProveedorWhapi.parsear_webhook\n"
        "                          +-- WHATSAPP_PROVIDER=meta   -> ProveedorMeta.parsear_webhook\n"
        "                          +-- WHATSAPP_PROVIDER=twilio -> ProveedorTwilio (no presente)\n"
        "                          |\n"
        "               (Solo si Meta) ProveedorMeta._verificar_firma(body, X-Hub-Signature-256)\n"
        "                          |\n"
        "                          +-- firma valida   -> parsea con Pydantic, retorna mensajes\n"
        "                          +-- firma invalida -> retorna []\n"
        "                          +-- sin app_secret -> return True (acepta sin verificar)\n"
        "                          |\n"
        "                Mensajes entrantes -> procesados por brain.py / Claude\n"
    )
    s.append(CODE(flujo))
    s.append(P(
        "<b>Verificacion adicional ya presente</b> (agent/providers/meta.py:191-207): replay protection "
        "con ventana de 600 s sobre timestamp del mensaje. <b>Pero vive despues de la firma</b>: si un "
        "atacante forja un payload sin firma, la replay protection no lo salva."
    ))

    # ── 2. Endpoint receiver ────────────────────────────────────────────
    s.append(H1("2. Endpoint receiver"))
    s.append(P("agent/main.py:"))
    ep_rows = [
        ["Endpoint", "Linea", "Funcion"],
        ["GET /webhook", "341",
         "webhook_verificacion -> proveedor.validar_webhook (challenge Meta para subscription)"],
        ["POST /webhook", "2154",
         "webhook_handler -> procesar_webhook -> proveedor.parsear_webhook"],
        ["POST /webhook/messages", "2160",
         "mismo handler que /webhook (alias para Whapi cuando configura /messages suffix)"],
    ]
    s.append(small_table(para_rows(ep_rows),
                         col_widths=[4.5*cm, 1.3*cm, 11.2*cm]))
    s.append(P(
        "<b>El endpoint POST /webhook es unico.</b> Que parser corre depende de la env var "
        "WHATSAPP_PROVIDER. No hay rutas separadas por provider."
    ))

    # ── 3. Validacion actual ────────────────────────────────────────────
    s.append(H1("3. Como se valida hoy la firma de Meta"))
    s.append(P("agent/providers/meta.py:125-150:"))
    codigo_actual = (
        'def _verificar_firma(self, body_bytes: bytes, signature_header: str) -> bool:\n'
        '    if not self.app_secret:\n'
        '        logger.warning("[META] META_APP_SECRET no configurado — webhook sin verificacion HMAC...")\n'
        '        return True  # Permitir sin firma si no se configuro (backwards compatible)\n'
        '\n'
        '    if not signature_header or not signature_header.startswith("sha256="):\n'
        '        logger.warning("[META] Webhook recibido sin firma X-Hub-Signature-256 valida — rechazado")\n'
        '        return False\n'
        '\n'
        '    expected = hmac.new(self.app_secret.encode(), body_bytes, hashlib.sha256).hexdigest()\n'
        '    if not hmac.compare_digest(signature_header[7:], expected):\n'
        '        logger.warning("[META] Firma HMAC del webhook NO coincide — payload rechazado")\n'
        '        return False\n'
        '\n'
        '    return True\n'
    )
    s.append(CODE(codigo_actual))
    s.append(P("<b>Buenas practicas que ya hace bien:</b>"))
    s.extend(bullets([
        "hmac.compare_digest (timing-safe).",
        "Validacion del prefijo 'sha256='.",
        "HMAC-SHA256 con app_secret como key y body crudo como mensaje.",
    ]))
    s.append(P(
        "<b>Problema:</b> la primera condicion (if not self.app_secret: return True) es el "
        "<b>fallback inseguro</b> — el patron explicito que cierra T0.3."
    ))

    # ── 4. Que pasa si META_APP_SECRET no esta? ─────────────────────────
    s.append(PageBreak())
    s.append(H1("4. Que pasa si META_APP_SECRET no esta configurado?"))
    fallback_rows = [
        ["Camino", "Comportamiento"],
        ["Provider activo es Meta + META_APP_SECRET vacio",
         "<b>Acepta cualquier payload</b> sin firma. Solo emite warning. Procesa los mensajes como reales."],
        ["Provider activo es Meta + META_APP_SECRET seteado + firma invalida",
         "Rechaza con False -> parsear_webhook retorna [] -> endpoint responde 200 OK sin procesar."],
        ["Provider activo es Meta + sin header X-Hub-Signature-256",
         "Rechaza con False (mismo path)."],
        ["Provider activo es Whapi",
         "_verificar_firma ni se invoca (Whapi no la implementa &mdash; ver §10.3)."],
    ]
    s.append(small_table(para_rows(fallback_rows),
                         col_widths=[7.0*cm, 10.0*cm]))
    s.append(P(
        "enhanced/diagnostics.py:135-144 tambien lee META_APP_SECRET pero solo para reportar diagnostico al admin, "
        "no para validar."
    ))
    s.append(P("<b>Tests existentes (tests/test_providers.py:237-285) codifican el comportamiento permisivo:</b>"))
    s.extend(bullets([
        "test_sin_secret_permite_todo (linea 238) &mdash; asume y verifica el path inseguro.",
        "test_firma_valida / test_firma_invalida / test_sin_header_firma cubren el camino seguro.",
        "test_webhook_rechaza_firma_invalida / test_webhook_acepta_firma_valida E2E.",
    ]))
    s.append(P(
        "Hay que <b>actualizar</b> test_sin_secret_permite_todo para que solo aplique en dev/test. "
        "Los demas siguen igual."
    ))

    # ── 5. Endpoint publico permite mensajes falsos? ────────────────────
    s.append(H1("5. El endpoint publico permite mensajes falsos o payloads no firmados?"))
    s.append(P("Depende del provider activo en produccion."))
    riesgo_rows = [
        ["Provider activo", "Endpoint publico", "Acepta payloads no firmados?"],
        ["Meta y META_APP_SECRET no seteado", "si",
         "<b>SI &mdash; riesgo P0 abierto</b>"],
        ["Meta y META_APP_SECRET seteado", "si", "No, rechaza con 200+[]"],
        ["Whapi (default actual)", "si",
         "<b>SI &mdash; riesgo P0 separado, ver §10.3</b>"],
    ]
    s.append(small_table(para_rows(riesgo_rows),
                         col_widths=[6.0*cm, 4.0*cm, 7.0*cm]))
    s.append(P(
        "<b>Necesito tu confirmacion operativa</b>: cual es el valor de WHATSAPP_PROVIDER en Render? "
        "Eso decide si T0.3 cierra un riesgo activo (Meta) o solo blinda codigo preparado para el futuro "
        "(igual que paso con Stripe T0.2). El repo apunta a whapi como default, pero el deploy puede tener "
        "otra configuracion."
    ))

    # ── 6. Variables en Render ──────────────────────────────────────────
    s.append(H1("6. Variables que deben estar en Render antes del merge"))
    var_rows = [
        ["Variable", "Origen", "Formato", "Cuando es obligatoria"],
        ["META_APP_SECRET",
         "Meta for Developers -> tu App -> 'Settings' -> 'Basic' -> 'App Secret' -> 'Show'",
         "string hex de 32 chars (sin prefijo)",
         "Solo si WHATSAPP_PROVIDER=meta en Render"],
        ["WHATSAPP_PROVIDER",
         "env var existente",
         "whapi | meta | twilio",
         "siempre"],
    ]
    s.append(small_table(para_rows(var_rows),
                         col_widths=[3.5*cm, 5.5*cm, 3.5*cm, 4.5*cm]))
    s.append(P(
        "<b>No solicito ver el valor.</b> Solo confirmacion de que esta seteado en Render <b>si</b> "
        "el provider activo es Meta."
    ))
    s.append(P(
        "Si el provider activo es Whapi, el check de Meta solo se ejecutaria si alguien cambiara "
        "WHATSAPP_PROVIDER=meta sin setear META_APP_SECRET. T0.3 protege ese caso futuro y cierra la "
        "superficie de ataque del codigo (similar a T0.2 backend)."
    ))

    # ── 7. Cambio minimo ────────────────────────────────────────────────
    s.append(H1("7. Cambio minimo recomendado"))
    s.append(P("<b>Patron distinto al de T0.2.</b> En Stripe el check se hizo al import del modulo. En Meta no es ideal porque:"))
    s.extend(bullets([
        "El app_secret se lee en ProveedorMeta.__init__(), no a nivel modulo.",
        "agent/providers/__init__.py:obtener_proveedor() solo importa Meta si WHATSAPP_PROVIDER=meta. Si esta en Whapi, Meta no se carga al startup.",
        "Hacer el check al import del modulo bloquearia tests y dev runs aunque se elija otro provider.",
    ]))

    s.append(H3("Recomendacion: hacer el check en ProveedorMeta.__init__():"))
    init_propuesto = (
        'def __init__(self):\n'
        '    self.access_token = os.getenv("META_ACCESS_TOKEN", "")\n'
        '    self.phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "")\n'
        '    self.verify_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "dona_webhook_secret")\n'
        '    self.app_secret = os.getenv("META_APP_SECRET", "").strip()\n'
        '    self.api_version = os.getenv("META_API_VERSION", "v21.0")\n'
        '    # ...\n'
        '    environment = os.getenv("ENVIRONMENT", "development").lower()\n'
        '    if environment == "production" and not self.app_secret:\n'
        '        raise RuntimeError(\n'
        '            "[META] META_APP_SECRET no configurado en produccion — "\n'
        '            "webhooks aceptarian payloads forjados, lo que permite a un "\n'
        '            "atacante inyectar mensajes WhatsApp falsos. Configura la "\n'
        '            "variable o cambia WHATSAPP_PROVIDER antes del deploy."\n'
        '        )\n'
    )
    s.append(CODE(init_propuesto))

    s.append(H3("Y en _verificar_firma — defensa en profundidad:"))
    verifica_propuesto = (
        'def _verificar_firma(self, body_bytes: bytes, signature_header: str) -> bool:\n'
        '    environment = os.getenv("ENVIRONMENT", "development").lower()\n'
        '    if not self.app_secret:\n'
        '        if environment == "production":\n'
        '            logger.error(\n'
        '                "[META] META_APP_SECRET no configurado en produccion — "\n'
        '                "rechazando webhook (defensa en profundidad)."\n'
        '            )\n'
        '            return False\n'
        '        logger.warning(\n'
        '            "[META] META_APP_SECRET no configurado — aceptando sin verificar "\n'
        '            "(INSEGURO, solo dev/test)."\n'
        '        )\n'
        '        return True\n'
        '    # ... resto del codigo actual sin cambios\n'
    )
    s.append(CODE(verifica_propuesto))
    s.append(P("Esto da <b>dos capas</b>:"))
    s.extend(bullets([
        "__init__ aborta el deploy si Meta es el provider activo en prod sin secret.",
        "_verificar_firma rechaza igual si por algun path el provider se instancia sin secret (defensa en profundidad).",
    ]))

    s.append(H3("Total de cambio"))
    s.extend(bullets([
        "agent/providers/meta.py: +12 lineas en __init__ + ~8 lineas modificadas en _verificar_firma.",
        ".env.example: +1 bloque documental para META_APP_SECRET.",
        "tests/test_providers.py: actualizar test_sin_secret_permite_todo y agregar TestVerificacionHMACProduction con 4 nuevos.",
        "<b>PR pequeno, ~25-35 lineas netas.</b> Mas chico que T0.2.",
    ]))

    # ── 8. Archivos que tocaria ─────────────────────────────────────────
    s.append(H1("8. Archivos que tocaria"))
    archivos_rows = [
        ["Archivo", "Tipo de cambio"],
        ["agent/providers/meta.py",
         "Agregar check en ProveedorMeta.__init__ + agregar branch production en _verificar_firma."],
        [".env.example",
         "Documentar META_APP_SECRET (hoy aparece comentado en el bloque Meta general; explicitar que es obligatorio en produccion)."],
        ["tests/test_providers.py",
         "Renombrar/actualizar test_sin_secret_permite_todo -> version dev. Agregar TestVerificacionHMACProduction con casos production."],
    ]
    s.append(small_table(para_rows(archivos_rows),
                         col_widths=[4.5*cm, 12.5*cm]))
    s.append(P("<b>Lo que NO toco:</b>"))
    s.extend(bullets([
        "agent/main.py &mdash; no requiere import top-level. El check vive en el __init__ del provider, que se ejecuta cuando obtener_proveedor() se llama en main.py:54.",
        "agent/providers/whapi.py &mdash; fuera del alcance de T0.3 (ver §10.3 sobre el riesgo separado).",
        "agent/providers/__init__.py (factory) &mdash; sin cambios.",
        "Endpoint webhook_verificacion (GET) &mdash; usa verify_token, no app_secret. No es parte de T0.3.",
    ]))

    # ── 9. Tests ────────────────────────────────────────────────────────
    s.append(H1("9. Tests a correr"))

    s.append(H2("9.1 Tests existentes a actualizar"))
    s.append(P("tests/test_providers.py clase TestVerificacionHMAC (lineas 237-285):"))
    s.extend(bullets([
        "test_sin_secret_permite_todo (linea 238): renombrar a test_sin_secret_en_dev_permite y setear monkeypatch.setenv('ENVIRONMENT', 'development') explicito. Mantener el assert.",
        "test_firma_valida, test_firma_invalida, test_sin_header_firma: sin cambios.",
        "test_webhook_rechaza_firma_invalida, test_webhook_acepta_firma_valida: sin cambios.",
    ]))

    s.append(H2("9.2 Tests nuevos a agregar"))
    nuevos = (
        'class TestVerificacionHMACProduction:\n'
        '    def test_production_sin_secret_levanta_runtime_error_en_init(self, monkeypatch):\n'
        '        monkeypatch.setenv("ENVIRONMENT", "production")\n'
        '        monkeypatch.delenv("META_APP_SECRET", raising=False)\n'
        '        with pytest.raises(RuntimeError, match="META_APP_SECRET"):\n'
        '            ProveedorMeta()\n'
        '\n'
        '    def test_production_con_secret_no_levanta_en_init(self, monkeypatch):\n'
        '        monkeypatch.setenv("ENVIRONMENT", "production")\n'
        '        monkeypatch.setenv("META_APP_SECRET", "test_secret_dummy")\n'
        '        ProveedorMeta()  # No debe levantar.\n'
        '\n'
        '    def test_production_runtime_sin_secret_rechaza_firma(self, monkeypatch):\n'
        '        # Defensa en profundidad: aunque el __init__ se haya saltado, runtime rechaza.\n'
        '        proveedor = ProveedorMeta()\n'
        '        proveedor.app_secret = ""\n'
        '        monkeypatch.setenv("ENVIRONMENT", "production")\n'
        '        assert proveedor._verificar_firma(b"body", "sha256=anything") is False\n'
        '\n'
        '    def test_dev_sin_secret_permite_todo(self, monkeypatch):\n'
        '        monkeypatch.setenv("ENVIRONMENT", "development")\n'
        '        proveedor = ProveedorMeta()\n'
        '        proveedor.app_secret = ""\n'
        '        assert proveedor._verificar_firma(b"body", "") is True\n'
    )
    s.append(CODE(nuevos))
    s.append(P("Total: <b>1 actualizado + 4 nuevos</b>."))

    s.append(H2("9.3 Suite completa"))
    s.append(P(
        "<i>pytest -q</i>. Estimado: 449 actuales + 4 nuevos = <b>~453 tests</b>, ~35 s."
    ))

    # ── 10. Riesgos ─────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("10. Riesgos de compatibilidad y deploy"))

    s.append(H2("10.1 Riesgos del PR"))
    riesgos_pr_rows = [
        ["Riesgo", "Probabilidad", "Mitigacion"],
        ["WHATSAPP_PROVIDER=meta en Render sin META_APP_SECRET -> deploy aborta",
         "Solo si meta activo",
         "Confirmar antes del merge"],
        ["WHATSAPP_PROVIDER=whapi en Render -> Meta no se instancia -> check no ejecuta -> deploy ok",
         "Probable (default)",
         "Sin accion; T0.3 igual blinda el codigo"],
        ["META_APP_SECRET mal configurado (espacios, caracteres invisibles)",
         "Baja",
         ".strip() ya aplicado en el codigo propuesto"],
        ["Tests existentes rompen",
         "1 test cambia de contrato",
         "Plan: actualizar (§9.1)"],
        ["Provider Meta funcional rechaza webhook real por mismatch de secret",
         "Solo si secret en Render no matchea con App Secret en Meta Dashboard",
         "Verificar antes"],
    ]
    s.append(small_table(para_rows(riesgos_pr_rows),
                         col_widths=[6.0*cm, 4.5*cm, 6.5*cm]))

    s.append(H2("10.2 Compatibilidad con WhatsApp/Meta"))
    s.extend(bullets([
        "X-Hub-Signature-256 es estandar Meta &mdash; sin cambios en como Meta firma.",
        "Replay protection (timestamps) sigue activa &mdash; sin cambios.",
        "Validacion GET de subscripcion (hub.challenge) sigue activa &mdash; sin cambios.",
        "META_WEBHOOK_VERIFY_TOKEN (otro secret distinto) &mdash; fuera de T0.3.",
    ]))
    s.append(P(
        "<b>Rollback</b>: si tras el merge un webhook real es rechazado por mismatch, revertir el commit "
        "en Render. El comportamiento previo (acepta sin firma) vuelve y los webhooks legitimos pasan."
    ))

    s.append(H2("10.3 Riesgo separado P0 — Whapi sin validacion de firma"))
    s.append(P(
        "<b>Hallazgo nuevo durante este diagnostico:</b> agent/providers/whapi.py <b>no implementa "
        "validacion de firma</b>. Whapi si soporta firma de webhooks (HMAC-SHA256 con secret configurado "
        "en panel Whapi), pero el codigo del repo simplemente hace request.json() y procesa el body crudo."
    ))
    s.append(P(
        "<b>Implicacion:</b> si WHATSAPP_PROVIDER=whapi en produccion (default), <b>cualquiera que "
        "conozca la URL /webhook puede enviar payloads forjados</b> y Dona los procesara como mensajes "
        "legitimos. Esto es un <b>P0 abierto independiente</b> que el plan v2.1 no listaba como tal."
    ))
    s.append(P(
        "<b>Esto NO es alcance de T0.3.</b> Es un <b>T0.10 nuevo</b> que deberia tomarse despues de T0.3 "
        "como Phase 0 extendida. Lo senalo aqui para que no quede oculto."
    ))

    # ── 11. Checklist ───────────────────────────────────────────────────
    s.append(H1("11. Checklist antes de mergear"))

    s.append(H2("11.1 Pre-PR (antes de empezar)"))
    s.extend(checklist([
        "Confirmar el valor actual de WHATSAPP_PROVIDER en Render. Si es meta, tambien confirmar META_APP_SECRET.",
        "Si WHATSAPP_PROVIDER=meta: confirmar que el secret en Render coincide con el 'App Secret' de Meta for Developers (mismo string hex 32 chars).",
        "Decidir nombre de branch: sugiero <b>pr/meta-webhook-firma-obligatoria</b>.",
        "Decidir si T0.10 (whapi sin firma) entra al backlog Phase 0 explicitamente.",
    ]))

    s.append(H2("11.2 Durante el PR (local)"))
    s.extend(checklist([
        "Implementar cambio en agent/providers/meta.py:__init__ y _verificar_firma.",
        "Documentar META_APP_SECRET en .env.example.",
        "Actualizar/extender tests en tests/test_providers.py.",
        "Correr <i>pytest -q</i> localmente &mdash; 100% verde.",
    ]))

    s.append(H2("11.3 Pre-push"))
    s.extend(checklist([
        "Verificar que el diff toca solo los 3 archivos previstos.",
        "Verificar que no se filtro el secret real en codigo, comentarios ni tests.",
        "Commit: <i>fix(seguridad): META_APP_SECRET obligatorio en produccion (T0.3)</i>.",
    ]))

    s.append(H2("11.4 Post-push, pre-merge"))
    s.extend(checklist([
        "Push a origin/pr/meta-webhook-firma-obligatoria.",
        "Abrir PR contra main en GitHub.",
        "<b>NO mergear</b> hasta confirmar la matriz de env vars.",
    ]))

    s.append(H2("11.5 Post-merge"))
    s.extend(checklist([
        "Render deploy debe iniciar y completar segun el provider activo:",
    ]))
    s.extend([
        Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&bull; Si WHATSAPP_PROVIDER=whapi: deploy normal (Meta ni se instancia).", styles["BulletDona"]),
        Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&bull; Si WHATSAPP_PROVIDER=meta con secret: deploy normal.", styles["BulletDona"]),
        Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&bull; Si WHATSAPP_PROVIDER=meta sin secret: aborta con RuntimeError [META]. Revertir.", styles["BulletDona"]),
    ])
    s.extend(checklist([
        "Si WHATSAPP_PROVIDER=meta activo: enviar un mensaje de prueba a Dona y verificar que llega. Verificar logs Render por '[META] Firma HMAC del webhook NO coincide'.",
        "Si WHATSAPP_PROVIDER=whapi activo: nada operacional cambia. T0.10 sigue abierto.",
    ]))

    # ── 12. Resumen ejecutivo ───────────────────────────────────────────
    s.append(H1("12. Resumen ejecutivo"))
    resumen_rows = [
        ["Aspecto", "Detalle"],
        ["Riesgo que cierra",
         "P0 &mdash; inyeccion de mensajes WhatsApp falsos via /webhook cuando provider es Meta sin app_secret"],
        ["Patron",
         "Check en ProveedorMeta.__init__ + defensa en profundidad en _verificar_firma. <b>Distinto al patron de Stripe</b> (no es check al import del modulo)."],
        ["Archivos", "3 (1 codigo, 1 docs, 1 tests)"],
        ["Tamano", "~25-35 lineas netas"],
        ["Tests", "1 actualizado + 4 nuevos"],
        ["Env vars",
         "META_APP_SECRET obligatorio en Render solo si WHATSAPP_PROVIDER=meta"],
        ["Compatibilidad",
         "Path permisivo se mantiene en development|test. Tests actualizados, no rotos."],
        ["Riesgo de deploy",
         "Bajo si la matriz WHATSAPP_PROVIDER <-> META_APP_SECRET esta consistente"],
        ["Reversible", "Si, redeploy del commit anterior"],
        ["Hallazgo separado",
         "<b>T0.10 nuevo</b>: whapi.py no valida firma de webhook. P0 abierto independiente."],
    ]
    s.append(small_table(para_rows(resumen_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(Spacer(1, 14))
    s.append(P(
        "<b>Estado:</b> no implementado todavia. Esperando OK del owner con confirmacion de:"
    ))
    s.extend(bullets([
        "Valor actual de WHATSAPP_PROVIDER en Render.",
        "Si META_APP_SECRET ya esta seteado en Render (en caso de que el provider sea Meta).",
        "Si abro T0.10 (whapi sin firma) como tarea separada en el backlog para tratar despues.",
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
        title="Dona — Diagnostico T0.3 Meta webhook",
        author="Diagnostico generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T0.3 Meta webhook signature obligatorio · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
