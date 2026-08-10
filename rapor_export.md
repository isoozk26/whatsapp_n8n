# WhatsApp AI — Müşteri Mesajına Cevap Verilmeme Durumu Uçtan Uca (E2E) Analiz Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 11 Ağustos 2026  
**Kapsam:** Müşteriden gelen WhatsApp mesajının yanıtlanamamasının tüm olası nedenleri, uçtan uca (E2E) yaşam döngüsü analizi, 10. alt ajan (Hermes) denetim sonuçları, SQL ve log teşhis rehberi, P0/P1/P2 bulgu matrisi ve çözüm önerileri.

---

## 1. YÖNETİCİ ÖZETİ

FiltreOto WhatsApp AI sistemi; Evolution API, n8n workflow motoru, PostgreSQL transactional outbox veritabanı ve OpenAI GPT model katmanından oluşmaktadır. Müşterinin mesaj atıp sistemin cevap vermediği senaryolar, mesajın yaşam döngüsündeki **5 ana aşamadan (Webhook Ingest, Batching & Claiming, AI Inference & Policy Parsing, Outbox Enqueue & Claims, Provider Delivery)** herhangi birinde meydana gelebilecek bir aksaklıktan kaynaklanır.

Bu raporda, bir müşteri mesajının sistem tarafından yanıtsız kalmasının **bütün uçtan uca nedenleri** teknik derinlikte, somut kod/veri tabanı nesne referanslarıyla ve 10. alt ajan (Hermes) hassas şema/terminoloji denetim bulgularıyla güncellenerek incelenmiştir.

### Temel Kök Neden Kategorileri:
1. **Giriş ve Doğrulama Engelleri (Ingest Phase):** Webhook Secret uyuşmazlığı (401), Yönetici Filtresi (`admin_phone_a`/`admin_phone_b` tam eşleşme ➔ HTTP 202 Accepted ile yutulur), Rate Limit aşımı (HTTP 202 Accepted ile yutulur), Mesaj Normalizasyonu/Geçersiz Event elenmesi (HTTP 202 Accepted).
2. **Kuyruk ve Zamanlama Engelleri (Batching Phase):** 120 saniyelik birleştirme penceresi beklenmesi, `Schedule Trigger` (15sn) durması, OpenAI Devre Kesicisinin (`circuit_breakers.openai`) açık olması (`open`), Manuel Mod (`manual_pause = true`) engeli.
3. **AI ve Politika Engelleri (AI & Policy Phase):** OpenAI API kotası/anahtar hatası, AI JSON çıktı doğrulama başarısızlığı, Otomasyonun Durdurulması (`pauseAutomation = true`) ve İnsan Aktarımı (handoff), Düşük güven skoru / Üst üste belirsiz mesajlar (`unclear` limitleyici).
4. **Outbox ve Kilit Engelleri (Outbox & Claims Phase):** `complete_ai_batch` sırasında outbox kaydı oluşmaması, Evolution Devre Kesicisinin (`circuit_breakers.evolution`) açık olması, Stale (`sending`) kilitlenme durumu.
5. **Gönderim ve Kanal Engelleri (Delivery Phase):** Evolution API HTTP 400/401/500 hataları, WhatsApp numara formatı uyumsuzluğu (`0532...`, `@LID` harf hassasiyeti), Evolution instance bağlantısının kopması, Max deneme (`attempt_count >= 3`) dolup `status = 'dead'` seviyesine düşme.

---

## 2. ŞEMA VE İŞLETİM TERMİNOLOJİSİ DÜZELTMELERİ (HERMES DENETİMİ)

10. Alt Ajan (Hermes) konsolidasyonu sonucunda raporda netleştirilen **şema ve runtime terminolojisi ayrımları**:

