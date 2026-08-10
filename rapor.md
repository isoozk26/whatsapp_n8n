# WhatsApp AI — Müşteri Mesajına Cevap Verilmeme Durumu Uçtan Uca (E2E) Analiz Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 11 Ağustos 2026  
**Kapsam:** Müşteriden gelen WhatsApp mesajının yanıtlanamamasının tüm olası nedenleri, uçtan uca (E2E) yaşam döngüsü analizi, SQL ve log teşhis rehberi, P0/P1/P2 bulgu matrisi ve çözüm önerileri.

---

## 1. YÖNETİCİ ÖZETİ

FiltreOto WhatsApp AI sistemi; Evolution API, n8n workflow motoru, PostgreSQL transactional outbox veritabanı ve OpenAI GPT model katmanından oluşmaktadır. Müşterinin mesaj atıp sistemin cevap vermediği senaryolar, mesajın yaşam döngüsündeki **5 ana aşamadan (Webhook Ingest, Batching & Claiming, AI Inference & Policy Parsing, Outbox Enqueue & Claims, Provider Delivery)** herhangi birinde meydana gelebilecek bir aksaklıktan kaynaklanır.

Bu raporda, bir müşteri mesajının sistem tarafından yanıtsız kalmasının **bütün uçtan uca nedenleri** teknik derinlikte ve somut kod/veri tabanı nesne referanslarıyla incelenmiştir.

### Temel Kök Neden Kategorileri:
1. **Giriş ve Doğrulama Engelleri (Ingest Phase):** Webhook Secret uyuşmazlığı (401), Yönetici Filtresi (`admin_phone_a`/`admin_phone_b` tam eşleşme), Mesaj Normalizasyonu/Geçersiz Event elenmesi.
2. **Kuyruk ve Zamanlama Engelleri (Batching Phase):** 120 saniyelik birleştirme penceresi beklenmesi, `Schedule Trigger` (15sn) durması, OpenAI Devre Kesicisinin (`circuit_breakers.openai`) açık olması (`open`), Manuel Mod (`manual_pause = true`) engeli.
3. **AI ve Politika Engelleri (AI & Policy Phase):** OpenAI API kotası/anahtar hatası, AI JSON çıktı doğrulama başarısızlığı, Otomasyonun Durdurulması (`pauseAutomation = true`) ve İnsan Aktarımı (handoff), Düşük güven skoru / Üst üste belirsiz mesajlar (`unclear` limitleyici).
4. **Outbox ve Kilit Engelleri (Outbox & Claims Phase):** `complete_ai_batch` sırasında outbox kaydı oluşmaması, Evolution Devre Kesicisinin (`circuit_breakers.evolution`) açık olması, Stale (`sending`) kilitlenme durumu.
5. **Gönderim ve Kanal Engelleri (Delivery Phase):** Evolution API HTTP 400/401/500 hataları, WhatsApp numara formatı uyumsuzluğu (`905...`), Evolution instance bağlantısının kopması, Max retry (3 deneme) dolup `dead_letter` seviyesine düşme.

---

## 2. KRİTİK AKIŞ ŞEMASI VE MESAJ YAŞAM DÖNGÜSÜ

```text
[AŞAMA 1: WEBHOOK & INGEST]
Evolution Webhook (POST /evolution-webhook)
  ├─► Validate Webhook Secret (Headers/Query token check) ──[HATA 401]──► Respond Unauthorized (Cevap yok)
  ├─► Load Admin Filter Settings ──► Apply Admin Number Filter
  │     └─► Is Admin Number? (admin_phone_a/b eşleşmesi) ──[EVET]──────► Respond Admin Filtered (Cevap yok)
  ├─► Normalize Payload ──► Valid Event? (Geçersiz/Boş/Status) ──[HAYIR]─► Respond Ignored (Cevap yok)
  ├─► Check Business Hours (Mesai dışı / OOH)
  │     └─► Off Hours? ──► OOH Wait (120s) ──► OOH Cooldown Check ──► Send OOH / Manager Alert
  ├─► Rate Limit Exceeded? ──[EVET]─────────────────────────────────────► Respond Rate Limited 429
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
Prepare Delivery (Payload Formatlama) ──► Send Delivery (HTTP POST to Evolution API /message/sendText)
  ├─► HTTP 200 OK ──► Tag Delivery Success ──► Record Delivery Result (status: 'delivered')
  └─► HTTP 4xx / 5xx / Timeout / Socket Error
        └─► Tag Delivery Error ──► Record Delivery Result (retry_count++)
              ├─► retry_count < 3 ──► Status: 'pending' (Yeniden Denenecek)
              └─► retry_count >= 3 ──► Status: 'dead_letter' (DÜŞTÜ - Yeniden Denenmez, Cevap Gitmez)
```

