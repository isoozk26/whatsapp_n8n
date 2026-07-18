#!/usr/bin/env python3
"""Apply SQL through a short-lived n8n workflow using the existing Postgres credential."""
import json
import os
import secrets
import sys
import urllib.request
from pathlib import Path

BASE = os.environ.get("N8N_BASE_URL", "https://n8n.filtreoto.online").rstrip("/")
API_KEY = os.environ.get("N8N_API_KEY")
ROOT = Path(__file__).resolve().parents[1]


def api(path, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("X-N8N-API-KEY", API_KEY)
    request.add_header("accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        return json.loads(body.decode("utf-8")) if body else {}


def main():
    if not API_KEY:
        raise SystemExit("N8N_API_KEY is required")
    files = [Path(arg) for arg in sys.argv[1:]] or sorted((ROOT / "db" / "migrations").glob("*.sql"))
    sql = "\n".join(path.read_text(encoding="utf-8") for path in files)
    credential = next((item for item in api("/api/v1/credentials").get("data", [])
                       if item.get("name") == "WhatsApp State PostgreSQL"), None)
    if not credential:
        raise SystemExit("WhatsApp State PostgreSQL credential not found")
    webhook_path = "maintenance-migrate-" + secrets.token_hex(16)
    webhook_id = secrets.token_hex(16)
    workflow = {
        "name": "TEMP WhatsApp DB Migration",
        "nodes": [
            {"parameters": {"httpMethod": "POST", "path": webhook_path, "responseMode": "lastNode", "options": {}},
             "id": webhook_id, "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
             "position": [200, 300], "webhookId": webhook_id},
            {"parameters": {"operation": "executeQuery", "query": sql, "options": {}},
             "id": secrets.token_hex(16), "name": "Apply Migration", "type": "n8n-nodes-base.postgres",
             "typeVersion": 2.6, "position": [500, 300],
             "credentials": {"postgres": {"id": credential["id"], "name": credential["name"]}}},
        ],
        "connections": {"Webhook": {"main": [[{"node": "Apply Migration", "type": "main", "index": 0}]]}},
        "settings": {"executionOrder": "v1", "timezone": "Europe/Istanbul"},
    }
    created = api("/api/v1/workflows", "POST", workflow)
    workflow_id = created["id"]
    try:
        api(f"/api/v1/workflows/{workflow_id}/activate", "POST", {})
        request = urllib.request.Request(f"{BASE}/webhook/{webhook_path}", data=b"{}", method="POST")
        request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=180) as response:
            result = response.read().decode("utf-8")
        print(f"Applied: {', '.join(path.name for path in files)}")
        print(result[:500])
    finally:
        try:
            api(f"/api/v1/workflows/{workflow_id}/deactivate", "POST", {})
        finally:
            api(f"/api/v1/workflows/{workflow_id}", "DELETE")


if __name__ == "__main__":
    main()
