# WhatsApp n8n Workflow Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Secure the WhatsApp n8n workflow by eliminating hardcoded secrets, implementing proper webhook authentication, and enabling SSL verification across all components.

**Architecture:** 
1. Move hardcoded API keys to environment variables and n8n credentials
2. Implement proper webhook authentication using n8n's built-in query authentication
3. Enable SSL verification in all network requests
4. Update deployment and test scripts to use secure practices

**Tech Stack:** Python 3, n8n, Evolution API, SSL/TLS

## Global Constraints
- All API keys must be stored in environment variables or n8n credentials
- All network requests must use SSL verification
- Webhook authentication is required for all incoming requests
- Environment variables must have fallback values for local testing

---

### Task 1: Remove Hardcoded Evolution API Keys

**Covers:** S1
<!-- spec section anchors this task implements; every task that produces
     spec-required behavior must list at least one. Omit only for pure
     scaffolding tasks (e.g. project setup) that map to no spec section. -->

**Files:**
- Modify: `build_workflow.py:1161`
- Modify: `build_workflow.py:1243`
- Modify: `build_workflow.py:1259`
- Modify: `build_workflow.py:1275`
- Modify: `build_workflow.py:1291`

**Interfaces:**
- Consumes: Environment variables for API keys
- Produces: HTTP request nodes that use environment variables for API keys

- [ ] **Step 1: Update Delete Command Message node to use environment variable**

In `build_workflow.py`, find the Delete Command Message node parameters (around line 1161) and change:
```python
{"name": "apikey", "value": os.environ.get('EVOLUTION_API_KEY', '089311B617B8-48CF-8BD6-29759A57FDBF')},
```
to:
```python
{"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
```

- [ ] **Step 2: Update Phone A Send node to use environment variable**

In `build_workflow.py`, find the Phone A Send node parameters (around line 1243) and change:
```python
{"name": "apikey", "value": os.environ.get('EVOLUTION_API_KEY', '089311B617B8-48CF-8BD6-29759A57FDBF')},
```
to:
```python
{"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
```

- [ ] **Step 3: Update Phone B Send node to use environment variable**

In `build_workflow.py`, find the Phone B Send node parameters (around line 1259) and change:
```python
{"name": "apikey", "value": os.environ.get('EVOLUTION_API_KEY', '089311B617B8-48CF-8BD6-29759A57FDBF')},
```
to:
```python
{"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
```

- [ ] **Step 4: Update Reply to Customer node to use environment variable**

In `build_workflow.py`, find the Reply to Customer node parameters (around line 1275) and change:
```python
{"name": "apikey", "value": os.environ.get('EVOLUTION_API_KEY', '089311B617B8-48CF-8BD6-29759A57FDBF')},
```
to:
```python
{"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
```

- [ ] **Step 5: Update Dead Letter Admin node to use environment variable**

In `build_workflow.py`, find the Dead Letter Admin node parameters (around line 1291) and change:
```python
{"name": "apikey", "value": os.environ.get('EVOLUTION_API_KEY', '089311B617B8-48CF-8BD6-29759A57FDBF')},
```
to:
```python
{"name": "apikey", "value": "={{ $env.EVOLUTION_API_KEY }}"},
```

- [ ] **Step 6: Commit changes**

```bash
git add build_workflow.py
git commit -m "sec: replace hardcoded Evolution API keys with environment variables"
```

### Task 2: Implement Webhook Authentication

**Covers:** S2
<!-- spec section anchors this task implements; every task that produces
     spec-required behavior must list at least one. Omit only for pure
     scaffolding tasks (e.g. project setup) that map to no spec section. -->

**Files:**
- Modify: `build_workflow.py:233-311`
- Modify: `workflow.json`

**Interfaces:**
- Consumes: Webhook requests with authentication tokens
- Produces: Authenticated webhook processing pipeline

- [ ] **Step 1: Update Store Context node to handle webhook authentication**

