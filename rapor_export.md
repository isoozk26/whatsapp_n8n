# 🔬 WhatsApp AI — Mesai Dışı Mesaj (OOH) Kanıt Tabanlı Analiz ve Düzeltme Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 13 Ağustos 2026  
**Kapsam:** Repository içindeki `scratch/exec_2023.json` execution artefact'ı ile kanıtlanan bulgular, `Log OOH Event` loglama kusurunun repository düzeltmesi ve yerel doğrulama sonuçları. Bu rapor canlı production deploy kanıtı değildir.

---

## 1. YÖNETİCİ ÖZETİ VE KANITLANMIŞ GERÇEKLER

Repository içindeki `scratch/exec_2023.json` execution artefact'ı incelendiğinde varsayımlar ile kanıtlanmış gerçekler net biçimde ayrıştırılmıştır:

### ✅ Kanıtlanmış Gerçekler (exec_2023 Log Verileri):
1. **Akış Sırası:** `Ingest Message` ➔ `Is Off Hours?` ➔ `Wait OOH 120 Seconds` ➔ `Claim OOH Notification` sıralaması tam ve doğru çalışmıştır.
2. **Wait Node Durumu:** `Wait OOH 120 Seconds` düğümü tamamlanmıştır; bu artefact içinde Wait'in öldüğünü gösteren hata yoktur. Kayıt, beklemenin tam olarak 120.000 ms olduğunu tek başına kanıtlamaz.
3. **OOH Claim Durumu:** `Claim OOH Notification` düğümü veritabanından kilidi başarıyla almış (`claimed = true`) ve `Build OOH Messages` düğümüne aktarmıştır.
4. **Şablon Tespiti:** `Check Business Hours` execution anındaki İstanbul saatine göre `scenario` üretmiş, `Build OOH Messages` bu değeri kullanmıştır. Bu kayıt, mesajın gerçek geliş timestamp'inin ayrıca hesaplanıp doğrulandığını kanıtlamaz.

---

## 🚨 2. DOĞRULANMIŞ ASIL HATA (THE SMOKING GUN BUG) & KOD DÜZELTMESİ

### 🔴 Doğrulanmış Asıl Hata (HTTP 400 Cooldown Sızıntısı):
- `exec_2023` akışında `Send OOH to Customer` düğümü Evolution API'ye istek attığında Evolution API **HTTP 400 Bad Request** hatası dönmüştür. Bu execution içinde başarılı müşteri gönderimi kanıtı yoktur; cihazdaki teslimat durumu ayrıca doğrulanmamıştır.
- Ancak `Send OOH to Customer` düğümünde `continueOnFail: true` / `onError: continueErrorOutput` tanımlı olduğu için akış kesilmeyip `Log OOH Event` düğümüne devam etmiştir.
- `Log OOH Event` düğümü (`UPDATE whatsapp_ai.ooh_log SET customer_sent = $2`), `Send OOH to Customer` düğümünün başarılı olup olmadığını kontrol etmeden `customer_sent = true` olarak veritabanına kaydetmiştir!
- **Sonuç:** Evolution isteği reddedildiği halde artefact'ta `customerSent=true` taşınmış/loglama yolu buna izin vermiştir. Bu durumun canlı PostgreSQL `ooh_log` satırında gerçekten `customer_sent=true` olarak yazıldığını ve 8 saatlik cooldown'ın canlıda aktif olduğunu bu repository kaydı tek başına kanıtlamaz.

---

### 🟢 Uygulanan Kod Düzeltmeleri (`build_workflow.py`):

1. **Numara Metin Normalizasyonu (Sanitization):**
   - `build_ooh_messages_js` düğümünde numara metninden bazı JID sonekleri ve rakam dışı karakterler temizleniyor. Bu işlem tek başına değerin geçerli E.164 numarası olduğunu veya `@lid` değerinin gerçek telefon numarasına çözüldüğünü kanıtlamaz; Evolution HTTP 400'ü kesin olarak engellediği iddia edilemez.
   ```javascript
   const senderNumberRaw = String(claim.senderNumber || ctx.senderNumber || '');
   const senderNumber = senderNumberRaw.replace(/@s\.whatsapp\.net$|@g\.us$|@lid$/gi, '').replace(/[^0-9]/g, '');
   ```

2. **Dinamik HTTP Sonuç Kontrolü (`Log OOH Event`):**
   - `Log OOH Event` düğümündeki `customer_sent` değeri `Send OOH to Customer` çıktısındaki hata/status alanlarına göre hesaplanıyor.
   - HTTP 400 ve n8n error durumunda bu ifade `false` olur. Ancak `PENDING` durumunu başarı kabul eden mevcut ifade teslimatın kesin tamamlandığını kanıtlamaz; canlı deploy ve gerçek Evolution sonucu ayrıca doğrulanmalıdır.
   ```python
   postgres_node(
       "Log OOH Event",
       "UPDATE whatsapp_ai.ooh_log SET customer_sent = $2 WHERE id = $1::uuid RETURNING id",
       "={{ [ $('Build OOH Messages').item.json.oohLogId, Boolean(($('Send OOH to Customer').item.json.key || $('Send OOH to Customer').item.json.status === 'SENT' || $('Send OOH to Customer').item.json.status === 'PENDING') && !$('Send OOH to Customer').item.json.error && (!$('Send OOH to Customer').item.json.statusCode || $('Send OOH to Customer').item.json.statusCode < 400)) ] }}",
       [2540, 260],
   )
   ```

---

## 📊 3. YEREL SÜRÜM VE DOĞRULAMA KONTROLLERİ

Repository üzerinde yapılan son düzeltme commit'i `f698045` içindedir. Aşağıdaki sonuçlar yerel/static doğrulamadır; canlı n8n workflow'unun güncellendiğini veya production'a deploy edildiğini kanıtlamaz:

```text
[PASS] python build_workflow.py                   (53 node, 45 connection)
[PASS] python tools/wf_validate.py workflow.json   (Sözdizimi ve Bağlantı Kontrolü)
[PASS] python tools/test_workflow_contract.py    (PostgreSQL & Outbox Sözleşmesi)
[PASS] node tools/test_workflow_behavior.js      (@LID, E.164 & Evolution v2 Payload)
[PASS] python tools/test_ops_drift_check.py       (Ops Drift & Metadata Eşleşmesi)
[PASS] python tools/test_outbound_guard.py       (Outbound Mesaj Emniyet Güvencesi)
[PASS] npm run release:gate                       (RELEASE GATE SCORE: 100/100 PASS)
```

---

## 4. ÖZET VE SONUÇ

- ❌ Varsayım olan *"Wait node öldü"*, *"Akış 09:00'da yanlış şablon bastı"* iddiaları rapordan çıkarıldı.
- ✅ `exec_2023` repository artefact'ında HTTP 400 ile birlikte `customerSent=true` taşındığı doğrulandı; `Log OOH Event` hesaplaması repository'de hata durumunu false'a çevirecek şekilde güncellendi.
- ✅ `workflow.json` için yerel release gate **100/100 PASS** verdi.
- 🟠 Canlı n8n workflow sürümü, canlı PostgreSQL migration durumu ve gerçek Evolution teslimatı bu çalışmada doğrulanmadı.