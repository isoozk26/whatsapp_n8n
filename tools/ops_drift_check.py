#!/usr/bin/env python3
"""Read-only n8n drift probe for the primary and operations workflows."""
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_MAIN_NAME = "WhatsApp AI - v13 PostgreSQL Outbox"
DEFAULT_OPS_NAME = "WhatsApp AI - Operations Schedules"


def request_json(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def workflow_config(prefix, default_name):
    return {
        "key": prefix.lower(),
        "id": os.environ.get(f"N8N_{prefix}_WORKFLOW_ID", ""),
        "expected_name": os.environ.get(f"N8N_EXPECTED_{prefix}_WORKFLOW_NAME", default_name),
        "expected_version": os.environ.get(f"N8N_EXPECTED_{prefix}_WORKFLOW_VERSION_ID", ""),
    }


def probe_workflow(base, headers, config):
    findings = []
    workflow_id = config["id"]
    label = config["key"]
    try:
        status, workflow = request_json(f"{base}/api/v1/workflows/{workflow_id}", headers)
        if status != 200:
            findings.append({"check": f"{label}_workflow", "error": f"HTTP {status}"})
            return findings
        if not workflow.get("active"):
            findings.append({"check": f"{label}_active", "actual": False})
        if workflow.get("name") != config["expected_name"]:
            findings.append({"check": f"{label}_name", "actual": workflow.get("name"), "expected": config["expected_name"]})
        version_id = workflow.get("versionId")
        if not version_id:
            findings.append({"check": f"{label}_version", "error": "versionId missing"})
        elif config["expected_version"] and version_id != config["expected_version"]:
            findings.append({"check": f"{label}_version", "actual": version_id, "expected": config["expected_version"]})

        status, executions = request_json(
            f"{base}/api/v1/executions?workflowId={workflow_id}&limit=1", headers
        )
        latest = executions.get("data", []) if status == 200 else []
        if status != 200:
            findings.append({"check": f"{label}_last_execution", "error": f"HTTP {status}"})
        elif not latest:
            findings.append({"check": f"{label}_last_execution", "error": "no execution found"})
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        findings.append({"check": f"{label}_n8n_api", "error": str(error)})
    return findings


def main():
    base = os.environ.get("N8N_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY", "")
    configs = [
        workflow_config("MAIN", DEFAULT_MAIN_NAME),
        workflow_config("OPS", DEFAULT_OPS_NAME),
    ]
    if not base:
        raise SystemExit("N8N_BASE_URL is required")
    if not api_key:
        raise SystemExit("N8N_API_KEY is required")
    missing = [f"N8N_{item['key'].upper()}_WORKFLOW_ID" for item in configs if not item["id"]]
    if missing:
        raise SystemExit(f"{', '.join(missing)} is required")

    headers = {"X-N8N-API-KEY": api_key}
    findings = []
    for config in configs:
        findings.extend(probe_workflow(base, headers, config))
    print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
