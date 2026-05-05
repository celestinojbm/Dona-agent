# Planes de Dona — índice

Carpeta con el histórico de documentos de planificación del producto.
Sirve como contexto para nuevos colaboradores y como rastro de las decisiones
que dieron forma al estado actual.

## Documento vigente

- **`Plan_Dona_v2_1_2026-04-30.pdf`** — referencia activa. Aplica los ajustes
  pre-implementación al Plan v2: fusión de T0.5 + T0.8, dos variantes para
  PR1 Sentry (autorización pendiente), primer paquete recomendado de
  implementación, y la incorporación de Adobe Firefly y Higgsfield al
  Tool Intelligence Layer + benchmark creativo. Este es el documento por
  el que se rige el backlog hoy.

## Addendums vigentes

- **`Addendum_Manus_Integration_2026-05-05.md`** — integra la referencia
  Manus al ADN de Dona. Define 7 conceptos (Playbooks, Execution Sandbox,
  Browser Operator por niveles, Builder orientado a crecimiento, Wide
  Research, documentos accionables, Workspace + Action Center) y un
  backlog priorizado con prefijo `M` (M0..M4) que se suma al backlog
  `T.x` del Plan v2.1 sin reemplazarlo. Incluye 6 anti-patterns
  vinculantes ("qué NO copiar de Manus") y mapping con las piezas Dona
  ya en producción (T1.3 / T1.4 / T1.5).

## Histórico (orden cronológico inverso)

- **`Plan_Dona_Refinado_v2_2026-04-29.pdf`** — v2. Introduce las 18 capas de
  refinación, el principio de "elevar también lo existente", la migración
  progresiva `telefono → workspace_id`, el Tool Intelligence Layer y el
  Public Sub-Agent con números del negocio. Reemplazado por v2.1 con
  ajustes operativos.
- **`Plan_Dona_Refinado_v1_2026-04-29.pdf`** — v1. Primera versión refinada
  tras la auditoría: arquitectura objetivo (Identity/Workspace, Subscription
  + Credits, Owner/Public agents, Orchestrator, Approval, Jobs, Audit log,
  Dashboard) y backlog en fases. Reemplazado por v2 (corregía: refactor
  big-bang de identidad, falta de checklist transversal y desnivel de
  calidad entre lo viejo y lo nuevo).
- **`plan-maestro-dona-2026-04-21.{html,pdf}`** — visión previa al rebrand
  definitivo de Dona como acelerador autónomo premium para negocios.
  Contiene el primer mapa de capacidades, antes de incorporar la auditoría
  del 27/04 y los hallazgos de seguridad. Útil para entender de dónde
  viene el producto.

## Auditorías relacionadas

- `../auditorias/2026-04-27.pdf` (`Auditoria_Dona_2026-04-27.pdf`) —
  auditoría de arquitectura/seguridad que disparó la serie de planes
  refinados v1 → v2 → v2.1.

## Scripts de generación

Los scripts reportlab que produjeron estos PDFs viven en `../scripts/`. Si
hay que regenerar un documento (cambio de branding, formato, errata), esos
scripts son la fuente reproducible.

## Reglas

- No editar los PDFs en sitio: si un plan necesita correcciones, generar
  una versión nueva con el script correspondiente y archivar la anterior.
- El **vigente** se actualiza solo aquí en este README cuando aparece una
  versión nueva.
