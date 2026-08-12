#!/usr/bin/env python3
"""Offline contracts for the PostgreSQL-backed workflow."""
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = json.loads((ROOT / "workflow.json").read_text(encoding="utf-8"))
SQL = "\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT / "db" / "migrations").glob("*.sql")))
FINAL_SQL = (ROOT / "db" / "migrations" / "053_finalize_ai_retry_and_priority.sql").read_text(encoding="utf-8")
SCHEMA_RECONCILE_SQL = (ROOT / "db" / "migrations" / "054_reconcile_delivery_priority_schema.sql").read_text(encoding="utf-8")
STALE_MONITOR_SQL = (ROOT / "db" / "migrations" / "055_stale_batch_monitor.sql").read_text(encoding="utf-8")
CHAT_MEMORY_SQL = (ROOT / "db" / "migrations" / "056_chat_memory.sql").read_text(encoding="utf-8")
ADMIN_FILTER_SQL = (ROOT / "db" / "migrations" / "057_admin_number_filter.sql").read_text(encoding="utf-8")


def node(name):
    return next(item for item in WORKFLOW["nodes"] if item["name"] == name)


def targets(source, output=0):
    ports = WORKFLOW["connections"].get(source, {}).get("main", [])
    return [] if output >= len(ports) else [item["node"] for item in ports[output]]


