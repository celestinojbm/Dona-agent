# Run Ledger — PR #56 HIGH dedicated confirmation

## Metadata

- Run ID: RUN-2026-05-25-high-dedicated-confirmation
- Agent-run ID: 2026-05-25-pr56-high-dedicated-confirmation
- Date: 2026-05-25
- PR: #56
- Branch: feat/high-dedicated-confirmation
- Merge commit: ffeffd5c560274f2ac25b8c081df2745e8d20f0d
- Risk: HIGH
- Status: merged

## Objective

Build the first real dedicated HIGH confirmation path for `enviar_mensaje_whatsapp` while keeping generic HIGH execution blocked.

The implementation adds an authenticated preview, exact human confirmation (`ENVIAR`), backend revalidation of ownership/type/risk/state, and concurrency-safe execution claiming before any provider call.

## Scope

Included:

- Backend dedicated preview and confirmation helpers for WhatsApp HIGH sends.
- Internal HMAC endpoints for `high-preview` and `high-confirmar`.
- Next route handlers that resolve `subscriptionId` server-side from auth.
- Action Center UI for preview and exact confirmation.
- Atomic `running` claim before credit reservation/provider call.
- Tests for non-string confirmation, no trim/coercion, sequential double confirmation, concurrent confirmation, provider mock, reservation state and saldo.

Excluded:

- No production/manual sends.
- No provider credentials or env changes.
- No scheduler changes.
- No deploy setting changes.
- No live payment/social/messaging provider configuration changes.
- No CRITICAL action execution.
- No automatic merge.

## Agents and roles

- Hermes: orchestration, implementation, tests, verification, msi publication and post-merge sync.
- Subagente read-only: independent security/code review focused on IDOR, confirmation coercion, double-send, credit races and PII logging.

Claude Code and Codex were not used directly for this PR. Codex was unavailable on the VPS, so the independent review used the read-only subagent fallback.

## Key decisions

- Keep generic `/acciones/ejecutar` blocked for HIGH.
- Require dedicated preview before confirmation.
- Require exact string `ENVIAR`; no `String(...)`, trim or coercion.
- Reject public route payloads such as `confirmacion: ["ENVIAR"]`.
- Do not auto-approve in the dedicated public path.
- Claim `running` atomically before reserving/charging credits to avoid double-send and reservation-release races.
- Allow preview to show full destination/message only to the authenticated owner; do not log those values.

## Verification

- `python -m pytest tests/test_automation_send_message_high.py tests/test_automation_endpoints.py tests/test_automation_execution.py tests/test_automation_creditos_reservas.py tests/test_automation_action_center.py -q`: 100 passed.
- `cd landing && npm test`: 58 passed.
- `cd landing && npm run lint`: 0 errors, 3 pre-existing warnings.
- `python -m pytest -q`: 933 passed, known aiosqlite/event-loop warnings.
- `git diff --check`: OK.
- Sensitive-value scan of diff: no findings.
- Independent read-only review final verdict: APROBADO.
- PR checks: Agent Runs Validation, Vercel and Vercel Preview Comments success.
- Post-merge smoke: `python scripts/validate_agent_runs.py` OK and `TestConfirmacionDedicadaHigh` 4 passed.

## Outcome

PR #56 was merged into `main` and both msi and VPS workspaces were synced cleanly. The HIGH WhatsApp send path now has a dedicated controlled execution gate.

## Rollback

Revert PR #56 if the dedicated HIGH confirmation path causes runtime issues. Generic HIGH execution was intentionally kept blocked, so rollback returns Dona to the previous safer state without a public HIGH send path.

## Residual risks

- HIGH external-effect path now exists and must remain guarded by preview, approval and exact confirmation.
- Product-level audit log/cost preview can be strengthened further.
- Test warnings from aiosqlite/event-loop remain a separate technical debt.
