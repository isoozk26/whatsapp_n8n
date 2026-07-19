---
name: whatsapp-ai-reviewer
description: Audit n8n WhatsApp AI workflows, PostgreSQL state, Evolution API delivery, OpenAI policy, security, concurrency, retries and MVP readiness. Use for repository audits, workflow reviews, production incident analysis and release gates.
---

# WhatsApp AI Reviewer

Use this skill for read-only audits by default. Never send a customer or administrator message, trigger a live webhook, or mutate production data unless the user explicitly authorizes that exact action.

## Audit workflow

1. Read `AGENTS.md`, `README.md`, workflow JSON/builders, migrations, tests and deployment scripts.
2. Validate JSON, node names, connection targets, credential references and workflow settings.
3. Extract and syntax-check every Code node JavaScript block.
4. Trace webhook → normalize → auth → valid-event filter → ingest → batch claim → AI → policy/parser → outbox → delivery claim → provider → result.
5. Verify authentication precedes ingest, fail-closed behavior, secret handling and header/query transition behavior.
6. Verify message-id idempotency, unique delivery fingerprints, `FOR UPDATE SKIP LOCKED`, lease/recovery and concurrent worker safety.
7. Verify AI schema recovery, product-code/vehicle validation, unverified claim blocking and customer/admin separation.
8. Verify retry limits, backoff, circuit breakers, `failed`/`dead`, provider response validation, queue age and delivery latency.
9. Run offline checks before live checks. Use live APIs read-only unless explicit mutation is requested.

## Evidence rules

- Cite the exact file, node, SQL function, execution ID or test result for every finding.
- Label unknowns as `Varsayım:` and state the consequence if false.
- Never claim a migration, credential, header or deployment is live without direct evidence.
- Separate confirmed defects from risks requiring production evidence.

## Severity and output

Classify findings as P0 (security/core flow/data loss/duplicates), P1 (material reliability or operations), or P2 (non-blocking debt). For each finding provide evidence, impact, likelihood, risk score, concrete fix and verification test. A full audit ends with an executive summary, logic/architecture findings, edge cases, MVP score, release decision and remaining blockers.

## Project invariants

- Webhook auth precedes database ingest.
- `message_id` is idempotent.
- Only authorized `fromMe` `++`/`--` commands change manual mode.
- AI handoff, complaint, low confidence and validation do not silently lock a customer.
- Unverified stock, price, compatibility and shipping claims are never sent.
- Customer/admin deliveries are separate outbox records.
- Every AI/provider failure has bounded retry or dead-letter behavior.
- Secrets never appear in output, commits, workflow JSON or logs.

## Repository checks

```text
python build_workflow.py
python tools/wf_validate.py
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/wf_security.py
python tools/outbound_guard.py
```

Do not delete or weaken a failing test to make the audit pass.
