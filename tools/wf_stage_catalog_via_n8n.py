#!/usr/bin/env python3
"""Stage MANN vehicle rows through temporary n8n webhooks; never activates an import."""
import json
import os
import secrets
import sys
import urllib.request
import urllib.error
import time
from pathlib import Path

import import_mann_catalog as catalog

BASE = os.environ.get("N8N_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("N8N_API_KEY")


def api(path, method="GET", payload=None, api_key=True, timeout=60):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=data, method=method)
    if api_key:
        request.add_header("X-N8N-API-KEY", API_KEY)
    request.add_header("Content-Type", "application/json")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                return json.loads(body.decode("utf-8")) if body else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {error.code}: {detail[:2000]}") from error
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def pg_node(name, query, replacements, credential, x, y):
    return {"parameters": {"operation": "executeQuery", "query": query,
            "options": {"queryReplacement": replacements}}, "id": secrets.token_hex(16), "name": name,
            "type": "n8n-nodes-base.postgres", "typeVersion": 2.6, "position": [x, y],
            "credentials": {"postgres": {"id": credential["id"], "name": credential["name"]}}}


def webhook(name, path, y):
    node_id = secrets.token_hex(16)
    return {"parameters": {"httpMethod": "POST", "path": path, "responseMode": "lastNode", "options": {}},
            "id": node_id, "name": name, "type": "n8n-nodes-base.webhook", "typeVersion": 2,
            "position": [100, y], "webhookId": node_id}


def first(result):
    return result[0] if isinstance(result, list) else result


def main():
    if not API_KEY or len(sys.argv) != 2:
        raise SystemExit("Usage: N8N_API_KEY=... wf_stage_catalog_via_n8n.py <csv>")
    path = Path(sys.argv[1])
    digest = catalog.checksum(path)
    credential = next(item for item in api("/api/v1/credentials").get("data", [])
                      if item.get("name") == "WhatsApp State PostgreSQL")
    prefix = "catalog-stage-" + secrets.token_hex(12)
    paths = {name: f"{prefix}-{name}" for name in ("begin", "chunk", "stats")}
    nodes = [webhook("Begin", paths["begin"], 100), webhook("Chunk", paths["chunk"], 300),
             webhook("Stats", paths["stats"], 500)]
    nodes += [
        pg_node("Begin SQL", "SELECT whatsapp_ai.begin_catalog_import($1,$2) AS import_id",
                "={{ [$json.body.checksum,$json.body.source] }}", credential, 400, 100),
        pg_node("Chunk SQL", """
          INSERT INTO whatsapp_ai.mann_vehicle_catalog(
            import_id,source_id,brand,model_series,engine,engine_codes,power_kw,power_bhp,
            displacement_ccm,fuel_type_raw,production_start,production_end,brand_norm,model_norm,engine_norm)
          SELECT $1::uuid,r.source_id,r.brand,r.model_series,r.engine,r.engine_codes,r.power_kw,r.power_bhp,
            r.displacement_ccm,r.fuel_type_raw,r.production_start,r.production_end,
            whatsapp_ai.norm_catalog_text(r.brand),whatsapp_ai.norm_catalog_text(r.model_series),whatsapp_ai.norm_catalog_text(r.engine)
          FROM jsonb_to_recordset($2::jsonb) AS r(source_id bigint,brand text,model_series text,engine text,
            engine_codes text[],power_kw integer,power_bhp integer,displacement_ccm integer,fuel_type_raw text,
            production_start integer,production_end integer)
          ON CONFLICT (import_id,source_id) DO UPDATE SET brand=excluded.brand,model_series=excluded.model_series,
            engine=excluded.engine,engine_codes=excluded.engine_codes,power_kw=excluded.power_kw,power_bhp=excluded.power_bhp,
            displacement_ccm=excluded.displacement_ccm,fuel_type_raw=excluded.fuel_type_raw,
            production_start=excluded.production_start,production_end=excluded.production_end,
            brand_norm=excluded.brand_norm,model_norm=excluded.model_norm,engine_norm=excluded.engine_norm
          RETURNING source_id
        """, "={{ [$json.body.importId,JSON.stringify($json.body.rows)] }}", credential, 400, 300),
        pg_node("Stats SQL", "SELECT whatsapp_ai.refresh_catalog_import_stats($1::uuid) AS result",
                "={{ [$json.body.importId] }}", credential, 400, 500),
    ]
    connections = {"Begin": {"main": [[{"node": "Begin SQL", "type": "main", "index": 0}]]},
                   "Chunk": {"main": [[{"node": "Chunk SQL", "type": "main", "index": 0}]]},
                   "Stats": {"main": [[{"node": "Stats SQL", "type": "main", "index": 0}]]}}
    created = api("/api/v1/workflows", "POST", {"name": "TEMP MANN Catalog Stage", "nodes": nodes,
                  "connections": connections, "settings": {"executionOrder": "v1", "timezone": "Europe/Istanbul"}})
    workflow_id = created["id"]
    try:
        api(f"/api/v1/workflows/{workflow_id}/activate", "POST", {})
        result = first(api(f"/webhook/{paths['begin']}", "POST", {"checksum": digest, "source": path.name}, False))
        import_id = result["import_id"]
        batch = []
        count = 0
        seen = set()
        for item in catalog.rows(path):
            vehicle_key = (item[1], item[2], item[3], tuple(item[4]), *item[5:])
            if vehicle_key in seen:
                continue
            seen.add(vehicle_key)
            staged = (len(seen), *item[1:])
            batch.append(dict(zip(("source_id","brand","model_series","engine","engine_codes","power_kw",
                "power_bhp","displacement_ccm","fuel_type_raw","production_start","production_end"), staged)))
            if len(batch) == 500:
                api(f"/webhook/{paths['chunk']}", "POST", {"importId": import_id, "rows": batch}, False, 120)
                count += len(batch); batch.clear()
        if batch:
            api(f"/webhook/{paths['chunk']}", "POST", {"importId": import_id, "rows": batch}, False, 120)
            count += len(batch)
        summary = first(api(f"/webhook/{paths['stats']}", "POST", {"importId": import_id}, False, 120))["result"]
        print(json.dumps({"checksum": digest, "sentRows": count, "summary": summary, "activated": False}))
    except Exception:
        executions = api(f"/api/v1/executions?workflowId={workflow_id}&status=error&limit=1&includeData=true")
        if executions.get("data"):
            execution = executions["data"][0]
            error = execution.get("data", {}).get("resultData", {}).get("error", {})
            print(json.dumps({"executionId": execution.get("id"), "error": error}, ensure_ascii=False), file=sys.stderr)
        raise
    finally:
        try: api(f"/api/v1/workflows/{workflow_id}/deactivate", "POST", {})
        finally: api(f"/api/v1/workflows/{workflow_id}", "DELETE")


if __name__ == "__main__":
    main()
