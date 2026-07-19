#!/usr/bin/env python3
"""Tool 1: Workflow Dogrulayici - workflow.json yapIsini dogrular"""
import json
import sys
import re
import hashlib
import subprocess
import tempfile
from pathlib import Path

def validate(path="workflow.json"):
    errors = []
    warnings = []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            wf = json.load(f)
    except FileNotFoundError:
        print(f"  DOSYA BULUNAMADI: {path}")
        return False
    except json.JSONDecodeError as e:
        print(f"  JSON HATASI: {e}")
        return False

    # Zorunlu ust alanlar
    for field in ["nodes", "connections"]:
        if field not in wf:
            errors.append(f"Eksik ust alan: {field}")

    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})
    
    # Node ID benzersizligi
    ids = [n.get("id") for n in nodes]
    dupes = [x for x in ids if ids.count(x) > 1]
    if dupes:
        errors.append(f"Tekrarlanan node ID: {set(dupes)}")

    # Her node'un zorunlu alanlari
    node_names = set()
    js_checksums = {}
    for n in nodes:
        name = n.get("name", "???")
        node_names.add(name)
        for field in ["id", "name", "type", "position"]:
            if field not in n:
                errors.append(f"'{name}' eksik alan: {field}")

        # JS kod kontrolu
        js = n.get("parameters", {}).get("jsCode", "")
        if js:
            mode = n.get("parameters", {}).get("mode", "runOnceForAllItems")
            if mode == "runOnceForEachItem":
                for disallowed in ("$input.first()", "$input.all()", "$input.last()"):
                    if disallowed in js:
                        errors.append(
                            f"'{name}' runOnceForEachItem modunda yasak girdi erişimi kullanıyor: {disallowed}"
                        )
                if re.search(r"return\s*\[\s*\{", js):
                    errors.append(
                        f"'{name}' runOnceForEachItem modunda öğe dizisi döndürüyor"
                    )
            backticks = js.count("`")
            if backticks % 2 != 0:
                warnings.append(f"'{name}' tek backtick: {backticks}")
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
                handle.write(js)
                js_path = handle.name
            try:
                checked = subprocess.run(["node", "--check", js_path], capture_output=True, text=True)
                if checked.returncode:
                    errors.append(f"'{name}' JavaScript syntax hatası: {checked.stderr.strip()}")
            finally:
                Path(js_path).unlink(missing_ok=True)
            js_checksums[name] = hashlib.md5(js.encode()).hexdigest()[:8]

    # Baglanti hatalari
    for source, conn in connections.items():
        if source not in node_names:
            errors.append(f"Baglanti kaynagi bulunamadi: '{source}'")
        for output_type, outputs in conn.items():
            for targets in outputs:
                for t in targets:
                    tname = t.get("node", "")
                    if tname not in node_names:
                        errors.append(f"Hedef node bulunamadi: '{tname}' (kaynak: '{source}')")

    # Sonuc
    print(f"\n{'='*50}")
    print(f"WORKFLOW DOGRULAMA: {path}")
    print(f"{'='*50}")
    print(f"  Node sayisi: {len(nodes)}")
    print(f"  Baglanti: {len(connections)} kaynak")
    print(f"  JS checksum: {len(js_checksums)} kod bloku")
    
    for name, cs in js_checksums.items():
        print(f"    {name}: {cs}")
    
    if errors:
        print(f"\n  {len(errors)} HATA:")
        for e in errors:
            print(f"    [HATA] {e}")
    
    if warnings:
        print(f"\n  {len(warnings)} UYARI:")
        for w in warnings:
            print(f"    [UYARI] {w}")
    
    if not errors and not warnings:
        print(f"\n  TUM KONTROLLERDEN GECTI")
    
    print(f"{'='*50}\n")
    return len(errors) == 0

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "workflow.json"
    ok = validate(path)
    sys.exit(0 if ok else 1)