| Alan / Konu | Eski Yanıltıcı Tanım | Doğru Şema & Runtime Gerçeği |
| --- | --- | --- |
| **Admin Filter Yanıtı** | `200 OK` | **`202 Accepted`** (`{ accepted: true, ignored: true, adminFiltered: true }`) |
| **Rate Limit Yanıtı** | `429 Rate Limited` | **`202 Accepted`** (`{ accepted: true, ignored: true, rateLimited: true }`) |
| **Outbox Deneme Sayısı** | `retry_count` | **`attempt_count`** (`whatsapp_ai.deliveries` tablosundaki gerçek sütun adı) |
| **Provider Gönderim Durumu** | `delivered` | **`sent`** (`status = 'sent'`: yalnızca Evolution API HTTP çağrısının başarılı olduğunu gösterir, WhatsApp alıcısının okuma makbuzu anlamına gelmez) |
| **Ölü Mektup Sınıflandırması** | `dead_letter` | **`deliveries.status = 'dead'` vs `whatsapp_ai.dead_letters` tablosu** (`deliveries` üzerindeki `dead` durumu ile tarihsel ölü mektup kayıtlarının tutulduğu `whatsapp_ai.dead_letters` tablosu birbirinden farklı nesnelerdir) |
| **Lokal vs Canlı Deploy** | *Local fix = Deploy edildi* | **Lokal Kod PASS ≠ Canlı n8n Active/Published Version**. Canlı sunucuda N8N_API_KEY, veritabanı kilitleri ve Evolution instance doğrulanmadan canlı yayın ilan edilemez. |

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

## 4. UÇTAN UCA (E2E) DETAYLI BAŞARISIZLIK VE CEVAP VERMEME NEDENLERİ

### AŞAMA 1: Giriş Webhook, Kimlik Doğrulama ve Ingest Başarısızlıkları

#### 1.1 Webhook Secret Doğrulama Başarısızlığı (`401 Unauthorized`)
* **İlgili Node'lar:** [Validate Webhook Secret](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1144), `Webhook Auth`, `Respond Unauthorized`
* **Mekanizma:** Evolution API'den gelen HTTP isteğindeki `X-Webhook-Secret` header'ı veya `token` query parametresi n8n `N8N_WEBHOOK_SECRET` ile eşleşmezse sistem isteği reddeder (`401`).
* **Müşteriye Etkisi:** Mesaj veritabanına hiç yazılmaz, akış anında durur, müşteriye hiçbir cevap gitmez.

#### 1.2 Yönetici Numarası Filtresine Takılma (`Respond Admin Filtered` -> `202 Accepted`)
* **İlgili Node'lar:** [Load Admin Filter Settings](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md#L116), [Apply Admin Number Filter](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1152), `Is Admin Number?`, `Respond Admin Filtered`
* **Mekanizma:** Mesajı atan numara `whatsapp_ai.settings` içindeki `admin_phone_a` veya `admin_phone_b` numaralarından biriyle tam eşleşiyorsa (ve mesaj yetkili komut `++`, `--`, `??` değilse), filtre tetiklenir.
* **Müşteriye Etkisi:** Yönetici numaralarından gelen mesajlara güvenlik gereği otomatik müşteri cevabı dönülmez. Evolution API'ye HTTP `202 Accepted` dönülerek webhook birikmesi önlenir.

#### 1.3 Geçersiz Event / Format Uyumsuzluğu / Rate Limit (`Respond Ignored` / `Respond Rate Limited` -> `202 Accepted`)
* **İlgili Node'lar:** [Normalize Payload](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1162), `Valid Event?`, `Respond Ignored`, `Respond Rate Limited`
* **Mekanizma:** Mesaj içeriği boşsa, metin içermeyen desteklenmeyen bir medya tipiyse, grup mesajıysa veya WhatsApp durum (status) güncellemesiyse elenir. 5 saniyeden kısa sürede aynı numaradan gelen aşırı mesajlarda rate limit devreye girer.
* **Müşteriye Etkisi:** HTTP `202 Accepted` dönülür; mesaj işlenmez ve bot yanıt vermez.

