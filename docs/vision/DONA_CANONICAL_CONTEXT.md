# DONA_CANONICAL_CONTEXT

Fecha: 2026-05-24
Estado: contexto canónico operativo para Hermes, Claude Code, Codex y OpenClaw/Dona Control.
Propósito: preservar la visión actual de Dona, evitar regresiones de contexto y guiar trabajo técnico/producto.

Nota de uso: este documento es **contexto de visión y operación para agentes**, no un sustituto del estado real del código. Para estado técnico vigente, verificar siempre `git log`, `git status`, `README.md`, `CLAUDE.md`, tests y el código actual. Las secciones 16 y 18 son un snapshot fechado 2026-05-24 y deben actualizarse o contrastarse antes de tomar decisiones técnicas.

---

## 1. Definición actual de Dona

Dona es una **plataforma-agente multimodelo de negocio y ejecución controlada**.

Dona convierte situaciones, recursos, objetivos e intención en:

- diagnósticos;
- oportunidades;
- activos;
- workflows/playbooks;
- documentos;
- diseños;
- campañas;
- automatizaciones;
- software;
- acciones externas reales;
- reportes y medición.

Todo debe operar con:

- créditos operativos;
- permisos humanos;
- trazabilidad;
- audit logs;
- medición;
- control de riesgo;
- límites de gasto;
- privacidad y seguridad.

Frases guía:

- Dona convierte potencial en producción.
- Dona convierte intención en ejecución controlada.
- Dona no solo genera; Dona ejecuta con control.
- Dona no es otro chat de IA.

WhatsApp es un canal de entrada importante, pero no define todo el producto.

---

## 2. Qué NO es Dona

Dona no debe reducirse a:

- chatbot;
- asistente pasivo;
- CRM genérico;
- automatización simple;
- herramienta solo de growth marketing;
- wrapper de modelos;
- galería de herramientas;
- marketplace prematuro;
- AgentKit template;
- clon de Venice, Manus, Lovable, Luma, Higgsfield, Kittl o cualquier referencia externa.

Las referencias externas son insumos aditivos, no reemplazos de estrategia.

---

## 3. Principio central de producto

El usuario es dueño. Dona es directora/operadora asistida.

Dona debe:

1. Entender contexto.
2. Diagnosticar situación.
3. Detectar oportunidades.
4. Crear activos.
5. Proponer acciones.
6. Mostrar costo, riesgo y permiso requerido.
7. Ejecutar solo lo autorizado.
8. Medir resultados.
9. Recomendar el siguiente paso.

Dona debe ocultar complejidad técnica, pero **no** debe ocultar decisiones importantes, costos, permisos o riesgos.

---

## 4. Jerarquía de fuentes

### 4.1 Fuentes más actuales y fuertes

Usar como base principal:

Nota: las rutas con prefijo `workspace/` pertenecen al entorno OpenClaw/Dona Control y pueden no existir dentro de este repo. No asumir que son archivos locales; pedir a Hermes/OpenClaw el extracto relevante si hace falta consultarlas.

1. `workspace/reports/Dona_Documento_Base_Final_2026-05-13.html`
   - Plataforma-agente multimodelo de negocio con créditos, permisos, activos, workflows y ejecución controlada.

2. `workspace/memory/2026-05-12.md`
   - Dona debe incorporar amplitud tipo Venice.ai: chat, documentos, imagen, video, voz/audio, código, agentes, workflows, integraciones y API.
   - Diferencial: ejecución real controlada.

3. `workspace/reports/Dona_Vision_Plataforma_Agente_Multimodelo_Venice_Benchmark_2026-05-12.html`
   - Venice es referencia de amplitud multimodelo; Dona debe ir más allá con ejecución de negocio.

4. `workspace/DONA_CONTROL_ROOM/README.md`
   - Dona como acelerador/orquestador autónomo que diagnostica, construye, ejecuta acciones autorizadas, mide y optimiza.

5. `workspace/DONA_CONTROL_ROOM/02_ROADMAP.md`
   - Roadmap premium.

6. `workspace/DONA_REFERENCIAS/DONA_STYLE_MEMORY.md`
   - Dirección creativa premium, moderna, editorial, tecnológica pero humana.

### 4.2 Fuentes legacy importantes

Preservar como insumos, no como instrucciones literales:

