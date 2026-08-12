# WhatsApp AI — Müşteri Mesajına Cevap Verilmeme Durumu Uçtan Uca (E2E) Analiz Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 12 Ağustos 2026  
**Kapsam:** Müşteriden gelen WhatsApp mesajının yanıtlanamamasının tüm olası nedenleri, uçtan uca (E2E) yaşam döngüsü analizi, 12 bulgunun düzeltme ve doğrulama durumları, SQL ve log teşhis rehberi, P0/P1/P2 bulgu matrisi ve çözüm önerileri.

---

## 1. YÖNETİCİ ÖZETİ

FiltreOto WhatsApp AI sistemi; Evolution API, n8n workflow motoru, PostgreSQL transactional outbox veritabanı ve OpenAI GPT model katmanından oluşmaktadır. Müşterinin mesaj atıp sistemin cevap vermediği senaryolar, mesajın yaşam döngüsündeki **5 ana aşamadan (Webhook Ingest, Batching & Claiming, AI Inference & Policy Parsing, Outbox Enqueue & Claims, Provider Delivery)** herhangi birinde meydana gelebilecek bir aksaklıktan kaynaklanır.

Bu raporda, tespit edilen tüm kritik hatalar (BUG 1-3) ve edge-case mantık sorunları (EDGE 1-5, TES 1-4) **[build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py)** içinde düzeltilmiş, `workflow.json` yeniden derlenmiş ve `release_gate` ile 100/100 PASS olarak doğrulanmıştır.

---

## 2. DÜZELTİLEN BUG VE EDGE CASE MATRİSİ

| ID | Kategori | İlgili Düğüm | Sorun & Düzeltme Özeti | Durum |
| --- | --- | --- | --- | --- |
| **BUG-1** | Kritik | `Validate Webhook Secret` | İki kademeli yetkilendirme: Token varlık kontrolü JS düğümünde, secret eşleştirme DB `ingest_message()` seviyesinde. | **ÇÖZÜLDÜ** ✅ |
| **BUG-2** | Orta | `Parse AI Output` | Yazısız görsellerdeki Türkçe fallback metninin AI prompt'a sızması engellendi; medya otomatik handoff mantığı düzeltildi. | **ÇÖZÜLDÜ** ✅ |
| **BUG-3** | Orta | `Parse AI Output` | `unsafeClaim` regex'i fiyat ve stok iddiası üreten AI yanıtlarını ezerek koruma sağlar. | **DOĞRULANDI** ✅ |
| **EDGE-1** | Test | `Parse AI Output` | VIN olmadan araç bilgisi kontrolünde motor gücü (`kW/HP`) veya hacmi (`CC`) varsa araç tam kabul edildi. | **ÇÖZÜLDÜ** ✅ |
| **EDGE-2** | Test | `Parse AI Output` | Alias normalizasyonunun allowed set kontrolünden önce çalışması doğrulandı. | **DOĞRULANDI** ✅ |
| **EDGE-3** | Test | `Parse AI Output` | `unclearCount` DB seviyesinde `whatsapp_ai.customer_states` üzerinden takip edildi. | **DOĞRULANDI** ✅ |
| **EDGE-4** | Test | `Prepare Delivery` | Boş `deliveryId` için `validDelivery = false` yapılarak PostgreSQL `$1::uuid` cast hatası engellendi. | **ÇÖZÜLDÜ** ✅ |
| **EDGE-5** | Test | `Record Delivery Result` | n8n JS boolean `true`/`false` değerinin PostgreSQL SQL `TRUE`/`FALSE` tipine dönüşümü doğrulandı. | **DOĞRULANDI** ✅ |
| **TES-1** | Mimari | `Prepare Ingest Failure` | 503 yanıtında `correlationId` alanının korunması doğrulandı. | **DOĞRULANDI** ✅ |
| **TES-2** | Mimari | `Store Context` | Prompt injection koruması JSON şema zorlaması ile sağlandı. | **DOĞRULANDI** ✅ |
| **TES-3** | Mimari | `Circuit Gate` | Devre kesici sıfırlaması DB `opened_until` timestamp üzerinden half-open yapıldı. | **DOĞRULANDI** ✅ |
| **TES-4** | Mimari | `Schedule Trigger` | Paralel worker adımları PostgreSQL `FOR UPDATE SKIP LOCKED` ile race condition'a karşı korundu. | **DOĞRULANDI** ✅ |