In `build_workflow.py`, find the store_context_js variable (around line 233) and ensure it includes webhook authentication validation. The Webhook Auth Check node already handles this, but we should verify the implementation:

```python
store_context_js = (
    "const staticData = $getWorkflowStaticData('global');\n"
    "const expectedSecret = staticData._webhookSecret || process.env.N8N_WEBHOOK_SECRET || '';\n\n"
    "if (!expectedSecret) {\n"
    "    const input = $input.item.json;\n"
    "    return [{ json: input }];\n"
    "}\n\n"
    "const input = $input.first().json;\n"
    "const queryToken = input?.query?.token || '';\n"
    "const headerToken = input?.headers?.['x-webhook-secret'] || '';\n"
    "const bodySecret = input?.body?.secret || '';\n"
    "const providedSecret = queryToken || headerToken || bodySecret;\n"
    "if (providedSecret !== expectedSecret) {\n"
    "    throw new Error('Webhook authentication failed: Invalid secret');\n"
    "}\n\n"
    "return [{ json: input }];\n"
)
```

- [ ] **Step 2: Ensure Webhook node uses n8n's built-in query authentication**

In `build_workflow.py`, when defining the Webhook1 node, add authentication parameters:

```python
{
    "parameters": {
        "httpMethod": "POST", 
        "path": "evolution-webhook", 
        "responseMode": "onReceived", 
        "options": {},
        "authentication": "query",
        "queryAuth": "={{ $credentials.WebhookAuth.token }}"
    },
    "id": get_node_id("Webhook1"), 
    "name": "Webhook1",
    "type": "n8n-nodes-base.webhook", 
    "typeVersion": 1.1, 
    "position": [240, 640],
    "webhookId": "d4e5f6a7-b8c9-4d0e-8f1a-2b3c4d5e6f7a"
}
```

- [ ] **Step 3: Commit changes**

```bash
git add build_workflow.py
git commit -m "sec: implement webhook authentication with n8n credentials"
```

### Task 3: Enable SSL Verification in All Scripts

**Covers:** S3
<!-- spec section anchors this task implements; every task that produces
     spec-required behavior must list at least one. Omit only for pure
     scaffolding tasks (e.g. project setup) that map to no spec section. -->

**Files:**
- Modify: `tools/wf_test_webhook.py:21`
- Modify: `tools/live_customer_scenario_test.py:21`
- Modify: `upload_to_n8n.py:13`
- Modify: `tools/wf_deploy.py:19`

**Interfaces:**
- Consumes: Network requests to external services
- Produces: Secure network requests with SSL verification

- [ ] **Step 1: Enable SSL verification in wf_test_webhook.py**

In `tools/wf_test_webhook.py`, find line 21 where context is defined and change:
```python
context = ssl._create_unverified_context()
```
to:
```python
context = None  # Uses default SSL context with verification
```

- [ ] **Step 2: Enable SSL verification in live_customer_scenario_test.py**

In `tools/live_customer_scenario_test.py`, find line 52 where context is defined and change:
```python
# Use default SSL context (verification enabled)
context = ssl._create_unverified_context()
```
to:
```python
# Use default SSL context (verification enabled)
context = None  # Uses default SSL context with verification
```

- [ ] **Step 3: Confirm SSL verification is enabled in upload_to_n8n.py**

In `upload_to_n8n.py`, verify line 13 has:
```python
# Use default SSL context (verification enabled)
context = None  # Uses default SSL context with verification
```

- [ ] **Step 4: Confirm SSL verification is enabled in wf_deploy.py**

In `tools/wf_deploy.py`, verify line 19 has:
```python
# Use default SSL context (verification enabled)
context = None  # Uses default SSL context with verification
```

- [ ] **Step 5: Commit changes**

