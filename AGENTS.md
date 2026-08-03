# WhatsApp AI Repository Rules

This repository contains the FiltreOto WhatsApp AI system: n8n, PostgreSQL, Evolution API and OpenAI.

## Session startup

At the beginning of every repository task, read this file, then load the matching project skill:

- Audits and incident analysis: `.codex/skills/whatsapp-ai-reviewer/SKILL.md`
- Workflow, SQL or message-policy fixes: `.codex/skills/n8n-workflow-fixer/SKILL.md`
- Migration, deploy, production verification or two-remote push: `.codex/skills/production-release-gate/SKILL.md`

Use the smallest matching skill set. Re-read relevant migrations and the workflow builder before changing behavior.

## Critical flow

Evolution webhook → normalize → authenticate → validate event → PostgreSQL ingest → batch claim → OpenAI policy → transactional outbox → delivery claim → Evolution API → delivery result.

## Non-negotiable rules

1. Authenticate before ingesting data.
2. Preserve message-id idempotency and concurrent claim safety.
3. Keep customer and administrator deliveries separate.
4. Never invent product codes or promise unverified stock, price, compatibility or shipping.
5. Only authorized `fromMe` `++`/`--` commands may change manual mode.
6. AI handoff must not silently block future customer messages.
7. Do not expose or commit credentials, tokens, phone numbers or database secrets.
8. Never send live messages during tests or audits without explicit approval.

## Change and release process

Inspect first, patch narrowly, run syntax/contract/behavior/security/outbound checks, then report exact results. Before production deployment, verify credentials, webhook headers, migration status, active workflow and execution settings. Do not declare success without evidence.

Runbook standardı:

- Canonical operasyon dokümanı `docs/runbook.md`'dir.
- `docs/RUNBOOK.md` ile yapılan eski referanslar artık bu dosyayı kasteder.
- Her deploy'da operasyon notları, evidence ve açık bulgular `docs/runbook.md` içinde güncellenir.

## Local deterministic tools

The project MCP server is configured in `.codex/config.toml` and exposes read-only workflow checks. Before proposing a workflow deployment, run `release_gate`. A `BLOCKED` decision is a release blocker; do not bypass or weaken the failing check.

```text
npm install
npm run release:gate
npm run test:mcp
```
