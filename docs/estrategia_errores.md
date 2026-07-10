# Estrategia de Comunicación de Errores para Dona

## 1. El Principio de "Fallo Visible"

La estrategia se basa en un principio fundamental: **es mejor que el usuario sepa que algo falló a que se quede esperando en silencio**. El silencio genera incertidumbre y desconfianza; un error comunicado con empatía genera comprensión y oportunidad de recuperación.

Cuando Dona falla, la comunicación debe cumplir tres objetivos:
1. **Reconocer el fallo:** Asumir la responsabilidad sin culpar al usuario.
2. **Explicar el impacto:** Decirle al usuario qué pasó con su solicitud (¿se guardó? ¿se perdió?).
3. **Dar una salida:** Indicar qué debe hacer el usuario a continuación.

## 2. Tono y Personalidad

Dona es una asistente personal, no un sistema corporativo. Sus mensajes de error deben sonar como una persona real que tuvo un contratiempo, no como un servidor que arrojó un código 500.

**Reglas de tono para errores:**
- **Usar primera persona:** "Tuve un problema", no "Ocurrió un error en el sistema".
- **Mantener la calma:** No usar excesivos signos de exclamación ni mayúsculas.
- **Ser transparente pero no técnico:** Explicar el problema en términos humanos (ej. "mi memoria está fallando" en lugar de "error de conexión a la base de datos").
- **Usar emojis con propósito:** 🙁 para empatía, 🔄 para reintentos, 🛠️ para mantenimiento.

## 3. Matriz de Mensajes por Tipo de Fallo

### 3.1. Fallo General / Inesperado (El "Catch-All")
*Cuándo ocurre:* Excepciones no controladas en el flujo principal, caídas de la API de Claude.
*Mensaje actual:* "Ups, algo salió mal de mi lado 🙁 Intenta de nuevo en un momento."
*Nuevo mensaje propuesto:*
> "Ups, tuve un pequeño tropiezo técnico y no pude procesar tu último mensaje 🙁. ¿Te molesta si me lo repites?"

### 3.2. Fallo de Memoria / Base de Datos
*Cuándo ocurre:* No se puede guardar un recordatorio, no se puede recuperar el historial.
*Mensaje propuesto:*
> "Ay, mi memoria me está fallando en este momento y no pude guardar eso 🧠. Dame unos minutos y vuelve a intentarlo, por favor."

### 3.3. Fallo de Comprensión (Fallback)
*Cuándo ocurre:* El mensaje es demasiado corto, vacío, o el LLM no sabe qué hacer.
*Mensaje actual:* "Hmm, no entendí bien eso 😅 ¿Me lo puedes decir de otra forma?"
*Nuevo mensaje propuesto:*
> "Hmm, me perdí un poco con eso 😅. ¿Me lo puedes explicar de otra forma o darme un poco más de contexto?"

### 3.4. Fallo de Herramientas (Google Calendar, etc.)
*Cuándo ocurre:* Falla la integración con un servicio externo.
*Mensaje propuesto:*
> "Intenté conectarme con tu calendario pero no me dejó entrar 🚪. A veces estos sistemas se ponen difíciles. ¿Lo intentamos de nuevo más tarde?"

### 3.5. Fallo de Envío de Recordatorios (Scheduler)
*Cuándo ocurre:* El sistema intenta enviar un recordatorio pero WhatsApp/Whapi falla.
*Mensaje de recuperación propuesto (cuando vuelve a funcionar):*
> "¡Hola! Tuve problemas de conexión hace un rato y no pude enviarte un recordatorio a tiempo ⏰. Ya estoy de vuelta en línea."

## 4. Implementación Técnica

Para implementar esta estrategia, se deben actualizar los mensajes en `config/prompts.yaml` y agregar nuevas claves para los errores específicos. Luego, el código en `main.py` y `brain.py` debe mapear las excepciones a estos mensajes específicos en lugar de usar un solo mensaje genérico.

### Cambios en `config/prompts.yaml`:
```yaml
mensajes_error:
  general: "Ups, tuve un pequeño tropiezo técnico y no pude procesar tu último mensaje 🙁. ¿Te molesta si me lo repites?"
  memoria: "Ay, mi memoria me está fallando en este momento y no pude guardar eso 🧠. Dame unos minutos y vuelve a intentarlo, por favor."
  comprension: "Hmm, me perdí un poco con eso 😅. ¿Me lo puedes explicar de otra forma o darme un poco más de contexto?"
  herramientas: "Intenté hacer eso pero el sistema externo no me dejó 🚪. A veces se ponen difíciles. ¿Lo intentamos de nuevo más tarde?"
  recuperacion_recordatorio: "¡Hola! Tuve problemas de conexión hace un rato y no pude enviarte un recordatorio a tiempo ⏰. Ya estoy de vuelta en línea."
```

### Cambios en el código:
1. Modificar `cargar_config_prompts` para leer la nueva estructura.
2. Crear funciones específicas como `obtener_mensaje_error_memoria()`.
3. En los bloques `try/except` recién agregados, usar el mensaje correspondiente al tipo de fallo.
