# Tool Intelligence Layer — `docs/tools/`

Registro de evaluación, integración y rotación de herramientas externas
usadas (o evaluadas) por Dona. Es **proceso documental**, no código vivo.

## Reglas

1. **Ninguna herramienta entra a `requirements.txt` o env vars sin ficha
   aprobada.** La ficha vive en `docs/tools/<slug>.md`.
2. **Decisiones rechazadas también se conservan** (decision log).
3. Cada ficha referencia las **capas (1–18)** del Plan v2 que toca.
4. Herramientas con costo unitario alto deben tener **fallback documentado**.
5. Revisión por defecto: **trimestral**.

## Plantilla mínima

Cada ficha sigue las 15 secciones del Plan v2.1 §H:

1. Nombre y categoría.
2. Qué hace.
3. Qué problema resuelve en Dona.
4. Módulo de aplicación.
5. Reemplaza a.
6. Complementa a.
7. Costo aproximado.
8. Calidad esperada.
9. Riesgos.
10. Privacidad / compliance.
11. Facilidad de integración.
12. Prioridad.
13. Experimento mínimo.
14. Decisión actual.
15. Revisión programada.

## Estado

- `adobe-firefly.md` — documentado, no integrado.
- `higgsfield.md` — documentado, no integrado.
- `matriz.md` — comparativa por categoría.

Tools en producción que **aún no tienen ficha retroactiva** (pendiente, no
bloqueante): Anthropic Claude, OpenAI, Groq, Google Gemini Image, Replicate
(video), HeyGen, ElevenLabs, Photoroom, Cloudflare R2, Stripe, Whapi, Meta
Cloud API, Twilio, Zep, MiroFish.
