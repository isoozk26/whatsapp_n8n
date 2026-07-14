#!/usr/bin/env python3
"""Tool: Hizli Durum - Proje durumunu ozetler"""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    print(f"\n{'='*60}")
    print("PROJE DURUMU - WhatsApp n8n Workflow v12.5 Enterprise")
    print(f"{'='*60}")

    # workflow.json kontrol
    wf_path = ROOT / 'workflow.json'
    if wf_path.exists():
        wf = json.loads(wf_path.read_text(encoding='utf-8'))
        nodes = wf.get('nodes', [])
        conns = wf.get('connections', {})
        print(f"\n  WORKFLOW:")
        print(f"    Node sayisi: {len(nodes)}")
        print(f"    Baglanti: {len(conns)} kaynak")
        print(f"    Isim: {wf.get('name', '?')}")
    else:
        print(f"\n  WORKFLOW: ❌ workflow.json bulunamadi")

    # build_workflow.py kontrol
    build_path = ROOT / 'build_workflow.py'
    if build_path.exists():
        content = build_path.read_text(encoding='utf-8')
        lines = content.count('\n') + 1
        cs = hashlib.md5(content.encode()).hexdigest()[:8]
        print(f"\n  KAYNAK KOD:")
        print(f"    build_workflow.py: {lines} satir, md5:{cs}")

        # Hardcoded key kontrolu
        import re
        hardcoded = re.findall(r'089311B617B8', content)
        print(f"    Hardcoded key: {len(hardcoded)} adet {'❌' if hardcoded else '✅'}")

        # env var kontrolu
        env_refs = re.findall(r"os\.environ\.get\('EVOLUTION_API_KEY'\)", content)
        print(f"    ENV referans: {len(env_refs)} adet")

    # Test durumu
    print(f"\n  TESTLER:")
    test_files = [
        ('wf_validate.py', 'Static Dogrulama'),
        ('test_workflow_contract.py', 'Contract Test'),
        ('wf_test.py', 'Simulasyon'),
        ('wf_security.py', 'Guvenlik Tarama'),
        ('wf_audit.py', 'Tam Audit'),
        ('wf_checkpoint.py', 'Checkpoint Tracker'),
    ]
    for fname, desc in test_files:
        fpath = ROOT / 'tools' / fname
        icon = '✅' if fpath.exists() else '❌'
        print(f"    {icon} {desc}: {fname}")

    # E2E Rapor
    e2e_path = ROOT / 'E2E_ANALIZ_RAPORU.md'
    if e2e_path.exists():
        print(f"\n  RAPOR: ✅ E2E_ANALIZ_RAPORU.md mevcut")
    else:
        print(f"\n  RAPOR: ⚠️ E2E_ANALIZ_RAPORU.md yok")

    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
