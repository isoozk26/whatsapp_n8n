# WhatsApp AI — v13 PostgreSQL Outbox — GPT-5.4 Operasyon & Codex Düzeltme Runbook

| Alan | Değer |
| --- | --- |
| Doküman sürümü | 4.0 |
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
10. Codex 5.4 Kod Düzeltme Görev Kartları ve Uygulama Rehberi

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
# 1. Workflow derleme ve JSON doğrulama
python build_workflow.py
python tools/wf_validate.py workflow.json

# 2. Sözleşme ve davranış testleri
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/test_ops_drift_check.py
python tools/test_outbound_guard.py

# 3. Güvenlik taraması
python tools/wf_security.py

# 4. Yerel Kalite Kapısı (Release Gate)
npm run release:gate
```

---

## 10. Codex 5.4 Kod Düzeltme Görev Kartları ve Uygulama Rehberi

Codex 5.4 modelinin kod tabanındaki tüm hataları sırasıyla düzeltmesi için detaylı uygulama talimatları:

---

### 📋 GÖREV KART K-01: Marka Kataloğuna `Suzuki`, `Mini`, `BMW` vb. Ekleme

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L514)
- **Satır:** ~514
- **Mevcut KOD:**
  ```javascript
  const brands = ['Fiat','Renault','Ford','Volkswagen','VW','Opel','Peugeot','Citroen','Toyota','Honda','Hyundai','Kia','Mercedes','BMW','Audi','Skoda','Seat','Dacia','Nissan'];
  ```
- **HEDEFLENEN KOD:**
  ```javascript
  const brands = ['Fiat','Renault','Ford','Volkswagen','VW','Opel','Peugeot','Citroen','Toyota','Honda','Hyundai','Kia','Mercedes','BMW','Audi','Skoda','Seat','Dacia','Nissan','Suzuki','Mini','Volvo','Mitsubishi','Subaru','Jeep'];
  ```
- **Açıklama:** Müşteri `Suzuki Swift` veya `Mini Cooper` araç bilgilerini verdiğinde bot markayı tanıyamadığı için araç tamlığı aksamakta ve fuzuli VIN istenmektedir. Markalar eklendiğinde `Suzuki` ve `Mini` tam araç olarak tanınır.

---

### 📋 GÖREV KART K-02: Papağan Döngüsünü Engelleme (Duplicate Response Guard)

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L504)
- **Satır:** ~504
- **Açıklama:** Bot aynı müşteriye üst üste 2 kez birebir aynı yanıtı verdiğinde müşteri bot döngüsüne (looping) girmektedir.
- **HEDEFLENEN KOD EKLEMESİ:**
  ```javascript
  const lastReplyText = String(ctx.lastReplyText || '').trim();
  if (reply.length > 0 && lastReplyText.length > 0 && reply === lastReplyText) {
    action = 'handoff';
    pauseAutomation = true;
    notifyAdmins = true;
    handoffReason = 'Tekrarlayan yanıt algılandı; temsilciye devredildi';
  }
  ```

---

### 📋 GÖREV KART K-03: "Mesai mesai" SLA Şablon Typo Düzeltmesi

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L461)
- **Satır:** ~461
- **Mevcut KOD:**
  ```javascript
  const SLA_TEXT = 'mesai saatleri içinde';
  const SLA_LINE = isBusinessHours
    ? `Mesai ${SLA_TEXT} dönüş yapacağız.`
    : 'Mesai dışındayız; talebiniz sıraya alındı, ilk iş saatinde dönüş yapılacak.';
  ```
- **HEDEFLENEN KOD:**
  ```javascript
  const SLA_TEXT = 'mesai saatleri içinde';
  const SLA_LINE = isBusinessHours
    ? 'Mesai saatleri içinde dönüş yapacağız.'
    : 'Mesai dışındayız; talebiniz sıraya alındı, ilk iş saatinde dönüş yapılacak.';
  ```

---

### 📋 GÖREV KART K-04: Ingress Event Filtresi (`MESSAGES_UPSERT`) Ekleme

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L82)
- **Satır:** ~82 (`normalize_js`)
- **HEDEFLENEN KOD:**
  ```javascript
  const eventType = String(payload?.event || root.event || root.body?.event || '');
  const isUpsert = !eventType || eventType === 'messages.upsert' || eventType === 'MESSAGES_UPSERT';
  const valid = Boolean(isUpsert && payload && messageId && senderNumber && !isGroup && !isBroadcast && !isProtocolMessage && !isEmpty && (!fromMe || command));
  ```
- **Açıklama:** Evolution API'den gelen `MESSAGES_UPDATE` veya `SEND_MESSAGE` gibi diğer etkinliklerin veritabanına girmesi engellenir.

---

### 📋 GÖREV KART K-05: OOH HTTP 400 Cooldown Sızıntısı Düzeltmesi

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1267)
- **Satır:** ~1267 (`Log OOH Event` postgres node)
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

- **İlgili Dosya:** [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L984)
- **Satır:** ~984 (`build_ooh_messages_js`)
- **HEDEFLENEN KOD:**
  ```javascript
  const senderNumberRaw = String(claim.senderNumber || ctx.senderNumber || '');
  const senderNumber = senderNumberRaw.replace(/@s\.whatsapp\.net$|@g\.us$|@lid$/gi, '').replace(/[^0-9]/g, '');
  ```

---

### 📋 GÖREV KART K-07: Legacy Policy Engine Test Suite Düzeltmesi

- **İlgili Dosya:** [tools/test_policy_engine.test.js](file:///C:/ILAN/WHATSAPP_N8N/tools/test_policy_engine.test.js#L536)
- **Satır:** ~536
- **Açıklama:** Testteki `_deliveryLedger` ve assertion beklentileri güncel v13 outbox yapısıyla eşleşecek şekilde güncellenmeli ve `node tools/test_policy_engine.test.js` çıkış kodu 0 olmalıdır.

---

### 📋 GÖREV KART K-08: Untracked Backup Klasörü Karantinası

- **İlgili Dosya:** [.gitignore](file:///C:/ILAN/WHATSAPP_N8N/.gitignore)
- **Açıklama:** `.gitignore` dosyasına `postgresql_backup/` satırı eklenerek 52MB boyutundaki dump dosyasının repoya girmesi engellenmelidir.

---

> *İşbu uygulama rehberi Codex 5.4 modelinin tüm hataları deterministik olarak sırayla ve hatasız düzeltebilmesi için hazırlanmıştır.*
