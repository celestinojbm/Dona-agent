# Estado de la transición — Dona app-first

Fuente de verdad del avance. Cuatro estados:

- **Hecho**: en `main` (y, si aplica, verificado en producción).
- **Probado**: en una rama/PR, con pruebas locales y/o CI en verde; falta merge.
- **Preparado**: documento o instrucción lista; falta que alguien lo ejecute.
- **Bloqueado**: depende de una decisión o acción de Celestino.

Sin identificadores privados (IDs de cliente, emails, teléfonos, claves,
hostnames internos).

Última actualización: 2026-10-08 (jornada 1, cierre) · base `main` = `958b525` (sin cambios: nada fusionado).

---

## J1 — Corte de cobros y página de pausa

| Elemento | Estado | Dónde |
|---|---|---|
| Checklist urgente de Stripe | **Preparado** | `ACCIONES-CELESTINO.md` § A |
| Ejecución del checklist en Stripe (cuenta Stravos, live) | **Bloqueado** (Celestino) | registrar resultado abajo |
| PR "Dona en pausa" (landing) | **Probado** (Landing CI y gitleaks en verde; pytest y pip-audit rojos heredados de `main`) | #288 · rama `claude/happy-babbage-bs15fv` |
| Preview de Vercel del PR revisada | **Bloqueado** (Celestino) | `ACCIONES-CELESTINO.md` § B1 |
| Render sin redeploy automático antes del merge | **Bloqueado** (Celestino) | `ACCIONES-CELESTINO.md` § B2 |
| Merge y verificación en producción | **Bloqueado** (OK de Celestino) | `ACCIONES-CELESTINO.md` § B3–B4 |
| Contacto en el aviso de pausa | **Bloqueado** (verificar correo) | `ACCIONES-CELESTINO.md` § E |

### Registro del corte (lo rellena Celestino)

| Dato | Valor |
|---|---|
| Suspensión histórica del backend | ~2026-06-24 (aprox., según `docs/CURRENT_STATE.md`) |
| Fecha/hora del corte efectivo de cobros (ET) | _pendiente_ |
| Suscripciones de Dona vivas en Stripe antes del corte | _pendiente_ |
| Suscripciones canceladas (inmediatas, sin factura final) | _pendiente_ |
| Cobros de Dona desde el 24 jun: fechas, nº y total | _pendiente_ |
| Facturas draft/open, conceptos pendientes, pagos en proceso | _pendiente_ |
| Payment links desactivados | _pendiente_ |
| Clave de API de la landing: exclusiva / compartida, contención aplicada | _pendiente_ |
| Endpoints de webhook: URL, estado final | _pendiente_ |
| SHA desplegado en producción tras el merge de la pausa | _pendiente_ |

Criterio de cierre de J1: ningún cobro nuevo iniciado después del corte y
ninguna vía de renovación pendiente (no "cero cobros históricos").

---

## Bloques siguientes

| Bloque | Estado | PR · rama | Depende de |
|---|---|---|---|
| Docs de transición | **Probado** (solo docs) | #289 · `claude/dona-transicion-docs` | #288 |
| J2 Respaldo y retiro | **Preparado** (`RESPALDO-Y-RETIRO.md`); **Bloqueado** (Celestino: inventario y respaldos) | — | J1 |
| J3 Repo sano y dependencias | **Probado**: CI completo en verde (pytest, pip-audit, gitleaks, landing) | #290 · `claude/j3-candidato-deps` | #288 |
| J4 Backend sin efectos externos | **Probado**: CI en verde | #291 · `claude/j4-backend-sin-efectos` | #290 |
| J5 Paquete MSI | **Probado**: CI en verde (sin Docker); **Preparado** el preflight para Hermes MSI | #292 · `claude/j5-paquete-msi` | #291 |
| J6 Conectividad MSI | **Preparado** (`MSI-RUNBOOK.md` § 3); **Bloqueado** (OK de arranque) | — | J5 |
| J7.1–J7.3 Modelo + runner | **Probado** (local: 2505 passed, diff-cover 90 %) | #293 · `claude/j7-app-first-modelo` | #291 |
| J7.4 API interna `/internal/app` | **Probado** (local: 2523 passed, diff-cover 86 %) | #294 · `claude/j7-app-first-api` | #293 |
| J7.5 UI `/app` + J7.6 demo | **Probado** (local: vitest 303, build, E2E móvil 13/13) | #295 · `claude/j7-app-first-ui` | J7.4 |
| J8 Piloto privado | **Preparado** (`ACCIONES-CELESTINO.md` § F); **Bloqueado** (merges, MSI y OK) | — | J5, J6, J7 |

