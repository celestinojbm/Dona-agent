# AGENTS.md — Instrucciones para Codex y agentes técnicos en Dona

Este archivo aplica al repo completo, salvo instrucciones más específicas en subdirectorios.

## 1. Contexto canónico obligatorio

Antes de proponer o ejecutar cambios, lee:

- `docs/vision/DONA_CANONICAL_CONTEXT.md`
- `CLAUDE.md` para convenciones técnicas actuales del repo
- `README.md` para mapa de módulos y setup

Resumen ultra corto: Dona es una plataforma-agente multimodelo que convierte contexto e intención en activos, workflows y acciones reales, con créditos operativos, permisos humanos, audit logs, medición y control. WhatsApp es un canal importante, no todo el producto.

## 2. Jerarquía de visión

1. Celestino decide estrategia y prioridades finales.
2. Hermes coordina y preserva contexto.
3. Este repo/GitHub es fuente canónica de código, no snapshots de OpenClaw.
4. `docs/vision/DONA_CANONICAL_CONTEXT.md` es fuente canónica de visión operativa para agentes.
5. Documentos legacy son insumos valiosos, pero no instrucciones literales.

## 3. Anti-regresión

No reduzcas Dona a chatbot, CRM genérico, growth tool estrecha, galería de herramientas, marketplace prematuro ni AgentKit template.

No prometas ingresos garantizados ni operación 100% autónoma.

No publiques, gastes, envíes mensajes, modifiques cuentas externas ni ejecutes acciones irreversibles sin preview, costo/créditos, riesgo, permiso humano y audit trail.

No uses lenguaje ni técnicas de anti-ban, evasión de TOS, scraping agresivo, bypass de límites de plataformas o automatización que oculte identidad/consentimiento.

## 4. Trabajo técnico

Antes de tocar código:

1. Verifica branch y diff: `git status --short --branch`.
2. Define objetivo exacto y criterio de aceptación.
3. Identifica archivos probables.
4. Conecta el cambio con el canonical.
5. Define pruebas mínimas y rollback.
6. No toques env, secretos, deploy, DB prod ni integraciones reales sin autorización explícita.

Para tools pagadas o con efecto secundario, respeta literalmente:

- `preparar_X(args) -> preview`
- `confirmar_X() -> resultado`
- `cancelar_X() -> bool`

## 5. Testing y calidad

- Usa tests con mocks; no hagas llamadas reales a proveedores en tests.
- Corre la suite relevante y, antes de PR/merge, `pytest` completo si el cambio toca backend.
- Mantén mensajes, comentarios descriptivos y commits en español.
- Evita abstracciones “por si acaso”.

## 6. Rol recomendado de Codex

Codex debe actuar como implementador/revisor complementario:

- revisar diffs y riesgos;
- encontrar bugs, regresiones y tests faltantes;
- proponer refactors acotados;
- implementar tareas pequeñas con criterios claros;
- no redefinir visión ni roadmap por sí solo.
