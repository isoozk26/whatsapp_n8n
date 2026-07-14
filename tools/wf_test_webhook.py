#!/usr/bin/env python3
"""WhatsApp AI v10 - Webhook Test Betigi"""
import json
import os
import urllib.request
import ssl
import time
import uuid

DEFAULT_TOKEN = "F9a2Km7Qx8LpN3vB7jR5wY2tH6dK4mS"
WEBHOOK_URL = f"https://n8n.filtreoto.online/webhook/evolution-webhook?token={os.environ.get('WEBHOOK_TOKEN', DEFAULT_TOKEN)}"
# Use default SSL context (verification enabled)
context = None  # Uses default SSL context with verification

def send_webhook(message_text, sender_number="905331112233", sender_name="Test Musteri", from_me=False, message_id=None):
    if not message_id:
        message_id = str(uuid.uuid4())
    
    # n8n's Webhook node adds the outer `body` field. The HTTP request body
    # must match Evolution's event payload directly, without another wrapper.
    payload = {
        "data": {
            "key": {
                "remoteJid": f"{sender_number}@s.whatsapp.net",
                "fromMe": from_me,
                "id": message_id
            },
            "message": {
                "conversation": message_text
            },
            "pushName": sender_name
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(WEBHOOK_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(req, context=context, timeout=10) as resp:
            result = resp.read().decode("utf-8")
            print(f"  [OK] {resp.status} - {result[:100]}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  [HATA] {e.code} - {e.read().decode()[:100]}")
        return False
    except Exception as e:
        print(f"  [HATA] {e}")
        return False

def test_scenario(name, message, sender="905331112233", sname="Test Musteri", from_me=False):
    print(f"\n{'='*50}")
    print(f"TEST: {name}")
    print(f"  Mesaj: {message}")
    print(f"  Gonderen: {sname} ({sender})")
    print(f"  fromMe: {from_me}")
    print(f"{'='*50}")
    send_webhook(message, sender, sname, from_me)
    time.sleep(1)

# ═══════════════════════════════════════════════════
# TEST 1: Normal Musteri Mesaji
# ════════════════════════════════════════════════
test_scenario(
    "1. Normal Musteri Mesaji",
    "Merhaba, Renault Clio 2018 icin yag filtresi ariyorum",
    "905331112233", "Ahmet Yilmaz"
)

# ═════════════════════════════════════════════════
# TEST 2: Yonetici ++ Komutu
# ═══════════════════════════════════════════════
test_scenario(
    "2. Yonetici ++ Komutu (Manuel Mod)",
    "++",
    "905331112233", "Ahmet Yilmaz",
    from_me=True
)

# ════════════════════════════════════════════════
# TEST 3: Yonetici -- Komutu
# ══════════════════════════════════════════════
test_scenario(
    "3. Yonetici -- Komutu (Otomatik Mod)",
    "--",
    "905331112233", "Ahmet Yilmaz",
    from_me=True
)

# ════════════════════════════════════════════════
# TEST 4: Musteri ++ Yazar
# ══════════════════════════════════════════════
test_scenario(
    "4. Musteri ++ Yazar (Komut Degil)",
    "++",
    "905342223344", "Mehmet Kaya"
)

# ════════════════════════════════════════════════
# TEST 5: Coklu Mesaj (Batch Test)
# ═══════════════════════════════════════════════
print(f"\n{'='*50}")
print("TEST: 5. Coklu Mesaj (Batch Test)")
print("  3 mesaj 5 sn arayla gonderilecek")
print(f"{'='*50}")
for i, msg in enumerate(["Merhaba", "Fiat Egea 2021", "Yag filtresi ariyorum"], 1):
    print(f"  [{i}/3] {msg}")
    send_webhook(msg, "905355556666", "Ali Demir")
    time.sleep(2)

# ═════════════════════════════════════════════════
# TEST 6: Duplicate Webhook
# ════════════════════════════════════════════
test_id = str(uuid.uuid4())
print(f"\n{'='*50}")
print("TEST: 6. Duplicate Webhook")
print(f"  Ayni messageId: {test_id[:8]}...")
print(f"{'='*50}")
send_webhook("Test mesaji", "905367778888", "Fatma Yildiz", message_id=test_id)
time.sleep(1)
send_webhook("Ayni mesaj tekrar", "905367778888", "Fatma Yildiz", message_id=test_id)

# ════════════════════════════════════════════════
# TEST 7: Belirsiz Mesaj
# ═══════════════════════════════════════════════
test_scenario(
    "7. Belirsiz Mesaj (?)",
    "?",
    "905378889999", "Hasan Coskun"
)

# ═══════════════════════════════════════════════
# TEST 8: Fiyat Sorusu
# ═══════════════════════════════════════════════
test_scenario(
    "8. Fiyat Sorusu",
    "Fiat Egea 2021 icin yag filtresi fiyati ne kadar?",
    "905389990000", "Zeynep Kara"
)

# ═══════════════════════════════════════════════
# TEST 9: Sase Numarasi
# ═══════════════════════════════════════════════
test_scenario(
    "9. Sase Numarasi",
    "BMW 320d 2019 aracim var. Sase numaram WBAPL5105KA123456",
    "905391112222", "Ali Demir"
)

# ═══════════════════════════════════════════════
# TEST 10: Sikayet (Handoff)
# ══════════════════════════════════════════════
test_scenario(
    "10. Sikayet (Handoff Test)",
    "Siparisim hasarli geldi, iade etmek istiyorum",
    "905392223333", "Emre Tan"
)

print(f"\n{'='*50}")
print("TUM TESTLER GONDERILDI")
print("  n8n Executions bolumunden sonuclari kontrol edin")
print("  Phone A ve B'ye bildirim gelip gelmedigini kontrol edin")
print(f"{'='*50}")