Orden de merge propuesto (cada merge publica la landing en Vercel; antes,
Render sin redeploy automático):

1. #290 (incluye #287, #286, #285, #243, #284 y la pausa de #288) — o #288
   solo si prefieres el corte mínimo primero.
2. #289 (docs).
3. #291 (J4) → #292 (J5) → #293 (J7) → #294 → #295.

Fusionar J7.5 en `main` **no abre** el piloto: `/app` sigue en 404 hasta
`DONA_APP_PILOTO_ENABLED=true` en Vercel y en el backend (§ F).

## Acciones de Celestino pendientes (resumen)

| # | Acción | Dónde | Bloquea |
|---|---|---|---|
| 1 | Contención de Stripe (§ A completa) y registro del corte | `ACCIONES-CELESTINO.md` § A | cierre de J1 |
| 2 | Render: Auto-Deploy en Off (o borrado tras respaldo) | `RESPALDO-Y-RETIRO.md` § 5.1 | **cualquier** merge |
| 3 | Revisar la preview de #288 (está protegida por Vercel: no la pude abrir) | Vercel | merge de #288 |
| 4 | Decidir estrategia de integración (A o B de #290) | PR #290 | J3 |
| 5 | Inventario y respaldos de Render/Railway/Supabase/R2 + restauración aislada | `RESPALDO-Y-RETIRO.md` §§ 2–4 | J2 |
| 6 | WhatsApp: quitar webhooks en Whapi/Meta, no borrar número ni WABA | `ACCIONES-CELESTINO.md` § C | — |
| 7 | Probar que `hola@usadona.com` recibe correo antes de publicarlo | `ACCIONES-CELESTINO.md` § E | contacto en el aviso |
| 8 | Autorizar el preflight de solo lectura en la MSI (Hermes MSI) | `MSI-RUNBOOK.md` § 1 | J5/J6 |
| 9 | Abrir el piloto con invitados (cuando J5–J7 estén fusionados y la MSI corra) | `ACCIONES-CELESTINO.md` § F | J8 |

## Cómo reanudar

```bash
git fetch origin
git checkout claude/j7-app-first-ui            # último bloque (incluye J7.1–J7.6)
python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q tests/test_app_first_modelo.py tests/test_app_first_ejecucion.py \
  tests/test_app_first_api.py tests/test_demo_app_first.py tests/test_efectos_arranque.py
(cd landing && npm ci && npx vitest run && npm run build)
```

Recorrido completo a mano: `APP-FIRST.md` § 11.

Siguiente bloque de código, sin depender de Celestino: lo que `APP-FIRST.md`
§ 8 deja fuera del piloto (editar agentes, invitar miembros, actualización
en vivo) y el refresco de `vitest` cuando npm permita salir de 4.1.9.
Lo que sí depende de él: J2 (respaldos), J6 (arranque en la MSI) y J8.

## Riesgos abiertos

- Las 3 suscripciones `active` de la BD pueden no reflejar Stripe (la BD dejó
  de recibir webhooks con la suspensión). Fuente de verdad: Stripe.
- Si las env `STRIPE_PRICE_*` están vacías en Vercel, la versión actual de
  `main` cobra con `price_data` inline: archivar precios no lo frena. Lo
  frena el PR de pausa o contener la clave (A6).
- Hasta el merge de la pausa, cada visita a `/checkout` en producción puede
  crear una sesión de pago real.
- `main` sigue con CI rojo (greenlet, cryptography, gitleaks) hasta que se
  fusione #290 (o #287/#286 y las huellas de `.gitleaksignore`).
- `vitest` 4.1.9 tiene un aviso abierto (dev, no llega a producción); npm 10
  falla al actualizarlo dentro del rango. Dependabot propone 5.0.3 (#278):
  es mayor, revisarlo aparte.
- El piloto `/app` usa un solo workspace por usuario y no se actualiza en
  vivo; el proveedor es simulado. No es todavía un producto para vender.
- El repo es público: todo lo que se commitea (docs incluidos) es visible.
- La imagen Docker del backend no se ha construido aún en ninguna máquina
  con este código (el sandbox no tiene daemon); lo hará Hermes MSI.
- Un merge a `main` publica la landing en Vercel; si Render sigue
  enganchado al repo, también intentaría redesplegar el backend.
