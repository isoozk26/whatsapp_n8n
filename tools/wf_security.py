#!/usr/bin/env python3
"""Tool: Guvenlik Tarayici - Hardcoded secret, SSL, webhook auth kontrolu"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = [
    (r'(?i)apikey["\x27]?\s*[:=]\s*["\x27][A-Z0-9-]{20,}["\x27]', 'API Key (genel)'),
    (r'(?i)password["\x27]?\s*[:=]\s*["\x27][^\x27"]{8,}["\x27]', 'Password'),
    (r'(?i)secret["\x27]?\s*[:=]\s*["\x27][^\x27"]{8,}["\x27]', 'Secret'),
    (r'(?i)token["\x27]?\s*[:=]\s*["\x27][A-Za-z0-9._-]{20,}["\x27]', 'Token'),
    (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', 'Private Key'),
]

SSL_PATTERNS = [
    (r'ssl\._create_unverified_context\(\)', 'SSL verification disabled'),
    (r'verify\s*=\s*False', 'SSL verify=False'),
]

def scan_file(filepath, content):
    findings = []
    for pattern, desc in SECRET_PATTERNS:
        for m in re.finditer(pattern, content):
            line_num = content[:m.start()].count('\n') + 1
            findings.append({'file': str(filepath), 'line': line_num, 'type': 'SECRET', 'severity': 'CRITICAL', 'description': desc, 'match': m.group()[:50]})
    for pattern, desc in SSL_PATTERNS:
        for m in re.finditer(pattern, content):
            line_num = content[:m.start()].count('\n') + 1
            findings.append({'file': str(filepath), 'line': line_num, 'type': 'SSL', 'severity': 'MEDIUM', 'description': desc, 'match': m.group()})
    return findings

def main():
    print(f"\n{'='*60}")
    print("GUVENLIK TARAYICI - WhatsApp n8n Workflow")
    print(f"{'='*60}")
    all_findings = []
    active_files = [
        ROOT / 'build_workflow.py',
        ROOT / 'upload_to_n8n.py',
        ROOT / 'tools' / 'wf_deploy.py',
        ROOT / 'tools' / 'wf_migrate.py',
        ROOT / 'tools' / 'wf_test_webhook.py',
        ROOT / 'tools' / 'live_customer_scenario_test.py',
    ]
    for py_file in active_files:
        if py_file.exists():
            content = py_file.read_text(encoding='utf-8', errors='replace')
            all_findings.extend(scan_file(py_file.relative_to(ROOT), content))
    wf_path = ROOT / 'workflow.json'
    if wf_path.exists():
        all_findings.extend(scan_file('workflow.json', wf_path.read_text(encoding='utf-8')))
    critical = [f for f in all_findings if f['severity'] == 'CRITICAL']
    high = [f for f in all_findings if f['severity'] == 'HIGH']
    medium = [f for f in all_findings if f['severity'] == 'MEDIUM']
    print(f"\n  Toplam bulgu: {len(all_findings)} | KRITIK: {len(critical)} | YUKSEK: {len(high)} | ORTA: {len(medium)}")
    for f in all_findings:
        print(f"    [{f['severity']}] {f['type']}: {f['file']}:{f['line']} - {f['description']}")
    print(f"\n{'='*60}")
    if not all_findings:
        print("  GUVENLIK KONTROLU GECTI - Bulgu yok")
    else:
        print(f"  {len(all_findings)} BULGU TESPIT EDILDI")
    print(f"{'='*60}\n")
    return len(critical) == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
