# Higgsfield (Soul + DoP + MCP)

> **Estado**: documentado, **no integrado**.
> **Decisión actual**: documentar y diseñar; PoC autorizado solo cuando se
> active la iniciativa "motion ads" (Phase 3) y haya revisión legal de TOS
> comerciales.
> **Capas tocadas**: 13 (Creative Engine).

---

## 1. Nombre y categoría

Higgsfield AI: Soul, DoP (Director of Photography), Cinema Studio. Categoría:
imagen (Soul) + image-to-video cinematic (DoP) + multi-model gateway.

## 2. Qué hace

- **Soul**: imagen con *character consistency* entre escenas, poses y
  lighting. 4K, cualquier aspect ratio.
- **DoP**: motion clips cinematográficos de 5 segundos a partir de una imagen
  estática. Tres tiers: `dop-lite` (entry), `dop-turbo` (2x más rápido,
  prioridad), `dop-preview` (premium, máxima calidad).
- **Cinema Studio**: composición de escenas multi-shot.
- **MCP gateway**: invoca también Seedance, Kling, Veo, Hailuo, Flux, Sora,
  GPT Image desde un solo endpoint. ~30 modelos detrás de la misma surface.

## 3. Qué problema resuelve en Dona

1. **Character consistency** para campañas de marca: un único "modelo virtual"
   se mantiene reconocible en 10+ imágenes diferentes. Ningún proveedor
   actualmente integrado en Dona resuelve esto bien.
2. **Motion ads premium** en 5–15s sin armado manual. Ruta más rápida para
   pasar de "tengo una foto del producto" a "tengo un ad de 5s listo para
   Instagram/TikTok".
3. **A/B testing de modelos** sin integrar cada API: el MCP/Cloud gateway
   permite probar Seedance vs Veo vs Kling con el mismo prompt y comparar.

## 4. Módulo de aplicación

- `agent/creativos/imagen.py` (Soul como provider opcional para character
  consistency).
- `agent/creativos/video.py` (DoP como provider de image-to-video).
- `agent/orchestrator/iniciativas/motion_ads.py` (futura, Phase 3).

## 5. Reemplaza a

Posible reemplazo del wrapper directo a Replicate / Veo / Seedance que ya
tiene Dona — si el modelo de créditos sale bien y los TOS comerciales lo
permiten. **No reemplaza Firefly** (estética y posicionamiento legal
diferentes).

## 6. Complementa a

- **Adobe Firefly** (estética distinta, foco "cinematic" vs "editorial").
- **Photoroom** (no compite, son categorías distintas).
- **ElevenLabs** (voz para acompañar el motion ad).

## 7. Costo aproximado

| Ruta | Costo |
|---|---|
| Planes consumer (web app) | Starter $15/mes, Plus $34, Ultra $84, Business $49/seat. Sirve para PoC humano, no producción. |
| Higgsfield Cloud REST | Pay-per-use por modelo y resolución. Pricing publicado en `cloud.higgsfield.ai`. |
| Vía WaveSpeed / Unifically (REST passthrough) | Pay-per-use por endpoint. Costo varía según partner. |
| MCP gateway dentro de Claude.ai | Mismo sistema de créditos de la cuenta del usuario; no aplica a backend de Dona. |

## 8. Calidad esperada

- Soul: 4–5/5 en character consistency. Resuelve un problema real que ningún
  proveedor actual de Dona cubre.
- DoP: 4–5/5 para motion ads de social media. `dop-preview` es el tier que
  apuntaríamos a producción para clientes pagantes.

## 9. Riesgos

1. **Compañía joven** (relativo a Adobe): riesgo de cambios de pricing/TOS,
   shutdown, o pivot. Mitigación: fallback documentado a Replicate/Veo
   directo por workflow.
2. **MCP es para Claude desktop/web del usuario, no para el backend
   programático**. Para Dona producción: usar Cloud REST oficial o passthrough
   (WaveSpeed/Unifically). No mezclar conceptos.
3. **TOS comerciales no garantizan commercial-safe by default**. La
   documentación oficial no menciona explícitamente clearance de derechos como
   Adobe Firefly. **Bloqueante** para uso en campañas comerciales reguladas
   antes de revisión legal del owner.
4. **Dependencia de modelos de terceros** que el gateway re-expone (Seedance,
   Kling, Veo, etc.). Cada uno tiene sus propios TOS. Si uno cambia, podría
   afectar el output disponible.

## 10. Privacidad / compliance

- Documentación oficial de Higgsfield no menciona explícitamente
  "commercial-safe by training". Hay que validar antes de campañas comerciales.
- Si el output se entrega como borrador / preview interno, riesgo legal es
  bajo. Si se entrega como asset final a clientes pagantes en industrias
  reguladas, **bloqueante** sin autorización legal explícita.
- Datos enviados al servicio: prompt + imagen base. Verificar política de
  retención de Higgsfield antes de enviar imágenes con caras / logos
  reconocibles.

## 11. Facilidad de integración

**Dos rutas**:

1. **MCP server en Claude del owner**: connector personalizado en
   Settings → Connectors apuntando a `https://mcp.higgsfield.ai/mcp`. Sin API
   keys; autenticación con cuenta Higgsfield. **No aplica al backend de Dona**.
2. **Higgsfield Cloud REST** o **WaveSpeed/Unifically REST**: programable
   desde `agent/creativos/`. Cloud REST oficial es más limpio; passthrough
   da pay-per-use sin compromiso de plan. Facilidad técnica: media.

**Esta es la ruta para Dona**: Cloud REST (preferido) o passthrough.

## 12. Prioridad

- **Alta** para feature "campañas de motion ads" (Phase 3, T3.6 generalizada
  más allá de Meta Ads).
- **Media** para imagen general (Soul vs Firefly compite; Firefly gana en
  legal/compliance, Soul gana en character consistency).

## 13. Experimento mínimo

PoC con Higgsfield Cloud REST:

- 20 motion ads (DoP-preview) a partir de imágenes ya generadas por Dona.
- 10 imágenes Soul con character consistency a partir de 1 base.
- Métricas: % aprobación, costo por clip aprobado, tiempo medio, comparación
  vs Veo/Seedance directo.

Duración estimada: 1 semana. Costo PoC: <$80.

## 14. Decisión actual

**Documentar y diseñar, no integrar todavía**. Bloqueado por:

1. Revisión legal del owner sobre TOS comerciales de Higgsfield.
2. Decisión sobre la iniciativa "motion ads" en backlog (Phase 3).
3. Confirmación de proveedor preferente: Cloud REST oficial vs passthrough.

Cuando esté integrada, el adaptador vivirá en `agent/creativos/higgsfield.py`
siguiendo el patrón `preparar_/confirmar_`.

## 15. Revisión programada

Próxima: **3 meses** desde la creación de esta ficha. Antes si se autoriza
Phase 3 motion ads.

---

## Referencias

- [Higgsfield MCP — AI Image & Video Generation for Any Agent](https://higgsfield.ai/mcp)
- [Higgsfield Cloud API](https://cloud.higgsfield.ai/)
- [Higgsfield AI pricing](https://higgsfield.ai/pricing)
- [Higgsfield DoP Image-to-Video API — WaveSpeedAI (passthrough)](https://wavespeed.ai/docs/docs-api/higgsfield/higgsfield-dop-image-to-video)
- [Higgsfield DoP API | Cinematic AI Video API — Unifically (passthrough)](https://unifically.com/models/higgsfield-dop)
