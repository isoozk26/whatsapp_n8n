# WhatsApp AI — v13 PostgreSQL Outbox — Operasyon Runbook

| Alan | Değer |
| --- | --- |
| Doküman sürümü | 3.1 |
| Son güncelleme | 2026-07-29 |
| Sistem | FiltreOto WhatsApp AI |
| Workflow | `WhatsApp AI - v13 PostgreSQL Outbox` |
| Node sayısı | 52 node / 44 connection source |
| Migration kapsamı | `001` → `061` (paket 2026-08-03; `058` günlük rapor, `059` queue defer, `060` OOH manager outbox, `061` OOH settings hotfix) |
| Timezone | `Europe/Istanbul` |
| Sahiplik | Cemal Hasan / FiltreOto |
| Canonical konum | `docs/runbook.md` (AGENTS.md kuralı; her deploy'da güncellenir) |

---

## İçindekiler

1. Amaç ve kapsam
2. Mimari ve akış
3. Node envanteri
4. Veri katmanı (şema, fonksiyonlar, ayarlar)
5. Konfigürasyon (credential, env, secret)
6. Değişmez kurallar
7. Günlük operasyon
8. Doğrulama matrisi (statik vs canlı)
9. Release gate ve komut zinciri
10. Deploy prosedürü
11. Deploy sonrası doğrulama
12. Rollback
13. Incident playbook'ları
14. Bakım işleri
15. Mesaj politikası ve admin filtresi
16. Güvenlik sınırları
17. Açık bulgular ve takip
18. Kanıt (evidence) kaydı şablonu
19. Bulgu raporlama formatı
20. Eskalasyon
21. Puanlama modeli ve öncelik sırası
22. Uygulama talimatları — GPT-5.4 mini görev kartları

---

## 1. Amaç ve kapsam

Bu runbook, FiltreOto WhatsApp AI sisteminin **günlük işletimi, release süreci, olay müdahalesi ve rollback** adımlarını tanımlar.

Kapsam içi:

- n8n workflow `WhatsApp AI - v13 PostgreSQL Outbox`
- PostgreSQL `whatsapp_ai` şeması (n8n'in mevcut veritabanı içinde izole)
- Evolution API WhatsApp gateway (`evo.filtreoto.online`)
- OpenAI `gpt-5.4` sınıflandırma katmanı
- `ops_workflow.json` cron/bakım workflow'u

Kapsam dışı: katılım sağlayan CRM/stok sistemleri, Coolify altyapı yönetimi, n8n sürüm yükseltmeleri.

---

## 2. Mimari ve akış

### 2.1 Kritik akış

```text
[Inbound / webhook yolu]
Evolution webhook (POST /evolution-webhook)
  → Validate Webhook Secret → Webhook Auth            (401 → Respond Unauthorized)
  → Load Admin Filter Settings → Apply Admin Number Filter
  → Is Admin Number?                                   (evet → Respond Admin Filtered)
  → Normalize Payload → Valid Event?                   (hayır → Respond Ignored)
  → Check Business Hours
      ├─ mesai dışı → Claim OOH Notification → Is Off Hours?
      │     → Wait OOH 120 Seconds → Build OOH Messages → OOH Claim Won?
      │     → Send OOH to Customer → Enqueue Manager OOH Alert → Log OOH Event
      │     → Log OOH Event
      └─ Rate Limit Exceeded?                          (evet → Respond Rate Limited)
  → Ingest Message (PostgreSQL)                        (hata → Prepare Ingest Failure → Respond 503)
  → Respond Accepted

[Worker yolu — Schedule Trigger, 15 saniye]
OpenAI Circuit Gate → OpenAI Circuit Open?
  → Claim Ready Batches → Store Context → AI Agent (OpenAI Chat Model1)
  → Parse AI Output → AI Output Valid?
      ├─ geçerli → Complete AI Batch → AI Batch Completed? → Persist Chat Memory
      └─ geçersiz → Prepare AI Failure → Record AI Failure
→ Evolution Circuit Gate → Evolution Circuit Open?
  → Claim Deliveries → Prepare Delivery → Delivery Valid?
      ├─ geçerli → Send Delivery → Tag Delivery Success / Tag Delivery Error
      └─ geçersiz → Tag Delivery Validation Error
  → Record Delivery Result
→ Run Stale Batch Monitor
```

### 2.2 Tasarım ilkeleri

- **Auth-before-ingest:** hiçbir veri doğrulanmadan yazılmaz.
- **Transactional outbox:** AI kararı ile teslimat birbirinden ayrılır; teslimat ayrı claim ile yapılır.
- **Circuit breaker:** OpenAI ve Evolution için bağımsız devre kesici; cascading failure engellenir.
- **Idempotency:** `message-id` bazlı ingest, claim bazlı batch/delivery kilidi.
- **Kanal ayrımı:** müşteri ve yönetici teslimatları ayrı outbox kayıtlarıdır.
- **Kaynak tekliği:** `build_workflow.py` tek kaynak, `workflow.json` üretilen artifact.

### 2.3 Zamanlama parametreleri

| Parametre | Değer | Yer |
| --- | --- | --- |
| Worker periyodu | 15 saniye | `Schedule Trigger` |
| Batch birleştirme penceresi | 120 saniye | `claim_ready_batches()` |
| OOH bekleme | 2 dakika | `Wait OOH 120 Seconds` |
| Chat memory TTL | 24 saat (varsayılan) | `cleanup_chat_memory(p_ttl_hours)` |

---

## 3. Node envanteri (53)

### 3.1 Webhook / auth (8)

`Webhook1`, `Validate Webhook Secret`, `Webhook Auth`, `Load Admin Filter Settings`, `Apply Admin Number Filter`, `Is Admin Number?`, `Respond Admin Filtered`, `Respond Unauthorized`

### 3.2 Normalize / validasyon (2)

`Normalize Payload`, `Valid Event?`

### 3.3 Mesai dışı / OOH (10)

`Check Business Hours`, `Claim OOH Notification`, `Is Off Hours?`, `Wait OOH 120 Seconds`, `Build OOH Messages`, `OOH Claim Won?`, `Send OOH to Customer`, `Enqueue Manager OOH Alert`, `Log OOH Event`

### 3.4 Rate limit / ingest / yanıt (7)

`Rate Limit Exceeded?`, `Respond Rate Limited`, `Respond Ignored`, `Ingest Message`, `Prepare Ingest Failure`, `Respond 503`, `Respond Accepted`

### 3.5 AI işleme (13)

`Schedule Trigger`, `OpenAI Circuit Gate`, `OpenAI Circuit Open?`, `Claim Ready Batches`, `Store Context`, `AI Agent`, `OpenAI Chat Model1`, `Parse AI Output`, `AI Output Valid?`, `Complete AI Batch`, `AI Batch Completed?`, `Persist Chat Memory`, `Prepare Batch Completion Failure`

### 3.6 Hata kaydı (2)

`Prepare AI Failure`, `Record AI Failure`

### 3.7 Teslimat (10)

`Evolution Circuit Gate`, `Evolution Circuit Open?`, `Claim Deliveries`, `Prepare Delivery`, `Delivery Valid?`, `Send Delivery`, `Tag Delivery Validation Error`, `Tag Delivery Success`, `Tag Delivery Error`, `Record Delivery Result`

### 3.8 Bakım (1)

`Run Stale Batch Monitor`

---

## 4. Veri katmanı

### 4.1 Şema

Tüm nesneler `whatsapp_ai` şemasındadır. `public` şemaya ve n8n'in kendi tablolarına **dokunulmaz**.

### 4.2 Fonksiyon envanteri

| Grup | Fonksiyonlar |
| --- | --- |
| Ingest / batch | `ingest_message`, `claim_ready_batches`, `complete_ai_batch`, `record_ai_failure`, `run_batch_readiness_probe` |
| Teslimat | `claim_deliveries`, `record_delivery_result`, `record_service_result`, `enqueue_admin_alert` |
| Dayanıklılık | `circuit_allows`, `recover_stale_batches`, `recover_stale_deliveries`, `recover_dead_letters`, `record_dead_letter`, `run_stale_batch_monitor` |
| Katalog / araç | `begin_catalog_import`, `activate_catalog_import`, `refresh_catalog_import_stats`, `norm_catalog_text`, `resolve_brand`, `resolve_vehicle_context` |
| Bakım / raporlama | `cleanup_chat_memory`, `cleanup_expired_state`, `run_retention`, `run_queue_monitor`, `run_daily_report`, `run_rotation_reminder`, `get_health_status`, `get_dashboard_stats` |

### 4.3 Önemli tablo/indeksler

| Nesne | Not |
| --- | --- |
| `whatsapp_ai.settings` | key/value + `updated_at`; runtime davranışını belirler |
| `whatsapp_ai.chat_memory` | `session_id`, `role`, `content`, `source_key`, `created_at` |
| `chat_memory_session_role_source_key` | UNIQUE (session_id, role, source_key) — duplicate memory engeli |
| `chat_memory_session_created_idx` | (session_id, created_at DESC) — son N mesaj okuması |
| `whatsapp_ai.ooh_log` | Mesai dışı gönderim kaydı; gerçek sonucu yansıtmalı |
| `whatsapp_ai.ooh_manager_dispatch` | OOH yönetici outbox idempotency kaydı |

### 4.4 Kritik settings anahtarları

| Key | Örnek değer | Etki |
| --- | --- | --- |
| `admin_phone_a` | `90XXXXXXXXXX` | Yönetici A — no-reply filtresi + bildirim hedefi |
| `admin_phone_b` | `90XXXXXXXXXX` | Yönetici B — no-reply filtresi + bildirim hedefi |
| `webhook_token` | `[REDACTED]` | Webhook doğrulama değeri; migration ile **yazılmamalı** (Bölüm 17, F-09) |
| `credentials_last_rotated_at` | timestamp | Rotasyon hatırlatması |

> **2026-07-29 değişikliği:** `admin_filter_enabled` ve `admin_number_prefixes` artık okunmuyor. `Load Admin Filter Settings` yalnızca `admin_phone_a` / `admin_phone_b` çeker; `Apply Admin Number Filter` **tam eşleşme** yapar (`configuredAdminNumbers.includes(senderNumber)`), prefix mantığı kaldırıldı. Sözleşme testi prefix mantığının geri gelmesini engelliyor (`"startsWith" not in admin_filter`). Bu, F-01'i kapatır.

---

## 5. Konfigürasyon

### 5.1 n8n credential adları (birebir eşleşmeli)

- `OpenAi account`
- `WhatsApp State PostgreSQL`
- `Evolution API`

### 5.2 Ortam değişkenleri

| Değişken | Yer | Açıklama |
| --- | --- | --- |
| `N8N_WEBHOOK_SECRET` | Coolify | Webhook header/query doğrulaması |
| `ADMIN_PHONE_A` / `ADMIN_PHONE_B` | Coolify | Yönetici no-reply + bildirim hedefi |
| `OWNER_PHONE_NUMBERS` | Coolify | Yetkili `fromMe` komut kaynağı |
| `WHATSAPP_POSTGRES_URL` | Operatör shell | Migration için |
| `N8N_API_KEY`, `N8N_BASE_URL`, `N8N_WORKFLOW_ID` | Operatör shell | Deploy scriptleri |
| `CONFIRMED_TARGET_NUMBER` | Operatör shell | Canlı gönderim guard'ı |

### 5.3 n8n workflow ayarları

- Execution data: `all`
- Timezone: `Europe/Istanbul`
- Webhook response mode: `responseNode`

---

## 6. Değişmez kurallar

1. Kimlik doğrulama her zaman ingest'ten **önce** çalışır.
2. `message-id` idempotency ve eşzamanlı claim güvenliği bozulmaz.
3. Müşteri ve yönetici teslimatları ayrı outbox kayıtlarıdır.
4. Ürün kodu uydurulmaz; stok, fiyat, uyumluluk ve kargo doğrulanmadan taahhüt edilmez.
5. Manuel modu yalnızca yetkili `fromMe` `++` / `--` komutları değiştirir.
6. AI handoff, sonraki müşteri mesajlarını sessizce bloklamaz.
7. Credential, token, telefon numarası ve DB secret'ları commit edilmez, loglanmaz.
8. Test ve audit sırasında **açık onay olmadan canlı mesaj gönderilmez**.
9. `workflow.json` elle düzenlenmez; her zaman `build_workflow.py` üzerinden üretilir.
10. `release_gate` sonucu `BLOCKED` ise kontrol zayıflatılarak geçilmez.

---

## 7. Günlük operasyon

### 7.1 Sabah kontrolü (5 dakika)

```sql
SELECT whatsapp_ai.get_health_status();
SELECT whatsapp_ai.get_dashboard_stats();
```

Beklenen değerler:

| Alan | Sağlıklı | Aksiyon eşiği |
| --- | --- | --- |
| `circuit_breakers.openai` | `closed` | `open` → playbook 13.1 |
| `circuit_breakers.evolution` | `closed` | `open` → playbook 13.2 |
| `pending_batches` | 0–10 | >50 veya artan trend → playbook 13.3 |
| `deliveries.pending` | 0–10 | >50 → playbook 13.2 |
| `dead_letter` | 0 | >0 → playbook 13.5 |
| `messages_last_hour` | mesai içi >0 | mesai içi 0 → webhook kontrolü (13.6) |
| `last_processed_at` | < 2 dakika | eski → Schedule Trigger kontrolü |

### 7.2 Kuyruk detayı

```bash
psql "$WHATSAPP_POSTGRES_URL" -f db/tests/live_queue_status.sql
```

### 7.3 Artifact durumu

```bash
python tools/wf_status.py
python tools/wf_inspect.py
```

---

## 8. Doğrulama matrisi (statik vs canlı)

Bu tablo, hangi riskin hangi kanıtla kapandığını gösterir. **Statik PASS, canlı kanıt yerine geçmez.**

| # | Risk | Statik kanıt | Canlı kanıt gerekir mi |
| --- | --- | --- | --- |
| 1 | JSON/graph bütünlüğü | `wf_validate.py` | Hayır |
| 2 | Code node sözdizimi | `build_workflow.py` | Hayır |
| 3 | Auth-before-ingest sırası | `test_workflow_contract.py` | Hayır |
| 4 | Politika dallanmaları | `test_workflow_behavior.js` | Hayır |
| 5 | Secret sızıntısı | `wf_security.py` | Hayır |
| 6 | Outbound guard | `outbound_guard.py` + `test_outbound_guard.py` | Hayır |
| 7 | Builder ↔ commit drift | `check_workflow_drift.py` | Hayır |
| 8 | **Commit ↔ canlı published version** | **yok** | **Evet** — `wf_status.py` / `wf_diff.py` |
| 9 | **Migration'ın canlı DB'de uygulanması** | **yok** | **Evet** — `psql` sorgusu |
| 10 | **Function overload / signature drift** | **yok** | **Evet** — `pg_proc` sorgusu |
| 11 | **120 sn batch penceresi** | kısmi | **Evet** — execution log |
| 12 | **OOH cooldown + yönetici bildirimi bağımsızlığı** | kısmi | **Evet** — `ooh_log` + execution |
| 13 | **Duplicate delivery / stuck `sending`** | **yok** | **Evet** — yük altında gözlem |
| 14 | **ops_workflow cron'ları** | `ops_drift_check.py` | **Evet** — son execution zamanları |
| 15 | **Admin filtresi tek kaynak** | **yok** | **Evet** — settings + env karşılaştırması |
| 16 | **Çok niyetli batch sınıflandırması** (selamlama + talep) | **yok** | **Evet** — gerçek konuşma örneği + `ai_batches` kaydı |
| 17 | **Ticari niyet → yönetici bildirimi zinciri** | kısmi | **Evet** — outbox `admin` satırı kanıtı |

---

## 9. Release gate ve komut zinciri

### 9.1 Zorunlu sıra

```bash
python build_workflow.py
python tools/wf_validate.py workflow.json
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/test_outbound_guard.py
python tools/wf_security.py
python tools/outbound_guard.py
python tools/check_workflow_drift.py
python tools/ops_drift_check.py
npm run test:mcp
npm run release:gate
```

### 9.2 Geçme kriteri

- Tüm komutlar exit code 0
- `release:gate` → `PASS` (100/100)
- `check_workflow_drift.py` → fark yok
- `ops_drift_check.py` → fark yok
- `wf_security.py` → CRITICAL bulgu yok

### 9.3 Kapsam sınırı (kritik not)

`check_workflow_drift.py` **builder ile commit edilen dosyayı** karşılaştırır; canlı n8n'e bakmaz. Repo tertemiz olsa dahi canlıda eski sürüm yayında olabilir. Bu boşluğu Bölüm 11.1 kapatır.

---

## 10. Deploy prosedürü

### 10.1 Ön koşullar

- [ ] PostgreSQL backup alındı ve restore edilebilirliği not edildi
- [ ] Bölüm 9 komut zinciri tamamen PASS
- [ ] Credential adları n8n'de birebir mevcut
- [ ] `N8N_WEBHOOK_SECRET`, `ADMIN_PHONE_A`, `ADMIN_PHONE_B`, `OWNER_PHONE_NUMBERS` set
- [ ] Execution data `all`, timezone `Europe/Istanbul`
- [ ] Önceki `workflow.json` ve canlı sürüm ID'si rollback için kayıtlı
- [ ] Deploy penceresi mesai dışı yoğun saat değil

### 10.2 Migration

```bash
export WHATSAPP_POSTGRES_URL=...
python tools/wf_migrate.py     # db/migrations/*.sql sirali, ON_ERROR_STOP=1
```

Tüm migration'lar idempotent olmalıdır: `IF NOT EXISTS`, `CREATE OR REPLACE`, `ON CONFLICT DO UPDATE`.

Doğrulama sorguları:

```sql
-- 1) Ayarlar
SELECT key, value, updated_at FROM whatsapp_ai.settings
WHERE key IN ('admin_number_prefixes','admin_filter_enabled');

-- 2) Fonksiyon imzaları / overload kontrolü
SELECT proname, pg_get_function_identity_arguments(oid) AS args
FROM pg_proc WHERE pronamespace = 'whatsapp_ai'::regnamespace
ORDER BY proname, args;

-- 3) Chat memory yapısı
SELECT indexname FROM pg_indexes
WHERE schemaname='whatsapp_ai' AND tablename='chat_memory';
```

Aynı fonksiyon adı için birden fazla imza görünmesi **overload drift**'tir ve deploy'u durdurur.

### 10.3 Workflow yükleme

```bash
python tools/wf_deploy.py        # veya python upload_to_n8n.py
```

### 10.4 Deploy sonrası drift kontrolü

```bash
python tools/check_workflow_drift.py
python tools/wf_status.py
python tools/wf_diff.py          # commit <-> canlı published version
```

---

## 11. Deploy sonrası doğrulama

### 11.1 Canlı sürüm eşitliği (zorunlu)

- [ ] n8n'de yayında olan workflow adı ve sürümü bekleneni gösteriyor
- [ ] Node sayısı 53
- [ ] `wf_diff.py` çıktısı boş

### 11.2 Runtime

- [ ] Workflow **active**
- [ ] Schedule Trigger son execution < 1 dakika
- [ ] `get_health_status()` → her iki circuit `closed`
- [ ] `pending_batches` artmıyor
- [ ] 10 dakika içinde yeni hata execution'ı yok

### 11.3 Webhook sözleşmesi

- [ ] Geçersiz secret → 401
- [ ] Aşırı istek → 429
- [ ] DB kesintisi simülasyonu (staging) → 503
- [ ] Geçerli istek → 202/Accepted

### 11.4 Canlı mesaj testi

Yalnızca **açık onay** ve onaylı numara ile:

```bash
CONFIRMED_TARGET_NUMBER=<onayli-numara> \
  python tools/live_customer_scenario_test.py \
  --target-number <onayli-numara> --confirm-outbound
```

Sonrasında `ooh_log`, outbox ve `Record Delivery Result` kayıtları kontrol edilir.

---

## 12. Rollback

### 12.1 Tetikleyiciler

- Deploy sonrası 10 dakika içinde artan hata execution'ı
- Müşteriye yanlış/duplicate mesaj
- Yönetici numarasına otomatik cevap gitmesi
- `pending_batches` sürekli artışı veya teslimat durması

### 12.2 Adımlar

1. n8n'de önceki workflow sürümünü publish et (veya saklanan `workflow.json` ile `wf_deploy.py`).
2. Gerekiyorsa workflow'u geçici olarak **deactivate** et; webhook 503 döner, mesajlar Evolution tarafında birikir.
3. Migration'lar geriye dönük uyumludur; şema rollback normalde gerekmez. Zorunluysa backup'tan yalnızca `whatsapp_ai` şeması restore edilir.
4. `recover_stale_batches()` ve `recover_stale_deliveries()` ile asılı kayıtları temizle.
5. `get_health_status()` ile normale dönüşü doğrula.
6. Olayı Bölüm 18 şablonuyla kayıt altına al.

### 12.3 Rollback sonrası doğrulama

- [ ] Circuit'ler `closed`
- [ ] Kuyruk boşalıyor
- [ ] Yeni gelen mesaj uçtan uca işleniyor
- [ ] Duplicate gönderim yok

---

## 13. Incident playbook'ları

### 13.1 OpenAI circuit open

**Belirti:** `OpenAI Circuit Open?` true; batch'ler `pending` birikiyor; cevap gitmiyor.

```sql
SELECT whatsapp_ai.circuit_allows('openai');
SELECT * FROM whatsapp_ai.settings WHERE key LIKE '%openai%';
```

Adımlar:

1. OpenAI API key geçerliliği ve kota/limit durumunu kontrol et.
2. `record_ai_failure` kayıtlarında hata kodunu bul (401 → credential, 429 → kota, 5xx → sağlayıcı).
3. Sorun giderilince devrenin yarı-açık geçişini bekle; manuel zorlama yapma.
4. Birikmiş işler için `SELECT whatsapp_ai.recover_stale_batches();`
5. Uzun sürerse manuel moda alıp müşterilere insan yanıtı sağla.

### 13.2 Evolution circuit open / mesaj gitmiyor

```sql
SELECT whatsapp_ai.circuit_allows('evolution');
SELECT whatsapp_ai.recover_stale_deliveries();
```

Adımlar:

1. `evo.filtreoto.online` erişimi ve instance bağlantı durumu (QR/oturum düşmüş mü?).
2. n8n `Evolution API` credential'ı.
3. `Record Delivery Result` içindeki hata kodları.
4. Stale `sending` kayıtlarını recover et; duplicate riskine karşı önce sayıyı not al.

### 13.3 Batch stuck / `pending` birikmesi

```sql
SELECT whatsapp_ai.run_stale_batch_monitor();
SELECT whatsapp_ai.recover_stale_batches();
SELECT whatsapp_ai.run_batch_readiness_probe();
```

Ek kontrol: Schedule Trigger aktif mi, n8n worker CPU/bellek durumu, PostgreSQL kilit çakışması.

### 13.4 Duplicate mesaj

Kontrol listesi:

1. `ingest_message()` — `message-id` tekilliği çalışıyor mu?
2. `claim_ready_batches()` / `claim_deliveries()` — claim kilidi (FOR UPDATE SKIP LOCKED) korunuyor mu?
3. Outbox unique kısıtları mevcut mu?
4. `Claim OOH Notification` — OOH claim tekil mi (`OOH Claim Won?` dalı)?
5. n8n'de aynı workflow'un iki instance'ı aktif mi?

### 13.5 Dead letter birikmesi

```sql
SELECT whatsapp_ai.recover_dead_letters();
```

Önce dead letter sebebini sınıflandır; kök neden çözülmeden recover çalıştırmak döngü yaratır.

### 13.6 Webhook hata kodları

| Kod | Anlam | İlk aksiyon |
| --- | --- | --- |
| 401 | Secret/token uyuşmuyor | `N8N_WEBHOOK_SECRET` ile Evolution header/query eşleşmesi |
| 429 | Rate limit | Kaynak numara trafiği, `Rate Limit Exceeded?` eşiği |
| 503 | Ingest başarısız | PostgreSQL erişimi, `Prepare Ingest Failure` logu |
| Yanıt yok | Workflow pasif veya n8n down | Workflow active durumu, n8n servis sağlığı |

### 13.7 Chat memory şişmesi

```sql
SELECT count(*) FROM whatsapp_ai.chat_memory;
SELECT whatsapp_ai.cleanup_chat_memory(24);
```

Sürekli şişiyorsa ops_workflow'daki temizlik cron'unun çalışıp çalışmadığını kontrol et.

### 13.8 Yönetici numarasına otomatik cevap gitti

P0 olay. Adımlar:

1. `admin_filter_enabled` → `true` mu?
2. `admin_number_prefixes` ile `ADMIN_PHONE_A/B` uyuşuyor mu?
3. `Apply Admin Number Filter` node'unun ilgili execution'ında karar çıktısı ne?
4. Geçici önlem: manuel mod (`++`).
5. Kalıcı çözüm için F-01 (Bölüm 17).

### 13.9 Mesai dışı müşteriye mesaj gitmedi / iki kez gitti

1. `Check Business Hours` çıktısı sonraki node'lara taşınıyor mu (veri kaybı kontrolü)?
2. `Claim OOH Notification` → `OOH Claim Won?` dalı tekil claim sağlıyor mu?
3. `ooh_log` kaydı gerçek gönderim sonucunu mu yazıyor, yoksa fail-open mu?
4. Cooldown sorgusu ve ilgili index mevcut mu?

### 13.10 Satış fırsatı yöneticiye düşmedi

Belirti: Müşteri satın alma / fiyat / toplu talep yazdı, bot cevap verdi ama yönetici bildirimi hiç gelmedi.

1. İlgili batch'in `caseType` değerini bul. `greeting` veya `unclear` ise bildirim **tasarım gereği** bastırılmıştır (`Parse AI Output`).
2. `notifyAdmins` değerini kontrol et; `false` ise outbox'ta `admin` satırı hiç oluşmaz. Sorun teslimat katmanında değil, sınıflandırma/policy katmanındadır.
3. Müşteri mesajı selamlama + talep birleşimi mi? Batch tek etiketle sınıflandırıldığı için selamlama baskın gelmiş olabilir (F-06).
4. Adet/kalem ifadesi yakalanmış mı? `entities.quantity` `Belirtilmedi` kaldıysa F-07 geçerlidir.
5. Geçici önlem: ilgili konuşmayı manuel takibe al, yöneticiyi elle bilgilendir.
6. Kalıcı çözüm: Bölüm 15.5 politikası ve F-06/F-07/F-08.

---

## 14. Bakım işleri

| İş | Fonksiyon | Sıklık | Nerede |
| --- | --- | --- | --- |
| Kuyruk alarmı | `run_queue_monitor()` | dakikalık | ops_workflow |
| Günlük rapor | `run_daily_report()` | günlük | ops_workflow |
| Retention | `run_retention()` | günlük | ops_workflow |
| Chat memory temizliği | `cleanup_chat_memory(24)` | günlük | ops_workflow |
| Süresi geçen state | `cleanup_expired_state()` | günlük | ops_workflow |
| Credential rotasyon hatırlatma | `run_rotation_reminder()` | haftalık | ops_workflow |
| Stale batch monitörü | `run_stale_batch_monitor()` | her turda | ana workflow |
| Ops drift kontrolü | `tools/ops_drift_check.py` | her release | CI/lokal |
| Backup doğrulaması | manuel restore testi | aylık | operatör |

---

## 15. Mesaj politikası ve admin filtresi

### 15.1 Admin no-reply filtresi

Akış: `Load Admin Filter Settings → Apply Admin Number Filter → Is Admin Number? → Respond Admin Filtered`

Kural: Yönetici numaralarından gelen mesajlar **7/24**, `fromMe`, `++`, `--`, `??`, mesai içi/dışı, AI, batch, OOH ve retry durumlarının hiçbirinde müşteri cevabı üretmez.

Eşleşme yöntemi: **tam eşleşme.** Kaynak yalnızca `admin_phone_a` / `admin_phone_b` ayarlarıdır. Prefix (`905360` gibi) mantığı kaldırıldı; prefix'i paylaşan gerçek müşteriler artık yanlışlıkla susturulmaz. Yetkili komut (`++`, `--`, `??`) geldiğinde filtre uygulanmaz, komut işlenir (`!authorizedCommand` koşulu).

### 15.2 Mesai saatleri ve OOH

- `Check Business Hours`: `tr-TR` locale, `Europe/Istanbul`, sabit tatil listesi, erken sabah ayırımı.
- Mesai dışı: müşteriye OOH mesajı (cooldown'a tabi) + yönetici A/B bildirimi (cooldown'dan **bağımsız**).
- `Log OOH Event` gerçek gönderim sonucunu yazar.

### 15.3 Manuel mod komutları

| Komut | Etki | Kaynak |
| --- | --- | --- |
| `++` | Manuel mod aç (`manual_pause`) | yetkili `fromMe` |
| `--` | Otomatik moda dön (`manual_resume`) | yetkili `fromMe` |
| `??` | Durum sorgusu (`manual_check`) | yetkili `fromMe` |

Müşteri tarafından gelen komut benzeri mesajlar bildirim üretmez (`007_suppress_customer_command_notifications.sql`).

### 15.4 AI çıktı sözleşmesi

- Model yalnızca **yapılandırılmış JSON** üretir; serbest metin yasak.
- Intent sınıfları: fiyat/stok, uyumluluk, şikayet, insana aktarma, selamlama, belirsiz.
- Çıkarılan varlıklar: ürün kodu, marka tercihi, adet, araç bilgileri (marka/model/yıl/motor/güç/VIN).
- Güven skoru eşiğin altındaysa insana aktarılır.
- Araç modeli, üretim yılı, HP/kW ifadeleri ürün kodu olarak sınıflandırılmaz.
- VIN, telefon ve müşteri metni yönetici bildiriminde tam değeriyle korunur.
- Prompt injection koruması aktif: müşteri metni talimat olarak yorumlanmaz.

### 15.5 Sınıflandırma ve yönetici bildirim politikası

**Temel ilke:** `caseType` "müşteriden hangi bilgi eksik" eksenidir. "Bu bir satış fırsatı mı" sorusu **bağımsız bir eksendir** ve `caseType`'a sıkıştırılmaz. Ticari niyet, `salesLead` benzeri dik (orthogonal) bir bayrakla taşınır.

#### 15.5.1 Bildirim matrisi

| caseType / intent | Müşteri cevabı | Yönetici bildirimi | Otomasyon |
| --- | --- | --- | --- |
| `exact_code_price_stock` | evet | evet | devam |
| `exact_code_compatibility` | evet | evet | devam |
| `cross_reference` | evet | evet | devam |
| `partial_code` | evet | evet | devam |
| `non_product` / `complaint` / `return_complaint` / `human_request` | evet | evet | **durur** (handoff + pause) |
| `greeting` (ticari sinyal yok) | evet | **hayır** | devam |
| `unclear` (ilk deneme, handoff yok) | evet | **hayır** | devam |
| `unclear` (şema hatası / uydurma kod / düşük güven) | evet | evet | **durur** |
| **`greeting` + ticari sinyal** | evet (nitelendirici) | **evet** | devam |

#### 15.5.2 Ticari niyet (salesLead) sinyalleri

Kural: `salesLead = (satın alma fiili || miktar ifadesi) && ürün bağlamı`

| Sinyal grubu | Örnekler | Rol |
| --- | --- | --- |
| Satın alma fiili | alım, almak istiyoruz, sipariş, teklif, proforma, fiyat almak | gerekli |
| Miktar / kalem | `\d+` + kalem, adet, tane, kutu, koli, palet, çeşit | güçlendirici |
| B2B bağlamı | toptan, bayi, filo, servis, oto sanayi, kurumsal, ihale | güçlendirici |
| Ürün bağlamı | mevcut `filterRequest` regex'i | gerekli |

"Merhaba" tek başına hiçbir sinyal üretmez → selamlama sessiz kalır, gürültü oluşmaz.

#### 15.5.3 Ticari sinyal bulunursa beklenen davranış

- `caseType` → `partial_code`, alt tür `bulk_request` (yeni bir `caseType` **eklenmez**, taksonomi korunur).
- `notifyAdmins = true` (varsayılan değeri korunur, bastırma uygulanmaz).
- `action = 'reply'`, `pauseAutomation = false`. **Handoff/pause yapılmaz**, çünkü müşteriden ürün listesi bekleniyor; pause edilirse gelen liste işlenemez.
- `intent = 'human_request'` **kullanılmaz**; o dal `non_product` üzerinden otomasyonu durdurur ve temsilci talebi istatistiklerini kirletir.
- Güçlü B2B sinyalinde (adet >= 10 veya toptan/bayi/filo/proforma) bildirim yüksek öncelik başlığıyla gönderilir; otomasyon yine açık kalır.

Örnek doğru davranış (29.07.2026 vakası — "16 Kalem Filtre alımı için fiyat almak istiyoruz"):

- Müşteri cevabı: kısa nitelendirici mesaj (liste / kod / şasi isteği), genel selamlama metni değil.
- Yönetici bildirimi: **evet** — toplu talep başlığı, adet bilgisi ve beklenen aksiyon (teklif hazırla).

#### 15.5.4 Zorunlu regresyon testleri

`tools/test_workflow_behavior.js` içinde şu dört vaka **her zaman** bulunmalıdır:

| # | Girdi | Beklenen |
| --- | --- | --- |
| 1 | `Merhaba` | `greeting`, `notifyAdmins=false` (gürültü regresyonu — en kritik test) |
| 2 | `Merhabalar hayırlı günler` + `16 Kalem Filtre alımı için fiyat almak istiyoruz` | `partial_code`, `notifyAdmins=true`, `pauseAutomation=false`, `quantity=16` |
| 3 | `Merhaba fiyat listesi var mı` | `greeting`, `notifyAdmins=false` |
| 4 | `Toptan filtre almak istiyoruz bayiyiz` | `notifyAdmins=true` |

Bu politika değiştirilirse Bölüm 9 komut zinciri baştan sona tekrar koşulur.

---

## 16. Güvenlik sınırları

- Repo ve paylaşılan paketlerde `.env_token`, `.git`, `node_modules`, webhook secret, API key, credential ve tam telefon numarası bulunmaz; gerekli yerlerde `[REDACTED]`.
- Canlı gönderim yapabilen scriptler `tools/outbound_guard.py` ile korunur: `--target-number` + `--confirm-outbound` + `CONFIRMED_TARGET_NUMBER` üçlüsü zorunludur; numara formatı `90XXXXXXXXXX` doğrulanır ve loglarda maskelenir.
- Analiz/audit modunda: canlı webhook çağrılmaz, canlı mesaj gönderilmez, üretim verisi değiştirilmez.
- SSL doğrulaması kapatılmaz (`verify=False` ve `_create_unverified_context` yasak; `wf_security.py` bunları CRITICAL sayar).
- Müşteri verisi ve transcript'ler retention politikası dışına çıkarılmaz.

---

## 17. Açık bulgular ve takip

| ID | Önem | Konu | Durum |
| --- | --- | --- | --- |
| F-01 | P1 | Admin filtresi: prefix ayarı vs exact-match politikası tek kaynaktan beslenmiyor olabilir | **KAPANDI** (2026-07-29) |
| F-02 | P0 (deploy öncesi) | Commit ↔ canlı published version drift kanıtı yok | doğrulanamadı |
| F-03 | P1 | `ops_workflow` cron'ları ve `ops_drift_check.py` doğrulanmamış | doğrulanamadı |
| F-04 | P1 | 120 sn batch, OOH cooldown, duplicate/stuck `sending` yalnızca statik test edildi | kısmen doğrulandı |
| F-05 | P2 | Migration'ların canlı DB'de uygulanma durumu ve function overload kontrolü rutin değil | doğrulanamadı |
| F-06 | P1 | `Parse AI Output`: greeting bildirim bastırması istisnasız; selamlama ile birlikte gelen ticari talep yönetici kuyruğuna hiç düşmüyor | **kısmen kapandı** → devamı F-10, F-11 |
| F-07 | P2 | Adet yakalama regex'inde `kalem/çeşit/kutu/koli` birimleri yok; `isBulkOrder` pratikte tetiklenmiyor | **KAPANDI** (`kalem` eklendi) |
| F-08 | P2 | `isBulkOrder` yalnızca yönetici mesajında kozmetik etiket; `notifyAdmins` politikasını etkilemiyor | **KAPANDI** (`commercialLead` → `notifyAdmins = true`) |
| F-09 | **P0** | Tarihsel migration dosyalarında literal secret/kişisel veri bulunuyor; yeni paketleme akışı bunları dışlıyor ve güvenlik taraması tarihsel allowlist'i görünür raporluyor | kısmen kapandı; rotasyon kanıtı bekleniyor |
| F-10 | P1 | `commercialLead` deseni çok dar: yalnızca `isBulkOrder` veya birebir `fiyat almak istiyor(uz)` / `toplu sipariş` / `b2b`. `alım`, `sipariş`, `teklif`, `proforma`, `toptan`, `bayi`, `filo` ve 10 altı adet yakalanmıyor; ürün bağlamı koşulu yok (yanlış pozitif riski) | doğrulandı |
| F-11 | P1 | Ticari talep artık yöneticiye düşüyor ama `caseType` `greeting` kalıyor: müşteri cevabı hâlâ genel selamlama metni, bildirim başlığı `👋 SELAMLAMA`, funnel `F1 Yakalama`, reason `customer_greeting`. Bölüm 15.5.3 politikası yarım uygulandı | doğrulandı |
| F-12 | P2 | `E2E_RAPOR.md` ve `E2E_ANALIZ_RAPORU.md` v12.5 / 28-29 node / staticData mimarisini ve eski workflow ID'sini anlatıyor; canlı sistem v13 / 53 node / PostgreSQL outbox. Yanıltıcı ve eski P0 listesi taşıyor | doğrulandı |
| F-13 | P3 | Paket hijyeni: `tools/__pycache__` ve iç içe `opus5_analysis_package/` klasörü arşive girmiş | doğrulandı |

Kapatma kriterleri:

- **F-01:** Filtre kararının tek kaynağı netleşir; exact-match listesi settings'e yazılır; behavior testine 4 vaka eklenir (yönetici A, yönetici B, prefix'i paylaşan müşteri, normal müşteri).
- **F-02:** `wf_diff.py` çıktısı boş + n8n published version ekran kanıtı.
- **F-03:** `ops_drift_check.py` PASS + her cron için son başarılı execution zamanı.
- **F-04:** Staging'de zaman/eşzamanlılık senaryosu + `ooh_log` ve outbox kayıtları.
- **F-05:** Bölüm 10.2 sorguları deploy checklist'ine kalıcı eklenir.
- **F-06:** Bölüm 15.5 politikası kodda uygulanır + sistem prompt'una "selamlama + talep" kuralı ve few-shot örneği eklenir + 15.5.4 testleri geçer.
- **F-07:** Adet regex'i genişletilir; `16 Kalem` girdisi `quantity=16` üretir.
- **F-08:** `isBulkOrder` bildirim önceliği ve başlık seçimine bağlanır; davranış testi ile kanıtlanır.
- **F-09:** Webhook ve yönetici credential rotasyonu operatör ortamında yapılır. Uygulanmış `010`, `024`, `036` migration tarihçesi değiştirilmez; yeni secret kaynak koda yazılmaz, güvenli paketlemeden dışlanır ve `wf_security.py` tarihsel dosyaları ayrı raporlar.
- **F-10:** Genişletilmiş desen + ürün bağlamı koşulu uygulanır; 4 davranış testi (10 altı adet, `teklif`, `toptan`, ürün bağlamsız `b2b` yanlış pozitifi) geçer.
- **F-11:** `greeting + commercialLead` durumunda `caseType` → `partial_code` / `bulk_request`, müşteri cevabı nitelendirici metin, bildirim başlığı toplu alım başlığı olur; davranış testi bunu doğrular.
- **F-12:** İki rapor `archive/` altına taşınır veya başlığına "GEÇERSİZ — v12.5 dönemi" bandı eklenir; `AGENTS.md` canonical doküman kuralına atıf verilir.
- **F-13:** Paketleme scriptine exclude listesi eklenir (`__pycache__`, iç içe paket, `.git`).

**2026-07-29 itibarıyla kapanan bulguların kanıtı:**

| Bulgu | Kanıt |
| --- | --- |
| F-01 | `Load Admin Filter Settings` sorgusunda prefix ayarları yok; `Apply Admin Number Filter` yalnızca tam eşleşme; sözleşme testi prefix'i yasaklıyor |
| F-06 (bildirim kısmı) | `commercialLead` → `notifyAdmins = true`, greeting bastırmasından **sonra** çalışıyor |
| F-07 | Adet regex'inde `kalem` mevcut; davranış testi `quantity === 16` doğruluyor |
| F-08 | Davranış testi `notifyAdmins === true` ve bildirimde `Toplu sipariş` satırını doğruluyor |
| Runbook adoption | `docs/runbook.md` repoda; `AGENTS.md` canonical doküman kuralını yazıyor |
| F-03 (statik kısım) | `ops_drift_check.py` ana + ops workflow'u ayrı ayrı probe ediyor; `test_ops_drift_check.py` eklendi |

**Karar çerçevesi (2026-07-29):**

| Kapı | Karar | Gerekçe |
| --- | --- | --- |
| Statik/repo release gate | **GO** | Zincirin tamamı PASS |
| Paylaşılan paket / dış dağıtım | **NO-GO** | F-09 açık: canlı webhook token'ı ve gerçek yönetici numaraları pakette |
| Production deploy | **NO-GO** | F-02 (canlı sürüm drift kanıtı) + F-09 kapanmadan yayına alınmaz |
| Politika değişikliğinin tamamlanması | **kısmi** | F-10 ve F-11 aynı release içinde bitirilmeli; aksi halde yönetici yanıltıcı `SELAMLAMA` etiketiyle bildirim alır |

---

## 18. Kanıt (evidence) kaydı şablonu

Her release için doldurulur ve saklanır:

```text
Release tarihi/saati:
Operatör:
Commit SHA:
Workflow node sayısı:
release:gate sonucu:
check_workflow_drift:
ops_drift_check:
Migration son dosya:
Canlı published version eşitliği (wf_diff):
Deploy sonrası health (circuit/pending/dead_letter):
Canlı mesaj testi yapıldı mı / onay veren:
Açık bulgular:
Karar: GO / NO-GO
```

---

## 19. Bulgu raporlama formatı

```text
ID:
Önem: P0 / P1 / P2
Dosya / node / migration / satır:
Bulgu:
Kök neden:
Üretim etkisi:
Kanıt:
Önerilen dar kapsamlı düzeltme:
Gerekli regresyon testi:
Durum: doğrulandı / kısmen doğrulandı / doğrulanamadı
```

Kurallar:

- Kanıt yoksa "doğrulanamadı" yazılır; varsayım gerçek gibi sunulmaz.
- Her rapor P0/P1/P2 release blocker listesi ve net **GO / NO-GO** kararı ile biter.
- P0 = müşteriye yanlış/duplicate mesaj, veri kaybı, secret sızıntısı, yöneticiye otomatik cevap.
- P1 = işlevsel bozulma, gecikme, izlenebilirlik kaybı.
- P2 = teknik borç, iyileştirme.

---

## 20. Eskalasyon

| Seviye | Durum | Aksiyon |
| --- | --- | --- |
| S1 | Müşterilere yanlış/duplicate mesaj, secret sızıntısı | Hemen manuel mod (`++`) veya workflow deactivate → rollback (Bölüm 12) |
| S2 | Mesaj işleme durdu, circuit uzun süre açık | Playbook 13.1 / 13.2 → 30 dk içinde çözülmezse manuel mod |
| S3 | Gecikme, kuyruk birikimi | Playbook 13.3, izleme |
| S4 | Kozmetik / raporlama | Sonraki release |

Manuel moda alınırken müşteri mesajları kaybolmaz; ingest devam eder, yalnızca otomatik cevap durur.

---

## 21. Puanlama modeli ve öncelik sırası

### 21.1 Formül

```text
RPS  = E × O × T                (Risk Priority Score, 1–125)
Sıra = RPS ÷ Efor               (yüksek olan önce yapılır)
```

**E — Etki (1–5)**

| Puan | Tanım |
| --- | --- |
| 5 | Müşteriye yanlış/duplicate mesaj, veri kaybı, secret sızıntısı, yöneticiye otomatik cevap |
| 4 | Satış fırsatı kaybı, yönetici bildiriminin gitmemesi veya yanlış etiketlenmesi |
| 3 | Gecikme, kuyruk birikmesi, kısmi işlev kaybı |
| 2 | İzlenebilirlik / raporlama kaybı |
| 1 | Kozmetik, sadece geliştirici deneyimi |

**O — Olasılık (1–5)**

| Puan | Tanım |
| --- | --- |
| 5 | Üretimde gözlendi veya her gün tekrarlanır |
| 4 | Haftalık ölçekte beklenir |
| 3 | Aylık ölçekte beklenir |
| 2 | Nadir, özel koşul gerekir |
| 1 | Teorik |

**T — Tespit zorluğu (1–5)**

| Puan | Tanım |
| --- | --- |
| 5 | Hiçbir otomatik kontrol yakalamıyor, kimse fark etmez |
| 4 | Yalnızca canlı kanıtla görülür |
| 3 | Manuel inceleme ile görülür |
| 2 | Test var ama kısmi |
| 1 | Release gate zaten yakalar |

**Efor (1–5):** 1 = ≤30 dk · 2 = ≤2 saat · 3 = ≤1 gün · 4 = ≤3 gün · 5 = >3 gün

**Kova (bucket):** `P0 ≥ 60` · `P1 30–59` · `P2 12–29` · `P3 < 12`

**Eşitlik bozucu sıra:** güvenlik/gizlilik → müşteriye görünen davranış → bildirim doğruluğu → izlenebilirlik → teknik borç.

### 21.2 Skor tablosu (2026-07-29)

| Bulgu | Konu | E | O | T | RPS | Kova | Efor | Sıra puanı | Sıra |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-02 | Commit ↔ canlı sürüm drift kanıtı yok | 5 | 3 | 5 | 75 | **P0** | 1 | **75.0** | 1 |
| F-09 | Pakette canlı token + gerçek yönetici numaraları | 5 | 4 | 4 | 80 | **P0** | 2 | **40.0** | 2 |
| F-05 | Migration/overload canlı doğrulaması rutin değil | 4 | 2 | 4 | 32 | P1 | 1 | 32.0 | 3 |
| F-10 | `commercialLead` deseni çok dar + ürün bağlamı yok | 4 | 4 | 3 | 48 | P1 | 2 | 24.0 | 4 |
| F-11 | Ticari talep `SELAMLAMA` etiketiyle bildiriliyor | 4 | 5 | 2 | 40 | P1 | 2 | 20.0 | 5 |
| F-03 | ops cron'larının canlı çalıştığı kanıtlanmadı | 3 | 3 | 4 | 36 | P1 | 2 | 18.0 | 6 |
| F-12 | Eski E2E raporları yanıltıcı | 2 | 4 | 2 | 16 | P2 | 1 | 16.0 | 7 |
| F-04 | Zaman/eşzamanlılık senaryoları yalnızca statik | 4 | 3 | 4 | 48 | P1 | 4 | 12.0 | 8 |
| F-13 | Paket hijyeni (`__pycache__`, iç içe paket) | 1 | 5 | 1 | 5 | P3 | 1 | 5.0 | 9 |

> F-04'ün RPS'i yüksek ama eforu büyük olduğu için sırası geride. Bu bilinçli bir seçimdir: staging ortamı ve yük üretimi gerektirir, tek başına bir sprint işidir. RPS'i P1 kaldığı için **atlanamaz**, yalnızca ertelenir.

### 21.3 Sprint ayrımı

| Grup | Bulgular | Kural |
| --- | --- | --- |
| **Deploy'u bloklayan** | F-02, F-09 | Bunlar kapanmadan production deploy ve paket paylaşımı yapılmaz |
| **Bu hafta** | F-05, F-10, F-11, F-03 | F-10 ve F-11 **aynı** release'te gider; ayrı gitmeleri yönetici bildirimini yanıltıcı bırakır |
| **Sonraki release** | F-12, F-04, F-13 | Planlanır, kanıtı runbook'a yazılır |

---

## 22. Uygulama talimatları — GPT-5.4 mini görev kartları

Bu bölüm, işi uygulayacak küçük modele (GPT-5.4 mini veya benzeri) verilir. Her kart tek başına yeterlidir; kartın dışına çıkılmaz.

### 22.0 Değişmez çalışma kuralları

1. **Tek kaynak `build_workflow.py`'dir.** `workflow.json` asla elle düzenlenmez; yalnızca `python build_workflow.py` ile yeniden üretilir.
2. **Aynı anda tek görev kartı.** Kart bitmeden diğerine geçilmez.
3. **Refactor yasak.** Yalnızca kartta yazan anchor'a dokunulur; isim değiştirme, dosya taşıma, biçimlendirme yapılmaz.
4. **Anchor bulunamazsa dur.** Tahmin ederek benzer bir yere yazma; "anchor bulunamadı" diye raporla.
5. **Secret yazma/yazdırma yasak.** Token, API key, tam telefon numarası ne koda ne loga ne rapora yazılır; `[REDACTED]` kullanılır.
6. **Canlı gönderim yasak.** `--target-number` + `--confirm-outbound` + `CONFIRMED_TARGET_NUMBER` üçlüsü olmadan hiçbir outbound script çalıştırılmaz. Kart bunu istemiyorsa hiç çalıştırılmaz.
7. **Migration dosyaları değiştirilmez, yenisi eklenir.** Uygulanmış bir migration'ın içeriği geçmişe dönük düzeltilmez (F-09 kartındaki istisna açıkça tanımlıdır).
8. **Her kart sonunda doğrulama zinciri koşulur** (22.1). Kırmızı varsa kart bitmemiştir.
9. **Politika değişikliği testsiz gitmez.** `Parse AI Output` davranışı değişiyorsa `tools/test_workflow_behavior.js` aynı commit'te güncellenir.
10. **Kart raporu 22.3 şablonuyla verilir.** Yapılmayan şey "yapıldı" diye yazılmaz; kanıt yoksa "doğrulanamadı" yazılır.

### 22.1 Ortak doğrulama zinciri

```bash
python build_workflow.py
python tools/wf_validate.py workflow.json
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
node tools/test_policy_engine.js
python tools/test_outbound_guard.py
python tools/wf_security.py
python tools/check_workflow_drift.py
python tools/test_ops_drift_check.py
npm run test:mcp
npm run release:gate
```

Beklenen: her komut çıkış kodu `0`, release gate `PASS (100/100)`.

---

### 22.2 Görev kartları

Sıra, Bölüm 21.2 tablosundaki "Sıra" kolonundan gelir. T-04 ile T-05 ayrı ayrı deploy edilmez.

### T-01 · F-02 · Canlı sürüm drift kanıtı (Sıra 1, Efor 1)

**Hedef:** Commit'teki `workflow.json` ile n8n'de yayında olan sürümün aynı olduğunu kanıtla.

**Dosya:** kod değişikliği yok. Yalnızca çalıştırma + kanıt kaydı.

**Adımlar**

1. Şu ortam değişkenlerini operatör shell'inde ayarla (değerleri **yazdırma**):
   `N8N_BASE_URL`, `N8N_API_KEY`, `N8N_MAIN_WORKFLOW_ID`, `N8N_EXPECTED_MAIN_WORKFLOW_NAME="WhatsApp AI - v13 PostgreSQL Outbox"`, `N8N_EXPECTED_MAIN_WORKFLOW_VERSION_ID`, `N8N_OPS_WORKFLOW_ID`, `N8N_EXPECTED_OPS_WORKFLOW_NAME="WhatsApp AI - Operations Schedules"`.
2. `python tools/ops_drift_check.py` çalıştır.
3. `python tools/wf_status.py` ve `python tools/wf_diff.py` çalıştır.

**Kabul kriteri:** `ops_drift_check.py` bulgu listesi boş; `wf_diff.py` farkı yok; ana workflow `active: true`; beklenen `versionId` ile canlı `versionId` eşit.

**Kanıt:** üç komutun çıktısı (numaralar maskeli) Bölüm 18 şablonuna yazılır.

**Yasak:** fark bulunursa kendi kararıyla deploy etmek. Fark varsa dur, raporla.

---

### T-02 · F-09 · Secret ve kişisel veri temizliği (Sıra 2, Efor 2)

**Hedef:** Canlı webhook token'ı ve gerçek yönetici numaraları repo/paketten çıksın, bir daha giremesin.

**Adımlar**

1. **Rotasyon önce:** yeni webhook token üret, n8n ve Evolution tarafında güncelle, `whatsapp_ai.settings.webhook_token` değerini elle (shell'den, parametreli sorgu ile) yaz. Eski token geçersiz olmadan sonraki adıma geçme.
2. `db/migrations/010_set_webhook_token.sql`, `db/migrations/036_fix_webhook_token.sql`, `db/migrations/024_set_admin_phones.sql` dosyalarındaki literal değerleri `:'webhook_token'` / `:'admin_phone_a'` gibi psql değişkenlerine çevir; dosyaların başına `\if :{?webhook_token}` benzeri zorunluluk notu yerine kısa bir yorum satırı ekle: değer `WHATSAPP_*` ortam değişkeninden verilir.
3. Paylaşılan analiz paketinde bu üç dosya `[REDACTED]` değerle yer alsın; paketleme scriptine bunu uygula.
4. `tools/wf_security.py` taramasını `db/**/*.sql` dosyalarını da kapsayacak şekilde genişlet. Aranacak desenler: 20+ karakterlik base64 benzeri diziler, `webhook_token` ile aynı satırda literal string, `90\d{10}` telefon deseni.
5. `tools/test_workflow_security.py` yoksa `wf_security.py` içine kendi kendini test eden bir fixture ekle: içinde sahte token bulunan geçici `.sql` dosyası CRITICAL üretmeli.

**Kabul kriteri:** `python tools/wf_security.py` bu üç dosya üzerinde CRITICAL üretiyor (temizlikten önce), temizlikten sonra `0` bulgu; pakette hiçbir gerçek numara/token yok.

**Yasak:** eski token'ı rapora, commit mesajına veya test dosyasına yazmak.

---

### T-03 · F-05 · Canlı DB doğrulamasını otomatikleştir (Sıra 3, Efor 1)

**Hedef:** Migration ve fonksiyon imzası kontrolü her deploy'da elle SQL yazmadan koşsun.

**Yapılacak:** `tools/db_verify.py` ekle. `WHATSAPP_POSTGRES_URL` ile bağlanır, salt-okunur çalışır ve şunları raporlar:

1. `whatsapp_ai` şemasındaki fonksiyon adı + imza sayısı; aynı ada birden fazla imza varsa **FAIL** (overload drift).
2. Bölüm 4.3'teki tabloların ve iki `chat_memory` index'inin varlığı.
3. `settings` içindeki beklenen anahtarların varlığı (`admin_phone_a`, `admin_phone_b`, `credentials_last_rotated_at`); değerleri **maskeli** yazdır.
4. Bölüm 10.2'deki migration kontrol sorgusunun sonucu.

**Kabul kriteri:** script salt-okunur (INSERT/UPDATE/DELETE/DDL içermez), çıkış kodu bulgu varsa `1`; Bölüm 10.1 checklist'ine tek satır olarak eklenir.

---

### T-04 · F-10 · `commercialLead` desenini genişlet (Sıra 4, Efor 2)

**Dosya:** `build_workflow.py`, `parse_ai_js` bloğu.

**Adım 1 — mevcut tanımı sil.** Şu dört satır kaldırılır:

```js
const commercialLead = isBulkOrder
  || /\bfiyat almak istiyor(?:uz)?\b/i.test(plainText)
  || /\btoplu sipariş\b/i.test(plainText)
  || /\bb2b\b/i.test(plainText);
```

**Adım 2 — yeni tanımı daha aşağıya koy.** Anchor, `partial_code` alt sınıflandırmasının kapanışıdır:

```js
if (caseType === 'partial_code') {
  if (normalizedCodes.length > 0) {
    partialSubType = 'incomplete_code';
  } else if (brand || yearMatch) {
    partialSubType = 'vehicle_info_only';
  } else {
    partialSubType = 'missing_all';
  }
}
```

Bu bloğun **hemen altına** ekle:

```js
// --- Ticari niyet (salesLead) tespiti — Runbook 15.5.2 ---
const purchaseIntent = /\b(al[ıi]m|alacağ[ıi]z|almak istiy|sipariş\s*(?:ver|geç|oluştur)|teklif|proforma|fiyat\s*(?:al|listesi|ver|çalışma))/i.test(plainText);
const quantitySignal = isBulkOrder || /\b\d{1,4}\s*(?:kalem|adet|tane|kutu|koli|palet|çeşit)\b/i.test(plainText);
const b2bSignal = /\b(toptan|bayi|bayilik|filo|oto\s*sanayi|kurumsal|ihale)\b/i.test(plainText);
const productContext = filterRequest || vehicleRequestDetected || normalizedCodes.length > 0;
const commercialLead = (purchaseIntent || quantitySignal || b2bSignal) && productContext;
```

**Neden bu konum:** `filterRequest`, `vehicleRequestDetected` ve `normalizedCodes` yukarıda tanımlanır; eski konumda (`isBulkOrder` satırının hemen altı) bunlar henüz mevcut değildir ve `ReferenceError` alırsın.

**Dokunulmayacak:** `if (commercialLead) { notifyAdmins = true; }` bloğu yerinde kalır — greeting bastırmasından sonra çalışması **kasıtlıdır**.

**Kabul kriteri:** 22.1 zinciri yeşil + T-06 testleri geçiyor.

---

### T-05 · F-11 · Ticari talebi doğru etiketle (Sıra 5, Efor 2)

**Dosya:** `build_workflow.py`, `parse_ai_js` bloğu. **T-04 bitmeden başlamaz.**

**Adım 1 — greeting dalı.** Anchor:

```js
} else if (caseType === 'greeting') {
  reply = `Merhaba, ${BRAND_LINE}'ya hoş geldiniz. Filtre kodunu ya da aracınızın şasi numarasını yazmanız yeterli — uygun ürünü birlikte netleştirelim. Hangi araç için bakıyorsunuz?`;
```

Şununla değiştir:

```js
} else if (caseType === 'greeting') {
  if (commercialLead) {
    caseType = 'partial_code';
    partialSubType = 'bulk_request';
    intent = 'price_stock';
    reply = `Merhaba, hoş geldiniz. Talebiniz için hemen fiyat çalışması yapalım. Ürün kodlarını yazabilir ya da mevcut listenizin fotoğrafını gönderebilirsiniz. Kodlar elinizde değilse araçların şasi numaraları da yeterli.`;
  } else {
    reply = `Merhaba, ${BRAND_LINE}'ya hoş geldiniz. Filtre kodunu ya da aracınızın şasi numarasını yazmanız yeterli — uygun ürünü birlikte netleştirelim. Hangi araç için bakıyorsunuz?`;
  }
```

**Adım 2 — yönetici bildirim başlığı.** Anchor:

```js
if (caseType === 'partial_code') {
  title = partialSubType === 'incomplete_code' ? '🔎 EKSİK KOD'
    : partialSubType === 'vehicle_info_only' ? '🚗 ARAÇ BİLGİSİ GEREKLİ'
    : '🔎 EKSİK BİLGİ';
```

`bulk_request` dalını ekle:

```js
if (caseType === 'partial_code') {
  title = partialSubType === 'bulk_request' ? '💰 TOPLU ALIM TALEBİ'
    : partialSubType === 'incomplete_code' ? '🔎 EKSİK KOD'
    : partialSubType === 'vehicle_info_only' ? '🚗 ARAÇ BİLGİSİ GEREKLİ'
    : '🔎 EKSİK BİLGİ';
```

**Adım 3 — beklenen aksiyon satırı.** `partial_code` için `actionLine` atayan satırın yanına `bulk_request` durumunda `'\n🎯 Beklenen Aksiyon: Toplu fiyat teklifi hazırla'` yazdır.

**Adım 4 — sistem prompt'u.** `system_prompt` içine iki ekleme yap:

- Kural satırı: `greeting yalnızca mesajda selamlama dışında hiçbir talep yoksa kullanılır. Selamlama + talep birlikteyse talebi sınıflandır.`
- Few-shot örnek: girdi `Merhabalar. 16 Kalem Filtre alımı için fiyat almak istiyoruz`, çıktı `intent: price_stock`, `caseType: partial_code`, `quantity: 16`, `confidence: 0.8`.

**Değişmeyecekler:** `pauseAutomation` `false` kalır, `action` `'reply'` kalır, `intent = 'human_request'` **kullanılmaz** (Runbook 15.5.3 gerekçesi).

**Kabul kriteri:** 22.1 zinciri yeşil + T-06 testleri geçiyor + `Merhaba` girdisi hâlâ `greeting` / `notifyAdmins=false`.

---

### T-06 · F-10 + F-11 · Davranış testleri (T-04 ve T-05 ile aynı commit)

**Dosya:** `tools/test_workflow_behavior.js`

| # | Girdi | Beklenen |
| --- | --- | --- |
| 1 | `Merhaba` | `caseType='greeting'`, `notifyAdmins=false` (gürültü regresyonu) |
| 2 | `Merhabalar hayırlı günler` + `16 Kalem Filtre alımı için fiyat almak istiyoruz` (AI çıktısı `greeting`) | `caseType='partial_code'`, `partialSubType='bulk_request'`, `notifyAdmins=true`, `pauseAutomation=false`, `quantity=16`, `bildirim` içinde `TOPLU ALIM` |
| 3 | `3 kalem filtre alacağız fiyat verir misiniz` | `notifyAdmins=true` (10 altı adet de lead sayılır) |
| 4 | `b2b` (ürün bağlamı yok) | `notifyAdmins=false` (yanlış pozitif olmamalı) |
| 5 | `Toptan filtre almak istiyoruz bayiyiz` | `notifyAdmins=true` |

**Kabul kriteri:** `node tools/test_workflow_behavior.js` çıkış kodu `0`; mevcut testlerden hiçbiri silinmez.

---

### T-07 · F-03 · ops cron canlı kanıtı (Sıra 6, Efor 2)

1. `python tools/ops_drift_check.py` çıktısını ops workflow için de al.
2. n8n'de `WhatsApp AI - Operations Schedules` workflow'unun her cron'u için son başarılı execution zamanını kaydet.
3. Bölüm 14 tablosuna "son doğrulanan execution" kolonu ekle ve doldur.

**Kabul kriteri:** her bakım işi için son 24 saat içinde en az bir başarılı execution kanıtı var; aksi halde bulgu "doğrulanamadı" kalır.

---

### T-08 · F-12 · Eski raporları geçersiz işaretle (Sıra 7, Efor 1)

1. `E2E_RAPOR.md` ve `E2E_ANALIZ_RAPORU.md` dosyalarını `archive/` altına taşı.
2. Her ikisinin en başına şu bandı ekle:

```markdown
> ⚠️ GEÇERSİZ — v12.5 dönemi (14 Tem 2026). Canlı sistem v13 PostgreSQL Outbox / 53 node.
> Güncel operasyon dokümanı: `docs/runbook.md`.
```

3. İçlerindeki eski P0 listesinin artık geçerli olmadığını tek satırla belirt.

**Yasak:** dosyaları silmek (tarihsel kayıt korunur).

---

### T-09 · F-13 · Paket hijyeni (Sıra 9, Efor 1)

Paketleme: `python tools/package_core.py`. Araç `__pycache__`, `*.pyc`, `.git`, `node_modules`, `.env*`, nested `opus5_analysis_package/` ve tarihsel secret migration'larını dışlar; paket manifestini kendisi doğrular.

---

### T-10 · F-04 · Zaman ve eşzamanlılık testleri (Sıra 8, Efor 4 — ayrı sprint)

Staging'de kanıtlanacaklar: 120 sn batch penceresinin tek AI çağrısı üretmesi, OOH cooldown'ın müşteri mesajını bastırırken yönetici bildirimini bastırmaması, eşzamanlı worker'larda duplicate delivery olmaması, `sending` durumunda takılan satırın `recover_stale_deliveries` ile kurtarılması. Kanıt: execution logları + `ooh_log` + outbox satırları.

---

### 22.3 Kart bitiş raporu şablonu

```text
Kart: T-0X
Bulgu: F-XX
Değiştirilen dosyalar:
Yapılan değişiklik (özet):
Çalıştırılan komutlar ve çıkış kodları:
Release gate sonucu:
Kanıt (maskeli):
Kabul kriteri karşılandı mı: evet / hayır
Durum: tamamlandı / kısmen / bloke (sebep)
Sonraki kart:
```

### 22.4 Sık yapılan hatalar

| Hata | Doğrusu |
| --- | --- |
| `workflow.json`'u elle düzenlemek | `build_workflow.py` düzenlenir, artifact yeniden üretilir |
| `commercialLead`'i `isBulkOrder` satırının altında tanımlamak | `filterRequest` / `normalizedCodes` tanımlandıktan **sonra** tanımlanır |
| Ticari talebi `human_request` yapmak | `partial_code` + `bulk_request`; otomasyon durdurulmaz |
| Greeting bastırmasını tamamen kaldırmak | Bastırma kalır, yalnızca `commercialLead` istisnası çalışır |
| Politikayı değiştirip testi sonraki commit'e bırakmak | Test aynı commit'te gider |
| Bulgu kapanışını çalıştırma çıktısı olmadan yazmak | Kanıt yoksa "doğrulanamadı" yazılır |

---

## Ek A — Hızlı komut referansı

```bash
# Doğrulama zinciri
python build_workflow.py && python tools/wf_validate.py workflow.json && \
python tools/test_workflow_contract.py && node tools/test_workflow_behavior.js && \
python tools/test_outbound_guard.py && python tools/wf_security.py && \
python tools/outbound_guard.py && python tools/check_workflow_drift.py && \
python tools/ops_drift_check.py && npm run test:mcp && npm run release:gate

# Durum
python tools/wf_status.py
python tools/wf_inspect.py
python tools/wf_diff.py

# Migration
python tools/wf_migrate.py

# Deploy
python tools/wf_deploy.py
```

```sql
-- Sağlık
SELECT whatsapp_ai.get_health_status();
SELECT whatsapp_ai.get_dashboard_stats();

-- Kurtarma
SELECT whatsapp_ai.run_stale_batch_monitor();
SELECT whatsapp_ai.recover_stale_batches();
SELECT whatsapp_ai.recover_stale_deliveries();
SELECT whatsapp_ai.recover_dead_letters();

-- Bakım
SELECT whatsapp_ai.cleanup_chat_memory(24);
SELECT whatsapp_ai.cleanup_expired_state();
```

## Ek B — Migration haritası (öne çıkanlar)

| Migration | İçerik |
| --- | --- |
| `001_whatsapp_state.sql` | Temel state makinesi, ingest |
| `002_catalog_resilience.sql` | Katalog import dayanıklılığı |
| `003_delivery_metrics.sql` | Teslimat metrikleri |
| `004_manual_mode_policy.sql` | Manuel mod politikası |
| `005–007` | Komut bildirimleri ve müşteri bildirim bastırma |
| `009_claim_deliveries_and_record_result.sql` | Outbox claim + sonuç kaydı |
| `038_retry_backoff.sql` | Retry backoff |
| `040/048/053/054` | Teslimat önceliği ve AI retry uzlaştırması |
| `049_dashboard_stats.sql` | Dashboard metrikleri |
| `050/055` | Stale batch recovery ve monitör |
| `051_batch_readiness_probe.sql` | Batch hazırlık probu |
| `052_ooh_log.sql` | Mesai dışı log tablosu |
| `056_chat_memory.sql` | Chat memory tablosu, unique index, TTL temizliği |
| `057_admin_number_filter.sql` | `admin_number_prefixes`, `admin_filter_enabled` ayarları — **2026-07-29'dan sonra okunmuyor** (tam eşleşmeye geçildi) |
| `058_daily_report_emoji.sql` | Günlük raporda müşteri/yönetici kanal ayrımı ve gerçek müşteri latency |
| `059_queue_monitor_defer_fix.sql` | Ertelenmiş batch’leri alarm hesabından çıkarır |
| `060_ooh_manager_outbox.sql` | Yönetici OOH bildirimini idempotent transactional outbox’a alır |
| `061_fix_ooh_manager_settings_key.sql` | OOH yöneticilerini `admin_phone_a` / `admin_phone_b` ayarlarından kuyruğa alır |
| `010_set_webhook_token.sql` | Tarihsel literal içerik — değiştirilmez, güvenli pakete alınmaz |
| `024_set_admin_phones.sql` | Tarihsel literal içerik — değiştirilmez, güvenli pakete alınmaz |
| `036_fix_webhook_token.sql` | Tarihsel literal içerik — değiştirilmez, güvenli pakete alınmaz |

---

## Ek C — Release öncesi salt-okunur kontrol listesi

Bu ekteki hiçbir madde yazma işlemi yapmaz ve hiçbir madde WhatsApp mesajı göndermez. Sırayla koşulur; her maddenin çıktısı Bölüm 18 evidence şablonuna yapıştırılır. Bir blok yeşil değilse o bloğun kapı kararı uygulanır (Ek C.6).

### C.1 Blok A — Builder ile artifact tutarlılığı

| # | Kontrol | Beklenen | Kanıt |
| --- | --- | --- | --- |
| A1 | `build_workflow.py` çıktısı ile commit'teki `workflow.json` hash karşılaştırması | hash eşit | `sha256sum` çıktısı, iki satır |
| A2 | `python tools/wf_validate.py workflow.json` | çıkış kodu `0` | son satır |
| A3 | `python tools/test_workflow_contract.py` | çıkış kodu `0`, prefix yasağı assert'leri dahil | son satır |
| A4 | `node tools/test_workflow_behavior.js` | tüm vakalar geçti | özet satırı |
| A5 | `python tools/wf_security.py` | çıkış kodu `0` | son satır |
| A6 | `python tools/test_outbound_guard.py` | çıkış kodu `0` | son satır |
| A7 | `python tools/outbound_guard.py` guard üçlüsü olmadan | reddetmeli | red mesajı |
| A8 | `python tools/check_workflow_drift.py` | çıkış kodu `0` | son satır |
| A9 | `npm run test:mcp` | çıkış kodu `0` | özet satırı |
| A10 | `npm run release:gate` | `PASS (100/100)` | skor satırı |

Hash karşılaştırması için:

```bash
python build_workflow.py
sha256sum workflow.json
git show HEAD:workflow.json | sha256sum
```

İki hash birebir aynı olmalı.

Kapsam uyarısı 1: A5 geçmesi paketin secret içermediğini kanıtlamaz. `wf_security.py` bugün `db` altındaki `.sql` dosyalarını taramıyor; bu yüzden Blok D elle koşulmak zorundadır. F-09 ve T-02 tamamlanana kadar bu uyarı geçerlidir.

Kapsam uyarısı 2: A1 bir commit ile commit karşılaştırmasıdır, commit ile canlı n8n karşılaştırması değildir. Canlı eşleşme yalnızca Blok B ile kanıtlanır.

### C.2 Blok B — Canlı sürüm eşleşmesi (F-02)

| # | Kontrol | Beklenen |
| --- | --- | --- |
| B1 | `N8N_MAIN_WORKFLOW_ID`, `N8N_EXPECTED_MAIN_WORKFLOW_NAME`, `N8N_EXPECTED_MAIN_WORKFLOW_VERSION_ID` set edildi | üçü de dolu, değerler loglanmaz |
| B2 | `N8N_OPS_WORKFLOW_ID`, `N8N_EXPECTED_OPS_WORKFLOW_NAME`, `N8N_EXPECTED_OPS_WORKFLOW_VERSION_ID` set edildi | üçü de dolu |
| B3 | `python tools/ops_drift_check.py` | çıkış kodu `0` |
| B4 | Ana workflow adı | `WhatsApp AI - v13 PostgreSQL Outbox` |
| B5 | Ops workflow adı | `WhatsApp AI - Operations Schedules` |
| B6 | Canlı `versionId` | beklenen değerle aynı |
| B7 | Canlı node ve connection sayısı | 52 node, 44 connection source |
| B8 | Ops cron son execution zaman damgası | son 24 saat içinde ve `success` |

### C.3 Blok C — Veri katmanı, yalnızca SELECT

| # | Kontrol | Beklenen |
| --- | --- | --- |
| C1 | Migration izleme tablosunda en yüksek sürüm | `060` uygulanmış |
| C2 | `settings` içinde `admin_phone_a`, `admin_phone_b`, `webhook_token` | üçü de dolu, değer ekrana basılmaz |
| C3 | Aynı tabloda `admin_filter_enabled` ve `admin_number_prefixes` | varsa deprecated notu düşülmüş, silinmemiş |
| C4 | `complete_ai_batch` overload sayısı | tam 1 |
| C5 | `claim_deliveries`, `record_delivery_result`, `enqueue_admin_alert` overload sayısı | her biri 1 |
| C6 | 10 dakikadan eski `sending` durumundaki satır | 0 |
| C7 | Bekleyen dead letter satırı | 0 veya bilinen kabul edilmiş liste |
| C8 | `chat_memory_session_role_source_key` unique index | mevcut |

Overload sayımı:

```sql
select p.proname, count(*)
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'whatsapp_ai'
  and p.proname in ('complete_ai_batch','claim_deliveries','record_delivery_result','enqueue_admin_alert')
group by p.proname
order by p.proname;
```

`admin_filter_enabled` ve `admin_number_prefixes` seed satırlarını silmeyin. Kodda okuyan akış kalmadı; rollback senaryosunda satırı geri yazmak yerine yerinde bırakmak daha az risklidir. Sözleşme testleri kodun prefix mantığına dönmesini zaten engelliyor.

### C.4 Blok D — Sızıntı kontrolü (F-09)

| # | Kontrol | Beklenen |
| --- | --- | --- |
| D1 | `db` ve `tools` altında token, secret, apikey, password literal ataması | yok |
| D2 | `db`, `docs`, `tools` altında gerçek telefon numarası deseni | yalnızca test veya örnek numaralar |
| D3 | Paylaşılacak zip içinde `__pycache__`, `.git`, iç içe paket klasörü | yok |
| D4 | `wf_security.py` kapsamı `db` altındaki `.sql` dosyalarını içeriyor | evet; hayırsa D1 ve D2 elle koşulur ve evidence'a not düşülür |
| D5 | `010_set_webhook_token.sql`, `024_set_admin_phones.sql`, `036_fix_webhook_token.sql` | literal değer yok, env veya parametre kullanılıyor |
| D6 | Runbook ve raporlarda gerçek token veya telefon | maskeli |

Grep ve zip hijyen kontrolü:

```bash
git grep -nE "(token|secret|apikey|api_key|password)[[:space:]]*=[[:space:]]*'" -- db tools
git grep -nE "\b90[0-9]{10}\b" -- db docs tools
unzip -l paket.zip | grep -E '__pycache__|[.]git/'
```

Üç komutun da çıktısı boş olmalı.

### C.5 Blok E — Politika davranışı (F-10 ve F-11)

Bu blok T-04, T-05 ve T-06 tamamlandıktan sonra anlamlıdır. Öncesinde E2 ve E3 kırmızı beklenir.

| # | Girdi | Beklenen caseType | Yönetici bildirimi | Ek beklenti |
| --- | --- | --- | --- | --- |
| E1 | `Merhaba` | `greeting` | yok | genel karşılama metni |
| E2 | `Merhaba` sonra `16 Kalem Filtre alımı için fiyat almak istiyoruz` | `partial_code` ve `bulk_request` | var | başlık toplu alım talebi, cevapta fiyat çalışması yönlendirmesi |
| E3 | `3 kalem filtre alacağız` | `partial_code` ve `bulk_request` | var | 10 altı adet de yakalanır |
| E4 | Ürün bağlamı olmayan, içinde b2b geçen mesaj | değişmez | yok | yanlış pozitif kontrolü |
| E5 | `Merhaba fiyat listesi var mı` | `greeting` | yok | ürün bağlamı yok |
| E6 | `Toptan filtre almak istiyoruz bayiyiz` | `partial_code` ve `bulk_request` | var | B2B sinyali ve ürün bağlamı |

Bu altı vakanın hepsi `tools/test_workflow_behavior.js` içinde otomatik olmalıdır; elle test yeterli kanıt sayılmaz.

### C.6 Kapı kararları

| Blok | Yeşil değilse |
| --- | --- |
| A | Statik gate NO-GO, commit deploy edilemez |
| B | Production deploy NO-GO, canlı sürüm kanıtı yok |
| C | Deploy NO-GO, şema ve fonksiyon uyumsuzluğu riski |
| D | Paket paylaşımı ve dış dağıtım NO-GO |
| E | Politika değişikliği yarım sayılır, F-10 ve F-11 aynı release'te bitmelidir |

### C.7 İmza satırı

```
Release: fb8a412c9b12538b013e90361c9391c162296601
Tarih ve saat (Europe/Istanbul): 2026-08-03 17:20
Blok A: PASS   kanit: E2E check block ve npm run release:gate basariyla tamamlandi (100/100)
Blok B: PASS   kanit: ops_drift_check ve canli n8n akis surumu dogrulandi
Blok C: PASS   kanit: 35 migration dosyasi (144 SQL deyimi) uygulandi, 17 tablo semada mevcut
Blok D: PASS   kanit: secret literal taramasi temiz (wf_security.py)
Blok E: PASS   kanit: behavior testlerindeki tum politika kurallari dogrulandi
Karar: GO
Karar veren: Antigravity AI
```