---

## 3. UÇTAN UCA (E2E) DETAYLI BAŞARISIZLIK VE CEVAP VERMEME NEDENLERİ

### AŞAMA 1: Giriş Webhook, Kimlik Doğrulama ve Ingest Başarısızlıkları

#### 1.1 Webhook Secret Doğrulama Başarısızlığı (`401 Unauthorized`)
* **İlgili Node'lar:** [Validate Webhook Secret](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1144), `Webhook Auth`, `Respond Unauthorized`
* **Mekanizma:** Evolution API'den gelen HTTP isteğindeki `X-Webhook-Secret` header'ı veya `token` query parametresi n8n `N8N_WEBHOOK_SECRET` ile eşleşmezse sistem isteği reddeder (`401`).
* **Müşteriye Etkisi:** Mesaj veritabanına hiç yazılmaz, akış anında durur, müşteriye hiçbir cevap gitmez.

#### 1.2 Yönetici Numarası Filtresine Takılma (`Admin Filtered`)
* **İlgili Node'lar:** [Load Admin Filter Settings](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md#L116), [Apply Admin Number Filter](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1152), `Is Admin Number?`, `Respond Admin Filtered`
* **Mekanizma:** Mesajı atan numara `whatsapp_ai.settings` içindeki `admin_phone_a` veya `admin_phone_b` numaralarından biriyle tam eşleşiyorsa (ve mesaj yetkili komut `++`, `--`, `??` değilse), filtre tetiklenir.
* **Müşteriye Etkisi:** Yönetici numaralarından gelen mesajlara güvenlik gereği otomatik müşteri cevabı dönülmez (`Respond Admin Filtered` -> `200 OK`).

#### 1.3 Geçersiz Event / Format Uyumsuzluğu (`Respond Ignored`)
* **İlgili Node'lar:** [Normalize Payload](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1162), `Valid Event?`, `Respond Ignored`
* **Mekanizma:** Mesaj içeriği boşsa, metin içermeyen desteklenmeyen bir medya tipiyse, grup mesajıysa veya WhatsApp durum (status) güncellemesiyse elenir. `fromMe = true` olan ancak yetkili komut içermeyen mesajlar da işlenmez.
* **Müşteriye Etkisi:** Otomasyon mesaja yanıt vermez.

#### 1.4 Mesai Dışı (Off-Hours / OOH) Bekleme ve Cooldown Engeli
* **İlgili Node'lar:** [Check Business Hours](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1170), `Claim OOH Notification`, `Wait OOH 120 Seconds`, [Build OOH Messages](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1219)
* **Mekanizma:** Mesaj mesai saatleri dışında gelmişse 120 saniyelik bekleme penceresine alınır. Eğer bu müşteriye son 24 saat içinde zaten OOH mesajı gönderilmişse (`ooh_log` cooldown kontrolü), ikinci kez OOH yanıtı atılmaz.
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
* **Mekanizma:** Müşteri mesaj attığında ilk mesaj `status = 'pending'` olarak batch'e eklenir. `claim_ready_batches` fonksiyonu, son mesajın üzerinden **en az 120 saniye** geçmeden batch'i `ready` duruma getirmez (ardışık mesaj birleştirme mantığı).
* **Müşteriye Etkisi:** Müşteri ilk mesajını attıktan sonraki 2 dakika boyunca sistem bilinçli olarak yanıt vermez, mesajların tamamlanmasını bekler.

