#!/usr/bin/env python3
"""Read-only n8n health/workflow/execution check.

All live identifiers and credentials must come from the operator environment.
This script intentionally never prints API keys or webhook secrets.
"""

import json
import os
import urllib.error
import urllib.request


N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("N8N_API_KEY", "")
WORKFLOW_ID = os.environ.get("N8N_WORKFLOW_ID", "")
if not N8N_BASE_URL:
    raise SystemExit("N8N_BASE_URL is required")
if not API_KEY:
    raise SystemExit("N8N_API_KEY is required")
if not WORKFLOW_ID:
    raise SystemExit("N8N_WORKFLOW_ID is required")

BASE = N8N_BASE_URL + "/api/v1"
HEADERS = {"X-N8N-API-KEY": API_KEY, "Accept": "application/json"}


def api_get(url):
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        try:
            body = json.loads(body)
        except ValueError:
            pass
        return error.code, body
    except Exception as error:  # pragma: no cover - operator connectivity path
        return None, str(error)


print("=" * 60)
print("N8N HEALTH CHECK")
print("=" * 60)
code, data = api_get(N8N_BASE_URL + "/healthz")
print("Status Code:", code)
print("Healthy:", code == 200 and isinstance(data, dict) and data.get("status") == "ok")

print()
print("=" * 60)
print("WORKFLOW STATUS")
print("=" * 60)
code, data = api_get(BASE + "/workflows/" + WORKFLOW_ID)
print("Status Code:", code)
if code == 200 and isinstance(data, dict):
    workflow = data.get("data", data)
    print("Name:", workflow.get("name"))
    print("Active:", workflow.get("active"))
    print("ID:", workflow.get("id"))
    print("Version:", workflow.get("versionId", workflow.get("version", "N/A")))
    print("UpdatedAt:", workflow.get("updatedAt", "N/A"))
else:
    print("Response:", data)

print()
print("=" * 60)
print("LAST 5 EXECUTIONS")
print("=" * 60)
code, data = api_get(BASE + "/executions?workflowId=" + WORKFLOW_ID + "&limit=5")
print("Status Code:", code)
if code == 200 and isinstance(data, dict):
    results = data.get("results", data.get("data", []))
    for execution in results if isinstance(results, list) else []:
        print(
            "ID: %s | Status: %s | Mode: %s | Started: %s | Stopped: %s"
            % (
                execution.get("id"),
                execution.get("status"),
                execution.get("mode"),
                execution.get("startedAt", "N/A"),
                execution.get("stoppedAt", "N/A"),
            )
        )
else:
    print("Response:", data)
