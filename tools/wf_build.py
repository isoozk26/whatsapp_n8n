#!/usr/bin/env python3
"""Tool 4: Build & Verify - build_workflow.py calistirip sonucu dogrular"""
import json
import subprocess
import hashlib
import sys
import os
import shutil

def build_and_verify():
    print(f"\n{'='*50}")
    print("BUILD & VERIFY")
    print(f"{'='*50}")

    # Orijinali yedekle
    if os.path.exists("workflow.json"):
        shutil.copy2("workflow.json", "workflow.json.verify_backup")

    # Build calistir
    print("\n  [1] build_workflow.py calistiriliyor...")
    result = subprocess.run([sys.executable, "build_workflow.py"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [HATA] build_workflow.py basarisiz:")
        print(f"    {result.stderr}")
        return False
    print(f"  [OK] {result.stdout.strip()}")

    # Workflow.json yukle
    try:
        with open("workflow.json", "r", encoding="utf-8") as f:
            wf = json.load(f)
    except Exception as e:
        print(f"  [HATA] workflow.json okunamadi: {e}")
        return False

    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})

    # Istatistikler
    print(f"\n  [2] Istatistikler:")
    print(f"    Node sayisi: {len(nodes)}")
    print(f"    Baglanti: {len(connections)} kaynak")

    # Node listesi
    print(f"\n  [3] Node listesi:")
    for n in nodes:
        print(f"    - {n['name']} ({n['type']})")

    # Baglanti haritasi
    print(f"\n  [4] Baglanti haritasi:")
    for source, conn in connections.items():
        for outputs in conn.values():
            for targets in outputs:
                for t in targets:
                    print(f"    {source} -> {t['node']}")

    # JS checksum
    print(f"\n  [5] JS Kod Checksum:")
    for n in nodes:
        js = n.get("parameters", {}).get("jsCode", "")
        if js:
            cs = hashlib.md5(js.encode()).hexdigest()[:8]
            print(f"    {n['name']}: {cs} ({len(js)} chars)")

    # Yedegi temizle
    if os.path.exists("workflow.json.verify_backup"):
        os.remove("workflow.json.verify_backup")

    print(f"\n  BUILD BASARILI")
    print(f"{'='*50}\n")
    return True


if __name__ == "__main__":
    ok = build_and_verify()
    sys.exit(0 if ok else 1)
