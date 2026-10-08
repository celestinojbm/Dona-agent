# Estado de la transición — Dona app-first

Fuente de verdad del avance. Cuatro estados:

- **Hecho**: en `main` (y, si aplica, verificado en producción).
- **Probado**: en una rama/PR, con pruebas locales y/o CI en verde; falta merge.
- **Preparado**: documento o instrucción lista; falta que alguien lo ejecute.
- **Bloqueado**: depende de una decisión o acción de Celestino.

Sin identificadores privados (IDs de cliente, emails, teléfonos, claves,
hostnames internos).

Última actualización: 2026-10-08 (jornada 1) · base `main` = `958b525` (sin cambios: nada fusionado).

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
| J3 Repo sano y dependencias | **Probado**: candidata con #287 + #286 + #285 + #243 + #284 + pausa; CI en verde salvo pytest (en curso en el momento de escribir) | #290 · `claude/j3-candidato-deps` | #288 |
| J4 Backend sin efectos externos | **Probado** (local: 2466 + 3 corregidos; diff-cover 97 %) | #291 · `claude/j4-backend-sin-efectos` | #290 |
| J5 Paquete MSI | **Probado** (CI sin Docker); **Preparado** el preflight para Hermes MSI | #292 · `claude/j5-paquete-msi` | #291 |
| J6 Conectividad MSI | **Preparado** (`MSI-RUNBOOK.md` § 3); **Bloqueado** (OK de arranque) | — | J5 |
| J7 Base app-first (backend: modelo + runner) | **Probado** (local) | `claude/j7-app-first-modelo` | #291 |
| J7.4–J7.6 (acceso propio, API, UI, demo) | Pendiente | — | J7 backend |
| J8 Piloto privado | Pendiente | — | J7 |

Orden de merge propuesto (cada merge publica la landing en Vercel; antes,
Render sin redeploy automático):

1. #287 → #286 → #288 (o la candidata #290 de una vez, ver su descripción).
2. #289 (docs).
3. #291 (J4) → #292 (J5) → J7.

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

## Cómo reanudar

```bash
git fetch origin
git checkout claude/j7-app-first-modelo        # último bloque de código
python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q tests/test_app_first_modelo.py tests/test_app_first_ejecucion.py tests/test_efectos_arranque.py
(cd landing && npm ci && npx vitest run)
```

Siguiente bloque de código: J7.4 (acceso propio y bridge `/internal/app/*`),
según `APP-FIRST.md` § 10.

## Riesgos abiertos

- Las 3 suscripciones `active` de la BD pueden no reflejar Stripe (la BD dejó
  de recibir webhooks con la suspensión). Fuente de verdad: Stripe.
- Si las env `STRIPE_PRICE_*` están vacías en Vercel, la versión actual de
  `main` cobra con `price_data` inline: archivar precios no lo frena. Lo
  frena el PR de pausa o contener la clave (A6).
- Hasta el merge de la pausa, cada visita a `/checkout` en producción puede
  crear una sesión de pago real.
- `main` sigue con CI rojo (greenlet, cryptography, gitleaks) hasta que se
  integren #287/#286 y las huellas de `.gitleaksignore`.
- El repo es público: todo lo que se commitea (docs incluidos) es visible.
- La imagen Docker del backend no se ha construido aún en ninguna máquina
  con este código (el sandbox no tiene daemon); lo hará Hermes MSI.
- Un merge a `main` publica la landing en Vercel; si Render sigue
  enganchado al repo, también intentaría redesplegar el backend.