#### 1.4 Mesai Dışı (Off-Hours / OOH) Bekleme ve Cooldown Engeli
* **İlgili Node'lar:** [Check Business Hours](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1170), `Claim OOH Notification`, `Wait OOH 120 Seconds`, [Build OOH Messages](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1219)
* **Mekanizma:** Mesaj mesai saatleri dışında gelmişse 120 saniyelik bekleme penceresine alınır. Eğer bu müşteriye son 8 saat içinde zaten OOH mesajı gönderilmişse (`ooh_log` cooldown kontrolü), ikinci kez OOH yanıtı atılmaz.
* **Müşteriye Etkisi:** Müşteri 2 dakika boyunca yanıt almaz; cooldown süresindeyse mesai dışı şablon mesajı tekrar gönderilmez.

#### 1.5 PostgreSQL Ingest Hata / Veritabanı Kesintisi (`503 Service Unavailable`)
* **İlgili Node'lar:** `Ingest Message`, `Prepare Ingest Failure`, `Respond 503`
* **SQL Fonksiyonu:** `whatsapp_ai.ingest_message()`
* **Mekanizma:** PostgreSQL veritabanına erişilemiyorsa, bağlantı havuzu dolduysa veya `ingest_message` SQL fonksiyonu hata verirse HTTP `503` dönülür.
* **Müşteriye Etkisi:** Mesaj veritabanına kaydedilemediği için kuyruğa girmez ve bot cevap veremez.

---

### AŞAMA 2: Batching, Zamanlayıcı (Worker) ve Devre Kesici (Circuit Breaker) Başarısızlıkları

#### 2.1 120 Saniyelik Batch Toplama Penceresi Beklemesi
* **İlgili Fonksiyon:** `whatsapp_ai.claim_ready_batches(p_batch_limit, p_window_seconds => 120)`
* **Mekanizma:** Müşteri mesaj attığında ilk mesaj `status = 'pending'` olarak batch'e eklenir. `claim_ready_batches` fonksiyonu, son mesajın üzerinden **en az 120 saniye** geçmeden batch'i `ready` duruma getirmez.
* **Müşteriye Etkisi:** Müşteri ilk mesajını attıktan sonraki 2 dakika boyunca sistem bilinçli olarak yanıt vermez.

#### 2.2 Schedule Trigger (Worker Döngüsü) Durması veya n8n Worker Çökmesi
* **İlgili Node:** `Schedule Trigger` (Her 15 saniyede bir çalışır)
* **Mekanizma:** n8n üzerinde workflow `active = false` konuma alınmışsa veya n8n worker servisi çökmüşse, 15 saniyelik zamanlayıcı çalışmaz.
* **Müşteriye Etkisi:** Mesajlar `whatsapp_ai.batches` tablosunda `pending` veya `ready` durumunda kalır.

#### 2.3 OpenAI Circuit Breaker Açık Olması (`circuit_breakers.openai = open`)
* **İlgili Node'lar:** `OpenAI Circuit Gate`, `OpenAI Circuit Open?`
* **SQL Fonksiyonu:** `whatsapp_ai.circuit_allows('openai')`
* **Mekanizma:** Üst üste gelen OpenAI API hataları nedeniyle `service_circuits` tablosundaki `openai` servisi `state = 'open'` durumuna geçmişse, worker batch'leri veritabanından çekmez (`Claim Ready Batches` bypass edilir).
* **Müşteriye Etkisi:** Devre kapanana kadar müşteri mesajları yanıtsız kalır.

#### 2.4 Müşteri Numarasının Manuel Modda Olması (`manual_pause = true`)
* **İlgili Tablo/Fonksiyon:** `whatsapp_ai.customer_states`, `manual_pause`
* **Mekanizma:** Müşteri için daha önce yetkili tarafından `++` komutu verilmişse veya sistem şikayet/düşük güven nedeniyle müşteriyi insana aktarmışsa (`manual_pause = true`), AI işlem hattı bu mesajı yanıtlamaz.
* **Müşteriye Etkisi:** Bot yanıt vermez; yalnızca insan operatör yanıt verebilir.

