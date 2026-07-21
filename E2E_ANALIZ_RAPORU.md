# WhatsApp n8n Workflow — Uçtan Uca (E2E) Analiz Raporu

**Workflow ID:** MbJkVXLDCOZ5umpp  
**Rapor Tarihi:** 14 Temmuz 2026  
**Workflow:** WhatsApp AI - v12.5 Enterprise  
**Canlı Ortam:** n8n.filtreoto.online  
**WhatsApp Altyapısı:** Evolution API — filtr instance  
**Kaynak Kod:** `build_workflow.py` (1554 satır, 94KB) → `workflow.json` (78KB, 29 node)  
**Not:** Bu rapor `DENETIM_RAPORU.md` (13 Temmuz 2026) ve `deployment_report.md` baz alınarak, son 3 plandaki düzeltmeler (Finalize Batch fix, runOnceForAllItems, fallback koruması, isim gizlilik) entegre edilerek hazırlanmıştır.

---

## 1. YÖNETİCİ ÖZETİ

### Sistem Amacı
Müşterinin WhatsApp üzerinden peş peşe yazdığı mesajları ayrı ayrı cevaplamak yerine tek bir konuşma paketi içinde toplamak, 120 saniyelik pencerede bekletmek, GPT-4o-mini ile sınıflandırmak ve çok kanallı (Telefon A + Telefon B + Müşteri) bildirim yapmak.

### Kritik Metrikler
| Metrik | Değer | Durum |
|--------|-------|-------|
| Node Sayısı | 29 | ✅ |
| Bağlantı Sayısı | 29 kaynak | ✅ |
| JS Kod Blokları | 13 (syntax check geçti) | ✅ |
| StaticData Alanları | 8 (_batches, _manualModes, _seenMessageIds, _unclearCounts, _adminNotifications, _deliveryLedger, _finalizedTokens, _lastReply) | ✅ |
| Güvenlik Açığı (Kritik) | 6 hardcoded API key + 1 JWT token | 🔴 **AÇIK** |
| Test Kapsamı (Politika Motoru) | 0% | 🔴 **BOŞ** |
| Race Condition Riski | 5 senaryo | 🟡 **ORTA** |
| Bellek Sızıntısı | _manualModes asla temizlenmiyor | 🟡 **ORTA** |

### Öncelikli Aksiyon Özeti
| Öncelik | Eylem | Sahip | Süre |
|---------|-------|-------|------|
| P0 | API anahtarlarını n8n credential vault'una taşı | DevOps | Bu hafta |
| P0 | `upload_to_n8n.py` JWT token'ını `.env`'e taşı | DevOps | Bu hafta |
| P0 | Catch bloklarına logging ekle | Backend | Bu hafta |
| P0 | SSL doğrulamasını etkinleştir (4 dosya) | DevOps | Bu hafta |
| P1 | Politika motoru için unit test yaz | QA | 2 hafta |
| P1 | Teslimat defteri testleri yaz | QA | 2 hafta |
| P1 | `_manualModes` temizleme ekle | Backend | 2 hafta |
| P1 | Ölü kodu temizle (3 JS bloğu) | Backend | 2 hafta |
| P1 | Webhook authentication ekle | Backend | 2 hafta |

---

## 2. SİSTEM MİMARİSİ

### 2.1 Veri Akışı Mimarisi

```
WhatsApp → Evolution API → n8n Webhook (/evolution-webhook)
                                    │
                              fromMe Check
                           ┌────┴────┐
                        true        false
                    (++/-- komut)  (normal mesaj)
                         │              │
                  Delete+Notify    Batch Collector
                                    │
                              Should Process?
                           ┌────┴────┐
                        false        true
                    (beklemede)  (120sn doldu)
                                    │
                           Store Context (regex)
                                    │
                            AI Agent (GPT-4o-mini)
                                    │
                         Parse AI Output (politika)
                              ┌─────┼─────┐
                              │     │     │
                          Phone A Phone B Customer
                              │     │     │
                          Tag Success/Err (her kanal)
                              │     │     │
                          Dead Letter (hatalı ise)
                              │     │     │
                           Finalize Batch
```

### 2.2 Paralel Zamanlayıcı (Her 15sn)
```
Schedule Trigger ─┬─ Stale Batch Check → Store Context → ...
                  └─ Idle Timeout Check → Phone A+B Bildirim
```

### 2.3 Node Haritası (29 Node)

| Kategori | Node Sayısı | Node Adları |
|----------|:-----------:|-------------|
| Giriş | 2 | Webhook1, fromMe Check |
| Mesaj Toplama | 2 | Batch Collector, Should Process? |
| Komut Yönetimi | 3 | Is Command?, Delete Command Message, (bildirimler) |
| AI İşlem Hattı | 4 | Store Context, AI Agent, OpenAI Chat Model1, Simple Memory |
| Politika & Karar | 4 | Parse AI Output, Should Notify Admins?, Should Reply Customer?, Clear Batch |
| Gönderim | 5 | Phone A Send, Phone B Send, Reply to Customer, Dead Letter Admin, (Delete Command) |
| Durum Takibi | 5 | Schedule Trigger, Stale Batch Check, Stale Exists?, Idle Timeout Check, Idle Alert? |
| Etiketleme | 6 | Tag Success Phone A/B/Reply, Tag Err Phone A/B/Reply |

