# agent/legal_pages.py — Páginas legales de Dona (Privacy Policy, ToS, DMCA)

"""
Páginas legales servidas desde el mismo dominio para cumplimiento regulatorio:

  - Privacy Policy (CCPA/CPRA + marco multi-estado de EEUU)
  - Terms of Service
  - Data deletion instructions

Las plantillas cumplen con:
  - CCPA/CPRA (California): derechos del consumidor, categorías de datos, opt-out.
  - VCDPA (Virginia), CPA (Colorado), CDPA (Connecticut), UCPA (Utah), TDPSA (Texas).
  - FTC Act Section 5: disclosure clara que Dona es un asistente de IA.
  - WhatsApp Business Solution Terms: opt-out accesible (STOP).
  - TCPA 47 CFR 64.1200: opt-out instantáneo sin costo.

NOTA: Esta es una plantilla de buena fe basada en best-practices. Para deploy
comercial con usuarios reales, validar con asesor legal de tu jurisdicción.
"""

import os
from datetime import date

EMPRESA_NOMBRE = os.getenv("LEGAL_EMPRESA", "Dona")
EMPRESA_EMAIL = os.getenv("LEGAL_EMAIL", "privacy@dona.ai")
EMPRESA_DIRECCION = os.getenv("LEGAL_DIRECCION", "[Dirección comercial pendiente de configurar]")
EMPRESA_ESTADO = os.getenv("LEGAL_ESTADO", "Delaware, USA")
ULTIMA_REVISION = os.getenv("LEGAL_ULTIMA_REVISION", date.today().isoformat())