#### 2.2 Schedule Trigger (Worker Döngüsü) Durması veya n8n Worker Çökmesi
* **İlgili Node:** `Schedule Trigger` (Her 15 saniyede bir çalışır)
* **Mekanizma:** n8n üzerinde workflow `active = false` konuma alınmışsa veya n8n worker servisi çökmüşse, 15 saniyelik zamanlayıcı çalışmaz.
* **Müşteriye Etkisi:** Mesajlar `whatsapp_ai.batches` tablosunda `pending` veya `ready` durumunda kalır, hiçbir zaman AI katmanına çekilmez ve yanıt üretilmez.

#### 2.3 OpenAI Circuit Breaker Açık Olması (`circuit_breakers.openai = open`)
* **İlgili Node'lar:** `OpenAI Circuit Gate`, `OpenAI Circuit Open?`
* **SQL Fonksiyonu:** `whatsapp_ai.circuit_allows('openai')`
* **Mekanizma:** Üst üste gelen OpenAI API hataları nedeniyle `service_circuits` tablosundaki `openai` servisi `state = 'open'` durumuna geçmişse, worker batch'leri veritabanından çekmez (`Claim Ready Batches` bypass edilir).
* **Müşteriye Etkisi:** OpenAI devresi kapanana (veya cooldown süresi dolana) kadar gelen tüm müşteri mesajları yanıtsız kalır.

#### 2.4 Müşteri Numarasının Manuel Modda Olması (`manual_pause = true`)
* **İlgili Tablo/Fonksiyon:** `whatsapp_ai.customer_states`, `manual_pause`
* **Mekanizma:** Müşteri için daha önce yetkili tarafından `++` komutu verilmişse veya sistem şikayet/düşük güven nedeniyle müşteriyi insana aktarmışsa (`manual_pause = true`), AI işlem hattı bu mesajı yanıtlamaz.
* **Müşteriye Etkisi:** Bot otomatik yanıt vermeyi durdurmuştur; yalnızca insan operatör yanıt verebilir.

---

### AŞAMA 3: AI Inference, Çıktı Doğrulama ve Politika Kararı Başarısızlıkları

#### 3.1 OpenAI API Servis Hataları (401, 429, 500, Timeout)
* **İlgili Node'lar:** `AI Agent`, `OpenAI Chat Model1`
* **Mekanizma:** OpenAI API anahtarı geçersizse (`401`), API kotası/rate-limit dolmuşsa (`429`) veya OpenAI tarafında kesinti varsa (`500/503`), node hata fırlatır.
* **Müşteriye Etkisi:** `Prepare AI Failure` tetiklenir, `whatsapp_ai.record_ai_failure()` çalışır. Batch `failed` durumuna geçer veya tekrar denenmek üzere askıda kalır. Müşteriye AI yanıtı gitmez.

#### 3.2 AI Çıktısının JSON Şemasına Uymaması veya Parse Hatası
* **İlgili Node:** [Parse AI Output](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1316)
* **Mekanizma:** Model beklenen JSON formatı yerine serbest metin üretirse veya zorunlu alanlar (`caseType`, `action`, `confidenceScore`) eksik/bozuk gelirse `Parse AI Output` hata fırlatır (`AI Output Valid? = false`).
* **Müşteriye Etkisi:** `Prepare AI Failure` çalışır, yanıt üretilemez.

#### 3.3 İnsan Aktarımı (Handoff) ve Otomasyonun Durdurulması (`pauseAutomation = true`)
* **İlgili Karar Mantığı:** `Parse AI Output` (caseType: `complaint`, `return_complaint`, `non_product`, `human_request`)
* **Mekanizma:** AI müşteri mesajını şikayet, iade, ürün dışı talep veya doğrudan insan temsilci isteği olarak sınıflandırırsa `pauseAutomation = true` ve `action = 'handoff'` kararını verir.
* **Müşteriye Etkisi:** Bot müşteriyle konuşmayı derhal keser, müşteriye bilgilendirme mesajı atabilir veya sessize geçer ve yöneticiye bildirim gönderir. Sonraki mesajlara bot cevap vermez.

#### 3.4 Üst Üste Belirsiz Mesaj (`unclear` Limitleyici)
* **İlgili Karar Mantığı:** `Parse AI Output` (`unclearCount >= 2`)
* **Mekanizma:** Müşteri ne istediği anlaşılamayan mesajlar atıyorsa, ilk `unclear` durumunda bot açıklama ister. İkinci kez `unclear` gelirse bot pes eder, insana aktarır (`pauseAutomation = true`).
* **Müşteriye Etkisi:** Bot daha fazla otomatik cevap vermeyerek konuşmayı durdurur.