- `DONA_DOCUMENTO_MAESTRO_VISION_2026-04-28.*`
- `DONA_VISION_FINAL_COMPLETA.md`
- `VISION_COMPLETA_DONA*`
- `VISION_MAESTRA_DONA_V4*`
- `DONA_LITE*`
- `PLAN_FASES*`
- `ENCUESTA_DONA_DETECCION.md`

Estas fuentes contienen ideas valiosas: ambición original, motores, Dona Lite, encuesta, visión económica, marketplace/Dona Network, Creative Studio y filosofía premium.

Deben ser reinterpretadas con seguridad, legal/compliance y estado técnico actual.

### 4.3 Fuentes técnicas que siempre requieren verificación

- snapshots `Dona-agent*` dentro de OpenClaw;
- reportes antiguos;
- logs;
- métricas;
- documentos técnicos no recientes.

El repo dentro de OpenClaw puede estar atrasado y no es fuente canónica de código.

---

## 5. Roles de agentes y herramientas

1. **Celestino**
   - Dueño estratégico.
   - Decide visión, prioridades, autorización de cambios sensibles y aprobación final.

2. **Hermes**
   - Orquestador técnico-operativo.
   - Guardián del contexto y la visión.
   - Coordina Claude Code, Codex, OpenClaw y otras herramientas.
   - Debe verificar estado real antes de actuar.

3. **Claude Code**
   - Implementador principal.
   - Trabaja en cambios concretos, PRs, tests, reportes.
   - No define visión final por sí solo.

4. **Codex**
   - Implementador/revisor/refactorizador complementario.
   - Útil para auditoría técnica, revisión de diffs, pruebas, refactors y segunda opinión.

5. **OpenClaw / Dona Control**
   - Memoria estratégica, auditor, crítico y expansor de visión.
   - No debe ser fuente única de verdad ni código canónico.
   - Puede revisar planes, detectar contradicciones, rescatar ideas olvidadas y auditar contexto.

6. **Herramientas nuevas**
   - Se tratan como referencias/capacidades candidatas.
   - No cambian estrategia salvo instrucción explícita de Celestino.

---

## 6. Reglas anti-regresión

Nunca hacer esto:

- reducir Dona a WhatsApp;
- reducir Dona a chatbot;
- reducir Dona a growth marketing;
- convertir Dona en una galería de herramientas sin iniciativas, permisos y resultados;
- construir marketplace completo antes del core loop;
- tratar OpenClaw/Claude/Codex como dueños de la visión;
- usar documentos antiguos como instrucciones literales;
- usar repo OpenClaw atrasado como código canónico;
- ejecutar acciones sensibles sin preview, costo, permiso, riesgo y audit trail;
- prometer ingresos garantizados;
- usar lenguaje de anti-ban/evasión de plataformas;
- ocultar uso de datos o costos relevantes al usuario.

---

## 7. Módulos centrales de Dona

### 7.1 Core product loop

El loop principal de Dona debe ser:

1. Entrada del usuario.
2. Contexto/memoria.
3. Diagnóstico.
4. Oportunidades.
5. Playbook/workflow.
6. Creación de activos.
7. Propuesta de acción.
8. Action Center.
9. Crédito/reserva/costo.
10. Permiso humano.
11. Ejecución controlada.
12. Medición.
13. Reporte.
14. Siguiente recomendación.

### 7.2 Capas de producto

1. Entrada conversacional
   - WhatsApp, web chat, dashboard; futuro: API, email, voz, plugins.

2. Contexto y memoria
   - usuario, negocio, objetivos, recursos, historial, activos, acciones, preferencias, límites.

3. Diagnóstico
   - situación actual, oportunidades, restricciones, capacidades, urgencias, riesgo.

4. Playbooks/workflows
   - rutas por tipo de usuario, acciones recomendadas, secuencias, checkpoints, medición.

5. Studio multimodelo
   - texto, documentos, imagen, video, voz/audio, código, research, assets comerciales.

6. Tool Intelligence Layer
   - selección de herramientas, costo, permisos, fallback, TOS/compliance, calidad esperada.

7. Action Center
   - acciones propuestas, aprobación/rechazo, costo, riesgo, preview, ejecución, estado, resultado.

8. Créditos
   - saldo, reserva, cobro, refund, top-ups, ledger, costo por acción.

