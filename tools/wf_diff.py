#!/usr/bin/env python3
"""Tool 3: Versiyon Karsilastirici - iki workflow.json karsilastirir"""
import json
import sys

def diff(file1, file2):
    with open(file1, "r", encoding="utf-8") as f:
        wf1 = json.load(f)
    with open(file2, "r", encoding="utf-8") as f:
        wf2 = json.load(f)

    nodes1 = {n["name"]: n for n in wf1.get("nodes", [])}
    nodes2 = {n["name"]: n for n in wf2.get("nodes", [])}

    added = set(nodes2.keys()) - set(nodes1.keys())
    removed = set(nodes1.keys()) - set(nodes2.keys())
    common = set(nodes1.keys()) & set(nodes2.keys())

    changed = []
    for name in sorted(common):
        n1, n2 = nodes1[name], nodes2[name]
        diffs = []
        if n1.get("parameters") != n2.get("parameters"):
            diffs.append("parameters")
        if n1.get("position") != n2.get("position"):
            diffs.append("position")
        if n1.get("type") != n2.get("type"):
            diffs.append("type")
        if n1.get("typeVersion") != n2.get("typeVersion"):
            diffs.append("typeVersion")
        if diffs:
            changed.append((name, diffs))

    conn1 = wf1.get("connections", {})
    conn2 = wf2.get("connections", {})
    conn_changed = conn1 != conn2

    print(f"\n{'='*50}")
    print(f"VERSIYON KARSILASTIRMA")
    print(f"  {file1} vs {file2}")
    print(f"{'='*50}")
    print(f"  {file1}: {len(nodes1)} node, {len(conn1)} baglanti")
    print(f"  {file2}: {len(nodes2)} node, {len(conn2)} baglanti")

    if added:
        print(f"\n  + EKLENEN ({len(added)}):")
        for a in sorted(added):
            print(f"    + {a}")

    if removed:
        print(f"\n  - SILINEN ({len(removed)}):")
        for r in sorted(removed):
            print(f"    - {r}")

    if changed:
        print(f"\n  ~ GUNCELLENEN ({len(changed)}):")
        for name, diffs in changed:
            print(f"    ~ {name}: {', '.join(diffs)}")

    if conn_changed:
        print(f"\n  * BAGLANTILAR DEGISTI")

    if not added and not removed and not changed and not conn_changed:
        print(f"\n  = FARK YOK")

    print(f"{'='*50}\n")
    return {"added": list(added), "removed": list(removed), "changed": [(n, d) for n, d in changed], "connChanged": conn_changed}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Kullanim: python wf_diff.py <dosya1> <dosya2>")
        sys.exit(1)
    diff(sys.argv[1], sys.argv[2])