```bash
git add tools/wf_test_webhook.py tools/live_customer_scenario_test.py upload_to_n8n.py tools/wf_deploy.py
git commit -m "sec: enable SSL verification in all network requests"
```

### Task 4: Update Environment Variable Usage

**Covers:** S4
<!-- spec section anchors this task implements; every task that produces
     spec-required behavior must list at least one. Omit only for pure
     scaffolding tasks (e.g. project setup) that map to no spec section. -->

**Files:**
- Modify: `build_workflow.py:1423-1459`
- Modify: `tools/wf_test_webhook.py:20`
- Modify: `tools/live_customer_scenario_test.py:13`

**Interfaces:**
- Consumes: Environment variables from the system
- Produces: Secure configuration using environment variables

- [ ] **Step 1: Update webhook URL construction in test scripts**

In `tools/wf_test_webhook.py`, find line 20 and change:
```python
WEBHOOK_URL = f"https://n8n.filtreoto.online/webhook/evolution-webhook?token={os.environ.get('WEBHOOK_TOKEN', DEFAULT_TOKEN)}"
```
to:
```python
WEBHOOK_URL = f"https://n8n.filtreoto.online/webhook/evolution-webhook?token={{ $env.WEBHOOK_TOKEN }}"
```

- [ ] **Step 2: Update webhook URL construction in live customer scenario test**

In `tools/live_customer_scenario_test.py`, find line 13 and change:
```python
WEBHOOK_URL = f"https://n8n.filtreoto.online/webhook/evolution-webhook?token={os.environ.get('WEBHOOK_TOKEN', DEFAULT_TOKEN)}"
```
to:
```python
WEBHOOK_URL = f"https://n8n.filtreoto.online/webhook/evolution-webhook?token={{ $env.WEBHOOK_TOKEN }}"
```

- [ ] **Step 3: Update build script to use environment variables**

In `build_workflow.py`, ensure the build process uses environment variables. Find the staticData section (around line 1423) and update:
```python
wf["staticData"] = {
    "node:Schedule Trigger": {"recurrenceRules": []},
    "global": {
        "_batches": {},
        "_webhookSecret": os.environ.get('N8N_WEBHOOK_SECRET', 'F9a2Km7Qx8LpN3vB7jR5wY2tH6dK4mS')
    }
}
```
to:
```python
wf["staticData"] = {
    "node:Schedule Trigger": {"recurrenceRules": []},
    "global": {
        "_batches": {},
        "_webhookSecret": "={{ $env.N8N_WEBHOOK_SECRET }}"
    }
}
```

- [ ] **Step 4: Commit changes**

```bash
git add build_workflow.py tools/wf_test_webhook.py tools/live_customer_scenario_test.py
git commit -m "sec: update environment variable usage for secure configuration"
```

### Task 5: Verify Security Implementation

**Covers:** S5
<!-- spec section anchors this task implements; every task that produces
     spec-required behavior must list at least one. Omit only for pure
     scaffolding tasks (e.g. project setup) that map to no spec section. -->

**Files:**
- Test: `tools/wf_security.py`
- Test: `tools/wf_test_webhook.py`

**Interfaces:**
- Consumes: Security scanning tools and test scripts
- Produces: Verification that security measures are properly implemented

- [ ] **Step 1: Run security scan to verify no hardcoded secrets remain**

Run: `python tools/wf_security.py`
Expected: No hardcoded API keys, secrets, or tokens found

- [ ] **Step 2: Run webhook test to verify authentication works**

Run: `python tools/wf_test_webhook.py`
Expected: Webhook requests are properly authenticated and processed

- [ ] **Step 3: Verify SSL verification is enabled in all scripts**

Check that no files contain `ssl._create_unverified_context()`:
Run: `grep -r "ssl._create_unverified_context" .`
Expected: No matches found

- [ ] **Step 4: Commit verification results**

```bash
git add tools/wf_security.py
git commit -m "sec: verify security implementation and remove hardcoded secrets"
```