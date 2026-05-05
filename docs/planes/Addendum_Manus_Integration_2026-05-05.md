# Addendum — Integración de referencia Manus en Dona

**Fecha:** 5 de mayo de 2026
**Tipo:** Addendum estratégico · sin código · sin deploy
**Vigente con:** `Plan_Dona_v2_1_2026-04-30.pdf` · **no lo reemplaza**, lo extiende

---

## 1. Decisión estratégica

Este documento integra la referencia **Manus** (agente generalista
basado en prompts) al ADN de Dona, **sin convertirla en Manus**.

- **No copiar Manus.** No queremos un agente generalista que ejecute
  cualquier prompt en sandbox.
- **Tomar la capacidad de ejecución.** La pieza valiosa de Manus es
  que ejecuta tareas reales (browser, archivos, automation) y entrega
  resultados, no solo respuestas.
- **Adaptarla al ADN de Dona.** Esa capacidad debe operar dentro del
  marco que Dona ya construyó: WhatsApp como canal, diagnóstico
  guiado, permisos explícitos, créditos como capacidad operativa,
  Tool Intelligence Layer, Action Center.

### Frase guía

> *"Manus convierte prompts en entregables. Dona debe convertir
> situaciones, recursos y objetivos en sistemas activos, autorizados
> y medibles de crecimiento."*

---

## 2. Continuidad con lo ya planificado

Este addendum **NO sustituye** ninguno de los compromisos vigentes:

- ✅ Plan v2.1 (`Plan_Dona_v2_1_2026-04-30.pdf`) sigue activo.
- ✅ Phase 0 (PRs T0.x) cerrada y desplegada.
- ✅ Phase 1 en curso: T1.3 (Stripe), T1.4 (dashboard), T1.5 (portal)
  ya en producción. T1.6 / T1.7 / T2.0 pendientes según roadmap actual.
- ✅ Tool Intelligence Layer y Action Center ya estaban en el Plan v2.1.

Las ideas Manus se agregan como **prefijo M (Manus-inspired)** al
backlog, paralelo o posterior a las T existentes según prioridad.

---

## 3. Conceptos integrados (7 piezas)

### 3.1 Dona Playbooks (vs Agent Skills de Manus)

**Manus**: el usuario escribe un prompt y Manus elige qué skills usar.

**Dona**: el usuario describe una situación (no un prompt). Dona
detecta qué playbook aplica y lo guía paso a paso desde WhatsApp.

**Diferencia clave**: el usuario de Dona **no necesita saber qué
prompt escribir**. Eso es feature, no bug — los emprendedores latinos
de WhatsApp no son power-users de IA.

**Mecánica**:
- Cada playbook tiene fases secuenciales con confirmación humana entre
  pasos (patrón `preparar_X` / `confirmar_X` de CLAUDE.md).
- Cada paso declara su costo en créditos antes de ejecutar (transparencia).
- Cada paso registra audit_log + outcome.
- Al final, el playbook entrega un resultado **medible** (lead capturado,
  oportunidad identificada, oferta vendida) — no un PDF huérfano.

### 3.2 Execution Sandbox (créditos · permisos · audit log)

**Manus**: VM aislada por sesión, sin restricciones de permisos
visibles para el usuario.

**Dona**: cada acción de tool corre dentro de un sandbox lógico con:
- **Créditos**: la acción solo arranca tras `cobrar_o_rechazar()`. La
  capacidad operativa la representan los créditos (T1.3 ya en
  producción).
- **Permisos**: el usuario otorga permisos por categoría
  (browser-readonly, browser-form-fill, browser-transactional,
  email-send, calendar-modify, etc.). Ya está la base con OAuth
  selectivo de Google.
- **Audit log**: cada acción deja una fila en `transacciones_credito`
  + entradas en logging estructurado. Reusa T1.3.

**Adición vs lo existente**: introducir **niveles de riesgo** como
dimensión transversal del catálogo de tools.

### 3.3 Browser Operator (controlado por niveles de riesgo)

**Manus**: navega, hace clicks, llena formularios, en cualquier sitio.

**Dona**: 3 niveles definidos:

