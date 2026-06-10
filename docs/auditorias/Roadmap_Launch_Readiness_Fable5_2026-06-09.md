# ROADMAP A "COMPLETAMENTE LISTA PARA LANZAR" — Dona

**Lectura ejecutiva:** la arquitectura del core loop (diagnóstico→…→permiso→créditos→ejecución→medición→reporte) está bien diseñada, pero hoy **cada eslabón crítico del loop tiene su implementación rota**: *permiso* es evadible (C4), *créditos* no es atómico en ninguna dirección (C1/C5/C6), *ejecución* sale sin verificar opt-out (C3) y *medición/reporte* pueden perderse en silencio (C6/A12). El patrón raíz no son 22 bugs sueltos: son **3 patrones sistémicos** — fail-open por configuración (C8), check-then-act sin atomicidad (C1/C5/C9/A13/A6) y fuentes externas sin sanitizar (A3/A4). Atacar los patrones, no los síntomas.

---

## 1. BLOQUEADORES DUROS DE LANZAMIENTO

Orden de ataque por tema. Regla de priorización: **(a) lo que multiplica todo lo demás, (b) lo que genera pasivo legal per-evento, (c) lo que rompe dinero, (d) lo que rompe confianza.**

### TEMA 0 — Patrón fail-open sistémico (multiplica todo lo demás)

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 0.1 | Invertir lógica de entorno en TODOS los módulos: fail-closed por defecto, permisivo solo con `ENVIRONMENT in ("development","test")` explícito. Un solo helper compartido `is_dev()` | **C8** | **S** | Ninguna. **Hacer primero: es 1 día y cierra 6 agujeros a la vez** |
| 0.2 | Readiness check en startup: validar `STRIPE_WEBHOOK_SECRET`, `ENCRYPTION_KEY`, `INTERNAL_BRIDGE_SECRET`, secrets de inbound/Meta/state OAuth. Si falta uno en prod → el deploy NO levanta | **C8, A5, A6, A7** | **S** | 0.1 |
| 0.3 | Arranque de DB fail-closed: verificar tablas críticas (dedup, billing, transacciones) post-init y abortar o responder 5xx a webhooks; advisory lock en DDL | **A8** | **M** | 0.2 |
| 0.4 | `crypto.py` fail-closed: `cifrar()` lanza `CryptoError` (nunca persiste plaintext), `InvalidToken` capturado con ERROR+métrica; system prompt fail-closed si `prompts.yaml` no carga | **A5, A12** | **S** | 0.2 |

### TEMA 1 — Pipeline de webhooks y dedup (amplificador de dinero y TCPA)

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 1.1 | Dedup atómico: `INSERT ... ON CONFLICT DO NOTHING`, rowcount decide; `IntegrityError` = ya procesado; descartar `mensaje_id=""`; fallos de DB a WARNING+métrica | **C9** | **S** | 0.3 |
| 1.2 | ACK inmediato del webhook + procesamiento en background con referencia persistida (no fire-and-forget). Esto elimina la causa raíz de reentregas (90s síncronos vs timeout de 10-20s del proveedor) | **C9** | **M** | 1.1 |

### TEMA 2 — TCPA: el mayor pasivo legal per-evento del sistema

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 2.1 | **Gate centralizado `puede_enviar(telefono)` fail-closed** (opt-out + límite diario + quiet hours) implementado en el **proveedor como choke point** — ningún path de salida puede saltárselo por construcción: inbound webhook, sobrecarga, simulación, ejecutor HIGH, recordatorios | **C3** | **M** | 0.1 |
| 2.2 | STOP durable: persistir con retry y alerta ANTES de confirmar la baja al usuario | **C3** | **S** | 2.1 |
| 2.3 | Scheduler de recordatorios con `SELECT ... FOR UPDATE SKIP LOCKED` (claim atómico) — elimina duplicados multi-worker | **C3** | **S** | 0.3 |
| 2.4 | Recurrencias sub-diarias: `fecha_fin`/tope de ocurrencias obligatorio + avance de próxima ocurrencia `> now()` (mata el catch-up storm post-downtime) | **C3** | **S** | 2.3 |
| 2.5 | Opt-out de **terceros destinatarios** en el ejecutor HIGH + límite por destino | **C3** | **M** | 2.1 |

