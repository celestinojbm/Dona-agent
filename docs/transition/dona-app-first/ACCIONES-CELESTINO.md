# Acciones de Celestino — paneles de proveedores

Cada acción indica **dónde**, **qué hacer**, **efecto** y **cómo comprobarlo**.
Claude Code no tiene acceso a estos paneles: todo lo de aquí lo ejecuta
Celestino. Anota los resultados en `ESTADO.md` (sin identificadores
privados: nada de IDs de cliente, emails, teléfonos ni claves).

Orden recomendado: **A (Stripe, ya)** → merge del PR de pausa → **B
(Vercel)** → **C (WhatsApp)** → **D (Render/Railway, ver
RESPALDO-Y-RETIRO.md)**.

---

## A. Contención urgente en Stripe (ejecutable ya, antes del PR)

Cuenta: **Stravos Enterprises LLC**, modo **live** (interruptor "Test mode"
apagado). La cuenta puede tener otros negocios: **filtra siempre por los
productos de Dona** (Premium 20 USD/mes, Pro 40 USD/mes, paquetes de
créditos 100/500/2000) y no toques nada más.

### A1. Registrar las dos fechas

| Momento | Valor | Fuente |
|---|---|---|
| Suspensión histórica del backend | ~2026-06-24 (aproximada) | `docs/CURRENT_STATE.md`; confirmar en el historial de Render |
| Corte efectivo de cobros | _fecha y hora ET en que terminas A2–A6_ | tu reloj al terminar |

No es lo mismo: la suspensión dejó de **prestar** servicio; el corte deja de
**cobrar**. Todo cobro entre ambas fechas es un cobro sin servicio.

### A2. Suscripciones

1. **Billing → Subscriptions**, estados *Active*, *Trialing*, *Past due*,
   *Unpaid* y *Paused*, producto Dona.
2. La base de datos local tiene **3 filas `active`** (premium, altas del 2 may,
   6 may y 1 jul; mismo teléfono). La BD dejó de recibir webhooks con la
   suspensión: **su estado no prueba nada**. Lo que cuenta es Stripe.
3. Para cada suscripción de Dona que siga viva: **Cancel subscription →
   immediately**. En el diálogo, revisa las opciones antes de confirmar: que
   **no** genere factura final, ni prorrateo, ni cobro de uso pendiente. No
   marques reembolso salvo que lo decidas expresamente.
4. Revisa también **subscription schedules** (suscripciones programadas a
   futuro) y cancélalas si son de Dona.

- **Efecto:** no habrá más renovaciones. **No tiene vuelta atrás automática**:
  una suscripción cancelada no se reactiva; habría que crear otra.
- **Comprobación:** el filtro anterior devuelve 0 suscripciones de Dona.

### A3. Facturas y pagos pendientes

1. **Billing → Invoices**, estados *Draft*, *Open* y *Past due*, producto Dona.
   - Un *draft* de suscripción se finaliza solo (~1 h después de creado) y
     se intenta cobrar. Si encuentras uno, **no lo borres ni lo anules por
     tu cuenta todavía**: anótalo y decide (anular / dejar / cobrar).
2. **Billing → Invoice items / pending items** (conceptos pendientes de
   facturar) de clientes de Dona: anotar.
3. **Payments**, estado *Processing* / *Requires action*: anotar.
4. **Payments** desde el **24 jun 2026** hasta hoy, cobros exitosos de Dona:
   anota **fechas, cantidad y total**. No fuerces "cero": si hubo cobros, se
   informan tal cual y el reembolso es tu decisión.

- **Comprobación:** lista escrita de obligaciones pendientes (puede estar
  vacía) con tu decisión al lado.

### A4. Enlaces de pago y sesiones de checkout

1. **Payment Links**: desactiva los de Dona (*Deactivate*, no borrar).
2. Sesiones de Checkout abiertas: el código **no fija `expires_at`**, así que
   Stripe las expira a las **24 h** de creadas. Una sesión abierta todavía se
   puede pagar hasta entonces. Busca en **Developers → Events** eventos
   `checkout.session.created` de las últimas 24 h sin su
   `checkout.session.completed`/`expired`. Si hay alguna, anótala (se puede
   expirar manualmente; decisión tuya).

### A5. Precios: archivar NO basta

Archivar los precios de Dona es un cinturón extra, **no una barrera**: si en
Vercel las variables `STRIPE_PRICE_PREMIUM`/`STRIPE_PRICE_PRO` están vacías,
`landing/app/api/checkout/route.ts` (versión actual de `main`) crea el
precio **inline** (`price_data`) y cobra igual. La barrera real es el PR de
pausa (B) o la contención de la clave (A6).

Si quieres archivarlos igualmente: **Products → producto de Dona → Archive**
(archivar, nunca borrar).

### A6. Clave de API que usa la landing

1. En **Vercel → proyecto de la landing → Settings → Environment
   Variables**, mira la variable `STRIPE_SECRET_KEY` (solo el sufijo visible;
   no copies el valor a ningún chat).
