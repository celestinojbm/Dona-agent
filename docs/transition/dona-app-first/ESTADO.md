# Estado de la transición — Dona app-first

Fuente de verdad del avance. Cuatro estados:

- **Hecho**: en `main` (y, si aplica, verificado en producción).
- **Probado**: en una rama/PR, con pruebas locales y/o CI en verde; falta merge.
- **Preparado**: documento o instrucción lista; falta que alguien lo ejecute.
- **Bloqueado**: depende de una decisión o acción de Celestino.

Sin identificadores privados (IDs de cliente, emails, teléfonos, claves,
hostnames internos).

Última actualización: 2026-10-08 · base `main` = `958b525`.

---

## J1 — Corte de cobros y página de pausa

| Elemento | Estado | Dónde |
|---|---|---|
| Checklist urgente de Stripe | **Preparado** | `ACCIONES-CELESTINO.md` § A |
| Ejecución del checklist en Stripe (cuenta Stravos, live) | **Bloqueado** (Celestino) | registrar resultado abajo |
| PR "Dona en pausa" (landing) | **Probado** | rama `claude/happy-babbage-bs15fv` |
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

| Bloque | Estado |
|---|---|
| J2 Respaldo y retiro de servicios antiguos | Pendiente (inventario lo hace Celestino) |
| J3 Repositorio sano y dependencias (#287 → #286 → #285) | Pendiente |
| J4 Backend arranca sin efectos externos | Pendiente |
| J5 Paquete de instalación en la MSI | Pendiente |
| J6 Conectividad y validación en la MSI | Pendiente |
| J7 Base de Dona app-first | Pendiente |
| J8 Piloto privado y relanzamiento | Pendiente |

## Riesgos abiertos

- Las 3 suscripciones `active` de la BD pueden no reflejar Stripe (la BD dejó
  de recibir webhooks con la suspensión). Fuente de verdad: Stripe.
- Si las env `STRIPE_PRICE_*` están vacías en Vercel, la versión actual de
  `main` cobra con `price_data` inline: archivar precios no lo frena. Lo
  frena el PR de pausa o contener la clave (A6).
- Hasta el merge de la pausa, cada visita a `/checkout` en producción puede
  crear una sesión de pago real.
- Un merge a `main` publica la landing en Vercel; si Render sigue
  enganchado al repo, también intentaría redesplegar el backend.
