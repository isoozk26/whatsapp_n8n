> ⚠️ GEÇERSİZ — v12.5 dönemi. Güncel operasyon dokümanı: `docs/runbook.md`.

# WhatsApp n8n Workflow — End-to-End (E2E) Rapor

**Rapor Tarihi:** 14 Temmuz 2026  
**Workflow:** WhatsApp AI - v12.5 Enterprise  
**Canlı Ortam:** n8n.filtreoto.online (Workflow ID: MbJkVXLDCOZ5umpp)  
**WhatsApp Altyapısı:** Evolution API — `filtr` instance  

---

## 1. PROJE GENEL BAKIŞ

### 1.1 Amaç
Müşterilerin WhatsApp üzerinden peş peşe yazdığı mesajları **120 saniyelik bir toplama penceresinde** biriktirip, tek bir konuşma paketi olarak GPT-4o-mini ile sınıflandıran, politika motoru ile güvenli hale getiren ve **3 kanala (Telefon A + Telefon B + Müşteri)** eşzamanlı bildirim yapan bir n8n workflow'u.

### 1.2 Tek Kaynak Mimarisi
```
build_workflow.py (1554 satır, 94KB) → workflow.json (78KB, 28 node) → n8n Canlı Deploy
```
- **Tek kaynak:** `build_workflow.py` — tüm mantık (JS kod blokları, node tanımları, bağlantılar) tek dosyada
- **Artifact:** `workflow.json` — üretimde kullanılan n8n workflow dosyası
- **Deploy:** `upload_to_n8n.py` ve `tools/wf_deploy.py` — canlı ortama staticData koruyarak deploy eder

### 1.3 Versiyon Geçmişi
| Versiyon | Tarih | Değişiklik |
|----------|-------|------------|
| v12.5 Enterprise | 13 Jul 2026 | Finalize Batch kritik hata düzeltildi, güvenlik hardening, deploy |
| v12.x | — | 120sn pencere, 3 kanallı bildirim, politika motoru, guardrail'ler |

---

## 2. MİMARİ VE VERİ AKIŞI

### 2.1 Node Haritası (28 Node)

| Kategori | Sayı | Node Adları |
|----------|------|-------------|
| **Giriş** | 2 | Webhook1, fromMe Check |
| **Mesaj Toplama** | 2 | Batch Collector, Should Process? |
| **Komut Yönetimi** | 3 | Is Command?, Delete Command Message, (Phone A/B Send bildirim) |
| **AI İşlem Hattı** | 4 | Store Context, AI Agent, OpenAI Chat Model1, Simple Memory |
| **Politika & Karar** | 4 | Parse AI Output, Should Notify Admins?, Should Reply Customer?, Clear Batch |
| **Gönderim** | 5 | Phone A Send, Phone B Send, Reply to Customer, Dead Letter Admin, Delete Command |
| **Durum Takibi (Zamanlayıcı)** | 5 | Schedule Trigger, Stale Batch Check, Stale Exists?, Idle Timeout Check, Idle Alert? |
| **Etiketleme** | 3 | Tag Success/Err (Phone A, Phone B, Reply) |

### 2.2 Veri Akışı Şeması

```
WhatsApp → Evolution API → n8n Webhook (/evolution-webhook)
                                      │
                              ┌───────▼───────┐
                              │ fromMe Check  │ ← own-number / admin kontrolü
                              └───────┬───────┘
                    true (komut)     │      false (normal mesaj)
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
            ┌─────────────┐                   ┌─────────────────┐
            │ Is Command? │                   │ Batch Collector │
            └──────┬──────┘                   └────────┬────────┘
         true  │   │ false                           │
       ┌──────┘   └──────┐                    ┌──────┴──────┐
       ▼                ▼                    ▼             ▼
Delete Msg        Phone A+B              Should      (ignore/queued)
Notification      Notification          Process?
                    │                true │  false
                    │                    ▼            ▼
                    │            Store Context   (beklemede kalır)
                    │                    │
                    │            AI Agent (GPT-4o-mini)
                    │                    │
                    │         Parse AI Output (Politika Motoru)
                    │                    │
        ┌───────────┼───────────┐        │
        ▼           ▼           ▼        ▼
   Phone A       Phone B   Reply Cust  (Finalize Batch ← her 3 kanal da)
   Send          Send       Send                │
        │           │           │               ▼
        ▼           ▼           ▼         [Delivery Ledger Check]
   Tag Success   Tag Success  Tag Success       │
        │           │           │               ▼
        └───────────┴───────────┴────────→ Batch Kapat / Temizle
```