2. En **Stripe → Developers → API keys**, identifica a qué clave
   corresponde ese sufijo:
   - **Clave restringida exclusiva de Dona** → revocarla es la contención
     **más rápida** (corta el checkout en el servidor al instante, incluso
     antes del PR). Hazlo y anota la hora.
   - **Clave secreta general de la cuenta Stravos** → **no la revoques**: la
     usarían otros negocios. Contención específica: borrar
     `STRIPE_SECRET_KEY` (y las `STRIPE_PRICE_*`) **solo del proyecto de la
     landing en Vercel** y redeployar ese proyecto. Más adelante crea una
     clave restringida propia de Dona si vuelve a cobrar.
3. El PR de pausa **no necesita** `STRIPE_SECRET_KEY`: verifica firmas de
   webhook solo con `STRIPE_WEBHOOK_SECRET`.

### A7. Webhook de Stripe

1. **Developers → Webhooks**: anota la URL de cada endpoint de Dona
   (¿`usadona.com/api/webhook`? ¿Render?) y si tiene entregas fallidas
   acumuladas (Stripe reintenta hasta 3 días).
2. Endpoints que apunten a **Render** → **Disable** (no borrar).
3. Endpoint de la landing: déjalo activo **solo si** `STRIPE_WEBHOOK_SECRET`
   está configurada en Vercel. Con el PR de pausa, un evento firmado recibe
   `200` sin ninguna acción comercial y se cortan los reintentos. Si la
   variable **no** existe, la pausa responde `503` y **no acepta eventos sin
   validar**: en ese caso **deshabilita el endpoint**.

### Cierre de A

Criterio: **ninguna vía de cobro nueva** (checkout bloqueado o clave
contenida, payment links desactivados) y **ninguna vía de renovación**
(0 suscripciones vivas, 0 schedules, drafts decididos). Anota en
`ESTADO.md`: fecha/hora del corte, nº de suscripciones canceladas, cobros
desde el 24 jun (fechas, nº, total) y decisiones pendientes.

---

## B. Vercel (después del merge del PR de pausa)

1. **Antes del merge**: abre la *preview* del PR y comprueba la página de
   pausa en `/`, `/checkout`, `/login`, `/dashboard`.
2. **Antes de cualquier merge a `main`**: confirma que **Render no puede
   redesplegar** (servicio borrado o *Auto-Deploy: Off*). Un merge a `main`
   publica la landing en Vercel y, si Render sigue enganchado, intentaría
   construir el backend.
3. Tras el merge: **Deployments → Production** muestra el SHA del merge.
4. Comprobaciones (`curl -i`):
   - `https://usadona.com/` → 200 y texto "Dona está en pausa".
   - `POST https://usadona.com/api/checkout` con cuerpo
     `{"plan":"premium","embedded":true}` → **503** `dona_en_pausa`.
   - `https://usadona.com/api/whatsapp-webhook` → **410**.
   - `https://usadona.com/prototipo` → 404; `/engineering` → 404.
5. Variables que dejan de usarse con la pausa (puedes borrarlas del proyecto
   de la landing cuando quieras; borrarlas reduce lo que un fallo futuro
   podría usar):
   - Cobro: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PREMIUM`, `STRIPE_PRICE_PRO`,
     `STRIPE_PRICE_PAQUETE_100/500/2000`, `STRIPE_PORTAL_RETURN_URL`,
     `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`.
   - Backend y login: `BACKEND_URL`, `INTERNAL_BRIDGE_SECRET`,
     `DASHBOARD_PASSWORD_SECRET`.
   - Panel de ingeniería: `PANEL_INGENIERIA_TOKEN`, `PANEL_GITHUB_TOKEN`,
     `GITHUB_TOKEN`, `PANEL_GITHUB_REPO`, `RENDER_API_KEY`,
     `PANEL_RENDER_WEB_ID`, `PANEL_RENDER_WORKER_ID`. Ojo: `RENDER_API_KEY`
     y los tokens de GitHub son credenciales de cuenta; si existen,
     revócalos en su proveedor cuando ya no hagan falta.
   - WhatsApp: `WHAPI_TOKEN`, `NEXT_PUBLIC_DONA_WHATSAPP_NUMBER`.
   - **Conserva** `STRIPE_WEBHOOK_SECRET` mientras el endpoint de Stripe esté
     activo, y `AUTH_SECRET`/`NEXTAUTH_SECRET`.

## C. WhatsApp (canal futuro, desconectado)

No se sabe qué proveedor usa producción (el default del código es Whapi).

- **Whapi.cloud**: canal → *Settings* → borra la *Webhook URL*. *Billing*:
  cancela o no renueves el plan del canal.
- **Meta (developers.facebook.com → App → WhatsApp → Configuration)**: quita
  el callback y desuscribe los campos del webhook.
- **No borres el número ni la WABA**: perder el número es irreversible.
- Comprobación: sin webhook configurado; plan cancelado;
  `/api/whatsapp-webhook` → 410.

## D. Render, Railway y Supabase

Ver `RESPALDO-Y-RETIRO.md`. Nada se borra antes de un respaldo comprobado.

## E. Correo de contacto

Antes de añadir `hola@usadona.com` al aviso de pausa: envía un correo de
prueba desde una cuenta externa y confirma que lo recibes (Cloudflare Email
Routing). Hasta entonces el aviso no muestra contacto.
