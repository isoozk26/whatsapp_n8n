# WhatsApp AI — v13 PostgreSQL Outbox — GPT-5.4 Operasyon & Codex Düzeltme Runbook

| Alan | Değer |
| --- | --- |
| Doküman sürümü | 4.2 |
| Son güncelleme | 2026-08-28 |
| Sistem | FiltreOto WhatsApp AI |
| AI Modeli | OpenAI `gpt-5.4` / Codex `5.4` |
| Workflow | `WhatsApp AI - v13 PostgreSQL Outbox` |
| Node sayısı | 53 node / 45 connection source |
| Migration kapsamı | `001` → `070` (070 dahil) |
| Timezone | `Europe/Istanbul` |
| Sahiplik | Cemal Hasan / FiltreOto |
| Canonical konum | `docs/runbook.md` |

---

## İçindekiler

1. Amaç ve kapsam
2. Mimari ve akış
3. Node envanteri
4. Veri katmanı (şema, fonksiyonlar, ayarlar)
5. Konfigürasyon (credential, env, secret)
6. Değişmez kurallar (Non-negotiables)
7. Release gate ve komut zinciri
8. Deploy ve doğrulama prosedürü
9. Rollback prosedürü
10. Codex 5.4 Kod Düzeltme Görev Kartları ve Uygulama Rehberi (K-01'den K-14'e)

---

## 1. Amaç ve kapsam

Bu runbook, FiltreOto WhatsApp AI sisteminin OpenAI **gpt-5.4** ve **Codex 5.4** ile **kod düzeltmesi, günlük işletimi, release süreci ve olay müdahalesi** adımlarını detaylandırır.

---

## 2. Mimari ve akış

### Kritik Akış Şeması
```text
[Inbound / Webhook Yolu]
Evolution webhook (POST /webhook/evolution-webhook?token=...)
  → Validate Webhook Secret → Webhook Auth            (401 → Respond Unauthorized)
  → Load Admin Filter Settings → Apply Admin Number Filter
  → Is Admin Number?                                   (evet → Respond Admin Filtered)
  → Normalize Payload (Evolution v2 root.data & @lid) → Valid Event? (hayır → Respond Ignored)
  → Check Business Hours
      ├─ mesai dışı → Claim OOH Notification → Is Off Hours?
      │     → Wait OOH 120 Seconds → Build OOH Messages → OOH Claim Won?
      │     → Send OOH to Customer → Enqueue Manager OOH Alert → Log OOH Event
      └─ Rate Limit Exceeded?                          (evet → Respond Rate Limited)
  → Ingest Message (PostgreSQL ingest_message 8 argüman)  (hata → Prepare Ingest Failure → Respond 503)
  → Respond Accepted (HTTP 202)
```

---

## 3. Node Envanteri (53 Node)

1. `Webhook1` 2. `Normalize Payload` 3. `Valid Event?` 4. `Validate Webhook Secret` 5. `Webhook Auth` 6. `Respond Unauthorized` 7. `Load Admin Filter Settings` 8. `Apply Admin Number Filter` 9. `Is Admin Number?` 10. `Respond Admin Filtered` 11. `Load Holiday Settings` 12. `Check Business Hours` 13. `Is Off Hours?` 14. `Wait OOH 120 Seconds` 15. `Claim OOH Notification` 16. `OOH Claim Won?` 17. `Build OOH Messages` 18. `Send OOH to Customer` 19. `Enqueue Manager OOH Alert` 20. `Log OOH Event` 21. `Rate Limit Exceeded?` 22. `Respond Rate Limited` 23. `Ingest Message` 24. `Respond Accepted` 25. `Prepare Ingest Failure` 26. `Respond 503` 27. `Schedule Trigger` 28. `OpenAI Circuit Gate` 29. `OpenAI Circuit Open?` 30. `Claim Ready Batches` 31. `Store Context` 32. `AI Agent` (gpt-5.4) 33. `Parse AI Output` 34. `AI Output Valid?` 35. `Complete AI Batch` 36. `AI Batch Completed?` 37. `Persist Chat Memory` 38. `Prepare AI Failure` 39. `Record AI Failure` 40. `Evolution Circuit Gate` 41. `Evolution Circuit Open?` 42. `Claim Deliveries` 43. `Prepare Delivery` 44. `Delivery Valid?` 45. `Send Delivery` 46. `Tag Delivery Success` 47. `Tag Delivery Error` 48. `Tag Delivery Validation Error` 49. `Record Delivery Result` 50. `Run Stale Batch Monitor` 51. `Respond Ignored` 52. `OpenAI Chat Model1` 53. `Simple In-Memory Vector Store`

