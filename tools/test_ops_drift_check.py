#!/usr/bin/env python3
"""Offline regression tests for the dual-workflow drift probe."""
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ops_drift_check", ROOT / "tools" / "ops_drift_check.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def run_probe(workflow, executions, config):
    responses = iter([(200, workflow), (200, executions)])
    original = MODULE.request_json
    MODULE.request_json = lambda *_args, **_kwargs: next(responses)
    try:
        return MODULE.probe_workflow("https://n8n.example", {}, config)
    finally:
        MODULE.request_json = original


def main():
    main_config = {"key": "main", "id": "main-id", "expected_name": MODULE.DEFAULT_MAIN_NAME, "expected_version": "main-v1"}
    ops_config = {"key": "ops", "id": "ops-id", "expected_name": MODULE.DEFAULT_OPS_NAME, "expected_version": "ops-v1"}
    assert run_probe({"active": True, "name": MODULE.DEFAULT_MAIN_NAME, "versionId": "main-v1"}, {"data": [{"id": "1"}]}, main_config) == []
    assert run_probe({"active": True, "name": MODULE.DEFAULT_OPS_NAME, "versionId": "stale"}, {"data": [{"id": "2"}]}, ops_config) == [{"check": "ops_version", "actual": "stale", "expected": "ops-v1"}]
    findings = run_probe({"active": False, "name": "wrong", "versionId": "ops-v1"}, {"data": []}, ops_config)
    assert {item["check"] for item in findings} == {"ops_active", "ops_name", "ops_last_execution"}
    print("ops drift check tests passed")


if __name__ == "__main__":
    main()
