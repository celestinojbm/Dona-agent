# Adobe Firefly + "Adobe for creativity" connector

> **Estado**: documentado, **no integrado**.
> **Decisión actual**: documentar y diseñar; PoC autorizado solo cuando haya
> definición del tier Pro (T1.5 del Plan v2) y volumen suficiente para
> justificar contrato Firefly Services enterprise.
> **Capas tocadas**: 13 (Creative Engine), 16 (Seguridad / compliance).

---

## 1. Nombre y categoría

Adobe Firefly + Adobe for creativity (connector para Claude). Categoría:
imagen + edición + composición + Stock licensed.

## 2. Qué hace

- **Firefly**: generación e edición de imagen (modelo *commercial-safe*).
- **Photoshop API / Illustrator / InDesign / Premiere / Lightroom / Express**:
  edición pro (no solo generación).
- **Adobe Stock**: assets licenciados como insumos para composición.
- **"Adobe for creativity" connector**: connector lanzado el 2026-04-28 para
  Claude.ai. Permite invocar 50+ herramientas pro con lenguaje natural desde
  la conversación de Claude (cliente). Acceso guest a ~40 herramientas; cuenta
  Adobe (free o paid) desbloquea más + límites + persistencia.

## 3. Qué problema resuelve en Dona

- **Calidad commercial-safe garantizada** para assets de marca de los
  Workspaces. Firefly está entrenado sobre Adobe Stock + contenido licenciado.
  Es la única ruta hoy con clearance de derechos comerciales clara, ventaja
  regulatoria sobre Midjourney / Stable Diffusion.
- **Edición pro**, no solo generación. Workflows multi-tool desde el
  orquestador (`agent/orchestrator/`) — generar + retocar + redimensionar +
  formatear para social.
- **Tier Pro / Enterprise** del modelo de monetización tendría a Firefly como
  diferenciador de calidad contra el tier Premium (que usa Gemini / nano-banana).

## 4. Módulo de aplicación

- `agent/creativos/` — adaptador REST.
- `agent/orchestrator/iniciativas/assets_marca.py` (futura, Phase 3).
- Futura iniciativa "campaña editorial regulada" para clientes de salud /
  legal / finanzas que requieren clearance de derechos.

## 5. Reemplaza a

Posible **reemplazo parcial** de Gemini Flash Image / Ideogram en el tier
"premium con licencia comercial garantizada". **No reemplaza** nano-banana
en tier "estándar barato" (costo Firefly es 5–10x más alto).

## 6. Complementa a

- **Photoroom** (background remove): Firefly tiene funciones similares pero
  Photoroom queda como fallback rápido y barato.
- **Replicate / Veo / Seedance**: Firefly no compite directo en video (Premiere
  edita, no genera).
- **Midjourney**: estética distinta; Midjourney puede mantenerse como tool
  *no* commercial-safe para previews internos.

## 7. Costo aproximado

| Ruta | Costo |
|---|---|
| Firefly Services REST API | $0.02–$0.10 por imagen según modelo (Image 4 Ultra ≈ 20 créditos ≈ $0.08–$0.10). Mínimo enterprise ≈ $1k/mes. |
| Cuenta Creative Cloud individual | Incluido en plan CC con créditos mensuales (~1000/mes en Pro). Sirve solo para PoC manual, no producción. |
| "Adobe for creativity" connector | Gratis dentro de Claude.ai con cuenta Adobe; aplica al Claude del usuario, no al backend de Dona. |

## 8. Calidad esperada

5/5 para uso editorial / branding. Output con derechos comerciales claros
(ventaja regulatoria). Modelos Image 3 / Image 4 / Image 4 Ultra varían en
fidelidad y costo.

## 9. Riesgos

1. **Pricing enterprise alto** (~$1k/mes mínimo) sin volumen suficiente.
2. **Modelos específicos del connector aún no documentados** públicamente —
   diferentes a los del Firefly AI Assistant (beta pública aparte).
3. **Connector requiere cuenta Adobe del usuario final** para desbloquear todas
   las herramientas — fricción de onboarding si quisiéramos pasar el
   connector al owner. (No aplica si usamos REST API directo desde Dona.)
4. **Dependencia de API Adobe**: estabilidad, deprecaciones, cambios de
   licencia. Mitigación: fallback a Gemini Flash Image documentado por
   workflow.

## 10. Privacidad / compliance

- Adobe explícita "commercial-safe by training data" (Adobe Stock + contenido
  licenciado).
- Entrega *rights clearance* que Midjourney / SD no entregan. Crítico para
  clientes regulados o que necesiten responder a abogados.
- TOS estándar Adobe Enterprise; revisión legal si firmamos contrato.

## 11. Facilidad de integración

**Dos rutas técnicas distintas**:

1. **MCP-style via "Adobe for creativity" connector**: aplica al Claude del
   usuario (claude.ai web/desktop), **no al backend de Dona**. El backend
   habla con Claude por API, no con Claude Desktop. Esta ruta sería relevante
   solo si Dona expusiera UX adicional "abre tu Claude desktop con este
   preset" (no es prioridad). Facilidad para el usuario final: alta.
2. **Firefly Services REST API**: programable desde el backend Dona. Requiere
   contrato enterprise. Facilidad técnica: media (REST estándar OAuth).
   **Esta es la ruta para Dona**.

## 12. Prioridad

**Alta** para tier premium / Pro plan. La integración técnica decidida
es la **ruta 2 (REST API)**, no MCP.

## 13. Experimento mínimo

PoC con cuenta CC individual o trial enterprise:

- 50 imágenes "campaña producto X" generadas con Firefly Image 4 Ultra.
- Comparación contra el setup actual (Gemini Flash Image) en tres ejes:
  costo por imagen aprobada, tiempo de generación, calidad subjetiva del
  owner + un cliente de prueba.
- Métricas: % aprobación owner, tiempo medio, costo, presencia de artefactos
  legales (texto en imagen, marcas registradas accidentales, etc.).

Duración estimada: 1 semana. Costo PoC: <$50 si usamos cuenta CC con
créditos incluidos.

## 14. Decisión actual

**Documentar y diseñar, no integrar todavía**. Bloqueado por:

1. Definición del tier Pro (T1.5 del Plan v2): qué workflows se le promete a
   ese tier y cómo se cobran.
2. Acceso a Firefly Services Enterprise (requiere contrato; decisión owner por
   costo).
3. Revisión legal del TOS de Firefly Services para uso revendido.

Cuando esté integrada, el adaptador vivirá en `agent/creativos/firefly.py`
siguiendo el patrón `preparar_/confirmar_` ya establecido.

## 15. Revisión programada

Próxima: **3 meses** desde la creación de esta ficha. Antes si se decide
arrancar Phase 3 con iniciativas creativas premium o si Adobe libera modelo
nuevo del connector con docs públicas.

---

## Referencias

- [Adobe for creativity: a new way to create with Adobe, now in Claude — Adobe Blog](https://blog.adobe.com/en/publish/2026/04/28/adobe-for-creativity-connector)
- [Adobe Ushers in a New Era of Creativity with New Creative Agent — Adobe News](https://news.adobe.com/news/2026/04/adobe-new-creative-agent)
- [Adobe brings agentic AI to Firefly, with Claude next — Axios](https://www.axios.com/2026/04/27/adobe-agentic-ai-firefly-claude)
- [Adobe Firefly API Pricing 2026 — SudoMock (referencia de pricing, no oficial)](https://sudomock.com/blog/adobe-firefly-api-pricing-2026)
- [Adobe Firefly Services overview](https://firefly.adobe.com/services)
