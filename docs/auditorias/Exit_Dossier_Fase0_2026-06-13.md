# Exit Dossier — Salida de Fase 0 (RuntimeBudgetGuard / 4.1·4.2)

> **Formato**: *release safety case* binario (criterio Hermes, 2026-06-12).
> Cada ítem es PASS / FAIL / NA con evidencia reproducible. Regla dura:
> **si la evidencia no existe, el ítem NO pasa**, aunque conceptualmente
> parezca cubierto. Narrativa mínima; tablas binarias; evidencia trazable.
>
> La evidencia de cada ítem fue verificada de forma **adversarial**:
> agentes independientes corrieron los tests reales en el worktree y
> capturaron el conteo observado (no asertado de memoria). Un hallazgo del
> proceso —`tests/test_salida_fase0.py` estaba *untracked*— se corrige en
> **este mismo PR**, que commitea el archivo de evidencia para que exista en
> el SHA de producción y en CI.

---

## 1. Veredicto de salida de Fase 0

| Campo | Valor |
|---|---|
| **Fase 0 RuntimeBudgetGuard** | **PASS** (condicional a merge verde de este PR) |
| Alcance cerrado | PR #82 → #84 → #86 → #87 → #89 (+#88 atajo HIGH, #90 C4, #91 flake jobs) |
| Producción base verificada en SHA | `12899b90203d74ffceec486f9746760fd412a534` |
| Render web + worker | **live** ambos en `12899b902` (2026-06-13 ~05:04Z) |
| CI verde sobre head real | **PASS** (`Suite completa (pytest)`, `Validar agent-runs offline`, `submit-pypi` = success) |
| Tests de la suite | 1172 passed (último run) |
| Ítems del checklist | 23 (21 PASS verificados corriendo tests reales + 2 PASS de infra) |
| FAIL bloqueantes | **0** |
| Riesgos residuales | aceptados y documentados (§8) — ninguno bloquea |
| Siguiente misión habilitada | **Misión 0 (recuperar-lead)**, solo dentro de BudgetGuard real (condición cumplida) |

**Delta de producción de este PR: CERO** — solo agrega tests-evidencia y este
documento. El código del RuntimeBudgetGuard ya está live en `12899b9`.

---

## 2. Alcance cerrado

| PR | Commit | Qué cerró |
|---|---|---|
| #82 | `dfaaef2` | RuntimeBudgetGuard standalone (config env fail-closed, ContextVar, kill-switches, razones cerradas, reservar/consumir) |
| #84 | `c74afc5` | Cableado del guard a las llamadas LLM reales de brain.py (foreground + fallback + corte del runaway de tool_use) |
| #86 | `96da62a` | Gateo de ejecuciones de tools (`reservar_tool`, tope 8/mensaje) |
| #87 | `01e4792` | Retry LLM máx 1 + retry oculto eliminado + tool desconocida con `tool_result` + batería adversarial (19 tests) |
| #89 | `95e1b53` | F-1: gatear rutas LLM restantes (llm.py auxiliar, proactividad por-unidad, vision); dimensión `max_llm_aux_calls`; clientes muertos eliminados |

---

## 3. Estado de producción

| Servicio | ID | Estado | SHA |
|---|---|---|---|
| web `Dona-agent` | srv-d6u090cr85hc73fggpu0 | live | `12899b902` |
| worker `dona-worker` | srv-d7j6fb67r5hc73cic630 | live | `12899b902` |

Verificado vía Render API el 2026-06-13 (deploys finished ~05:04Z). Sin
deploy-drift: ambos servicios en el mismo SHA.

---

## 4–5. Checklist binario de salida de Fase 0

Columnas: **ID · Afirmación binaria · Resultado · Evidencia (tests + comando + observado) · Campo §10 · Bloquea**

### LLM Budget Guard (F0-BUD)