9. Ejecución
   - dry-run, ejecutores LOW/MEDIUM/HIGH, integraciones, colas, reintentos, idempotencia.

10. Medición y optimización
   - audit logs, resultados, métricas, reportes y siguiente recomendación.

---

## 8. Créditos operativos

Los créditos de Dona son **capacidad operativa**.

Representan consumo/costo de acciones como:

- uso de modelos IA;
- generación de texto, imagen, video, voz o código;
- investigación;
- mensajes;
- automatizaciones;
- herramientas externas;
- assets;
- campañas;
- workflows.

Reglas:

- Usar el término “créditos operativos”.
- Mostrar saldo, costo estimado y movimientos relevantes.
- Previsualizar consumo antes de acciones sensibles.
- Separar créditos incluidos, top-ups, gasto externo, presupuesto publicitario y pagos a terceros.
- No tratar créditos como dinero transferible sin diseño legal.
- No implementar wallet, escrow, regalías o tokens transferibles sin revisión legal/compliance.

---

## 9. Permisos y niveles de riesgo

### 9.1 Autónomo

Dona puede hacer sin aprobación fuerte:

- analizar contexto;
- crear borradores;
- preparar assets internos;
- simular escenarios;
- organizar datos;
- generar reportes internos;
- proponer acciones.

### 9.2 Aprobación simple

Requiere confirmación del usuario:

- publicar contenido;
- enviar mensaje individual;
- activar workflow simple;
- crear landing pública;
- contactar prospecto individual.

### 9.3 Aprobación fuerte

Requiere preview claro, costo, riesgo, alcance y confirmación explícita:

- gastar dinero;
- enviar mensajes masivos;
- lanzar anuncios;
- comprar herramientas;
- modificar cuentas externas;
- cambios públicos importantes;
- acciones difíciles de revertir.

### 9.4 CRITICAL

Bloqueado por defecto.

Solo se habilita con diseño explícito, confirmación fuerte, audit log, rollback y autorización de Celestino si aplica.

Ejemplos CRITICAL:

- eliminar o sobrescribir datos masivamente;
- transferir dinero, crear obligaciones financieras o mover fondos;
- activar envíos masivos, campañas pagadas o automatizaciones difíciles de detener;
- cambiar credenciales, secretos, permisos de cuentas externas o configuración de producción;
- modificar integraciones con riesgo alto de TOS, privacidad, reputación o bloqueo de plataforma;
- ejecutar código no revisado contra producción;
- exponer datos personales, archivos privados o historiales sensibles.

---

## 10. Formato mínimo de una acción Dona

Toda acción propuesta debe incluir:

- qué hará;
- por qué;
- objetivo;
- costo/créditos;
- riesgo;
- permiso requerido;
- datos usados;
- herramienta/integración usada;
- preview cuando aplique;
- resultado esperado;
- métrica de éxito;
- fallback;
- reversibilidad;
- audit log.

---

## 11. Dirección visual y creativa

Dona debe sentirse:

- premium;
- clara;
- moderna;
- editorial;
- tecnológica pero humana;
- visualmente fuerte;
- fácil de entender;
- tipo producto de alto nivel;
- más aceleradora autónoma que chatbot.

Referencias aditivas:

- LumaLabs: video premium/futurista, outputs audiovisuales fuertes.
- Higgsfield: multimodalidad creativa experimental y usable.
- Kittl: diseño gráfico comercial refinado; mejor referencia visual que Canva.
- Lovable: intención → app/landing/herramienta, preview/edit/deploy loop.
- Venice.ai: amplitud multimodelo, créditos, privacidad, interfaz de modelos.
- Manus: ejecución delegada, pero evitar opacidad y generalismo.
- Linear: claridad de estados, workflows, UX premium operacional.
- Stripe: confianza, billing, créditos, historial y precisión financiera.
- Raycast/Vercel/Arc: velocidad, polish, command palette, modernidad.

Canva puede servir como referencia de accesibilidad, pero no como identidad visual de Dona.

---

## 12. Tool Intelligence Layer

Dona no debe construir todo desde cero. Debe saber seleccionar, combinar y orquestar herramientas.

Cada herramienta candidata debe tener ficha con:

- qué hace;
- API real disponible;
- si sirve para producción o solo como conector/UI;
- costo;
- permisos;
- TOS;
- privacidad;
- calidad esperada;
- fallback;
- riesgo;
- capa de Dona que mejora;
- prioridad.