def main():
    names = [item["name"] for item in WORKFLOW["nodes"]]
    assert len(names) == len(set(names))
    for removed in ("Should Process?", "Finalize Batch", "Batch Collector", "Stale Batch Check", "Simple Memory",
                     "Vehicle Catalog?", "Prepare Catalog Lookup", "Resolve Vehicle Catalog", "Apply Catalog Decision"):
        assert removed not in names, f"legacy node remains: {removed}"

    webhook = node("Webhook1")
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == "evolution-webhook", "webhook path must not contain a query token"
    assert webhook["parameters"]["responseMode"] == "responseNode"
    assert targets("Webhook1") == ["Normalize Payload"]
    assert targets("Normalize Payload") == ["Validate Webhook Secret"]
    assert targets("Validate Webhook Secret") == ["Webhook Auth"]
    assert targets("Webhook Auth", 0) == ["Load Admin Filter Settings"]
    assert targets("Webhook Auth", 1) == ["Respond Unauthorized"]
    assert targets("Load Admin Filter Settings") == ["Apply Admin Number Filter"]
    assert targets("Apply Admin Number Filter") == ["Is Admin Number?"]
    admin_filter_query = node("Load Admin Filter Settings")["parameters"]["query"]
    admin_filter_code = node("Apply Admin Number Filter")["parameters"]["jsCode"]
    assert 'key = \'admin_phone_a\'' in admin_filter_query
    assert 'key = \'admin_phone_b\'' in admin_filter_query
    assert "admin_number_prefixes" not in admin_filter_query
    assert "configuredAdminNumbers.includes(senderNumber)" in admin_filter_code
    assert "startsWith(prefix)" not in admin_filter_code
    assert targets("Is Admin Number?", 0) == ["Respond Admin Filtered"]
    assert targets("Is Admin Number?", 1) == ["Valid Event?"]
    assert node("Respond Admin Filtered")["parameters"]["options"]["responseCode"] == 202
    assert node("Respond Unauthorized")["parameters"]["options"]["responseCode"] == 401

    normalize = node("Normalize Payload")["parameters"]["jsCode"]
    assert "root.body?.body?.data" in normalize
    assert "root.data" in normalize
    assert "isGroup" in normalize and "isBroadcast" in normalize
    assert targets("Valid Event?", 0) == ["Load Holiday Settings"]
    assert targets("Valid Event?", 1) == ["Respond Ignored"]
    assert targets("Load Holiday Settings") == ["Check Business Hours"]
    assert targets("Check Business Hours") == ["Rate Limit Exceeded?"]
    assert "$('Check Business Hours').item.json.offHours === true" in node("Is Off Hours?")["parameters"]["conditions"]["conditions"][0]["leftValue"]
    assert targets("Ingest Message", 0) == ["Respond Accepted", "Is Off Hours?"]
    assert targets("Respond Accepted") == []
    assert targets("Is Off Hours?", 0) == ["Wait OOH 120 Seconds"]
    assert targets("Is Off Hours?", 1) == []
    assert targets("Wait OOH 120 Seconds") == ["Claim OOH Notification"]
    assert targets("Claim OOH Notification") == ["OOH Claim Won?"]
    assert targets("OOH Claim Won?", 0) == ["Build OOH Messages"]
    assert targets("OOH Claim Won?", 1) == []
    assert targets("Build OOH Messages") == ["Send OOH to Customer"]
    assert targets("Send OOH to Customer", 0) == ["Enqueue Manager OOH Alert"]
    assert targets("Send OOH to Customer", 1) == ["Enqueue Manager OOH Alert"]
    assert targets("Enqueue Manager OOH Alert") == ["Log OOH Event"]
    assert targets("Log OOH Event") == []
    assert targets("Rate Limit Exceeded?", 0) == ["Respond Rate Limited"]
    assert targets("Rate Limit Exceeded?", 1) == ["Ingest Message"]
    assert node("Respond Rate Limited")["parameters"]["options"]["responseCode"] == 202
    assert "rateLimitExceeded" in normalize
    check_hours = node("Check Business Hours")["parameters"]["jsCode"]
    assert "Sat: [9, 18]" in check_hours
    assert "offHours" in check_hours
    assert "nextAiAttemptAt" in check_hours
    wait = node("Wait OOH 120 Seconds")
    assert wait["type"] == "n8n-nodes-base.wait"
    assert wait["parameters"]["amount"] == 2
    assert wait["parameters"]["unit"] == "minutes"
    claim_sql = node("Claim OOH Notification")["parameters"]["query"].lower()
    assert "first_message_at <= clock_timestamp() - interval '120 seconds'" in claim_sql
    assert "for update skip locked" in claim_sql
    assert "customer_sent = false" in claim_sql

    store = node("Store Context")["parameters"]["jsCode"]
    assert ".normalize('NFKC')" in store
    assert ".replace(/<\\|im_start\\|>/gi, '')" in store
    assert "chatMemoryText" in store
    assert "chat_memory" in node("Claim Ready Batches")["parameters"]["query"]
    admin_filter = node("Apply Admin Number Filter")["parameters"]["jsCode"]
    assert "authorizedCommand" in admin_filter
    assert "configuredAdminNumbers.includes(senderNumber)" in admin_filter
    assert "startsWith" not in admin_filter

    assert targets("AI Agent", 0) == ["Parse AI Output"]
    assert targets("AI Agent", 1) == ["Prepare AI Failure"]
    assert targets("Parse AI Output") == ["AI Output Valid?"]
    assert targets("AI Output Valid?", 0) == ["Complete AI Batch"]
    assert targets("AI Output Valid?", 1) == ["Prepare AI Failure"]
    assert targets("Complete AI Batch") == ["AI Batch Completed?"]
    assert targets("AI Batch Completed?", 1) == ["Prepare Batch Completion Failure"]
    assert targets("AI Batch Completed?", 0) == ["Persist Chat Memory"]
    assert targets("Persist Chat Memory") == []
    assert targets("Prepare Batch Completion Failure") == ["Record AI Failure"]
    parse = node("Parse AI Output")["parameters"]["jsCode"]
    assert "vehicle_based_search" not in parse
    assert "catalogEmoji" not in parse
    for forbidden in ("$getWorkflowStaticData", "_deliveryLedger", "_batches", "_adminNotifications"):
        assert forbidden not in parse
    assert "SLA_TEXT" in parse
    assert "BRAND_LINE" in parse
    assert "SLA_LINE" in parse
    assert "suppressEmoji" in parse
    assert "HOLIDAYS" in parse and "BUSINESS_HOURS" in parse
    assert "Sat: [9, 18]" in parse
    assert "const isBulkOrder" in parse
    assert "const purchaseIntent =" in parse
    assert "const quantitySignal =" in parse
    assert "const b2bSignal =" in parse
    assert "const productContext =" in parse
    assert "bulk_request" in parse
    assert "TOPLU ALIM TALEBİ" in parse
    assert "Toplu sipariş" in parse

    assert targets("Send Delivery", 0) == ["Tag Delivery Success"]
    assert targets("Send Delivery", 1) == ["Tag Delivery Error"]
    assert targets("Tag Delivery Success") == ["Record Delivery Result"]
    assert targets("Tag Delivery Error") == ["Record Delivery Result"]
    send = node("Send Delivery")
    assert send["parameters"]["authentication"] == "predefinedCredentialType"
    assert send["credentials"]["httpHeaderAuth"]["name"] == "Evolution API"
    tag_success = node("Tag Delivery Success")["parameters"]["jsCode"]
    assert "providerId.length > 0" in tag_success
    assert "missing_provider_message_id" in tag_success
    for http_name in ("Send OOH to Customer",):
        http_node = node(http_name)
        assert http_node["type"] == "n8n-nodes-base.httpRequest"
        assert http_node["continueOnFail"] is True
        assert http_node["alwaysOutputData"] is True
        assert "ignoreSslIssues" not in http_node["parameters"].get("options", {})

    enqueue = node("Enqueue Manager OOH Alert")
    assert enqueue["type"] == "n8n-nodes-base.postgres"
    assert "enqueue_ooh_manager_alert" in enqueue["parameters"]["query"]
    assert "$('Build OOH Messages').item.json.oohLogId" in enqueue["parameters"]["options"]["queryReplacement"]
    assert "$('Build OOH Messages').item.json.managerMsg" in enqueue["parameters"]["options"]["queryReplacement"]
    assert "ignoreSslIssues" not in node("Send Delivery")["parameters"].get("options", {})

    assert targets("Schedule Trigger") == ["OpenAI Circuit Gate", "Evolution Circuit Gate", "Run Stale Batch Monitor"]
    for pg_name in ("Ingest Message", "OpenAI Circuit Gate", "Claim Ready Batches", "Complete AI Batch", "Record AI Failure", "Evolution Circuit Gate", "Claim Deliveries", "Record Delivery Result", "Claim OOH Notification", "Enqueue Manager OOH Alert", "Log OOH Event"):
        pg = node(pg_name)
        assert pg["type"] == "n8n-nodes-base.postgres"
        assert pg["credentials"]["postgres"]["name"] in ("WhatsApp State PostgreSQL", "Postgres account")
    stale_monitor = node("Run Stale Batch Monitor")
    assert stale_monitor["type"] == "n8n-nodes-base.postgres"
    assert "run_stale_batch_monitor" in stale_monitor["parameters"]["query"]

    for table in ("settings", "batches", "messages", "manual_modes", "admin_notifications", "unclear_counts", "deliveries", "system_events", "ooh_log", "ooh_manager_dispatch", "chat_memory"):
        assert f"whatsapp_ai.{table}" in SQL
    for function in ("ingest_message", "claim_ready_batches", "complete_ai_batch", "record_ai_failure", "claim_deliveries", "record_delivery_result", "cleanup_expired_state", "recover_stale_deliveries", "run_queue_monitor", "run_daily_report", "run_batch_readiness_probe", "run_stale_batch_monitor", "enqueue_ooh_manager_alert"):
        assert f"FUNCTION whatsapp_ai.{function}" in SQL
    assert "p_correlation_id text DEFAULT ''" in SQL
    assert "correlationId', p_correlation_id" in SQL
    assert "manual_pause" in SQL
    assert "manual_resume" in SQL
    assert "manual_check" in SQL
    assert "customer_sent boolean not null default false" in SQL.lower()
    assert "manager_sent boolean not null default false" in SQL.lower()
    assert "deferred" in SQL.lower()
    assert "channel = 'customer'" in SQL.lower()
    assert "kind', 'ooh_manager'" in SQL.lower()
    assert "primary key (ooh_log_id, channel)" in SQL.lower()
    assert "create index if not exists idx_ooh_log_created" in SQL.lower()
    assert "create index if not exists idx_ooh_log_sender" in SQL.lower()
    assert "create index if not exists idx_ooh_log_sender_created" in SQL.lower()
    assert "interval '8 hours'" in node("Claim OOH Notification")["parameters"]["query"].lower()
    ingest_query = node("Ingest Message")["parameters"]["options"]["queryReplacement"]
    assert "fromMe: $('Normalize Payload').item.json.fromMe" in ingest_query
    assert "command: $('Normalize Payload').item.json.command" in ingest_query
    assert "nextAiAttemptAt" in ingest_query
    assert "x-webhook-secret" in normalize
    assert "webhook_legacy_query_enabled" in SQL
    assert "p_next_ai_attempt_at timestamptz DEFAULT NULL" in SQL
    assert "next_ai_attempt_at = CASE" in SQL
    assert "first_attempt_at" in SQL and "latency_ms" in SQL
    assert "FOR UPDATE SKIP LOCKED" in SQL
    assert SQL.count("processing_token = p_batch_token") >= 4
    assert "UNIQUE (batch_token, channel)" in SQL
    assert "CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'dead'))" in SQL
    assert "assignee_name text" in SQL
    assert "AT TIME ZONE 'Europe/Istanbul'" in SQL
    assert "interval '120 seconds'" in SQL
    assert "recover_stale_batches" in SQL
    assert "stale_batch_recovery" in SQL
    assert "first_message_at = clock_timestamp() - interval '120 seconds'" in SQL
    assert "status = CASE WHEN p_pause_automation THEN 'manual' ELSE 'pending' END" in SQL
    assert "'staleBatches', whatsapp_ai.recover_stale_batches()" in SQL
    assert "interval '10 seconds'" not in SQL
    assert "ai_attempt_count > 0" in SQL
    assert "DROP TABLE IF EXISTS whatsapp_ai.mann_vehicle_catalog" in SQL
    assert "DROP TABLE IF EXISTS whatsapp_ai.catalog_imports" in SQL
    assert "DROP TABLE IF EXISTS whatsapp_ai.customer_vehicle_context" in SQL
    assert "DROP FUNCTION IF EXISTS whatsapp_ai.complete_ai_batch(text, uuid, text, text, boolean, boolean, boolean, text, text)" in FINAL_SQL
    assert "DROP FUNCTION IF EXISTS whatsapp_ai.record_ai_failure(text, uuid, text, text)" in FINAL_SQL
    assert "priority" in FINAL_SQL
    assert "next_ai_attempt_at = clock_timestamp() + CASE v_attempt" in FINAL_SQL
    assert "ADD COLUMN IF NOT EXISTS priority integer NOT NULL DEFAULT 50" in SCHEMA_RECONCILE_SQL
    assert "ORDER BY d.priority DESC, d.created_at" in SCHEMA_RECONCILE_SQL
    assert "CREATE INDEX deliveries_ready_idx" in SCHEMA_RECONCILE_SQL
    assert "STALE BATCH ALERT" in STALE_MONITOR_SQL
    assert "run_stale_batch_monitor" in STALE_MONITOR_SQL
    assert "stale_batch_monitor" in STALE_MONITOR_SQL
    assert "source_key" in CHAT_MEMORY_SQL
    assert "cleanup_chat_memory" in CHAT_MEMORY_SQL
    assert "admin_number_prefixes" in ADMIN_FILTER_SQL
    assert "admin_filter_enabled" in ADMIN_FILTER_SQL
    assert "state IN ('closed', 'open', 'half_open')" in SQL
    assert "run_batch_readiness_probe" in SQL
    assert "claimableCount" in SQL
    assert "nextClaimInSeconds" in SQL
    assert "staleProcessingCount" in SQL
    assert "current_setting('TimeZone')" in SQL
    assert "customer_sent = true" in node("Claim OOH Notification")["parameters"]["query"].lower()

    parse = node("Parse AI Output")["parameters"]["jsCode"]
    assert "textUpper = plainText.toUpperCase()" in parse
    assert "code.toUpperCase()" in parse
    assert "const safetyText = String(reply || '')" in parse
    assert ".replace(/\\u0131/g, 'i')" in parse
    assert ".replace(/\\u0130/g, 'i')" in parse
    assert ".replace(/\\u0049/g, 'i')" in parse
    assert "reply = reply.replace(/\\*\\*(.+?)\\*\\*/g, '*$1*');" in parse
    assert "mevcut\\s+gorunuyor" in parse
    assert "Talebinizi ürün uzmanımıza ilettik" in parse
    assert "mesajınızı aldık, ürün uzmanımız inceliyor" in parse
    assert "Merhaba, ${BRAND_LINE}'ya hoş geldiniz" in parse
    assert "Talebinizi aldık ve ekibimize ilettik." in parse
    assert "schemaVersion: '13.6'" in parse
    assert "fingerprint: `${ctx.senderNumber}:" in parse

    for retry_name in ("Ingest Message", "Claim Ready Batches", "Claim Deliveries", "Complete AI Batch", "Persist Chat Memory", "Load Admin Filter Settings", "Record AI Failure", "Record Delivery Result", "OpenAI Circuit Gate", "Evolution Circuit Gate"):
        retry_node = node(retry_name)
        assert retry_node["retryOnFail"] is True
        assert retry_node["maxTries"] == 3
        assert retry_node["waitBetweenTries"] == 2000

    assert node("Evolution Circuit Gate")["position"] == [352, 1040]
    assert node("Evolution Circuit Open?")["position"] == [560, 1040]
    assert node("Claim Deliveries")["position"] == [784, 1040]
    assert node("Prepare Delivery")["position"] == [1008, 1040]
    assert node("Delivery Valid?")["position"] == [1232, 1040]
    assert node("Send Delivery")["position"] == [1456, 1040]
    assert node("Tag Delivery Success")["position"] == [1680, 960]
    assert node("Tag Delivery Error")["position"] == [1680, 1088]
    assert node("Tag Delivery Validation Error")["position"] == [1456, 1216]
    assert node("Record Delivery Result")["position"] == [1904, 1040]

    source = (ROOT / "build_workflow.py").read_text(encoding="utf-8")
    assert not re.search(r"apikey.{0,30}[A-F0-9]{20,}", source, flags=re.I | re.S)
    assert "webhook_token" in SQL, "PostgreSQL webhook auth must be present"
    assert "N8N_POSTGRES_CREDENTIAL_ID" in source
    assert "vehicle_based_search" not in source
    assert "prepare_catalog_js" not in source
    assert "apply_catalog_js" not in source
    print("[PASS] PostgreSQL state, auth, token and outbox contracts")


if __name__ == "__main__":
    main()