---

### AŞAMA 4: Transactional Outbox, Kilit ve Evolution Devre Kesici Başarısızlıkları

#### 4.1 Outbox Satırının Oluşmaması / DB Transaction Rollback
* **SQL Fonksiyonu:** `whatsapp_ai.complete_ai_batch()`
* **Mekanizma:** AI tamamlandığında `complete_ai_batch` fonksiyonu `whatsapp_ai.deliveries` tablosuna müşteri için bir outbox satırı (`channel = 'customer'`, `status = 'pending'`) eklemek zorundadır. SQL işlemi sırasında bir kısıt ihlali veya hata olursa outbox satırı oluşmaz.
* **Müşteriye Etkisi:** AI cevap üretmiş olsa bile outbox'a yazılamadığı için hiçbir zaman gönderim aşamasına geçemez.

#### 4.2 Evolution API Circuit Breaker Açık Olması (`circuit_breakers.evolution = open`)
* **İlgili Node'lar:** `Evolution Circuit Gate`, `Evolution Circuit Open?`
* **SQL Fonksiyonu:** `whatsapp_ai.circuit_allows('evolution')`
* **Mekanizma:** Evolution API bağlantı veya HTTP hataları nedeniyle `evolution` devresi `open` durumuna geçmişse, worker teslimat kuyruğundaki mesajları çekmez (`Claim Deliveries` bypass edilir).
* **Müşteriye Etkisi:** Müşterinin cevabı outbox'ta bekler, gönderim yapılmaz.

#### 4.3 Stale Delivery Kilidi (`status = 'sending'` Kalması)
* **SQL Fonksiyonları:** `whatsapp_ai.claim_deliveries()`, `whatsapp_ai.recover_stale_deliveries()`
* **Mekanizma:** Worker delivery satırını `FOR UPDATE SKIP LOCKED` ile kilitleyip `sending` durumuna getirir. Eğer gönderim sırasında n8n worker bir anda çöker veya kilit açılmadan iş parçacığı sonlanırsa satır `sending` olarak sıkışır.
* **Müşteriye Etkisi:** Mesaj gönderilemez. `recover_stale_deliveries()` kurtarma fonksiyonu çalışana kadar mesaj askıda kalır.

---

### AŞAMA 5: Gönderim Sağlayıcısı (Evolution API) ve Sonuç İşleme Başarısızlıkları

#### 5.1 Evolution API HTTP Hataları (HTTP 400 Bad Request / 401 / 500)
* **İlgili Node:** `Send Delivery` (HTTP POST `https://evo.filtreoto.online/message/sendText/...`)
* **Mekanizma:** Evolution API sunucusundan HTTP 400 (parametre hatası), HTTP 401 (API Key geçersiz) veya HTTP 500 dönmesi.
* **Müşteriye Etkisi:** `Tag Delivery Error` çalışır. Mesaj gönderilemez, hata kaydı tutulur.

#### 5.2 WhatsApp Telefon Numarası Format Uyumsuzluğu
* **İlgili Node/Hazırlık:** [Prepare Delivery](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L1362)
* **Mekanizma:** `number` alanına giden telefon numarasında `+` işareti kalması, ülke kodunun eksik olması veya `@s.whatsapp.net` ekinin Evolution payload beklentisiyle çakışması durumunda Evolution API HTTP `400 Bad Request` yanıtı döner.
* **Müşteriye Etkisi:** Gönderim reddedilir, müşteriye ulaşmaz.

#### 5.3 Evolution WhatsApp Instance Oturumunun Düşmesi (Unconnected / QR Required)
* **Mekanizma:** Evolution API üzerindeki WhatsApp oturumu (instance) düşmüş, telefonun şarjı bitmiş veya WhatsApp Web bağlantısı kopmuşsa.
* **Müşteriye Etkisi:** Evolution API isteği kabul edemez veya dahili hata verir; mesaj müşterinin telefonuna iletilmez.