---

## 3. KRİTİK AKIŞ ŞEMASI VE MESAJ YAŞAM DÖNGÜSÜ

```text
[AŞAMA 1: WEBHOOK & INGEST]
Evolution Webhook (POST /evolution-webhook)
  ├─► Validate Webhook Secret (Headers/Query token check) ──[HATA 401]──► Respond Unauthorized (401)
  ├─► Load Admin Filter Settings ──► Apply Admin Number Filter
  │     └─► Is Admin Number? (admin_phone_a/b eşleşmesi) ──[EVET]──────► Respond Admin Filtered (202 Accepted)
  ├─► Normalize Payload ──► Valid Event? (Geçersiz/Boş/Status) ──[HAYIR]─► Respond Ignored (202 Accepted)
  ├─► Check Business Hours (Mesai dışı / OOH)
  │     └─► Off Hours? ──► OOH Wait (120s) ──► OOH Cooldown Check ──► Send OOH / Manager Alert
  ├─► Rate Limit Exceeded? ──[EVET]─────────────────────────────────────► Respond Rate Limited (202 Accepted)
  └─► Ingest Message (whatsapp_ai.ingest_message) ──[DB HATA]───────────► Respond 503 Service Unavailable
        └─► SUCCESS ──► Respond 202 Accepted (Kayıt 'pending' statusuyla whatsapp_ai.batches'te)

[AŞAMA 2: BATCHING & CLAIMING] (Schedule Trigger - Her 15 Saniyede Bir)
OpenAI Circuit Gate ──► OpenAI Circuit Open? ──[EVET: OPEN]────────────► İşlem Atlanır (Cevap Bekler)
  └─► [HAYIR: CLOSED] ──► Claim Ready Batches (whatsapp_ai.claim_ready_batches, 120s pencere)
        ├─► Manuel Mod Aktif mi? (manual_pause = true) ──[EVET]─────────► Otomatik Cevap Üretilmez
        └─► Batches Claimed ('processing' statusuna geçer)

[AŞAMA 3: AI INFERENCE & POLICY PARSING]
Store Context (Mesaj geçmişi + Araç/Parça Regex) ──► AI Agent (GPT-5.4 / GPT-4o)
  ├─► OpenAI API Hata (401/429/5xx) ──► Record AI Failure ──► Service Circuit Failure Counter++
  └─► AI Yanıt Verdi ──► Parse AI Output (JSON Sözleşme Kontrolü)
        ├─► Çıktı Geçersiz / Parse Hatası ──► Record AI Failure (Batch stuck / retry)
        └─► Çıktı Geçerli ──► Politika Değerlendirmesi:
              ├─► pauseAutomation = true (Handoff/Şikayet/İnsana Aktarım) ──► Bot Cevabı Kesilir + Admin Uyarılır
              ├─► unclear (2. tekrarlayan belirsiz mesaj) ───────────────► Bot Susturulur + İnsana Aktarılır
              └─► action = 'reply' ──► Complete AI Batch (whatsapp_ai.complete_ai_batch)
                    └─► whatsapp_ai.deliveries tablosuna outbox kaydı eklenir

[AŞAMA 4: OUTBOX ENQUEUE & DELIVERY CLAIM] (Zamanlayıcı İş Akışı)
Evolution Circuit Gate ──► Evolution Circuit Open? ──[EVET: OPEN]────────► Teslimat Durdurulur (Cevap Gecikir)
  └─► [HAYIR: CLOSED] ──► Claim Deliveries (whatsapp_ai.claim_deliveries, status 'sending')

[AŞAMA 5: PROVIDER DELIVERY & RESULT PROCESSING]
Prepare Delivery (Payload Formatlama & @LID Normalizasyonu) ──► Send Delivery (HTTP POST to Evolution API)
  ├─► HTTP 200 OK ──► Tag Delivery Success ──► Record Delivery Result (status: 'sent')
  └─► HTTP 4xx / 5xx / Timeout / Socket Error
        └─► Tag Delivery Error ──► Record Delivery Result (attempt_count++)
              ├─► attempt_count < 3 ──► Status: 'pending' (Yeniden Denenecek)
              └─► attempt_count >= 3 ──► Status: 'dead' (DÜŞTÜ - Yeniden Denenmez, Cevap Gitmez)
```

