#!/usr/bin/env python3
"""Apply WhatsApp state migrations to n8n's existing PostgreSQL database."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"

def main():
    database_url = os.environ.get("WHATSAPP_POSTGRES_URL")
    if not database_url:
        raise SystemExit("WHATSAPP_POSTGRES_URL is required; use n8n's existing PostgreSQL connection URL")
    psql = shutil.which("psql")
    if not psql:
        raise SystemExit("psql is required to apply migrations")
    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        raise SystemExit("No SQL migrations found")
    for migration in files:
        print(f"Applying {migration.name}")
        result = subprocess.run([psql, database_url, "-v", "ON_ERROR_STOP=1", "-f", str(migration)], text=True)
        if result.returncode:
            return result.returncode
    print("PostgreSQL migrations: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
