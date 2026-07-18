#!/usr/bin/env python3
"""Stage and explicitly activate the MANN vehicle catalog in PostgreSQL."""
import argparse
import csv
import hashlib
import os
import re
from pathlib import Path


REQUIRED = [
    "ID", "Marka", "Model Serisi", "Motor", "Motor Kodu", "Güç (kW)",
    "Güç (BHP)", "Hacim (ccm)", "Yakıt Tipi", "Üretim Başlangıç", "Üretim Bitiş",
]


def number(value):
    match = re.search(r"\d+", str(value or "").replace(".", ""))
    return int(match.group()) if match else None


def year(value):
    match = re.search(r"\b(19\d{2}|20\d{2})\b", str(value or ""))
    return int(match.group()) if match else None


def engine_codes(value):
    return [part.strip() for part in re.split(r"[,;/|]", str(value or "")) if part.strip()]


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in REQUIRED if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")
        for row in reader:
            if not all(str(row.get(key, "")).strip() for key in ("ID", "Marka", "Model Serisi", "Motor")):
                continue
            yield (
                number(row["ID"]), row["Marka"].strip(), row["Model Serisi"].strip(), row["Motor"].strip(),
                engine_codes(row["Motor Kodu"]), number(row["Güç (kW)"]), number(row["Güç (BHP)"]),
                number(row["Hacim (ccm)"]), row["Yakıt Tipi"].strip() or None,
                year(row["Üretim Başlangıç"]), year(row["Üretim Bitiş"]),
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--database-url", default=os.environ.get("WHATSAPP_POSTGRES_URL"))
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--checksum", help="Required confirmation checksum for activation")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("Set WHATSAPP_POSTGRES_URL or pass --database-url")
    source_checksum = checksum(args.csv_path)
    if args.activate and args.checksum != source_checksum:
        raise SystemExit(f"Activation refused. Expected --checksum {source_checksum}")

    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install psycopg[binary] to run the importer") from exc

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT whatsapp_ai.begin_catalog_import(%s,%s)", (source_checksum, args.csv_path.name))
            import_id = cursor.fetchone()[0]
            if not args.activate:
                statement = """
                    INSERT INTO whatsapp_ai.mann_vehicle_catalog(
                      import_id,source_id,brand,model_series,engine,engine_codes,power_kw,power_bhp,
                      displacement_ccm,fuel_type_raw,production_start,production_end,
                      brand_norm,model_norm,engine_norm)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                      whatsapp_ai.norm_catalog_text(%s),whatsapp_ai.norm_catalog_text(%s),whatsapp_ai.norm_catalog_text(%s))
                """
                batch = []
                seen = set()
                for item in rows(args.csv_path):
                    vehicle_key = (item[1], item[2], item[3], tuple(item[4]), *item[5:])
                    if vehicle_key in seen:
                        continue
                    seen.add(vehicle_key)
                    staged = (len(seen), *item[1:])
                    batch.append((import_id, *staged, staged[1], staged[2], staged[3]))
                    if len(batch) == 1000:
                        cursor.executemany(statement, batch)
                        batch.clear()
                if batch:
                    cursor.executemany(statement, batch)
                cursor.execute("SELECT whatsapp_ai.refresh_catalog_import_stats(%s)", (import_id,))
            else:
                cursor.execute("SELECT whatsapp_ai.activate_catalog_import(%s,%s)", (import_id, source_checksum))
            result = cursor.fetchone()[0]
        connection.commit()
    print({"checksum": source_checksum, "result": result, "activated": args.activate})


if __name__ == "__main__":
    main()
