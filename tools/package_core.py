#!/usr/bin/env python3
"""Create a secret-safe source archive from the current working tree."""
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "core.zip"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".mimocode", "opus5_analysis_package"}
SKIP_NAMES = {"core.zip", "core-safe.zip"}
SKIP_HISTORICAL = {
    "db/migrations/010_set_webhook_token.sql",
    "db/migrations/024_set_admin_phones.sql",
    "db/migrations/036_fix_webhook_token.sql",
}
FORBIDDEN = re.compile(r"(^|/)(\.env(?:\..*)?|.*\.(?:pem|key|p12|pfx)|.*secret.*|.*token.*)(/|$)", re.I)


def excluded(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if relative in SKIP_HISTORICAL or path.name in SKIP_NAMES:
        return True
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    return bool(FORBIDDEN.search(relative))


def main() -> int:
    files = [p for p in ROOT.rglob("*") if p.is_file() and not excluded(p)]
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(OUTPUT) as archive:
        names = archive.namelist()
        bad = [name for name in names if excluded(ROOT / Path(name))]
    if bad:
        print("PACKAGE FAILED: forbidden entries present")
        for name in bad:
            print(f"  - {name}")
        return 1
    print(f"PACKAGE PASS: {OUTPUT} ({len(names)} files, {OUTPUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