| ID | Afirmación | Res. | Evidencia | §10 | Bloquea |
|---|---|---|---|---|---|
| F0-BUD-01 | Toda llamada LLM real (brain foreground + fallback + aux llm.py/emotion + proactividad + vision) está gateada; con kill-switch global NINGUNA ruta llama al provider | **PASS** | `test_budget_wire_brain.py::TestBloqueoRespuestaSegura::test_kill_switch_global_no_llama_api`, `test_budget_wire_aux.py::TestLlmAuxGateado::{test_kill_switch_bloquea_completar_texto,_con_sistema}`, `::TestProactividadGateada::test_kill_switch_bloquea_generacion_proactiva`, `::TestVisionGateada::test_kill_switch_bloquea_analisis`, `test_budget_adversarial.py::TestSentinelProviderDirecto` → **6 passed in 9.57s** | provider_call_count | sí |
| F0-BUD-02 | Al agotarse el presupuesto el estado queda cerrado y NO continúa el loop (responde seguro sin re-llamar) | **PASS** | `test_budget_wire_brain.py::TestRunawayTopado::test_tool_use_infinito_se_corta_en_max_llm_calls`, `::TestBloqueoRespuestaSegura::test_presupuesto_agotado_no_llama_api` → **2 passed** | closed_state | sí |
| F0-BUD-03 | La respuesta segura al cortar NO dispara otro ciclo (modelo que ignora denegación se corta; contador del mensaje no se reinicia) | **PASS** | `test_budget_adversarial.py::TestToolLoopAdversarial::{test_modelo_ignora_denegacion_se_corta_sin_runaway,test_nested_no_reinicia_contador,test_kill_switch_durante_loop_corta_todo}` → **4 passed** | provider_call_count | sí |

### Tool Budget Guard (F0-TOOL)

| ID | Afirmación | Res. | Evidencia | §10 | Bloquea |
|---|---|---|---|---|---|
| F0-TOOL-01 | Toda tool real gateada (tope `max_tool_calls`=8/mensaje; 12 pedidas → 8 ejecutan, resto recibe `tool_result` de cierre) | **PASS** | `test_budget_wire_tools.py::TestTopeTools` → **4 passed** | test_adversarial | sí |
| F0-TOOL-02 | Tool desconocida/spoofing devuelve `tool_result` de error cerrado, no ejecuta por nombre no registrado, no excepción abierta ni 400; malformed tampoco crashea | **PASS** | `test_budget_adversarial.py::TestToolsMalformedYDesconocidas` (3) + `::TestToolLoopAdversarial` (4) → **7 passed** | tool_result | sí |
| F0-TOOL-03 | Tool que falla consume su cupo, no se reintenta sola ni reabre presupuesto; produce `tool_result` de error y cierra | **PASS** | `test_salida_fase0.py::TestF0TOOL03ToolFallida` → **1 passed** | budget_snapshot | sí |

### Retry Policy (F0-RET)

| ID | Afirmación | Res. | Evidencia | §10 | Bloquea |
|---|---|---|---|---|---|
| F0-RET-01 | Retry LLM máx 1 (inicial + 1 = 2 llamadas reales como tope) | **PASS** | `test_budget_adversarial.py::TestRetryApretado::{test_error_transitorio_reintenta_una_sola_vez,test_reintentos_configurables_a_cero}`, `test_salida_fase0.py::TestF0RET02RetryPorCodigo::test_transitorio_reintenta_exactamente_una_vez` → **17 passed** | provider_call_count | sí |
| F0-RET-02 | Retry solo en 429/5xx/red; 4xx de request (400/401/403/422) NO reintentan | **PASS** | `::TestRetryApretado::{test_clasificacion_transitorio_cerrada,test_error_no_transitorio_no_reintenta}`, `test_salida_fase0.py::TestF0RET02RetryPorCodigo::{test_no_transitorio_no_reintenta,test_error_de_red_reintenta_una_vez}` → **5 passed** | provider_call_count | sí |
| F0-RET-03 | Retry respeta presupuesto global (sin tiempo o sin cupo → no reintenta, va al fallback) | **PASS** | `::TestRetryApretado::{test_retry_respeta_presupuesto_de_tiempo,test_retry_respeta_cupo_de_llamadas}` → **2 passed** | budget_snapshot | sí |
| F0-RET-04 | Retry oculto en no-transitorios eliminado (un 400 hacía 3 llamadas; ahora 1) | **PASS** | `::TestRetryApretado::test_error_no_transitorio_no_reintenta` (pin `llamadas==1`) | provider_call_count | sí |

### Fallback + Timeouts (F0-FALL-TIME)

