# Dona: roadmap F1–F35 (para diseño UX/UI) · v3 (borrador)

Corte: 22 oct 2026 (ET). Fuente: repo `celestinojbm/Dona-agent`, revisado solo en lectura.

**Nota sobre las fuentes.** Busqué la numeración F1–F23 en tres sitios:
- Los PDF del plan: `docs/planes/Plan_Dona_v2_1_2026-04-30.pdf`, `plan-maestro-dona-2026-04-21.pdf` y `Plan_Dona_Refinado_v2_2026-04-29.pdf`, leídos con pdftotext.
- Los docs de `docs/`.
- Las descripciones de PRs.

Los PDF no usan códigos F. Se organizan por **Fases 1–9** (plan maestro) y por tareas T/G (plan refinado). Los códigos F solo aparecen en títulos y descripciones de PRs de oct 2026. No existe en el repo un documento que liste F1–F23 completo, así que no hay definición para las F que no tienen PR.

## Features

| F | Qué hace | Estado | Pantallas / flujos clave | Fuente |
|---|---|---|---|---|
| F1 | Autonomía por tipo de acción, niveles L1–L4. El modelo solo propone. Las acciones sensibles (permisos, credenciales, destructivas, envíos a terceros) siempre requieren confirmación humana. Toda autorización queda guardada, verificable y es de uso único | En curso: PR listo para revisión, checks en verde, no fusionado | Comandos `autonomía ver` / `autonomía <acción> nivel <N>`. Flujo preparar → confirmar. Subir de nivel pide confirmación; bajar es inmediato | PR #301 |
| F3 | Recibo por acción: acción, proveedores y modelos, coste base vs. observado, créditos, saldo resultante. Débito idempotente. No es factura fiscal | Hecha: fusionado el 21 oct; mostrar el recibo depende del flag `DONA_CREDIT_RECEIPTS_ENABLED` | Comandos `recibo <id>` / `último recibo`. Desglose por paso. Tarifa +30%. Retención de 90 días | PR #300; commit e2462b8 |
| F12 | Primer resultado en 5 minutos: onboarding hasta un resultado tangible (borrador de seguimiento) y medición del tiempo hasta el primer valor (TTFV). Créditos de bienvenida configurables | En curso: draft, checks en verde | Home con input hero "¿Qué quieres lograr hoy?" y chips solo de lo implementado (`primer-valor-hero.tsx`). Botones de al menos 44 px y foco visible | PR #303 |
| F14 | Plan vivo de tarea: pasos, coste máximo y destinatarios, actualizados en vivo. Si el plan cambia, hace falta una nueva autorización | En curso: draft, checks en verde | Panel "Dona trabajando…" (`plan-vivo-panel.tsx`): `aria-live`, estado en texto y no solo con color, pulso con `motion-reduce`. Checklist en WhatsApp (◻︎/▶︎/✅/⚠️) | PR #302 |
| F16 | Prompt estable con caché de Anthropic para bajar coste y latencia. No cambia la UX | Hecha: fusionado el 21 oct, apagado por defecto; caché real sin probar por presupuesto 0 USD | Ninguna, es backend | PR #299; commit bdaca89 |
| F23 | Selector y combinación de modelos: elegir modelo por chat o por agente, cambiarlo a mitad de conversación sin perder contexto, modo Auto por tarea y coste, planificar con uno y ejecutar con otro, comparar lado a lado, sugerencias | En curso: draft, checks en verde | `selector-modelo.tsx` (opciones con Auto y "recomendado"). `comparacion-modelos.tsx` (lado a lado con chips; estados vacío, carga y error). El recibo F3 muestra el modelo usado en cada paso. Referencias de UX en `docs/ux/f23-multi-model-referencias.md`, que está en la rama del PR | PR #306 |