---

## 4. Release Gate ve Komut Zinciri

Codex 5.4 ile kod düzeltmeleri tamamlandıktan sonra sırasıyla şu komutlar çalıştırılmalıdır:

```bash
python build_workflow.py
python tools/wf_validate.py workflow.json
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/test_ops_drift_check.py
python tools/test_outbound_guard.py
node tools/test_policy_engine.test.js
npm run release:gate
```

---

## 10. Codex 5.4 Kod Düzeltme Görev Kartları ve Uygulama Rehberi

---

### 📋 GÖREV KART K-01: Marka Kataloğuna `Suzuki`, `Mini`, `BMW`, `Subaru` vb. Ekleme

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L516)
- **HEDEFLENEN KOD:**
  ```javascript
  const brands = ['Fiat','Renault','Ford','Volkswagen','VW','Opel','Peugeot','Citroen','Toyota','Honda','Hyundai','Kia','Mercedes','BMW','Audi','Skoda','Seat','Dacia','Nissan','Suzuki','Mini','Subaru','Volvo','Mitsubishi','Jeep','Porsche','Land Rover'];
  ```

---

### 📋 GÖREV KART K-02: Papağan Döngüsünü Engelleme (Duplicate Response Guard)

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L802)
- **HEDEFLENEN KOD:**
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

### 📋 GÖREV KART K-03: "Mesai mesai" SLA Şablon Typo Düzeltmesi

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L463)
- **HEDEFLENEN KOD:**
  ```javascript
  const SLA_TEXT = 'mesai saatleri içinde';
  const SLA_LINE = isBusinessHours
    ? 'Mesai saatleri içinde dönüş yapacağız.'
    : 'Mesai dışındayız; talebiniz sıraya alındı, ilk iş saatinde dönüş yapılacak.';
  ```

---

### 📋 GÖREV KART K-04: Ingress Event Filtresi (`MESSAGES_UPSERT`) Ekleme

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L89)
- **HEDEFLENEN KOD:**
  ```javascript
  const eventType = String(root.event || root.body?.event || root.body?.body?.event || '');
  const isUpsert = !eventType || eventType === 'messages.upsert' || eventType === 'MESSAGES_UPSERT';
  ```

---

### 📋 GÖREV KART K-05: OOH HTTP 400 Cooldown Sızıntısı Düzeltmesi

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1289)
- **HEDEFLENEN KOD:**
  ```python
  postgres_node(
      "Log OOH Event",
      "UPDATE whatsapp_ai.ooh_log SET customer_sent = $2 WHERE id = $1::uuid RETURNING id",
      "={{ [ $('Build OOH Messages').item.json.oohLogId, Boolean(($('Send OOH to Customer').item.json.key || $('Send OOH to Customer').item.json.status === 'SENT' || $('Send OOH to Customer').item.json.status === 'PENDING') && !$('Send OOH to Customer').item.json.error && (!$('Send OOH to Customer').item.json.statusCode || $('Send OOH to Customer').item.json.statusCode < 400)) ] }}",
      [2540, 260],
  ),
  ```

---

### 📋 GÖREV KART K-06: OOH Adresleme ve Numara Temizliği

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1000)
- **HEDEFLENEN KOD:**
  ```javascript
  const senderNumberRaw = String(claim.senderNumber || ctx.senderNumber || '');
  const isLid = senderNumberRaw.toLowerCase().endsWith('@lid');
  const senderNumber = isLid
    ? senderNumberRaw.replace(/[^0-9@a-zA-Z._-]/g, '').replace(/@lid$/i, '@lid')
    : senderNumberRaw.replace(/@s\.whatsapp\.net$|@g\.us$/gi, '').replace(/[^0-9]/g, '');
  ```

