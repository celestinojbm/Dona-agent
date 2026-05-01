# Matriz comparativa — herramientas creativas

> Tabla viva. Cada cambio requiere actualizar la ficha individual en
> `docs/tools/<slug>.md` y el changelog al pie.

---

## Categoría: Imagen

| Herramienta | En Dona hoy | Costo aprox. | Commercial-safe | Fortalezas | Decisión |
|---|---|---|---|---|---|
| Google Gemini Flash Image (nano-banana) | **Integrada** | bajo | parcial | velocidad, costo | mantener (tier Premium) |
| Google Gemini Pro Image | **Integrada** | medio | parcial | calidad media | mantener (fallback de Ideogram) |
| Ideogram | **Integrada** | medio (~$0.025) | parcial | tipografía legible | mantener (tier Premium para logos/posters) |
| Adobe Firefly | Documentada, no integrada | $0.02–$0.10 | **sí (clearance Adobe Stock)** | calidad editorial, IP segura | PoC pendiente (Pro/Enterprise) |
| Higgsfield Soul | Documentada, no integrada | pay-per-use | no garantizado | character consistency | PoC pendiente |
| Midjourney | No integrada | medio | **no** | estética | descartada para producción comercial |

## Categoría: Video / motion ads

| Herramienta | En Dona hoy | Costo aprox. | Commercial-safe | Fortalezas | Decisión |
|---|---|---|---|---|---|
| Replicate Seedance-1-lite | **Integrada** | ~$0.05/video | parcial | rápido, barato | mantener |
| Replicate Veo 3 | **Integrada** | medio-alto | parcial | calidad alta, audio | mantener |
| HeyGen | **Integrada** | medio | sí | avatares con voz | mantener |
| Higgsfield DoP | Documentada, no integrada | pay-per-use | no garantizado | image-to-video cinematic | PoC pendiente |
| Runway | No evaluada | alto | sí | timeline, edición pro | evaluar después de Higgsfield |

## Categoría: Voz / TTS

| Herramienta | En Dona hoy | Costo aprox. | Fortalezas | Decisión |
|---|---|---|---|---|
| ElevenLabs | **Integrada** | freemium → pago | calidad multilingüe | mantener |
| OpenAI TTS-1 | **Integrada** | bajo | rápido, barato | mantener (fallback) |

## Categoría: LLM

| Herramienta | En Dona hoy | Decisión |
|---|---|---|
| Anthropic Claude Sonnet 4.6 | **Integrada (principal)** | mantener |
| OpenAI GPT-4o | **Integrada (fallback)** | mantener |
| DeepSeek | **Integrada (fallback)** | mantener |
| Anthropic Claude Haiku | **Integrada (haiku para tareas baratas)** | mantener |

## Categoría: Edición específica

| Herramienta | En Dona hoy | Decisión |
|---|---|---|
| Photoroom (background remove) | **Integrada** | mantener |
| Adobe Photoshop API | Documentada via Firefly Services | PoC con Firefly |

## Categoría: Documentos

| Herramienta | En Dona hoy | Decisión |
|---|---|---|
| reportlab (PDF Python) | **Integrada** | mantener (genera factura/cotización) |

---

## Cómo usar esta matriz

1. **Antes de proponer una integración nueva**: localizar la categoría,
   verificar si el problema ya está cubierto; abrir ficha en
   `docs/tools/<slug>.md`.
2. **Antes de cobrar a un cliente por un asset**: validar que la
   herramienta de la cadena tenga columna "Commercial-safe = sí" — sino,
   buscar fallback Adobe Firefly o equivalente.
3. **Cada workflow del Orchestrator** debe declarar qué herramienta de cada
   categoría usa, en qué orden, y cuál es su fallback.

---

## Changelog

- **2026-04-30** — Creación de la matriz. Adobe Firefly y Higgsfield añadidos
  como documentados pero no integrados.
