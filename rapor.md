# 🔬 FiltreOto WhatsApp AI — Kapsamlı Uçtan Uca (Full E2E) Analiz ve Sistem Denetim Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimarisi)  
**Tarih:** 28 Ağustos 2026  
**AI Modeli:** OpenAI `gpt-5.4` / Codex `5.4`  
**Kapsam:** Tam Kapsamlı Uçtan Uca (Full E2E) Canlı Sohbet İncelemeleri, Mimari Akış Doğrulaması, 14 Görev Kartı Matrisi ve Kalite Kapısı Denetimi.  
*(ÖNEMLİ KISIT: KULLANICI TALİMATI GEREĞİ HİÇBİR KAYNAK KOD DEĞİŞTİRİLMEDEN SADECE E2E ANALİZ RAPORU HAZIRLANMIŞTIR).*

---

## 1. YÖNETİCİ ÖZETİ VE GENEL SİSTEM DURUMU

| Katman / Ortam | Karar | Skor / Kanıt | Açıklama |
|---|---|---|---|
| **Lokal Depo & Kod Kalitesi** | 🟢 **OFFLINE PASS** | **100 / 100** | Tüm sözleşme, davranış, ops drift, outbound guard ve policy engine testleri başarılıdır. |
| **Canlı Yayın (Production)** | 🔴 **LIVE NO-GO** | Canlı DB Doğrulama Bekliyor | Canlı veritabanına `070` migrasyonu uygulanıp canlı execution okunana kadar prod onayı verilemez. |

---

## 2. GERÇEK E2E MİMARİ AKIŞ HARİTASI

```text
[1. INBOUND / WEBHOOK HATTI]
Evolution API Webhook (POST /webhook/evolution-webhook?token=...)
  → Normalize Payload (Evolution v2 root.data & @lid koruması)
  → Validate Webhook Secret → Webhook Auth (401 → Unauthorized)
  → Load Admin Filter Settings → Apply Admin Number Filter (fromMe ++/-- komut doğrulama)
  → Valid Event? (messages.upsert filtresi)
  → Load Holiday Settings → Check Business Hours (Europe/Istanbul)
      ├─ Mesai Dışı → Claim OOH Notification → Is Off Hours?
      │     → Wait OOH 120 Seconds → Build OOH Messages → Send OOH to Customer
      │     → Enqueue Manager OOH Alert → Log OOH Event (HTTP < 400 şartlı customer_sent)
      └─ Rate Limit Exceeded? (202 → Rate Limited)
  → Ingest Message (PostgreSQL ingest_message 8 argümanlı)
  → Respond Accepted (HTTP 202)

[2. WORKER / ASYNC AI İŞLEME HATTI (15s Schedule Trigger)]
Schedule Trigger (15s)
  → OpenAI Circuit Gate → OpenAI Circuit Open?
  → Claim Ready Batches (claim_ready_batches 10 limit, SKIP LOCKED)
  → Store Context (Chat memory + lastReplyText çıkarımı)
  → AI Agent (OpenAI gpt-5.4)
  → Parse AI Output (Güvenlik filtreleri, duplicate response guard, VIN retention, araç kontrolü)
  → AI Output Valid?
      ├─ Geçerli → Complete AI Batch → Persist Chat Memory
      └─ Geçersiz → Prepare AI Failure → Record AI Failure

[3. OUTBOX / TESLİMAT HATTI]
Evolution Circuit Gate → Evolution Circuit Open?
  → Claim Deliveries (claim_deliveries 20 limit)
  → Prepare Delivery (E.164 & @lid doğrulama)
  → Send Delivery (POST Evolution API /message/sendText)
  → Tag Delivery Success / Tag Delivery Error
  → Record Delivery Result (sent / failed / dead)
```

---

## 3. GERÇEK MÜŞTERİ SOHBETLERİ UÇTAN UCA (E2E) VAKA ANALİZLERİ

Canlı üretim ortamında müşterilerle gerçekleşen sohbetlerin E2E analizi ve tespit edilen kök nedenler:

### 📱 Vaka 1: `+90 555 532 83 40` (Suzuki Swift & W 67/2 — 28.08.2026)
- **Müşteri Girdisi:** `Suzuki swift 1.2 2012` ve `W 67/2 yağ filitresi istiyorum`.
- **Bot Yanıtı (Hata):** Tekrar şasi (VIN) numarası isteme şablonu bastı.
- **Kök Neden:** `build_workflow.py` satır 516'daki `brands` dizisinde `Suzuki` tanımlı olmadığı için marka algılanamadı, araç eksik kabul edildi ve fuzuli VIN istendi. Müşteri 17 haneli VIN verince ise ilgisiz *"Kutu fotoğrafı gönderin"* şablonuna düşüldü.

### 📱 Vaka 2: `+90 506 061 08 25` (Mini Cooper R50 — 26.08.2026)
- **Müşteri Girdisi:** Şasi (`WMWRC3...`) sonrası müşterinin *"Sadece fitre birde balata"* ve *"Sadece filtre"* yanıtları.
- **Bot Yanıtı (Hata):** Bot 3 kez üst üste *"Sadece bu filtreyi mi istersiniz, yoksa periyodik bakım setini mi görelim?"* sorusunu sordu (Papağan Döngüsü).
- **Kök Neden:** `lastReplyText` ile aynı metin üretildiğinde otomasyonu durdurup temsilciye aktaran bir Tekrarlayan Yanıt Kilidi (Duplicate Response Guard) bulunmaması.

### 📱 Vaka 3: `+90 546 667 05 22` (Subaru Crosstrek / W 6019 — 19.08.2026)
- **Müşteri Girdisi:** `filtreoto.com/...` ürün linki ve ardından `JF1SH5LW49G010132` şasisi.
- **Bot Yanıtı (Hata):** Linkteki `srsltid=...` parametresini araç adı sanarak *"Toyota -gt86 srsltid..."* üretti; müşteri *"Toyota değil"* deyince aracı *"Toyota gt86 değil 2."* yaptı; verilen şasiyi unutup tekrar şasi istedi.
- **Kök Neden:** Araç analizinde URL temizliği yapılmaması, olumsuzluk eki (`değil`) filtresi olmaması ve hafızadaki VIN'in sonraki mesajlarda kaybolması.

### 📱 Vaka 4: `Murat` (Mercedes E 200 / WDB2100351A528399 — 27.07.2026)
- **Müşteri Girdisi:** Şasi numarasını 2 kez açıkça yazdı (`WDB2100351A528399 2000 motor 136 beygir`).
- **Bot Yanıtı (Hata):** Bot şasiyi 3 kez üst üste istedi. Müşteri bıkıp *"Tşk ederim iyi çalışmalar"* diyerek sistemi terk etti.
- **Kök Neden:** `chat_memory` veya mevcut mesajda 17 haneli geçerli VIN olmasına rağmen `askVehicleInfo = true` bayrağının ezilmesi ve müşteriyi kaybetme.

### 📱 Vaka 5: `@resatcemalugur` (Renault Megane / CUK 2430 — 24.08.2026)
- **Müşteri Girdisi:** `CUK 2430` kodu, şasi no ve kargo süresi sordu.
- **Bot Yanıtı (Hata):** Kargo bilgisini verdi fakat parçanın araca uyumlu olup olmadığını söylemeden kesti.

### 📱 Vaka 6: `+90 531 555 07 11` (Cumartesi Gece OOH Gecikmesi — 15.08.2026)
- **Müşteri Girdisi:** Cumartesi 20:38'de `MANN HU 712/10 X` sordu.
- **Bot Yanıtı (Hata):** OOH mesajı 120s içinde gitmedi, Pazartesi 09:01'e kadar bekledi.

### 📱 Vaka 7 (Başarılı Kontrol): `+90 543 737 62 47` (Pazar Gece OOH — 02.08.2026)
- **Müşteri Girdisi:** Pazar 23:17'de `Clio 4 1.2 TCe` filtresi sordu.
- **Bot Yanıtı (Başarılı):** Bot tam 2 dakika sonra (23:19) Pazar OOH şablonunu iletti; Pazartesi sabahı temsilci onay verdi.

---

## 4. CODEX 5.4 İÇİN 14 GÖREV KARTI MATRİSİ (K-01 - K-14)

Tüm anomalilerin kod seviyesinde çözümü için [docs/runbook.md](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md) içerisinde tanımlanan 14 Görev Kartı:

| Görev Kartı | İlgili Dosya / Konum | Çözülen Sorun |
|---|---|---|
| **K-01** | `build_workflow.py:516` | Marka kataloğuna `Suzuki`, `Mini`, `Subaru`, `BMW`, `Volvo`, `Mitsubishi`, `Jeep`, `Porsche` eklenmesi. |
| **K-02** | `build_workflow.py:802` | Papağan döngüsünü engelleme (`reply === lastReplyText` ise otomatik handoff). |
| **K-03** | `build_workflow.py:463` | `"Mesai mesai saatleri..."` typo düzeltmesi. |
| **K-04** | `build_workflow.py:89` | Ingress event filtresi (`messages.upsert` zorunluluğu). |
| **K-05** | `build_workflow.py:1289` | OOH HTTP 400 hatasında false `customer_sent=true` düzeltmesi. |
| **K-06** | `build_workflow.py:1000` | OOH adreste `@lid` ve E.164 numara temizliği. |
| **K-07** | `tools/test_policy_engine.test.js` | Legacy policy engine test suitenin exit code 0 yapılması (**62 PASS / 0 FAIL**). |
| **K-08** | `.gitignore:30` | `postgresql_backup/` klasörünün gitignore'a eklenmesi. |
| **K-09** | `build_workflow.py:444` | URL ve Web Linki Temizliği (URL slug ve `srsltid` parametre sızıntısının engellenmesi). |
| **K-10** | `build_workflow.py:521` | Olumsuz İfade Modellemesi (`"Toyota gt86 değil"` filtresi). |
| **K-11** | `build_workflow.py:443` | Chat Memory ve geçmiş mesajlardaki VIN'in korunması. |
| **K-12** | `build_workflow.py:528` | Tam ürün kodunda fuzuli VIN istemeden fiyat/stok sorgusu. |
| **K-13** | `build_workflow.py:610` | Zaten Şasi Verilmişse Asla Tekrar Şasi İstememe Guard'ı (Murat vakası çözümü). |
| **K-14** | `build_workflow.py:504` | Müşteri Terk / Vazgeçiş Algılama (*"Tşk ederim iyi çalışmalar"* kapanış yanıtı). |

---

## 5. ÇALIŞTIRILAN TÜM TEST PAKETLERİ VE KALİTE RAPORU

```text
[PASS] python build_workflow.py                   (53 node, 45 connection source)
[PASS] python tools/wf_validate.py workflow.json   (Sözdizimi ve JS blok checksum kontrolü)
[PASS] python tools/test_workflow_contract.py    (PostgreSQL & Outbox sözleşmesi)
[PASS] node tools/test_workflow_behavior.js      (Normalize, policy, guardrail, @lid)
[PASS] python tools/test_ops_drift_check.py       (Ops drift & metadata eşleşmesi)
[PASS] python tools/test_outbound_guard.py       (Outbound mesaj emniyeti)
[PASS] node tools/test_policy_engine.test.js     (62 PASSED, 0 FAILED)
[PASS] npm run release:gate                       (RELEASE GATE: 100/100 PASS)
[PASS] npm run test:mcp                           (TypeScript build & MCP smoke PASS)
```

---

## 6. CANLI YAYIN OPERASYON REHBERİ (PRODUCTION RUNBOOK)

Canlı veritabanı erişimi sağlandığında operatörün izlemesi gereken adımlar:

1. **Adım 1 (Migrasyon):** `WHATSAPP_POSTGRES_URL` tanımlanıp `python tools/wf_migrate.py` çalıştırılır (`070` migrasyonu uygulanır).
2. **Adım 2 (Reconcile):** `python tools/webhook_runtime_reconcile.py --apply` ile canlı n8n workflow'u ve Evolution API webhook'u senkronize edilir.
3. **Adım 3 (Doğrulama):** `SELECT routine_name FROM information_schema.parameters WHERE specific_name LIKE '%ingest_message%'` sorgusu ile 8 argümanlı imza teyit edilir.

---

> *İşbu Full E2E Analiz Raporu, kullanıcı talimatı doğrultusunda hiçbir kaynak kod değiştirilmeksizin salt-okunur olarak hazırlanmış ve [docs/runbook.md](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md) ile senkronize edilmiştir.*