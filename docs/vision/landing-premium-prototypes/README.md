# Prototipos premium de landing Dona

Fecha: 2026-05-31
Estado: prototipo comparativo, no producción.

## Propósito

Este directorio contiene una exploración visual de alto nivel para la próxima landing pública de Dona. El objetivo es comparar tres direcciones premium antes de tocar la landing productiva en `landing/`.

El prototipo deriva de:

- `docs/vision/DONA_CANONICAL_CONTEXT.md`
- `docs/vision/DONA_LANDING_PREMIUM_REDESIGN_BRIEF.md`
- referencias visuales aditivas: Luma, Higgsfield, Kittl, Lovable, `ltx.io` y `ltx.studio`

## Cómo abrir

Abrir directamente en navegador:

```text
docs/vision/landing-premium-prototypes/dona-landing-premium-prototypes.html
```

El HTML es self-contained y debe funcionar como archivo local (`file://`).

## Direcciones incluidas

### A. Execution Suite / LTX-inspired

Dirección oscura, editorial y de suite creativa/enterprise. Explora Dona como sistema completo con módulos: Studio, Flow, Agents, Memory, Actions y Control Room.

Inspiración: LTX, LTX Studio, Linear, Raycast/Vercel en sobriedad y control.

### B. Prompt to Production / Luma-Lovable-inspired

Dirección centrada en la transformación de una intención en plan, activos, permisos, ejecución y medición. WhatsApp aparece como canal de entrada, no como identidad completa.

Inspiración: Luma por demo/impacto y Lovable por claridad del loop idea → resultado → refine/ship.

### C. Multimodal Output Gallery / Higgsfield-Kittl-inspired

Dirección de galería multimodal con outputs, starting points y cards de resultados. Muestra amplitud: texto, voz, imagen, video, docs, datos, workflows y acciones.

Inspiración: Higgsfield por densidad multimodal y Kittl por outputs visuales/profesionales.

## Criterios para elegir dirección

Celestino debería evaluar cada dirección según:

1. ¿Se siente como producto premium de alto nivel?
2. ¿Evita reducir Dona a chatbot o WhatsApp?
3. ¿Muestra outputs y workflows reales, no solo texto aspiracional?
4. ¿Comunica créditos, permisos, riesgo, audit trail, medición y Control Room?
5. ¿Puede evolucionar hacia una landing productiva real sin rehacer todo?
6. ¿Se diferencia de Canva/SaaS genérico?
7. ¿Puede soportar assets, videos y motion de alta calidad en la siguiente fase?

## Qué no es

- No es la landing productiva.
- No contiene assets finales.
- No prueba conversión real.
- No sustituye QA visual, diseño de marca final ni implementación Next.js.
- No autoriza cambios en producción.

## Siguiente paso recomendado

Elegir una dirección principal o una combinación de partes. Luego crear un PR de implementación acotado para convertir esa dirección en componentes reales de `landing/`, con tests, browser QA y revisión independiente.
