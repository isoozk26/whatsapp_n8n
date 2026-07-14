#!/usr/bin/env python3
"""Tool: Tam Audit - Tum kontrolleri tek seferde calistirir"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run_check(name, cmd, cwd=None):
    print(f"\n  [{name}] Calistiriliyor...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or ROOT, timeout=120)
        if result.returncode == 0:
            print(f"  [{name}] ✅ PASS")
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n')[:3]:
                    print(f"    {line}")
            return True
        else:
            print(f"  [{name}] ❌ FAIL (exit {result.returncode})")
            if result.stderr.strip():
                for line in result.stderr.strip().split('\n')[:3]:
                    print(f"    {line}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  [{name}] ⏱️ TIMEOUT")
        return False
    except Exception as e:
        print(f"  [{name}] ❌ ERROR: {e}")
        return False

def main():
    print(f"\n{'='*60}")
    print("TAM AUDIT - WhatsApp n8n Workflow")
    print(f"{'='*60}")

    results = {}

    # 1. Build
    results['Build'] = run_check('Build', [sys.executable, 'build_workflow.py'])

    # 2. Validate
    results['Validate'] = run_check('Validate', [sys.executable, 'tools/wf_validate.py', 'workflow.json'])

    # 3. Contract Tests
    results['Contract'] = run_check('Contract', [sys.executable, 'tools/test_workflow_contract.py'])

    # 4. Security Scan
    results['Security'] = run_check('Security', [sys.executable, 'tools/wf_security.py'])

    # 5. Simulation Tests
    results['Simulation'] = run_check('Simulation', [sys.executable, 'tools/wf_test.py'])

    # Summary
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"  SONUC: {passed}/{total} TEST GECTI")
    for name, ok in results.items():
        icon = '✅' if ok else '❌'
        print(f"    {icon} {name}")
    print(f"{'='*60}\n")

    return passed == total

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
