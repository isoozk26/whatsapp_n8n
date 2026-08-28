# 🔬 Canlı Müşteri Sohbet Logları Uçtan Uca (E2E) Analiz ve Teşhis Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 28 Ağustos 2026  
**Kapsam:** 3 Gerçek Müşteri Sohbet Oturumu Uçtan Uca (E2E) Analizi ve Sistem Davranış Teşhisi.  
*(ÖNEMLİ KISIT: KULLANICI TALİMATI GEREĞİ HİÇBİR KOD DEĞİŞTİRİLMEDEN SADECE ANALİZ VE ÖNERİ RAPORU HAZIRLANMIŞTIR).*

---

## 1. YÖNETİCİ ÖZETİ

İletilen 3 farklı gerçek müşteri sohbet oturumu (`+90 555 532 83 40`, `+90 506 061 08 25`, `@resatcemalugur`) uçtan uca incelenmiş ve sistemde tespit edilen **5 temel bot davranış aksaklığı** kod seviyesindeki kök nedenleriyle belirlenmiştir:

1. **"Suzuki" Marka Eksikliği ve Fuzuli Şasi (VIN) İsrarı:** Müşteri marka, model, yıl, motor hacmi ve ürün kodunu (`Suzuki Swift 1.2 2012 W 67/2`) eksiksiz verdiği halde sistemin markayı tanıyamayıp tekrar şasi no istemesi.
2. **Papağan Döngüsü (Looping Bot):** Müşteri *"Sadece filtre"* cevabı verdiği halde sistemin 3 kez üst üste **birebir aynı soruyu** sorması (*"Sadece bu filtreyi mi istersiniz, yoksa periyodik bakım setini mi görelim?"*).
3. **Ruhsat Görseline Şasi İstenmesi:** Müşteri ruhsat fotoğrafı gönderdiği halde OCR/medya işleme eksikliğinden dolayı botun tekrar şasi isteme şablonu basması.
4. **VIN Verildiği Halde İlgisiz Ürün Görseli Fotoğrafı Talebi:** Geçerli 17 haneli şasi verildikten sonra botun alakasız biçimde *"Paylaştığınız kodu birebir doğrulamak için... kutu veya ürün üzerindeki yazının fotoğrafını gönderebilir misiniz?"* mesajı atması.
5. **"Mesai mesai" Kelime Tekrarı (Typo):** `SLA_LINE` değişkenindeki kelime birleşimi hatası nedeniyle *"Mesai mesai saatleri içinde dönüş yapacağız."* metninin basılması.

---

## 2. MÜŞTERİ SOHBET LOGLARI DETAYLI TEŞHİSİ

### 📱 SOHBET 1: `+90 555 532 83 40` (Suzuki Swift & W 67/2 — 28.08.2026)
- **Olay Akışı:**
  - Müşteri: `MANN-FILTER C 26 006` ve `yağ filtresi` istedi.
  - Bot: Şasi no veya marka/model/yıl/motor istedi.
  - Müşteri: `Suzuki swift 1.2 2012` ve `W 67/2 yağ filitresi istiyorum` yazdı.
  - Bot (Hatalı): Tekrar aynı şasi isteme metnini gönderdi!
  - Müşteri: `TSMNZC72S00165509` (17 haneli VIN) gönderdi.
  - Bot (Hatalı): *"Paylaştığınız kodu birebir doğrulamak için... kutu veya ürün üzerindeki yazının fotoğrafını gönderebilir misiniz?"* dedi.
- **Kök Neden (Kod Karşılığı):**
  - [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L514) satır 514'te tanımlı `const brands = ['Fiat','Renault','Ford','Volkswagen','VW','Opel','Peugeot','Citroen','Toyota','Honda','Hyundai','Kia','Mercedes','BMW','Audi','Skoda','Seat','Dacia','Nissan'];` dizisinde **`Suzuki` markası bulunmamaktadır**.
  - `Suzuki` algılanamayınca `missingVehicleFields` içine `'marka'` eklenmiş, araç eksik kabul edilerek **marka+model+yıl+motor verildiği halde tekrar VIN istenmiştir**.
  - VIN verildikten sonra ise bot parçayı sorgulamak yerine ilgisiz kutu fotoğrafı şablonuna düşmüştür.

