#!/usr/bin/env python3
"""Build the n8n operational schedules for WhatsApp AI."""
import json
import os
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "ops_workflow.json"
POSTGRES_ID = os.environ.get("N8N_POSTGRES_CREDENTIAL_ID", "whatsapp-state-postgres")
POSTGRES_NAME = os.environ.get("N8N_POSTGRES_CREDENTIAL_NAME", "WhatsApp State PostgreSQL")


def node_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://filtreoto.online/n8n/ops/{name}"))


def trigger(name, rule, position):
    return {"parameters": {"rule": {"interval": [rule]}}, "id": node_id(name), "name": name,
            "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": position}


def postgres(name, query, position):
    return {"parameters": {"operation": "executeQuery", "query": query, "options": {}},
            "id": node_id(name), "name": name, "type": "n8n-nodes-base.postgres", "typeVersion": 2.6,
            "position": position, "credentials": {"postgres": {"id": POSTGRES_ID, "name": POSTGRES_NAME}}}


jobs = [
    ("Delivery Recovery Every Minute", {"field": "minutes", "minutesInterval": 1},
     "Recover Stale Deliveries", "SELECT whatsapp_ai.recover_stale_deliveries() AS result", 40),
    ("Queue Monitor Every Minute", {"field": "minutes", "minutesInterval": 1},
     "Run Queue Monitor", "SELECT whatsapp_ai.run_queue_monitor() AS result", 120),
    ("Daily Report 0830", {"field": "cronExpression", "expression": "30 8 * * *"},
     "Run Daily Report", "SELECT whatsapp_ai.run_daily_report() AS result", 320),
    ("Retention 0410", {"field": "cronExpression", "expression": "10 4 * * *"},
     "Run Retention", "SELECT whatsapp_ai.run_retention() AS result", 520),
    ("Rotation Reminder 0900", {"field": "cronExpression", "expression": "0 9 * * *"},
     "Run Rotation Reminder", "SELECT whatsapp_ai.run_rotation_reminder() AS result", 720),
]
nodes = []
connections = {}
for trigger_name, rule, job_name, query, y in jobs:
    nodes.extend([trigger(trigger_name, rule, [120, y]), postgres(job_name, query, [400, y])])
    connections[trigger_name] = {"main": [[{"node": job_name, "type": "main", "index": 0}]]}

workflow = {
    "name": "WhatsApp AI - Operations Schedules", "nodes": nodes, "connections": connections,
    "settings": {"executionOrder": "v1", "timezone": "Europe/Istanbul",
                 "saveDataErrorExecution": "all", "saveDataSuccessExecution": "none"},
    "staticData": {}, "pinData": {}, "active": False,
}

if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT.name}: {len(nodes)} nodes")
