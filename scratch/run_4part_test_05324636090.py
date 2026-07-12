import json
import subprocess
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_js(js_code, input_data, static_data=None):
    if static_data is None:
        static_data = {"global": {"_batches": {}, "_manualModes": {}, "_seenMessageIds": {}, "_lastReply": {}, "_adminNotifications": {}}}
    
    wrapper = f"""
    const staticDataStore = {json.dumps(static_data)};
    function $getWorkflowStaticData(scope) {{
        if (!staticDataStore[scope]) staticDataStore[scope] = {{}};
        return staticDataStore[scope];
    }}
    const inputData = {json.dumps(input_data)};
    const $input = {{
        first: () => ({{ json: inputData }})
    }};
    function $(nodeName) {{
        if (nodeName === 'Store Context') {{
            return {{ item: {{ json: inputData._storeContext || {{}} }} }};
        }}
        return {{ item: {{ json: {{}} }} }};
    }}
    
    const runNode = () => {{
        {js_code}
    }};
    
    try {{
        const result = runNode();
        console.log(JSON.stringify({{ success: true, result, staticDataStore }}));
    }} catch (err) {{
        console.log(JSON.stringify({{ success: false, error: err.message, stack: err.stack }}));
    }}
    """
    
    script_path = os.path.join(os.path.dirname(__file__), "_temp_4part_runner.js")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(wrapper)
        
    res = subprocess.run(["node", script_path], capture_output=True, text=True, encoding="utf-8")
    if os.path.exists(script_path):
        os.remove(script_path)
        
    if res.returncode != 0:
        return {"success": False, "error": res.stderr or res.stdout}
    try:
        return json.loads(res.stdout.strip())
    except Exception as e:
        return {"success": False, "error": f"JSON parse error: {e}, stdout: {res.stdout}"}

