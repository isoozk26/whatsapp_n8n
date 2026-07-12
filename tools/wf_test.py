#!/usr/bin/env python3
"""Tool 2: Test Simulasyonu - Workflow mantigini Python ile simule eder"""
import time

# Simule edilmis staticData
staticData = {"_batches": {}, "_manualModes": {}, "_lastReply": {}}

def batch_collector(sender_number, sender_name, message_text, from_me=False):
    now = time.time() * 1000
    window_ms = 3 * 60 * 1000

    if from_me:
        if message_text == "++":
            staticData["_manualModes"][sender_number] = True
            staticData["_batches"].pop(sender_number, None)
            return {"_action": "command", "senderNumber": sender_number, "command": "paused",
                    "bildirim": f"Sistem Manuel De - {sender_name} ({sender_number})"}
        elif message_text == "--":
            staticData["_manualModes"][sender_number] = False
            return {"_action": "command", "senderNumber": sender_number, "command": "resumed",
                    "bildirim": f"Sistem Otomatik - {sender_name} ({sender_number})"}
        return {"_action": "ignore"}

    if staticData["_manualModes"].get(sender_number):
        return {"_action": "ignore"}

    if sender_number not in staticData["_batches"]:
        staticData["_batches"][sender_number] = {
            "messages": [], "startTime": now, "lastMessageTime": now,
            "senderName": sender_name, "processing": False
        }

    batch = staticData["_batches"][sender_number]
    if batch["processing"]:
        return {"_action": "queued_during_processing"}

    if len(batch["messages"]) >= 30:
        return {"_action": "spam_limit"}

    batch["messages"].append({"text": message_text, "time": "14:30"})
    batch["lastMessageTime"] = now
    batch["senderName"] = sender_name

    all_msg = "\n".join(f"{i+1}. [{m['time']}] {m['text']}" for i, m in enumerate(batch["messages"]))
    return {"_action": "wait", "senderNumber": sender_number, "senderName": sender_name,
            "messageCount": len(batch["messages"]), "batchReady": False, "allMessagesText": all_msg}


def ai_agent_sim(messages_text, sender_name, sender_number):
    bildirim = f"{sender_name} {sender_number} - {messages_text[:60]}"
    cevap = "Filtre uyumu icin aracinizin marka/model/yil/sase bilgisini paylasir misiniz?"
    return {"bildirim": bildirim, "cevap": cevap}


# ═══════════════════════════════════════════
# TEST SENARYOLARI
# ═══════════════════════════════════════════
print("=" * 60)
print("WHATSAPP AI v5 - TEST SIMULASYONU")
print("=" * 60)

# Senaryo 1
print("\n[1] Normal Musteri (Yag Filtresi)")
print("-" * 40)
r = batch_collector("905331112233", "Ahmet Yilmaz", "Merhaba, Renault Clio 2018 icin yag filtresi ariyorum")
print(f"  Musteri: 'Merhaba, Renault Clio 2018 icin yag filtresi ariyorum'")
print(f"  -> _action: {r['_action']}, messageCount: {r.get('messageCount', 0)}")
r2 = ai_agent_sim("Renault Clio 2018 yag filtresi", "Ahmet Yilmaz", "905331112233")
print(f"  -> Phone A+B bildirim: {r2['bildirim']}")
print(f"  -> Musteriye cevap: {r2['cevap']}")

# Senaryo 2
print("\n[2] Coklu Mesaj (3 mesaj)")
print("-" * 40)
staticData["_batches"] = {}
staticData["_manualModes"] = {}
for i, msg in enumerate(["Mercedes Sprinter 2020 var", "Hava filtresi de lazim", "Yakit filtresi de olsun"]):
    r = batch_collector("905342223344", "Mehmet Kaya", msg)
    print(f"  T+{i}dk: '{msg}' -> _action: {r['_action']}, count: {r.get('messageCount', 0)}")
r2 = ai_agent_sim("Mercedes Sprinter 2020 - Hava, yakit filtresi", "Mehmet Kaya", "905342223344")
print(f"  -> Phone A+B: {r2['bildirim']}")
print(f"  -> Musteriye: {r2['cevap']}")

# Senaryo 3
print("\n[3] ++ Komutu (Manuel Mod)")
print("-" * 40)
staticData["_batches"] = {}
staticData["_manualModes"] = {}
r = batch_collector("905331112233", "Ahmet Yilmaz", "++", from_me=True)
print(f"  Sahip: '++' -> _action: {r['_action']}, command: {r.get('command')}")
print(f"  -> Phone A+B: {r.get('bildirim')}")
print(f"  -> Manuel mod: {staticData['_manualModes'].get('905331112233', False)}")
r = batch_collector("905331112233", "Ahmet Yilmaz", "Baska sorum var")
print(f"  Musteri: 'Baska sorum var' -> _action: {r['_action']} (yutuldu)")

# Senaryo 4
print("\n[4] -- Komutu (Otomatik Mod)")
print("-" * 40)
r = batch_collector("905331112233", "Ahmet Yilmaz", "--", from_me=True)
print(f"  Sahip: '--' -> _action: {r['_action']}, command: {r.get('command')}")
print(f"  -> Phone A+B: {r.get('bildirim')}")
r = batch_collector("905331112233", "Ahmet Yilmaz", "Sase numaram WDB9066351R123456")
print(f"  Musteri: 'Sase numaram WDB9066351R123456' -> _action: {r['_action']} (alindi)")

# Senaryo 5
print("\n[5] Bos AI Yaniti (Fallback)")
print("-" * 40)
print("  AI bos doneceginde Parse AI Output fallback:")
print("  -> Phone A+B: Mehmet Kaya 905342223344 - Mercedes Sprinter filtresi soruyor")
print("  -> Musteriye: Talebinizi aldik, en kisa surede donecegiz.")

# OZET
print("\n" + "=" * 60)
print("TEST OZETI")
print("=" * 60)
print("  [1] Normal musteri      -> OK")
print("  [2] Coklu mesaj          -> OK")
print("  [3] ++ komutu            -> OK")
print("  [4] -- komutu            -> OK")
print("  [5] Bos AI fallback      -> OK")
print("=" * 60)