#### 5.4 Retry Sınırının Aşılması ve Ölü Mektup (`dead_letter`) Durumu
* **SQL Fonksiyonu:** `whatsapp_ai.record_delivery_result()`
* **Mekanizma:** Başarısız bir teslimat denemesi sonrasında `retry_count` artırılır. Deneme sayısı 3'e ulaştığında sistem satırı `dead_letter` olarak işaretler.
* **Müşteriye Etkisi:** Sistem bu mesaj için daha fazla otomatik yeniden deneme yapmaz. Müşteri cevapsız kalır.

---

## 4. BULGU VE RİSK SINIFLANDIRMA MATRİSİ (P0 / P1 / P2)

| ID | Önem | Kök Neden / Risk Alanı | Etki | Tespit ve Doğrulama Yöntemi |
| --- | --- | --- | --- | --- |
| **F-14** | **P0** | Evolution API HTTP 400 / Format Hatası sonucu Mesajın `dead_letter` Olması | Müşteriye üretilen yanıt iletilemez, mesaj kalıcı olarak düşer. | `SELECT * FROM whatsapp_ai.deliveries WHERE status='dead_letter';` |
| **F-02** | **P0** | Published Workflow Drift (Repo `workflow.json` ile Canlı n8n Sürüm Uyumsuzluğu) | Repo'da yazılan düzeltmeler canlıda aktif olmayabilir. | `python tools/check_workflow_drift.py` & `python tools/wf_status.py` |
| **F-16** | **P0** | OpenAI veya Evolution Circuit Breaker'ın `open` Durumda Takılı Kalması | Tüm müşteri mesajları veya tüm teslimatlar tamamen durur. | `SELECT * FROM whatsapp_ai.service_circuits;` |
| **F-17** | **P1** | 120 Saniyelik Batch Penceresi Nedeniyle Müşterinin Yanıtı "Geç" Alması | Müşteri sistemin yanıt vermediğini sanıp tekrar yazar veya görüşmeyi terk eder. | `whatsapp_ai.batches` tablosunda `processing_started_at` incelemesi. |
| **F-18** | **P1** | Müşterinin Yanlışlıkla Manuel Moda (`manual_pause = true`) Alınması | Müşteri bot yanıtlarından tamamen mahrum kalır, sadece insan yanıtı bekler. | `SELECT * FROM whatsapp_ai.customer_states WHERE manual_pause=true;` |
| **F-19** | **P1** | Stale Batch / Stale Delivery Kilidi (`processing` veya `sending` kalması) | Mesaj işleme döngüsünde asılı kalır, ne tamamlanır ne reddedilir. | `SELECT whatsapp_ai.run_batch_readiness_probe();` |
| **F-20** | **P2** | Yönetici Numarası Filtresinin (`admin_phone_a/b`) Yanlış Konfigürasyonu | Yönetici mesajlarına bot yanıt verir veya yönetici bildirimi gitmez. | `SELECT key, value FROM whatsapp_ai.settings WHERE key LIKE 'admin_%';` |

---

## 5. CANLI TEŞHİS VE VERİTABANI ANALİZ REHBERİ (DIAGNOSTIC RUNBOOK)

Bir müşteri "mesaj attım cevap gelmedi" dediğinde, operatörün sırasıyla çalıştırması gereken **teşhis SQL sorguları**:

### 1. Adım: Son Mesajların ve İlgili Numaranın Durumunu Sorgula
```sql
-- Müşterinin mesajı veritabanına girmiş mi?
SELECT 
    id, sender_number, sender_name, 
    payload->>'conversation' AS mesaj, 
    received_at 
FROM whatsapp_ai.messages 
WHERE sender_number LIKE '%905XXXXXXXXX%' -- Müşteri numarası
ORDER BY received_at DESC LIMIT 5;
```
* **Sonuç Yorumu:** Kayıt yoksa -> Webhook Secret (401), Admin Filter veya Ingest Hatalı.

---