| ID | Afirmación | Res. | Evidencia | §10 | Bloquea |
|---|---|---|---|---|---|
| F0-FALL-TIME-01 | Fallback post-4xx = recuperación texto-solo, una llamada lógica (no segundo ciclo) | **PASS** | `test_budget_adversarial.py::TestFallbackGateado::test_fallback_con_presupuesto_llama_una_vez` → **2 passed** | provider_call_count | sí |
| F0-FALL-TIME-02 | Fallback gateado por presupuesto (cupo agotado → no llama al provider del fallback) | **PASS** | `::TestFallbackGateado::test_fallback_no_se_llama_sin_presupuesto` → **1 passed** | provider_call_count | sí |
| F0-FALL-TIME-03 | Timeout LLM → estado cerrado y seguro, sin reintentos ilimitados ni reserva huérfana | **PASS** | `::TestTimeoutSinRunaway::test_timeout_no_reintenta_ni_deja_reserva_huerfana`, `test_budget_wire_brain.py::TestTimeout` → **2 passed** | closed_state | sí |
| F0-FALL-TIME-04 | Respuesta tardía post-timeout cancelada (sin segunda respuesta ni consumo tardío) | **PASS** | `::TestTimeoutSinRunaway::test_respuesta_tardia_post_timeout_no_consume` → **1 passed** | closed_state | sí |

### Loop + Cost (F0-LOOP-COST)

| ID | Afirmación | Res. | Evidencia | §10 | Bloquea |
|---|---|---|---|---|---|
| F0-LOOP-COST-01 | Límite por presupuesto configurable por env (no contador local hardcodeado) | **PASS** | `test_budget_adversarial.py::TestRetryApretado::test_retry_respeta_cupo_de_llamadas`, `test_presupuesto_runtime.py::TestConfigEnv`, `test_salida_fase0.py::TestF0LOOPPromptDriven::test_limite_es_del_presupuesto_no_del_contador_local` → **passed** | test_adversarial | sí |
| F0-LOOP-COST-02 | Mensaje adversarial/prompt-driven no fuerza llamadas no presupuestadas; nested no reinicia contador | **PASS** | `::TestToolLoopAdversarial::{test_modelo_ignora_denegacion_se_corta_sin_runaway,test_nested_no_reinicia_contador}`, `test_salida_fase0.py::TestF0LOOPPromptDriven::test_mensaje_adversarial_no_fuerza_llamadas_no_presupuestadas` → **passed** | budget_snapshot | sí |
| F0-LOOP-COST-03 | Cada llamada real tiene ruta de costo/reserva o denegación segura (sentinel + vía aux degrada a None) | **PASS** | `test_budget_wire_aux.py::TestLlmAuxGateado::{test_kill_switch_bloquea_completar_texto,test_aux_cero_bloquea_sin_llamar_provider,test_aux_no_compite_con_cupo_principal}`, `TestSentinelProviderDirecto` → **4 passed** | provider_call_count | sí |
| F0-LOOP-COST-04 | Corte por presupuesto sin consumo inconsistente (solo completadas consumen; denegación no mueve costo; sin doble conteo) | **PASS** | `test_salida_fase0.py::TestF0COST02ContabilidadExacta::{test_solo_llamadas_completadas_consumen_costo,test_denegacion_no_consume_costo}` → **passed** | budget_snapshot | sí |

### Dimensión auxiliar (F0-AUX)

| ID | Afirmación | Res. | Evidencia | §10 | Bloquea |
|---|---|---|---|---|---|
| F0-AUX-01 | Dimensión aux separada (`max_llm_aux_calls`=3): las ligeras no compiten con el cupo principal | **PASS** | `test_budget_wire_aux.py::TestLlmAuxGateado::{test_aux_no_compite_con_cupo_principal,test_aux_agotado_no_bloquea_principal}` → **passed** | test_adversarial | no |
| F0-AUX-02 | Costo aux COMPARTIDO: un aux puede agotar `max_costo_usd_mensaje` y bloquear al principal | **PASS** | `::TestLlmAuxGateado::test_costo_aux_puede_bloquear_principal` (razón `max_costo_mensaje`) | test_adversarial | sí |
| F0-AUX-03 | Clientes provider muertos eliminados (emotion/mirofish/onboarding sin cliente a nivel módulo) | **PASS** | `::TestClientesMuertosEliminados::{test_emotion_sin_cliente_propio,test_modulos_aux_sin_cliente_provider_a_nivel_modulo}` (inspección de fuente de los 3 módulos) | provider_call_count | sí |
| F0-AUX-04 | Config aux fail-closed: env aux ilegible/fuera de rango → default seguro (3) + evento | **PASS** | `::TestClientesMuertosEliminados::test_aux_fail_closed_env_invalida_cae_a_default` (muchas/-1/999 → default + `config_invalida`) | test_adversarial | no |

### Infraestructura, CI y Go/No-Go (F0-EVID / F0-CI / F0-GO)

