# Plan de transición — Dona app-first

Objetivo: retirar limpiamente la oferta actual (cortar cobros, conservar
datos, sanear el repo) y construir la primera versión usable de Dona como
aplicación propia de propósito general: áreas, proyectos, responsables y
agentes que ejecutan trabajo con permisos, evidencia y supervisión.

WhatsApp queda como **canal opcional futuro**. No es el producto ni un
requisito para usar Dona. El servicio actual **no se reactiva**.

Documentos de esta carpeta:

| Archivo | Para qué |
|---|---|
| `PLAN.md` | este plan: jornadas, dependencias, reglas |
| `ESTADO.md` | hecho / probado / preparado / bloqueado |
| `ACCIONES-CELESTINO.md` | pasos de panel, con efecto y comprobación |
| `RESPALDO-Y-RETIRO.md` | inventario, respaldos y retiro de Render/Railway/Supabase |
| `MSI-RUNBOOK.md` | preflight y paquete de instalación en la MSI |
| `APP-FIRST.md` | diseño del producto mínimo (J7) |
| `EVIDENCIA.md` | SHA, comandos, resultados y límites de cada bloque |

`docs/CURRENT_STATE.md` es el snapshot anterior (Fase 0, julio). Desde ahora
el estado vivo es `ESTADO.md`.

---

## Reparto

| Quién | Qué |
|---|---|
| Claude Code | inspección del repo, código, pruebas, documentación, PRs. Sin paneles ni credenciales de producción |
| Celestino | decisiones y operaciones en Stripe, Render, Railway, Vercel, Supabase, Whapi/Meta, Cloudflare; aprueba cada merge |
| Hermes MSI | constructor/operador local, con encargos preparados por Claude Code y autorizados por Celestino |
| Hermes OptiPlex | auditor de solo lectura. Dona **no** se aloja ahí |

## Reglas que aplican a todas las jornadas

1. Ramas propias y PRs. Nada se fusiona a `main` ni se despliega sin OK
   explícito de Celestino: **un merge a `main` publica la landing en
   Vercel**.
2. Ni paneles de proveedores ni credenciales de producción desde Claude
   Code. Las acciones de panel quedan en `ACCIONES-CELESTINO.md`.
3. No se borran datos, no se reescribe historia, no se rotan secretos. El
   retiro de recursos lo hace Celestino, después de un respaldo comprobado.
4. Ningún secreto, dato personal ni identificador privado de infraestructura
   en commits, capturas o informes.
5. Sin llamadas facturables a modelos, sin mensajes, sin cobros reales:
   proveedores simulados en pruebas.
6. Se respetan las ramas de otras sesiones; si hace falta integrarlas, se
   hace en una rama candidata propia con dependencias declaradas.
7. Antes de usar un inventario, se comprueba el estado actual (SHA, PRs,
   versiones, CI).

---

## Jornadas y dependencias

```
J1 pausa ──┬──> J3 deps ──> J4 backend sin efectos ──> J5 paquete MSI ──> J6 conectividad ──┐
           └──> J2 respaldo/retiro (Celestino)                                               ├──> J7 app-first ──> J8 piloto
                                                                                             ┘
```

| Jornada | Entregable verificable | Depende de | Quién cierra |
|---|---|---|---|
| **J1** corte de cobros y pausa | checklist Stripe ejecutado; PR de pausa en producción con SHA verificado | — | Celestino (Stripe, merge, verificación) |
| **J2** respaldo y retiro | inventario cerrado; dumps cifrados con checksum y restauración aislada comprobada; acta de recursos retirados | J1 (cobros cortados) | Celestino |
| **J3** repo sano | rama candidata con #287 + #286 + #285 + pausa, CI completo verde, advisories revisados | J1 | Claude Code prepara; Celestino integra |
| **J4** backend sin efectos | perfil de pausa/staging con scheduler, workers y conectores apagados por defecto; tests de arranque | J3 (suite instalable) | Claude Code (PR) |
| **J5** paquete MSI | preflight de solo lectura; compose versionado, sin secretos, puertos solo en loopback | J4 | Claude Code prepara; Hermes MSI ejecuta preflight con OK |
| **J6** conectividad | staging accesible solo por accesos aprobados; health/readiness; rechazo no autorizado | J5 + OK de arranque | Celestino autoriza; Hermes MSI opera |
| **J7** base app-first | 1 área, 1 proyecto, 2 agentes (responsable/ejecutor), tareas con estados reales, aprobación y evidencia; proveedores simulados | J4 (y J6 para demo en MSI) | Claude Code (PRs) |
| **J8** piloto privado | demo con datos sintéticos, guía, mapa pantalla→API→prueba, términos actualizados; PR de relanzamiento separado y **sin** Stripe activo | J7 | Celestino acepta |

### Qué se puede adelantar en paralelo

- J2 (paneles) avanza en cuanto J1 corta los cobros, sin esperar a J3.
- Diseño de J7 (`APP-FIRST.md`) y preflight de J5 (`MSI-RUNBOOK.md`) se
  preparan sin depender de Celestino.
- J4 se puede escribir sobre la rama candidata de J3 antes de que J3 se
  integre (declarando la dependencia).

## Checkpoint al cerrar cada jornada

En `ESTADO.md` y en el mensaje de cierre:

- Rama, PR y SHA exacto.
- Cambios terminados.
- Pruebas ejecutadas y resultados.
- Lo preparado que aún no se ha aplicado.
- Acciones concretas de Celestino.
- Limitaciones y riesgos pendientes.
- Próximo bloque y cómo reanudar (`git fetch origin && git checkout <rama>`
  y el comando de pruebas del bloque).