---

### AŞAMA 3: AI Inference, Çıktı Doğrulama ve Politika Kararı Başarısızlıkları

#### 3.1 OpenAI API Servis Hataları (401, 429, 500, Timeout)
* **İlgili Node'lar:** `AI Agent`, `OpenAI Chat Model1`
* **Mekanizma:** OpenAI API anahtarı geçersizse (`401`), API kotası/rate-limit dolmuşsa (`429`) veya OpenAI tarafında kesinti varsa (`500/503`), node hata fırlatır.
* **Müşteriye Etkisi:** `Prepare AI Failure` tetiklenir, `whatsapp_ai.record_ai_failure()` çalışır. Batch `failed` durumuna geçer.

#### 3.2 AI Çıktısının JSON Şemasına Uymaması veya Parse Hatası
* **İlgili Node:** [Parse AI Output](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1316)
* **Mekanizma:** Model beklenen JSON formatı yerine serbest metin üretirse veya zorunlu alanlar eksik/bozuk gelirse `Parse AI Output` hata fırlatır (`AI Output Valid? = false`).
* **Müşteriye Etkisi:** `Prepare AI Failure` çalışır, yanıt üretilemez.

#### 3.3 İnsan Aktarımı (Handoff) ve Otomasyonun Durdurulması (`pauseAutomation = true`)
* **İlgili Karar Mantığı:** `Parse AI Output` (caseType: `complaint`, `return_complaint`, `non_product`, `human_request`)
* **Mekanizma:** AI müşteri mesajını şikayet, iade, ürün dışı talep veya insan temsilci isteği olarak sınıflandırırsa `pauseAutomation = true` ve `action = 'handoff'` kararını verir.
* **Müşteriye Etkisi:** Bot konuşmayı keser, yöneticiyi uyarır. Sonraki mesajlara bot cevap vermez.

#### 3.4 Üst Üste Belirsiz Mesaj (`unclear` Limitleyici)
* **İlgili Karar Mantığı:** `Parse AI Output` (`unclearCount >= 2`)
* **Mekanizma:** İkinci kez `unclear` gelen müşteride bot pes eder, insana aktarır (`pauseAutomation = true`).
* **Müşteriye Etkisi:** Bot daha fazla otomatik cevap vermeyerek konuşmayı durdurur.

---

### AŞAMA 4: Transactional Outbox, Kilit ve Evolution Devre Kesici Başarısızlıkları

#### 4.1 Outbox Satırının Oluşmaması / DB Transaction Rollback
* **SQL Fonksiyonu:** `whatsapp_ai.complete_ai_batch()`
* **Mekanizma:** AI tamamlandığında `complete_ai_batch` fonksiyonu `whatsapp_ai.deliveries` tablosuna müşteri için bir outbox satırı (`channel = 'customer'`, `status = 'pending'`) eklemek zorundadır.
* **Müşteriye Etkisi:** Outbox satırı oluşmazsa gönderim aşamasına geçilemez.

#### 4.2 Evolution API Circuit Breaker Açık Olması (`circuit_breakers.evolution = open`)
* **İlgili Node'lar:** `Evolution Circuit Gate`, `Evolution Circuit Open?`
* **SQL Fonksiyonu:** `whatsapp_ai.circuit_allows('evolution')`
* **Mekanizma:** Evolution API hataları nedeniyle `evolution` devresi `open` durumuna geçmişse, worker teslimat kuyruğundaki mesajları çekmez.
* **Müşteriye Etkisi:** Cevap outbox'ta bekler, gönderilmez.

#### 4.3 Stale Delivery Kilidi (`status = 'sending'` Kalması)
* **SQL Fonksiyonları:** `whatsapp_ai.claim_deliveries()`, `whatsapp_ai.recover_stale_deliveries()`
* **Mekanizma:** Worker delivery satırını `FOR UPDATE SKIP LOCKED` ile kilitleyip `sending` yapdıktan sonra çökerse satır `sending` olarak kalır.
* **Müşteriye Etkisi:** `recover_stale_deliveries()` çalışana kadar mesaj askıda kalır.