### TEMA 3 — Integridad de dinero (créditos = el contrato del producto)

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 3.1 | UNIQUE parcial en `stripe_session_id` + `IntegrityError`→skip; `EventoStripeProcesado` insertado ANTES del handler con PK como gate; tabla de invoices procesados con `invoice_id` PK (eliminar "último invoice") | **C1** | **M** | 0.3 |
| 3.2 | Exigir `payment_status=="paid"` y `mode=="payment"` antes de acreditar | **A11** | **S** | 3.1 |
| 3.3 | Ciclo de créditos de automation: UPDATE condicional + rowcount en todas las transiciones; `liberar()` con claim atómico e idempotente; `cobrar()` retorna `tx_id` (eliminar matching heurístico); **una sola capa dueña del ciclo** (resolver duplicación execution.py↔credits.py); marcador "side-effect ejecutado"→confirmar, nunca liberar; validar `costo>0`; límite de reintentos | **C5** | **L** | 0.3, 1.1 |
| 3.4 | UNIQUE en `idempotency_key` de acciones + UPDATE condicional en `_cambiar_estado`; deprecar `marcar_running` no atómico | **A13** | **S** | 3.3 |

### TEMA 4 — Costo LLM (sangrado económico inducible)

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 4.1 | Timeouts (`wait_for`) en TODAS las llamadas LLM + límite de tamaño de entrada (sin esto el fallback es teatro) | **C6** | **S** | Ninguna |
| 4.2 | Tope de profundidad (~5) en recursión de tool calls | **C6** | **S** | Ninguna |
| 4.3 | `cobrar_o_rechazar` al inicio de todo flujo caro (simulación, redes, generación principal), abortando fallbacks si el cobro falló — esto ES el eslabón créditos→ejecución del loop | **C6** | **M** | 3.3 |
| 4.4 | Circuit breaker de presupuesto diario (global + por usuario) y `registrar_uso_tokens` no-fire-and-forget con alerta — sin medición fiable, el loop medición→reporte miente | **C6** | **M** | 4.1 |

### TEMA 5 — Gates de permiso humano (el "permiso" del core loop)

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 5.1 | **Eliminar el atajo legacy** `confirmar_enviar_mensaje_whatsapp` (auto-approve + IDOR). El camino endurecido ya existe; el atajo lo anula | **C4** | **S** | Ninguna |
| 5.2 | `transicion_valida(actual, destino, riesgo)`: rechazar `→running` para CRITICAL siempre; HIGH exige confirmación dedicada; default HIGH/rechazo para tipos desconocidos; bloquear CRITICAL también en endpoints y en `aprobar_accion` | **C4, A13** | **M** | 3.4 |
| 5.3 | `!exec` fuera de WhatsApp (caller-ID spoofeable) → canal admin autenticado con `compare_digest` o 2º factor | **C4** | **S** | 5.2 |
| 5.4 | Enforcement server-side de `preparar_X/confirmar_X`: confirmación validada fuera del LLM, desde el último mensaje del usuario, nunca en el mismo turno; borradores en Postgres con TTL+nonce; ownership+actor en todas las operaciones del Action Center | **A4, A13** | **M** | 5.2 |
| 5.5 | Sanitización única para TODA fuente externa (Calendar/Contacts/Tasks/Vision/audio/MiroFish/perfil/filename) antes del LLM; nunca interpolar datos externos en la parte instruccional; delimitadores con nonce por request | **A3** | **M** | Ninguna (paralelo) |

### TEMA 6 — Identidad y vinculación de cuentas

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 6.1 | OAuth Google: link generado SOLO desde la conversación WhatsApp autenticada, token HMAC efímero single-use mapeado server-side; nonce invalidado al consumir; `html.escape()`+CSP en callback | **C7** | **M** | 0.2 |
| 6.2 | Dashboard: recovery condicionado a verificación de email/OTP; lockout fail-closed si bridge no configurado; contador atómico `ON CONFLICT DO UPDATE +1`; email normalizado en un punto único; HMAC con timestamp+path | **A6** | **M** | 0.2 |
| 6.3 | ADMIN_TOKEN solo por header Bearer; `/voice/reenviar` con `RequestValidator` Twilio fail-closed; eliminar default de Meta + `compare_digest`; tokens inbound con `key_version` revocable | **A7** | **M** | 0.2 |

