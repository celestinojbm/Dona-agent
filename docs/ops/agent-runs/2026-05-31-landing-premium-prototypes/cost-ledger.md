# Cost Ledger — Landing Premium Prototypes

Fecha: 2026-05-31
Run ID: `2026-05-31-landing-premium-prototypes`
Riesgo: MEDIUM

## Alcance económico

Tarea de prototipado visual docs/artifact-only. No ejecuta proveedores de Dona, no genera imágenes/video con APIs pagas, no despliega producción y no modifica runtime.

## Costos directos previstos

- Claude Code Opus 4.8 con `--effort max`: costo superior al uso normal, autorizado por Celestino para tareas críticas de calidad.
- Browser/local QA: sin costo externo.
- Git/GitHub PR: sin costo externo adicional.

## Límites de gasto operativo

- Usar `--max-turns` para evitar loops largos.
- No usar generación de imágenes/video externa en esta fase.
- Si el prototipo requiere assets de pago o herramientas externas, documentarlo como recomendación futura, no comprar ni ejecutar.

## Riesgos de costo

- Opus 4.8 `max` puede gastar más y sobreanalizar. Se usa aquí porque la dirección visual premium define percepción de producto.
- No se configurará `max` como default global para todas las tareas; se aplica explícitamente en esta fase.

## Cierre

Pendiente de registrar costo real reportado por Claude Code.

## Registro real de ejecuciÃ³n

- Claude Code se ejecutÃ³ con `claude-opus-4-8` y `--effort max`.
- El proceso generÃ³ el prototipo HTML principal, pero no devolviÃ³ JSON final antes del timeout/espera prolongada.
- Hermes detuvo manualmente el proceso para evitar gasto indefinido y completÃ³ README/normalizaciÃ³n/validaciÃ³n.
- Costo exacto de esa ejecuciÃ³n: no disponible porque `claude-dona-prototype-result.json` no se creÃ³.
- Riesgo operativo: `max` puede quedarse en loops largos; para prÃ³ximas ejecuciones usar `--max-turns`, revisar artefactos parciales y considerar dividir diseÃ±o/implementaciÃ³n en subtareas mÃ¡s pequeÃ±as.

## Cierre de costo

Costo exacto de Claude Code Opus 4.8 `max`: no disponible porque el proceso no generÃ³ JSON final antes de ser detenido manualmente.

DecisiÃ³n operativa:

- El uso de `max` fue adecuado para la fase visual crÃ­tica.
- Para prÃ³ximas tareas largas con `max`, dividir en subtareas o usar ejecuciÃ³n en background controlada para evitar timeouts y capturar JSON de costo completo.
