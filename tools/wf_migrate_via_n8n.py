#!/usr/bin/env python3
"""Apply SQL through a short-lived n8n workflow using the existing Postgres credential."""
import json
import os
import secrets
import sys
import urllib.request
from pathlib import Path
import uuid
from urllib.error import HTTPError

BASE = os.environ.get("N8N_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("N8N_API_KEY")
ROOT = Path(__file__).resolve().parents[1]


def split_sql(sql):
    """Split SQL while preserving PostgreSQL dollar-quoted function bodies."""
    statements, current, tag, quote = [], [], None, None
    i = 0
    while i < len(sql):
        if tag:
            if sql.startswith(tag, i):
                current.append(tag); i += len(tag); tag = None; continue
            current.append(sql[i]); i += 1; continue
        if quote:
            current.append(sql[i])
            if sql[i] == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    current.append(sql[i + 1]); i += 2; continue
                quote = None
            i += 1; continue
        if sql[i] in "'\"":
            quote = sql[i]; current.append(sql[i]); i += 1; continue
        if sql[i] == '$':
            end = sql.find('$', i + 1)
            if end != -1 and all(c.isalnum() or c == '_' for c in sql[i + 1:end]):
                tag = sql[i:end + 1]; current.append(tag); i = end + 1; continue
        if sql[i] == ';':
            statement = ''.join(current).strip()
            if statement and statement.upper() not in {'BEGIN', 'COMMIT'}:
                statements.append(statement)
            current = []; i += 1; continue
        current.append(sql[i]); i += 1
    statement = ''.join(current).strip()
    if statement and statement.upper() not in {'BEGIN', 'COMMIT'}:
        statements.append(statement)
    return statements


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
    statements = split_sql(sql)
    credential = next((item for item in api("/api/v1/credentials").get("data", [])
                       if item.get("name") == "WhatsApp State PostgreSQL"), None)
    if not credential:
        raise SystemExit("WhatsApp State PostgreSQL credential not found")
    webhook_path = "maintenance-migrate-" + secrets.token_hex(16)
    webhook_id = secrets.token_hex(16)
    nodes = [{"parameters": {"httpMethod": "POST", "path": webhook_path, "responseMode": "lastNode", "options": {}},
              "id": webhook_id, "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
              "position": [200, 300], "webhookId": webhook_id}]
    connections = {}
    previous = "Webhook"
    for index, statement in enumerate(statements, 1):
        name = f"Apply {index:03d}"
        node = {"parameters": {"operation": "executeQuery", "query": statement, "options": {}},
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"migration/{webhook_id}/{index}")),
                "name": name, "type": "n8n-nodes-base.postgres", "typeVersion": 2.6,
                "position": [500 + (index % 4) * 260, 300 + (index // 4) * 180],
                "alwaysOutputData": True,
                "credentials": {"postgres": {"id": credential["id"], "name": credential["name"]}}}
        nodes.append(node)
        connections[previous] = {"main": [[{"node": name, "type": "main", "index": 0}]]}
        previous = name
    workflow = {
        "name": "TEMP WhatsApp DB Migration",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1", "timezone": "Europe/Istanbul"},
    }
    created = api("/api/v1/workflows", "POST", workflow)
    workflow_id = created["id"]
    try:
        api(f"/api/v1/workflows/{workflow_id}/activate", "POST", {})
        request = urllib.request.Request(f"{BASE}/webhook/{webhook_path}", data=b"{}", method="POST")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = response.read().decode("utf-8")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"migration webhook HTTP {error.code}: {detail[:2000]}") from error
        print(f"Applied: {', '.join(path.name for path in files)} ({len(statements)} SQL statements)")
        print(result[:500])
    finally:
        try:
            api(f"/api/v1/workflows/{workflow_id}/deactivate", "POST", {})
        finally:
            api(f"/api/v1/workflows/{workflow_id}", "DELETE")


if __name__ == "__main__":
    main()
