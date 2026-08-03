#!/usr/bin/env python3
"""Reconcile the production n8n webhook owner and Evolution webhook config.

Dry-run is the default. Pass --apply only from an operator shell with fresh
credentials in environment variables. Secret values are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


N8N_BASE = os.environ.get("N8N_BASE_URL", "").rstrip("/")
N8N_KEY = os.environ.get("N8N_API_KEY", "")
TARGET_ID = os.environ.get("N8N_WORKFLOW_ID", "")
TARGET_NAME = os.environ.get(
    "N8N_EXPECTED_MAIN_WORKFLOW_NAME", "WhatsApp AI - v13 PostgreSQL Outbox"
)
EVOLUTION_BASE = os.environ.get("EVOLUTION_BASE_URL", "https://evo.filtreoto.online").rstrip("/")
EVOLUTION_KEY = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "otofiltre")
WEBHOOK_SECRET = os.environ.get("N8N_WEBHOOK_SECRET", "")
WEBHOOK_PATH = "evolution-webhook"


def require_common(apply: bool) -> None:
    missing = []
    if not N8N_BASE:
        missing.append("N8N_BASE_URL")
    if not N8N_KEY:
        missing.append("N8N_API_KEY")
    if not TARGET_ID:
        missing.append("N8N_WORKFLOW_ID")
    if apply and not EVOLUTION_KEY:
        missing.append("EVOLUTION_API_KEY")
    if apply and not WEBHOOK_SECRET:
        missing.append("N8N_WEBHOOK_SECRET")
    if missing:
        raise SystemExit("Missing required environment: " + ", ".join(missing))


def request_json(url: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8")
            return response.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {error.code} from {url}: {detail}") from error


def n8n(path: str, method: str = "GET", payload: dict | None = None):
    return request_json(
        N8N_BASE + "/api/v1" + path,
        method,
        payload,
        {"X-N8N-API-KEY": N8N_KEY, "Accept": "application/json"},
    )[1]


def webhook_nodes(workflow: dict) -> list[dict]:
    result = []
    for node in workflow.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.webhook":
            continue
        parameters = node.get("parameters") or {}
        result.append(
            {
                "name": node.get("name"),
                "method": parameters.get("httpMethod"),
                "path": parameters.get("path"),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="mutate n8n/Evolution runtime")
    args = parser.parse_args()
    require_common(args.apply)

    workflows = n8n("/workflows?limit=100").get("data", [])
    owners = []
    target = None
    for workflow in workflows:
        paths = webhook_nodes(workflow)
        if any(item["method"] == "POST" and item["path"] == WEBHOOK_PATH for item in paths):
            owners.append(workflow)
        if workflow.get("id") == TARGET_ID:
            target = workflow

    if target is None:
        raise SystemExit("Target workflow was not found by N8N_WORKFLOW_ID")
    if target.get("name") != TARGET_NAME:
        raise SystemExit("Target workflow name does not match expected main workflow")

    print(f"Target workflow: {target.get('id')} | active={target.get('active')} | name={target.get('name')}")
    print(f"Production webhook path owners: {len(owners)}")
    for workflow in owners:
        print(f"  - {workflow.get('id')} | active={workflow.get('active')} | name={workflow.get('name')}")

    if not args.apply:
        print("DRY RUN: no runtime changes made")
        return 0

    for workflow in owners:
        if workflow.get("id") != TARGET_ID and workflow.get("active") is True:
            n8n(f"/workflows/{workflow['id']}/deactivate", "POST", {})
            print(f"Deactivated duplicate path owner: {workflow.get('id')}")
    if target.get("active") is not True:
        n8n(f"/workflows/{TARGET_ID}/activate", "POST", {})
        print("Activated target workflow")

    payload = {
        "webhook": {
            "enabled": True,
            "url": f"{N8N_BASE}/webhook/{WEBHOOK_PATH}?token={WEBHOOK_SECRET}",
            "webhookByEvents": False,
            "webhookBase64": False,
            "events": ["MESSAGES_UPSERT"],
        }
    }
    request_json(
        f"{EVOLUTION_BASE}/webhook/set/{EVOLUTION_INSTANCE}",
        "POST",
        payload,
        {"apikey": EVOLUTION_KEY, "Accept": "application/json"},
    )
    print("Evolution webhook updated: production path, MESSAGES_UPSERT, webhookByEvents=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
