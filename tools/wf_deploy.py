#!/usr/bin/env python3
"""Tool: n8n Workflow Yukleme (Deploy) - Calisan SSL cozumu ile"""
import urllib.request
import json
import ssl
import sys

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxODdkNjMwOS1kY2I5LTRkNzYtOGVmOS1mOTMwYjZlYmZlNzMiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiYzYxYjY5ZjEtYTBiNS00NWYzLWI3MTYtYTdiNGFlZTM5Yjc3IiwiaWF0IjoxNzgzNjkwMTQ3LCJleHAiOjE3ODYyMzM2MDB9.wooyq2bNvJe4gxjVtr45tM_PAZ_R2SrmZhDWtcDqcY4'
WORKFLOW_ID = 'MbJkVXLDCOZ5umpp'
N8N_URL = 'https://n8n.filtreoto.online'

def deploy(workflow_path='workflow.json'):
    url = f'{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}'
    
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
    
    payload = {
        'name': workflow.get('name'),
        'nodes': workflow.get('nodes'),
        'connections': workflow.get('connections'),
        'settings': settings
    }
    
    req_data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=req_data, method='PUT')
    req.add_header('X-N8N-API-KEY', TOKEN)
    req.add_header('Content-Type', 'application/json')
    req.add_header('accept', 'application/json')
    context = ssl._create_unverified_context()
    
    print(f'Yukleniyor: {workflow_path}')
    print(f'  Workflow: {workflow.get("name")}')
    print(f'  Node: {len(workflow.get("nodes", []))}')
    
    try:
        with urllib.request.urlopen(req, context=context) as response:
            res_json = json.loads(response.read().decode('utf-8'))
            print(f'  BASARILI')
            print(f'  Active: {res_json.get("active")}')
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
