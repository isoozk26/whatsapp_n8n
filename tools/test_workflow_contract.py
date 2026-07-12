#!/usr/bin/env python3
"""Offline contract tests for the generated n8n workflow."""
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflow.json"


def targets(workflow, source, output=0):
    ports = workflow["connections"].get(source, {}).get("main", [])
    if output >= len(ports):
        return []
    return [edge["node"] for edge in ports[output]]


def main():
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    names = [node["name"] for node in workflow["nodes"]]
    assert len(names) == len(set(names)), "Node names must be unique"
    assert "Respond OK1" not in names, "onReceived webhook must not use Respond to Webhook"

    expected = {
        "Phone A Send": ("Tag Success Phone A", "Tag Err Phone A"),
        "Phone B Send": ("Tag Success Phone B", "Tag Err Phone B"),
        "Reply to Customer": ("Tag Success Reply", "Tag Err Reply"),
    }
    for sender, (success_tag, error_tag) in expected.items():
        assert targets(workflow, sender, 0) == [success_tag]
        assert targets(workflow, sender, 1) == [error_tag]
        assert targets(workflow, success_tag, 0) == ["Finalize Batch"]
        assert targets(workflow, error_tag, 0) == ["Dead Letter Admin"]

    assert targets(workflow, "Dead Letter Admin", 0) == ["Finalize Batch"]
    finalize = next(n for n in workflow["nodes"] if n["name"] == "Finalize Batch")
    finalize_code = finalize["parameters"]["jsCode"]
    for contract in ("_deliveryLedger", "completedChannel", "allCompleted", "Object.assign"):
        assert contract in finalize_code, f"Finalize contract missing: {contract}"

    print("[PASS] workflow graph and delivery-ledger contracts")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
