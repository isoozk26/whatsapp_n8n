---
name: n8n-workflow-fixer
description: Diagnose and safely implement fixes in the FiltreOto n8n WhatsApp workflow, Python workflow builders, generated JSON, PostgreSQL migrations and offline tests. Use when changing workflow logic, message templates, authentication, batching, manual mode, AI policy, outbox delivery or recovery behavior.
---

# n8n Workflow Fixer

Treat Python builders and SQL migrations as sources of truth. Do not make a durable fix only in generated workflow JSON or the live n8n editor.

## Fix workflow

1. Read `AGENTS.md`, the relevant builder, generated workflow, migrations and tests.
2. Reproduce the defect from code, execution evidence or a deterministic test. Distinguish webhook, ingest, AI, policy, outbox and provider failures.
3. Preserve unrelated dirty-worktree changes. Patch the smallest source-of-truth surface.
4. Prefer a new idempotent migration for production schema/data behavior. Use `CREATE OR REPLACE`, guarded DDL and targeted cleanup; never erase broad production data without explicit approval.
5. Regenerate workflow JSON from its builder after builder changes.
6. Add or update a regression test for the exact defect.
7. Run the repository checks before proposing deployment.

## Required safeguards

- Keep authentication before database ingest.
- Keep message and delivery idempotency intact.
- Use parameterized SQL and atomic claims with `FOR UPDATE SKIP LOCKED` or an equivalent proven mechanism.
- Allow only authorized `fromMe` commands to change manual mode.
- Never allow AI handoff to silently lock later customer messages.
- Keep customer and administrator outbox records independent.
- Reject invented product codes and unverified stock, price, compatibility or shipping claims.
- Never embed secrets or credential values in code, JSON, tests or logs.
- Never send a live customer/admin message during validation without explicit approval.

## Validation commands

Run applicable checks in this order:

```text
python build_workflow.py
python tools/wf_validate.py
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/wf_security.py
python tools/outbound_guard.py
```

Treat a generated-file drift, JavaScript syntax error, broken connection, secret finding or outbound-guard failure as a release blocker. Do not weaken tests to pass.

## Handoff

Report the root cause, changed behavior, files changed, tests run, remaining live prerequisites and whether deployment/push occurred. Do not claim production success from local tests alone.
