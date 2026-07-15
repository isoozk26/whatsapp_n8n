import urllib.request
import json
import os

token = os.environ.get('N8N_API_KEY')
if not token:
    raise ValueError("N8N_API_KEY required")

wf_id = "g5UAfSi9bj7mRRCn"
url = f"https://n8n.filtreoto.online/api/v1/workflows/{wf_id}"
req = urllib.request.Request(url)
req.add_header("X-N8N-API-KEY", token)
req.add_header("accept", "application/json")

with urllib.request.urlopen(req, timeout=10) as r:
    wf = json.loads(r.read().decode())

sd = wf.get("staticData", {})
print(f"staticData keys: {list(sd.keys())}")
print(f"global keys: {list(sd.get('global', {}).keys())}")
print(f"_webhookSecret present: {'_webhookSecret' in sd.get('global', {})}")
if "_webhookSecret" in sd.get("global", {}):
    print(f"secret length: {len(sd['global']['_webhookSecret'])}")

nodes = [n.get("name") for n in wf.get("nodes", [])]
print(f"Node count: {len(nodes)}")
print(f"Has Webhook Auth Check: {'Webhook Auth Check' in nodes}")
print(f"Active: {wf.get('active')}")

# Check webhook node responseMode
for n in wf.get("nodes", []):
    if n.get("name") == "Webhook1":
        print(f"Webhook1 responseMode: {n.get('parameters', {}).get('responseMode')}")