### 2.4 Durum Yönetimi (StaticData)

| Alan | Başlangıç | Temizleme Stratejisi | Risk |
|------|-----------|---------------------|------|
| `_batches` | Boş obje | Batch boşsa sil, manuel modda sil | Düşük |
| `_manualModes` | Boş obje | **Asla silinmez** — `true`/`false` sadece toggle | **Yüksek (bellek sızıntısı)** |
| `_seenMessageIds` | Boş obje | 6 saat TTL + 3000 üst limit (LRU) | Orta (her mesajda O(n) tarama) |
| `_unclearCounts` | Boş obje | `unclear` olmayan caseType'ta sil | Düşük |
| `_adminNotifications` | Boş obje | 500 kayıt limiti, 200 eski silinir | Düşük |
| `_deliveryLedger` | Boş obje | 10 dakika TTL | Düşük |
| `_finalizedTokens` | Boş obje | 10 dakika TTL | Düşük |
| `_lastReply` | Boş obje | Idle alerttet veya yeni mesajda sil | Düşük |

### 2.5 İşlem Zaman Çizelgesi

```
T+0s     Müşteri ilk mesajı gönderir
T+0s     Webhook yanıt verir, mesaj batch'e eklenir
T+15s    İlk Stale Batch Check çalışır (henüz 120sn dolmadı)
T+30s    İkinci Stale Batch Check
...
T+120s   120 saniye doldu → batch processing'e alınır
T+120-135s Sonraki Stale Batch Check'te batch claimed edilir
T+135s   Store Context (regex tarama)
T+136s   AI Agent (GPT-4o-mini çağrısı)
T+137s   Parse AI Output (politika motoru)
T+138s   Phone A + Phone B + Customer gönderimi (paralel)
T+138s   Teslimat defteri kontrolü
T+139s   Batch kapatılır
```

---

## 3. GÜVENLİK ANALİZİ

### 3.1 KRİTİK — Hardcoded API Anahtarı (6 Tekrar)

**Bulgu:** Evolution API anahtarı `[REDACTED]` kaynak kodda düz metin olarak 6 kez tekrar ediyor.

| Konum | Satır | Node |
|-------|:-----:|------|
| `build_workflow.py` | 1121 | Delete Command Message |
| `build_workflow.py` | 1203 | Phone A Send |
| `build_workflow.py` | 1243 | Phone B Send |
| `build_workflow.py` | 1283 | Reply to Customer |
| `build_workflow.py` | 1323 | Dead Letter Admin |
| `upload_to_n8n.py` | 6 | n8n API JWT tokenı |

**Risk:** Repo erişimi olan herkes WhatsApp mesajı gönderebilir, mesaj silebilir veya Evolution API'yi suistimal edebilir.  
**Öneri:** Tüm API anahtarlarını n8n credential vault'una taşıyın. `upload_to_n8n.py`'daki JWT tokenını ortam değişkenine taşıyın.

### 3.2 YÜKSEK — n8n API JWT Tokenı Kaynak Kodda

**Bulgu:** `upload_to_n8n.py:6` satırında n8n API JWT tokenı düz metin olarak yer alıyor. Bu token ile workflow güncellenebilir, silinebilir veya okunabilir.

**Öneri:** Token'ı `.env` dosyasına veya n8n credential system'ine taşıyın.

### 3.3 YÜKSEK — Webhook Authentication Yok

**Bulgu:** `/webhook/evolution-webhook` endpoint'inde herhangi bir authentication mekanizması bulunmuyor. Evolution API'den gelen webhook'lar doğrulanmıyor.

**Risk:** Yetkisiz kaynaklar sahte webhook'lar gönderebilir.  
**Öneri:** Webhook secret/token veya IP whitelist ekleyin.

### 3.4 ORTA — Hardcoded Admin Telefon Numaraları (4 Tekrar)

**Bulgu:** `905052237182`, `905306056066`, `905363955525` numaraları hem yetkilendirme mantığında hem de gönderim hedeflerinde hardcoded.

**Öneri:** Numaraları n8n credential system veya environment variable'a taşıyın.

### 3.5 ORTA — SSL Doğrulaması Devre Dışı (4 Dosya)

**Bulgu:** `ssl._create_unverified_context()` 4 farklı dosyada kullanılıyor:

| Dosya | Satır |
|-------|:-----:|
| `upload_to_n8n.py` | 13 (artık `context = None` - düzeltildi) |
| `tools/wf_test_webhook.py` | 10 |
| `tools/wf_deploy.py` | 39 |
| `tools/live_customer_scenario_test.py` | 50 |

**Risk:** Man-in-the-middle saldırılarına açık.  
**Öneri:** SSL sertifika doğrulamasını tüm dosyalarda etkinleştirin.

