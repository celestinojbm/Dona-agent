# SLA Interno de Resolución de Errores (Fase de Lanzamiento)

Este documento define los Acuerdos de Nivel de Servicio (SLA) internos para el proyecto Dona. Al ser un proyecto en fase de lanzamiento operado por una sola persona, este SLA no es una promesa pública, sino una **herramienta de priorización interna** para evitar el agotamiento (burnout) y asegurar que los problemas críticos se resuelvan rápido sin sacrificar el desarrollo de nuevas funcionalidades.

## 1. Clasificación de Severidad

Los errores se clasifican en tres niveles de severidad, basados en el impacto real sobre la experiencia del usuario.

| Nivel | Nombre | Descripción | Ejemplos |
|---|---|---|---|
| **P1** | **Crítico (Caída Total)** | Dona no responde a ningún usuario, o una función core (recordatorios) está completamente rota. | - Whapi bloqueado por falta de pago.<br>- Base de datos caída (Supabase down).<br>- Claude API rechazando todas las peticiones. |
| **P2** | **Alto (Degradación)** | Dona responde, pero con errores frecuentes, o una función importante falla para algunos usuarios. | - Fallos intermitentes de conexión a Google Calendar.<br>- Dona responde con el mensaje de error "general" a ciertos prompts específicos.<br>- Retrasos de >5 minutos en enviar recordatorios. |
| **P3** | **Bajo (Cosmético/Aislado)** | Dona funciona, pero hay comportamientos extraños que no bloquean el uso principal. | - Dona usa un emoji raro.<br>- El resumen matutino tiene un error tipográfico.<br>- Un usuario específico tiene un problema con su zona horaria. |

## 2. Tiempos de Respuesta y Resolución Esperados

Dado que el equipo es de una sola persona, los tiempos de resolución asumen horario laboral normal (ej. 9 AM - 7 PM), excepto para los P1 que requieren atención inmediata si ocurren durante el día.

| Nivel | Tiempo de Detección (TDD) | Tiempo de Primera Respuesta (TTR) | Tiempo de Resolución Esperado |
|---|---|---|---|
| **P1** | < 2 horas | Inmediato (mensaje masivo si es posible) | **< 4 horas** (desde la detección) |
| **P2** | < 24 horas | Siguiente día hábil | **< 48 horas** |
| **P3** | Revisión semanal | N/A (no requiere respuesta directa) | **En el próximo ciclo de desarrollo** |

*Nota: El "Tiempo de Primera Respuesta" se refiere a avisar a los usuarios afectados (si es posible) de que se está trabajando en el problema, no necesariamente a tener la solución lista.*

## 3. Protocolo de Actuación por Nivel

### Protocolo P1 (Crítico)
1. **Confirmar:** Verificar en los logs de Render (`https://dashboard.render.com/`) si el error es generalizado.
2. **Contener:** Si el error es por un deploy reciente, hacer *rollback* al commit anterior inmediatamente. No intentar arreglar en caliente (hotfix) si el rollback toma menos de 5 minutos.
3. **Comunicar:** Si la caída dura más de 1 hora, enviar un mensaje manual a los usuarios activos (si son pocos) avisando del mantenimiento.
4. **Resolver:** Diagnosticar y aplicar el fix.

### Protocolo P2 (Alto)
1. **Reproducir:** Intentar reproducir el error enviando un mensaje a Dona desde un número de prueba.
2. **Aislar:** Identificar si el problema es de código, de base de datos, o de un proveedor externo (ej. Whapi, Anthropic).
3. **Planificar:** Asignar un bloque de 1-2 horas al día siguiente para resolverlo. No interrumpir el trabajo actual a menos que amenace con convertirse en P1.

### Protocolo P3 (Bajo)
1. **Registrar:** Anotar el bug en una lista de tareas (Notion, Trello, o un archivo de texto).
2. **Ignorar temporalmente:** No interrumpir el flujo de trabajo.
3. **Agrupar:** Resolver varios P3 juntos durante un día dedicado a "limpieza de bugs" (ej. viernes por la tarde).

## 4. Herramientas de Monitoreo Actuales

Para cumplir con este SLA, se depende de las siguientes herramientas:
- **Logs de Render:** Fuente principal de verdad. Revisar proactivamente 1 vez al día durante la primera semana de lanzamiento.
- **Endpoint `/diagnostico`:** Usar para verificar rápidamente si Whapi y la red están funcionando.
- **Mensajes de Error Visibles:** Gracias a la estrategia de "fallo visible", los usuarios recibirán mensajes específicos (ej. "mi memoria está fallando"). Si un usuario reporta uno de estos mensajes, acelera el diagnóstico.

## 5. Regla de Oro del SLA

**Si un bug P2 o P3 toma más de 2 horas en resolverse, se pausa.** Se documenta lo aprendido y se retoma al día siguiente. El objetivo en la fase de lanzamiento es mantener el sistema vivo (P1) y aprender de los usuarios, no tener un código perfecto.
