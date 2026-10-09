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

---

## J1 · seguimiento en CI (#288)

- Landing (lint · typecheck · test · build): verde.
- gitleaks: rojo en `92d0b22` por un fixture propio (`generic-api-key` en
  `landing/lib/auth-pausa.test.ts:43`). Corregido en `231844f` (valor
  construido en ejecución) y, como el commit ya estaba publicado, huella
  exacta en `.gitleaksignore` (`5cbfb97`) → verde. Sin ampliar `.gitleaks.toml`.
- pytest y pip-audit: rojos **heredados de `main`** (ver J3). Comentado en el PR.
- Preview de Vercel: protegida (302 al login de Vercel); la revisa Celestino.

## J3 · candidata de dependencias (#290) — 2026-10-08

Rama `claude/j3-candidato-deps` @ `f96738f`. Merges de #287 (`620067f`),
#286 (`4d3efd0`), #285 (`edd559f`), #243 (lockfile regenerado con `npm
install` por conflicto con #285), #284 y la pausa.

| Comprobación (instalación limpia, Python 3.11.17, Node 22) | Resultado |
|---|---|
| `pip install -r requirements-dev.txt` | greenlet 3.5.6, SQLAlchemy 2.1.4, cryptography 50.0.2 |
| `pytest --cov=agent --cov-fail-under=46` | **2422 passed**, cobertura 62.89 % |
| `pip-audit -r requirements.txt` (mismo ignore que el workflow) | sin vulnerabilidades conocidas |
| Landing `npm ci`, lint, typecheck, vitest, build | verde (252 tests) |
| `npm audit --omit=dev` | **0** (en `main`: 8, 3 críticas) |
| gitleaks modo git, historial completo, config del repo | sin hallazgos (con las 7 huellas) |

Reproducción del fallo de `main`: en un venv limpio con `requirements.txt`
de `main`, `import sqlalchemy.ext.asyncio` → `ImportError` (greenlet); la
suite da 613 fallos, igual que en CI.

Clasificación de gitleaks (historial completo de `main`, 483 commits):

| Huella (commit:archivo:línea) | Qué es | Decisión |
|---|---|---|
| `ccf1009…:tests/test_automation_audit.py:31` | `"dona-secret123"` como valor que el sanitizador debe descartar | fixture → huella |
| `e4181aa…:landing/lib/auth-matcher.test.ts:471` | ids de Stripe ficticios `cus_SECRET12345` | fixture → huella |
| `2e77dfe…:tests/test_welcome_premium.py:96,112` | contraseñas de formato `dona-abc123def456` | fixture → huella |
| `a5e338c…:tests/test_logging.py:63,68` | claves con patrón `AAAABBBB…` para el redactor de logs | fixture → huella |
| `92d0b22…:landing/lib/auth-pausa.test.ts:43` | fixture de formato del test de authorize (propio) | fixture → huella; corregido en el árbol |

Ningún hallazgo es una credencial real: no hay rotación que preparar por gitleaks.

Pendiente documentado: `vitest`/`@vitest/mocker` ≤4.1.10 (moderada, solo
dev; `npm install vitest@4.1.11` falla con un bug de npm 10) y `braces` (sin
versión corregida; solo tooling de lint).

## J4 · backend sin efectos (#291)

Rama `claude/j4-backend-sin-efectos` @ `440f63f`.

| Comprobación | Resultado |
|---|---|
| Suite completa con cobertura (Python 3.11) | 2466 passed, 3 fallos en `test_readiness_secrets.py` por el helper de "todo configurado" → corregido en `8872fe2`; re-ejecución 62 passed |
| `tests/test_efectos_arranque.py` | 47 passed (incluye arranque y apagado completos de la app con httpx saliente bloqueado) |
| diff-cover vs `origin/main` | 97 % (umbral 80 %) |
| `ruff check agent` | limpio |
| Landing vitest / tsc / eslint | 262 passed / OK / OK |

## J5 · paquete MSI (#292)

Rama `claude/j5-paquete-msi` @ `7b18c17`.

| Comprobación | Resultado |
|---|---|
| `tests/test_deploy_msi.py` | 6 passed; con el puerto publicado fuera de loopback → 1 fallo (mutación detectada) |
| `docker compose config` (sin daemon) | válido; `DONA_SHA`/`DONA_ENV_FILE` obligatorios |
| `validar.sh` | OK; caso negativo (0.0.0.0) rechazado |
| `bash -n` de los scripts | OK |
| Construcción de la imagen | **no verificada**: el sandbox no tiene daemon de Docker |

## J7 · backend app-first (modelo + runner)

Rama `claude/j7-app-first-modelo` @ `eb3d1e1`.

| Comprobación | Resultado |
|---|---|
| `tests/test_app_first_modelo.py` | 17 passed (aislamiento entre workspaces, permisos, valores cerrados, transiciones, cuentas, esquema aditivo) |
| `tests/test_app_first_ejecucion.py` | 19 passed (flujo completo, idempotencia, dos workers, aprobación/rechazo, herramienta no permitida, presupuesto, fallo y reintento sin duplicar efectos, reinicio del worker, cancelación, aislamiento, worker apagado, inproc) |
| Mutaciones | sin chequeo de presupuesto → 1 fallo; reclamo sin condición de estado → 3 fallos |
| Proveedores | solo `simulado`; cualquier otro modelo → `proveedor_no_disponible` sin red |
| Suite completa con cobertura | **2505 passed**, cobertura total 64,56 % (piso 46 %) |
| diff-cover vs la base (`claude/j4-backend-sin-efectos`) | 90 % (piso 80 %) |
| gitleaks sobre el rango | sin hallazgos |

## J7.4–J7.6 · API, UI `/app` y demo — 2026-10-08

Ramas `claude/j7-app-first-api` (API) y `claude/j7-app-first-ui` (UI +
demo), apiladas sobre J7.

| Comprobación | Resultado |
|---|---|
| `tests/test_app_first_api.py` + modelo + ejecución | 48 passed (ruta plana en `app.routes`, piloto apagado = 404 aun con firma válida, firma ausente/errónea = 401, registro solo por invitación, duplicado = 409, lockout tras 10 fallos = 429, flujo completo por la API, aislamiento entre usuarios) |
| `tests/test_demo_app_first.py` | 6 passed (demo completa y repetible con la app real en proceso, sin invitación, worker apagado con pista, solo loopback, backend caído) |
| Landing `npx vitest run` | **35 archivos, 303 tests** en verde (nuevos: bridge `/internal/app`, provider `cuenta`, server actions, puerta del layout, piloto) |
| Landing `tsc --noEmit` / `eslint` | sin errores (1 warning preexistente del `<img>` del pixel) |
| `next build` | OK; rutas dinámicas `/app`, `/app/entrar`, `/app/registro`, `/app/proyectos/[id]`, `/app/tareas/[id]` |

| Suite completa sobre la UI (1.ª corrida) | **1 fallo real**: `test_smoke_e2e::test_webhook_routes_registradas` — `include_router` dejaba un `_IncludedRouter` sin `.path` en `app.routes` (FastAPI 0.142). Corregido registrando la ruta con `add_api_route` (`75906a8`) + test de regresión que falla con el código anterior |
| Suite completa tras la corrección | **2523 passed**, cobertura 64,79 %; diff-cover 86 % vs #293 |

### Recorrido E2E en navegador (local, proveedor simulado)

Backend local (`uvicorn`, SQLite temporal, solo `DONA_WORKER_ENABLED`
encendido; WhatsApp, Stripe, LLM, scheduler e inbound apagados) + `next
start` del build + Chromium (Playwright) en viewport móvil 390×844. Secretos
generados al vuelo, datos sintéticos (`ana@example.com`).

| Paso | Resultado |
|---|---|
| Registro con correo no invitado | rechazado: "Este correo no tiene invitación al piloto." |
| Registro invitado | crea espacio, área "General", agentes Responsable y Ejecutor |
| Crear proyecto con 2 criterios, tarea asignada al Ejecutor, mensaje | OK |
| Ejecutar la tarea "Publicar…" | queda en "Necesita aprobación" con riesgo alto y preview marcada "simulado" |
| Aprobar | tarea "Completada"; evidencias: texto, registro de la operación, revisión del responsable; cada una con sha256 |
| Salir; entrar con contraseña mala; entrar bien | rechazado / vuelve a `/app` |
| `/` | sigue mostrando "Dona está en pausa" |
| Desborde horizontal a 390 px | ninguno en inicio, proyecto y tarea |

**13 de 13 pasos OK**, repetido desde una base vacía tras pulir textos.

### Límites

- El script E2E de Playwright no está en el repo (Playwright no es
  dependencia de la landing); el recorrido reproducible para Celestino es
  `scripts/demo_app_first.py` (API) más la guía de `APP-FIRST.md` § 11.
- No probado contra Vercel ni contra la MSI: el piloto no está abierto
  (ver `ACCIONES-CELESTINO.md` § F).
- El texto del agente y la revisión del responsable son simulados; ningún
  modelo real ha intervenido.

## J1 en producción — 2026-10-09 03:30 UTC

Tras el merge de #290 (que incluye #288) en `main` = `c032211`. Peticiones
anónimas a `https://usadona.com`, sin credenciales:

| Ruta | Resultado |
|---|---|
| `/`, `/checkout`, `/success`, `/dashboard`, `/login`, términos, privacidad | 200 con "Dona está en pausa" |
| `/prototipo`, `/engineering`, `/app` | 404 |
| `POST /api/checkout` | 503 (sin código de Stripe) |
| `POST /api/billing-portal` | 503 |
| `POST /api/webhook` sin firma | 400 (hay secreto configurado; la firma se exige) |
| `GET /api/whatsapp-webhook` | 410 |
| Pixel de Facebook en `/` | ausente |

No verificado desde aquí: que Stripe no tenga suscripciones vivas ni
enlaces de pago activos (eso es § A de `ACCIONES-CELESTINO.md`).