---

## 4. KOD KALİTESİ VE TEKNİK BORÇ

### 4.1 YÜKSEK — Sessiz Hata Yutma (7 Catch Bloğu)

| Satır | Blok | Yutulan Hata |
|-------|------|-------------|
| 392-394 | `Store Context` okuma | Upstream node hatası |
| 412-421 | AI JSON parse (1. deneme) | Geçersiz JSON |
| 575-582 | `Store Context` okuma (tekrar) | Aynı |
| 599-606 | AI JSON parse (tekrar) | Aynı |
| 1103 | Batch okuma | Merge hatası |
| 1105 | Input okuma | `$input.item.json` hatası |
| 1509-1513 | Workflow.json okuma | Bozuk dosya — tüm veriyi siler |

**Risk:** Hatalar sessizce yutuluyor, debug imkansız. Özellikle satır 1509'daki `except Exception: wf = {}` eğer workflow.json bozulursa tüm veriyi sessizce siler.  
**Öneri:** Her catch bloğuna logging ekleyin. Kritik hatalarda fail-safe davranın.

### 4.2 ORTA — Ölü/Kopya Kod (3 Değişken)

| Değişken | İlk Tanım | İkinci Tanım (Override) | Satırlar |
|----------|-----------|------------------------|----------|
| `store_context_js` | 243-316 (tam) | - | Tek tanım (eski kopya silinmiş) |
| `ai_agent_system_message` | 320-373 | - | Tek tanım (eski kopya silinmiş) |
| `parse_ai_output_js` | 375-1099 | - | Tek tanım (eski kopya silinmiş) |

**Durum:** Eski planlardaki kopya kodları **temizlenmiş**. `test_workflow_contract.py` satır 96-99 bu doğrulamayı yapıyor.

### 4.3 ORTA — Bellek Sızıntısı: `_manualModes`

**Bulgu:** `_manualModes` asla temizlenmiyor. `++` ile `true`, `--` ile `false` yapılıyor ancak entry hiç silinmiyor.

**Risk:** Uzun süreli kullanımda `_manualModes` objesi büyüyecek.  
**Öneri:** Müşteri batch'i tamamen silindiğinde `_manualModes` entry'sini de silin (`build_workflow.py` satır 1000-1011 kısmi temizlik var, eksik).

### 4.4 DÜŞÜK — `_seenMessageIds` O(n) Temizleme

**Bulgu:** Her gelen mesajda tüm `_seenMessageIds` objesi taranıyor (6 saat TTL kontrolü). 3000 entry ile bu performans sorunu olabilir.

**Öneri:** Lazy cleanup veya periyodik cleanup kullanın.

---

## 5. EŞ ZAMANLILIK (RACE CONDITION) ANALİZİ

### 5.1 YÜKSEK — Batch Collector ↔ Stale Batch Check Çarpışması

**Bulgu:** `splice(0)` (satır 212) ve `batch.processing = true` (satır 215) ayrı satırlarda. Eğer n8n aynı anda iki execution çalıştırırsa mesaj kaybolabilir.

**Mevcut Koruma:** JavaScript tek threaded event loop'u — synchronous blok içinde güvenli.  
**Risk:** n8n paralel execution başlatırsa risk gerçekleşir.

### 5.2 ORTA — Finalize Batch Çoklu Yoldan Çağrı

**Bulgu:** Hem `Should Notify Admins?` hem `Should Reply Customer?` bağımsız olarak `Finalize Batch`'e bağlanıyor. Aynı batchToken için iki paralel finalizasyon denemesi olabilir.

**Mevcut Koruma:** `_finalizedTokens` idempotancy guard'ı var.  
**Risk:** Guard 10 dakika sonra TTL ile siliniyor — bu sürede geç teslimat gelirse çift kapatma riski.

### 5.3 DÜŞÜK — Batch Token İzolasyonu

**Mevcut Koruma:** `batchToken` ile her batch benzersiz token alıyor, `Parse AI Output` içinde doğrulama yapılıyor (`validClaim` kontrolü).  
**Durum:** Güvenli.

---

## 6. TEST KAPSAMI ANALİZİ

### 6.1 Mevcut Testler

| Test Dosyası | Tür | Senaryo Sayısı | Kalite |
|-------------|-----|:--------------:|--------|
| `wf_test.py` | Python simülasyonu | 5 | **Düşük** — Production'dan farklı field isimleri, assertion yok |
| `wf_test_webhook.py` | Canlı webhook | 10 | **Orta** — Gerçek webhook gönderiyor ama yanıt doğrulama yok |
| `test_workflow_contract.py` | Statik sözleşme | ~15 | **Yüksek** — Graph yapısal doğrulama iyi |
| `wf_test_templates.py` | Dokümantasyon | 20 | **Yok** — Sadece print, executable değil |
| `live_customer_scenario_test.py` | Canlı test | 1 | **Düşük** — Tek senaryo |

### 6.2 Kritik Test Kapsamı Boşlukları

