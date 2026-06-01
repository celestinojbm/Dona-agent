# Tool Ledger — Landing Premium Prototypes

Fecha: 2026-05-31
Run ID: `2026-05-31-landing-premium-prototypes`
Riesgo: MEDIUM

## Herramientas previstas

### Claude Code

- Modelo: `claude-opus-4-8`
- Effort: `max`
- Modo: print mode (`-p`)
- Workspace: `C:\Users\celes\dona-worktrees\landing-premium-prototypes`
- Permisos esperados: lectura/escritura de docs/prototype artifacts, comandos de validación offline.

### Git

- Branch: `feat/landing-premium-prototypes`
- Base: `origin/main` en `4897759`

### Browser QA

- Abrir archivo HTML local generado.
- Verificar visualmente estructura, legibilidad y que existan 3 variantes.
- Sin login, sin formularios externos, sin producción.

### Validadores offline

- `git diff --check`
- `python scripts/validate_agent_runs.py`
- `python -m json.tool docs/ops/agent-runs/index.json`
- scope check
- secret scan básico

## Herramientas prohibidas

- APIs productivas de Dona.
- Deploys.
- Acceso a `.env` o secretos.
- Proveedores de imagen/video pagos.
- Formularios o acciones externas.

## Cierre

Pendiente.

## Registro real de herramientas

- Claude Code Opus 4.8 `max` generÃ³ `dona-landing-premium-prototypes.html` parcialmente/completamente, pero quedÃ³ corriendo sin cerrar JSON.
- Hermes detuvo PIDs de Claude/PowerShell asociados cuando el HTML ya existÃ­a para evitar loop/costo indefinido.
- Hermes agregÃ³ `README.md`, eliminÃ³ `_parts`, normalizÃ³ caracteres de control y aÃ±adiÃ³ una franja comparativa inicial.
- Browser QA se ejecutÃ³ sobre servidor local temporal `http://127.0.0.1:8765/` en copia del artefacto.
- Browser console: 0 mensajes, 0 errores JS.
