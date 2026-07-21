#!/usr/bin/env python3
"""Read-only drift probe intended for a 10-minute host/Coolify cron."""
import json
import os
import sys
import urllib.error
import urllib.request


def request_json(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main():
    base = os.environ.get("N8N_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY", "")
    workflow_id = os.environ.get("N8N_WORKFLOW_ID", "")
    expected_name = os.environ.get("N8N_EXPECTED_WORKFLOW_NAME", "WhatsApp AI - v13 PostgreSQL Outbox")
    if not api_key:
        raise SystemExit("N8N_API_KEY is required")
    if not workflow_id:
        raise SystemExit("N8N_WORKFLOW_ID is required")
    findings = []
    try:
        status, workflow = request_json(
            f"{base}/api/v1/workflows/{workflow_id}", {"X-N8N-API-KEY": api_key}
        )
        if status != 200:
            findings.append({"check": "workflow", "error": f"HTTP {status}"})
        if not workflow.get("active"):
            findings.append({"check": "workflow_active", "actual": False})
        if workflow.get("name") != expected_name:
            findings.append({"check": "workflow_name", "actual": workflow.get("name"), "expected": expected_name})
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        findings.append({"check": "n8n_api", "error": str(error)})
    print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
