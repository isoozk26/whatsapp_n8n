#!/usr/bin/env python3
"""Offline contracts for the PostgreSQL-backed workflow."""
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = json.loads((ROOT / "workflow.json").read_text(encoding="utf-8"))
SQL = (ROOT / "db" / "migrations" / "001_whatsapp_state.sql").read_text(encoding="utf-8")


def node(name):
    return next(item for item in WORKFLOW["nodes"] if item["name"] == name)


def targets(source, output=0):
    ports = WORKFLOW["connections"].get(source, {}).get("main", [])
    return [] if output >= len(ports) else [item["node"] for item in ports[output]]


def main():
    names = [item["name"] for item in WORKFLOW["nodes"]]
    assert len(names) == len(set(names))
    for removed in ("Should Process?", "Finalize Batch", "Batch Collector", "Stale Batch Check", "Simple Memory"):
        assert removed not in names, f"legacy node remains: {removed}"

    webhook = node("Webhook1")
    assert webhook["parameters"]["responseMode"] == "responseNode"
    assert targets("Webhook1") == ["Normalize Payload"]
    assert targets("Ingest Message") == ["Webhook Auth"]
    assert targets("Webhook Auth", 0) == ["Respond Accepted"]
    assert targets("Webhook Auth", 1) == ["Respond Unauthorized"]
    assert node("Respond Unauthorized")["parameters"]["options"]["responseCode"] == 401

    normalize = node("Normalize Payload")["parameters"]["jsCode"]
    assert "body?.body?.data || root.body?.data" in normalize
    assert "isGroup" in normalize and "isBroadcast" in normalize
    assert targets("Valid Event?", 0) == ["Ingest Message"]

    assert targets("AI Agent", 0) == ["Parse AI Output"]
    assert targets("AI Agent", 1) == ["Record AI Failure"]
    assert targets("Parse AI Output") == ["AI Output Valid?"]
    assert targets("AI Output Valid?", 0) == ["Complete AI Batch"]
    assert targets("AI Output Valid?", 1) == ["Record AI Failure"]
    parse = node("Parse AI Output")["parameters"]["jsCode"]
    for forbidden in ("$getWorkflowStaticData", "_deliveryLedger", "_batches", "_adminNotifications"):
        assert forbidden not in parse

    assert targets("Send Delivery", 0) == ["Tag Delivery Success"]
    assert targets("Send Delivery", 1) == ["Tag Delivery Error"]
    assert targets("Tag Delivery Success") == ["Record Delivery Result"]
    assert targets("Tag Delivery Error") == ["Record Delivery Result"]
    send = node("Send Delivery")
    assert send["parameters"]["authentication"] == "predefinedCredentialType"
    assert send["credentials"]["httpHeaderAuth"]["name"] == "Evolution API"

    for pg_name in ("Ingest Message", "Claim Ready Batches", "Complete AI Batch", "Record AI Failure", "Claim Deliveries", "Record Delivery Result", "Cleanup State"):
        pg = node(pg_name)
        assert pg["type"] == "n8n-nodes-base.postgres"
        assert pg["credentials"]["postgres"]["name"] == "WhatsApp State PostgreSQL"

    for table in ("settings", "batches", "messages", "manual_modes", "admin_notifications", "unclear_counts", "deliveries", "system_events"):
        assert f"whatsapp_ai.{table}" in SQL
    for function in ("ingest_message", "claim_ready_batches", "complete_ai_batch", "record_ai_failure", "claim_deliveries", "record_delivery_result", "cleanup_expired_state"):
        assert f"FUNCTION whatsapp_ai.{function}" in SQL
    assert "FOR UPDATE SKIP LOCKED" in SQL
    assert SQL.count("processing_token = p_batch_token") >= 4
    assert "UNIQUE (batch_token, channel)" in SQL
    assert "CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'dead'))" in SQL
    assert "assignee_name text" in SQL
    assert "AT TIME ZONE 'Europe/Istanbul'" in SQL
    assert "interval '120 seconds'" in SQL
    assert "interval '10 seconds'" not in SQL

    source = (ROOT / "build_workflow.py").read_text(encoding="utf-8")
    assert not re.search(r"apikey.{0,30}[A-F0-9]{20,}", source, flags=re.I | re.S)
    assert "$env." not in source
    assert "N8N_POSTGRES_CREDENTIAL_ID" in source
    print("[PASS] PostgreSQL state, auth, token and outbox contracts")


if __name__ == "__main__":
    main()
