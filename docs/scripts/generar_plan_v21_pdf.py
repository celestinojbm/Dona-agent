"""
Genera Plan_Dona_v2_1_2026-04-30.pdf con los ajustes pre-implementacion:
- Fusion T0.5 + T0.8.
- PR1 Sentry con Variantes A y B (autorizacion pendiente).
- Primer paquete actualizado (6 PRs).
- Tool Intelligence Layer: fichas Adobe Firefly + Higgsfield.
- Benchmark creativo actualizado.
- Workflows premium para Dona.

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

OUTPUT = r"C:\Users\celes\Dona-agent\Plan_Dona_v2_1_2026-04-30.pdf"

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


def kv_table(rows, col_widths=(4.5*cm, 12.5*cm)):
    rows_para = [[Paragraph("<b>" + r[0] + "</b>", styles["BodyTight"]),
                  Paragraph(r[1], styles["BodyTight"])] for r in rows]
    return small_table(rows_para, col_widths=col_widths, header=False)


def build_story():
    s = []

    # Portada
    s.append(Paragraph("Dona — Plan v2.1 (ajustes pre-implementacion)", styles["TitleBig"]))
    s.append(Paragraph(
        "Fecha: 2026-04-30 &nbsp;·&nbsp; HEAD: 5b7d42d &nbsp;·&nbsp; "
        "Estado: planificacion, no implementacion &nbsp;·&nbsp; Modo: solo lectura.",
        styles["MetaTop"],
    ))

    s.append(P(
        "Este documento aplica los ajustes pedidos sobre el Plan v2: fusion de T0.5 y T0.8, dos variantes "
        "para PR1 con autorizacion pendiente, primer paquete recomendado actualizado, y la incorporacion de "
        "<b>Adobe Firefly</b> y <b>Higgsfield</b> al Tool Intelligence Layer + benchmark creativo. La verificacion "
        "tecnica se hizo contra documentacion oficial (Adobe Blog 2026-04-28, Higgsfield MCP)."
    ))

    # ── 1. Confirmacion de ajustes ──────────────────────────────────────
    s.append(H1("1. Confirmacion de ajustes obligatorios"))

    s.append(H2("1.1 Fusion T0.5 + T0.8"))
    s.append(P(
        "Confirmado. Ambas tareas tratan del mismo problema: PII / contactos del owner hardcodeados. Quedan fusionadas "
        "en una sola tarea / un solo PR. T0.8 queda eliminada del backlog (absorbida)."
    ))

    s.append(H3("T0.5 nueva (reemplaza a T0.5 + T0.8 originales) — Centralizar contactos del owner en env vars"))
    t05_rows = [
        ["Objetivo",
         "Eliminar cualquier numero/contacto personal hardcodeado del repo. Todo va por env var; sin env var, el endpoint correspondiente devuelve 404."],
        ["Capas tocadas", "16"],
        ["Archivos probables",
         "agent/main.py:2165-2172 (/voice/reenviar + TwiML); .env.example. Grep adicional para detectar otros literales personales."],
        ["Riesgo", "Bajo. Cambio local; sin efectos en produccion si la env var queda configurada."],
        ["Tests requeridos",
         "Con VOICE_FORWARD_NUMBER → TwiML correcto; sin var → 404; smoke test que valida que no quedan numeros E.164 personales en codigo (grep -E '\\+1[0-9]{10}')."],
        ["Criterio de aceptacion",
         "Ningun numero personal aparece en grep del repo; endpoint funciona con env var; falla limpio sin ella."],
        ["Confirmacion humana", "No"],
    ]
    s.append(kv_table(t05_rows))

    s.append(H2("1.2 PR1 Sentry — dos variantes con autorizacion pendiente"))
    s.append(P(
        "Confirmado: <b>PR1 no se ejecuta hasta autorizar variante</b>. Mientras tanto el orden recomendado del paquete "
        "se reagenda para que PR1 no sea bloqueante."
    ))

    s.append(H3("Variante A — Log sanitization sin nueva dependencia"))
    va_rows = [
        ["Objetivo",
         "Logs JSON estructurados con redaction de PII (telefono, email, contenido de mensajes, tokens, payloads de webhook). Sin tocar requirements.txt."],
        ["Capas tocadas", "16, 17"],
        ["Archivos probables",
         "agent/logging_config.py (extender con JsonFormatter propio + PIIRedactor filter); agent/main.py (middleware existente, solo se ajusta el formatter)."],
        ["Riesgo",
         "Bajo. Cambio puramente local de formatting + filtros. Cero dependencias nuevas. Cero costo recurrente."],
        ["Tests requeridos",
         "tests/test_logging.py: telefonos E.164, emails, image_id, audio_id, body de webhook se enmascaran en INFO; mantenidos en DEBUG con flag LOG_LEVEL=DEBUG; logs de error preservan stacktrace; formato JSON parseable."],
        ["Criterio de aceptacion",
         "Logs en produccion salen JSON, PII redactada. Sin instalar nada. Render logs ya parsean JSON."],
        ["Confirmacion humana",
         "Si — solo confirmar que se usan los logs nativos de Render (sin observabilidad externa) en esta etapa."],
        ["Lo que NO entrega",
         "Errores agrupados, alertas, performance traces. Eso requiere Variante B (o T4.4 mas adelante)."],
    ]
    s.append(kv_table(va_rows))

    s.append(H3("Variante B — Log sanitization + Sentry (con dependencia autorizada)"))
    vb_rows = [
        ["Objetivo", "Todo lo de Variante A + integracion Sentry para errores agrupados, releases, performance opcional."],
        ["Capas tocadas", "16, 17"],
        ["Archivos probables",
         "Variante A + agent/main.py (sentry_sdk.init con before_send que pasa por el PIIRedactor); requirements.txt (anadir sentry-sdk[fastapi]); .env.example (SENTRY_DSN)."],
        ["Riesgo",
         "Bajo-medio. Sin DSN configurado, sentry-sdk es no-op. Costo Sentry segun volumen (free tier suficiente para Phase 0)."],
        ["Tests requeridos",
         "Variante A + test que verifica before_send redacta PII antes del envio; en local sin DSN no hay overhead."],
        ["Criterio de aceptacion",
         "Errores en prod agrupados en Sentry con PII redactada; rollback = quitar SENTRY_DSN y la lib queda inerte."],
        ["Confirmacion humana",
         "Si — autorizar dependencia sentry-sdk[fastapi] + crear cuenta Sentry + DSN en Render env."],
        ["Trade-off",
         "Variante B requiere proveedor externo + cuenta + DSN; Variante A no. Si la decision sobre observabilidad aun no esta madura, A es el camino seguro y B se hace en T4.4."],
    ]
    s.append(kv_table(vb_rows))

    s.append(P(
        "<b>Recomendacion</b>: Variante A para Phase 0; Variante B en T4.4 cuando el plan de observabilidad este completo "
        "(incluyendo alertas, releases, performance, on-call). Esto desacopla seguridad de Phase 0 de la decision de proveedor de observabilidad."
    ))

    # ── 2. Primer paquete actualizado ───────────────────────────────────
    s.append(PageBreak())
    s.append(H1("2. Primer paquete recomendado actualizado"))
    s.append(P("<b>Paquete Phase 0 v2.1</b>: 6 PRs (antes 7). T0.8 absorbida en T0.5."))

    paquete_rows = [
        ["Orden", "PR", "Tarea", "Bloqueado por", "Conf"],
        ["1", "PR1", "Log sanitization (Variante A o B segun decision)", "Decision owner", "Si"],
        ["2", "PR2", "Inventario legacy (enhanced/, start.sh, mounts compose, migration.py)",
         "Autorizacion para docs/legacy-inventory.md", "Si"],
        ["3", "PR3", "Centralizar contactos del owner en env vars (T0.5 fusionada)", "—", "No"],
        ["4", "PR4", "Disclaimer legal del landing alineado con realidad", "Wording final", "Si"],
        ["5", "PR5", "Stripe webhook firma obligatoria en prod",
         "Confirmacion de que STRIPE_WEBHOOK_SECRET esta en Render", "No"],
        ["6", "PR6", "Meta webhook firma obligatoria en prod",
         "Confirmacion de que META_APP_SECRET esta en Render", "No"],
        ["7", "PR7", "INBOUND_WEBHOOK_SECRET sin fallback en prod",
         "Comunicacion al owner si hay tokens emitidos", "Si"],
    ]
    s.append(small_table(para_rows(paquete_rows),
                         col_widths=[1.2*cm, 1.1*cm, 7.2*cm, 6.5*cm, 1.2*cm]))

    s.append(H3("Notas"))
    s.extend(bullets([
        "Si <b>Variante A</b> se elige para PR1, PR1 queda desbloqueado de inmediato.",
        "Si <b>Variante B</b>, PR1 espera DSN + cuenta Sentry, y se hace mientras PR2/PR3 avanzan.",
        "PR3 (T0.5 fusionada) puede ejecutarse en paralelo a PR2 — no comparten archivos.",
        "PR4 puede ejecutarse en paralelo con cualquiera; solo toca landing/app/page.tsx.",
        "PR5/PR6/PR7 quedan al final por requerir coordinacion con paneles externos.",
        "Total: 6 PRs efectivos. Ningun PR > 5 archivos. Ningun PR introduce arquitectura nueva.",
    ]))

    # ── 3. Tool Intelligence Layer ──────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("3. Tool Intelligence Layer — fichas Adobe Firefly y Higgsfield"))

    s.append(P("Investigado contra documentacion oficial:"))
    s.extend(bullets([
        "<b>Adobe</b> lanzo el conector “Adobe for creativity” para Claude el 2026-04-28 (Adobe Blog). Expone 50+ herramientas pro de Photoshop, Illustrator, Firefly, Express, Premiere, Lightroom, InDesign y Stock dentro de Claude. Acceso guest a ~40 herramientas; sign-in con cuenta Adobe (free o paid) desbloquea mas + limites + persistencia. Modelos especificos de Firefly dentro del conector aun no documentados — eso es el Firefly AI Assistant aparte (beta publica).",
        "<b>Higgsfield</b> expone un MCP server publico (https://mcp.higgsfield.ai/mcp) que se agrega a Claude por Settings → Connectors, sin API keys, autenticando con cuenta Higgsfield. Cubre ~30 modelos: Soul (imagen, character consistency), Nano Banana, Flux, Seedance, Kling, Veo, Hailuo. Hasta 4K imagen y 15s video. Pricing: Starter $15, Plus $34, Ultra $84, Business $49/seat. REST API pay-per-use disponible via terceros (WaveSpeed, Unifically) para uso programatico.",
    ]))

    # 3.1 Ficha Adobe
    s.append(H2("3.1 Ficha — Adobe Firefly + “Adobe for creativity” connector"))
    adobe_rows = [
        ["Nombre", "Adobe Firefly + Adobe for creativity (connector para Claude)"],
        ["Categoria", "Imagen + edicion + composicion + Stock licensed"],
        ["Que hace",
         "Generacion y edicion de imagen (Firefly), retoque pro (Photoshop), vectorial (Illustrator), maquetacion (InDesign), edicion de video (Premiere), foto (Lightroom), assets sociales (Express). Via conector, todo invocable por Claude en lenguaje natural."],
        ["Que problema resuelve en Dona",
         "Calidad <b>commercial-safe</b> garantizada para assets de marca de los Workspaces (Firefly entrenado en Adobe Stock + contenido licenciado). Edicion pro (no solo generacion). Workflows multi-tool desde el orquestador."],
        ["Modulo de aplicacion",
         "agent/creativos/, agent/orchestrator/iniciativas/assets_marca.py, futura iniciativa “campana editorial”."],
        ["Reemplaza a",
         "Posible reemplazo parcial de Gemini Flash Image / Ideogram en el tier “premium con licencia comercial garantizada”. No reemplaza nano-banana en tier “estandar barato”."],
        ["Complementa a",
         "Photoroom (bg remove); Replicate/Veo/Seedance (video); Midjourney (estetica distinta)."],
        ["Costo aproximado",
         "API: $0.02–$0.10 por imagen segun modelo (Image 4 Ultra ~20 creditos = ~$0.08–$0.10); enterprise minimo ~$1k/mes. Connector via cuenta Adobe Creative Cloud individual: incluido en plan CC con creditos mensuales."],
        ["Calidad esperada",
         "5/5 para uso editorial / branding. Output con derechos comerciales claros (ventaja regulatoria sobre Midjourney/Stable Diffusion)."],
        ["Riesgos",
         "(a) Pricing enterprise alto; (b) modelos Firefly especificos del connector aun no documentados; (c) connector requiere cuenta Adobe del usuario final si queremos desbloquear todas las herramientas — friccion de onboarding; (d) dependencia de API Adobe (estabilidad, deprecaciones)."],
        ["Privacidad / compliance",
         "Adobe explicita “commercial-safe by training data” (Adobe Stock + licensed). Entrega rights clearance que Midjourney / SD no entregan. Critico para clientes regulados o que respondan a abogados."],
        ["Facilidad de integracion",
         "Dos rutas: (1) MCP-style via “Adobe for creativity” connector — aplica al Claude del usuario, no al backend; (2) Adobe Firefly Services REST API — programable desde el backend Dona, requiere contrato enterprise. <b>Ruta 2 es la que aplica para Dona</b>."],
        ["Prioridad",
         "Alta para tier premium / Pro plan. Decision de integracion tecnica = ruta 2 (REST API), no MCP."],
        ["Experimento minimo",
         "PoC con Firefly Services API: generar 50 imagenes “campana producto X” + comparar costo/calidad/legal vs Gemini Flash Image actual. Metricas: % aprobacion del owner, tiempo de generacion, costo por imagen aprobada."],
        ["Decision actual",
         "Documentar y disenar, no integrar todavia. Bloqueado por: definicion del tier Pro (T1.5) + acceso a Firefly Services (decision owner por costo)."],
        ["Revision programada", "Trimestral."],
    ]
    s.append(kv_table(adobe_rows))

    # 3.2 Ficha Higgsfield
    s.append(H2("3.2 Ficha — Higgsfield (Soul + DoP + MCP)"))
    higgs_rows = [
        ["Nombre", "Higgsfield AI (Soul, DoP, Cinema Studio + MCP server + Cloud REST)"],
        ["Categoria", "Imagen (Soul) + Image-to-video cinematic (DoP) + multi-model gateway"],
        ["Que hace",
         "Soul: imagen con character consistency entre escenas/poses/lighting (4K, cualquier aspect ratio). DoP: motion clips cinematograficos de 5s a partir de imagen (lite/turbo/preview). MCP gateway: invoca tambien Seedance, Kling, Veo, Hailuo, Flux, Sora, GPT Image desde un solo endpoint."],
        ["Que problema resuelve en Dona",
         "(a) Character consistency para campanas (mismo “modelo” en 10 imagenes diferentes); (b) motion ads premium en 5–15s sin armado manual; (c) acceso a N modelos de video detras de un solo connector — util para A/B testing sin integrar cada API."],
        ["Modulo de aplicacion",
         "agent/creativos/imagen.py, agent/creativos/video.py, agent/orchestrator/iniciativas/motion_ads.py (futura)."],
        ["Reemplaza a",
         "Posible reemplazo del wrapper directo a Replicate/Veo/Seedance que ya tiene Dona — si el modelo de creditos sale bien."],
        ["Complementa a",
         "Adobe Firefly (estetica distinta, foco cinematic); Photoroom (no compite)."],
        ["Costo aproximado",
         "Planes consumer: $15–$84/mes; Business $49/seat. REST API pay-per-use via WaveSpeed/Unifically. MCP usa el mismo sistema de creditos."],
        ["Calidad esperada",
         "4–5/5 para motion ads. Soul resuelve un problema real (consistency) que ningun proveedor actual de Dona resuelve."],
        ["Riesgos",
         "(a) Compania joven, riesgo de cambios de pricing/TOS; (b) MCP es para usar dentro de Claude desktop/web del usuario, no programatico server-side — para Dona en produccion se usa Cloud REST o WaveSpeed; (c) terminos comerciales de Higgsfield deben revisarse antes de revender output a clientes pagantes."],
        ["Privacidad / compliance",
         "Documentacion oficial no menciona explicitamente “commercial-safe by training”. Hay que validar con legal antes de campanas comerciales reguladas."],
        ["Facilidad de integracion",
         "Dos rutas: (1) MCP server en Claude del owner (no aplica a Dona en produccion); (2) Higgsfield Cloud REST o WaveSpeed/Unifically REST — programable desde agent/creativos/."],
        ["Prioridad",
         "Alta para feature “campanas de motion ads” (Phase 3, si se generaliza mas alla de Meta Ads). Media para imagen general (Soul vs Firefly compite)."],
        ["Experimento minimo",
         "PoC con Cloud REST: 20 motion ads a partir de imagenes ya generadas por Dona. Metricas: % aprobacion, costo por clip aprobado, tiempo medio."],
        ["Decision actual",
         "Documentar y disenar, no integrar todavia. Bloqueado por: revision legal de TOS comerciales + decision sobre la iniciativa “motion ads” en backlog."],
        ["Revision programada", "Trimestral."],
    ]
    s.append(kv_table(higgs_rows))

    # 3.3 Como aplican integraciones con Claude
    s.append(H2("3.3 Como aplican las integraciones con Claude a Dona"))
    s.append(P("Distincion tecnica clave que afecta la decision de integracion:"))
    rutas_rows = [
        ["Integracion con Claude", "Quien la usa", "Aplica a Dona en produccion"],
        ["Adobe “Adobe for creativity” connector",
         "El usuario final dentro de su Claude (web/desktop)",
         "<b>No directo</b> para el backend de Dona. El backend habla con Claude por API, no con Claude Desktop del owner. Util solo si Dona expone “abre tu Claude desktop con este preset” como UX adicional."],
        ["Higgsfield MCP en Claude", "Igual que arriba",
         "<b>No directo</b> en backend de Dona."],
        ["Adobe Firefly Services REST API",
         "Backend de Dona (programatico)", "<b>Si</b>. Ruta de integracion real para Phase 3."],
        ["Higgsfield Cloud REST + WaveSpeed/Unifically REST",
         "Backend de Dona (programatico)", "<b>Si</b>. Ruta de integracion real para Phase 3."],
        ["Anthropic Claude Sonnet 4.6 con tool-use que llama a las APIs REST",
         "Backend de Dona (Claude actua como agente, no como UI)",
         "<b>Si</b>. Es el patron que ya usa Dona y donde encajan ambas integraciones."],
    ]
    s.append(small_table(para_rows(rutas_rows), col_widths=[5.0*cm, 4.5*cm, 7.5*cm]))
    s.append(P(
        "<b>Conclusion tecnica</b>: las dos noticias de “X integra con Claude” se refieren a connectors para Claude.ai (cliente). "
        "Para Dona, lo relevante es la <b>REST API programatica</b> de cada uno, llamada desde el orquestador de Dona usando "
        "Claude Sonnet 4.6 + tool-use. La narrativa de marca puede mencionar “compatibilidad con el ecosistema Claude”, "
        "pero la integracion tecnica real va por REST."
    ))

    # ── 4. Benchmark creativo actualizado ───────────────────────────────
    s.append(PageBreak())
    s.append(H1("4. Benchmark creativo actualizado"))
    s.append(P("Con Adobe Firefly y Higgsfield anadidos:"))
    bench_rows = [
        ["Compania", "Capa(s)", "Lo que tomamos como vara"],
        ["Adobe Firefly", "13, 16",
         "Output commercial-safe by training data (Adobe Stock + licensed). Estandar legal/IP que ningun competidor open-source iguala. Modelo de creditos."],
        ["Adobe Creative Cloud (Photoshop/Illustrator/Premiere)", "13, 11",
         "Edicion pro (no solo generacion). Workflows compuestos, no one-shot."],
        ["Higgsfield Soul", "13",
         "Character consistency entre escenas (un unico “modelo virtual” para una marca)."],
        ["Higgsfield DoP", "13",
         "Motion ads cinematograficos image-to-video, listos para social."],
        ["Canva", "13, 11", "Plantillas que no se ven a plantilla, accesibles a no-disenadores."],
        ["Kittl", "13", "Assets de marca para small business (logos, packaging, type-driven)."],
        ["Runway", "13", "Video IA con control granular, timeline, edicion."],
        ["Ideogram", "13", "Texto legible dentro de imagen (logos, posters con tipografia)."],
        ["Midjourney", "13", "Estetica distintiva. <b>No commercial-safe by default</b> — riesgo IP."],
        ["ElevenLabs", "13, 4", "Voz; modelo de creditos transparente."],
    ]
    s.append(small_table(para_rows(bench_rows),
                         col_widths=[5.5*cm, 1.6*cm, 9.9*cm]))
    s.append(C(
        "Aplicacion operativa: cada PR de creative engine en Dona declara que benchmark le aplica. "
        "Ejemplo: una iniciativa “campana editorial regulada” debe medirse vs Adobe Firefly (legal/IP), no vs Midjourney."
    ))

    # ── 5. Workflows premium para Dona ──────────────────────────────────
    s.append(H1("5. Workflows premium sugeridos (diseno, no implementacion)"))
    s.append(P(
        "Bajo Tool Intelligence Layer, hipotesis a validar en Phase 3, sin codigo todavia:"
    ))
    wf_rows = [
        ["Workflow", "Tools (orden de invocacion)", "Capas", "Tier"],
        ["Asset de marca regulado (legal, salud, finanzas)",
         "Adobe Firefly Services REST → Photoshop API (composicion) → entrega",
         "13, 16", "Pro/Enterprise"],
        ["Motion ad de producto (5–15s)",
         "Imagen base (Gemini/Firefly) → Higgsfield DoP REST → entrega",
         "13", "Premium+"],
        ["Campana visual con character consistency",
         "Higgsfield Soul (entrenamiento) → 8–12 imagenes con mismo modelo → entrega",
         "13", "Pro"],
        ["Editorial / social pack (10 imagenes + 3 motion + 1 copy bundle)",
         "Firefly REST + Higgsfield DoP + Claude Sonnet 4.6 (copy) → preview en dashboard → confirmar_ → entrega",
         "5, 8, 13", "Pro/Enterprise"],
        ["Logo / type-driven asset",
         "Ideogram o Adobe Illustrator API (via Adobe Firefly Services si disponible)",
         "13", "Premium+"],
    ]
    s.append(small_table(para_rows(wf_rows),
                         col_widths=[4.6*cm, 7.4*cm, 1.8*cm, 3.2*cm]))

    s.append(P("Cada workflow:"))
    s.extend(bullets([
        "Pasa por el Approval Layer (preparar_/confirmar_).",
        "Cobra creditos del cap del Workspace o del sub-agente publico segun el caso.",
        "Deja audit log con tools usadas, costo real, output URL.",
        "Tiene fallback documentado (si Firefly cae → Gemini; si Higgsfield cae → Veo directo).",
    ]))

    # ── 6. Riesgos y dependencias ───────────────────────────────────────
    s.append(H1("6. Riesgos y dependencias anadidas"))
    riesgos_rows = [
        ["Riesgo", "Mitigacion"],
        ["Confusion tecnica “X integra con Claude” → asumir MCP en backend",
         "Documento tecnico aclara: la ruta para Dona es REST API, no MCP. (Seccion 3.3)"],
        ["Pricing enterprise Firefly (~$1k/mes minimo) sin volumen suficiente",
         "PoC primero; integracion solo cuando haya N Workspaces Pro pagantes que justifiquen el contrato."],
        ["TOS comerciales de Higgsfield no garantizan commercial-safe",
         "Revision legal antes de cualquier campana pagante; en su defecto, quedan como tools para preview/borrador, no para entrega final."],
        ["Lock-in en un proveedor creativo unico",
         "Tool Intelligence Layer obliga a tener fallback documentado por workflow."],
        ["Sub-agente publico accede a tools premium sin owner saber",
         "Approval Layer + cap por canal; tools premium solo invocables por owner Dona."],
    ]
    s.append(small_table(para_rows(riesgos_rows), col_widths=[7.5*cm, 9.5*cm]))

    # ── 7. Decisiones bloqueantes nuevas ────────────────────────────────
    s.append(H1("7. Decisiones bloqueantes nuevas"))
    s.append(P("Adicionales a las de v2:"))
    s.extend(bullets([
        "<b>PR1 Variante A vs B</b> — antes de empezar Phase 0.",
        "<b>Acceso a Adobe Firefly Services</b>: ¿levantamos contrato enterprise (~$1k/mes minimo) o esperamos a tener N Workspaces Pro pagantes? Recomendacion: PoC via cuenta CC individual primero; contrato cuando haya ROI.",
        "<b>Higgsfield TOS comerciales</b>: revision legal del owner antes de Phase 3. Si el output no es commercial-safe garantizado, tier Pro no puede prometer entrega final con Higgsfield.",
        "<b>Cuenta Adobe del owner para PoC</b>: necesaria solo para PoC inicial (cuenta CC normal alcanza).",
        "<b>Provider gateway o REST directo</b>: para Higgsfield, ¿usamos Higgsfield Cloud REST oficial o passthrough via WaveSpeed/Unifically? Cloud REST es mas limpio; passthrough da pricing por uso sin compromiso.",
    ]))

    # ── 8. Proximo paso ─────────────────────────────────────────────────
    s.append(H1("8. Proximo paso"))
    s.append(P("Pendientes para desbloquear Phase 0:"))
    s.extend(bullets([
        "Confirma <b>PR1 Variante A o B</b>.",
        "Confirma <b>wording del disclaimer</b> (PR4).",
        "Autoriza <b>inventario legacy</b> (docs/legacy-inventory.md).",
        "Confirma si abrimos <b>fichas formales</b> en docs/tools/ para Adobe Firefly y Higgsfield (puedo redactarlas como documentos de planificacion, sin codigo).",
    ]))
    s.append(P("No habra edits hasta autorizacion por PR."))

    # ── Sources ─────────────────────────────────────────────────────────
    s.append(H1("Sources"))
    s.extend(bullets([
        "Adobe for creativity: a new way to create with Adobe, now in Claude — Adobe Blog. https://blog.adobe.com/en/publish/2026/04/28/adobe-for-creativity-connector",
        "Adobe Ushers in a New Era of Creativity with New Creative Agent — Adobe News. https://news.adobe.com/news/2026/04/adobe-new-creative-agent",
        "Exclusive: Adobe brings agentic AI to Firefly, with Claude next — Axios. https://www.axios.com/2026/04/27/adobe-agentic-ai-firefly-claude",
        "Anthropic expands Claude with Adobe, Blender and Autodesk integrations — FoneArena. https://www.fonearena.com/blog/481271/anthropic-claude-adobe-blender-autodesk-integration.html",
        "Adobe Firefly API Pricing 2026 — SudoMock. https://sudomock.com/blog/adobe-firefly-api-pricing-2026",
        "Higgsfield MCP — AI Image &amp; Video Generation for Any Agent. https://higgsfield.ai/mcp",
        "Higgsfield Cloud API. https://cloud.higgsfield.ai/",
        "Higgsfield AI pricing. https://higgsfield.ai/pricing",
        "Higgsfield DoP Image to Video API — WaveSpeedAI. https://wavespeed.ai/docs/docs-api/higgsfield/higgsfield-dop-image-to-video",
        "Higgsfield DoP API | Cinematic AI Video API — Unifically. https://unifically.com/models/higgsfield-dop",
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
        title="Dona — Plan v2.1 (ajustes pre-implementacion)",
        author="Plan generado a partir de la conversacion con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch, "Dona — Plan v2.1 · 2026-04-30")
        canvas.drawRightString(LETTER[0] - 0.7*inch, 0.4*inch, f"Pagina {doc.page}")
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
