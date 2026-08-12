# WhatsApp AI — Canlı Yayın Doğrulama ve E2E Analiz Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 12 Ağustos 2026  
**Kapsam:** Lokal ve repository kontrollerinin doğrulanması, canlı ortam doğrulama eksikliklerinin (9 madde) tespiti ve 4 fazlı canlıya geçiş (Production Release Gate) rehberi.

---

## 1. YÖNETİCİ ÖZETİ VE ÇİFT KATMANLI DURUM MATRİSİ

Sistem durumsal olarak iki ayrı katmanda değerlendirilmiştir:

### 🟢 Katman 1: Kod Tabanı & Repository Durumu (GO — 100/100 PASS)
- **Commit Durumu:** `4ca5212` (Head)
- **Uzak Depolar:** `github/main` ve `origin/main` aynı commit'tedir (`4ca5212`).
- **Migrasyon:** `070_manual_mode_admin_notification.sql` oluşturuldu ve depoda mevcut.
- **Workflow Derlemesi:** 53 Node, 45 Connection Source.
- **Yerel Testler:** `wf_validate.py`, `test_workflow_contract.py`, `test_workflow_behavior.js`, `test_ops_drift_check.py`, `test_outbound_guard.py` **PASS**.
- **Release Gate Skoru:** **100 / 100 PASS**.

### 🔴 Katman 2: Canlı Ortam (Production) Doğrulama Durumu (NO-GO — Doğrulama Bekliyor)
Canlı sunucu erişimi olmadan kod bazlı "sistem tamamen düzeldi" demek yanıltıcı olacağından, aşağıdaki 9 canlı kontrol maddesi operatör tarafından doğrulanana kadar **Production Kararı: NO-GO**'dur.

---

## 2. CANLI ORTAM DOĞRULANMAMIŞ MADDELER MATRİSİ (9 KRİTİK MADDE)

| # | Canlı Kontrol Maddesi | Beklenen Durum | Doğrulama Yöntemi | Durum |
| --- | --- | --- | --- | --- |
| 1 | **Migration 067 Canlı DB** | Uygulanmış | `python tools/wf_migrate.py` | 🔴 Doğrulanmadı |
| 2 | **Migration 070 Canlı DB** | Uygulanmış | `python tools/wf_migrate.py` | 🔴 Doğrulanmadı |
| 3 | **`ingest_message` İmzası** | 8 Parametreli | SQL `information_schema.parameters` | 🔴 Doğrulanmadı |
| 4 | **n8n Workflow Sürümü** | `4ca5212` (v13) | `python tools/webhook_runtime_reconcile.py` | 🔴 Doğrulanmadı |
| 5 | **Workflow Active Şalteri** | `active = true` | n8n GUI / API | 🔴 Doğrulanmadı |
| 6 | **Gece Mesajları Ingest** | DB'ye yazıldı | `SELECT * FROM whatsapp_ai.messages` | 🔴 Doğrulanmadı |
| 7 | **OOH Customer Delivery** | Outbox'ta oluştu | `SELECT * FROM whatsapp_ai.deliveries` | 🔴 Doğrulanmadı |
| 8 | **Evolution Provider Status**| `sent` | `deliveries.status = 'sent'` | 🔴 Doğrulanmadı |
| 9 | **Gerçek WhatsApp Teslimatı**| Müşteri/Admin aldı | Telefon / Evolution Logs | 🔴 Doğrulanmadı |

---

## 3. CANLI GECE MESAJLARI (INCIDENT) POTANSİYEL KÖK NEDEN KATMANLARI

Gece gelen iki müşteri mesajının yanıtsız kalmasının 6 olası canlı ortam kök nedeni:
1. **Schema Drift:** Canlı veritabanında `ingest_message` fonksiyonunun eski 7 parametreli imzada kalması.
2. **Workflow Active Sıfırlanması:** Canlı n8n üzerinde workflow'un `active = false` durumunda kalması.
3. **Webhook URL / Token Uyuşmazlığı:** Evolution API URL token'ı ile veritabanı `webhook_token` farkı.
4. **OOH Wait Branch Kesintisi:** 120 saniyelik bekleme sırasında n8n worker'ın veya zamanlayıcının durması.
5. **Evolution Provider 400/401 Hataları:** Evolution API tarafında instance QR oturumunun düşmesi.
6. **Claim OOH Lock Engeli:** `ooh_log` tablosunda kilitlenme oluşması.

---

## 4. 4 FAZLI CANLI VERİLEŞTİRME VE RECONCILE REHBERİ (RUNBOOK)

Operatörün canlı ortamda sırasıyla çalıştırması gereken 4 adımlı doğrulama prosedürü:

### Faz 1: Canlı Veritabanı Migrasyonlarını Uygulayın ve İmzayı Doğrulayın
Terminalinizde canlı veritabanı URL'ini tanımlayıp migrasyonları uygulayın:
```bash
export WHATSAPP_POSTGRES_URL="postgresql://user:password@host:port/dbname"
python tools/wf_migrate.py
```
*İmza Doğrulama SQL:*
```sql
SELECT routine_name, parameter_name, data_type, ordinal_position
FROM information_schema.parameters
WHERE specific_name LIKE '%ingest_message%'
ORDER BY ordinal_position;
```

### Faz 2: Canlı n8n Workflow'unu Güncelleyin ve Active Edin
```bash
export N8N_BASE_URL="https://n8n.filtreoto.online"
export N8N_API_KEY="<YENI_API_KEY>"
export N8N_WORKFLOW_ID="<CANLI_WORKFLOW_ID>"
export EVOLUTION_BASE_URL="https://evo.filtreoto.online"
export EVOLUTION_API_KEY="<EVOLUTION_API_KEY>"
export EVOLUTION_INSTANCE="otofiltre"
export N8N_WEBHOOK_SECRET="efb34f7a2e23ff3382bdde8a6703b64a796381a0b341f10c"

python tools/webhook_runtime_reconcile.py --apply
```

### Faz 3: Canlı Veritabanı ve Outbox Sorgularını Çalıştırın
```sql
-- 1. Geceki Mesajlar DB'ye Düştü mü?
SELECT id, sender_number, payload->>'conversation' AS mesaj, received_at 
FROM whatsapp_ai.messages WHERE received_at > now() - interval '24 hours' ORDER BY received_at DESC;

-- 2. Batches Hangi Durumda?
SELECT id, sender_number, status, first_message_at, updated_at 
FROM whatsapp_ai.batches ORDER BY updated_at DESC LIMIT 5;

-- 3. Outbox ve Evolution Teslimat Durumu
SELECT id, channel, destination, status, attempt_count, error_message, sent_at 
FROM whatsapp_ai.deliveries ORDER BY created_at DESC LIMIT 5;
```

### Faz 4: Gerçek Senaryo İle Teslimat Emniyetini Doğrulayın
```bash
export N8N_WEBHOOK_URL="https://n8n.filtreoto.online/webhook/evolution-webhook"
export WEBHOOK_TOKEN="efb34f7a2e23ff3382bdde8a6703b64a796381a0b341f10c"

python tools/live_customer_scenario_test.py --confirm-outbound --confirm-live --target-number 90532XXXXXXX
```

---

## 5. NİHAİ YAYIN KARARI (RELEASE DECISION)

```text
================================================================================
  KOD TABANI & DEPO (GIT):       🟢 GO (PASS 100/100 - Commit: 4ca5212)
  CANLI ORTAM (PRODUCTION):      🔴 NO-GO (Canlı Doğrulama Bekliyor)
================================================================================
```
