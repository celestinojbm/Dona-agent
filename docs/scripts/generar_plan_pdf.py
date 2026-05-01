"""
Genera Plan_Dona_Refinado_v1_2026-04-29.pdf con el plan refinado entregado en chat.

Solo se ejecuta una vez para producir el PDF descargable.
No toca ningún archivo del proyecto. No envía datos a internet.
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

OUTPUT = r"C:\Users\celes\Dona-agent\Plan_Dona_Refinado_v1_2026-04-29.pdf"

# ── Estilos ────────────────────────────────────────────────────────────────
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
    name="BodyTight", parent=styles["BodyText"], fontSize=9.5, leading=13,
    alignment=TA_LEFT, spaceAfter=2, textColor=colors.HexColor("#222222"),
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
    name="Caption", parent=styles["Body"], fontSize=8.5, leading=11,
    textColor=colors.HexColor("#6b7280"), spaceAfter=10,
))


def H1(t): return Paragraph(t, styles["H1"])
def H2(t): return Paragraph(t, styles["H2"])
def H3(t): return Paragraph(t, styles["H3"])
def P(t): return Paragraph(t, styles["Body"])
def PT(t): return Paragraph(t, styles["BodyTight"])
def C(t): return Paragraph(t, styles["Caption"])
def CODE(t): return Paragraph(t.replace(" ", "&nbsp;").replace("\n", "<br/>"), styles["CodeBox"])


def bullets(items):
    out = []
    for it in items:
        out.append(Paragraph("&bull; " + it, styles["BulletDona"]))
    return out


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


# ── Contenido ──────────────────────────────────────────────────────────────

def build_story():
    s = []

    # Portada
    s.append(Paragraph("Dona — Plan Refinado v1", styles["TitleBig"]))
    s.append(Paragraph(
        "Fecha: 2026-04-29 &nbsp;·&nbsp; HEAD: 5b7d42d &nbsp;·&nbsp; Estado: planificación, no implementación &nbsp;·&nbsp; "
        "Modo: solo lectura.",
        styles["MetaTop"],
    ))

    s.append(P(
        "Este documento es la versión refinada del plan de trabajo para Dona. Incorpora correcciones del owner: "
        "Workspace/Business como raíz; identidades email + teléfono vinculadas; monetización híbrida "
        "(suscripción mensual con créditos incluidos + top-ups); Stripe como única fuente de verdad en backend Python; "
        "posicionamiento de Dona como acelerador / orquestador autónomo premium para negocios "
        "(internamente: AI workforce / orchestration layer; nunca AGI público); "
        "cifrado campo-a-campo preservando índices y reporting; sub-agente público aislado por canal/Workspace."
    ))

    # ── A. Arquitectura objetivo v1 ───────────────────────────────────────
    s.append(H1("A. Arquitectura objetivo v1"))

    s.append(H2("A.1 Vista de capas"))
    diagrama = (
        "+-----------------------------------------------------------------+\n"
        "|                         DASHBOARD WEB                           |\n"
        "|   (Next.js — Owner UI: iniciativas, autorizaciones, métricas)    |\n"
        "+-----------------------------+-----------------------------------+\n"
        "                              | NextAuth magic-link + OTP WhatsApp\n"
        "                              v\n"
        "+-----------------------------------------------------------------+\n"
        "|                  IDENTITY & WORKSPACE LAYER                      |\n"
        "|   Workspace = unidad raíz (1 negocio). Identidades vinculadas:   |\n"
        "|   - email (login web), telefono_owner (WhatsApp privado),        |\n"
        "|     stripe_customer_id, oauth grants.                            |\n"
        "|   Roles dentro del workspace: owner / member (futuro) / agent.   |\n"
        "+-------------+-----------------------------+-----------------------+\n"
        "              |                             |\n"
        "              v                             v\n"
        "+--------------------------+  +--------------------------------+\n"
        "| SUBSCRIPTION + CREDITS   |  |       AUDIT LOG                |\n"
        "| Plan + créditos incluidos|  | (workspace, actor, accion,     |\n"
        "| /mes + top-ups; sync por |  |  recurso, antes/después,       |\n"
        "| webhook Stripe (única    |  |  ip, ts) — append-only.        |\n"
        "| fuente: backend Python). |  +--------------------------------+\n"
        "+-------------+------------+\n"
        "              |\n"
        "              v\n"
        "+-----------------------------------------------------------------+\n"
        "|                      ORCHESTRATOR (core)                         |\n"
        "|   State-machine: diagnostico -> plan -> preparar -> autorizar -> |\n"
        "|   ejecutar -> medir -> optimizar.                                 |\n"
        "|   Persiste Iniciativa(workspace, tipo, estado, pasos, costos).   |\n"
        "+----+-------------------------------------------+----------------+\n"
        "     |                                           |\n"
        "     v                                           v\n"
        "+--------------------+                  +-------------------------+\n"
        "| OWNER DONA         |                  | PUBLIC SUB-AGENT        |\n"
        "| Canal: telefono    |                  | Canal: 1..N numeros del |\n"
        "| del owner. Acceso  |                  | negocio (Whapi/Meta)    |\n"
        "| total al workspace |                  | registrados en          |\n"
        "| OAuth, orquestador |                  | Workspace. Aislado:     |\n"
        "| tools premium,     |                  | persona, prompt y       |\n"
        "| autoriza acciones  |                  | knowledge propios; NO   |\n"
        "| publicas. Persona  |                  | accede a memoria        |\n"
        "| ejecutiva, lider   |                  | privada del owner; cap  |\n"
        "| de operaciones.    |                  | de creditos separado.   |\n"
        "+----------+---------+                  +------------+------------+\n"
        "           |                                          |\n"
        "           v                                          v\n"
        "+-----------------------------------------------------------------+\n"
        "|        PERMISSIONS / APPROVAL LAYER (preparar_/confirmar_)       |\n"
        "|  Toda accion con efecto externo o costo pasa por ApprovalGate:  |\n"
        "|  - quien autoriza (siempre el owner, nunca el sub-agent publico) |\n"
        "|  - canal de autorizacion (WhatsApp del owner o dashboard)         |\n"
        "|  - TTL del preview (15 min default)                                |\n"
        "|  - registro en audit log                                           |\n"
        "+-------------+---------------------------------------+-------------+\n"
        "              |                                       |\n"
        "              v                                       v\n"
        "+--------------------------+                  +------------------------+\n"
        "| JOBS / WORKERS            |                 |   TOOLS                |\n"
        "| arq + Redis (web + worker |                 | preparar_imagen,       |\n"
        "| Render); APScheduler en   |                 | confirmar_campana,     |\n"
        "| worker exclusivo.         |                 | preparar_landing, etc. |\n"
        "| Idempotencia por job_id.  |                 +------------------------+\n"
        "+--------------------------+\n"
    )
    s.append(CODE(diagrama))

    # A.2 Componentes
    s.append(H2("A.2 Componentes"))

    s.append(H3("A.2.1 Identity / Workspace"))
    s.extend(bullets([
        "Workspace es la raíz: un negocio = un workspace.",
        "Tablas: <b>workspaces</b>, <b>workspace_identities</b> (tipo: email | phone_owner | stripe_customer | oauth_grant), <b>workspace_members</b> (rol).",
        "Vinculación email&harr;teléfono por <b>doble verificación</b>: magic-link al email + OTP por WhatsApp al telefono_owner. Una identidad solo se vincula tras ambos retos.",
        "Cada request resuelve workspace_id antes de cualquier acción; no hay rutas globales sin workspace.",
    ]))

    s.append(H3("A.2.2 Subscription + Credits"))
    s.extend(bullets([
        "Plan en backend (<b>free | premium | pro | enterprise</b>) con campos: creditos_incluidos_mes, tools_desbloqueadas, cap_sub_agentes_publicos, cap_canales.",
        "Sincronización <b>única</b> vía webhook Stripe en backend Python:",
        "&nbsp;&nbsp;&nbsp;&nbsp;customer.subscription.created/updated/deleted → cambia plan del workspace.",
        "&nbsp;&nbsp;&nbsp;&nbsp;invoice.payment_succeeded → renueva créditos incluidos del mes.",
        "&nbsp;&nbsp;&nbsp;&nbsp;checkout.session.completed (mode=payment) → top-up (créditos extra).",
        "Landing redirige a Stripe Checkout y muestra estado, pero <b>no procesa efectos</b> (no acredita ni notifica WhatsApp).",
        "Cap de créditos por sub-agente público para limitar abuso desde canales públicos.",
    ]))

    s.append(H3("A.2.3 Owner Dona (privado)"))
    s.extend(bullets([
        "Atado al telefono_owner del workspace.",
        "Acceso total al estado del workspace, OAuth tokens, audit log, orquestador.",
        "Puede iniciar iniciativas, autorizar/rechazar previews, configurar el sub-agente público.",
        "Persona “líder de operaciones” — directa, premium, en español; nunca “asistente personal”.",
    ]))

    s.append(H3("A.2.4 Public customer-facing sub-agent (clave para la visión)"))
    s.extend(bullets([
        "<b>Aislamiento estricto</b>: cada workspace puede tener N canales públicos (números WhatsApp Meta/Whapi del negocio). Cada canal tiene su propio prompt, knowledge base, FAQ, persona, idioma, horario y cap de créditos.",
        "Tablas: <b>public_agents</b>(workspace_id, canal_id, persona_prompt, knowledge_ref, creditos_cap_mes, creditos_consumidos_mes, activo), <b>public_channels</b>(workspace_id, provider, phone_number_id, credenciales_cifradas).",
        "Routing del webhook entrante: provider + phone_number_id → workspace_id + public_agent_id. Si no matchea, va al canal owner (default).",
        "<b>Permisos restringidos</b>: solo lee public_agents.knowledge_ref y business.cliente_publico; <b>no</b> accede a Mensaje privado del owner ni a OAuth tokens.",
        "Puede capturar leads, agendar (si el workspace lo habilita), responder FAQ, escalar al owner.",
        "<b>No</b> puede ejecutar confirmar_* (campañas, pagos, mass mailings) — solo el owner autoriza.",
        "Cualquier acción que cobra créditos descuenta del cap del sub-agente, no del cap general del workspace.",
        "TCPA por canal: cada cliente final del workspace puede hacer STOP y queda registrado en tcpa_optouts(workspace_id, canal_id, telefono_cliente).",
        "Auditoría obligatoria: cada conversación pública genera fila en audit_log con tag <i>public_agent</i>.",
    ]))

    s.append(H3("A.2.5 Orchestrator"))
    s.extend(bullets([
        "Módulo nuevo agent/orchestrator/.",
        "Modelo Iniciativa(id, workspace_id, tipo, estado, plan_json, costos_estimados, costos_reales, pasos[], creado_por, autorizada_por, ts).",
        "Estados: borrador → diagnostico → plan_propuesto → autorizando → ejecutando → midiendo → optimizando → archivada/cancelada.",
        "Cada paso es un Job arq con preparar_/confirmar_ y autorización del owner.",
    ]))

    s.append(H3("A.2.6 Permissions / Approval layer"))
    s.extend(bullets([
        "Decorador / dependency requiere_aprobacion(scope, costo, ttl) que cualquier confirmar_* cruza.",
        "Aprobaciones expresadas en dashboard (botón) o WhatsApp del owner (confirmar/cancelar).",
        "Audit log obligatorio en cada aprobación con before/after.",
        "Sub-agente público nunca dispara aprobación; siempre escala al owner.",
    ]))

    s.append(H3("A.2.7 Jobs / Workers"))
    s.extend(bullets([
        "arq con Redis. Web service solo recibe webhooks, dispara encolado.",
        "Worker dedicado en Render (type: worker).",
        "APScheduler reside <b>solo</b> en worker (no en web) → permite escalar gunicorn web a 2+ workers en el futuro.",
        "Idempotencia por (workspace_id, tipo, dedup_key).",
    ]))

    s.append(H3("A.2.8 Audit log"))
    s.extend(bullets([
        "Tabla audit_log(id, workspace_id, actor_tipo, actor_id, accion, recurso_tipo, recurso_id, antes_json, despues_json, ip, ua, ts) append-only.",
        "Retención mínima 12 meses (CCPA/CPRA + due diligence).",
        "Owner puede exportar su audit log via dashboard (cumplimiento de derecho de acceso).",
    ]))

    s.append(H3("A.2.9 Dashboard (web premium)"))
    s.extend(bullets([
        "Vistas: Iniciativas en curso, Autorizaciones pendientes, Assets generados, Conexiones (OAuth), Sub-agentes públicos (configuración + métricas + cap de créditos), Plan + créditos, Audit log, Privacidad (export/delete).",
        "NextAuth con magic-link email; sesión bound a workspace_id resuelto en cada request.",
    ]))

    # A.3 Cifrado
    s.append(H2("A.3 Modelo de cifrado campo-a-campo"))
    s.append(P(
        "Política: <b>no cifrar todo</b>. Cifrar solo lo que es PII pesado o secreto, manteniendo índices, búsqueda y reporting funcionales."
    ))

    cifrado_rows = [
        ["Campo", "Estrategia", "Razón"],
        ["Mensaje.content (WhatsApp privado del owner)",
         "Fernet random + columna keywords_hash[] (HMAC) opcional para búsqueda futura",
         "PII alto, raramente se busca exact-match"],
        ["Mensaje.content (sub-agente público)",
         "Fernet random",
         "Igual al anterior"],
        ["cliente.telefono (CRM público)",
         "HMAC-SHA256 determinístico (telefono_hash) + Fernet random (telefono_cifrado)",
         "Exact-match lookup; valor solo se descifra al mostrar"],
        ["cliente.email", "Igual al teléfono", "Mismo patrón"],
        ["cliente.nombre", "Fernet random", "Display only"],
        ["Venta.monto, Gasto.monto, fechas, categorías",
         "Texto plano",
         "Reporting / agregaciones críticas"],
        ["OAuth tokens (access/refresh)",
         "Fernet (ya implementado)",
         "Secreto de proveedor"],
        ["WebAgent cookies", "Fernet (ya implementado)", "Secreto de sesión"],
        ["public_channels.credenciales_cifradas",
         "Fernet random", "Tokens Meta/Whapi por canal"],
        ["Workspace.telefono_owner",
         "Texto plano + índice", "Lookup primario del webhook"],
        ["audit_log.antes_json / despues_json",
         "Fernet random si contiene PII; metadata estructural plana",
         "Auditoría legible para el owner"],
        ["Datos del onboarding privado (proyectos, notas)",
         "Fernet random", "PII alto, display only"],
    ]
    rows_para = [[Paragraph(c, styles["BodyTight"]) for c in r] for r in cifrado_rows]
    s.append(small_table(rows_para, col_widths=[5.2*cm, 6.2*cm, 5.6*cm]))
    s.append(C("Reglas de migración: clave versionada (v1, v2…) — descifrar acepta múltiples; cifrar usa la actual. "
               "Helper hashed_lookup(secret, valor) para campos determinísticos. Tests verifican estabilidad del HMAC y rotación."))

    # ── B. Backlog ─────────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("B. Backlog ejecutable"))
    s.append(C("Convención: <b>Conf</b> = requiere confirmación humana antes de empezar."))

    # Phase 0
    s.append(H2("Phase 0 — Security blockers"))
    s.append(C("No se construye feature hasta cerrar esto."))
    phase0 = [
        ("T0.1 — Eliminar autenticación con password fake en landing",
         "Cerrar el ATO trivial; usuario solo entra si controla el email + (opcional) WhatsApp.",
         "landing/auth.ts; landing/app/login/page.tsx; landing/app/api/auth/[...nextauth]/route.ts; nuevas rutas API para magic-link callback. landing/AGENTS.md recordatorio: revisar node_modules/next/dist/docs/ antes de cambiar APIs de Next.",
         "Bloquear logins existentes durante el cambio; flujos de NextAuth EmailProvider requieren proveedor SMTP configurado.",
         "landing/tests/auth.test.ts — magic-link rechaza tokens expirados; login solo con email no autoriza sin confirmar link; sesión incluye workspace_id y plan correctos.",
         "Campo password desaparece; login pide email; magic-link entra al dashboard; tokens OTP de 15 min; rate-limit 5/h por email; pruebas pasan.",
         "Sí — decidir proveedor SMTP (Resend/Postmark/SES) antes."),
        ("T0.2 — Stripe webhook: firma obligatoria en producción",
         "Rechazar 400 si STRIPE_WEBHOOK_SECRET falta y ENVIRONMENT=production.",
         "agent/billing.py:366-384; agent/main.py:2112-2151; tests/test_billing.py.",
         "Si la env var está mal en Render, todo el flujo de créditos falla en vivo.",
         "Webhook con env=production y sin secret → 500 al startup (no a runtime); con secret y firma inválida → 400; con firma válida → 200; idempotencia por stripe_session_id.",
         "En prod no hay path que acepte payload sin firma; logs muestran rechazo explícito.",
         "No"),
        ("T0.3 — Meta webhook: firma obligatoria en producción",
         "Rechazar payloads sin META_APP_SECRET en prod.",
         "agent/providers/meta.py:131-150; tests/test_providers.py.",
         "Si las env vars de Meta no están en Render, webhooks rebotan y mensajes se pierden.",
         "env=production sin app_secret → falla startup; con app_secret y firma inválida → array vacío y log; firma válida → mensajes parseados.",
         "Prod no tiene path “permitir sin firma”.",
         "No"),
        ("T0.4 — INBOUND_WEBHOOK_SECRET sin fallback en producción",
         "Eliminar fallbacks derivados (de ADMIN_TOKEN o literal); en prod debe exigir env var.",
         "agent/inbound_tokens.py:30-42; tests/test_inbound_tokens.py.",
         "Tokens emitidos previamente con secret derivado quedan inválidos → notificar al owner antes (rotación).",
         "Prod sin secret → RuntimeError; secret válido → token verifica; cambio de secret → tokens previos fallan.",
         "Prod sin secret no arranca.",
         "No"),
        ("T0.5 — Eliminar número personal hardcodeado en /voice/reenviar",
         "Mover +14076936023 a env var (VOICE_FORWARD_NUMBER); si no existe, devolver 404.",
         "agent/main.py:2165-2172.",
         "Ninguno.",
         "Con env var → TwiML correcto; sin env var → 404; admin auth opcional.",
         "Ningún número personal aparece en código.",
         "No"),
        ("T0.6 — Disclaimer legal del landing alineado con realidad",
         "Quitar afirmaciones falsas (“encriptación end-to-end”, “no compartimos datos con terceros”) hasta que sean ciertas.",
         "landing/app/page.tsx:99 (whyDona.cards), :131 (faq.items), :142 (footer disclaimer); mismas claves en bloque EN.",
         "Marketing pierde un selling point hasta que el cifrado universal esté listo (Phase 1).",
         "Visual review; lint de strings prohibidas (end-to-end, extremo a extremo) en CI futuro.",
         "Ninguna afirmación de seguridad sin sustento técnico.",
         "Sí — decidir wording exacto."),
        ("T0.7 — Audit dependencies del legacy (no borrar, mapear)",
         "Dejar inventario de qué usa start.sh, enhanced/, mounts de docker-compose.yml, migration.py. No tocar.",
         "Documento de salida en docs/legacy-inventory.md (creación pendiente de autorización).",
         "Ninguno (lectura sola).",
         "N/A.",
         "Lista con: archivo → quién lo importa, quién lo invoca en runtime, qué env vars depende, recomendación (mantener / mover / deprecar) sin borrar.",
         "Sí — autorización para crear el documento."),
    ]
    for t in phase0:
        s.append(task_block(*t))

    # Phase 1
    s.append(H2("Phase 1 — Identity + billing foundation"))
    phase1 = [
        ("T1.1 — Modelo Workspace + identidades vinculadas",
         "Crear tablas workspaces, workspace_identities, workspace_members; resolver workspace_id en todo flujo.",
         "agent/memory.py (modelos); agent/identity/ (módulo nuevo); alembic/versions/002_workspaces.py; tests/test_identity.py.",
         "Migración de usuarios existentes (cada teléfono actual = un workspace nuevo).",
         "Crear workspace; vincular email; vincular teléfono con OTP; resolver workspace por teléfono / por email / por stripe_customer_id; conflicto (mismo email en dos workspaces) bloqueado.",
         "100% del código que hoy hace where telefono == X se sustituye por resolución → workspace_id. Cero llamadas a tools sin workspace_id.",
         "Sí — decidir nombre del identificador raíz (workspace / business / cuenta)."),
        ("T1.2 — Magic-link email + OTP WhatsApp",
         "Vinculación de identidades requiere ambos challenges.",
         "landing/auth.ts; landing/app/api/auth/[...]; agent/identity/otp.py; agent/main.py (POST /identity/verify_otp); tests/test_identity_otp.py.",
         "Phishing si magic-link no expira; UX adicional para vincular.",
         "Magic-link expira a 15 min; OTP de 6 dígitos máx 5 intentos expira 10 min; vinculación sin ambos retos rechaza.",
         "Login web + WhatsApp del mismo workspace coordinados.",
         "Depende de T0.1 (proveedor SMTP)."),
        ("T1.3 — Migrar billing a fuente única backend Python",
         "Deprecar landing/app/api/webhook/route.ts (procesamiento). Landing solo crea Checkout y redirige; backend Python procesa todo.",
         "landing/app/api/webhook/route.ts (vaciar a 410 Gone con instrucción de redirigir); agent/billing.py (handlers de subscription events); agent/main.py (sigue siendo /webhook/stripe); tests/test_billing.py.",
         "Si Stripe Dashboard tiene endpoint del landing configurado, hay que actualizarlo antes del deploy.",
         "customer.subscription.created → workspace.plan actualizado; invoice.payment_succeeded → créditos incluidos renovados; customer.subscription.deleted → plan free; checkout.session.completed mode=payment → top-up; doble entrega no duplica.",
         "Solo el endpoint backend procesa eventos; el del landing devuelve 410 con mensaje.",
         "Sí — coordinar cambio de URL en Stripe Dashboard."),
        ("T1.4 — Plan + créditos híbrido",
         "Tabla plans(codigo, creditos_incluidos_mes, tools_desbloqueadas[], cap_sub_agentes, cap_canales, precio_centavos, stripe_price_id). Asignación de créditos al renovar.",
         "agent/memory.py; agent/billing.py; alembic/versions/003_plans.py; tests/test_plans.py.",
         "Corner case de upgrade/downgrade mid-cycle.",
         "Upgrade prorratea créditos; downgrade no quita los ya consumidos; renovación mensual idempotente por (workspace_id, periodo).",
         "Créditos se renuevan automáticamente; tools premium gateadas por plan.",
         "Sí — definir matriz exacta plan↔tools↔créditos."),
        ("T1.5 — Cifrado campo-a-campo (modelo del A.3)",
         "Implementar Fernet versionado + helpers HMAC para campos determinísticos; migrar campos del A.3.",
         "agent/crypto.py (extender); agent/memory.py (decoradores/types); alembic/versions/004_encrypted_fields.py (agregar columnas _hash/_cifrado); tests/test_crypto_fields.py.",
         "Migración de datos existentes (mensajes del owner) requiere job batch; índices nuevos (HMAC) necesitan creación cuidadosa.",
         "Cifrar/descifrar con key v1 y v2; HMAC determinístico estable; búsqueda por cliente.telefono_hash retorna mismo registro post-cifrado.",
         "PII identificada en A.3 está cifrada en DB; queries que dependen de ella siguen funcionando.",
         "Sí — confirmar matriz del A.3."),
        ("T1.6 — Audit log append-only",
         "Tabla + helper audit(workspace_id, actor, accion, recurso, antes, despues) invocado por confirmar_*, login, cambios de plan, vinculación de identidades.",
         "agent/memory.py; agent/audit.py (nuevo); alembic/versions/005_audit_log.py; tests/test_audit.py.",
         "Volumen — proyectar retención y particionado.",
         "Insertar entry no permite update/delete (constraint o trigger); query por workspace_id + rango fechas; export funciona.",
         "Cada acción crítica deja fila; export para CCPA disponible.",
         "No"),
    ]
    for t in phase1:
        s.append(task_block(*t))

    # Phase 2
    s.append(H2("Phase 2 — Premium product / Dashboard"))
    phase2 = [
        ("T2.1 — Dashboard: Iniciativas + Autorizaciones",
         "Vistas reales en /dashboard/iniciativas y /dashboard/aprobaciones.",
         "landing/app/dashboard/iniciativas/page.tsx; landing/app/dashboard/aprobaciones/page.tsx; API routes que llaman al backend; landing/lib/api.ts (cliente firmado por sesión NextAuth).",
         "landing/AGENTS.md exige consultar node_modules/next/dist/docs/ antes de tocar APIs de Next — incorporar al checklist por PR.",
         "Playwright/Vitest — owner ve solo iniciativas de su workspace; aprobar dispara confirmar_*; cancelar dispara cancelar_*.",
         "Owner puede aprobar/cancelar desde web sin necesidad de WhatsApp.",
         "No"),
        ("T2.2 — Dashboard: Conexiones OAuth",
         "Iniciar/desconectar OAuth de Gmail, Calendar, Drive, Meta Business, Google Ads desde el dashboard.",
         "landing/app/dashboard/conexiones/page.tsx; backend agent/main.py (extender /auth/google/login con state firmado que incluya workspace_id y return_to=dashboard).",
         "CSRF en OAuth callback.",
         "State firmado con HMAC + nonce; callback verifica state; redirige al dashboard.",
         "Owner conecta Gmail desde el dashboard y aparece “conectado”.",
         "No"),
        ("T2.3 — Dashboard: Plan + créditos",
         "Vista con plan vigente, créditos restantes, historial de transacciones, link a Customer Portal de Stripe.",
         "landing/app/dashboard/billing/page.tsx; API que llama a agent/billing.py:obtener_resumen filtrado por workspace.",
         "Filtrar correctamente por workspace_id.",
         "Owner solo ve sus créditos; llamada cross-workspace rechazada.",
         "Owner ve y administra plan sin escribirle a Dona.",
         "No"),
        ("T2.4 — Dashboard: Sub-agentes públicos (configuración)",
         "CRUD de canales públicos + sub-agentes; persona, prompt, knowledge, cap de créditos, horarios, idioma.",
         "landing/app/dashboard/sub-agentes/page.tsx; agent/public_agents/ (módulo nuevo); agent/memory.py (public_agents, public_channels); alembic.",
         "Prompt injection desde el owner que comprometa al sub-agente; aislamiento estricto del knowledge.",
         "Crear canal Whapi; webhook entrante a ese número rutea al sub-agente correcto; sub-agente NO ve mensajes del owner; cap de créditos detiene generaciones cuando se agota.",
         "Owner configura un sub-agente para su negocio, conecta un número, prueba conversación, ve métricas.",
         "Sí — confirmar diseño del knowledge base por canal (vector store por workspace, namespace public:{canal_id})."),
        ("T2.5 — Dashboard: Privacidad (CCPA real)",
         "Export JSON descargable + delete real (soft 30 días, hard después) con verificación OTP doble.",
         "agent/privacy.py (nuevo); agent/main.py (reemplazar handlers manuales actuales); landing/app/dashboard/privacidad/page.tsx; alembic (deletion_requests).",
         "Borrado afecta integridad referencial; coordinar con audit log (que sobrevive 30 días anónimos).",
         "Export retorna todos los datos del workspace en JSON estructurado; delete soft enmascara PII; delete hard 30 días después purga; idempotencia.",
         "Cumple plazo 45 días CCPA con UX self-service.",
         "Sí — decidir política de retención del audit log post-delete."),
        ("T2.6 — Reposicionamiento producto",
         "Prompts, copy del landing, dashboard, mensajes proactivos describen Dona como acelerador autónomo para negocios, no asistente personal.",
         "agent/brain.py (system prompts en :1308, :3205 y otros); landing/app/page.tsx (i18n.ES y i18n.EN: hero, capabilities, whyDona, FAQ, footer disclaimer); agent/onboarding.py; agent/comandos_info.py (texto de ayuda); agent/legal_pages.py.",
         "Prompt regression — re-validar tests de brain.py. Prohibir uso público de “AGI” / “AI workforce” en copy externo.",
         "Snapshot tests del system prompt; lint de strings prohibidas (asistente personal, personal assistant, AGI) en landing/app/, agent/brain.py, agent/legal_pages.py.",
         "Copy externo posiciona orquestación; copy interno puede usar “AI workforce” en docs internos.",
         "Sí — pasar copy nuevo en español/inglés antes de merge."),
    ]
    for t in phase2:
        s.append(task_block(*t))

    # Phase 3
    s.append(H2("Phase 3 — Autonomous orchestration"))
    phase3 = [
        ("T3.1 — Módulo orchestrator base",
         "State-machine de iniciativas con persistencia.",
         "agent/orchestrator/__init__.py; agent/orchestrator/state.py; agent/orchestrator/iniciativa.py; agent/memory.py (modelo Iniciativa); alembic; tests/test_orchestrator.py.",
         "Complejidad — empezar con 1 tipo de iniciativa simple antes de generalizar.",
         "Transición válida entre estados; transición inválida rechazada; cancelación desde cualquier estado; reanudación tras restart (estado en DB, no en memoria).",
         "Una iniciativa fluye end-to-end.",
         "No"),
        ("T3.2 — Iniciativa: Diagnóstico de negocio",
         "Primera iniciativa lista — analiza estado del workspace (datos OAuth, mensajes, ventas) y produce reporte con oportunidades.",
         "agent/orchestrator/iniciativas/diagnostico.py; prompt en agent/brain.py; tests/test_diagnostico.py.",
         "Alucinaciones; usar Claude Sonnet 4.6 con grounding en datos reales.",
         "Diagnóstico con mock de datos genera reporte estructurado; sin datos pide vincular fuentes.",
         "Owner pide “diagnóstico” y recibe reporte con N oportunidades clasificadas por impacto.",
         "Sí — definir formato del reporte."),
        ("T3.3 — Iniciativa: Generación de assets de marca (imagen + copy)",
         "Orquesta preparar_imagen + copy + variantes; owner aprueba bundle.",
         "agent/orchestrator/iniciativas/assets_marca.py; integraciones existentes en agent/creativos/.",
         "Créditos altos por iniciativa — confirmar caps.",
         "Bundle preview con N variantes; aprobar/rechazar bundle entero o parcial.",
         "Owner pide “imágenes para mi campaña” y recibe set autorizable.",
         "No"),
        ("T3.4 — Iniciativa: Atención automatizada en sub-agente público",
         "Configura el sub-agente público para atender clientes finales con escalation al owner.",
         "agent/orchestrator/iniciativas/atencion_publica.py; agent/public_agents/runner.py; prompts.",
         "TCPA — el sub-agente solo responde a mensajes entrantes, nunca proactivos sin opt-in explícito del cliente final.",
         "Cliente escribe → sub-agente responde con FAQ; STOP → opt-out por canal; intento de mass mailing bloqueado.",
         "Workspace activa atención y un cliente final recibe respuesta correcta sin tocar al owner.",
         "Sí — diseñar flujo de escalation (cuándo al owner, cuándo no)."),
        ("T3.5 — Iniciativa: Campaña Meta Ads",
         "preparar_campana_meta_ads → preview budget/audiencia/creatives → confirmar_ → trackear KPIs.",
         "agent/orchestrator/iniciativas/campana_meta.py; agent/integrations/meta_ads.py (nuevo); env vars.",
         "Spend autorizado erróneamente; cap diario obligatorio en preview.",
         "Preview muestra budget máximo; confirmar requiere aprobación humana explícita; cap diario aplica.",
         "Owner lanza campaña pequeña en sandbox y ve métricas.",
         "Sí — Meta Business OAuth + cap default + sandbox account."),
    ]
    for t in phase3:
        s.append(task_block(*t))

    # Phase 4
    s.append(H2("Phase 4 — Scale + observability"))
    phase4 = [
        ("T4.1 — Render: web + worker separados",
         "Agregar render.yaml con dos servicios; JOBS_BACKEND=arq obligatorio en prod.",
         "render.yaml (nuevo); Dockerfile (sin cambios o Dockerfile.worker); docs internos.",
         "Doble billing en Render; coordinar APScheduler solo en worker.",
         "Smoke de encolar→worker procesa; web sin scheduler no dispara dobles.",
         "Jobs sobreviven restarts del web.",
         "Sí — autorización de costo Render."),
        ("T4.2 — Multi-worker gunicorn",
         "Escalar web a 2+ workers; APScheduler ya está en worker.",
         "Dockerfile (-w 2); agent/scheduler.py (no-op si proceso es web).",
         "Estado in-memory (dedupe, rate-limiter) duplicado — verificar que ya migró a Redis/DB.",
         "Stress test con N requests concurrentes; dedupe sigue funcionando cross-process.",
         "Web maneja 2x throughput.",
         "No"),
        ("T4.3 — Alembic real + autogenerate",
         "Snapshot del schema actual con --autogenerate; deprecar metadata.create_all() en runtime.",
         "alembic/versions/006_baseline_autogen.py; agent/main.py:lifespan (quitar inicializar_db directo, usar alembic).",
         "Divergencias entre schema runtime y autogenerate — comparar antes de aplicar.",
         "CI corre alembic upgrade head en DB vacía y compara con metadata actual.",
         "Rollback funciona; nuevas columnas pasan por revisión.",
         "Sí — pre-flight comparación."),
        ("T4.4 — Observabilidad",
         "Logs estructurados JSON, Sentry, alertas en jobs fallidos > N.",
         "agent/logging_config.py; agent/jobs/worker.py; env vars.",
         "PII en logs — sanitizar antes de loguear.",
         "Logger redacta texto de mensajes en nivel INFO; mantiene en DEBUG con flag.",
         "Dashboards básicos en Sentry/Render.",
         "Sí — proveedor (Sentry/Datadog/Logtail)."),
        ("T4.5 — CI: GitHub Actions",
         "pytest + lint + type-check + build de landing en cada PR.",
         ".github/workflows/ci.yml (nuevo).",
         "Secrets en CI — solo usar fixtures.",
         "Workflow corre verde en branch limpia.",
         "PR no merge sin CI verde.",
         "No"),
        ("T4.6 — Auditoría de legacy (decisión, no borrado)",
         "Con base en T0.7, decidir destino de start.sh, enhanced/, mounts del compose, migration.py. Decisiones individuales por cada uno.",
         "Depende de la decisión.",
         "Borrar algo en uso → tests + búsqueda de imports antes de cualquier remove.",
         "Full suite verde tras cada decisión aplicada.",
         "Cada item del legacy tiene status (mantener / mover / deprecar fase X).",
         "Sí — uno por uno."),
    ]
    for t in phase4:
        s.append(task_block(*t))

    # ── C. Tareas con confirmación ────────────────────────────────────────
    s.append(PageBreak())
    s.append(H1("C. Tareas que requieren confirmación humana"))
    conf_rows = [
        ["ID", "Por qué requiere confirmación"],
        ["T0.1", "Proveedor SMTP para magic-link"],
        ["T0.6", "Wording del nuevo disclaimer legal"],
        ["T0.7", "Autorización para crear docs/legacy-inventory.md"],
        ["T1.1", "Nombre del identificador raíz (workspace/business/cuenta)"],
        ["T1.3", "Actualizar URL del webhook en Stripe Dashboard sin downtime"],
        ["T1.4", "Matriz exacta plan ↔ tools ↔ créditos"],
        ["T1.5", "Confirmar matriz de cifrado del A.3"],
        ["T2.4", "Diseño del knowledge base por canal (vector store + namespace)"],
        ["T2.5", "Retención del audit log post-delete"],
        ["T2.6", "Copy nuevo ES/EN antes de merge"],
        ["T3.2", "Formato del reporte de diagnóstico"],
        ["T3.4", "Flujo de escalation owner ↔ sub-agente público"],
        ["T3.5", "Meta Business OAuth + sandbox + cap default"],
        ["T4.1", "Autorización de costo Render (worker separado)"],
        ["T4.3", "Pre-flight comparación schema runtime vs autogen"],
        ["T4.4", "Proveedor de observabilidad"],
        ["T4.6", "Decisiones individuales por cada item legacy"],
    ]
    rows_para = [[Paragraph(c, styles["BodyTight"]) for c in r] for r in conf_rows]
    s.append(small_table(rows_para, col_widths=[2.5*cm, 14.5*cm]))

    # ── D. Decisiones bloqueantes ────────────────────────────────────────
    s.append(H1("D. Decisiones que aún requieren confirmación (bloqueantes)"))
    decisiones = [
        "<b>Nombre del identificador raíz</b>: Workspace / Business / Cuenta. Propongo <i>Workspace</i> (consistente con SaaS B2B).",
        "<b>Proveedor SMTP</b> para magic-link: Resend / Postmark / SES / Mailgun.",
        "<b>Matriz plan ↔ tools ↔ créditos</b>: precios del plan (los $20/$40 actuales del landing son fijos o propuesta?), créditos incluidos/mes por plan, qué tools desbloquea cada plan (orchestrator avanzado solo Pro? sub-agentes públicos solo Premium+?), cap de sub-agentes públicos por plan, precios de top-ups (mantener paquetes 100/500/2000 actuales?).",
        "<b>Confirmar matriz de cifrado</b> propuesta en A.3 — qué campos quedan en plano, cuáles HMAC, cuáles Fernet random.",
        "<b>Política del audit log post-delete</b>: anonimizar (mantener registro con actor=anonimo) vs hard delete. CCPA permite mantener si se justifica como necesario para seguridad/legal.",
        "<b>Flujo de escalation owner ↔ sub-agente público</b>: ¿cuándo escala? (preguntas fuera de FAQ, intent de queja, monto de transacción > X, palabras clave configuradas).",
        "<b>Knowledge base del sub-agente público</b>: vector store gestionado (pgvector ya está en uso indirecto?) o externo (Zep/Pinecone)?",
        "<b>Reposicionamiento del copy</b>: ¿hay versión preliminar del nuevo wording? Hero, capabilities, FAQ, disclaimer.",
        "<b>Política de retención</b> de mensajes privados del owner y públicos del sub-agente: ¿iguales? CCPA permite “mientras la cuenta esté activa”, pero por sub-agente público puede convenir un límite (90/180 días) por costo + privacidad.",
        "<b>Sandbox de Meta Ads / Google Ads</b>: ¿tenemos cuenta sandbox para integration tests?",
        "<b>Stripe Customer Portal</b>: ¿lo activamos para que el owner administre cancelación, métodos de pago y facturas sin código nuestro?",
        "<b>Decisión sobre enhanced/</b>: tras T0.7 (inventario), ¿lo fusionamos en agent/ (sistemas como tipo de iniciativa) o lo mantenemos paralelo?",
        "<b>Decisión sobre landing/app/api/whatsapp-webhook/route.ts</b>: ¿lo deprecamos (Meta apunta directo al backend Render) o lo mantenemos como proxy con headers filtrados? Lo segundo es útil para CDN/WAF; lo primero es más simple.",
        "<b>TCPA por sub-agente público</b>: ¿quién es responsable legal (Dona o el negocio dueño del workspace)? Asumimos negocio, pero el ToS/Privacy del workspace tiene que reflejarlo. Requiere revisión legal antes de Phase 3 T3.4.",
    ]
    for d in decisiones:
        s.append(Paragraph("&bull; " + d, styles["BulletDona"]))

    s.append(Spacer(1, 18))
    s.append(C(
        "Próximo paso: respuesta a las decisiones bloqueantes (especialmente 1, 3, 4, 6, 7, 14) "
        "antes de empezar a implementar. No habrá edits hasta autorización explícita por tarea."
    ))

    return s


def task_block(titulo, objetivo, archivos, riesgo, tests, criterio, conf):
    """Render de una tarea como bloque KeepTogether."""
    rows = [
        ["Objetivo", objetivo],
        ["Archivos probables", archivos],
        ["Riesgo", riesgo],
        ["Tests requeridos", tests],
        ["Criterio de aceptación", criterio],
        ["Requiere confirmación", conf],
    ]
    rows_para = [[Paragraph("<b>" + r[0] + "</b>", styles["BodyTight"]),
                  Paragraph(r[1], styles["BodyTight"])] for r in rows]
    tbl = small_table(rows_para, col_widths=[4.0*cm, 13.0*cm], header=False)
    block = [
        Paragraph("<b>" + titulo + "</b>", styles["H3"]),
        tbl,
        Spacer(1, 6),
    ]
    return KeepTogether(block)


def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=LETTER,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        title="Dona — Plan Refinado v1",
        author="Plan generado a partir de la conversación con Claude",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(0.7*inch, 0.4*inch, "Dona — Plan Refinado v1 · 2026-04-29")
        canvas.drawRightString(
            LETTER[0] - 0.7*inch, 0.4*inch,
            f"Página {doc.page}",
        )
        canvas.restoreState()

    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"OK: {OUTPUT}")


if __name__ == "__main__":
    main()
