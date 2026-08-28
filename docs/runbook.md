# WhatsApp AI — v13 PostgreSQL Outbox — GPT-5.4 Operasyon ve Kod Düzeltme Runbook'u

| Alan | Değer |
| --- | --- |
| Doküman sürümü | 4.5 (Kapsamlı Kod Düzeltme & Operasyon Sürümü) |
| Son güncelleme | 2026-08-28 |
| Sistem | FiltreOto WhatsApp AI |
| Hedef AI Modeli | OpenAI `gpt-5.4` / Codex `5.4` |
| Workflow Adı | `WhatsApp AI - v13 PostgreSQL Outbox` |
| Node Sayısı | 53 node / 45 connection source |
| Migrasyon Kapsamı | `001` → `070` (070 dahil) |
| Zaman Dilimi | `Europe/Istanbul` |
| Sahiplik | Cemal Hasan / FiltreOto |
| Canonical Konum | `docs/runbook.md` |

---

## İçindekiler

1. Amaç ve Kapsam
2. Mimari ve Kritik Akış Şeması
3. 53-Node Envanteri ve Sorumlulukları
4. Veri Katmanı (001 - 070 Migrasyonları)
5. Değişmez Kurallar (Non-Negotiables)
6. GPT-5.4 Model Parametreleri ve İstek Standartları
7. Release Gate ve Doğrulama Komut Zinciri
8. Canlı Deploy ve Veritabanı Doğrulama Prosedürü
9. Rollback Prosedürü
10. **GPT-5.4 / Codex 5.4 Detaylı Kod Düzeltme Görev Kartları (K-01'den K-14'e)**

---

## 1. Amaç ve Kapsam

Bu runbook, FiltreOto WhatsApp AI sisteminde tespit edilen tüm bot davranış, mantık, halüsinasyon, döngü ve hafıza kayıplarının **OpenAI gpt-5.4** ve **Codex 5.4** modelleri tarafından kod seviyesinde tek adımda deterministik olarak düzeltilmesi ve sistemin güvenle işletilmesi için hazırlanmıştır.

---

## 2. Mimari ve Kritik Akış Şeması

```text
[1. INBOUND / WEBHOOK HATTI]
Evolution API Webhook (POST /webhook/evolution-webhook?token=...)
  → Normalize Payload (Evolution v2 root.data & @lid normalizasyonu)
  → Validate Webhook Secret → Webhook Auth (401 → Respond Unauthorized)
  → Load Admin Filter Settings → Apply Admin Number Filter (fromMe ++/-- yetki kontrolü)
  → Valid Event? (messages.upsert filtresi)
  → Load Holiday Settings → Check Business Hours (Europe/Istanbul)
      ├─ Mesai Dışı → Claim OOH Notification → Is Off Hours?
      │     → Wait OOH 120 Seconds → Build OOH Messages → Send OOH to Customer
      │     → Enqueue Manager OOH Alert → Log OOH Event (customer_sent=true yalnız HTTP 200/201'de)
      └─ Rate Limit Exceeded? (202 → Respond Rate Limited)
  → Ingest Message (PostgreSQL ingest_message 8 argümanlı)
  → Respond Accepted (HTTP 202)

[2. WORKER / ASYNC AI İŞLEME HATTI (15s Schedule Trigger)]
Schedule Trigger (15s)
  → OpenAI Circuit Gate → OpenAI Circuit Open?
  → Claim Ready Batches (claim_ready_batches 10 limit, SKIP LOCKED)
  → Store Context (Chat memory + lastReplyText çıkarımı)
  → AI Agent (OpenAI gpt-5.4)
  → Parse AI Output (K-01'den K-14'e guardrail, duplicate reply guard, VIN retention, marka kontrolü)
  → AI Output Valid?
      ├─ Geçerli → Complete AI Batch → Persist Chat Memory
      └─ Geçersiz → Prepare AI Failure → Record AI Failure

[3. OUTBOX / TESLİMAT HATTI]
Evolution Circuit Gate → Evolution Circuit Open?
  → Claim Deliveries (claim_deliveries 20 limit)
  → Prepare Delivery (E.164 & @lid doğrulama)
  → Send Delivery (POST Evolution API /message/sendText)
  → Tag Delivery Success / Tag Delivery Error
  → Record Delivery Result (sent / failed / dead)
```

---

## 3. 53-Node Envanteri

