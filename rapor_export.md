# 🔬 Canlı Müşteri Sohbetleri Uçtan Uca (E2E) Analiz Raporu & Codex 5.4 Düzeltme Kartları

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 28 Ağustos 2026  
**Kapsam:** 4 Gerçek Müşteri Sohbeti Analizi (`+90 555 532 83 40`, `+90 506 061 08 25`, `@resatcemalugur`, `+90 546 667 05 22`) ve Codex 5.4 için 12 Düzeltme Görev Kartı (`docs/runbook.md`).

---

## 1. YÖNETİCİ ÖZETİ

İletilen 4. gerçek müşteri sohbetinde (`+90 546 667 05 22` - Subaru / W 6019) sistemin yaşadığı kritik mantık kazaları:
1. **URL Slug / Query String Sızıntısı:** Müşteri ürün web sitesi linki paylaştığında botun linkteki `srsltid=...` parametresini araç modeli sanıp *"Toyota -gt86 srsltid AfmBOoqcZ5Gk2UQF2fga9jql8xS6-fcDqBTfwRB3jdtBxh1hvxgSi"* şeklinde araç üretmesi.
2. **Olumsuz İfade Algılayamama:** Müşteri *"Toyota gt86 değil"* dediğinde botun aracı *"Toyota gt86 değil 2."* olarak modellemesi.
3. **Geçmiş Şasi Numarasını (VIN) Unutma:** Müşteri 17 haneli geçerli şasiyi (`JF1SH5LW49G010132`) verdiği halde sonraki mesajda fiyat sorunca sistemin hafızayı unutup tekrar şasi istemesi.
4. **Müşterinin İsyanı:** Müşterinin *"İnsan yok mu orada, yapay zekaya dert anlatamıyorum"* diyerek temsilci istemesi.

---

## 2. 4 MÜŞTERİ SOHBETİNİN KARŞILAŞTIRMALI ANOMALİ TABLOSU

| Müşteri / Numara | Müşteri Talebi | Botun Hatalı Davranışı | Koddaki Kök Neden | Codex 5.4 Çözüm Kartı |
|---|---|---|---|---|
| **+90 555 532 83 40** | `Suzuki Swift 1.2 2012` + `W 67/2` | Marka+model+yıl+motor verildiği halde tekrar VIN istedi; VIN verilince ilgisiz kutu fotosu istedi. | `brands` içinde `Suzuki` yok; VIN sonrası alakasız şablon. | **K-01**, **K-12** |
| **+90 506 061 08 25** | `Mini Cooper R50` + `WMWRC3...` | *"Sadece filtre"* cevabına rağmen 3 kez üst üste *"Sadece bu filtreyi mi istersiniz..."* sordu. | Papağan döngüsü; tekrarlayan yanıt guard'ı yok. | **K-02** |
| **@resatcemalugur** | `MANN CUK 2430` + `VF1JMO...` | Kargo süresini söyledi ama parçanın uyumluluğunu söylemeden kesti. | Kargo kuralının uyumluluk cevabını ezmesi. | **K-12** |
| **+90 546 667 05 22** | `Subaru` + `W 6019` + `JF1SH5...` | URL'deki `srsltid` parametresini araç modeli yaptı; *"Toyota değil"* lafını araç yaptı; verilen VIN'i unuttu. | URL temizliği yok; negation yok; `Subaru` eksik; chat memory VIN kaybı. | **K-01, K-09, K-10, K-11, K-12** |

---

## 3. CODEX 5.4 İÇİN 12 ADET KOD DÜZELTME GÖREV KARTI ÖZETİ

Tüm bu hataları Codex 5.4'ün sırayla düzeltebilmesi için **[docs/runbook.md](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md)** içerisinde 12 Görev Kartı (K-01 - K-12) oluşturulmuştur:

- **K-01:** Marka kataloğuna `Suzuki`, `Mini`, `Subaru`, `BMW`, `Volvo`, `Mitsubishi`, `Jeep` ekleme.
- **K-02:** Papağan döngüsünü engelleme (`reply === lastReplyText` ise handoff).
- **K-03:** `"Mesai mesai saatleri..."` typo düzeltmesi.
- **K-04:** Ingress event filtresi (`messages.upsert` zorunluluğu).
- **K-05:** OOH HTTP 400 hatasında false `customer_sent=true` düzeltmesi.
- **K-06:** OOH adreste `@lid` temizliği.
- **K-07:** Legacy test suite `tools/test_policy_engine.test.js` düzeltmesi.
- **K-08:** `postgresql_backup/` klasörünün `.gitignore`'a eklenmesi.
- **K-09:** URL ve Web Linki Temizliği (URL slug ve query string sızıntısını engelleme).
- **K-10:** Olumsuz İfade Modellemesi (`"Toyota gt86 değil"` filtresi).
- **K-11:** Chat Memory ve geçmiş mesajlardaki VIN'in korunması.
- **K-12:** Tam ürün kodunda fuzuli VIN istemeden fiyat/stok sorgusu.

---

> *İşbu rapor ve [docs/runbook.md](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md) rehberi Codex 5.4 modelinin kod tabanındaki tüm anomalileri tek adımda çözebilmesi için hazırlanmıştır.*