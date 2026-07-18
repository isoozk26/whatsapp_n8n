#!/usr/bin/env python3
"""Tool: n8n Workflow Yukleme (Deploy) - Calisan SSL cozumu ile"""
import urllib.request
import json
import ssl
import sys
import os

TOKEN = os.environ.get('N8N_API_KEY')
if not TOKEN:
    raise ValueError("N8N_API_KEY environment variable is required")

WORKFLOW_ID = os.environ.get('N8N_WORKFLOW_ID', 'pW8YzDP44WpeJ6CJ')
N8N_URL = 'https://n8n.filtreoto.online'

def deploy(workflow_path='workflow.json'):
    create_mode = WORKFLOW_ID == 'create'
    url = f'{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}'
    # Use default SSL context (verification enabled)
    context = None  # Uses default SSL context with verification
    
    with open(workflow_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    
    # Settings filtreleme - n8n API sadece belirli alanlari kabul eder
    settings = {}
    if 'settings' in workflow and isinstance(workflow['settings'], dict):
        valid_keys = ['saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
                      'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder']
        for k in valid_keys:
            if k in workflow['settings']:
                settings[k] = workflow['settings'][k]
    
    live_was_active = True
    if not create_mode:
        get_req = urllib.request.Request(url, method='GET')
        get_req.add_header('X-N8N-API-KEY', TOKEN)
        get_req.add_header('accept', 'application/json')
        try:
            with urllib.request.urlopen(get_req, context=context) as response:
                live_workflow = json.loads(response.read().decode('utf-8'))
        except Exception as exc:
            print(f'  HATA: Canli workflow durumu okunamadi, deploy iptal: {exc}')
            return False
        live_was_active = live_workflow.get('active') is True
    credentials_req = urllib.request.Request(f'{N8N_URL}/api/v1/credentials', method='GET')
    credentials_req.add_header('X-N8N-API-KEY', TOKEN)
    credentials_req.add_header('accept', 'application/json')
    with urllib.request.urlopen(credentials_req, context=context) as response:
        credentials = json.loads(response.read().decode('utf-8')).get('data', [])
    credential_ids = {item.get('name'): item.get('id') for item in credentials}
    required = {'OpenAi account', 'WhatsApp State PostgreSQL', 'Evolution API'}
    missing = sorted(required - set(credential_ids))
    if missing:
        print('  HATA: Eksik n8n credentials: ' + ', '.join(missing))
        return False
    for node in workflow.get('nodes', []):
        for reference in (node.get('credentials') or {}).values():
            if reference.get('name') in credential_ids:
                reference['id'] = credential_ids[reference['name']]
    payload = {
        'name': workflow.get('name'),
        'nodes': workflow.get('nodes'),
        'connections': workflow.get('connections'),
        'settings': settings,
        'staticData': workflow.get('staticData', {})
    }
    
    req_data = json.dumps(payload).encode('utf-8')
    target_url = f'{N8N_URL}/api/v1/workflows' if create_mode else url
    req = urllib.request.Request(target_url, data=req_data, method='POST' if create_mode else 'PUT')
    req.add_header('X-N8N-API-KEY', TOKEN)
    req.add_header('Content-Type', 'application/json')
    req.add_header('accept', 'application/json')
    print(f'Yukleniyor: {workflow_path}')
    print(f'  Workflow: {workflow.get("name")}')
    print(f'  Node: {len(workflow.get("nodes", []))}')
    
    try:
        with urllib.request.urlopen(req, context=context) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            print(f'  BASARILI')
            print(f'  Active: {res_json.get("active")}')
            if create_mode:
                url = f'{N8N_URL}/api/v1/workflows/{res_json["id"]}'
                print(f'  Workflow ID: {res_json["id"]}')
        if live_was_active:
            for action in ('deactivate', 'activate'):
                action_req = urllib.request.Request(f'{url}/{action}', data=b'{}', method='POST')
                action_req.add_header('X-N8N-API-KEY', TOKEN)
                action_req.add_header('Content-Type', 'application/json')
                action_req.add_header('accept', 'application/json')
                with urllib.request.urlopen(action_req, context=context) as response:
                    published = json.loads(response.read().decode('utf-8'))
            if published.get('active') is not True:
                raise RuntimeError('Publish dogrulamasi basarisiz: active=true donmedi')
            print(f'  Published Version: {published.get("activeVersionId") or published.get("versionId")}')
        return True
    except urllib.error.HTTPError as he:
        print(f'  HATA {he.code}: {he.read().decode("utf-8")[:200]}')
        return False
    except Exception as e:
        print(f'  HATA: {e}')
        return False

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'workflow.json'
    ok = deploy(path)
    sys.exit(0 if ok else 1)