1. `Webhook1` (n8n-nodes-base.webhook v2)
2. `Normalize Payload` (Code Node - Evolution v2 root.data & @lid)
3. `Valid Event?` (If Node - messages.upsert doğrulama)
4. `Validate Webhook Secret` (Code Node)
5. `Webhook Auth` (If Node)
6. `Respond Unauthorized` (Respond to Webhook 401)
7. `Load Admin Filter Settings` (PostgreSQL Node)
8. `Apply Admin Number Filter` (Code Node - Admin Number Authorization)
9. `Is Admin Number?` (If Node)
10. `Respond Admin Filtered` (Respond to Webhook 202)
11. `Load Holiday Settings` (PostgreSQL Node)
12. `Check Business Hours` (Code Node - Europe/Istanbul)
13. `Is Off Hours?` (If Node)
14. `Wait OOH 120 Seconds` (Wait Node)
15. `Claim OOH Notification` (PostgreSQL Node)
16. `OOH Claim Won?` (If Node)
17. `Build OOH Messages` (Code Node - E.164 Cleaned)
18. `Send OOH to Customer` (HTTP Request Node)
19. `Enqueue Manager OOH Alert` (PostgreSQL Node)
20. `Log OOH Event` (PostgreSQL Node - Dynamic HTTP Success Mapping)
21. `Rate Limit Exceeded?` (If Node)
22. `Respond Rate Limited` (Respond to Webhook 202)
23. `Ingest Message` (PostgreSQL Node - 8 Argümanlı)
24. `Respond Accepted` (Respond to Webhook 202)
25. `Prepare Ingest Failure` (Code Node)
26. `Respond 503` (Respond to Webhook 503)
27. `Schedule Trigger` (Schedule Trigger 15s)
28. `OpenAI Circuit Gate` (PostgreSQL Node)
29. `OpenAI Circuit Open?` (If Node)
30. `Claim Ready Batches` (PostgreSQL Node)
31. `Store Context` (Code Node)
32. `AI Agent` (OpenAI Agent - gpt-5.4)
33. `Parse AI Output` (Code Node - Guardrail, Duplicate Guard & Vehicle Check)
34. `AI Output Valid?` (If Node)
35. `Complete AI Batch` (PostgreSQL Node)
36. `AI Batch Completed?` (If Node)
37. `Persist Chat Memory` (PostgreSQL Node)
38. `Prepare AI Failure` (Code Node)
39. `Record AI Failure` (PostgreSQL Node)
40. `Evolution Circuit Gate` (PostgreSQL Node)
41. `Evolution Circuit Open?` (If Node)
42. `Claim Deliveries` (PostgreSQL Node)
43. `Prepare Delivery` (Code Node - E.164 & @lid Validation)
44. `Delivery Valid?` (If Node)
45. `Send Delivery` (HTTP Request Node - Evolution sendText)
46. `Tag Delivery Success` (Code Node)
47. `Tag Delivery Error` (Code Node)
48. `Tag Delivery Validation Error` (Code Node)
49. `Record Delivery Result` (PostgreSQL Node)
50. `Run Stale Batch Monitor` (PostgreSQL Node)
51. `Respond Ignored` (Respond to Webhook 202)
52. `OpenAI Chat Model1` (OpenAI Model Node - gpt-5.4)
53. `Simple In-Memory Vector Store` (n8n Vector Store Node)

---

## 4. Değişmez Kurallar (Non-Negotiables)

1. **Auth-Before-Ingest:** Veri tabanına kaydedilmeden önce webhook secret doğrulanmalıdır.
2. **Idempotency:** `message_id` bazlı çifte kayıt engellenmelidir.
3. **Manuel Mod Emniyeti:** Yalnızca tanımlı yöneticilerden gelen `fromMe` `++`/`--` komutları manuel modu değiştirebilir.
4. **Gizlilik:** Token, şifre ve telefon numaraları açıkta loglanamaz.
5. **Canlı Mesaj Gönderim Yasağı:** Testlerde gerçek kullanıcılara canlı mesaj atılamaz (`test_outbound_guard.py`).

---

## 5. GPT-5.4 Model Parametreleri ve İstek Standartları

- **Model Adı:** `gpt-5.4`
- **Sıcaklık (Temperature):** `0.1` (Deterministik yanıtlar ve sıfır hallucination).
- **Format:** `response_format: { type: "json_object" }` (Yalnızca şemaya uygun JSON çıktısı).
- **Prompt Sanitization:** Müşteri mesajlarındaki URL'ler ayıklanmalı, zararlı prompt injection girişimleri temizlenmelidir.

---

## 6. Release Gate ve Komut Zinciri

Codex 5.4 ile kod düzeltmeleri tamamlandıktan sonra sırasıyla şu komutlar çalıştırılmalıdır:

```bash
# 1. Workflow derleme ve JSON doğrulama
python build_workflow.py
python tools/wf_validate.py workflow.json

# 2. Sözleşme ve davranış testleri
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/test_ops_drift_check.py
python tools/test_outbound_guard.py
node tools/test_policy_engine.test.js

# 3. Güvenlik taraması
python tools/wf_security.py

# 4. Kalite Kapısı (Release Gate)
npm run release:gate
npm run test:mcp
```

---

## 10. GPT-5.4 / Codex 5.4 Detaylı Kod Düzeltme Görev Kartları

Aşağıdaki 14 görev kartı, GPT-5.4 / Codex 5.4 modelinin kod tabanındaki tüm anomalileri tek seferde düzeltebilmesi için hazırlanmış kesin uygulama talimatlarıdır:

---

### 📋 GÖREV KART K-01: Marka Kataloğunun Genişletilmesi
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L516)
- **Konum:** Satır ~516
- **Mevcut Durum:** `Suzuki`, `Mini`, `Subaru`, `BMW`, `Volvo`, `Mitsubishi`, `Jeep`, `Porsche` eksik olduğundan bu araçlar tanınamıyor ve fuzuli VIN isteniyordu.
- **Hedef Kod:**
  ```javascript
  const brands = ['Fiat','Renault','Ford','Volkswagen','VW','Opel','Peugeot','Citroen','Toyota','Honda','Hyundai','Kia','Mercedes','BMW','Audi','Skoda','Seat','Dacia','Nissan','Suzuki','Mini','Volvo','Mitsubishi','Subaru','Jeep','Porsche','Land Rover'];
  ```

---

### 📋 GÖREV KART K-02: Papağan Döngüsü Engeli (Duplicate Response Guard)
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L802)
- **Konum:** Satır ~802
- **Sorun:** Müşteriye 3 kez üst üste *"Sadece bu filtreyi mi istersiniz..."* soruluyordu.
- **Hedef Kod:**
  ```javascript
  const lastReplyText = String(ctx.lastReplyText || '').trim();
  if (reply.length > 0 && lastReplyText.length > 0 && reply === lastReplyText) {
    action = 'handoff';
    pauseAutomation = true;
    notifyAdmins = true;
    handoffReason = 'Tekrarlayan yanıt algılandı; temsilciye devredildi';
    replyStatus = 'handed_off';
  }
  ```

---

### 📋 GÖREV KART K-03: "Mesai mesai" SLA Typo Düzeltmesi
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L463)
- **Konum:** Satır ~463
- **Hedef Kod:**
  ```javascript
  const SLA_TEXT = 'mesai saatleri içinde';
  const SLA_LINE = isBusinessHours
    ? 'Mesai saatleri içinde dönüş yapacağız.'
    : 'Mesai dışındayız; talebiniz sıraya alındı, ilk iş saatinde dönüş yapılacak.';
  ```

---

### 📋 GÖREV KART K-04: Ingress Event Filtresi (`MESSAGES_UPSERT`)
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L89)
- **Konum:** Satır ~89 (`normalize_js`)
- **Hedef Kod:**
  ```javascript
  const eventType = String(root.event || root.body?.event || root.body?.body?.event || '');
  const isUpsert = !eventType || eventType === 'messages.upsert' || eventType === 'MESSAGES_UPSERT';
  const valid = Boolean(isUpsert && payload && messageId && senderNumber && !isGroup && !isBroadcast && !isProtocolMessage && !isEmpty && (!fromMe || command));
  ```

---

### 📋 GÖREV KART K-05: OOH HTTP 400 Cooldown Sızıntısı Engeli
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1289)
- **Konum:** Satır ~1289 (`Log OOH Event` postgres node)
- **Hedef Kod:**
  ```python
  postgres_node(
      "Log OOH Event",
      "UPDATE whatsapp_ai.ooh_log SET customer_sent = $2 WHERE id = $1::uuid RETURNING id",
      "={{ [ $('Build OOH Messages').item.json.oohLogId, Boolean(($('Send OOH to Customer').item.json.key || $('Send OOH to Customer').item.json.status === 'SENT' || $('Send OOH to Customer').item.json.status === 'PENDING') && !$('Send OOH to Customer').item.json.error && (!$('Send OOH to Customer').item.json.statusCode || $('Send OOH to Customer').item.json.statusCode < 400)) ] }}",
      [2540, 260],
  ),
  ```

---

### 📋 GÖREV KART K-06: OOH Adresleme ve Numara Temizliği (@lid)
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1000)
- **Konum:** Satır ~1000 (`build_ooh_messages_js`)
- **Hedef Kod:**
  ```javascript
  const senderNumberRaw = String(claim.senderNumber || ctx.senderNumber || '');
  const isLid = senderNumberRaw.toLowerCase().endsWith('@lid');
  const senderNumber = isLid
    ? senderNumberRaw.replace(/[^0-9@a-zA-Z._-]/g, '').replace(/@lid$/i, '@lid')
    : senderNumberRaw.replace(/@s\.whatsapp\.net$|@g\.us$/gi, '').replace(/[^0-9]/g, '');
  ```