| Kapsam Alanı | Durum | Risk |
|-------------|-------|------|
| Politika motoru (8 caseType) | **Test edilmemiş** | Yüksek |
| Guardrail ihlalleri (fiyat halüsinasyonu, stok garantisi) | **Test edilmemiş** | Yüksek |
| Kaynak ihlali (PRV-001 — AI uydurma ürün kodu) | **Test edilmemiş** | Yüksek |
| Teslimat hatası → Dead Letter → Finalize | **Test edilmemiş** | Yüksek |
| Teslimat defteri (3 kanal tamamlama) | **Test edilmemiş** | Yüksek |
| batchToken izolasyonu | **Test edilmemiş** | Yüksek |
| İşlem zaman aşımı kurtarma (2 dk) | **Test edilmemiş** | Yüksek |
| Manuel mod (handoff → pauseAutomation) | **Test edilmemiş** | Orta |
| Idle timeout (10 dk sessizlik) | **Test edilmemiş** | Orta |
| Belirsiz talep artışı (2x → handoff) | **Test edilmemiş** | Orta |
| Admin bildirim soğutma (3 dk) | **Test edilmemiş** | Orta |

---

## 7. DEPLOY VE OPERASYONEL GÜVENLİK

| Konu | Durum | Risk |
|------|-------|------|
| staticData koruma | `upload_to_n8n.py` live staticData'yı okuyup koruyor | İyi |
| Workflow publish | Deploy sonrası workflow publish edilmezse canlıda eski sürüm çalışır | **Orta** |
| Rollback mekanizması | Yok — eski workflow.json git history'den geri alınabilir | Orta |
| Schema doğrulama | `wf_validate.py` ile yapılıyor | İyi |
| JS syntax check | `node --check` ile build'te doğrulanıyor | İyi |

### Deploy Akışı (Mevcut)
```bash
python build_workflow.py              # 1. Build
python tools/wf_validate.py workflow.json  # 2. Static doğrulama
python tools/test_workflow_contract.py     # 3. Contract testleri
python upload_to_n8n.py               # 4. Canlı deploy + publish
```

**Eksik:** CI/CD pipeline yok — manuel deploy riski var (P2: CI/CD pipeline).

---

## 8. VERİ AKIŞI VE DAYANIKLILIK

### 8.1 Batch Lifecycle

```
[Mesaj Gelen] → Batch Collector (pendingMessages'e ekle)
    ↓
[120sn Doldu] → Stale Batch Check (claimBatch: processing=true, token ata)
    ↓
[AI İşleme] → Store Context → AI Agent → Parse AI Output
    ↓
[Paralel Gönderim] → Phone A + Phone B + Customer
    ↓
[Tag Success/Err] → completedChannel / failedChannel ekle
    ↓
[Finalize Batch] → deliveryLedger kontrol → tamamlandıysa batch sil
```

### 8.2 Delivery Ledger (Teslimat Defteri)

`Parse AI Output` node'unda (satır 896-902):
```javascript
const expectedChannels = { phoneA: true, phoneB: true };
if (shouldReplyCustomer) expectedChannels['customer'] = true;
staticData._deliveryLedger[batchToken] = {
  createdAt: Date.now(),
  expected: expectedChannels,
  completed: {}
};
```

Her gönderim kanalı (Phone A, Phone B, Customer) `Tag Success` node'larında `completedChannel` ile işaretlenir. `Finalize Batch` tüm kanallar `completed` olunca batch'i kapatır.

### 8.3 Dead Letter Sistemi