def _base_html(titulo: str, contenido: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{titulo} — {EMPRESA_NOMBRE}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 760px; margin: 0 auto; padding: 32px 24px;
           color: #1a1a1a; line-height: 1.6; background: #fafafa; }}
    h1 {{ font-size: 2rem; margin-bottom: 4px; }}
    h2 {{ font-size: 1.25rem; margin-top: 32px; border-bottom: 1px solid #e0e0e0;
          padding-bottom: 8px; }}
    h3 {{ font-size: 1.05rem; margin-top: 20px; }}
    p, li {{ color: #333; }}
    ul {{ padding-left: 24px; }}
    .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 32px; }}
    .toc {{ background: #fff; border: 1px solid #e0e0e0; padding: 16px 24px;
            border-radius: 8px; margin-bottom: 32px; }}
    .toc a {{ color: #2563eb; text-decoration: none; }}
    .toc a:hover {{ text-decoration: underline; }}
    a {{ color: #2563eb; }}
    code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }}
    hr {{ border: 0; border-top: 1px solid #e0e0e0; margin: 40px 0; }}
    footer {{ color: #888; font-size: 0.85rem; text-align: center; margin-top: 40px; }}
  </style>
</head>
<body>
{contenido}
<hr>
<footer>
  © {date.today().year} {EMPRESA_NOMBRE}. {EMPRESA_ESTADO}.<br>
  Contacto: <a href="mailto:{EMPRESA_EMAIL}">{EMPRESA_EMAIL}</a>
</footer>
</body>
</html>"""


def privacy_policy_html() -> str:
    """Política de privacidad — cumple CCPA/CPRA + marco multi-estado EEUU."""
    contenido = f"""
<h1>Política de Privacidad</h1>
<div class="meta">Última actualización: {ULTIMA_REVISION}</div>

<div class="toc">
  <strong>Contenido:</strong>
  <ul>
    <li><a href="#quienes">1. Quiénes somos</a></li>
    <li><a href="#datos">2. Qué datos recopilamos</a></li>
    <li><a href="#uso">3. Cómo usamos tus datos</a></li>
    <li><a href="#compartir">4. Con quién compartimos tus datos</a></li>
    <li><a href="#retencion">5. Retención de datos</a></li>
    <li><a href="#ia">6. Uso de inteligencia artificial</a></li>
    <li><a href="#derechos">7. Tus derechos (CCPA/CPRA y otros estados)</a></li>
    <li><a href="#seguridad">8. Seguridad</a></li>
    <li><a href="#menores">9. Menores de edad</a></li>
    <li><a href="#cambios">10. Cambios a esta política</a></li>
    <li><a href="#contacto">11. Contacto</a></li>
  </ul>
</div>

<h2 id="quienes">1. Quiénes somos</h2>
<p>{EMPRESA_NOMBRE} ("nosotros", "nuestro") opera el servicio <strong>Dona</strong>, un
asistente de inteligencia artificial accesible por WhatsApp que ayuda a usuarios y pequeños
negocios a organizar tareas, clientes, ventas y comunicaciones.</p>
<p>Domicilio comercial: {EMPRESA_DIRECCION}, {EMPRESA_ESTADO}.</p>

<h2 id="datos">2. Qué datos recopilamos</h2>
<p>Recopilamos únicamente los datos necesarios para prestar el servicio:</p>
<h3>Datos proporcionados por ti</h3>
<ul>
  <li><strong>Número de teléfono</strong> (identificador principal de cuenta).</li>
  <li><strong>Nombre, ciudad, proyectos, contexto personal</strong> que compartas durante el onboarding.</li>
  <li><strong>Mensajes de WhatsApp</strong> (texto, transcripciones de audio, imágenes analizadas).</li>
  <li><strong>Datos de negocio</strong>: clientes, productos, ventas, gastos, pedidos, cotizaciones que registres.</li>
  <li><strong>Credenciales OAuth</strong> de Google (Calendar, Gmail, Sheets, Drive) si optas por conectar tu cuenta.</li>
</ul>

<h3>Datos recopilados automáticamente</h3>
<ul>
  <li>Timestamps de interacción.</li>
  <li>Metadatos de mensajes (IDs de WhatsApp, estado de lectura).</li>
  <li>Logs técnicos (IP del webhook, errores) para depuración — anonimizados tras 7 días.</li>
</ul>

<h3>Lo que NO recopilamos</h3>
<ul>
  <li>No rastreamos cookies de terceros ni pixels publicitarios.</li>
  <li>No vendemos ni compartimos tus datos con brokers de datos.</li>
  <li>No accedemos a datos de contactos, ubicación GPS, ni micrófono fuera de WhatsApp.</li>
</ul>

<h2 id="uso">3. Cómo usamos tus datos</h2>
<p>Tus datos se usan exclusivamente para:</p>
<ul>
  <li>Procesar tus mensajes y generar respuestas personalizadas.</li>
  <li>Ejecutar las acciones que solicites (crear recordatorios, registrar ventas, enviar correos).</li>
  <li>Mejorar tu experiencia (recordar tu nombre, contexto, preferencias).</li>
  <li>Detectar abuso y fraude (rate limiting, deduplicación de mensajes).</li>
  <li>Cumplir obligaciones legales.</li>
</ul>

<h2 id="compartir">4. Con quién compartimos tus datos</h2>
<p>Usamos los siguientes proveedores ("subprocessors") para operar el servicio:</p>
<ul>
  <li><strong>Anthropic, Inc.</strong> — procesa tus mensajes via API de Claude para generar respuestas. Retención por parte de Anthropic: 30 días (logs), no usa datos para entrenamiento.</li>
  <li><strong>OpenAI</strong> — usado únicamente para transcripción de audios (Whisper). No se retienen datos.</li>
  <li><strong>Groq</strong> — procesamiento acelerado de modelos de lenguaje.</li>
  <li><strong>Google LLC</strong> — si conectas Calendar/Gmail/Sheets voluntariamente.</li>
  <li><strong>Meta Platforms / WhatsApp / Whapi.cloud / Twilio</strong> — entrega de mensajes (tu proveedor de WhatsApp).</li>
  <li><strong>Railway / PostgreSQL managed hosting</strong> — almacenamiento de datos (cifrado en reposo).</li>
</ul>
<p>No vendemos tus datos. No los compartimos para publicidad de terceros.</p>

<h2 id="retencion">5. Retención de datos</h2>
<ul>
  <li><strong>Historial de mensajes</strong>: mientras tu cuenta esté activa.</li>
  <li><strong>Datos de negocio</strong>: mientras la cuenta esté activa o lo solicites.</li>
  <li><strong>Logs técnicos</strong>: 7 días.</li>
  <li><strong>Datos de dedup (IDs de mensajes WhatsApp)</strong>: 2 horas.</li>
  <li><strong>Tokens OAuth cifrados</strong>: hasta que revoques el acceso.</li>
</ul>
<p>Puedes solicitar la eliminación total de tus datos en cualquier momento (ver sección 7).</p>

<h2 id="ia">6. Uso de inteligencia artificial</h2>
<p>Dona es un <strong>asistente automatizado basado en inteligencia artificial</strong>, no un humano.
Todas las respuestas son generadas por modelos de lenguaje (principalmente Claude de Anthropic).</p>
<p>La IA puede cometer errores. No tomes decisiones médicas, legales o financieras críticas
basándote exclusivamente en las respuestas de Dona. Verifica siempre información importante
con profesionales.</p>
<p>No usamos tus mensajes para entrenar modelos de IA. Anthropic tampoco los usa para entrenamiento
bajo los términos de su API comercial.</p>

<h2 id="derechos">7. Tus derechos como consumidor</h2>
<p>Si eres residente de California (CCPA/CPRA), Virginia (VCDPA), Colorado (CPA),
Connecticut (CDPA), Utah (UCPA), Texas (TDPSA), u otro estado con ley de privacidad,
tienes los siguientes derechos:</p>
<ul>
  <li><strong>Derecho a saber</strong>: qué datos tenemos sobre ti y cómo los usamos.</li>
  <li><strong>Derecho a acceder / portabilidad</strong>: recibir una copia de tus datos en formato estructurado (JSON).</li>
  <li><strong>Derecho a eliminar</strong>: solicitar el borrado total de tu cuenta y datos.</li>
  <li><strong>Derecho a corregir</strong>: rectificar datos inexactos.</li>
  <li><strong>Derecho a opt-out de venta de datos</strong>: no vendemos datos, pero este derecho está garantizado.</li>
  <li><strong>Derecho a no discriminación</strong>: ejercer estos derechos no afecta tu acceso al servicio.</li>
</ul>
<h3>Cómo ejercerlos</h3>
<ul>
  <li>Envía <code>STOP</code> por WhatsApp para opt-out inmediato de mensajes proactivos (TCPA compliant).</li>
  <li>Escribe a <a href="mailto:{EMPRESA_EMAIL}">{EMPRESA_EMAIL}</a> para cualquier solicitud.</li>
  <li>Endpoint self-service: <code>GET /privacy/export?telefono=TU_NUMERO</code> (autenticado por tu teléfono).</li>
  <li>Endpoint self-service de borrado: <code>POST /privacy/delete?telefono=TU_NUMERO&amp;confirmacion=BORRAR</code>.</li>
</ul>
<p>Respondemos a todas las solicitudes dentro de <strong>45 días</strong> (CCPA) / <strong>30 días</strong> (estados similares).</p>

<h2 id="seguridad">8. Seguridad</h2>
<ul>
  <li>Tokens OAuth cifrados con Fernet (AES-128-CBC + HMAC-SHA256) en reposo.</li>
  <li>Firmas HMAC-SHA256 para webhooks de WhatsApp.</li>
  <li>TLS 1.2+ en todas las comunicaciones.</li>
  <li>Protección CSRF en OAuth (state firmado con nonce y expiración).</li>
  <li>Comparaciones timing-safe (hmac.compare_digest) en autenticación.</li>
  <li>Rate limiting para prevenir abuso.</li>
</ul>
<p>Ningún sistema es 100% seguro. En caso de brecha, notificaremos a usuarios afectados
dentro de los plazos que establezca la ley aplicable.</p>

<h2 id="menores">9. Menores de edad</h2>
<p>Dona no está dirigida a menores de 18 años. No recopilamos intencionalmente datos de
menores. Si descubres que un menor ha proporcionado datos, contáctanos para eliminarlos.</p>

<h2 id="cambios">10. Cambios a esta política</h2>
<p>Publicaremos cambios en esta página y, cuando sean materiales, notificaremos por WhatsApp
con 30 días de antelación cuando sea razonablemente posible.</p>

<h2 id="contacto">11. Contacto</h2>
<p>Para preguntas, solicitudes o quejas:</p>
<ul>
  <li>Email: <a href="mailto:{EMPRESA_EMAIL}">{EMPRESA_EMAIL}</a></li>
  <li>Dirección: {EMPRESA_DIRECCION}, {EMPRESA_ESTADO}</li>
</ul>
<p>Si eres residente de California y no estás satisfecho con nuestra respuesta, puedes
escalar al <a href="https://oag.ca.gov/privacy/ccpa">Attorney General de California</a>.</p>
"""
    return _base_html("Política de Privacidad", contenido)


def terms_html() -> str:
    """Términos de servicio."""
    contenido = f"""
<h1>Términos de Servicio</h1>
<div class="meta">Última actualización: {ULTIMA_REVISION}</div>

<h2>1. Aceptación</h2>
<p>Al usar Dona aceptas estos términos. Si no estás de acuerdo, deja de usar el servicio.</p>

<h2>2. Descripción del servicio</h2>
<p>Dona es un asistente de inteligencia artificial accesible por WhatsApp que ayuda con
tareas, organización, negocio, finanzas y comunicaciones.</p>
<p>Dona <strong>NO es</strong>:</p>
<ul>
  <li>Un asesor financiero, legal, médico o fiscal licenciado.</li>
  <li>Un sistema de facturación electrónica certificado.</li>
  <li>Una institución financiera o procesador de pagos.</li>
  <li>Un sustituto del juicio humano en decisiones importantes.</li>
</ul>

<h2>3. Elegibilidad</h2>
<p>Debes tener al menos 18 años y capacidad legal para contratar.</p>

<h2>4. Uso aceptable</h2>
<p>Aceptas NO usar Dona para:</p>
<ul>
  <li>Actividades ilegales o fraudulentas.</li>
  <li>Enviar spam o mensajes masivos no solicitados.</li>
  <li>Acosar, difamar o amenazar a terceros.</li>
  <li>Vulnerar sistemas, intentar jailbreaking, o abusar de la API.</li>
  <li>Reventa del servicio sin autorización escrita.</li>
  <li>Procesar datos sensibles regulados (PHI, PCI) sin acuerdo específico.</li>
</ul>

<h2>5. Inteligencia artificial — Descargo de responsabilidad</h2>
<p>Las respuestas de Dona son generadas por modelos de IA y pueden contener errores,
información desactualizada o alucinaciones. Verifica información crítica con fuentes
autoritativas. Dona no sustituye asesoramiento profesional.</p>

<h2>6. Propiedad intelectual</h2>
<p>Tú conservas todos los derechos sobre los datos que nos envíes. Nos otorgas una licencia
limitada y no exclusiva para procesarlos con el único fin de prestarte el servicio.</p>
<p>Dona y su código son propiedad de {EMPRESA_NOMBRE}.</p>

<h2>7. Precios y facturación</h2>
<p>El servicio puede tener planes gratuitos con límites (quotas) y planes de pago. Los
precios se informan en <a href="/">la página principal</a> y pueden cambiar con 30 días
de aviso.</p>

<h2>8. Terminación</h2>
<p>Puedes dejar de usar Dona en cualquier momento enviando <code>STOP</code> o solicitando
el borrado en <a href="mailto:{EMPRESA_EMAIL}">{EMPRESA_EMAIL}</a>.</p>
<p>Podemos suspender cuentas que violen estos términos, con notificación previa salvo en
casos de abuso evidente.</p>

<h2>9. Limitación de responsabilidad</h2>
<p>HASTA EL MÁXIMO PERMITIDO POR LA LEY, {EMPRESA_NOMBRE.upper()} NO SERÁ RESPONSABLE POR
DAÑOS INDIRECTOS, INCIDENTALES, CONSECUENCIALES O PUNITIVOS. NUESTRA RESPONSABILIDAD TOTAL
NO EXCEDERÁ LO QUE HAYAS PAGADO EN LOS ÚLTIMOS 12 MESES, O $100 USD, EL QUE SEA MAYOR.</p>

<h2>10. Ley aplicable</h2>
<p>Estos términos se rigen por las leyes del estado de {EMPRESA_ESTADO}, sin considerar
conflicto de leyes. Las disputas se resolverán en los tribunales competentes de esa
jurisdicción, salvo que la ley aplicable del consumidor establezca lo contrario.</p>

<h2>11. Cambios a estos términos</h2>
<p>Podemos actualizar estos términos con notificación de 30 días para cambios materiales.</p>

<h2>12. Contacto</h2>
<p><a href="mailto:{EMPRESA_EMAIL}">{EMPRESA_EMAIL}</a></p>
"""
    return _base_html("Términos de Servicio", contenido)
