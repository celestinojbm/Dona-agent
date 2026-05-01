"""
Genera Diagnostico_T04_Inbound_Webhook_2026-05-01.pdf con el diagnostico
de solo lectura del bloque P0 INBOUND_WEBHOOK_SECRET sin fallback (T0.4).

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

OUTPUT = r"C:\Users\celes\Dona-agent\Diagnostico_T04_Inbound_Webhook_2026-05-01.pdf"

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
    s.append(Paragraph("T0.4 — INBOUND_WEBHOOK_SECRET sin fallback", styles["TitleBig"]))
    s.append(Paragraph(
        "Diagnostico de solo lectura &nbsp;·&nbsp; Fecha: 2026-05-01 &nbsp;·&nbsp; "
        "Modo: solo lectura. &nbsp;·&nbsp; Sin cambios, sin commits, sin push.",
        styles["MetaTop"],
    ))

    s.append(BANNER(
        "<b>Diferencia clave con T0.2 y T0.3:</b> hay tokens emitidos vivos en servicios externos "
        "(Zapier/Make/n8n). Antes de implementar T0.4, hay que decidir el plan de rotacion "
        "(seccion 12) segun el escenario actual de Render. <b>Necesito confirmacion del owner</b> "
        "sobre si INBOUND_WEBHOOK_SECRET ya esta seteado y si hay tokens vivos."
    ))

    # ── 1. Donde se usa ────────────────────────────────────────────────
    s.append(H1("1. Donde se usa INBOUND_WEBHOOK_SECRET"))
    s.append(P(
        "Un solo modulo lo lee: <b>agent/inbound_tokens.py:32</b> dentro de la funcion _secreto(). "
        "Esa funcion la consumen dos rutas criticas:"
    ))
    usos_rows = [
        ["Funcion", "Llamada desde", "Que hace"],
        ["_secreto() -> generar_token(telefono)",
         "agent/main.py:526-527 (GET /admin/inbound/token)",
         "Emite tokens HMAC para que el owner los pegue en Zapier/Make/n8n."],
        ["_secreto() -> verificar_token(token)",
         "agent/main.py:550-551 (POST /webhook/inbound/{token})",
         "Valida el token recibido del servicio externo y devuelve el telefono asociado."],
    ]
    s.append(small_table(para_rows(usos_rows),
                         col_widths=[5.0*cm, 5.5*cm, 6.5*cm]))
    s.append(P(
        "INBOUND_WEBHOOK_SECRET aparece tambien documentada en .env.example:145-151 como variable opcional."
    ))

    # ── 2. Fallback actual ──────────────────────────────────────────────
    s.append(H1("2. Fallback actual si la variable no esta configurada"))
    s.append(P("agent/inbound_tokens.py:30-42:"))
    codigo_actual = (
        'def _secreto() -> bytes:\n'
        '    secret = os.getenv("INBOUND_WEBHOOK_SECRET", "").strip()\n'
        '    if secret:\n'
        '        return secret.encode("utf-8")\n'
        '    # Fallback en dev: derivar de ADMIN_TOKEN si existe, sino un valor fijo de dev.\n'
        '    admin = os.getenv("ADMIN_TOKEN", "").strip()\n'
        '    if admin:\n'
        '        logger.warning("[INBOUND] INBOUND_WEBHOOK_SECRET no configurado, derivando de ADMIN_TOKEN")\n'
        '        return hashlib.sha256(b"inbound-webhook-derived|" + admin.encode("utf-8")).digest()\n'
        '    logger.warning("[INBOUND] INBOUND_WEBHOOK_SECRET no configurado — usando valor de desarrollo INSEGURO")\n'
        '    return b"dona-inbound-dev-secret-do-not-use-in-prod"\n'
    )
    s.append(CODE(codigo_actual))
    s.append(P("Tres caminos en orden de preferencia:"))
    s.extend(bullets([
        "<b>Secret real</b> (INBOUND_WEBHOOK_SECRET no vacio) &mdash; ruta segura.",
        "<b>Derivado de ADMIN_TOKEN</b>: SHA256(b'inbound-webhook-derived|' + ADMIN_TOKEN). Warning. Inseguro en produccion.",
        "<b>Literal hardcodeado</b> b'dona-inbound-dev-secret-do-not-use-in-prod'. Warning. Catastrofico si se llega aqui.",
    ]))

    # ── 3. ADMIN_TOKEN derivado y literales ────────────────────────────
    s.append(H1("3. Uso de ADMIN_TOKEN, valores derivados o literales de desarrollo"))
    paths_rows = [
        ["Path", "Inseguridad", "Por que"],
        ["Derivar de ADMIN_TOKEN", "<b>Alta</b> en produccion",
         "El derivado es sha256(prefijo_publico + ADMIN_TOKEN). El prefijo esta en el repo publico ('inbound-webhook-derived|'). Cualquiera con acceso a ADMIN_TOKEN (un dev, un leak de logs, un dump de Render env) puede recomputar el secret y forjar tokens. <b>Acopla dos secretos que deberian ser independientes.</b>"],
        ["Literal 'dona-inbound-dev-secret-do-not-use-in-prod'", "<b>Critica</b> en produccion",
         "El literal esta en el repo publico de GitHub. Cualquier persona en Internet puede usarlo si Dona corre con ese fallback. Forja tokens para cualquier telefono que el atacante invente."],
    ]
    s.append(small_table(para_rows(paths_rows),
                         col_widths=[5.0*cm, 3.5*cm, 8.5*cm]))

    # ── 4. Endpoints e integraciones ────────────────────────────────────
    s.append(H1("4. Endpoints / integraciones que dependen del secret"))

    s.append(H2("4.1 GET /admin/inbound/token?telefono=<E.164> (agent/main.py:513-537)"))
    s.extend(bullets([
        "<b>Acceso</b>: solo owner (Bearer ADMIN_TOKEN).",
        "<b>Output</b>: token + URL &lt;BASE_URL&gt;/webhook/inbound/&lt;token&gt; lista para pegar en Zapier/Make/n8n.",
        "<b>Quien lo usa</b>: el owner. Cero impacto si la URL del endpoint no cambia.",
    ]))

    s.append(H2("4.2 POST /webhook/inbound/{token} (agent/main.py:540-569)"))
    s.extend(bullets([
        "<b>Acceso</b>: publico (no requiere admin token).",
        "<b>Body</b>: {'mensaje': 'texto...'}.",
        "<b>Comportamiento</b>: si el token es valido, envia el mensaje via proveedor.enviar_mensaje (Meta o Whapi). Trunca a 4000 chars.",
        "<b>Quien lo usa</b>: servicios externos (Zapier/Make/n8n triggers, Shopify, Stripe events del owner, etc.).",
    ]))

    s.append(H2("4.3 Integraciones reales conectadas"))
    s.append(P(
        "No hay registro en codigo de que Zaps/Makes estan activos. El owner es el unico que sabe. "
        "<b>Cada token emitido vive donde el owner lo pego.</b>"
    ))

    # ── 5. Tokens emitidos vivos ────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("5. Tokens ya emitidos que podrian invalidarse con una rotacion"))
    s.append(P(
        "<b>Realidad tecnica</b>: cada token esta firmado con el secret vigente al momento de emision. "
        "Si el secret cambia, <b>todos</b> los tokens previos quedan invalidos (responden 403 al primer POST)."
    ))
    s.append(P(
        "<b>Necesito tu confirmacion operativa</b> sobre el estado actual de la variable en Render &mdash; "
        "esto define el alcance del impacto:"
    ))
    escenarios_rows = [
        ["Escenario", "Efecto del cambio T0.4 + setear INBOUND_WEBHOOK_SECRET"],
        ["A. INBOUND_WEBHOOK_SECRET ya esta en Render con un valor real",
         "<b>Cero impacto.</b> El cambio T0.4 solo cierra paths fallback. Tokens existentes siguen validos."],
        ["B. INBOUND_WEBHOOK_SECRET no esta, ADMIN_TOKEN si (path derivado activo hoy)",
         "Tokens existentes firmados con derivado. Setear INBOUND_WEBHOOK_SECRET nuevo = <b>invalidacion masiva</b>."],
        ["C. Ninguna de las dos (literal activo)",
         "Tokens existentes firmados con el literal publico. <b>Compromiso preexistente</b> &mdash; hay que rotar si o si."],
    ]
    s.append(small_table(para_rows(escenarios_rows),
                         col_widths=[6.0*cm, 11.0*cm]))

    # ── 6. Riesgo real ──────────────────────────────────────────────────
    s.append(H1("6. Riesgo real actual si el fallback sigue activo en produccion"))

    s.append(H2("6.1 Escenario A (INBOUND_WEBHOOK_SECRET ya seteado)"))
    s.append(P("Riesgo bajo. El check de import ni siquiera se ejecuta porque la variable esta. T0.4 solo blinda codigo."))

    s.append(H2("6.2 Escenario B (derivado de ADMIN_TOKEN)"))
    s.append(P("Riesgo <b>alto</b>:"))
    s.extend(bullets([
        "Cualquier filtracion de ADMIN_TOKEN (logs, dump, ex-empleado) entrega tambien el secret de inbound webhooks.",
        "Atacante recomputa el HMAC, forja un token valido para &lt;cualquier-numero&gt;, y hace POST /webhook/inbound/&lt;forjado&gt; con {'mensaje': 'Spam!'}.",
        "Dona envia spam por Meta/Whapi al telefono que el atacante elija. <b>Costos</b>, <b>abuso del proveedor</b> (puede llevar a baneo de Meta App o WHAPI_TOKEN), <b>violacion de TCPA</b>.",
    ]))

    s.append(H2("6.3 Escenario C (literal hardcodeado)"))
    s.append(P("Riesgo <b>catastrofico</b>:"))
    s.extend(bullets([
        "El secret esta en GitHub publico. Cualquiera puede armar tokens validos.",
        "Mismo abuso que arriba pero sin barrera de entrada.",
        "Si Dona corre asi en produccion aunque sea unas horas, se debe asumir <b>compromiso de tokens</b> y rotar de inmediato.",
    ]))

    s.append(H2("6.4 Defensa actual"))
    s.append(P(
        "agent/main.py:540-569 valida el token con compare_digest (timing-safe, bien) pero <b>no hay</b>:"
    ))
    s.extend(bullets([
        "Rate limiting en /webhook/inbound/{token} (un atacante puede martillar el endpoint).",
        "Logging detallado de intentos rechazados (los 403 quedan en log estandar).",
        "TTL de tokens (los tokens no expiran 'por diseno' segun el docstring).",
    ]))
    s.append(P(
        "T0.4 no resuelve eso. Cierra solo el agujero del secret. El rate limiting y el TTL son tareas separadas."
    ))

    # ── 7. Variables en Render ──────────────────────────────────────────
    s.append(H1("7. Variables que deben estar en Render antes del merge"))
    s.append(P("Solo una:"))
    var_rows = [
        ["Variable", "Origen", "Formato", "Comando para generar"],
        ["INBOUND_WEBHOOK_SECRET",
         "string aleatorio largo, decision del owner",
         "URL-safe, 32+ chars",
         "python -c \"import secrets; print(secrets.token_urlsafe(32))\""],
    ]
    s.append(small_table(para_rows(var_rows),
                         col_widths=[4.5*cm, 4.5*cm, 3.0*cm, 5.0*cm]))
    s.append(P(
        "<b>No solicito ver el valor.</b> Solo confirmacion de que esta seteada en Render con un valor "
        "que <b>no es derivado de ADMIN_TOKEN ni el literal del repo</b>."
    ))
    s.append(P("ADMIN_TOKEN no se modifica en este PR. Sigue siendo el Bearer del endpoint /admin/*."))

    # ── 8. Cambio minimo ────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("8. Cambio minimo recomendado"))
    s.append(P(
        "<b>Patron identico al de T0.2</b> (Stripe). El modulo inbound_tokens.py se importa al startup desde "
        "main.py, asi que un check al import-time aborta el deploy si falta el secret."
    ))

    s.append(H2("8.1 agent/inbound_tokens.py"))
    s.append(P("Agregar al <b>top del modulo</b> (tras el logger):"))
    bloque_top = (
        '_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()\n'
        '\n'
        'if _ENVIRONMENT == "production" and not os.getenv("INBOUND_WEBHOOK_SECRET", "").strip():\n'
        '    raise RuntimeError(\n'
        '        "[INBOUND] INBOUND_WEBHOOK_SECRET no configurado en produccion — "\n'
        '        "los tokens caerian a un fallback derivado de ADMIN_TOKEN o a un "\n'
        '        "literal publico del repo, lo que permitiria a un atacante forjar "\n'
        '        "tokens para enviar mensajes WhatsApp a cualquier numero. "\n'
        '        "Configura la variable antes de reintentar el deploy."\n'
        '    )\n'
    )
    s.append(CODE(bloque_top))

    s.append(P("Modificar _secreto() para defensa en profundidad:"))
    secreto_propuesto = (
        'def _secreto() -> bytes:\n'
        '    secret = os.getenv("INBOUND_WEBHOOK_SECRET", "").strip()\n'
        '    if secret:\n'
        '        return secret.encode("utf-8")\n'
        '    # En produccion no debemos llegar aqui (el check de import lo evita), pero\n'
        '    # como defensa en profundidad rechazamos via RuntimeError si la env var\n'
        '    # desaparece despues del startup.\n'
        '    environment = os.getenv("ENVIRONMENT", "development").lower()\n'
        '    if environment == "production":\n'
        '        raise RuntimeError(\n'
        '            "[INBOUND] INBOUND_WEBHOOK_SECRET no configurado en produccion"\n'
        '        )\n'
        '    # Fallback dev/test: derivar de ADMIN_TOKEN o literal. Solo no-prod.\n'
        '    admin = os.getenv("ADMIN_TOKEN", "").strip()\n'
        '    if admin:\n'
        '        logger.warning("[INBOUND] ... derivando de ADMIN_TOKEN (INSEGURO, solo dev/test)")\n'
        '        return hashlib.sha256(b"inbound-webhook-derived|" + admin.encode("utf-8")).digest()\n'
        '    logger.warning("[INBOUND] ... usando valor de desarrollo INSEGURO (solo dev/test)")\n'
        '    return b"dona-inbound-dev-secret-do-not-use-in-prod"\n'
    )
    s.append(CODE(secreto_propuesto))

    s.append(H2("8.2 agent/main.py"))
    s.append(P(
        "Agregar <i>import agent.inbound_tokens  # noqa: F401</i> despues del import de agent.billing "
        "que ya esta. Una linea. Fuerza el check al startup."
    ))

    s.append(H2("8.3 .env.example"))
    s.append(P(
        "Reformular el bloque actual (linea 145-151) para enfatizar obligatoriedad en produccion. "
        "Sin valores reales."
    ))

    s.append(H2("8.4 Total de cambio"))
    s.extend(bullets([
        "agent/inbound_tokens.py: +12 lineas top-level + ~6 lineas en _secreto().",
        "agent/main.py: +1 linea.",
        ".env.example: ajustar bloque existente, +3 lineas.",
        "tests/test_inbound_tokens.py: 4 tests nuevos.",
        "<b>PR pequeno, ~25-30 lineas netas.</b>",
    ]))

    # ── 9. Archivos ─────────────────────────────────────────────────────
    s.append(H1("9. Archivos que tocaria"))
    arch_rows = [
        ["Archivo", "Tipo de cambio"],
        ["agent/inbound_tokens.py",
         "Top-level: _ENVIRONMENT + check RuntimeError si production sin secret. Modificar _secreto() para rechazar en production (defensa en profundidad)."],
        ["agent/main.py",
         "Agregar 'import agent.inbound_tokens  # noqa: F401' despues del import de agent.billing."],
        [".env.example",
         "Reformular bloque INBOUND_WEBHOOK_SECRET enfatizando obligatoriedad en produccion. Sin valores reales."],
        ["tests/test_inbound_tokens.py",
         "Agregar TestSecretoProduction con 4 tests."],
    ]
    s.append(small_table(para_rows(arch_rows),
                         col_widths=[4.5*cm, 12.5*cm]))
    s.append(P("<b>Lo que NO toco:</b>"))
    s.extend(bullets([
        "agent/main.py:webhook_inbound (handler) &mdash; su logica ya rechaza con 403 si verificar_token retorna None. No requiere cambios.",
        "agent/main.py:admin_generar_token_inbound &mdash; sin cambios.",
        "Comportamiento de generar_token y verificar_token (la logica HMAC) &mdash; sin cambios. Solo cambia de donde sale el secret.",
        "Rate limiting, TTL, audit log de inbound &mdash; fuera del alcance de T0.4 (tareas separadas).",
    ]))

    # ── 10. Tests ───────────────────────────────────────────────────────
    s.append(H1("10. Tests a correr"))

    s.append(H2("10.1 Tests existentes a actualizar"))
    s.extend(bullets([
        "8 tests actuales pasan tal cual con el monkeypatch de INBOUND_WEBHOOK_SECRET='test-secret-xyz' (autouse fixture en linea 12-15). <b>Sin cambios necesarios.</b>",
        "El fixture autouse ya garantiza que el secret esta seteado, asi que el check de production no levanta en entorno de tests.",
    ]))

    s.append(H2("10.2 Tests nuevos a agregar"))
    nuevos = (
        'class TestSecretoProduction:\n'
        '    """T0.4: el modulo no debe arrancar en produccion sin INBOUND_WEBHOOK_SECRET."""\n'
        '\n'
        '    def test_production_sin_secret_levanta_runtime_error_al_reload(self, monkeypatch):\n'
        '        import importlib\n'
        '        monkeypatch.setenv("ENVIRONMENT", "production")\n'
        '        monkeypatch.delenv("INBOUND_WEBHOOK_SECRET", raising=False)\n'
        '        try:\n'
        '            with pytest.raises(RuntimeError, match="INBOUND_WEBHOOK_SECRET"):\n'
        '                importlib.reload(inbound_tokens)\n'
        '        finally:\n'
        '            monkeypatch.setenv("ENVIRONMENT", "test")\n'
        '            monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "test-secret-xyz")\n'
        '            importlib.reload(inbound_tokens)\n'
        '\n'
        '    def test_production_secret_solo_whitespace_levanta(self, monkeypatch):\n'
        '        # Similar: con valor "   " levanta RuntimeError.\n'
        '\n'
        '    def test_production_runtime_sin_secret_levanta_en_secreto(self, monkeypatch):\n'
        '        # Defensa en profundidad: si el secret desaparece despues del import.\n'
        '\n'
        '    def test_production_con_secret_funciona(self, monkeypatch):\n'
        '        # Con secret valido, _secreto() retorna los bytes correctos.\n'
    )
    s.append(CODE(nuevos))
    s.append(P(
        "Total: 8 existentes + 4 nuevos = <b>12 tests</b> en test_inbound_tokens.py."
    ))

    s.append(H2("10.3 Suite completa"))
    s.append(P(
        "<i>pytest -q</i>. Estimado: 455 actuales + 4 nuevos = <b>~459 tests</b>, ~92 s."
    ))

    # ── 11. Riesgos ─────────────────────────────────────────────────────
    s.append(H1("11. Riesgos de compatibilidad y deploy"))
    riesgos_rows = [
        ["Riesgo", "Probabilidad", "Mitigacion"],
        ["Render sin INBOUND_WEBHOOK_SECRET -> deploy aborta",
         "Solo si escenario era B o C antes del merge",
         "Setear primero, mergear despues"],
        ["Tokens emitidos antes del PR son invalidados por la rotacion",
         "Solo si escenario B o C -> necesita re-emision",
         "Plan de rotacion de §12"],
        ["ADMIN_TOKEN se sigue derivando en dev",
         "OK por diseno (path dev permitido)",
         "Solo cambia en produccion"],
        ["Tests existentes rompen",
         "Minima &mdash; el fixture autouse ya setea el secret",
         "Plan: ningun test existente rompe"],
        ["Reload del modulo en tests deja estado roto",
         "Baja, ya manejado en T0.2",
         "Patron try/finally con restore"],
    ]
    s.append(small_table(para_rows(riesgos_rows),
                         col_widths=[6.0*cm, 4.5*cm, 6.5*cm]))

    s.append(P("<b>Compatibilidad con Zapier/Make/n8n:</b>"))
    s.extend(bullets([
        "El formato del token NO cambia.",
        "El endpoint /webhook/inbound/{token} sigue identico.",
        "Solo cambia el secret bajo el cual se firma. Si el secret en Render es el mismo que ya estaba activo -> cero impacto.",
    ]))

    # ── 12. Plan de rotacion ────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("12. Plan de rotacion seguro"))
    s.append(P(
        "Esta es <b>la parte distinta</b> de T0.4 vs T0.2 y T0.3. Hay tokens emitidos vivos en servicios externos."
    ))

    s.append(H2("12.1 Antes de empezar el PR — Diagnostico operativo"))
    s.append(P("El owner debe responder (yo no necesito ver valores):"))
    s.extend(bullets([
        "<b>Esta hoy INBOUND_WEBHOOK_SECRET seteado en Render?</b>",
        "Si si -> escenario A. Cero rotacion. PR seguro.",
        "Si no:",
    ]))
    s.extend([
        Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&bull; <b>Se esta usando hoy /webhook/inbound/?</b> Que Zaps/Makes/n8ns estan conectados? Hay tokens ya emitidos en uso real?", styles["BulletDona"]),
        Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&bull; Si <b>no hay tokens en uso</b> -> escenario 'facil': setear el secret, mergear, listo. No hay impacto.", styles["BulletDona"]),
        Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&bull; Si <b>hay tokens en uso</b> -> escenario 'rotacion coordinada' (§12.2 abajo).", styles["BulletDona"]),
    ])

    s.append(H2("12.2 Rotacion coordinada (solo si escenario B/C con tokens vivos)"))
    s.append(P("Pasos en orden estricto:"))
    s.extend(bullets([
        "<b>Inventario</b> (offline, owner): listar todos los Zaps/Makes/n8ns que apuntan a /webhook/inbound/... Anotar el telefono asociado a cada uno (no el token, no el secret &mdash; solo el telefono).",
        "<b>Generar nuevo secret aleatorio</b>: <i>python -c \"import secrets; print(secrets.token_urlsafe(32))\"</i>. El owner copia el valor (yo no lo veo).",
        "<b>Setear INBOUND_WEBHOOK_SECRET en Render</b> con ese valor. Render redeploya (despliegue de la env var sin codigo nuevo). En ese momento: tokens viejos quedan invalidos (responden 403). Cero deploy de codigo nuevo todavia.",
        "<b>Verificar en Render dashboard</b> que el deploy con la nueva env termino OK.",
        "<b>Mergear el PR T0.4</b>. Render redeploya con el codigo nuevo. El check del import pasa porque el secret esta.",
        "<b>Re-emitir tokens</b> para cada telefono del inventario: GET /admin/inbound/token?telefono=&lt;E.164&gt;. El owner pega cada nueva URL en el Zap/Make/n8n correspondiente.",
        "<b>Probar</b> un disparo desde cada Zap -> confirmar que llega el mensaje a WhatsApp.",
    ]))
    s.append(P(
        "<b>Tiempo estimado de la ventana de rotura:</b> entre paso 3 y paso 7. Durante ese tiempo, los Zaps externos "
        "disparan POST que devuelven 403. El owner debe coordinar con sus integraciones para minimizar esa ventana."
    ))

    s.append(H2("12.3 Variante 'rotacion zero-downtime' (no recomendada para este PR)"))
    s.append(P(
        "Soportar <b>dos secrets simultaneamente</b> (INBOUND_WEBHOOK_SECRET_PRIMARY + INBOUND_WEBHOOK_SECRET_PREVIOUS) "
        "durante una ventana de transicion. verificar_token aceptaria tokens firmados por cualquiera. generar_token "
        "solo usa el primary."
    ))
    s.extend(bullets([
        "<b>Pros:</b> los tokens viejos siguen funcionando hasta que se haya migrado el ultimo Zap.",
        "<b>Contras:</b> ~30 lineas extra de codigo + mas complejidad. Si Dona tiene pocas integraciones (probable), no vale la pena.",
        "<b>Recomendacion:</b> no implementar en T0.4. Si el owner reporta que tiene 10+ Zaps activos, lo podemos retomar como T0.4-bis.",
    ]))

    # ── 13. Checklist ───────────────────────────────────────────────────
    s.append(H1("13. Checklist antes de mergear"))

    s.append(H2("13.1 Pre-PR (antes de empezar)"))
    s.extend(checklist([
        "Confirmar el estado actual de INBOUND_WEBHOOK_SECRET en Render (escenario A/B/C).",
        "Si escenario B o C: hacer inventario de Zaps/Makes/n8ns activos antes de tocar nada.",
        "Decidir nombre de branch: sugiero <b>pr/inbound-webhook-secret-obligatorio</b>.",
        "Si hay tokens vivos: avisar a los servicios externos del corte planificado.",
    ]))

    s.append(H2("13.2 Pre-merge (durante rotacion si aplica)"))
    s.extend(checklist([
        "Generar nuevo INBOUND_WEBHOOK_SECRET con <i>secrets.token_urlsafe(32)</i>.",
        "Setear en Render (sin mergear todavia).",
        "Verificar que el deploy con la nueva env termino OK.",
        "(Opcional) Re-emitir tokens de prueba y validar que disparan mensajes.",
    ]))

    s.append(H2("13.3 Durante el PR (local)"))
    s.extend(checklist([
        "Implementar cambio en agent/inbound_tokens.py (top-level + _secreto()).",
        "Agregar import en agent/main.py.",
        "Reformular .env.example.",
        "Agregar TestSecretoProduction (4 tests).",
        "<i>pytest -q</i> localmente &mdash; 100% verde.",
    ]))

    s.append(H2("13.4 Pre-push"))
    s.extend(checklist([
        "Diff toca solo los 4 archivos previstos.",
        "Ningun secret real en codigo, comentarios ni tests.",
        "Commit: <i>fix(seguridad): INBOUND_WEBHOOK_SECRET obligatorio en produccion</i>.",
    ]))

    s.append(H2("13.5 Post-push, pre-merge"))
    s.extend(checklist([
        "Push a origin/pr/inbound-webhook-secret-obligatorio.",
        "Confirmar visualmente que INBOUND_WEBHOOK_SECRET esta en Render.",
        "Si hay rotacion pendiente: completarla antes de mergear.",
    ]))

    s.append(H2("13.6 Post-merge"))
    s.extend(checklist([
        "Render deploy debe completar sin RuntimeError.",
        "Probar GET /admin/inbound/token con un telefono -> URL valida.",
        "Probar POST /webhook/inbound/&lt;token&gt; con la URL recien emitida -> mensaje llega a WhatsApp.",
        "Si hay Zaps existentes que aun no se actualizaron: completar la migracion.",
        "Verificar logs por 403 inesperados (Zaps todavia con token viejo).",
    ]))

    # ── 14. Resumen ejecutivo ───────────────────────────────────────────
    s.append(H1("14. Resumen ejecutivo"))
    resumen_rows = [
        ["Aspecto", "Detalle"],
        ["Riesgo que cierra",
         "P0 &mdash; token forjable que permite enviar mensajes WhatsApp a cualquier numero (escenarios B y C). En escenario A solo blinda codigo."],
        ["Patron",
         "Identico a T0.2: check al import del modulo + defensa en profundidad en _secreto()."],
        ["Archivos", "4 (1 codigo, 1 import 1 linea, 1 docs, 1 tests)"],
        ["Tamano", "~25-30 lineas netas"],
        ["Tests", "0 actualizados + 4 nuevos"],
        ["Env var", "INBOUND_WEBHOOK_SECRET obligatoria en Render"],
        ["Compatibilidad",
         "Tokens existentes solo siguen validos si el secret no cambia. Si hay rotacion -> seguir §12.2"],
        ["Riesgo de deploy",
         "Bajo si la matriz env vars esta consistente"],
        ["Reversible", "Si, redeploy del commit anterior"],
        ["Dependencia operativa",
         "Inventario de Zaps/Makes/n8ns antes de la rotacion si aplica"],
    ]
    s.append(small_table(para_rows(resumen_rows),
                         col_widths=[5.0*cm, 12.0*cm]))

    s.append(Spacer(1, 14))
    s.append(P(
        "<b>Estado:</b> no implementado todavia. Esperando OK del owner con confirmacion de:"
    ))
    s.extend(bullets([
        "Estado actual de INBOUND_WEBHOOK_SECRET en Render (escenario A/B/C).",
        "Si hay tokens emitidos vivos en Zapier/Make/n8n y cuantos aproximadamente.",
        "Si autorizas la rotacion coordinada o preferis 'no hay tokens vivos, mergear directo'.",
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
        title="Dona — Diagnostico T0.4 Inbound webhook",
        author="Diagnostico generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch,
                          "Dona — T0.4 INBOUND_WEBHOOK_SECRET sin fallback · 2026-05-01")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
