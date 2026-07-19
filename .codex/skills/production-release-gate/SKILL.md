---
name: production-release-gate
description: Validate, migrate, deploy and verify the FiltreOto WhatsApp AI system in production. Use for n8n releases, PostgreSQL migration rollout, two-remote Git pushes, post-deploy execution checks, rollback decisions and production readiness confirmation.
---

# Production Release Gate

Require explicit authorization before mutating live n8n, PostgreSQL or Git remotes. Authorization to deploy does not authorize sending customer or administrator messages.

## Release sequence

1. Read `AGENTS.md`, the relevant diff, migration files and deployment tools.
2. Confirm the intended files only; preserve unrelated working-tree changes and untracked user files.
3. Run builder, validation, contract, behavior, security and outbound-guard checks. Stop on any blocker.
4. Scan the diff for credentials, API keys, webhook secrets, phone numbers and destructive SQL.
5. Apply required idempotent database migrations before deploying workflows that depend on them.
6. Require explicit success evidence from the migration runner; an HTTP status alone is insufficient.
7. Deploy the generated workflow with the repository deployment tool, preserving credential references by name.
8. Verify `active=true`, the published version, workflow settings, auth node, send URL and credential reference with read-only API calls.
9. Inspect new webhook/worker executions and queue state read-only. Do not trigger a live webhook or outbound message unless separately approved.
10. Commit only task files and push both `github/main` and `origin/main` when requested.

## Release blockers

- Missing or rejected API credentials.
- Migration failure, unknown migration state or generated drift.
- Webhook auth after ingest or fail-open secret handling.
- Missing Evolution credential reference.
- Failing contract/security/outbound checks.
- Unbounded retry, stuck `sending`, unexpected `dead` growth or duplicate delivery evidence.
- `saveDataSuccessExecution` not set to `all` during production diagnosis.

## Rollback and recovery

- Do not use destructive Git reset or overwrite user changes.
- Retain the previous published workflow/version as rollback evidence.
- If migration state is uncertain, stop workflow deployment and diagnose first.
- If a customer is blocked by stale state, use a targeted, reviewed migration; do not replay an ignored message without outbound approval.

## Release report

State the commit, both remote results, migration result, active published version, tests, execution evidence and unresolved manual steps. Redact all secret values.
