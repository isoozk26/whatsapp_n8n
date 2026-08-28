# 🔬 Canlı Müşteri Sohbetleri Uçtan Uca (E2E) Analiz Raporu & Codex 5.4 Düzeltme Kartları

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 28 Ağustos 2026  
**Kapsam:** Gerçek Müşteri Sohbetleri Analizi (`Murat`, `+90 531 555 07 11`, `+90 543 737 62 47`, `+90 546 667 05 22`, vb.) ve Codex 5.4 için 14 Düzeltme Görev Kartı (`docs/runbook.md`).

---

## 1. YÖNETİCİ ÖZETİ VE YENİ SOHBET ANALİZLERİ

### 📱 Sohbet: `Murat` (27.07.2026 - Mercedes E 200 / Şasi Kaybı Faciası)
- **Olay:** Müşteri 16:07'de `WDB2100351A528399` şasi numarasını verdi. Bot araç bilgilerini aldı. Ancak 16:10'da bot talebi çözemediğini söyledi. Müşteri polen filtresi istediğini belirtti. Bot 16:13'te **şasiyi unutup tekrar şasi istedi**. Müşteri 16:14'te şasiyi **ikinci kez** yazdı. Bot 16:16'da **üçüncü kez şasi istedi**! Müşteri *"Tşk ederim iyi çalışmalar"* diyerek sistemi terk etti.
- **Kök Neden:** Chat memory'de VIN olmasına rağmen `askVehicleInfo` bayrağının tekrar tetiklenmesi ve hafızanın ezilmesi.

### 📱 Sohbet: `+90 531 555 07 11` (15.08.2026 - Cumartesi Gece)
- **Olay:** Müşteri Cumartesi 20:38'de `MANN-FILTER HU 712/10 X` istedi. Pazartesi 09:01'e kadar yanıt gitmedi.

### 📱 Sohbet: `+90 543 737 62 47` (02.08.2026 - Pazar Gece / Başarılı OOH Örneği)
- **Olay:** Müşteri Pazar 23:17'de `Clio 4 1.2 TCe` için yağ filtresi sordu. Bot 23:19'da Pazar OOH şablonunu başarıyla gönderdi. Pazartesi sabah 10:16'da temsilci onay verdi.

---

## 2. CODEX 5.4 İÇİN 14 ADET KOD DÜZELTME GÖREV KARTI (K-01 - K-14)

- **K-01:** Marka kataloğuna `Suzuki`, `Mini`, `Subaru`, `BMW`, `Volvo`, `Mitsubishi`, `Jeep`, `Porsche` ekleme.
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
- **K-13:** **Zaten Şasi Verilmişse Asla Tekrar Şasi İstememe Guard'ı (Murat Sohbeti Çözümü).**
- **K-14:** **Müşteri Terk / Vazgeçiş Algılama ("Tşk ederim iyi çalışmalar" yanıtı).**

---

> *İşbu rapor ve [docs/runbook.md](file:///C:/ILAN/WHATSAPP_N8N/docs/runbook.md) rehberi Codex 5.4 modelinin kod tabanındaki tüm anomalileri tek adımda çözebilmesi için hazırlanmıştır.*