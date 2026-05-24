# Permissions Model — Hermes para Dona Agent

## Principio

Hermes debe operar con privilegio mínimo. Un token amplio no es una comodidad aceptable para operación diaria si permite tocar workflows, secrets, deploys o configuración admin.

## Roles de credencial

### HERMES_READ

Uso permitido:
- Leer repositorio.
- Leer issues/PRs/commits.
- Leer checks/statuses/logs si aplica.

Permisos esperados:
- Metadata: read
- Contents: read
- Pull requests: read
- Issues: read
- Checks: read
- Actions: read, solo para logs

Prohibido:
- Push.
- Crear PRs.
- Modificar workflows.
- Secrets/settings/deploys.

### HERMES_PR_WRITE

Uso permitido:
- Crear ramas.
- Push a ramas no protegidas.
- Crear/actualizar PRs.
- Comentar PRs.

Permisos esperados:
- Contents: write, limitado al repo.
- Pull requests: write.
- Issues: write, si se necesitan comentarios/labels.
- Checks/Actions: read.

Prohibido:
- Push directo a main.
- Workflow write.
- Repo administration.
- Secrets/environments.
- Deploy write.

### HERMES_CI_READ

Uso permitido:
- Leer CI/checks/logs.
- Diagnosticar fallos.

Permisos esperados:
- Actions: read.
- Checks: read.
- Contents: read.
- Pull requests: read.

Prohibido:
- Modificar workflows.
- Re-run con costo o side effects sin aprobación.
- Deploy.

### HERMES_DEPLOY

Uso permitido:
- Deploy/rollback a staging o producción cuando exista aprobación humana.

Condición:
- No debe estar cargado en sesiones normales.
- Debe ser temporal, auditado y preferiblemente limitado a staging.

Prohibido:
- Uso para lectura normal.
- Uso sin Run Ledger HIGH/CRITICAL.

### HERMES_ADMIN

Uso permitido:
- Cambiar branch protection, secrets, environments, repo settings, collaborators.

Condición:
- Evitar como estado normal del agente.
- Preferir ejecución humana manual.
- Si se usa con Hermes, debe ser sesión temporal con aprobación reforzada.

## Registro obligatorio en Run Ledger

Cada tarea debe declarar:

- Credencial prevista.
- Credencial realmente usada.
- Por qué era el menor permiso posible.
- Si hubo 403/permisos insuficientes.
- Si se pidió escalación humana.

## Estado actual conocido

En la auditoría de 2026-05-24 se observó un token de GitHub CLI en `msi` con scopes amplios (`repo`, `workflow`, `read:org`, `gist`). Ese estado no cumple privilegio mínimo para operación diaria. Debe migrarse a tokens separados antes de aumentar autonomía.

## Reglas de bloqueo

- Si una tarea de lectura requiere ADMIN, detener y revisar permisos.
- Si una tarea normal requiere workflow write, subir a HIGH y pedir aprobación.
- Si una tarea requiere secrets/deploy/settings, subir a CRITICAL y pedir aprobación reforzada.
- Nunca resolver un 403 aumentando permisos automáticamente.
