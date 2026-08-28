# 🔬 WhatsApp AI / n8n — Codex 5.4 Kod Düzeltme ve Operasyon Rehberi Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 28 Ağustos 2026  
**Kapsam:** Codex 5.4 için Tüm Hataların Detaylı Düzeltme Görev Kartları ve Uygulama Rehberi (`docs/runbook.md`).

---

## 1. YÖNETİCİ ÖZETİ

Tespit edilen tüm hataların **Codex 5.4** modeli tarafından kod seviyesinde eksiksiz ve tek seferde düzeltilebilmesi amacıyla **[docs/runbook.md](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md)** dokümanı güncellenmiş ve **9 Adet Detaylı Codex 5.4 Görev Kartı (K-01'den K-08'e)** hazırlanmıştır.

---

## 2. CODEX 5.4 İÇİN HAZIRLANAN DÜZELTME GÖREV KARTLARI

| Görev Kartı | İlgili Dosya / Konum | Sorun Özeti | Codex 5.4 Hedef Çözümü |
|---|---|---|---|
| **K-01** | `build_workflow.py:514` | `Suzuki`, `Mini`, `BMW` vb. markalar eksik. | `brands` dizisine eksik markalar eklenecek. |
| **K-02** | `build_workflow.py:504` | Papağan döngüsü (aynı soruyu 3 kez sorma). | `lastReplyText` ile aynı metin üretilirse `action = 'handoff'` yapılacak. |
| **K-03** | `build_workflow.py:461` | `"Mesai mesai saatleri..."` typo'su. | `SLA_LINE` şablon birleşimi düzeltilecek. |
| **K-04** | `build_workflow.py:82` | Ingress event filtresi eksik. | `MESSAGES_UPSERT` dışındaki webhook'lar süzülecek. |
| **K-05** | `build_workflow.py:1267` | HTTP 400 hatasında false `customer_sent=true`. | HTTP status < 400 şartına bağlanacak. |
| **K-06** | `build_workflow.py:984` | OOH adreste `@lid` silinip geçersiz numara üretilmesi. | E.164 sanitization uygulanacak. |
| **K-07** | `build_workflow.py:1170` | DB sorgusunun auth öncesi çalışması. | Token auth preflight öne alınacak. |
| **K-08** | `tools/test_policy_engine.test.js` | Legacy test paketinde exit 1 (FAIL). | Test beklentileri v13 outbox yapısına hizalanacak. |
| **K-09** | `.gitignore` | 52MB dump dosyasının repoya girmesi. | `postgresql_backup/` gitignore'a eklenecek. |

---

## 3. CODEX 5.4 SONRASI UYGULANACAK TEST ZİNCİRİ

Codex 5.4 ile kod düzeltmeleri yapıldıktan sonra çalıştırılması gereken doğrulama komutları:

```bash
# 1. Workflow derleme ve JSON doğrulama
python build_workflow.py
python tools/wf_validate.py workflow.json

# 2. Test paketleri
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/test_ops_drift_check.py
python tools/test_outbound_guard.py
node tools/test_policy_engine.test.js

# 3. Kalite kapısı
npm run release:gate
```

---

> *İşbu rapor ve [docs/runbook.md](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md) rehberi Codex 5.4 modelinin kod tabanındaki tüm hataları tek adımda düzeltebilmesi için hazırlanmıştır.*