### TEMA 7 — Privacidad CCPA/CPRA (no se puede operar en EEUU sin esto)

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 7.1 | Verified consumer request: export/delete iniciados solo desde el chat WhatsApp autenticado u OTP por ese canal (el teléfono NO es secreto) | **C2** | **M** | Ninguna |
| 7.2 | Tabla `privacy_requests` con timestamp/estado/SLA de 45 días + entrega real del export (link firmado expirante o job persistente) — eliminar la promesa falsa de email | **C2** | **M** | 7.1 |
| 7.3 | Lista canónica única de tablas-PII derivada de `Base.metadata` compartida por export y delete; delete fail-closed ante fallo parcial; match exacto (eliminar el `LIKE '%telefono%'` que borra datos ajenos) | **C2** | **M** | 7.2 |
| 7.4 | PII en logs: helper único `mask_phone()`, prohibir contenido conversacional en INFO, normalizar rutas (el token inbound en logs es **capacidad de envío** filtrada), eliminar `whapi.py:144` | **A1** | **M** | Ninguna (paralelo desde día 1) |
| 7.5 | DeepSeek: DPA o exclusión para payloads con PII; redactar system prompt en fallback; actualizar privacy notice | **A2** | **M** | Decisión de negocio, no solo ingeniería |
| 7.6 | Export financiero a Drive: permisos owner-only por default, link compartible solo vía preparar/confirmar | **A10** | **S** | 5.4 |

### TEMA 8 — Auditoría y degradación honesta

| # | Qué | Responde a | Esfuerzo | Dependencias |
|---|---|---|---|---|
| 8.1 | Audit trail: whitelist por tipo de evento, sanitizado recursivo, `default=str`, audit en misma transacción u outbox, audit HIGH incondicional, retención `max(dias,365)` — el audit trail es promesa de producto ("creditos enteros con audit trail"), no opcional | **A12** | **M** | 5.2 |
| 8.2 | Rate limiter: verificación por-usuario antes del cupo global, fallback degradado conservador con métrica, reconexión perezosa a Redis, member con uuid | **A9** | **S/M** | Ninguna |

---

## 2. FASES

### Fase 0 — Parar el sangrado (semana 1, ~1 semana)
**Contenido:** Tema 0 completo + 1.1 + 4.1/4.2 + 5.1 + 2.2 + freeze de marketing/adquisición.
**Criterio de salida:** ningún control de seguridad depende de un string de entorno; el deploy falla si falta un secret; un webhook duplicado no se reprocesa; un STOP nunca se confirma sin persistir; el atajo legacy no existe; ninguna llamada LLM puede colgar o recursar sin tope. *Todo esto es S salvo 0.3 — es la semana de mayor ROI de riesgo del proyecto.*

### Fase 1 — Hardening de dinero y ejecución (semanas 2-4)
**Contenido:** Temas 1 (resto), 3, 4 (resto), 5 (resto).
**Criterio de salida:** test de concurrencia que dispara el mismo webhook Stripe 10x en paralelo → exactamente 1 acreditación; ciclo de créditos con claim atómico en cada transición y una sola capa dueña; ninguna acción HIGH/CRITICAL ejecuta sin confirmación humana verificable server-side, incluso bajo inyección de prompt simulada (red team interno); presupuesto LLM con kill-switch probado. **El core loop permiso→créditos→ejecución queda íntegro por construcción.**

### Fase 2 — Cumplimiento y superficie (semanas 4-6, parcialmente paralelo a Fase 1)
**Contenido:** Temas 2 (resto), 6, 7, 8.
**Criterio de salida:** ningún envío saliente —de cualquier path— sale sin pasar por `puede_enviar()`; export/delete CCPA funcionan end-to-end con request verificado, SLA trackeado y entrega real; cero teléfonos completos ni contenido conversacional en logs de los últimos 7 días (verificado con grep automatizado en CI); OAuth no vinculable por terceros; decisión DeepSeek cerrada y reflejada en privacy notice; admin solo por header.

