# F23 · Estudio de referencia: selector y combinación de modelos

**Fecha:** 2026-10-21 · **Para:** diseñar el selector/combinación de modelos de
Dona (app-first). Síntesis de cómo lo resuelven Cursor, Claude Desktop, ChatGPT,
Manus y Relevance AI, con detalles de UI accionables. Complementa el informe REA
(`rea-dona/informes/rea-referencias-dona.md`); ese informe **no** se versiona en
este repo. No se copian recursos de las referencias: se reinterpretan a la
identidad de Dona (negro + aguamarina `#00E5B0`).

## 1. Patrones de selección de modelo

| Producto | Dónde vive el selector | Modo Auto | Cambio a mitad de chat | Combinación |
|---|---|---|---|---|
| **Cursor** | Dropdown junto al input del chat/agente; "Auto" como opción destacada | Sí ("Auto" elige modelo) | Sí, el contexto del chat se mantiene | Agentes host/worker separados |
| **Claude Desktop** | Selector por conversación (menú compacto) | No explícito | Sí, por conversación | Plugins/skills, no modelos combinados |
| **ChatGPT** | Picker arriba del hilo; submodos (Auto/Thinking) | Sí (Auto enruta por dificultad) | Sí, sin perder el hilo | — |
| **Manus** | Catálogo "All models" + elección por tarea | Implícito por tarea | Sí (tarea con su contexto) | Multi-agente Planner/Ejecución |
| **Relevance AI** | Modelo por agente/tool | Por configuración | Entre pasos del workflow | Cadenas de agentes, autonomía L1–L4 |

**Lecciones para Dona:**
- El selector vive **por chat y por agente** (dos scopes), como Cursor/Relevance.
  → tabla `preferencia_modelo(scope, scope_id)`.
- "Auto" es **una opción más del grupo** (no un toggle aparte), primera en la
  lista, con copy que explica el criterio: *"Auto (elige por tarea y coste)"*.
- Cambiar de modelo **no reinicia el hilo**: el historial es model-agnostic; sólo
  cambia quién atiende el próximo turno (lo implementa `cambiar_modelo`).

## 2. Detalles de UI (espaciado, animación, copy)

- **Espaciado:** filas de opción ≥44px (target táctil), padding interno 12–16px,
  gutter de 8px entre chips. Panel con `--radius-lg` (16px) y borde de luz
  `rgba(255,255,255,.08)` sobre `#0A0A0A` (no sombra: en negro la jerarquía es
  luz de borde).
- **Estado activo:** borde + fondo aguamarina al 10–12% (`aria-checked`), nunca
  sólo color — se refuerza con el badge de texto "recomendado".
- **Animación:** hover 120ms; el "pensando/streaming" usa pulso aguamarina al
  ~12% de opacidad; **`prefers-reduced-motion` desactiva el pulso** (queda el
  color fijo). Entradas `cubic-bezier(0.2,0,0,1)`.
- **Copy (español, imperativo, cálido):**
  - Selector: "Modelo de este chat".
  - Auto: "Auto (elige por tarea y coste)".
  - Recomendado: badge "recomendado".
  - Comparar: "Elige dos modelos para comparar sus respuestas lado a lado.",
    botón "Usar esta".
  - Cambio a mitad de chat: "Cambié a {modelo}. Seguimos con el mismo contexto."

## 3. Estados vacío / carga / error

| Estado | Patrón | Copy |
|---|---|---|
| Vacío (comparación) | Texto + CTA, sin columnas | "Elige dos modelos para comparar sus respuestas lado a lado." |
| Cargando (por columna) | Esqueleto `bg-white/5` con pulso (reduced-motion: sin pulso) | (sin texto; nunca spinner solo) |
| Error (por columna) | Mensaje `--danger` con `role="alert"`, la otra columna sigue | "No pude obtener la respuesta de {modelo}. Reintenta o usa la otra." |
| Modo Auto eligiendo | Badge "recomendado" + razón breve | "Elegí {modelo} por {razón}." |
| Combinación en curso | Reusa el plan vivo (F14) en la app: paso + modelo por paso | "Planeando con {A}, ejecutando con {B}…" |

## 4. Modo Auto y combinación (cómo lo aterriza Dona)

- **Auto** (determinístico, 0 USD): elige por **clase de tarea** y **coste**
  (`elegir_auto`): tareas potentes (planificación/razonamiento) → el modelo más
  capaz si hay presupuesto; tareas baratas o presupuesto ajustado → el más
  barato que sirve. La UI muestra el modelo elegido y la razón.
- **Combinar** (como Manus Planner/Ejecución y Cursor host/worker):
  - *Plan + ejecución*: un modelo planifica, otro ejecuta cada paso.
  - *Comparar lado a lado*: dos modelos responden lo mismo; el usuario elige.
  - En ambos se **registra el modelo por paso** → el recibo (F3) muestra qué
    modelo se usó en cada paso (`pasos_para_recibo` → `linea_paso`/`desglose`).

## 5. Sugerencias (chips)

Reinterpreta las "respuestas sugeridas" de ChatGPT/Relevance:
- **Respuestas sugeridas** (chips cortos, acción inmediata): p. ej. "Confirmar",
  "Ajustar el tono", "Acortar".
- **Siguientes acciones** (chips de acción de negocio): "Enviar borrador",
  "Programar recordatorio", "Ver recibo".
- **Modelo recomendado**: el de `elegir_auto` para la clase de tarea actual.
Todo determinístico por defecto (sin gasto); una versión futura podría pedir las
sugerencias a un modelo.

## 6. Arquitectura (capa común de proveedores)

- Interfaz única `ProveedorModelo.generar(...)`; adaptadores Anthropic / OpenAI /
  Google. **Claves sólo en variables de entorno del backend** (`ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `GEMINI_API_KEY`); nunca en el front ni en el código.
- **Precios por modelo configurables**: tabla base + override `DONA_MODEL_PRICES`
  (JSON). El coste se calcula con `Decimal` (nunca `float`).
- **Sin llamadas reales de pago**: `ProveedorSimulado` cubre pruebas y demo
  etiquetada (presupuesto 0 USD). El flag `DONA_MULTI_MODEL_ENABLED` está apagado
  por defecto → se usa el modelo por defecto actual.

## 7. Accesibilidad (resumen)

- `radiogroup`/`radio` nativos para el selector; cada respuesta comparada es una
  `region` etiquetada por el modelo.
- Foco visible aguamarina 3px; estado comunicado con **texto**, no sólo color.
- Targets ≥44px; chips ≥36px; `aria-live="polite"` donde haya streaming;
  `prefers-reduced-motion` respetado.