Riesgos:

- no confundir inspiración con integración inmediata;
- no asumir API programática si solo existe UI;
- no usar herramientas creativas sin revisar licencias/IP;
- no automatizar plataformas contra TOS.

---

## 13. Usuarios y playbooks iniciales

Dona puede servir a muchos perfiles, pero no debe construir para todos al mismo tiempo.

Segmentos posibles:

- personas con habilidad no monetizada;
- microemprendedores;
- negocios pequeños;
- restaurantes/cafeterías;
- profesionales independientes;
- creadores;
- tiendas;
- agencias/freelancers;
- equipos pequeños.

Prioridad:

- mantener visión amplia;
- elegir 2-3 playbooks iniciales;
- medir activación y valor;
- iterar.

Playbooks iniciales posibles:

- diagnóstico de negocio;
- oferta comercial;
- perfil/bio/branding base;
- landing/catálogo;
- mensajes de venta;
- contenido 7 días;
- recuperación de leads;
- seguimiento WhatsApp;
- reporte semanal;
- mejora de dashboard/perfil.

---

## 14. Legacy ideas preservadas, pero no operativas todavía

Estas ideas deben seguir vivas como visión o backlog, pero no gobernar implementación inmediata:

- Dona como “sistema operativo económico”;
- Dona Lite;
- encuesta de detección;
- motor actuarial;
- Dona Network;
- marketplace;
- Creative Studio completo;
- API pública;
- agentes especializados;
- router multimodelo avanzado;
- browser/operator controlado;
- execution sandbox;
- white label;
- visión filosófica de abundancia/AGI/salario universal.

Reformulaciones obligatorias:

- “sistema operativo económico” → plataforma operativa/multimodelo para crecimiento y ejecución controlada;
- “motor actuarial” → motor de viabilidad/priorización hasta tener datos;
- “ingresos automáticos” → experimentos medibles para generar oportunidades;
- “Dona hace todo” → Dona prepara y ejecuta acciones autorizadas;
- “tokens/dinero” → créditos operativos no transferibles;
- “usuario no ve costos” → usuario ve costos/límites sin cargar complejidad técnica.

---

## 15. Legal, compliance y promesas

No usar como claim público ni comportamiento por defecto:

- ingresos garantizados;
- dinero rápido;
- probabilidades de éxito no validadas;
- operación 100% autónoma;
- usuario sin control;
- tokens como dinero;
- wallet/escrow/regalías sin marco legal;
- anti-ban/evasión de plataformas;
- entrenar IA sin informar;
- publicar/contactar/gastar sin permiso;
- AGI/salario universal como promesa comercial;
- “imposible que falle”.

Reglas:

- No prometer ingresos garantizados.
- No ejecutar gasto sin autorización.
- No enviar mensajes sin consentimiento/controles.
- No ocultar uso de datos.
- No revelar secretos.
- No automatizar contra TOS.
- Todo dinero, pagos, créditos transferibles, escrow, marketplace y comisiones requiere revisión legal/compliance.

---

## 16. Estado técnico actual resumido

Según memorias/reportes de OpenClaw y contexto actual:

### Avanzado/implementado

- Base de seguridad para webhooks/secrets/logs.
- Stripe/billing/créditos iniciales.
- Customer Portal.
- Top-ups.
- Dashboard con créditos/plan/movimientos/estado.
- Auth dashboard corregido.
- Tour inicial.
- Diagnóstico inicial extendido T2.0.E.
- Action Center / Automation Core T2.1.A.
- Dashboard/endpoints Action Center T2.1.B.
- Ejecutores LOW/MEDIUM con LLM/fallbacks T2.1.C.
- Créditos/reservas/reconciliación T2.1.D.
- Scheduler opt-in T2.1.E apagado por defecto.
- Primer executor HIGH WhatsApp T2.2 sin trigger expuesto.

### Pendientes críticos

- Verificar repo canónico en GitHub/msi.
- Confirmar branch/main actual.
- Completar smoke T2.1.D reservas/créditos en producción.
- Confirmar T2.2 sin trigger activo.
- Mantener scheduler apagado.
- No exponer HIGH WhatsApp hasta cerrar UX/permisos/smoke.
- Actualizar instrucciones de agentes con este canonical.