### Fase 3 — Escala y robustez (post-lanzamiento, continuo)
**Contenido:** medios (M1 resurrección de subs, etc.), `MultiFernet` con rotación de claves, Alembic formal, migración a cola real para procesamiento background, refinamiento de rate limiter (Lua/token bucket), observabilidad de modo degradado.
**Criterio de salida:** rolling deploys sin DDL races; rotación de claves ejecutada al menos una vez; dashboards de presupuesto LLM y modo degradado.

---

## 3. MEJORAS POST-LANZAMIENTO (importantes, no bloquean)

- **M1** — resurrección de suscripción cancelada por eventos fuera de orden (frecuencia baja, impacto acotado; sí antes de escalar volumen de subs).
- **MultiFernet/rotación de claves** (A5 parcial): el fail-closed sí bloquea; la rotación puede esperar semanas, no meses.
- **Rate limiter avanzado** (script Lua atómico, token bucket): el fix conservador de Fase 0/2 basta para el volumen inicial.
- **Alembic como paso formal de deploy** (A8 parcial): el advisory lock + verificación post-init bloquean; la migración a Alembic es deuda ordenada.
- **Cola real (no asyncio tasks)** para procesamiento background: el ACK inmediato + referencias persistidas bastan al inicio.
- **Revocación granular de tokens inbound** por usuario (A7 parcial): `key_version` global revocable es suficiente para lanzar.
- Word-boundary matching y refinamientos del guardrail multimodal (A4 parcial) más allá del fail-closed básico.

---

## 4. LO QUE YA ESTÁ BIEN (no romperlo)

- **El camino endurecido de confirmación existe y es correcto** (`approved` + literal `ENVIAR` + ownership): C4 es el atajo que lo anula, no el diseño. La corrección es eliminar bypasses, no rediseñar.
- **El claim atómico correcto ya existe en `action_center`** coexistiendo con el incorrecto — hay patrón de referencia interno para todo el Tema 3.
- **STOP antes de dedup es el orden legalmente correcto** (la auditoría lo confirmó como no-hallazgo). Mantenerlo.
- **Whapi implementa validación de firma** — solo confirmar wiring, no construir desde cero.
- **La arquitectura de idempotencia en capas (Stripe) es la correcta** — falla la atomicidad de cada capa, no el concepto.
- **Existe audit trail, cifrado Fernet, dedup, rate limiter, lockout, tokens inbound firmados, guardrails en prompts.yaml**: en cada área el *control existe*; el trabajo es convertir fail-open en fail-closed y check-then-act en atómico. Eso es mucho más barato que construir.
- **El delete CCPA conoce más tablas que el export** — esa lista es la semilla de la lista canónica (7.3).

---

## 5. ESTIMACIÓN Y RIESGO #1

**Estimación realista:** con 2-3 ingenieros senior dedicados, **6-8 semanas a launch-ready** (Fase 0: 1 semana; Fases 1-2 en paralelo parcial: 4-6 semanas; 1 semana de verificación adversarial: tests de concurrencia sobre dinero, red team de inyección sobre gates, grep de PII en logs, simulacro de CCPA request end-to-end). Con 1 solo ingeniero: 10-12 semanas. Los usuarios actuales pueden mantenerse **sin adquisición activa** tras completar Fase 0.

**Riesgo #1 si se lanza ya: TCPA (C3).** Es el único hallazgo con **daño estatutario per-mensaje ($500–$1,500), acumulativo, irreversible y demandable en class action** — y el sistema hoy lo multiplica activamente: scheduler sin lock duplica envíos, las recurrencias sin tope generan tormentas post-downtime, y el STOP fail-open hace que el usuario crea que se dio de baja mientras Dona le sigue escribiendo (el agravante perfecto ante un juez). Un solo usuario molesto con capturas de pantalla de mensajes post-STOP es una demanda que puede costar más que toda la ronda. C1/C5 pierden dinero recuperable; C2 genera riesgo regulatorio con plazo de gracia de facto; **C3 genera pasivo legal instantáneo en cada mensaje enviado**. Para un producto cuya tesis es *"agente que ejecuta acciones reales en tu nombre"*, perder el control de la ejecución saliente no es un bug: es la negación de la visión.
