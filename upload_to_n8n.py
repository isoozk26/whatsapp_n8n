import urllib.request
import json
import ssl
import os

token = os.environ.get('N8N_API_KEY')
if not token:
    raise ValueError("N8N_API_KEY environment variable is required")

wf_id = os.environ.get("N8N_WORKFLOW_ID", "pW8YzDP44WpeJ6CJ")
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

# Read the current workflow before replacing its graph.
get_req = urllib.request.Request(url, method="GET")
get_req.add_header("X-N8N-API-KEY", token)
get_req.add_header("accept", "application/json")
try:
    with urllib.request.urlopen(get_req, context=context) as resp:
        live_workflow = json.loads(resp.read().decode("utf-8"))
except Exception as e:
    raise SystemExit(f"Live workflow state could not be read; deploy aborted: {e}")
live_was_active = live_workflow.get("active") is True

credentials_req = urllib.request.Request("https://n8n.filtreoto.online/api/v1/credentials", method="GET")
credentials_req.add_header("X-N8N-API-KEY", token)
credentials_req.add_header("accept", "application/json")
with urllib.request.urlopen(credentials_req, context=context) as response:
    credentials = json.loads(response.read().decode("utf-8")).get("data", [])
credential_ids = {item.get("name"): item.get("id") for item in credentials}
required_credentials = {"OpenAi account", "WhatsApp State PostgreSQL", "Evolution API"}
missing = sorted(required_credentials - set(credential_ids))
if missing:
    raise SystemExit("Deploy aborted; missing n8n credentials: " + ", ".join(missing))
for node in wf_data["nodes"]:
    for reference in (node.get("credentials") or {}).values():
        if reference.get("name") in credential_ids:
            reference["id"] = credential_ids[reference["name"]]

# Set name and exact allowed fields required by n8n PUT endpoint
payload = {
    "name": wf_data.get("name", "WhatsApp AI - v13 PostgreSQL Outbox"),
    "nodes": wf_data["nodes"],
    "connections": wf_data["connections"],
    "settings": wf_data.get("settings", {}),
    "staticData": wf_data.get("staticData", {})
}

req_body = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url, data=req_body, method="PUT")
req.add_header("X-N8N-API-KEY", token)
req.add_header("Content-Type", "application/json")
req.add_header("accept", "application/json")

print(f"Uploading PostgreSQL outbox workflow ({len(payload['nodes'])} nodes) to n8n server ({wf_id})...")
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