---

### AŞAMA 5: Gönderim Sağlayıcısı (Evolution API) ve Sonuç İşleme Başarısızlıkları

#### 5.1 Evolution API HTTP Hataları (HTTP 400 Bad Request / 401 / 500)
* **İlgili Node:** `Send Delivery` (HTTP POST `https://evo.filtreoto.online/message/sendText/...`)
* **Mekanizma:** Evolution API sunucusundan HTTP 400, 401 veya 500 dönmesi.
* **Müşteriye Etkisi:** `Tag Delivery Error` çalışır. `attempt_count` artırılır.

#### 5.2 WhatsApp Telefon Numarası Format Uyumsuzluğu & `@LID` Harf Hassasiyeti
* **İlgili Node/Hazırlık:** [Prepare Delivery](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1082)
* **Mekanizma:** Telefon numarasının E.164 (`90`) olmaması veya büyük harfli `@LID` eklerinin bozulması HTTP 400 hatası doğurur.
* **Düzeltme:** `Prepare Delivery` node'unda E.164 uluslararası ülke kodu (`90`) otomatik tamamlama, `@LID` için `.toLowerCase()` ve `/^[0-9]{5,20}@lid$/i` validasyonu eklendi.
* **Müşteriye Etkisi:** Numaralandırma kaynaklı HTTP 400 reddi engellendi.

#### 5.3 Evolution WhatsApp Instance Oturumunun Düşmesi
* **Mekanizma:** Evolution API üzerindeki WhatsApp oturumu (instance) düşmüşse.
* **Müşteriye Etkisi:** İletim başarısız olur, `attempt_count` artar.

#### 5.4 Deneme Sınırının Aşılması ve Ölü Mektup (`status = 'dead'`) Durumu
* **SQL Fonksiyonu:** `whatsapp_ai.record_delivery_result()`
* **Mekanizma:** Deneme sayısı 3'e ulaştığında (`attempt_count >= 3`) sistem delivery satırını `status = 'dead'` yapar ve `whatsapp_ai.dead_letters` tablosuna tarihsel ölü mektup audit kaydı ekler.
* **Müşteriye Etkisi:** Sistem bu mesaj için otomatik yeniden deneme yapmayı durdurur.

---

## 5. BULGU VE RİSK SINIFLANDIRMA MATRİSİ (P0 / P1 / P2)

| ID | Önem | Kök Neden / Risk Alanı | Etki | Tespit ve Doğrulama Yöntemi | Durum |
| --- | --- | --- | --- | --- | --- |
| **F-14** | **P0** | Evolution API HTTP 400 / Format Hatası (`status = 'dead'`) | Müşteriye yanıt iletilemez, mesaj düşer. | `Prepare Delivery` E.164 & @LID düzeltmesi | **ÇÖZÜLDÜ** ✅ |
| **F-02** | **P0** | Published Workflow Drift (n8n sürüm uyumsuzluğu) | Repo düzeltmeleri canlıda aktif olmayabilir. | `python tools/check_workflow_drift.py` | PASS ✅ |
| **F-16** | **P0** | OpenAI veya Evolution Circuit Breaker'ın `open` Kalması | Tüm müşteri mesajları veya teslimatlar durur. | `SELECT * FROM whatsapp_ai.service_circuits;` | İzlemede |
| **F-17** | **P1** | 120 Saniyelik Batch Penceresi Gecikmesi | Müşteri yanıtı "geç" alır. | `whatsapp_ai.batches` incelemesi | Tasarım Gereği |
| **F-18** | **P1** | Müşterinin Yanlışlıkla Manuel Moda (`manual_pause = true`) Alınması | Müşteri bot yanıtından mahrum kalır. | `SELECT * FROM whatsapp_ai.customer_states WHERE manual_pause=true;` | Kontrol Edilmeli |
| **F-19** | **P1** | Stale Batch / Stale Delivery Kilidi (`sending` kalması) | Mesaj işleme döngüsünde asılı kalır. | `SELECT whatsapp_ai.run_batch_readiness_probe();` | Recovery aktif |