| Nivel | Permite | Ejemplo | Autorización |
|---|---|---|---|
| L1 read-only | Scraping de info pública | "ver precios de la competencia en sitio X" | Implícita por el playbook activo |
| L2 form fill | Llenar formularios sin pago | "responder al lead en form de contacto" | Preview + confirmación humana por WhatsApp |
| L3 transactional | Comprar, pagar, login con credenciales del usuario | "reservar dominio en Namecheap" | Doble confirmación + permiso guardado + límite de gasto |

**Encaja con**:
- Patrón `preparar_X` / `confirmar_X` de CLAUDE.md (irreversibles
  exigen confirmación).
- Approval gates del Plan v2.1.

### 3.4 Builder de activos orientado a crecimiento (no webs genéricas)

**Manus**: genera webs, scripts, archivos como artifacts.

**Dona**: cada activo nace **dentro de una iniciativa con KPI**.

| Activo Manus genérico | Activo Dona orientado a crecimiento |
|---|---|
| "Crea una landing" | "Landing para capturar 50 leads esta semana de la oferta X, con form que dispara el playbook de cualificación" |
| "Hazme un script" | "Automatiza la conciliación de pagos de la cuenta X cada lunes y avísame si hay anomalías" |
| "Genera un slide" | "Propuesta comercial para cliente X con tracker de envío/lectura/respuesta y CTA medible" |

**Regla**: ningún activo se entrega sin estar conectado a una
iniciativa con KPI.

### 3.5 Wide Research como Motor de Oportunidades

**Manus**: research deep, output enciclopédico.

**Dona**: research **rankeado y accionable**.

**Outputs típicos**:
- Tabla de competidores con precio, propuesta, debilidad, oportunidad
  para Dona.
- Lista de palabras clave con volumen / intención / esfuerzo / acción
  sugerida.
- Lista de leads potenciales con score y siguiente paso recomendado.

**Diferencia con Manus**: el output siempre incluye una columna
"acción siguiente" + costo en créditos para ejecutarla.

### 3.6 Documentos como activos accionables

**Manus**: PDFs y slides son artifacts terminales.

**Dona**: cada PDF / slide / propuesta es **un nodo dentro de una
iniciativa**. El documento incluye:
- Tracker de envío (¿se entregó?).
- Tracker de lectura (¿se abrió?).
- Tracker de respuesta (¿hubo CTA?).
- Acción siguiente sugerida si no hubo respuesta en N días.

Se conectan al Action Center: si el documento queda sin respuesta,
aparece como item pendiente con sugerencia de seguimiento.

### 3.7 Workspace vivo + Action Center

**Manus**: cada sesión es un workspace nuevo desechable.

**Dona**: el workspace **es el negocio del usuario**, persistente y
vivo. T1.4 ya empezó (saldo, plan, transacciones). El roadmap completo:

- **Workspace vivo**: estado actual del negocio (no estático).
  Iniciativas activas, KPIs, alertas, oportunidades detectadas por
  Wide Research.
- **Action Center**: cola priorizada de cosas que requieren al usuario.
  Cada item lleva: descripción, costo en créditos, nivel de
  autorización requerido, deadline si aplica.

**Encaja con**: Dashboard T1.4 ya tiene la estructura base
(`/api/dashboard-data`). Extender en T2.x para sumar Action Center
como sección.

---

## 4. Mapping con planificación existente

Tabla de cómo cada concepto Manus se conecta al backlog Dona vigente:

| Concepto Manus | Pieza Dona existente | Estado | Relación |
|---|---|---|---|
| Agent Skills | Playbooks | Concepto nuevo | M1 backlog |
| Sandbox sin créditos | `cobrar_o_rechazar()` + audit log | ✅ producción | Reusa |
| Browser tools sin niveles | Approval gates · `preparar_X`/`confirmar_X` | ✅ patrón existente | Extender con niveles |
| Web builder genérico | Builder orientado a iniciativas | Concepto nuevo | M3 backlog |
| Wide Research | Motor de Oportunidades | Concepto nuevo | M3 backlog |
| Documentos como artifacts | Documentos accionables (PDF + tracker) | Parcial: ya hay PDFs en /admin | Extender con tracker |
| Workspace efímero | Dashboard + Workspace vivo | T1.4 base · T2 extensión | Extender |
| Action Center | Action Center | Concepto nuevo | M4 backlog |