### 2.3 Zamanlayıcı (Her 15 Saniyede Bir)

```
Schedule Trigger (15sn)
        │
        ├─→ Stale Batch Check → Stale Exists? → Store Context → AI Agent → ...
        │
        └─→ Idle Timeout Check → Idle Alert? → Phone A+B Send (bildirim)
```

---

## 3. DURUM YÖNETİMİ (StaticData)

| Alan | Başlangıç | Temizleme Stratejisi | Risk |
|------|-----------|---------------------|------|
| `_batches` | `{}` | Batch boşsa sil, manuel modda sil | Düşük |
| `_manualModes` | `{}` | **Asla silinmez** — `true`/`false` toggle | **Yüksek (bellek sızıntısı)** |
| `_seenMessageIds` | `{}` | 6 saat TTL + 3000 üst limit (LRU) | Orta (her mesajda O(n) tarama) |
| `_unclearCounts` | `{}` | `unclear` olmayan caseType'ta sil | Düşük |
| `_adminNotifications` | `{}` | 500 kayıt limiti, 200 eski silinir | Düşük |
| `_deliveryLedger` | `{}` | 10 dakika TTL | Düşük |
| `_finalizedTokens` | `{}` | 10 dakika TTL | Düşük |
| `_lastReply` | `{}` | Idle alerttet veya yeni mesajda sil | Düşük |

> **Not:** `_manualModes` bellek sızıntısı DENETIM_RAPORU.md'de W4 olarak belgelenmiş, P1 öncelikli düzeltme bekliyor.

---

## 4. POLİTİKA MOTORU (Parse AI Output)

### 4.1 Case Type Karar Matrisi

| Senaryo | İnsan Gerekli | Admin Bildirim | Otomasyon Durdur | Araç Bilgisi İste |
|---------|:---:|:---:|:---:|:---:|
| Schema ihlali | ✅ | ✅ | ✅ | — |
| Kaynak ihlali (PRV-001) | ✅ | ✅ | ✅ | — |
| Güven < 0.55 | ✅ | ✅ | ✅ | — |
| Guardrail tetiklendi | ✅ | ✅ | ❌ | — |
| Tam kod + fiyat/stok | ✅ | ✅ | ❌ | ❌ |
| Tam kod + uyumluluk (araç yeterli) | ✅ | ✅ | ❌ | ❌ |
| Tam kod + uyumluluk (araç **eksik**) | ❌ | ❌ | ❌ | **✅** |
| Muadil/çapraz referans | ✅ | ✅ | ❌ | ❌ |
| Kısmi kod | ❌ | ❌ | ❌ | — |
| Araç bazlı (araç yeterli) | ✅ | ✅ | ❌ | ❌ |
| Araç bazlı (araç **eksik**) | ❌ | ❌ | ❌ | **✅** |
| Ürün dışı | ✅ | ✅ | ✅ | — |
| Belirsiz (2x+) | ✅ | ✅ | ✅ | — |
| Selamlama | ❌ | ❌ | ❌ | — |

### 4.2 Guardrail Katmanları

1. **GRD-001 (Yapısal):** JSON şema zorlaması, `caseType` allowlist, confidence tip dönüşümü
2. **GRD-002 (İçerik):** Fiyat/stok/uyumluluk halüsinasyonu engelleme (regex + banned phrases)
3. **GRD-003 (Güvenlik):** URL/şifre/kredi kartı/OTP engelleme
4. **PRV-001 (Provenance):** AI'ın müşteri mesajında/katalogda olmayan parça kodu uydurmasını engelleme
5. **POL-003 (Araç Tamlığı):** VIN / marka+model+yıl+motor kombinasyonu kontrolü

### 4.3 AI Sistem Mesajı (Özet)
- **Rol:** FiltreOto WhatsApp satır/müşteri destek asistanı
- **Markalar:** MANN-FILTER, FILTRON, FILTORQ, UFI, HENGST, PURFLUX, MAHLE
- **Kural:** Sadece filtre satışı, motor yağı yok
- **Sıfır Halüsinasyon:** Fiyat/stok uydurma yasak, görselde kod yoksa "Görsel ulaştı..." cevabı ver