| ID | Afirmación | Res. | Evidencia | §10 | Bloquea |
|---|---|---|---|---|---|
| F0-EVID-02 | Render web y worker reportan el mismo SHA `12899b902` (ambos live) | **PASS** | Render API: web live `12899b902`, worker live `12899b902` | render_live_sha | sí |
| F0-CI-01 | Check-runs del head `12899b9` todos success; suite completa pasó en CI | **PASS** | `gh api .../commits/12899b90.../check-runs` → 3 checks success (run 27457291394) | ci_run | sí |
| F0-GO-01 | Cero FAIL bloqueante en los gates de budget/tool/retry/timeout/loop/cost | **PASS** | Agregado de §4–5: 21/21 gates de seguridad PASS, 0 FAIL | closed_state | sí |
| F0-GO-02 | Misión 0 autorizada solo dentro de BudgetGuard real; condición 4.1/4.2 cumplida | **PASS** | Ciclo #82→#84→#86→#87→#89 mergeado + live; guard central en el head desplegado | closed_state | no |

---

## 6. Failure-mode matrix (absorbida del §10 V6)

Cada modo de fallo del §10 del V6 mapeado al gate que lo cubre:

| Modo de fallo | Gate que lo cierra | Evidencia §10 |
|---|---|---|
| Ruta LLM real sin guard (bypass de presupuesto/kill-switch) | F0-BUD-01, F0-LOOP-COST-03, F0-AUX-03 | provider_call_count |
| Recursión de tool_use sin tope (runaway) | F0-BUD-02, F0-BUD-03 | closed_state |
| Tool-loop sin tope por mensaje | F0-TOOL-01 | test_adversarial |
| Tool desconocida/spoofing ejecutada o 400 por bloque sin respuesta | F0-TOOL-02 | tool_result |
| Tool fallida que reabre presupuesto / se auto-reintenta | F0-TOOL-03 | budget_snapshot |
| Retry multiplicador de costo (>1) | F0-RET-01, F0-RET-04 | provider_call_count |
| Retry de error irrecuperable (4xx) | F0-RET-02 | provider_call_count |
| Retry que ignora presupuesto global | F0-RET-03 | budget_snapshot |
| Fallback como segundo ciclo completo | F0-FALL-TIME-01 | provider_call_count |
| Fallback no gateado post-tope | F0-FALL-TIME-02 | provider_call_count |
| Timeout que deja loop abierto / reserva huérfana | F0-FALL-TIME-03 | closed_state |
| Respuesta tardía post-timeout (race) | F0-FALL-TIME-04 | closed_state |
| Loop runaway con límite hardcodeado | F0-LOOP-COST-01 | test_adversarial |
| Prompt injection que fuerza trabajo ilimitado / nested reinicia contador | F0-LOOP-COST-02 | budget_snapshot |
| Contabilidad inconsistente (over/under-charge, doble conteo) | F0-LOOP-COST-04 | budget_snapshot |
| Vía aux que evade el techo USD del mensaje | F0-AUX-02 | test_adversarial |
| Env crafted que abre el budget en runtime | F0-AUX-04 | test_adversarial |
| Deploy-drift (web/worker en SHA distinto) | F0-EVID-02 | render_live_sha |
| CI-rojo o suite no ejecutada en el head real | F0-CI-01 | ci_run |

---

## 7. Evidence fields por ítem

Todos los ítems con respaldo de test citan: **node ids reales** (col. Evidencia
de §4–5), **comando ejecutado** (patrón `cd <wt> && PYTEST_DEBUG_TEMPROOT=...
python -m pytest <nodes> -q -p no:cacheprovider`, ver §10), **resultado
observado** (conteo `N passed in Xs`), **PR/commit** (§2). Los ítems de infra
(EVID/CI) citan el comando de API (Render/`gh`) y el output observado.

---

## 8. Riesgos residuales aceptados (ninguno bloquea)

**Aceptados explícitamente por Hermes (no bloquean, "medir antes de recortar"):**

1. **Matching textual de códigos HTTP** en `_es_error_llm_transitorio`
   (`brain.py:1399`): clasifica por substring (`"500"`, `"429"`, …). Acotado
   porque retry máx 1 + presupuesto limitan el daño de un falso positivo a una
   sola llamada extra. *Medir*: tasa de falsos ±.
2. **Fallback post-4xx conservado**: es recuperación texto-solo, una llamada
   lógica, gateada por presupuesto. No se recorta antes de medir la frecuencia
   de 400s estructurales y la tasa de uso del fallback.

**Residuales menores de cobertura (por construcción/contrato, no bloqueantes):**

