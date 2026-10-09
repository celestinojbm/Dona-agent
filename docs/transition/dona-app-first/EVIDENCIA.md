# Evidencia — Dona app-first

Registro de lo comprobado: SHA, comandos, resultados y límites. Cada entrada
dice qué se verificó y qué **no** se pudo verificar desde aquí.

---

## J1 · PR de pausa — 2026-10-08

- Base: `main` = `958b5250ac2e04075d74bb061eeebd3504911be4` (2026-07-19).
- Rama: `claude/happy-babbage-bs15fv`. SHA del commit: ver el PR.
- Entorno: sandbox de Claude Code (Linux), Node v22.22.0, `npm ci` desde
  `landing/package-lock.json` (next 16.2.10, next-auth 5.0.0-beta.31,
  stripe 22.3.0, vitest 4.1.9).

### Comprobaciones previas (2026-10-07/08)

| Qué | Resultado |
|---|---|
| `https://dona-agent.onrender.com/` | `503`, cabecera `x-render-routing: suspend`, cuerpo "This service has been suspended." |
| `/robots.txt`, `/sitemap.xml` en producción | `404` |
| `/prototipo` en producción | `200`, título "Dona — prototipo hero v2" |
| `/terminos-y-condiciones` en producción | describe a Dona como "asistente inteligente para negocios, accesible principalmente por WhatsApp", fecha 2 may 2026 |

### Comandos y resultados (en `landing/`)

| Comando | Resultado |
|---|---|
| `npm run lint` | 0 errores, 1 warning preexistente (`<img>` del pixel en `app/layout.tsx`) |
| `npm run typecheck` | sin errores |
| `npx vitest run` | **28 archivos, 252 tests, todos en verde** |
| `npm run build` (env de placeholder iguales a `.github/workflows/landing.yml`) | build OK |

Prueba de que los tests detectan la regresión: con `DONA_EN_PAUSA` puesto en
`false` a mano, `pausa-rutas`, `auth-pausa` y `pausa` fallan (**19 de 24
tests en rojo**). Después se restauró el valor; el diff final lo deja en
`true`.

### Smoke test sobre el build (`next start` local, puerto 3100)

Variables: solo `STRIPE_WEBHOOK_SECRET` de prueba, `AUTH_SECRET` de
placeholder y `AUTH_TRUST_HOST=true` (necesaria fuera de Vercel). **Sin**
`STRIPE_SECRET_KEY`, sin `BACKEND_URL`.

| Petición | Respuesta |
|---|---|
| `GET /`, `/checkout`, `/success`, `/cancel`, `/login`, `/dashboard`, `/soporte` | 200 con "Dona está en pausa"; sin pixel de Facebook; sin Stripe.js |
| `GET /terminos-y-condiciones`, `/politica-de-privacidad` | 200 con aviso de pausa |
| `GET /engineering`, `/prototipo`, `/no-existe` | 404 (página 404 en español) |
| `POST /api/checkout` (suscripción embebida y top-up) | 503 `dona_en_pausa` |
| `GET` y `POST /api/whatsapp-webhook` | 410 `dona_en_pausa` |
| `POST /api/billing-portal`, `/api/cancel-subscription`, `/api/chat`, `/api/automation/acciones/1/ejecutar`; `GET /api/dashboard-data` | 503 `dona_en_pausa` |
| `GET /api/engineering/data`, `POST /api/engineering/login` | 404 |
| `POST /api/webhook` firmado con el secreto de prueba | 200 `{received:true, paused:true}`; log: solo id, tipo, livemode, created |
| `POST /api/webhook` con firma inválida / sin firma | 400 / 400 |
| Login completo por NextAuth (CSRF + `callback/credentials`) con contraseña de formato válido | 302 a `/login?error=CredentialsSignin`; **ninguna cookie de sesión emitida**; `/api/auth/session` → `null`; sin intento de llamar a Stripe |

### Límites

- **No** verificado desde aquí: preview de Vercel, variables reales de
  Vercel, estado de Stripe (suscripciones, cobros, endpoints, claves),
  Render, Railway, Supabase, Whapi/Meta. Lo hace Celestino.
- El acuse del webhook en pausa **no reconcilia la base de datos**. La
  conciliación de cierre se hace contra Stripe.
- Las sesiones de Checkout ya abiertas en Stripe antes del merge siguen
  pagables hasta que caduquen (24 h por defecto). El PR solo impide crear
  nuevas.
- La evidencia de webhooks recibidos en pausa vive en los logs de Vercel
  (retención limitada del plan); Stripe conserva los eventos en su panel.