---

### 📋 GÖREV KART K-07: Legacy Policy Engine Test Suite Düzeltmesi

- **İlgili Dosya:** [tools/test_policy_engine.test.js](file:///C:/ILAN/WHATSAPP_N8N/tools/test_policy_engine.test.js)
- **Hedef:** Test suite 62 PASSED / 0 FAILED (Exit code 0) olmalıdır.

---

### 📋 GÖREV KART K-08: Untracked Backup Klasörü Karantinası

- **İlgili Dosya:** [.gitignore](file:///C:/ILAN/WHATSAPP_N8N/.gitignore#L30)
- **Hedef:** `postgresql_backup/` satırı eklenmelidir.

---

### 📋 GÖREV KART K-09: URL ve Web Linki Temizliği (URL Slug Sızıntısı Engeli)

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L444)
- **Sorun:** Müşteri ürün linki paylaştığında linkteki `srsltid=...` parametreleri araç adı sanılmaktadır.
- **HEDEFLENEN KOD:**
  ```javascript
  const cleanVehicleText = vehicleSourceText.replace(/https?:\/\/[^\s]+/gi, ' ');
  ```

---

### 📋 GÖREV KART K-10: Olumsuz İfade Modellemesi ("Toyota gt86 değil" Filtresi)

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L521)
- **Sorun:** Müşteri `"Toyota değil"` dediğinde aracı `"Toyota değil 2."` yapmaktadır.
- **HEDEFLENEN KOD:**
  ```javascript
  if (/\b(?:değil|degil|yok|olmayan)\b/i.test(modelPart)) {
    modelPart = '';
  }
  ```

---

### 📋 GÖREV KART K-11: Chat Memory'deki VIN'in Korunması

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L443)
- **Sorun:** Müşteri şasiyi (`WDB2100351A528399` veya `JF1SH5...`) önceden verdiği halde sonraki mesajlarda sistem şasiyi unutmakta ve tekrar şasi istemektedir.
- **HEDEFLENEN KOD:**
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

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L528)
- **HEDEFLENEN KOD:**
  ```javascript
  if (detectedCodes.length > 0 && /\b(mevcut mu|var mı|fiyat|stok|kaç para|ne kadar)\b/i.test(plainText) && !/\b(uyar mı|uyumlu mu)\b/i.test(plainText)) {
    caseType = 'exact_code_price_stock';
    askVehicleInfo = false;
  }
  ```

---

### 📋 GÖREV KART K-13: Zaten Şasi Verilmişse Asla Tekrar Şasi İstememe Guard'ı

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L610)
- **Sorun (Murat Sohbeti):** Müşteri 2 kez `WDB2100351A528399` şasisini yazdığı halde bot 3 kez üst üste şasi istedi ve müşteri sistemi terk etti.
- **HEDEFLENEN KOD:**
  ```javascript
  // Eğer geçmişte veya mevcut mesajda geçerli 17 haneli VIN varsa asla tekrar VIN isteme!
  if (detectedVin || (Array.isArray(entities.vehicles) && entities.vehicles.some(v => v.vin && v.vin.length === 17))) {
    askVehicleInfo = false;
  }
  ```

---

### 📋 GÖREV KART K-14: Müşteri Terk / Vazgeçiş Algılama ("Tşk ederim iyi çalışmalar")

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L504)
- **Sorun:** Müşteri botun ısrarlarından bıkıp *"Tşk ederim iyi çalışmalar"* veya *"Kalsın istemiyorum"* yazdığında bot tekrar ürün veya araç sormaktadır.
- **HEDEFLENEN KOD:**
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

> *İşbu runbook Codex 5.4 modelinin 14 adet görev kartını sırasıyla uygulayarak sistemdeki tüm müşteri kaybı ve papağan döngüsü anomalilerini çözmesi için güncellenmiştir.*