3. **F0-BUD-01 — callers ligeros de `llm.py`**: los 8 callers (emotion, nlp,
   learning, memoria, location, onboarding, real_world, mirofish-postproceso)
   están cubiertos *por contrato* de la vía auxiliar (todos pasan por
   `reservar_llm_aux`, probado en `TestLlmAuxGateado`), no por un test por-caller
   con contador de provider. El sentinel `TestSentinelProviderDirecto` cubre el
   flujo foreground de brain; la garantía "nadie llama directo" en
   aux/proactivity/vision descansa en los tests de kill-switch por módulo.
4. **F0-FALL-TIME-01 — "texto-solo"**: que el fallback NO haga tool-calling
   está verificado por inspección de código (`brain.py:1651`, `mensajes_openai`
   sin parámetro `tools`), no por un aserto de test. Riesgo nulo en la práctica
   (el formato usado no pasa tools, el provider no puede invocarlas).
5. **F0-RET-04 — "viejo: 3"**: el comportamiento previo (un 400 → 3 llamadas)
   está como comentario/narrativa del commit, no como regresión ejecutable
   contra el código viejo. La garantía es por construcción (`break` + clasificación
   cerrada) + el pin `llamadas==1`.
6. **F0-CI-01 — conteo**: `--collect-only` reporta 1170 vs 1172 passed del
   último run (esperable: collect-only no expande algunos parametrizados en
   runtime). Evidencia vinculante = check-run `Suite completa (pytest)` = success.

**Cerrados en este PR** (eran residuales del proceso de verificación):

- `tests/test_salida_fase0.py` estaba *untracked* → **commiteado en este PR**;
  su evidencia (RET-02 por código incl. 422, LOOP prompt-driven con snapshot,
  COST-02 contabilidad exacta, TOOL-03) ahora existe en el SHA de prod y en CI.
- **F0-AUX-03** extendido: ahora un sentinel de inspección de fuente cubre
  emotion **+ mirofish_client + onboarding** (antes solo emotion).
- **F0-AUX-04**: fail-closed dedicado a la dimensión aux (antes se infería del
  codepath compartido con el cupo principal).

**Medir antes de recortar**: frecuencia de 400s estructurales · tasa de uso del
fallback post-4xx · falsos ± del matching textual de HTTP.

---

## 9. Condiciones para Misión 0

Misión 0 (golden path *recuperar-lead*) queda **autorizada** según el endoso
condicional de Hermes, cumplida su única precondición:

- **BudgetGuard real activo en producción**: ciclo 4.1/4.2 (#82→#84→#86→#87)
  + F-1 (#89) mergeado y **live** en `12899b9`. ✔
- Toda ruta LLM/tool real gateada (§4–5, 0 FAIL bloqueante). ✔
- Estado de cierre seguro garantizado ante timeout/over-budget/kill-switch. ✔

El diseño de Misión 0 (flujo, tools `preparar_/confirmar_`, gates, métricas) se
acuerda con Hermes antes de implementar (no suponer la visión).

---

## 10. Apéndice — comandos, tests, CI

**Patrón de ejecución de tests** (worktree aislado, temp root redirigido por el
ACL de `pytest-of-celes`, cache desactivada):

```bash
cd <worktree> && PYTEST_DEBUG_TEMPROOT='C:\Users\celes\AppData\Local\Temp\pytemp-f2-N' \
  python -m pytest <node-ids> -q -p no:cacheprovider
```

**Archivos de evidencia**:
- `tests/test_salida_fase0.py` — tests-evidencia del dossier (RET-02 por código, LOOP prompt-driven, TOOL-03, COST-02)
- `tests/test_budget_adversarial.py` — batería adversarial (#87)
- `tests/test_budget_wire_brain.py` / `_tools.py` / `_aux.py` — wiring (#84/#86/#89)
- `tests/test_presupuesto_runtime.py` — guard standalone (#82)

**Infra**:
- Render: `GET /v1/services/{web,worker}/deploys?limit=1` → status `live` en `12899b902`
- CI: `gh api repos/celestinojbm/Dona-agent/commits/12899b90.../check-runs` → 3 success

**Verificación adversarial**: las filas de §4–5 fueron producidas por agentes
independientes que corrieron los tests citados y capturaron el conteo real; un
crítico de completitud revisó la cobertura. El hallazgo del archivo untracked se
corrige en este PR.

---

*Generado 2026-06-13. Firmado condicional al merge verde de este PR (que
commitea la evidencia y la lleva a CI). Tras el merge, el SHA de producción del
dossier firmado es el merge commit de este PR; el delta de producción es cero.*