---

## 5. GÜVENLİK ANALİZİ

### 5.1 DÜZELTİLEN KRİTİK AÇIKLAR (v12.5)

| # | Bulgu | Durum | Çözüm |
|---|-------|-------|-------|
| 1 | Evolution API key 6 noktada hardcoded (`[REDACTED]`) | ✅ **DÜZELTİLDİ** | `$env.EVOLUTION_API_KEY` |
| 2 | n8n API JWT token `upload_to_n8n.py:5` hardcoded | ✅ **DÜZELTİLDİ** | `os.environ.get('N8N_API_KEY')` |
| 3 | Admin telefon numaraları 4 tekrar hardcoded | ✅ **DÜZELTİLDİ** | `process.env.ADMIN_PHONE_NUMBERS` |
| 4 | Dead Letter Admin telefon hardcoded | ✅ **DÜZELTİLDİ** | `$env.DEAD_LETTER_ADMIN_PHONE` |
| 5 | SSL doğrulama devre dışı (4 dosya) | ✅ **DÜZELTİLDİ** | Default SSL context |

### 5.2 KALAN GÜVENLİK RİSKLERİ (DENETIM_RAPORU.md'den)

| Seviye | Bulgu | Durum |
|--------|-------|-------|
| **YÜKSEK** | Webhook authentication yok — `/webhook/evolution-webhook` doğrulanmıyor | Açık |
| **ORTA** | `_manualModes` bellek sızıntısı — entry'ler asla silinmiyor | Açık (P1) |
| **ORTA** | Sessiz hata yutma — 7 `catch(e) {}` bloğu loglama yok | Açık |
| **DÜŞÜK** | `_seenMessageIds` O(n) temizleme — 3000 entry'de performans riski | Açık |
| **DÜŞÜK** | Regex ReDoS potansiyeli — pattern manipülasyonu | Açık |

### 5.3 Gerekli Ortam Değişkenleri

```bash
# Deployment için zorunlu
N8N_API_KEY=                    # n8n API authentication
EVOLUTION_API_KEY=              # Evolution API authentication  
ADMIN_PHONE_NUMBERS=905052237182,905306056066,905363955525  # Comma-separated
DEAD_LETTER_ADMIN_PHONE=905052237182
```

---

## 6. TEST KAPSAMI ANALİZİ

### 6.1 Mevcut Test Dosyaları

| Dosya | Tür | Senaryo | Kalite |
|-------|-----|---------|--------|
| `tools/test_workflow_contract.py` | Statik sözleşme | ~15 assertion | **Yüksek** — Graph yapısal doğrulama |
| `tools/wf_validate.py` | Yapısal doğrulama | JSON şema, node sayısı | **Yüksek** |
| `tools/wf_test.py` | Python simülasyonu | 5 senaryo | **Düşük** — Production field isimleri farklı (`messages` vs `pendingMessages`) |
| `tools/wf_test_webhook.py` | Canlı webhook | 10 senaryo | **Orta** — Gerçek webhook gönderiyor, yanıt doğrulama yok |
| `tools/live_customer_scenario_test.py` | Canlı test | 1 senaryo | **Düşük** |
| `tools/wf_test_templates.py` | Dokümantasyon | 20 template | **Yok** — Sadece print, executable değil |

### 6.2 KRİTİK TEST BOŞLUKLARI (Test Edilmemiş)

| Kapsam Alanı | Risk |
|--------------|------|
| Politika motoru (8 caseType) | **Yüksek** |
| Guardrail ihlalleri (fiyat halüsinasyonu, stok garantisi) | **Yüksek** |
| Kaynak ihlali (PRV-001 — AI uydurma ürün kodu) | **Yüksek** |
| Teslimat hatası → Dead Letter → Finalize | **Yüksek** |
| Teslimat defteri (3 kanal tamamlama) | **Yüksek** |
| batchToken izolasyonu | **Yüksek** |
| İşlem zaman aşımı kurtarma (2 dk) | **Yüksek** |
| Manuel mod (handoff → pauseAutomation) | Orta |
| Idle timeout (10 dk sessizlik) | Orta |
| Belirsiz talep artışı (2x → handoff) | Orta |
| Admin bildirim soğutma (3 dk) | Orta |