### Riesgos técnicos

- Identidad email/teléfono/Stripe/workspace necesita robustecimiento.
- Snapshots OpenClaw pueden estar desactualizados.
- Logs/métricas históricas no sustituyen observabilidad moderna.
- Riesgo de costos IA sin router/catálogos/límites.
- Riesgo de PII en logs futuros.
- Riesgo de activar ejecución HIGH prematuramente.

---

## 17. Reglas para trabajo técnico

Antes de tocar código:

1. Verificar fuente de verdad: repo GitHub/msi actual, no snapshots OpenClaw.
2. Revisar branch y diff.
3. Definir objetivo exacto.
4. Conectar cambio al producto y a este canonical.
5. Identificar archivos probables.
6. Definir criterios de aceptación.
7. Definir pruebas mínimas.
8. Definir riesgo/rollback.
9. No modificar env/deploy/secrets/DB/producción sin autorización explícita.

Todo paquete para Claude Code/Codex debe incluir:

- objetivo;
- contexto de producto;
- archivos probables;
- requisitos funcionales;
- UX/UI;
- seguridad;
- aceptación;
- tests;
- rollback;
- qué no tocar.

Nada se considera terminado sin:

- revisión de producto;
- revisión visual/premium si aplica;
- revisión técnica;
- revisión de seguridad;
- prueba funcional real o justificación de por qué no aplica.

---

## 18. Roadmap inmediato recomendado

Orden recomendado:

1. Distribuir este `DONA_CANONICAL_CONTEXT.md` a Hermes, Claude Code, Codex y OpenClaw.
2. Verificar repo canónico actual en msi/GitHub.
3. Completar smoke T2.1.D reservas/créditos.
4. Confirmar T2.2 post-merge sin trigger activo.
5. Mantener scheduler apagado hasta smoke completo.
6. Elegir el próximo PR pequeño.
7. Priorizar cerrar el core loop:
   - diagnóstico → oportunidad → activo → acción → aprobación → créditos → ejecución → medición → reporte.
8. Luego avanzar a Dona Studio multimodelo, router de modelos, agentes y assets.

---

## 19. Uso de OpenClaw desde ahora

OpenClaw debe usarse como:

- auditor de visión;
- memoria estratégica;
- detector de contradicciones;
- revisor de planes;
- fuente de ideas legacy;
- crítico de contexto.

OpenClaw no debe:

- reemplazar la visión actual;
- ejecutar código desde snapshots viejos;
- decidir roadmap final solo;
- tratar documentos antiguos como instrucciones literales;
- modificar repo/deploy/secrets sin autorización.

Cuando se le pida revisar algo, debe recibir:

1. Este canonical.
2. El documento de insights organizado.
3. El objetivo concreto.
4. Qué fuentes debe priorizar.
5. Qué no debe tocar.

---

## 20. Uso de referencias nuevas

Cuando Celestino comparta una nueva idea, producto, herramienta o referencia:

1. Tratarla como insumo aditivo.
2. Extraer capacidades, UX, estética o patrón operativo.
3. Clasificar qué capa mejora:
   - Studio;
   - Tool Intelligence Layer;
   - Action Center;
   - Playbooks;
   - agentes;
   - onboarding;
   - backend;
   - ejecución;
   - visual/branding;
   - GTM.
4. Evaluar costo, riesgo, permisos, privacidad y fallback.
5. Decidir: integrar ahora, documentar para después, usar como inspiración o descartar.
6. No interpretarla como pivote salvo instrucción explícita.

---

## 21. Resumen ultra corto para agentes

Dona es una plataforma-agente multimodelo que convierte contexto e intención en activos, workflows y acciones reales, con créditos, permisos, audit logs, medición y control humano.

No es chatbot, CRM genérico ni growth tool estrecha. WhatsApp es canal, no producto completo.

El core loop es: diagnosticar → proponer → crear → pedir permiso → ejecutar → medir → optimizar.

No prometer ingresos garantizados. No gastar, publicar, enviar o modificar cuentas externas sin permisos claros. No usar snapshots OpenClaw como código canónico. No dejar que documentos antiguos reemplacen la visión actual.

Hermes coordina. Claude Code implementa. Codex revisa/implementa. OpenClaw audita y preserva memoria. Celestino decide.
