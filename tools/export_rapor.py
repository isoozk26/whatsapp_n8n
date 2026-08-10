#!/usr/bin/env python3
"""
Export tool for rapor.md.
Converts markdown report into:
- rapor_export.md (Standalone Markdown Export)
- rapor_export.json (Structured JSON Export)
- rapor_export.txt (Standalone Plain-Text Export)
"""

import json
import os
import re
import shutil
import sys


def parse_rapor_md(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Report file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()

    # Extract metadata
    metadata = {}
    doc_title = ""
    sections = []

    current_section = None
    current_subsection = None
    current_content = []

    for line in lines:
        if line.startswith("# ") and not doc_title:
            doc_title = line.replace("# ", "").strip()
            continue

        if line.startswith("**Doküman:**"):
            metadata["document"] = line.split("**Doküman:**")[1].replace("`", "").strip()
            continue
        elif line.startswith("**Sistem:**"):
            metadata["system"] = line.split("**Sistem:**")[1].strip()
            continue
        elif line.startswith("**Tarih:**"):
            metadata["date"] = line.split("**Tarih:**")[1].strip()
            continue
        elif line.startswith("**Kapsam:**"):
            metadata["scope"] = line.split("**Kapsam:**")[1].strip()
            continue

        # Section headers
        if line.startswith("## "):
            if current_section:
                current_section["content"] = "\n".join(current_content).strip()
                sections.append(current_section)
                current_content = []

            sec_title = line.replace("## ", "").strip()
            current_section = {"title": sec_title, "content": "", "subsections": []}
            current_subsection = None
            continue

        if line.startswith("### ") and current_section:
            subsec_title = line.replace("### ", "").strip()
            current_subsection = {"title": subsec_title, "content": ""}
            current_section["subsections"].append(current_subsection)
            continue

        current_content.append(line)

    if current_section:
        current_section["content"] = "\n".join(current_content).strip()
        sections.append(current_section)

    return {
        "title": doc_title,
        "metadata": metadata,
        "section_count": len(sections),
        "sections": sections,
        "raw_content": content,
    }


def export_md(input_path, output_path):
    shutil.copyfile(input_path, output_path)
    print(f"[EXPORT SUCCESS] Markdown report exported to: {output_path}")


def export_json(parsed_data, output_path):
    # Save structured JSON without raw content to keep it clean
    json_data = {k: v for k, v in parsed_data.items() if k != "raw_content"}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"[EXPORT SUCCESS] JSON report exported to: {output_path}")


def export_txt(parsed_data, output_path):
    txt_lines = []
    txt_lines.append("================================================================================")
    txt_lines.append(parsed_data["title"].upper())
    txt_lines.append("================================================================================")
    txt_lines.append("")

    for k, v in parsed_data["metadata"].items():
        txt_lines.append(f"{k.upper()}: {v}")

    txt_lines.append("")
    txt_lines.append("-" * 80)

    for sec in parsed_data["sections"]:
        txt_lines.append("")
        txt_lines.append(f"=== {sec['title']} ===")
        txt_lines.append("")
        if sec["content"]:
            txt_lines.append(sec["content"])
            txt_lines.append("")

        for subsec in sec.get("subsections", []):
            txt_lines.append(f"--- {subsec['title']} ---")
            if subsec["content"]:
                txt_lines.append(subsec["content"])
            txt_lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    print(f"[EXPORT SUCCESS] Standalone text report exported to: {output_path}")


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rapor_md = os.path.join(repo_root, "rapor.md")
    md_out = os.path.join(repo_root, "rapor_export.md")
    json_out = os.path.join(repo_root, "rapor_export.json")
    txt_out = os.path.join(repo_root, "rapor_export.txt")

    if not os.path.exists(rapor_md):
        print(f"Error: {rapor_md} does not exist.")
        sys.exit(1)

    print("Parsing and exporting rapor.md...")
    parsed = parse_rapor_md(rapor_md)

    export_md(rapor_md, md_out)
    export_json(parsed, json_out)
    export_txt(parsed, txt_out)

    print("\nExport completed successfully for all 3 formats (.md, .json, .txt)!")


if __name__ == "__main__":
    main()