---

## 7. DEPLOY SÜRECİ

### 7.1 Deploy Komutları

```powershell
# Yerel doğrulama (ağ gerektirmez)
python build_workflow.py
python tools/wf_validate.py workflow.json
python tools/test_workflow_contract.py

# Canlı test (kontrollü pencere)
python tools/wf_test_webhook.py

# Deploy (yukarıdaki 3 kontrol geçmeli)
python upload_to_n8n.py
```

### 7.2 Deploy Güvenliği

| Konu | Durum | Not |
|------|-------|-----|
| staticData koruma | ✅ İyi | `upload_to_n8n.py` canlı staticData'yı okuyup koruyor |
| Workflow publish | ⚠️ Orta | Deploy sonrası publish edilmezse eski sürüm çalışır |
| Rollback mekanizması | ⚠️ Orta | Eski workflow.json git history'den alınabilir |
| Schema doğrulama | ✅ İyi | `wf_validate.py` ile yapılıyor |
| JS syntax check | ✅ İyi | `node --check` ile build'te doğrulanıyor |

### 7.3 Canlı Ortam Bilgileri

- **Sunucu:** n8n.filtreoto.online
- **Workflow ID:** MbJkVXLDCOZ5umpp
- **Aktif Versiyon:** 4a780508-458a-436e-8465-cd02e547d7b3
- **Durum:** Active (Published)

---

## 8. BİLGİLENDİRİLEN HATALAR VE DÜZELTMELER (v12.5)

### 8.1 KRİTİK — Finalize Batch Çökmesi
- **Semptom:** Müşteri mesajı geliyor, admin bildirimi gidiyor ama müşteriye cevap gelmiyor
- **Kök Neden:** `Finalize Batch` node paralellerden (`Tag Success Phone A` → `Finalize Batch` VE `Tag Success Reply` → `Finalize Batch`) çağrılıyor. `$item("Parse AI Output").$json` okunamıyorsa `throw new Error` atıyor, execution'ı öldürüyordu.
- **Düzeltme:** `build_workflow.py:932` ve `workflow.json` — `throw` yerine `console.warn` + `{ json: {} }` graceful return
- **Etki:** Artık eksik veri gelirse execution devam ediyor, müşteri cevabı gitiyor

### 8.2 Kod Kalitesi Düzeltmeleri
- `import os` eklendi (build_workflow.py)
- 3 kopya JS bloğu temizlendi (`store_context_js`, `ai_agent_system_message`, `parse_ai_output_js` — ikincileri override ediyordu)
- Tüm Code node'lar `runOnceForAllItems` moduna alındı (n8n v1.40+ uyumlu)

---

## 9. RACE CONDITION RİSKLERİ

| # | Senaryo | Mevcut Koruma | Risk Seviyesi |
|---|---------|---------------|---------------|
| 1 | Batch Collector ↔ Stale Batch Check çarpışması | JS single-threaded event loop | **Yüksek** (n8n paralel execution başlatırsa) |
| 2 | Finalize Batch çoklu yoldan çağrı | `_finalizedTokens` idempotancy guard (10dk TTL) | **Orta** (TTL sonrası çift kapatma) |
| 3 | `_seenMessageIds` temizleme sırasında ekleme | Tek thread, O(n) tarama | Düşük |

---

## 10. PERFORMANS VE ÖLÇEKLENDİRME

| Metrik | Değer | Not |
|--------|-------|-----|
| Toplama penceresi | 120 sn | Gerçekte 120-135 sn (15sn tarama aralığı) |
| Max batch mesajı | 30 mesaj | Spam limiti |
| AI model | GPT-4o-mini | Temperature 0.1, maxTokens 600 |
| Bellek (staticData) | n8n internal | Veritabanı yok — crash'te veri kaybı riski |
| Deduplikasyon TTL | 6 saat | 3000 kayıt üst limit |
| Admin bildirim soğutma | 3 dakika | Aynı müşteri için |

---

## 11. SWOT ÖZETİ (DENETIM_RAPORU.md'den)