---

## 5. Backlog priorizado · prefijo M (Manus-inspired)

> Convención: **M0 → M4**, paralelo o posterior a T1.x / T2.x del Plan
> v2.1. NO sustituye nada del backlog T.x.

### M0 — Foundations (puede solaparse con T1.6 actual)

| Ticket | Título | Encaja con | Estimación |
|---|---|---|---|
| M0.1 | Catálogo de tools con nivel de riesgo declarado | Tool Intelligence Layer (Plan v2.1) | S |
| M0.2 | Permisos por categoría guardados en backend (browser-readonly, browser-form, etc.) | Approval gates existentes | M |
| M0.3 | Métricas y costos por tool en `/admin/metrics` | T1.6 observabilidad propuesta | S |

### M1 — Playbooks v1 (después de T1.6 / T2.0)

| Ticket | Título | Estimación |
|---|---|---|
| M1.1 | Playbook engine — estado persistente, pasos secuenciales con confirmación, integración con `preparar_X`/`confirmar_X` | L |
| M1.2 | Playbook **Diagnóstico de negocio por WhatsApp** (end-to-end, primer playbook completo) | M |
| M1.3 | Playbook **Mapa de oportunidades** | M |
| M1.4 | Playbook **Plan de contenido 7 días** (low-risk, alto valor percibido) | S |

### M2 — Browser Operator

| Ticket | Título | Estimación |
|---|---|---|
| M2.1 | Browser L1 read-only — scraper headless con timeout y rate limit, output structurado | M |
| M2.2 | Browser L2 form fill — preview HTML + confirmación humana por WhatsApp | L |
| M2.3 | Browser L3 transactional — credenciales en vault, doble confirmación, límite de gasto por sesión | XL |

### M3 — Builder + Wide Research

| Ticket | Título | Estimación |
|---|---|---|
| M3.1 | Builder activo: **Landing simple + formulario** atado a iniciativa con KPI | L |
| M3.2 | Wide Research → tabla rankeada de competencia / leads / palabras clave | L |
| M3.3 | Documentos accionables: PDFs con tracker de envío / lectura / respuesta | M |

### M4 — Action Center + Workspace vivo

| Ticket | Título | Estimación |
|---|---|---|
| M4.1 | Action Center: cola priorizada de items pendientes con costo + nivel de autorización | M |
| M4.2 | Workspace vivo: KPIs + iniciativas activas + oportunidades detectadas | L |
| M4.3 | Playbook **Reactivación de clientes** | M |
| M4.4 | Playbook **Reporte semanal de métricas** automático | S |

---

## 6. Riesgos y conflictos detectados

| Riesgo | Severidad | Notas / Mitigación |
|---|---|---|
| Scope creep · Dona se vuelve generalista por error | Alta | El "Qué NO copiar" (sección 7) es vinculante. Cada ticket M nuevo se valida contra esa lista antes de entrar a backlog activo. |
| M2 Browser Operator se acerca a Manus genérico | Media | Los 3 niveles de riesgo + integración obligatoria con un playbook activo lo mantienen vertical. Sin browser standalone tipo "Dona, navega lo que quieras". |
| Costos: cada módulo M necesita pricing/créditos definido antes de implementar | Funcional | Definir matriz "tool × créditos" en M0.3 antes de M1+. |
| Sobrecarga del usuario · demasiadas opciones de playbook | Media | Empezar con 1 playbook completo (M1.2 Diagnóstico) antes de sumar 6 más. |
| Carga operativa · Dona ya en producción con primer usuario | Media | Cada M se valida con prueba real antes del siguiente. No batch deploys de M2+M3 juntos. |
| Conflicto con T1.6 (observabilidad) · M0.3 podría duplicar trabajo | Bajo | M0.3 = parte de T1.6, mismo PR. |
| Promesas comerciales: "Manus para negocios" puede sonar a copy | Baja | Comunicación pública evita comparación directa. Hablar de capacidades, no de competidores. |

---

## 7. Qué NO copiar de Manus (anti-patterns vinculantes)

Estas reglas son **bloqueadoras** para cualquier ticket M:

| Anti-pattern | Razón |
|---|---|
| Exigir que el usuario sepa qué prompt escribir | Los emprendedores de WhatsApp no son power-users. Dona detecta la situación y propone el playbook. |
| Prometer autonomía total sin permisos fuertes | Cada acción con efecto irreversible exige autorización explícita. Sin excepciones. |
| Lanzar herramientas por moda sin métrica | Cada tool nueva debe declarar su costo, su nivel de riesgo y al menos un playbook que la consume. |
| Vender resultados financieros garantizados | Dona acelera y mide; no garantiza ROI. Comunicación honesta (T2.0 onboarding lo refuerza). |
| Crear assets desconectados de una iniciativa medible | Regla de la sección 3.4: ningún activo sin KPI. |
| Ocultar costos al usuario | Cada paso de playbook declara créditos ANTES de ejecutar. Transparencia es feature. |

---

## 8. Playbooks iniciales recomendados (M1+)

Los 7 que listó el owner, ya con encuadre y créditos estimados:

| # | Playbook | Cuándo aplica | Ticket | Créditos estimados |
|---|---|---|---|---|
| 1 | **Diagnóstico de negocio por WhatsApp** | Onboarding · primer mes | M1.2 | 30–80 según profundidad |
| 2 | **Mapa de oportunidades** | Tras diagnóstico · mensual | M1.3 | 50–120 |
| 3 | **Oferta inicial vendible** | Tras diagnóstico · negocios sin oferta clara | (M3 dep.) | 80–150 |
| 4 | **Landing simple + formulario** | Tras oferta vendible | M3.1 | 100–200 |
| 5 | **Reactivación de clientes** | Mensual · negocios con base de clientes | M4.3 | 60–120 |
| 6 | **Plan de contenido 7 días** | Semanal | M1.4 | 30–60 |
| 7 | **Reporte semanal de métricas** | Semanal · automático tras opt-in | M4.4 | 10–20 (automatizable) |

> Las cifras son estimaciones para sizing; se calibran en M0.3 cuando
> haya métricas reales de costo de cada tool.

---

## 9. Lo que NO se implementó en este turno

- ✅ Cero código nuevo en `agent/`, `landing/`, `tests/`, `alembic/`.
- ✅ Cero cambios de env vars (Render, Vercel, locales).
- ✅ Cero modificaciones a Stripe Dashboard, base de datos, servicios externos.
- ✅ Cero deploys.
- ✅ Cero merges automáticos.
- ✅ Cambios locales no relacionados (T1.5 PDFs untracked en `docs/auditorias/`) **no fueron tocados**.

Solo se creó este documento + entry correspondiente en
`docs/planes/README.md`.

---

## 10. Siguiente paso recomendado

1. **Owner revisa el addendum**, ajusta o aprueba.
2. Si aprueba, M0.1 / M0.2 / M0.3 se pueden implementar **dentro de
   T1.6** (observabilidad mínima) con un poco más de scope, sin sumar
   un PR aparte. Eso lo deja listo el catálogo + permisos antes de M1.
3. M1 (Playbooks engine + Diagnóstico) entra **después de T1.7
   (top-ups)** o **después de T2.0 (onboarding premium)**, decisión
   owner según qué bloquee más al primer usuario.
4. M2–M4 quedan en backlog estratégico, sin compromiso de fecha hasta
   tener M1 funcionando con un playbook real en producción.

### Cuándo mergear este addendum al repo

Si el owner aprueba, puede ir como un PR pequeño
`pr/addendum-manus-integration` que:
- Agrega `docs/planes/Addendum_Manus_Integration_2026-05-05.md`.
- Actualiza `docs/planes/README.md` con la entry del addendum.
- (Opcional) PDF generado del addendum en mismo PR para archivo
  permanente.

No requiere Stripe Dashboard, env vars, deploy ni cambios de código.

---

*Documento generado el 2026-05-05 por Claude Code (Opus 4.7) en sesión
con el owner. Addendum estratégico · sin código · sin deploy · sin
modificaciones a infraestructura externa. Vigente con
Plan_Dona_v2_1_2026-04-30.pdf · no lo reemplaza.*