---

## 6. CANLI TEŞHİS VE VERİTABANI ANALİZ REHBERİ (DIAGNOSTIC RUNBOOK)

Bir müşteri "mesaj attım cevap gelmedi" dediğinde, operatörün sırasıyla çalıştırması gereken **teşhis SQL sorguları**:

### 1. Adım: Son Mesajların ve İlgili Numaranın Durumunu Sorgula
```sql
SELECT id, sender_number, sender_name, payload->>'conversation' AS mesaj, received_at 
FROM whatsapp_ai.messages WHERE sender_number LIKE '%905XXXXXXXXX%' ORDER BY received_at DESC LIMIT 5;
```

### 2. Adım: Batch ve İşleme Durumunu Kontrol Et
```sql
SELECT id, sender_number, status, processing_started_at, created_at, updated_at
FROM whatsapp_ai.batches WHERE sender_number LIKE '%905XXXXXXXXX%' ORDER BY created_at DESC LIMIT 5;
```

### 3. Adım: Müşterinin Manuel Mod Durumunu Kontrol Et
```sql
SELECT phone_number, manual_pause, last_action, updated_at 
FROM whatsapp_ai.customer_states WHERE phone_number LIKE '%905XXXXXXXXX%';
```

### 4. Adım: Outbox ve Teslimat (Deliveries) Durumunu Sorgula (Sütun: attempt_count)
```sql
SELECT id, channel, destination, status, attempt_count, error_message, created_at, sent_at 
FROM whatsapp_ai.deliveries WHERE destination LIKE '%905XXXXXXXXX%' ORDER BY created_at DESC LIMIT 5;
```

### 5. Adım: Ölü Mektup (Dead Letter) Tablosunu Sorgula
```sql
SELECT * FROM whatsapp_ai.dead_letters WHERE destination LIKE '%905XXXXXXXXX%' ORDER BY created_at DESC LIMIT 5;
```

### 6. Adım: Genel Sistem Sağlığını ve Devre Kesicileri Sorgula
```sql
SELECT service, state, consecutive_failures, opened_until, last_error_code FROM whatsapp_ai.service_circuits;
SELECT * FROM whatsapp_ai.get_health_status();
```

---

## 7. RELEASE VE DENETİM KARARI (RELEASE GATE DECISION)

| Kontrol Adı | Sonuç | Durum |
| --- | --- | --- |
| `workflow_validate_json` | PASS | Bağımlılıklar ve JSON şeması doğrulandı |
| `workflow_validate_graph` | PASS | Graph ve bağlantı yönleri doğrulandı |
| `workflow_check_code_nodes` | PASS | Tüm JavaScript Code node sözdizimi doğrulandı |
| `workflow_check_expressions` | PASS | n8n expression ifadeleri doğrulandı |
| `test_workflow_behavior.js` | PASS | `@LID` ve E.164 normalizasyon regresyon testleri geçti |
| `release_gate` | **PASS (100/100)** | Tüm yerel statik güvenlik ve sözleşme testleri geçti |

| Ortam / Kapsam | Karar | Gerekçe |
| --- | --- | --- |
| **Lokal & Kod Mimarisi** | **🟢 GO (100/100 PASS)** | Tüm kod hataları ve alt ajan latent riskleri yamalandı, commit/push edildi. |
| **Canlı Yayın (Production)** | **🔴 NO-GO (Canlı Doğrulama Bekliyor)** | Canlı veritabanı kilitleri, n8n active-published version eşitliği ve Evolution API canlı oturumu operatör tarafından doğrulanana kadar canlıya geçiş yapılmaz. |