---

### 📋 GÖREV KART K-07: Legacy Policy Engine Test Suite Düzeltmesi
- **Dosya:** [tools/test_policy_engine.test.js](file:///C:/ILAN/WHATSAPP_N8N/tools/test_policy_engine.test.js)
- **Hedef:** Test suite **62 PASSED / 0 FAILED** ile exit code 0 vermelidir.

---

### 📋 GÖREV KART K-08: Untracked Backup Klasörü Karantinası
- **Dosya:** [.gitignore](file:///C:/ILAN/WHATSAPP_N8N/.gitignore#L30)
- **Hedef Kod:** `.gitignore` dosyasına `postgresql_backup/` satırı eklenmelidir.

---

### 📋 GÖREV KART K-09: URL ve Web Linki Temizliği (URL Slug Sızıntısı Engeli)
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L444)
- **Sorun:** Müşteri ürün linki paylaştığında linkteki `srsltid=...` parametresi araç modeli sanılarak `"Toyota -gt86 srsltid..."` üretiliyordu.
- **Hedef Kod:**
  ```javascript
  const cleanVehicleText = vehicleSourceText.replace(/https?:\/\/[^\s]+/gi, ' ');
  ```

---

### 📋 GÖREV KART K-10: Olumsuz İfade Modellemesi ("Toyota gt86 değil" Filtresi)
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L521)
- **Sorun:** Müşteri `"Toyota değil"` dediğinde araç modeli `"Toyota değil 2."` oluyordu.
- **Hedef Kod:**
  ```javascript
  if (/\b(?:değil|degil|yok|olmayan)\b/i.test(modelPart)) {
    modelPart = '';
  }
  ```

---

### 📋 GÖREV KART K-11: Chat Memory'deki VIN'in Korunması
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L443)
- **Sorun:** Müşteri şasiyi (`WDB2100351A528399` veya `JF1SH5...`) önceden verdiği halde sonraki mesajlarda hafıza kaybolup tekrar şasi isteniyordu.
- **Hedef Kod:**
  ```javascript
  const vinMatch = vehicleSourceText.match(/\b([A-HJ-NPR-Z0-9]{17})\b/i);
  const detectedVin = vinMatch ? vinMatch[1].toUpperCase() : '';
  if (detectedVin && !entities.vehicles?.some(v => v.vin)) {
    if (!entities.vehicles) entities.vehicles = [];
    entities.vehicles.push({ vin: detectedVin, raw: detectedVin });
  }
  ```

---

### 📋 GÖREV KART K-12: Tam Parça Kodunda Fuzuli VIN Engeli
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L528)
- **Hedef Kod:**
  ```javascript
  if (detectedCodes.length > 0 && /\b(mevcut mu|var mı|fiyat|stok|kaç para|ne kadar)\b/i.test(plainText) && !/\b(uyar mı|uyumlu mu)\b/i.test(plainText)) {
    caseType = 'exact_code_price_stock';
    askVehicleInfo = false;
  }
  ```

---

### 📋 GÖREV KART K-13: Zaten Şasi Verilmişse Asla Tekrar Şasi İstememe Guard'ı
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L610)
- **Sorun (Murat Vakası):** Müşteri 2 kez `WDB2100351A528399` şasisini yazdığı halde bot 3 kez şasi istedi ve müşteri sistemi terk etti.
- **Hedef Kod:**
  ```javascript
  if (detectedVin || (Array.isArray(entities.vehicles) && entities.vehicles.some(v => v.vin && v.vin.length === 17))) {
    askVehicleInfo = false;
  }
  ```

---

### 📋 GÖREV KART K-14: Müşteri Terk / Vazgeçiş Algılama
- **Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L504)
- **Sorun:** Müşteri *"Tşk ederim iyi çalışmalar"* veya *"Kalsın istemiyorum"* yazdığında bot tekrar soru sormasın.
- **Hedef Kod:**
  ```javascript
  const isAbandonment = /\b(tşk ederim iyi çalışmalar|teşekkür ederim iyi çalışmalar|kalsın|istemiyorum|vazgeçtim|sağolun iyi çalışmalar)\b/i.test(plainText);
  if (isAbandonment) {
    action = 'reply';
    reply = 'Biz teşekkür eder, iyi çalışmalar dileriz. 🙏 İhtiyaç duyduğunuz her an buradayız.';
    pauseAutomation = true;
    notifyAdmins = false;
  }
  ```

---

> *İşbu runbook GPT-5.4 ve Codex 5.4 modellerinin kod tabanındaki tüm mantık, döngü, hafıza ve halüsinasyon hatalarını çözmesi için hazırlanmıştır.*