---

## 4. CANLI TEŞHİS VE VERİTABANI ANALİZ REHBERİ (DIAGNOSTIC RUNBOOK)

```sql
-- 1. Ingest Mesaj Kontrolü
SELECT id, sender_number, sender_name, payload->>'conversation' AS mesaj, received_at 
FROM whatsapp_ai.messages WHERE sender_number LIKE '%905XXXXXXXXX%' ORDER BY received_at DESC LIMIT 5;

-- 2. Batch Durum Kontrolü
SELECT id, sender_number, status, processing_started_at, created_at, updated_at
FROM whatsapp_ai.batches WHERE sender_number LIKE '%905XXXXXXXXX%' ORDER BY created_at DESC LIMIT 5;

-- 3. Manuel Mod Kontrolü
SELECT phone_number, manual_pause, last_action, updated_at 
FROM whatsapp_ai.customer_states WHERE phone_number LIKE '%905XXXXXXXXX%';

-- 4. Outbox Teslimat Kontrolü (Sütun: attempt_count)
SELECT id, channel, destination, status, attempt_count, error_message, created_at, sent_at 
FROM whatsapp_ai.deliveries WHERE destination LIKE '%905XXXXXXXXX%' ORDER BY created_at DESC LIMIT 5;

-- 5. Ölü Mektup (Dead Letter) Tablosu
SELECT * FROM whatsapp_ai.dead_letters WHERE destination LIKE '%905XXXXXXXXX%' ORDER BY created_at DESC LIMIT 5;

-- 6. Devre Kesiciler ve Sağlık Durumu
SELECT service, state, consecutive_failures, opened_until, last_error_code FROM whatsapp_ai.service_circuits;
SELECT * FROM whatsapp_ai.get_health_status();
```

---

## 5. RELEASE VE DENETİM KARARI (RELEASE GATE DECISION)

| Kontrol Adı | Sonuç | Durum |
| --- | --- | --- |
| `workflow_validate_json` | PASS | Bağımlılıklar ve JSON şeması doğrulandı |
| `workflow_validate_graph` | PASS | Graph ve bağlantı yönleri doğrulandı |
| `workflow_check_code_nodes` | PASS | Tüm JavaScript Code node sözdizimi doğrulandı |
| `workflow_check_expressions` | PASS | n8n expression ifadeleri doğrulandı |
| `test_workflow_behavior.js` | PASS | `@LID`, E.164 ve media fallback regresyon testleri geçti |
| `release_gate` | **PASS (100/100)** | Tüm yerel statik güvenlik ve sözleşme testleri geçti |

| Ortam / Kapsam | Karar | Gerekçe |
| --- | --- | --- |
| **Lokal & Kod Mimarisi** | **🟢 GO (100/100 PASS)** | Tüm kod mimarisi ve statik testler PASS. Düzeltmeler tamamlandı. |
| **Canlı Yayın (Production)** | **🔴 NO-GO (Canlı Doğrulama Bekliyor)** | Canlı veritabanı kilitleri, n8n active-published version eşitliği ve Evolution API canlı oturumu operatör tarafından doğrulanana kadar canlıya geçiş yapılmaz. |