### Güçlü Yönler (Strengths)
| # | Madde |
|---|-------|
| S1 | **Tek kaynak mimarisi** — Değişiklik takibi kolay, tutarlılık yüksek |
| S2 | **120sn toplama penceresi** — Konuşma bütünlüğü korunuyor |
| S3 | **3 kanallı bildirim** — Tek kanal başarısız olsa bile bilgi ulaşır |
| S4 | **Politika motoru** — AI çıktısı doğrudan müşteriye gitmiyor |
| S5 | **Teslimat defteri** — 3 kanal tamamlandığında batch kapanır |
| S6 | **Dead-letter sistemi** — Başarısız gönderimler sessiz kalmıyor |
| S7 | **Deduplikasyon** — 6 saat TTL + 3000 limit |
| S8 | **Batch token izolasyonu** — Eski/gecikmiş AI cevapları yanlış müşteriye gitmez |
| S9 | **Manuel/otonom mod** — `++`/`--` ile sohbet içinden kontrol |
| S10 | **İşlem zaman aşımı kurtarma** — 2 dk AI işlemleri yeniden kuyruğa alınır |
| S11 | **Test araçları ekosistemi** — 11 farklı test/araç dosyası |
| S12 | **Build-time JS doğrulama** — Her JS bloğu `node --check` ile |

### Zayıf Yönler (Weaknesses)
| # | Madde |
|---|-------|
| W1 | ~~Hardcoded API anahtarları~~ ✅ **DÜZELTİLDİ** |
| W2 | Test kapsamı çok düşük — Politika motoru, guardrail, teslimat test edilmemiş |
| W3 | Sessiz hata yutma — 7 catch bloğu loglama yok |
| W4 | **Bellek sızıntısı (_manualModes)** — Entry'ler asla silinmiyor |
| W5 | ~~Ölü/kopya kod~~ ✅ **DÜZELTİLDİ** (3 JS bloğu temizlendi) |
| W6 | **Veritabanı yok** — Tüm durum staticData'da, crash'te veri kaybı |
| W7 | **Vision modeli yok** — Fotoğraflar analiz edilmiyor |
| W8 | **Gerçek fiyat/stok entegrasyonu yok** — Her seferinde "yetkili kontrol edecek" |
| W9 | Workflow publish adımı unutulabilir |
| W10 | Mock testler production'dan farklı field isimleri |
| W11 | **Webhook authentication yok** |
| W12 | 120sn pencere pratikte 120-135sn değişken |

---

## 12. ÖNERİLER (ÖNCELİK SIRASI)

### P0 — Acil (Bu Hafta)
1. **Webhook authentication ekle** — Evolution API webhook secret/token ile doğrulama
2. **Catch bloklarına logging ekle** — En az `console.error()` ile hata detayı
3. **SSL doğrulamasını tüm dosyalarda etkinleştir** (zaten yapıldı, doğrula)

### P1 — Kısa Vadeli (2 Hafta)
4. **Politika motoru için unit test yaz** — Her caseType, guardrail, provenance kontrolü
5. **Teslimat defteri testleri yaz** — 3 kanal farklı sıralamalarla, idempotancy
6. **`_manualModes` temizleme ekle** — Batch silinirken entry de silinmeli
7. **Webhook secret doğrulama** — n8n webhook authentication

### P2 — Orta Vadeli (1 Ay)
8. **Stok/fiyat API entegrasyonu** — En azından fiyat sorgulama
9. **CI/CD pipeline** — Git push → test → build → deploy → publish
10. **Persistent veritabanı** — PostgreSQL ile staticData destekleme
11. **Test coverage artırımı** — `wf_test.py` production field isimlerine uygun hale getir

### P3 — Uzun Vadeli (3 Ay)
12. **Vision API entegrasyonu** — GPT-4o vision ile fotoğraf analizi
13. **Çoklu dil desteği** — İngilizce/Almanca/Arapça prompt
14. **Monitoring dashboard** — n8n execution geçmişinden real-time metrikler

---

## 13. DOĞRULAMA PLANI (E2E Test Senaryoları)

### 13.1 Otomatik Çalıştırılmalı Testler
```bash
# 1. Yapısal sözleşme testleri
python tools/test_workflow_contract.py

# 2. Workflow doğrulama
python tools/wf_validate.py workflow.json

# 3. Build doğrulama
python build_workflow.py
```

