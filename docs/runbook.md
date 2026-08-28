# WhatsApp AI — v13 PostgreSQL Outbox — GPT-5.4 Operasyon Runbook

| Alan | Değer |
| --- | --- |
| Doküman sürümü | 3.5 |
| Son güncelleme | 2026-08-28 |
| Sistem | FiltreOto WhatsApp AI |
| AI Modeli | OpenAI `gpt-5.4` |
| Workflow | `WhatsApp AI - v13 PostgreSQL Outbox` |
| Node sayısı | 53 node / 45 connection source (builder çıktısı; canlı sayı `ops_drift_check` ile doğrulanır) |
| Migration kapsamı | `001` → `070` (070 dahil: Manuel mod yönetici outbox bildirimi & 8 argümanlı ingest_message) |
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
6. Değişmez kurallar (Non-negotiables)
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
22. Uygulama talimatları — GPT-5.4 görev kartları

---

## 1. Amaç ve kapsam

Bu runbook, FiltreOto WhatsApp AI sisteminin OpenAI **gpt-5.4** modeli ile **günlük işletimi, release süreci, olay müdahalesi ve rollback** adımlarını tanımlar.

Kapsam içi:
- n8n workflow `WhatsApp AI - v13 PostgreSQL Outbox` (53 Node)
- OpenAI `gpt-5.4` akıllı filtre uyuşmazlık, kod sorgulama ve müşteri hizmetleri katmanı
- PostgreSQL `whatsapp_ai` şeması (001-070 migrasyon zinciri)
- Evolution API WhatsApp gateway (`evo.filtreoto.online`)
- `ops_workflow.json` cron/bakım workflow'u

---

## 2. Mimari ve akış

### 2.1 Kritik Akış Şeması

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

[Worker Yolu — Schedule Trigger, 15 saniye]
OpenAI Circuit Gate → OpenAI Circuit Open?
  → Claim Ready Batches → Store Context → AI Agent (OpenAI gpt-5.4)
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

### 2.2 Tasarım İlkeleri

- **Auth-before-ingest:** Yetkisiz istekler veritabanına ulaşmadan reddedilir.
- **Transactional Outbox:** AI kararı ile WhatsApp mesaj gönderimi ayrılmıştır; outbox teslimatı `claim_deliveries` ile yapılır.
- **Circuit Breaker:** OpenAI ve Evolution API için bağımsız devre kesiciler aktif izlenir.
- **Idempotency:** `message_id` bazlı çifte kayıt engelleme ve atomik kilit mekanizması (`FOR UPDATE SKIP LOCKED`).
- **GPT-5.4 Entegrasyonu:** Yüksek doğrulukta marka, model, yıl, VIN ve parça kodu çıkarımı; hallucination koruması.

---

## 3. Node Envanteri (53 Node)

1. `Webhook1` (n8n-nodes-base.webhook v2)
2. `Normalize Payload` (Code Node - Evolution v2 & @lid)
3. `Valid Event?` (If Node)
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
33. `Parse AI Output` (Code Node - Guardrail & Vehicle Check)
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

## 4. Veri Katmanı (Migrasyonlar 001 - 070)

- **001 - 050:** Temel mesajlaşma, outbox, devre kesici ve batch kilit mimarisi.
- **051 - 066:** OOH logları, admin bildirim outbox'ı, unique pending kilitleri ve holiday ayarları.
- **067_command_admin_notifications.sql:** Yetkili komutlarda admin outbox bildirimi ve 8 argümanlı `ingest_message` imzası.
- **067_dashboard_health_ingest_reconcile.sql:** Eski 7 argümanlı fonksiyonun kaldırılması ve dashboard metriklerinin güncellenmesi.
- **068_ops_dry_run_guard.sql:** Bakım işlemlerinde ops koruması.
- **069_health_dead_delivery_warning.sql:** Dead delivery sayısı uyarı eşiği.
- **070_manual_mode_admin_notification.sql:** Müşteri manuel moddayken yeni mesaj attığında yöneticilere outbox üzerinden anlık WhatsApp bildirimi oluşturulması.

---

## 5. Değişmez Kurallar (Non-Negotiable Rules)

1. **Yetkilendirme:** Veri veritabanına yazılmadan önce webhook token ve yetki doğrulaması yapılır.
2. **Idempotency:** `message_id` ve `batch_token` eşsizliği korunur.
3. **Manuel Mod Yetkisi:** Yalnızca tanımlı admin numaralarından gelen `fromMe` `++`/`--` komutları manuel modu değiştirebilir.
4. **Gizlilik:** API anahtarları, DB parolaları ve telefon numaraları sohbet loglarında veya commit'lerde açık edilemez.
5. **Canlı Mesaj Gönderim Yasağı:** Testlerde canlı kullanıcılara izinsiz mesaj atılamaz (`test_outbound_guard.py` emniyeti).
6. **Canlı Doğrulama Şartı:** Canlı DB ve n8n kanıtı alınmadan "Production GO" kararı verilemez.

---

## 6. Release Gate ve Komut Zinciri

Her deploy öncesinde lokal olarak aşağıdaki doğrulama komut dizisi çalıştırılmalıdır:

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

## 7. Deploy ve Doğrulama Prosedürü

### 7.1 Canlıya Veritabanı Migrasyonlarını Uygulama
```bash
export WHATSAPP_POSTGRES_URL="postgresql://user:password@host:port/dbname"
python tools/wf_migrate.py
```

### 7.2 Canlı n8n ve Evolution Reconcile
```bash
export N8N_BASE_URL="https://n8n.filtreoto.online"
export N8N_API_KEY="<NEW_API_KEY>"
export N8N_WORKFLOW_ID="<WORKFLOW_ID>"
export EVOLUTION_BASE_URL="https://evo.filtreoto.online"
export EVOLUTION_API_KEY="<EVOLUTION_API_KEY>"
export EVOLUTION_INSTANCE="otofiltre"
export N8N_WEBHOOK_SECRET="efb34f7a2e23ff3382bdde8a6703b64a796381a0b341f10c"

python tools/webhook_runtime_reconcile.py --apply
```

### 7.3 Canlı Veritabanı Kontrol Sorgusu
```sql
SELECT routine_name, parameter_name, data_type, ordinal_position
FROM information_schema.parameters
WHERE specific_name LIKE '%ingest_message%'
ORDER BY ordinal_position;
```

---

## 8. Rollback Prosedürü

Eğer canlı ortamda beklenmeyen bir aksaklık görülürse:

1. n8n arayüzünde ilgili workflow'u `Active = OFF` yapın.
2. Git deposunda bir önceki stabil commit'e dönün (`git checkout <previous_stable_commit>`).
3. `python build_workflow.py` çalıştırıp stabil `workflow.json` dosyasını n8n'e aktarın.
4. `Active = ON` konuma getirin.

---

## 9. GPT-5.4 Görev Kartları ve Operasyon Talimatları

GPT-5.4 modeli ile çalışırken dikkat edilecek hususlar:
- **Model parametresi:** `gpt-5.4` olarak ayarlanmalıdır.
- **Sıcaklık (Temperature):** 0.1 (Deterministik yanıtlar ve sıfır hallucination için).
- **Prompt Ayrımı:** Müşteri metni prompt'a girmeden önce sanitization uygulanır.
- **Eksik Araç Takibi:** VIN bulunmadığında motor gücü veya motor hacmi bilgisi araç tamlığı için yeterli kabul edilir.

---

> *İşbu runbook `AGENTS.md` standartlarına uygun olarak en güncel v13 mimarisi ve GPT-5.4 gereksinimleri doğrultusunda hazırlanmıştır.*
