#!/usr/bin/env python3
"""Tool 6: Node Inceleyici - belirli bir node'un detaylarini gosterir"""
import json
import sys
import hashlib

def inspect(node_name=None):
    with open("workflow.json", "r", encoding="utf-8") as f:
        wf = json.load(f)

    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})

    # Arama
    if node_name:
        matches = [n for n in nodes if node_name.lower() in n["name"].lower()]
        if not matches:
            print(f"  '{node_name}' ile eslesen node bulunamadi.")
            print(f"  Mevcut node'lar: {', '.join(n['name'] for n in nodes)}")
            return
        target = matches[0]
    else:
        # Tum node'lari listele
        print(f"\n{'='*50}")
        print("NODE LISTESI")
        print(f"{'='*50}")
        for n in nodes:
            js = n.get("parameters", {}).get("jsCode", "")
            js_info = f" [JS: {len(js)} chars]" if js else ""
            print(f"  - {n['name']} ({n['type']}){js_info}")
        print(f"{'='*50}\n")
        return

    # Node detayi
    name = target["name"]
    print(f"\n{'='*50}")
    print(f"NODE: {name}")
    print(f"{'='*50}")
    print(f"  ID: {target.get('id')}")
    print(f"  Type: {target.get('type')}")
    print(f"  Version: {target.get('typeVersion')}")
    print(f"  Position: {target.get('position')}")

    # Parametreler
    params = target.get("parameters", {})
    print(f"\n  PARAMETRELER:")
    for key, val in params.items():
        if key == "jsCode":
            js = val
            cs = hashlib.md5(js.encode()).hexdigest()[:8]
            print(f"    {key}: [JS CODE - {len(js)} chars, md5:{cs}]")
            # JS kodunu goster
            print(f"\n  JS KODU:")
            for i, line in enumerate(js.split("\n")[:30], 1):
                print(f"    {i:3d}| {line}")
            if js.count("\n") > 30:
                print(f"    ... ({js.count(chr(10))+1} satir toplam)")
        elif isinstance(val, str) and len(val) > 100:
            print(f"    {key}: {val[:100]}...")
        else:
            print(f"    {key}: {val}")

    # Baglantilar
    print(f"\n  BAGLANTILAR:")
    # Gelen
    incoming = []
    for source, conn in connections.items():
        for outputs in conn.values():
            for targets in outputs:
                for t in targets:
                    if t.get("node") == name:
                        incoming.append(source)
    if incoming:
        print(f"    Gelen: {', '.join(incoming)}")
    else:
        print(f"    Gelen: (yok - tetikleyici)")

    # Giden
    outgoing = []
    if name in connections:
        for outputs in connections[name].values():
            for targets in outputs:
                for t in targets:
                    outgoing.append(t.get("node"))
    if outgoing:
        print(f"    Giden: {', '.join(outgoing)}")
    else:
        print(f"    Giden: (yok - son node)")

    # Credentials
    creds = target.get("credentials")
    if creds:
        print(f"\n  CREDENTIALS:")
        for cred_name, cred in creds.items():
            print(f"    {cred_name}: {cred.get('name')} (id: {cred.get('id')})")

    print(f"{'='*50}\n")


if __name__ == "__main__":
    name = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    inspect(name)
