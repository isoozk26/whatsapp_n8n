#!/usr/bin/env python3
"""Offline contract tests for the generated n8n workflow."""
import json
import re
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
        assert targets(workflow, error_tag, 0) == ["Dead Letter Admin", "Finalize Batch"]

    assert targets(workflow, "Should Notify Admins?", 1) == ["Finalize Batch"]
    assert targets(workflow, "Should Reply Customer?", 1) == ["Finalize Batch"]

    command_targets = targets(workflow, "Is Command?", 0)
    assert command_targets == ["Delete Command Message", "Phone A Send", "Phone B Send"]
    delete_command = next(n for n in workflow["nodes"] if n["name"] == "Delete Command Message")
    assert delete_command["parameters"]["method"] == "DELETE"
    assert delete_command["parameters"]["url"].endswith("/chat/deleteMessageForEveryone/filtr")
    for field in ("commandMessageId", "commandFromMe", "commandRemoteJid"):
        assert field in delete_command["parameters"]["body"]

    collector = next(n for n in workflow["nodes"] if n["name"] == "Batch Collector")
    collector_code = collector["parameters"]["jsCode"]
    assert "905363955525" in collector_code
    for field in ("commandMessageId", "commandFromMe", "commandRemoteJid"):
        assert field in collector_code

    assert targets(workflow, "Dead Letter Admin", 0) == []
    finalize = next(n for n in workflow["nodes"] if n["name"] == "Finalize Batch")
    finalize_code = finalize["parameters"]["jsCode"]
    for contract in ("_deliveryLedger", "completedChannel", "allCompleted", "Object.assign"):
        assert contract in finalize_code, f"Finalize contract missing: {contract}"

    stale = next(n for n in workflow["nodes"] if n["name"] == "Stale Batch Check")
    stale_code = stale["parameters"]["jsCode"]
    assert "BATCH_WINDOW_MS    = 120 * 1000" in stale_code
    assert "IDLE_WINDOW_MS" not in stale_code
    assert "MAX_WAIT_MS" not in stale_code
    assert "enabled !== true" in stale_code, "Legacy false manual-mode entries must be cleaned"

    assert collector_code.count("Object.entries(staticData._seenMessageIds)") == 1
    assert "cleanupIntervalMs = 5 * 60 * 1000" in collector_code
    assert "delete staticData._manualModes[senderNumber]" in collector_code

    parse = next(n for n in workflow["nodes"] if n["name"] == "Parse AI Output")
    parse_code = parse["parameters"]["jsCode"]
    for contract in (
        "shouldNotifyAdmin = true",
        "phoneA: true",
        "phoneB: true",
        "shouldReplyCustomer",
        "expectedChannels['customer']",
    ):
        assert contract in parse_code, f"Three-channel batch contract missing: {contract}"

    for node in workflow["nodes"]:
        parameters = node.get("parameters", {})
        if parameters.get("mode") != "runOnceForEachItem":
            continue
        code = parameters.get("jsCode", "")
        for disallowed in ("$input.first()", "$input.all()", "$input.last()"):
            assert disallowed not in code, (
                f"{node['name']} uses {disallowed} in runOnceForEachItem mode"
            )
        assert not re.search(r"return\s*\[\s*\{", code), (
            f"{node['name']} returns an item array in runOnceForEachItem mode"
        )

    source = (ROOT / "build_workflow.py").read_text(encoding="utf-8")
    for assignment in ("store_context_js", "ai_agent_system_message", "parse_ai_output_js"):
        assert len(re.findall(rf"^{assignment}\s*=", source, flags=re.MULTILINE)) == 1, (
            f"Duplicate assignment remains: {assignment}"
        )
    assert "catch(e) {}" not in source and "catch(e2) {}" not in source
    assert "except Exception:\n    wf = {}" not in source

    for deploy_script in (ROOT / "upload_to_n8n.py", ROOT / "tools" / "wf_deploy.py"):
        deploy_source = deploy_script.read_text(encoding="utf-8")
        assert "deactivate" in deploy_source and "activate" in deploy_source
        assert "staticData" in deploy_source

    print("[PASS] workflow graph and delivery-ledger contracts")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
