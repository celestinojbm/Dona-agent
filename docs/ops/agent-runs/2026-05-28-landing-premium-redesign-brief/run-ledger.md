# Run Ledger — Landing Premium Redesign Brief

Fecha: 2026-05-28
Run ID: `2026-05-28-landing-premium-redesign-brief`
Riesgo: MEDIUM
Estado inicial: pre-flight
Branch: `docs/landing-premium-redesign-brief`
Commit base local: `693eecda` (`fix(landing): usar agent-runs local en build (#62)`)

## Objetivo exacto

Crear un brief/documento de dirección visual y narrativa para el rediseño premium de la landing de Dona, incorporando referencias visuales indicadas por Celestino: Luma, Higgsfield, Kittl, Lovable, LTX (`ltx.io`) y LTX Studio (`ltx.studio`).

El brief debe servir como contrato previo para una fase futura de prototipado/implementación, sin modificar aún código visual, componentes, estilos, runtime, deploy ni producción.

## Scope permitido

- Crear documento de visión/dirección para landing bajo `docs/vision/`.
- Crear ledgers de esta ejecución bajo `docs/ops/agent-runs/2026-05-28-landing-premium-redesign-brief/`.
- Validar Markdown, diff, scope y agent-runs offline.
- Abrir PR docs-only si las verificaciones pasan.

## No-scope explícito

- No modificar `landing/app/page.tsx`, CSS, componentes ni tests de frontend.
- No generar ni versionar imágenes, videos o assets finales.
- No tocar `.env`, secretos, deploy, CI/CD, billing, WhatsApp, proveedores, scheduler, auth, DB ni integraciones reales.
- No redefinir la visión canónica; el brief debe derivar de `DONA_CANONICAL_CONTEXT.md`.
- No reducir Dona a WhatsApp, chatbot, Canva-like, marketplace o galería de tools.
- No copiar literalmente la identidad, nombres, layouts, copy o assets de las referencias.

## Contexto leído / a leer

- `docs/vision/DONA_CANONICAL_CONTEXT.md`
- `CLAUDE.md`
- `README.md`
- `AGENTS.md` raíz y `landing/AGENTS.md` vía contexto de herramientas
- Landing actual observada en `https://usadona.com`
- Referencias observadas read-only: `lumalabs.ai`, `higgsfield.ai`, `kittl.com`, `lovable.dev`, `ltx.io`, `ltx.studio`
- `docs/ops/RUN_LEDGER_POLICY.md`

## Archivos que se podrían modificar

- `docs/vision/DONA_LANDING_PREMIUM_REDESIGN_BRIEF.md`
- `docs/ops/agent-runs/2026-05-28-landing-premium-redesign-brief/run-ledger.md`
- `docs/ops/agent-runs/2026-05-28-landing-premium-redesign-brief/cost-ledger.md`
- `docs/ops/agent-runs/2026-05-28-landing-premium-redesign-brief/tool-ledger.md`

## Herramientas permitidas

- Lectura de archivos del repo.
- Browser read-only en URLs públicas de referencia.
- Escritura de Markdown docs-only.
- Git local para branch, diff, commit.
- Validadores offline (`git diff --check`, `python scripts/validate_agent_runs.py`, JSON/secret/scope checks).
- GitHub PR vía máquina autenticada si VPS no tiene credenciales.

## Herramientas prohibidas

- Login en sitios externos.
- Formularios, compras, envíos, acciones productivas o scraping agresivo.
- Uso de secretos o llamadas a APIs live.
- Deploy, merge, force-push o cambios en `main`.

## Plan paso a paso

1. Crear branch docs-only desde `main` ya sincronizado con PR #62.
2. Crear Run Ledger pre-flight.
3. Redactar brief de rediseño premium con:
   - objetivo;
   - anti-regresión;
   - referencias y patrones extraídos;
   - narrativa propuesta;
   - arquitectura de página;
   - dirección visual/motion/assets;
   - criterios de aceptación;
   - plan de ejecución con Hermes, Claude Code, Codex y OpenClaw.
4. Crear Cost Ledger y Tool Ledger.
5. Validar scope, Markdown/diff y agent-runs offline.
6. Commit docs-only.
7. Publicar branch/PR por ruta autenticada sin tocar workspaces sucios de Windows.
8. Reportar URL del PR, archivos tocados y verificaciones.

## Verificaciones previstas

- `git diff --check`
- `python scripts/validate_agent_runs.py`
- `python -m json.tool docs/ops/agent-runs/index.json`
- Scope check: solo archivos docs permitidos.
- Secret scan básico sobre diff/ledgers.
- Revisión de contenido contra anti-regresión canónica.

## Aprobación requerida

Celestino autorizó explícitamente continuar con la recomendación: crear el PR docs-only de brief antes de código visual.

## Rollback esperado

Cerrar PR sin merge o revertir el commit docs-only. No hay cambios runtime ni deploy.

## Cierre

Estado: completado para commit local; PR pendiente de publicación.

Archivos creados:

- `docs/vision/DONA_LANDING_PREMIUM_REDESIGN_BRIEF.md`
- `docs/ops/agent-runs/2026-05-28-landing-premium-redesign-brief/run-ledger.md`
- `docs/ops/agent-runs/2026-05-28-landing-premium-redesign-brief/cost-ledger.md`
- `docs/ops/agent-runs/2026-05-28-landing-premium-redesign-brief/tool-ledger.md`

Verificaciones ejecutadas:

- `git diff --cached --check`: OK
- Scope check staged: OK, solo 4 archivos docs permitidos
- `python scripts/validate_agent_runs.py`: OK (`agent-runs OK: 7 runs`)
- `python -m json.tool docs/ops/agent-runs/index.json`: OK
- Secret scan staged docs: OK
- Content anti-regression check: OK
- Revisión independiente read-only: aprobada, sin bloqueantes

Riesgos encontrados:

- El brief no implementa cambios visuales; requiere fase posterior de prototipo/implementación.
- La publicación del PR requiere ruta autenticada porque el VPS no tiene `gh` ni credenciales GitHub para el repo privado.

Desvíos respecto al plan:

- No se actualizó `docs/ops/agent-runs/index.json` porque aún no existe número de PR y el objetivo principal es un brief docs-only. Los ledgers quedan versionados como evidencia del run.

Próxima acción requerida:

- Publicar el branch como PR docs-only y usar este brief como contrato para la fase de prototipos visuales.
