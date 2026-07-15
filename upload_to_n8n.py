import urllib.request
import json
import ssl
import os

token = os.environ.get('N8N_API_KEY')
if not token:
    raise ValueError("N8N_API_KEY environment variable is required")

wf_id = "g5UAfSi9bj7mRRCn"
url = f"https://n8n.filtreoto.online/api/v1/workflows/{wf_id}"
# Use default SSL context (verification enabled)
context = None  # Uses default SSL context with verification


def workflow_action(action):
    action_req = urllib.request.Request(f"{url}/{action}", data=b"{}", method="POST")
    action_req.add_header("X-N8N-API-KEY", token)
    action_req.add_header("Content-Type", "application/json")
    action_req.add_header("accept", "application/json")
    with urllib.request.urlopen(action_req, context=context) as response:
        return json.loads(response.read().decode("utf-8"))

with open("workflow.json", "r", encoding="utf-8") as f:
    wf_data = json.load(f)

# Preserve live workflow state (queued batches, manual modes, delivery ledger)
# across code-only deployments. Sending the freshly generated empty staticData
# would otherwise discard messages that are waiting to be processed.
get_req = urllib.request.Request(url, method="GET")
get_req.add_header("X-N8N-API-KEY", token)
get_req.add_header("accept", "application/json")
try:
    with urllib.request.urlopen(get_req, context=context) as resp:
        live_workflow = json.loads(resp.read().decode("utf-8"))
except Exception as e:
    raise SystemExit(f"Live workflow state could not be read; deploy aborted: {e}")
live_was_active = live_workflow.get("active") is True

# Ensure _webhookSecret exists in live staticData
live_static = live_workflow.get("staticData", {}) or {}
if "global" not in live_static:
    live_static["global"] = {}
if "_webhookSecret" not in live_static["global"]:
    live_static["global"]["_webhookSecret"] = os.environ.get('N8N_WEBHOOK_SECRET', 'F9a2Km7Qx8LpN3vB7jR5wY2tH6dK4mS')
    print(f"  Injected _webhookSecret into live staticData.global")

# Set name and exact allowed fields required by n8n PUT endpoint
payload = {
    "name": "WhatsApp AI - v12.5 Enterprise",
    "nodes": wf_data["nodes"],
    "connections": wf_data["connections"],
    "settings": wf_data.get("settings", {}),
    "staticData": live_static
}

req_body = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url, data=req_body, method="PUT")
req.add_header("X-N8N-API-KEY", token)
req.add_header("Content-Type", "application/json")
req.add_header("accept", "application/json")

print(f"Uploading v12.5 Enterprise ({len(payload['nodes'])} nodes) to n8n server ({wf_id})...")
try:
    with urllib.request.urlopen(req, context=context) as resp:
        res_json = json.loads(resp.read().decode("utf-8"))
        print("SUCCESS! Workflow updated on live server:")
        print("  ID:", res_json.get("id"))
        print("  Name:", res_json.get("name"))
        print("  Active:", res_json.get("active"))
        print("  Updated At:", res_json.get("updatedAt"))
    if live_was_active:
        workflow_action("deactivate")
        published = workflow_action("activate")
        if published.get("active") is not True:
            raise RuntimeError("Workflow publish dogrulama basarisiz: active=true donmedi")
        print("  Published Active Version:", published.get("activeVersionId") or published.get("versionId"))
except urllib.error.HTTPError as he:
    raise SystemExit(f"HTTP Error {he.code}: {he.reason}; Detail: {he.read().decode('utf-8')}")
except Exception as e:
    raise SystemExit(f"Upload Failed: {e}")