Relacionados, sin código F: **0A** sistema visual oscuro aguamarina (tokens, `dona-btn`, `dona-input`, `dona-card`, `dona-badge`, `dona-modal`), en draft (PR #297). **0B** RLS en 47 tablas, fusionado (PR #298).

**Resumen:** 6 features definidas (F1, F3, F12, F14, F16, F23). Los códigos F2, F4–F11, F13, F15 y F17–F22 se eliminaron (ver más abajo).

## Decisiones de UX ya tomadas

- **App-first, WhatsApp secundario.**
  - El plan maestro de abril decía "WhatsApp ahora · App móvil + web en fase 6". La Fase 6 pedía paridad conversacional con WhatsApp, login por OTP y un dashboard con tareas, recordatorios y finanzas.
  - El rumbo cambió en oct: commit 8c8ed80 ("plan, respaldo/retiro, runbook MSI y diseño app-first"), con detalle en `docs/transition/dona-app-first/APP-FIRST.md`.
  - PRs del bloque: #293–#295 (UI `/app` del piloto con cuentas por invitación y demo sintético), todos en draft.
  - F23 dice explícitamente "Dona es app-first; esto vive en la app" (PR #306).
- **Riesgo y autonomía L1–L4** (PR #301):
  - L1: confirmar cada acción.
  - L2: automático bajo un umbral.
  - L3: ejecuta y notifica.
  - L4: automático dentro del tope del periodo.
  - Sin tope nunca hay autonomía ilimitada. Con el flag apagado, todo funciona como L1.
  - Siempre humanas: permisos, autonomía, credenciales, acciones destructivas y envíos a terceros.
  - F14 liga la confirmación a la versión y el hash del plan (PR #302).
- **Créditos y recibos (F3):**
  - Recibo por acción con desglose por paso.
  - Tarifa +30% y retención de 90 días (commit e2462b8, "respuestas Celestino").
  - Importes siempre como NUMERIC/string, nunca float.
  - No es factura fiscal (PR #300).
- **F23 multimodelo:**
  - Modo Auto, modelo recomendado, cambio sin perder contexto y comparación lado a lado.
  - Precios por modelo configurables. Claves solo en el backend (PR #306).
- **Stripe fuera de alcance y pagos pausados:**
  - Commit 92d0b22 "feat(landing): poner Dona en pausa y cortar cobros".
  - `docs/transition/dona-app-first/ESTADO.md` tiene la tabla de corte de cobros en Stripe con campos aún `_pendiente_`.
  - El PR de dependabot #234 (Stripe 15.x) sigue abierto y conviene cerrarlo.
  - Sin gasto en pruebas: F16 y F23 se probaron con 0 USD y proveedor simulado (commit bdaca89, PR #306).
- **Accesibilidad (se repite en todos los PRs):** foco visible, botones de al menos 44 px, estado en texto y no solo con color, `motion-reduce`, `aria-live`. Ver PRs #297, #302, #303 y #306.


---

## Decisiones confirmadas por Celestino el 22-oct

Celestino las confirmó en su chat el 22 oct 2026.

1. **Créditos únicos con presupuesto por agente.** Alerta al 80% y pausa al 100%. Corresponde a F32.
2. **Piloto solo con créditos de regalo simulados al registrarse.** Sin Stripe y con 0 USD. Encaja con la pausa de cobros (commit 92d0b22) y con los créditos de bienvenida de F12 (PR #303).
3. **WhatsApp solo para avisos y aprobaciones.** Corresponde a F35 y refuerza app-first.
4. **Orden de las nuevas features:** F25 rutinas → F28 memoria en capas → F27 entregables compartibles → F26 conectores/plugins → F24 computadora propia por agente.
5. **Autonomía L2 por defecto, ajustable por agente.** Cambia el comportamiento de F1: según el PR #301, con el flag apagado todo funciona como L1.
6. **F23:** modo automático por tarea, elección manual por agente o chat, y combinación de modelos donde uno trabaja y otro revisa. El PR #306 implementa "uno planifica, otro ejecuta" y "comparar lado a lado"; el patrón "uno revisa" queda como trabajo futuro, en un PR aparte.
7. **Piloto de uso interno.**

## Fuente de F24–F35

Canvas "Dona vs plataformas de agentes IA 2026" (https://cursor.com/canvas/store-46fa6d6e-5038-406d-972a-b16e05470a6e/d8e50ce7-67af-46f6-91a8-79389512ebc6), leído el 22 oct 2026. Es un análisis competitivo con propuestas; no son specs del repo. El propio canvas sugiere que los huecos F2–F22 pueden absorber estas piezas.

## Lista limpia priorizada

| # | Código | Nombre | Estado | Fuente |
|---|---|---|---|---|
| 1 | F3 | Recibo por acción y débito idempotente (+30%, 90 días) | Hecha | PR #300, commit e2462b8 |
| 2 | F16 | Prompt estable con caché (backend) | Hecha (apagada por defecto) | PR #299 |
| 3 | F1 | Autonomía L1–L4 por acción (se fusiona con L1; L2 por defecto va en un PR aparte) | En curso, PR listo para revisión | PR #301; decisión 5 |
| 4 | F14 | Plan vivo de tarea | En curso (draft) | PR #302 |
| 5 | F12 | Primer resultado en 5 minutos (créditos de regalo simulados) | En curso (draft) | PR #303; decisión 2 |
| 6 | F23 | Multimodelo: Auto, elección manual, combinación de modelos | En curso (draft) | PR #306; decisión 6 |
| 7 | F32 | Créditos únicos con presupuesto por agente (80% alerta / 100% pausa) | Pendiente | Canvas; decisión 1 |
| 8 | F35 | Canales secundarios: WhatsApp solo para avisos y aprobaciones | Pendiente | Canvas; decisión 3 |
| 9 | F25 | Rutinas programadas y disparadores | Pendiente | Canvas; decisión 4 |
| 10 | F28 | Memoria en capas (organización, proyecto, agente), editable y con olvido | Pendiente | Canvas; decisión 4 |
| 11 | F27 | Entregables compartibles (páginas, docs, slides, hojas) | Pendiente | Canvas; decisión 4 |
| 12 | F26 | Conectores MCP y plugins | Pendiente | Canvas; decisión 4 |
| 13 | F24 | Computadora propia por agente, con vista en vivo y replay | Pendiente | Canvas; decisión 4 |
| 14 | F30 | Plantillas de empresa en el onboarding (amplía F12) | Pendiente, sin priorizar | Canvas |
| 15 | F29 | Orquestador con subagentes en paralelo | Pendiente, sin priorizar | Canvas |
| 16 | F34 | Registro de auditoría y replay exportable | Pendiente, sin priorizar | Canvas |
| 17 | F33 | Toma de control del navegador del agente | Pendiente, sin priorizar (depende de F24) | Canvas |
| 18 | F31 | Voz: dictado, modo conversación y llamadas | Pendiente, sin priorizar | Canvas |

Criterios del orden:
- Primero lo hecho y lo que está en curso.
- Después F32 y F35, porque el piloto los necesita (decisiones 1 a 3).
- Luego el orden de la decisión 4.
- El resto sigue el orden rápido/impacto del canvas.

Relacionados, sin código F: 0A sistema visual (draft, PR #297) y 0B RLS (hecho, PR #298).

## Códigos eliminados

Se eliminaron F2, F4–F11, F13, F15 y F17–F22 porque no tienen definición en ninguna fuente. Lo decidió Celestino el 22-oct. No se renumera nada: los códigos existentes se mantienen.

## Trabajo futuro: PRs en borrador aparte

- **L2 por defecto**, después de fusionar #301. El #301 entra con L1 por defecto; este PR cambia el nivel por defecto a L2, ajustable por agente (decisión 5).
- **Revisión entre modelos**, después de #306. Un modelo trabaja y otro revisa (decisión 6).

## F28 · Subsección: memoria de intenciones mencionadas una sola vez (aprobada por Celestino el 22-oct)

Origen: sección "Propuestas de la vigilancia diaria" del canvas "Dona vs plataformas de agentes IA 2026" (22 oct 2026). Según lo reportó Grok Bot, sin verificar: Muse de Meta es un agente personal en su propia VM que actúa sobre algo que el usuario mencionó una vez y pide confirmación antes de comprar.

- **Qué es.** Dona guarda como "intención" algo que el usuario dijo de pasada (por ejemplo, "tengo que renovar el dominio en noviembre") y más adelante lo propone como sugerencia o como borrador de rutina (F25).
- **Nunca ejecuta sola.** Una intención no es una autorización. Para actuar sobre ella se sigue el flujo de F1, preparar → confirmar, con el nivel L1–L4 del agente. Todo gasto y todo envío a terceros pide siempre aprobación humana. Una intención nunca puede subir el nivel de autonomía.
- **Privacidad.** Es visible y editable en la pantalla Memoria de la app, en la capa de agente o proyecto. Cada intención tiene vencimiento (propuesta: 30 días si no se confirma). Se puede borrar o apagar por agente. No guarda datos sensibles: salud, credenciales ni datos de pago.
- **Falsos positivos.** Dona solo la propone como un chip "¿Lo recuerdo?" que el usuario acepta. Si no lo acepta, no se guarda. Cada sugerencia muestra la frase de origen.
- **Coste.** Apagada por defecto, con su propio flag. En el piloto se prueba con proveedor simulado (0 USD, sin pruebas pagadas). En producción consume créditos del presupuesto del agente (F32).
- **Canales.** Va en la app (app-first). WhatsApp solo avisa o pide la aprobación (F35).