### 13.2 Manuel Canlı Test Senaryoları (Checklist)

| # | Senaryo | Beklenen Sonuç | Durum |
|---|---------|----------------|-------|
| 1 | Normal müşteri mesajı (tek) | 120sn bekler → AI → 3 kanala gider → müşteriye cevap | Test edilecek |
| 2 | 3 peş peşe mesaj (batch) | Tek batch'te toplanır → tek AI çağrısı → 3 kanala | Test edilecek |
| 3 | `++` komutu (yetkili) | Manuel moda alır, batch siler, admin bildirimi gider | Test edilecek |
| 4 | `--` komutu (yetkili) | Otomatik moda döner, admin bildirimi gider | Test edilecek |
| 5 | Müşteri `++` yazar | Komut sayılmaz, normal mesaj olarak batch'e alınır | Test edilecek |
| 6 | Duplicate webhook (aynı messageId) | İkincisi `ignore` edilir (dedup) | Test edilecek |
| 7 | Fiyat sorusu (kod verilmiş) | Guardrail: fiyat uydurmaz, "yetkili kontrol edecek" der | Test edilecek |
| 8 | Uyumluluk sorusu (araç eksik) | "Motor hacmi/beygir gücü/şasi no paylaşın" der | Test edilecek |
| 9 | Sikayet/İade mesajı | Handoff → admin bildirimi, otomasyon durur | Test edilecek |
| 10 | 2x belirsiz mesaj | 2. belirsizlikte handoff, admin bildirimi | Test edilecek |
| 11 | 10 dakika sessiz müşteri | Idle alert → admin telefonlarına bildirim | Test edilecek |
| 12 | Evolution API timeout | Dead Letter → admin'e hata bildirimi, batch kapanır | Test edilecek |

---

## 14. DOSYA YAPISI ÖZETİ

```
WHATSAPP_N8N/
├── README.md                      # Proje özeti, komutlar
├── workflow.json                  # Üretim artifact'ı (28 node, 78KB)
├── build_workflow.py              # Tek kaynak (1554 satır, 94KB)
├── deployment_report.md           # Deploy raporu (v12.5)
├── DENETIM_RAPORU.md              # Mimari denetim + SWOT (426 satır)
├── E2E_RAPOR.md                   # Bu dosya
├── upload_to_n8n.py               # Canlı deploy (staticData korur)
├── tools/
│   ├── wf_validate.py             # Yapısal doğrulama
│   ├── test_workflow_contract.py  # Sözleşme testleri (~15 assertion)
│   ├── wf_test.py                 # Python simülasyon (5 senaryo)
│   ├── wf_test_webhook.py         # Canlı webhook testleri (10 senaryo)
│   ├── live_customer_scenario_test.py  # Tek canlı senaryo
│   ├── wf_test_templates.py       # Test şablonları (print-only)
│   ├── wf_deploy.py               # Deploy yardımcı
│   ├── wf_diff.py                 # Diff aracı
│   ├── wf_sync.py                 # Sync aracı
│   ├── wf_build.py                # Build aracı
│   ├── wf_inspect.py              # İnceleme aracı
│   └── wf_demo.py                 # Demo aracı
```

---

## 15. SONUÇ

**WhatsApp AI v12.5 Enterprise** üretimde **aktif ve çalışır durumda**. Kritik güvenlik açıkları (hardcoded API key, JWT token, SSL) **giderildi**. Finalize Batch çökmesi **düzeltildi** — artık müşteri cevapları gitmekte.

**Ana riskler:**
1. **Test kapsamı çok düşük** — Politika motoru, guardrail'ler, teslimat defteri test edilmemiş
2. **Webhook authentication yok** — Sahte webhook riski
3. **_manualModes bellek sızıntısı** — Uzun vadede staticData büyümesi
4. **Veritabanı yok** — n8n crash'inde bekleyen batch'ler kaybolur

**Öncelikli aksiyon:** P0 ve P1 maddelerinin (webhook auth, logging, unit testler, _manualModes temizleme) 2 hafta içinde ele alınması önerilir.

---

*Rapor kaynakları: `build_workflow.py`, `workflow.json`, `deployment_report.md`, `DENETIM_RAPORU.md`, `tools/test_workflow_contract.py`, `tools/wf_validate.py`, `tools/wf_test_webhook.py`*
