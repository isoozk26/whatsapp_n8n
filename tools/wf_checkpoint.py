#!/usr/bin/env python3
"""Tool: Checkpoint Tracker - CHECKPOINT durumunu takip eder"""
import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_FILE = ROOT / '.checkpoint_status.json'

DEFAULT_CHECKPOINTS = {
    "CP1": {
        "name": "KRITIK GUVENLIK - Hardcoded key kaldir",
        "status": "done",
        "items": [
            {"id": "1.1", "desc": "Evolution API key fallback kaldir", "status": "done"},
            {"id": "1.2", "desc": "workflow.json temizle", "status": "done"},
            {"id": "1.3", "desc": "workflow.json.backup sil", "status": "done"},
        ]
    },
    "CP2": {
        "name": "WEBHOOK GUVENLIGI",
        "status": "pending",
        "items": [
            {"id": "2.1", "desc": "Evolution API webhook secret ekle", "status": "pending"},
            {"id": "2.2", "desc": "n8n Webhook node auth ekle", "status": "pending"},
            {"id": "2.3", "desc": "Webhook secret n8n credential'a tasi", "status": "pending"},
        ]
    },
    "CP3": {
        "name": "HATA LOGLAMA",
        "status": "pending",
        "items": [
            {"id": "3.1", "desc": "parse_ai_output_js catch bloklarina console.error", "status": "pending"},
            {"id": "3.2", "desc": "finalize_batch_js catch bloklarina logging", "status": "pending"},
            {"id": "3.3", "desc": "batch_collector_js catch bloğuna logging", "status": "pending"},
        ]
    },
    "CP4": {
        "name": "MANUAL MODES BELLEK SIZINTISI",
        "status": "pending",
        "items": [
            {"id": "4.1", "desc": "_manualModes icin 24s TTL ekle", "status": "pending"},
            {"id": "4.2", "desc": "Batch silinirken _manualModes de sil", "status": "pending"},
            {"id": "4.3", "desc": "Contract test'e TTL dogrulama ekle", "status": "pending"},
        ]
    },
    "CP5": {
        "name": "RACE CONDITION KORUMASI",
        "status": "pending",
        "items": [
            {"id": "5.1", "desc": "processingToken atomik kilidi", "status": "pending"},
            {"id": "5.2", "desc": "splice/processing flag atomik blok", "status": "pending"},
            {"id": "5.3", "desc": "Race condition test senaryosu", "status": "pending"},
        ]
    },
}

def load_status():
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text(encoding='utf-8'))
    return DEFAULT_CHECKPOINTS

def save_status(status):
    CHECKPOINT_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding='utf-8')

def show_status():
    status = load_status()
    print(f"\n{'='*60}")
    print("CHECKPOINT DURUM RAPORU")
    print(f"{'='*60}")
    total_done = 0
    total_items = 0
    for cp_id, cp in status.items():
        done = sum(1 for i in cp['items'] if i['status'] == 'done')
        total = len(cp['items'])
        total_done += done
        total_items += total
        icon = '✅' if done == total else '⏳' if done > 0 else '⬜'
        print(f"  {icon} {cp_id}: {cp['name']} [{done}/{total}]")
        for item in cp['items']:
            item_icon = '✅' if item['status'] == 'done' else '⬜'
            print(f"      {item_icon} {item['id']}: {item['desc']}")
    print(f"\n  GENEL: {total_done}/{total_items} tamamlandi")
    print(f"{'='*60}\n")

def update_item(cp_id, item_id, new_status):
    status = load_status()
    if cp_id not in status:
        print(f"  HATA: {cp_id} bulunamadi")
        return False
    for item in status[cp_id]['items']:
        if item['id'] == item_id:
            item['status'] = new_status
            item['updated_at'] = datetime.now().isoformat()
            # CP statusunu guncelle
            all_done = all(i['status'] == 'done' for i in status[cp_id]['items'])
            any_done = any(i['status'] == 'done' for i in status[cp_id]['items'])
            status[cp_id]['status'] = 'done' if all_done else 'in_progress' if any_done else 'pending'
            save_status(status)
            print(f"  Guncellendi: {cp_id}.{item_id} -> {new_status}")
            return True
    print(f"  HATA: {item_id} bulunamadi")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_status()
    elif sys.argv[1] == 'update' and len(sys.argv) == 4:
        update_item(sys.argv[2], sys.argv[3], 'done')
    elif sys.argv[1] == 'reset':
        save_status(DEFAULT_CHECKPOINTS)
        print("  Checkpoint durumu sifirlandi")
    else:
        print("Kullanim:")
        print("  python wf_checkpoint.py              # Durumu goster")
        print("  python wf_checkpoint.py update CP1 1.1  # Item'i done isaretle")
        print("  python wf_checkpoint.py reset         # Sifirla")
