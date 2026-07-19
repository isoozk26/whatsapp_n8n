#!/usr/bin/env python3
"""Fail when the committed workflow artifact differs from its source builder."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="workflow-drift-") as directory:
        generated = Path(directory) / "workflow.json"
        env = os.environ.copy()
        env["N8N_WORKFLOW_OUTPUT"] = str(generated)
        result = subprocess.run(
            [sys.executable, str(ROOT / "build_workflow.py")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            sys.stderr.write(result.stdout + result.stderr)
            return result.returncode
        expected = load(ROOT / "workflow.json")
        actual = load(generated)
        if expected != actual:
            print("[FAIL] workflow.json is out of sync with build_workflow.py")
            return 1
    print("[PASS] workflow artifact matches build_workflow.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