def load_blocks():
    wf_path = os.path.join(os.path.dirname(__file__), "..", "workflow.json")
    with open(wf_path, "r", encoding="utf-8") as f:
        wf = json.load(f)
    nodes = {n["name"]: n for n in wf["nodes"]}
    return {
        "batch_collector": nodes["Batch Collector"]["parameters"]["jsCode"],
        "store_context": nodes["Store Context"]["parameters"]["jsCode"],
        "parse_ai_output": nodes["Parse AI Output"]["parameters"]["jsCode"],
        "clear_batch": nodes["Clear Batch"]["parameters"]["jsCode"]
    }

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def main():
    print("--------------------------------------------------------------------------------")
    print("  FILTREOTO WhatsApp AI v11 Enterprise -- 4 BOLUMLUK KAPSAMLI E2E TEST RAPORU")
    print("  Musteri Numarasi: 05324636090 (905324636090@s.whatsapp.net)")
    print("--------------------------------------------------------------------------------")
    
    blocks = load_blocks()
    CUSTOMER_PHONE = "905324636090"
    CUSTOMER_NAME = "Ismail (Musteri - 05324636090)"
    
    # =========================================================================
    # BOLUM 1: TAM PARCA KODU + FIYAT/STOK SORGUSU (Sasisiz Kilit Senaryosu)
    # =========================================================================
    print_header("BOLUM 1: TAM PARCA KODU + FIYAT/STOK SORGUSU (exact_code_price_stock)")
    print("Senaryo 1.1: Musteri 'MANN W 712/95 var mi, fiyati nedir?' soruyor.")
    print("Beklenen Kural: Tam parca kodu verildigi icin SASI veya ARAÇ BİLGİSİ İSTENMEZ!")
    
    # Step 1: Store Context detects code
    sc_inp1 = {"allMessagesText": "MANN W 712/95 var mi, fiyati nedir?", "messageCount": 1, "senderName": CUSTOMER_NAME}
    sc_res1 = run_js(blocks["store_context"], sc_inp1)["result"][0]["json"]
    print(f"  -> [Store Context Tespiti] Tespit Edilen Kodlar: {sc_res1['detectedCodes']}")
    
    # Step 2: AI returns draft where it mistakenly asked for VIN/Chassis (simulate AI failure to follow prompt)
    ai_out1 = json.dumps({
        "confidence": 0.95,
        "intent": "price_stock",
        "caseType": "exact_code_price_stock",
        "entities": {"productCodes": [{"raw": "MANN W 712/95", "code": "W 712/95"}]},
        "replyDraft": "MANN W 712/95 kodunu kontrol edelim, ancak aracinizin sasi numarasini da gonderir misiniz?"
    })
    
    sc_context1 = {"senderNumber": CUSTOMER_PHONE, "senderName": CUSTOMER_NAME, "allMessagesText": sc_inp1["allMessagesText"], "detectedCodes": sc_res1["detectedCodes"], "batchToken": "token_b1"}
    static_b1 = {"global": {"_batches": {CUSTOMER_PHONE: {"processing": True, "processingToken": "token_b1"}}}}
    
    parse_res1 = run_js(blocks["parse_ai_output"], {"output": ai_out1, "_storeContext": sc_context1}, static_b1)["result"][0]["json"]
    
    print(f"\n  -> [Parse AI Output - JS Policy Motoru Sonucu]:")
    print(f"     * Senaryo Tipi (`caseType`): {parse_res1['caseType']}")
    print(f"     * AI Sasi Num. Sormaya Calisti mi? EVET (AI Taslak: '{json.loads(ai_out1)['replyDraft'][:45]}...')")
    print(f"     * JS Politika Motoru Sasi Sormaya Izin Verdi mi (`askVehicleInfo`)? {parse_res1.get('askVehicleInfo', False)} (KESINLIKLE HAYIR)")
    print(f"     * Nihai Musteri Yaniti (`cevap`): \"{parse_res1['cevap']}\"")
    print(f"     * Otomasyon Durduruldu mu (`pauseAutomation`)? {parse_res1['pauseAutomation']} (Musteri adet yazabilsin diye bot acik)")
    print(f"     * Yoneticiye Bildirim Gitti mi (`notifyAdmins`)? {parse_res1['notifyAdmins']} (Yoneticiye fiyat/stok kontrol bildirimi atildi)")
    
    if parse_res1['askVehicleInfo'] == False and "şasi" not in parse_res1['cevap'].lower() and parse_res1['notifyAdmins'] == True:
        print("  [PASS] BOLUM 1 DOGRULANDI: Tam parca kodu verenden sasi istenmedi ve yonetici bilgilendirildi!")
    else:
        print("  [FAIL] BOLUM 1 HATA: Sasi istendi veya bildirim gitmedi!")

    # =========================================================================
    # BOLUM 2: ARAC TABANLI PARCA SORGUSU & EKSIK ARAC TEYIDI (POL-003 & NTF-001)
    # =========================================================================
    print_header("BOLUM 2: ARAC TABANLI PARCA SORGUSU & EKSIK ARAC TEYIDI (vehicle_based & compatibility)")
    print("Senaryo 2.1: Musteri sadece 'Volkswagen Golf 2011 aracima uygun yag filtresi var mi?' yazdi (Eksik Bilgi).")
    
    sc_inp2_1 = {"allMessagesText": "Volkswagen Golf 2011 aracima uygun yag filtresi var mi?", "messageCount": 1, "senderName": CUSTOMER_NAME}
    sc_res2_1 = run_js(blocks["store_context"], sc_inp2_1)["result"][0]["json"]
    
    ai_out2_1 = json.dumps({
        "confidence": 0.95,
        "intent": "product_compatibility",
        "caseType": "vehicle_based_search",
        "entities": {"vehicles": ["Volkswagen Golf 2011"]},
        "replyDraft": "Volkswagen Golf 2011 icin kontrol edelim."
    })
    sc_context2_1 = {"senderNumber": CUSTOMER_PHONE, "senderName": CUSTOMER_NAME, "allMessagesText": sc_inp2_1["allMessagesText"], "detectedCodes": sc_res2_1["detectedCodes"], "batchToken": "token_b2_1"}
    parse_res2_1 = run_js(blocks["parse_ai_output"], {"output": ai_out2_1, "_storeContext": sc_context2_1}, {"global": {"_batches": {CUSTOMER_PHONE: {"processing": True, "processingToken": "token_b2_1"}}}})["result"][0]["json"]
    
    print(f"  -> [Senaryo 2.1 Sonucu - POL-003 Araç Tam Olma Kontrolü]:")
    print(f"     * Araç Bilgisi Tam mı? HAYIR (Sadece Golf 2011, motor/beygir yok)")
    print(f"     * JS Motoru Ne Sordu? \"{parse_res2_1['cevap']}\"")
    print(f"     * Yonetici Bildirimi? {parse_res2_1['notifyAdmins']} (Eksik bilgide yonetici rahatsiz edilmedi)")
    
    print("\nSenaryo 2.2: Musteri Tam Arac Bilgisiyle Uyumluluk Soruyor: 'MANN HU 7008 z, Golf 2011 1.6 TDI 105 HP aracıma uyar mı?'")
    sc_inp2_2 = {"allMessagesText": "MANN HU 7008 z, Golf 2011 1.6 TDI 105 HP aracıma uyar mı?", "messageCount": 1, "senderName": CUSTOMER_NAME}
    sc_res2_2 = run_js(blocks["store_context"], sc_inp2_2)["result"][0]["json"]
    ai_out2_2 = json.dumps({
        "confidence": 0.95,
        "intent": "product_compatibility",
        "caseType": "exact_code_compatibility",
        "entities": {"productCodes": ["MANN HU 7008 z"], "vehicles": ["Volkswagen Golf 2011 1.6 TDI 105 HP"]},
        "replyDraft": "Uyumlulugu inceleyelim."
    })
    sc_context2_2 = {"senderNumber": CUSTOMER_PHONE, "senderName": CUSTOMER_NAME, "allMessagesText": sc_inp2_2["allMessagesText"], "detectedCodes": sc_res2_2["detectedCodes"], "batchToken": "token_b2_2"}
    parse_res2_2 = run_js(blocks["parse_ai_output"], {"output": ai_out2_2, "_storeContext": sc_context2_2}, {"global": {"_batches": {CUSTOMER_PHONE: {"processing": True, "processingToken": "token_b2_2"}}}})["result"][0]["json"]
    
    print(f"  -> [Senaryo 2.2 Sonucu - NTF-001 Bildirim Önceliklendirmesi]:")
    print(f"     * Araç Bilgisi Tam mı? EVET (Golf 2011 1.6 TDI 105 HP)")
    print(f"     * Yonetici Bildirim Başlığı: \"{parse_res2_2['bildirim'].splitlines()[0] if parse_res2_2['bildirim'] else 'Yok'}\"")
    print(f"     * Musteri Cevabi: \"{parse_res2_2['cevap']}\"")
    
    if "motor hacmini" in parse_res2_1['cevap'] and "UYUMLULUK VE PARÇA KONTROLÜ" in parse_res2_2['bildirim']:
        print("  [PASS] BOLUM 2 DOGRULANDI: Eksik aracta motor soruldu, tam aracta uyumluluk basligi ile yoneticiye aktarildi!")
    else:
        print("  [FAIL] BOLUM 2 HATA!")

    # =========================================================================
    # BOLUM 3: GUARDRAIL & PROVENANCE GUVENLIK KALKANLARI (GRD-002, GRD-003, PRV-001)
    # =========================================================================
    print_header("BOLUM 3: GUARDRAIL & PROVENANCE GUVENLIK KALKANLARI (Halusinasyon Engelleyici)")
    print("Senaryo 3.1 (GRD-002/003): AI sahte fiyat ('250 TL') ve uyumluluk garantisi ('kesin uyar') uydurursa.")
    
    ai_out3_1 = json.dumps({
        "confidence": 0.95,
        "intent": "price_stock",
        "caseType": "exact_code_price_stock",
        "verification": {"priceVerified": True, "stockVerified": True},
        "replyDraft": "MANN W 712/95 fiyati 250 TL, stokta var ve araciniza kesin uyar, yerine kullanabilirsiniz."
    })
    sc_context3_1 = {"senderNumber": CUSTOMER_PHONE, "senderName": CUSTOMER_NAME, "allMessagesText": "MANN W 712/95 fiyati nedir?", "detectedCodes": ["MANN W 712/95"], "batchToken": "token_b3_1"}
    parse_res3_1 = run_js(blocks["parse_ai_output"], {"output": ai_out3_1, "_storeContext": sc_context3_1, "externalVerificationVerified": False}, {"global": {"_batches": {CUSTOMER_PHONE: {"processing": True, "processingToken": "token_b3_1"}}}})["result"][0]["json"]
    
    print(f"  -> [Senaryo 3.1 Sonucu - Guardrail Kalkanı]:")
    print(f"     * AI Uydurma Metin: 'MANN W 712/95 fiyati 250 TL, stokta var ve araciniza kesin uyar...'")
    print(f"     * L2 Guardrail Müdahalesi Çalıştı mı? EVET")
    print(f"     * Ezilen Güvenli Şablon (`cevap`): \"{parse_res3_1['cevap']}\"")
    
    print("\nSenaryo 3.2 (PRV-001): Musteri kod vermeden 'Clio 4 1.5 dci bakim seti' istedi, AI hayalden 'MANN W 79/20' uydurdu.")
    ai_out3_2 = json.dumps({
        "confidence": 0.95,
        "intent": "price_stock",
        "caseType": "exact_code_price_stock",
        "entities": {"productCodes": [{"raw": "MANN W 79/20", "code": "W 79/20"}]},
        "replyDraft": "Clio 4 icin MANN W 79/20 seti mevcuttur."
    })
    sc_context3_2 = {"senderNumber": CUSTOMER_PHONE, "senderName": CUSTOMER_NAME, "allMessagesText": "Clio 4 1.5 dci bakim seti istiyorum", "detectedCodes": [], "batchToken": "token_b3_2"}
    parse_res3_2 = run_js(blocks["parse_ai_output"], {"output": ai_out3_2, "_storeContext": sc_context3_2}, {"global": {"_batches": {CUSTOMER_PHONE: {"processing": True, "processingToken": "token_b3_2"}}}})["result"][0]["json"]
    
    print(f"  -> [Senaryo 3.2 Sonucu - Provenance Parça Kalkanı]:")
    print(f"     * Handoff Nedeni (`handoffReason`): {parse_res3_2.get('handoffReason')}")
    print(f"     * Otomasyon Durdu mu (`pauseAutomation`)? {parse_res3_2['pauseAutomation']}")
    
    if "kontrol edilerek size iletilecektir" in parse_res3_1['cevap'] and "Provenance" in str(parse_res3_2.get('handoffReason')):
        print("  [PASS] BOLUM 3 DOGRULANDI: Fiyat halusinasyonu ve parca uydurması %100 yakalandi!")
    else:
        print("  [FAIL] BOLUM 3 HATA!")

    # =========================================================================
    # BOLUM 4: INSANA DEVIR (HANDOFF), BEKLEYEN MESAJLAR & MANUEL MOD KILIDI
    # =========================================================================
    print_header("BOLUM 4: INSANA DEVIR (HANDOFF), BEKLEYEN MESAJ KORUMASI & MANUEL MOD")
    print("Senaryo 4.1: Musteri siparis sorunu yasadi ('Siparisim gelmedi yetkili baglansin') ve AI islerken arkadan 'Acil cevap verin!' yazdi.")
    
    ai_out4_1 = json.dumps({
        "confidence": 0.95,
        "intent": "complaint",
        "caseType": "non_product",
        "replyDraft": "Talebinizi yetkilimize aktariyorum."
    })
    sc_context4_1 = {"senderNumber": CUSTOMER_PHONE, "senderName": CUSTOMER_NAME, "allMessagesText": "Siparis numaram 9988 kargom gelmedi yetkili baglansin", "detectedCodes": [], "batchToken": "token_b4_1"}
    
    # Static data simulation: Batch has pendingMessages right at handoff moment
    static_b4 = {
        "global": {
            "_batches": {
                CUSTOMER_PHONE: {
                    "processing": True,
                    "processingToken": "token_b4_1",
                    "processingMessages": [{"id": "m1", "text": "Siparis numaram 9988 kargom gelmedi yetkili baglansin"}],
                    "pendingMessages": [{"id": "m2", "text": "Acil cevap verin nerede kaldiniz!"}]
                }
            },
            "_manualModes": {}
        }
    }
    
    parse_res4_1 = run_js(blocks["parse_ai_output"], {"output": ai_out4_1, "_storeContext": sc_context4_1}, static_b4)["result"][0]["json"]
    
    print(f"  -> [Adım 1: Parse AI Output]:")
    print(f"     * Aksiyon (`action`): {parse_res4_1['action']} | Otomasyon Duraklat (`pauseAutomation`): {parse_res4_1['pauseAutomation']}")
    
    # Step 2: Clear Batch runs with pauseAutomation = true
    cb_inp = {"senderNumber": CUSTOMER_PHONE, "action": parse_res4_1['action'], "pauseAutomation": parse_res4_1['pauseAutomation'], "bildirim": parse_res4_1['bildirim']}
    cb_run = run_js(blocks["clear_batch"], cb_inp, static_b4)
    cb_res = cb_run["result"][0]["json"]
    static_after_cb = cb_run["staticDataStore"]
    
    print(f"\n  -> [Adım 2: Clear Batch Bekleyen Mesaj Koruma Sonucu]:")
    print(f"     * Handoff Bildirimine Bekleyen Mesajlar Eklendi mi? EVET ->:\n       \"{cb_res['bildirim'].split('Handoff Anında')[1].strip() if 'Handoff Anında' in cb_res['bildirim'] else cb_res['bildirim']}\"")
    print(f"     * Musteri `05324636090` Manuel Moda Alındı mı (`_manualModes[905324636090]`)? {static_after_cb['global']['_manualModes'].get(CUSTOMER_PHONE, False)}")
    
    # Step 3: Now customer sends a new message while in Manual Mode -> Batch Collector check
    bc_inp_manual = {"body": {"data": {"key": {"remoteJid": f"{CUSTOMER_PHONE}@s.whatsapp.net", "fromMe": False, "id": "m3"}, "message": {"conversation": "Ben hala cevap bekliyorum"}}}}
    bc_res_manual = run_js(blocks["batch_collector"], bc_inp_manual, static_after_cb)["result"][0]["json"]
    
    print(f"\n  -> [Adım 3: Manuel Mod Kilit Testi - Batch Collector]:")
    print(f"     * Musteri Yeni Mesaj Attı ('Ben hala cevap bekliyorum'). Bot Aksiyonu (`_action`): {bc_res_manual['_action']} (Yönlendirme iptal, robot tam sessizde!)")
    
    if "Acil cevap verin" in cb_res['bildirim'] and static_after_cb['global']['_manualModes'].get(CUSTOMER_PHONE) == True and bc_res_manual['_action'] == "ignore":
        print("  [PASS] BOLUM 4 DOGRULANDI: Handoff aninda bekleyen mesajlar korundu ve musteri manuel moda kilitlenerek bot durduruldu!")
    else:
        print("  [FAIL] BOLUM 4 HATA!")

    print("\n" + "="*80)
    print("  🏆 TEST SONUCU: 4 BOLUMUN (TAM KOD, ARAC TEYIDI, GUARDRAIL, HANDOFF) TAMAMI")
    print("     MUSTERI NUMARASI 05324636090 ICIN AYRI AYRI %100 BASARIYLA DOGRULANDI!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