### 2. Adım: Batch ve İşleme Durumunu Kontrol Et
```sql
-- Batch durup kalmış mı veya manuel modda mı?
SELECT 
    id, sender_number, status, 
    processing_started_at, 
    created_at, updated_at
FROM whatsapp_ai.batches 
WHERE sender_number LIKE '%905XXXXXXXXX%' 
ORDER BY created_at DESC LIMIT 5;
```
* **Status `pending` (120sn üstü):** Schedule Trigger durmuş olabilir.
* **Status `processing` (5dk üstü):** Worker çökmüş / Stale kalmış.
* **Status `failed`:** AI hatası alınmış.

---

### 3. Adım: Müşterinin Manuel Mod Durumunu Kontrol Et
```sql
SELECT 
    phone_number, manual_pause, 
    last_action, updated_at 
FROM whatsapp_ai.customer_states 
WHERE phone_number LIKE '%905XXXXXXXXX%';
```
* **`manual_pause = true` ise:** Müşteri insan temsilci modundadır. `--` komutu verilmeden bot yanıt vermez.

---

### 4. Adım: Outbox ve Teslimat (Deliveries) Durumunu Sorgula
```sql
-- Müşteriye giden yanıt oluşmuş mu, gönderilmiş mi, dead letter mı?
SELECT 
    id, channel, destination, status, 
    retry_count, error_message, 
    created_at, sent_at 
FROM whatsapp_ai.deliveries 
WHERE destination LIKE '%905XXXXXXXXX%' 
ORDER BY created_at DESC LIMIT 5;
```
* **Status `pending` / `sending`:** Evolution Devre Kesici açık veya Evolution API erişilemiyor.
* **Status `dead_letter`:** Evolution API 3 kez HTTP hatası (örn. 400 Bad Request) döndürmüş.

---

### 5. Adım: Genel Sistem Sağlığını ve Devre Kesicileri Sorgula
```sql
-- Devre kesiciler kapalı (sağlıklı) mı?
SELECT service, state, consecutive_failures, opened_until, last_error_code 
FROM whatsapp_ai.service_circuits;

-- Genel sağlık durumu
SELECT * FROM whatsapp_ai.get_health_status();
```

---

## 6. KALICI İYİLEŞTİRME VE KORUMA ÖNERİLERİ

1. **Evolution API Payload Format Guard'ı:**
   `Prepare Delivery` node'unda telefon numarası normalizasyonu sıkılaştırılmalı, `+` işaretleri ve yetkisiz karakterler temizlenerek Evolution API'nin HTTP 400 döndürmesi önlenmelidir.

2. **Otomatik Stale Recovery Cron İşlemi:**
   `ops_workflow.json` içinde `recover_stale_batches()` ve `recover_stale_deliveries()` fonksiyonlarının her 5 dakikada bir otomatik tetiklendiğinden emin olunmalıdır.

3. **Devre Kesici (Circuit Breaker) Uyarısı:**
   `service_circuits` tablosunda `openai` veya `evolution` servisi `open` duruma geçtiğinde yöneticilere anlık Telegram/WhatsApp alarmı atan izleme mekanizması güçlendirilmelidir.

4. **Manuel Mod Temizliği (Timeout Handoff):**
   Şikayet veya belirsizlik nedeniyle `manual_pause = true` olan müşteriler için opsiyonel bir TTL (örn. 24 saat sonra otomatik sıfırlama veya operatöre hatırlatma) kuralı değerlendirilmelidir.

---

## 7. RELEASE VE DENETİM KARARI (RELEASE GATE DECISION)

| Kontrol Adı | Sonuç | Durum |
| --- | --- | --- |
| `workflow_validate_json` | PASS | Bağımlılıklar ve JSON şeması doğrulandı |
| `workflow_validate_graph` | PASS | Graph ve bağlantı yönleri doğrulandı |
| `workflow_check_code_nodes` | PASS | Tüm JavaScript Code node sözdizimi doğrulandı |
| `workflow_check_expressions` | PASS | n8n expression ifadeleri doğrulandı |
| `release_gate` | **PASS (100/100)** | Tüm yerel statik güvenlik ve sözleşme testleri geçti |

> [!IMPORTANT]
> **OPERASYONEL NOT:** Yerel kod ve release gate testleri %100 PASS durumundadır. Canlı ortamda müşteri mesajının cevapsız kalmaması için Evolution API instance bağlantısının aktif olduğu ve `whatsapp_ai.service_circuits` devresinin `closed` olduğu doğrulanmalıdır.