Başarısız gönderimler `Tag Err` node'larından `Dead Letter Admin` node'una gider:
- Hedef: `905052237182` (hardcoded - environment variable'a çevrildi)
- Hata detayı: Execution ID, failed channel, batch token, hata mesajı içerir
- `Finalize Batch` yine çağrılır (idempotent guard ile)

### 8.4 Idempotency Koruması

- `_finalizedTokens`: 10 dakika TTL ile çift finalizasyon engellenir
- `_seenMessageIds`: 6 saat TTL + 3000 limit ile deduplikasyon
- `batchToken`: Her batch benzersiz, `validClaim` ile doğrulanır

---

## 9. AI VE POLİTİKA MOTORU

### 9.1 Prompt Mimarisi (Store Context → AI Agent)

**Store Context** (satır 243-316): Regex tabanlı filtre kodu, VIN, araç ipucu tespiti. `codePatterns` dizisi (9 pattern) ile MANN, FILTRON, UFI, HENGST, PURFLUX, MAHLE, FILTORQ kodlarını yakalar.

**AI Agent System Message** (satır 320-373): 
- Sıfır halüsinasyon kuralları (fiyat/stok uydurma yasak)
- Vision kuralları (görselden kod uydurma yasak)
- İş bilgi kuralları (DOC-001 lokasyon, DOC-002 orijinal marka garantisi)
- CaseType sınıflandırması (8 tip)

### 9.2 Politika Motoru (Parse AI Output) — Karar Matrisi

| Senaryo | İnsan Gerekli | Admin Bildirim | Otomasyon Durdur | Araç Bilgisi İste |
|---------|:---:|:---:|:---:|:---:|
| Şema ihlali | Evet | Evet | Evet | — |
| Kaynak ihlali (PRV-001) | Evet | Evet | Evet | — |
| Güven < 0.55 | Evet | Evet | Evet | — |
| Guardrail tetiklendi | Evet | Evet | Hayır | — |
| Tam kod + fiyat/stok | Evet | Evet | Hayır | Hayır |
| Tam kod + uyumluluk (araç yeterli) | Evet | Evet | Hayır | Hayır |
| Tam kod + uyumluluk (araç eksik) | Hayır | Hayır | Hayır | **Evet** |
| Muadil/çapraz referans | Evet | Evet | Hayır | Hayır |
| Kısmi kod | Hayır | Hayır | Hayır | — |
| Araç bazlı (araç yeterli) | Evet | Evet | Hayır | Hayır |
| Araç bazlı (araç eksik) | Hayır | Hayır | Hayır | **Evet** |
| Ürün dışı | Evet | Evet | Evet | — |
| Belirsiz (2x+) | Evet | Evet | Evet | — |
| Selamlama | Hayır | Hayır | Hayır | — |

### 9.3 Guardrail Katmanları (Parse AI Output)

1. **GRD-001** — Güvenli olmayan içerik (URL, şifre, kredi kartı, OTP)
2. **GRD-002** — Doğrulanmamış rakamsal fiyat/TL halüsinasyonu (PRICE_PATTERN)
3. **GRD-003** — Yasaklı stok/uyumluluk garantisi (COMPAT_GUARANTEE, STOCK_GUARANTEE, BANNED_PHRASES - 22 kalıp)
4. **PRV-001** — Provenance check: AI çıktısındaki parça kodlarının müşteri mesajında veya regex tespitinde olup olmadığı kontrolü
5. **SCH-001** — CaseType allowlist (8 geçerli tip, diğerleri `unclear`'e düşürülür)
6. **POL-003** — Araç bilgi tamlığı kontrolü (`isVehicleComplete` fonksiyonu)

### 9.4 Son Düzeltmeler (Son 3 Plan)

| Düzeltme | Durum | Konum |
|----------|-------|-------|
| `runOnceForAllItems` moduna geçiş | ✅ Uygulandı | Tüm Code node'lar |
| Finalize Batch fallback koruması | ✅ Uygulandı | `clear_batch_js` satır 929-934, 957-959 |
| İsim gizlilik kuralı (Müşteri ismi replyDraft'tan silinir) | ✅ Uygulandı | `parse_ai_output_js` satır 883-892 |
| Hala throw eden satır (satır 932) | ⚠️ Kaldırılmalı | `clear_batch_js` satır 932: `throw new Error('Finalize Batch girdisi okunamadı')` |

---

## 10. PERFORMANS VE ÖLÇEKLENEBİLİRLİK

| Metrik | Değer | Not |
|--------|-------|-----|
| Toplama penceresi | 120 sn (sabit) | Pratikte 120-135 sn (15sn polling) |
| Polling aralığı | 15 sn | Schedule Trigger |
| AI timeout recovery | 2 dk | Stale Batch Check içinde |
| Max batch mesajı | 30 | Batch Collector |
| SeenMessageIds limiti | 3000 (LRU 2500'e indirir) | |
| Admin bildirim soğutma | 3 dk | Aynı müşteri için |
| Idle alert eşiği | 10 dk | Sessiz müşteri |

### Ölçeklenebilirlik Sınırları
- **staticData bellek içinde** — n8n restart'inde veri kaybı
- **Veritabanı yok** — Crash dayanıklılığı yok (W6)
- **Redis/PostgreSQL entegrasyonu yok** — O9, O10 fırsatları

---

## 11. GÜNCELLENMİŞ SWOT ANALİZİ

### Güçlü Yönler (Strengths) — 12 (+1 Yeni)

| # | Güçlü Yön | Açıklama |
|---|-----------|----------|
| S1 | **Tek kaynak mimarisi** | `build_workflow.py` tek dosyada tüm mantık. Değişiklik takibi kolay, tutarlılık yüksek. |
| S2 | **120 saniyelik toplama penceresi** | Müşteri mesajları tek tek değil, konuşma bütünlüğü içinde değerlendiriliyor. |
| S3 | **Çok kanallı bildirim** | Telefon A + Telefon B + müşteri — üç ayrı kanal. Tek kanal başarısız olsa bile bilgi ulaşır. |
| S4 | **Politika motoru** | AI çıktısı doğrudan müşteriye gitmiyor. Fiyat/stok/uyumluluk halüsinasyonlarına karşı ikinci kontrol katmanı var. |
| S5 | **Teslimat defteri** | 3 kanalın teslimat durumu takip ediliyor. Batch ancak tüm kanallar tamamlandığında kapatılıyor. |
| S6 | **Dead-letter sistemi** | Başarısız gönderimler sessiz kalmıyor — hata bildirimi üretiliyor. |
| S7 | **Tekrarlanan mesaj koruması** | `_seenMessageIds` ile deduplikasyon. 6 saat TTL ve 3000 kayıt üst limiti. |
| S8 | **Batch token izolasyonu** | Gecikmiş veya eski AI cevapları yanlış müşteriye gitmesin diye token doğrulaması. |
| S9 | **Manuel/otonom mod** | `++`/`--` komutlarıyla sohbet içinden kontrol. AI hatalı davrandığında insan müdahalesine hızlı geçiş. |
| S10 | **İşlem zaman aşımı kurtarma** | 2 dakika süren AI işlemleri otomatik olarak yeniden kuyruğa alınıyor. |
| S11 | **Test araçları ekosistemi** | 12 farklı test/aracı dosyası. Validate, build, diff, inspect, demo, test template'leri mevcut. |
| S12 | **Build-time JS doğrulama** | Her JS bloğu `node --check` ile syntax doğrulamasından geçiyor. |
| **S13 (YENİ)** | **İsim gizlilik koruması** | Müşteri ismi AI cevabından otomatik temizleniyor (GDPR/KVKK uyumu) |

### Zayıf Yönler (Weaknesses) — 12 (+1 Yeni)

| # | Zayıf Yön | Açıklama |
|---|-----------|----------|
| W1 | **Hardcoded API anahtarları** | Evolution API key 6 kez, n8n JWT token 1 kez kaynak kodda. Güvenlik açığı. |
| W2 | **Test kapsamı çok düşük** | Politika motoru, guardrail'ler, teslimat defteri, race condition'lar test edilmemiş. |
| W3 | **Sessiz hata yutma** | 7 `catch(e) {}` bloğu. Hatalar loglanmadan yutuluyor, debug imkansız. |
| W4 | **Bellek sızıntısı (_manualModes)** | Entry'ler asla silinmiyor. Uzun süreli kullanımda büyüme riski. |
| W5 | **Ölü/kopya kod** | ~~3 JS bloğu iki kez tanımlanmış~~ — **TEMİZLENDİ** (ancak test yaparak doğrulanmalı). |
| W6 | **Veritabanı yok** | Tüm durum verileri n8n staticData içinde. Crash durumunda veri kaybı riski. |
| W7 | **Vision modeli yok** | Fotoğraflar analiz edilmiyor. AI'dan fotoğraf yorumlamaması isteniyor ama bu bir sınır. |
| W8 | **Gerçek fiyat/stok entegrasyonu yok** | AI kesin fiyat/stok bilgisi veremiyor — her seferinde "yetkilimiz kontrol edecek" deniyor. |
| W9 | **Workflow publish adımı unutulabilir** | Deploy sonrası publish edilmezse canlıda eski sürüm kalır. |
| W10 | **Mock testler production'dan farklı** | `wf_test.py`'deki mock field isimleri (`messages`) production'dakinden (`pendingMessages`) farklı. |
| W11 | **Webhook authentication yok** | Herhangi bir kaynaktan sahte webhook gönderilebilir. |
| W12 | **120sn pencere pratikte 120-135sn** | 15sn tarama aralığı nedeniyle gerçek gecikme değişken. |
| **W13 (YENİ)** | **Finalize Batch hala throw ediyor** | `clear_batch_js` satır 932: `throw new Error('Finalize Batch girdisi okunamadı')` — runOnceForAllItems modunda daha nadir ama hâlâ risk. |

### Fırsatlar (Opportunities) — 10

| # | Fırsat | Etki |
|---|--------|------|
| O1 | **Stok/fiyat API entegrasyonu** | Doğrudan tedarikçi veya kendi stok sistemi ile entegrasyon. AI'nın "yetkilimiz kontrol edecek" demesi ortadan kalkar. |
| O2 | **Vision API entegrasyonu** | GPT-4o'nun vision özelliği ile fotoğraf analizi. Müşteri fotoğraf gönderdiğinde ürün kodu otomatik çıkartılabilir. |
| O3 | **Gelişmiş test kapsamı** | Politika motoru, guardrail ve teslimat testleri eklenerek regresyon testi güvenilirliği artar. |
| O4 | **Grafik tabanlı dashboard** | n8n execution geçmişinden real-time istatistik: yanıt süreleri, başarı oranları, manuel mod sıklığı. |
| O5 | **Çoklu dil desteği** | AI prompt'una İngilikce/Almanca/Arapça desteği eklenebilir. |
| O6 | **Müşteri memnuniyet anketi** | Otomatik cevap sonrası kısa anket: "Yardımcı olabildik mi?" — sürekli iyileştirme. |
| O7 | **A/B test altyapısı** | Farklı AI model.prompt kombinasyonlarını test etme. |
| O8 | **CI/CD pipeline** | Git push → otomatik test → deploy → publish. Manuel deploy riskini ortadan kaldırır. |
| O9 | **Persistent veritabanı** | PostgreSQL/MongoDB ile staticData'yı desteklemek. Crash dayanıklılık ve sorgulama imkanı. |
| O10 | **Redis-based kuyruk** | 120 saniyelik pencereyi Redis ile yönetmek. n8n bağımsız ölçekleme. |

### Tehditler (Threats) — 10

| # | Tehdit | Olasılık | Etki |
|---|--------|:--------:|------|
| T1 | **API anahtarı sızıntısı** | Yüksek | Kritik — WhatsApp spam, hesap askıya alma |
| T2 | **Evolution API kesintisi** | Orta | Yüksek — tüm müşteri iletişimi durur |
| T3 | **n8n staticData kaybı** | Düşük | Yüksek — bekleyen batch'ler, manuel modlar silinir |
| T4 | **AI model maliyet artışı** | Yüksek | Orta — GPT-4o-mini fiyat değişikliği |
| T5 | **WhatsApp politika değişikliği** | Düşük | Yüksek — numara engelleme, API kısıtlaması |
| T6 | **ReDoS saldırısı** | Düşük | Orta — regex pattern'leri manipüle edilebilir |
| T7 | **Race condition istismarı** | Düşük | Orta — aynı anda çok fazla mesaj gelmesi |
| T8 | **KVKK uyumsuzluğu** | Orta | Yüksek — müşteri telefon numaraları ve mesajları işleniyor |
| T9 | **Deploy hatası** | Orta | Yüksek — publish edilmemiş workflow, eski kod canlıda kalır |
| T10 | **GPT-4o-mini kalite düşüşü** | Orta | Orta — AI cevap kalitesi etkilenir |

---

## 12. ÖNCELİKLİ AKSİYON PLANI

### P0 — Acil (Bu Hafta)

| # | Eylem | Dosya/Alan | Kabul Kriteri |
|---|-------|------------|---------------|
| 1 | API anahtarlarını n8n credential vault'una taşı | `build_workflow.py` (6 yer), `upload_to_n8n.py` | Hardcoded key yok, credential reference kullanılıyor |
| 2 | `upload_to_n8n.py` JWT token'ını `.env`'e taşı | `upload_to_n8n.py:6` | Token env var'dan okunuyor |
| 3 | Catch bloklarına logging ekle | `build_workflow.py` (7 yer) | Her catch'te `console.error` logu var |
| 4 | SSL doğrulamasını etkinleştir | `tools/wf_test_webhook.py:10`, `tools/wf_deploy.py:39`, `tools/live_customer_scenario_test.py:50` | `ssl._create_unverified_context()` yok |
| 5 | Finalize Batch throw satırını kaldır/guvenli hale getir | `build_workflow.py:932` | `throw new Error` yok, graceful return var |

### P1 — Kısa Vadeli (2 Hafta)

| # | Eylem | Kabul Kriteri |
|---|-------|---------------|
| 6 | Politika motoru için unit test yaz (her caseType, her guardrail, provenance) | 8 caseType × 3 guardrail × 2 provenance = min 24 test |
| 7 | Teslimat defteri testleri yaz (3 kanal farklı sıralamalarla, idempotancy) | 6 permütasyon + 3 hata senaryosu |
| 8 | `_manualModes` temizleme ekle (batch silinince entry de sil) | `clear_batch_js` içinde `_manualModes[senderNumber]` delete |
| 9 | Webhook authentication ekle (Evolution API webhook secret) | Webhook doğrulama middleware |
| 10 | Admin telefon numaralarını env/credential'a taşı | Hardcoded telefon yok |

### P2 — Orta Vadeli (1 Ay)

| # | Eylem | Kabul Kriteri |
|---|-------|---------------|
| 11 | Stok/fiyat API entegrasyonu (en azından fiyat sorgulama) | AI artık "yetkili kontrol edecek" demiyor |
| 12 | CI/CD pipeline (Git push → test → build → deploy → publish) | GitHub Actions / GitLab CI |
| 13 | Persistent veritabanı (PostgreSQL ile staticData destekleme) | n8n restart'inde veri kaybı yok |
| 14 | Test coverage artırımı (`wf_test.py` production ile uyumlu hale getir, assertion ekle) | Tüm testler pass, mock field isimleri düzeltildi |

### P3 — Uzun Vadeli (3 Ay)

| # | Eylem |
|---|-------|
| 15 | Vision API entegrasyonu (fotoğraf analizi) |
| 16 | Çoklu dil desteği |
| 17 | Monitoring dashboard (n8n execution geçmişinden real-time metrikler) |

---

## 13. DOĞRULAMA VE SMOKE TEST SENARYOLARI

### Deploy Sonrası Çalıştırılacak Kontroller

#### 13.1 Static Doğrulama (Otomatik)
```bash
python build_workflow.py                    # Build başarılı
python tools/wf_validate.py workflow.json   # 0 hata, 0 uyarı
python tools/test_workflow_contract.py      # Tüm contract testleri PASS
python tools/wf_build.py                    # Build istatistikleri tutarlı
```

#### 13.2 Simülasyon Testleri (Otomatik)
```bash
python tools/wf_test.py                     # 5/5 senaryo PASS
```

#### 13.3 Canlı Smoke Test (Manuel — Kontrollü)
```bash
# Güvenlik anahtarı gerekli
python tools/live_customer_scenario_test.py --confirm-live
```
**Beklenen Sonuç:**
- HTTP 200 yanıtı
- Telefon A + Telefon B'ye bildirim gider
- Müşteriye AI cevabı gider (veya handoff mesajı)
- n8n execution loglarında hata yok

#### 13.4 Manuel Doğrulama Senaryoları

| Senaryo | Adımlar | Beklenen |
|---------|---------|----------|
| Normal müşteri (filtre kodu) | "MANN W 712/95 fiyatı nedir?" gönder | Admin bildirimi + müşteriye "yetkili kontrol edecek" cevabı |
| Müşteri uyumluluk sorusu | "MANN W 712/95 Clio'mda uyar mı?" + şasi no | Araç bilgisi isteği cevabı |
| ++ komutu | Sahip numarasıdan "++" gönder | Manuel mod aktif, admin bildirimi "Sistem Manuel De" |
| -- komutu | Sahip numarasıdan "--" gönder | Manuel mod kapalı, admin bildirimi "Sistem Otomatik" |
| Belirsiz mesaj (2x) | "asdasd" → 2 dk sonra "sdfgh" | Handoff, admin bildirimi "Talep 2 kez anlaşılamadı" |
| Fotoğraf gönderimi | Medya mesajı (imageMessage) | "Görsel ulaştı. Ürün üzerindeki marka ve parça kodunu yazılı olarak paylaşabilir misiniz?" |
| Spam koruması | 31 mesaj ardışık gönder | `_action: "spam_limit"` |

---

## 14. DOSYA REFERANS VE SATIR EŞLEŞMELERİ

### Kritik Dosyalar

| Dosya | Satır Aralığı | Açıklama |
|-------|--------------|----------|
| `build_workflow.py` | 1-1554 | Tek kaynak, tüm node/JS tanımları |
| `workflow.json` | 1-1136 | Üretim artifact'ı (29 node) |
| `upload_to_n8n.py` | 1-73 | Deploy scripti (staticData koruma, publish) |
| `tools/wf_validate.py` | 1-110 | Static doğrulama |
| `tools/test_workflow_contract.py` | 1-117 | Graph/contract testleri |
| `tools/wf_test.py` | 1-129 | Simülasyon testleri |
| `tools/live_customer_scenario_test.py` | 1-68 | Canlı smoke test |

### Kritik JS Blokları (build_workflow.py içinde)

| Blok | Satır Aralığı | Node |
|------|--------------|------|
| `batch_collector_js` | 39-161 | Batch Collector |
| `stale_batch_check_js` | 163-240 | Stale Batch Check |
| `store_context_js` | 243-316 | Store Context |
| `ai_agent_system_message` | 320-373 | AI Agent (prompt) |
| `parse_ai_output_js` | 375-1099 | Parse AI Output (politika motoru) |
| `clear_batch_js` | 927-1031 | Finalize Batch |
| `idle_timeout_check_js` | 1033-1053 | Idle Timeout Check |
| `tag_*_js` | 1058-1063 | 6 Tag node'u |

### Güvenlik ile İlgili Satırlar

| Konum | Satır | Sorun |
|-------|------|-------|
| `build_workflow.py` | 1121, 1203, 1243, 1283, 1323 | Hardcoded Evolution API key |
| `build_workflow.py` | 1121 | `os.environ.get('EVOLUTION_API_KEY', '[REDACTED]...')` fallback hardcoded |
| `upload_to_n8n.py` | 6 | `os.environ.get('N8N_API_KEY')` — env zorunlu ama token hala repoda olabilir |
| `tools/wf_test_webhook.py` | 10 | `ssl._create_unverified_context()` |
| `tools/wf_deploy.py` | 39 | `ssl._create_unverified_context()` |
| `tools/live_customer_scenario_test.py` | 50 | `ssl._create_unverified_context()` |

---

## 15. RAPOR SONU

**Kaynaklar:**
- `build_workflow.py` (tek kaynak)
- `workflow.json` (üretim artifact'ı)
- `upload_to_n8n.py` (deploy)
- `DENETIM_RAPORU.md` (13 Temmuz 2026)
- `deployment_report.md` (son deploy)
- `tools/` dizinindeki 12 test/aracı dosyası
- `.mimocode/plans/` dizinindeki son 3 plan (Finalize Batch fix, runOnceForAllItems, fallback, isim gizlilik)

**Not:** Bu raporda belirtilen tüm satır numaraları `build_workflow.py` v12.5 Enterprise sürümüne aittir. Kod güncellendiğinde satır numaraları değişebilir — `grep` ile doğrulama önerilir.

**Sonraki Adım:** P0 öğelerinin (1-5) bu hafta içinde kapatılması ve CI/CD pipeline (P2-12) başlatılması önerilir.