---

### 📱 SOHBET 2: `+90 506 061 08 25` (Mini Cooper R50 & Balata — 26.08.2026)
- **Olay Akışı:**
  - Müşteri şasisini verdi: `WMWRC31010TB84880`.
  - Bot (16:08): *"🛠️ Araç bilgilerinizi aldım; aracınız için uyumlu filtre setini kontrol ediyorum. Sadece bu filtreyi mi istersiniz, yoksa periyodik bakım setinin tamamını mı görelim?"*
  - Müşteri (16:08): *"Sadece fitre birde balata takımı"*
  - Bot (16:11 - Hatalı): *"🛠️ Araç bilgilerinizi aldım... Sadece bu filtreyi mi istersiniz, yoksa periyodik bakım setinin tamamını mı görelim?"*
  - Müşteri (16:11): *"Sadece filtre"*
  - Bot (16:14 - Hatalı): *"🛠️ Araç bilgilerinizi aldım... Sadece bu filtreyi mi istersiniz, yoksa periyodik bakım setinin tamamını mı görelim?"*
  - Admin (16:58): `++` atıp botu durdurdu ve manuel devraldı.
- **Kök Neden (Kod Karşılığı):**
  - **Papağan Döngüsü (Looping Bot):** Müşterinin kısa yönlendirme cevapları (`Sadece filtre`) durum makinesinde yeni bir girdi kabul edilmemiş ve bot 3 kez üst üste **aynı şablonu** tekrarlamıştır. Sistemde üst üste aynı cevabın verilmesini engelleyen bir kilit mekanizması yoktur.

---

### 📱 SOHBET 3: `@resatcemalugur` (MANN CUK 2430 & Megane VIN — 24.08.2026)
- **Olay Akışı:**
  - Müşteri `MANN-FILTER CUK 2430` ve şasi no (`VF1JMOCOH32503738`) gönderdi. Kargo ücreti sordu.
  - Bot kargo teslimat süresi bilgisini verdi, fakat `CUK 2430` ürününün şasiye uyumlu olup olmadığını yanıtlamadı. Admin `++` ile devraldı.

---

## 3. İYİLEŞTİRME VE ÇÖZÜM ÖNERİLERİ

1. **Marka Kataloğunun Genişletilmesi:**
   - `build_workflow.py` satır 514'teki `brands` dizisine `Suzuki`, `Mini`, `BMW`, `Volvo`, `Mitsubishi`, `Subaru`, `Jeep` markaları eklenmelidir.

2. **Tekrarlayan Yanıt Kilidi (Duplicate Response Guard):**
   - Bot aynı müşteriye **2 kez üst üste birebir aynı şablon metnini gönderememelidir**. İkinci tekrarda sistem otomatik olarak `action = 'handoff'`, `pauseAutomation = true` ile temsilciye devretmelidir.

3. **Ruhsat Görseli Akıllı Algılama:**
   - Müşteri görsel (ruhsat) yüklediğinde bot tekrar metin olarak şasi istemek yerine *"Ruhsat görseliniz alındı, uzmanımız şasi numarasını ruhsattan okuyarak filtre uyumunu kontrol ediyor"* yanıtı vermelidir.

4. **"Mesai mesai" Typo Düzeltmesi:**
   - [build_workflow.py](file:///C:/ILAN/WHATSAPP_N8N/build_workflow.py#L461) satır 461-462'deki `Mesai ${SLA_TEXT}` birleşimi `SLA_TEXT` (`"mesai saatleri içinde dönüş yapacağız."`) olarak düzeltilmelidir.

---

> *Rapor, kullanıcı talimatı doğrultusunda hiçbir kaynak kod değiştirilmeksizin salt-okunur E2E analiz ile hazırlanmıştır.*