# Tool Ledger — <RUN_ID>

## Regla

Cada herramienta usada en una tarea MEDIUM+ debe poder justificarse por necesidad, alcance mínimo y evidencia resultante.

## Tabla principal

| # | Tool | Acción | Motivo | Entrada sensible | Resultado | Riesgo | Evidencia |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  | No / Sí redactada |  | LOW/MEDIUM/HIGH/CRITICAL |  |

## Checklist por tool call

Antes de usar una herramienta, responder:

- [ ] ¿La herramienta es necesaria?
- [ ] ¿Es la herramienta de menor privilegio posible?
- [ ] ¿El scope está dentro del Run Ledger?
- [ ] ¿Puede exponer secrets, tokens, PII o producción?
- [ ] ¿Requiere aprobación humana?
- [ ] ¿Existe una forma de verificar el resultado?

Después de usarla:

- [ ] Resultado registrado.
- [ ] Error/reintento registrado si ocurrió.
- [ ] No se imprimieron secrets ni PII innecesaria.
- [ ] Si apareció dato sensible, se detuvo o se redactó.

## Clasificación de herramientas

| Tipo | Ejemplos | Riesgo base | Notas |
| --- | --- | --- | --- |
| Lectura local | read_file, search_files | LOW | Subir a MEDIUM si lee datos sensibles |
| Escritura repo | write_file, patch | MEDIUM | Solo archivos autorizados |
| Shell/git | terminal | MEDIUM | Prohibido deploy/secrets/live sin aprobación |
| GitHub PR | gh pr create/view | MEDIUM | No settings/secrets/workflows |
| Revisión agente | Codex, delegate_task | MEDIUM | Read-only salvo autorización explícita |
| Producción | Vercel/Render/DB/Stripe/Meta | HIGH/CRITICAL | Fuera de scope por defecto |
| Secrets/admin | GitHub settings, tokens, .env | CRITICAL | Humano/aprobación reforzada |

## Cierre

- Total tool calls:
- Tool calls fuera del plan: sí/no.
- Justificación de cualquier desvío:
- Evidencia principal:
