# deploy/msi — Dona staging en la MSI

Paquete del bloque J5. Procedimiento completo, preflight y conectividad:
`docs/transition/dona-app-first/MSI-RUNBOOK.md`.

| Archivo | Qué hace | ¿Cambia algo? |
|---|---|---|
| `validar.sh` | Valida el compose (proyecto `dona`, puertos solo en `127.0.0.1`, Redis sin puertos). Sin daemon de Docker | No |
| `construir.sh <sha>` | `git archive` del commit exacto → imagen `dona-api:<sha>` | Crea una imagen |
| `arrancar.sh [--arq]` | Valida, comprueba imagen y permisos del env file, levanta el stack | **Arranca contenedores: requiere OK de Celestino** |
| `estado.sh` | Contenedores, consumo, SHA en ejecución, volúmenes y salud de Dona | No |
| `parar.sh` | `docker compose stop` del stack `dona` | Para contenedores; **conserva volúmenes** |
| `dona.env.example` | Perfil de pausa: efectos externos apagados, sin credenciales de cobro, envío ni modelos | — |

Reglas que verifica `tests/test_deploy_msi.py` en CI:

- Solo se publican puertos en `127.0.0.1`. Dentro del contenedor la app
  escucha en `0.0.0.0:8000`; lo que limita la exposición es el puerto
  publicado del host.
- La imagen se identifica por el SHA del commit (`DONA_SHA`, obligatorio).
- El scheduler está forzado a apagado en el worker (un solo responsable).
- Ningún script contiene `down -v`, `volume rm` ni `prune`.
- El env de ejemplo trae todos los efectos en `false` y ningún secreto con valor.

No usar el `docker-compose.yml` de la raíz del repo para la MSI: publica el
puerto en todas las interfaces y monta `./knowledge` y `./config` del árbol
de trabajo.
