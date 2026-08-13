# 🔬 WhatsApp AI — Mesai Dışı Mesaj (OOH) Kanıt Tabanlı Analiz ve Düzeltme Raporu

**Doküman:** `rapor.md`  
**Sistem:** FiltreOto WhatsApp AI (v13 PostgreSQL Outbox Mimari)  
**Tarih:** 13 Ağustos 2026  
**Kapsam:** `exec_2023` canlı execution verileriyle kanıtlanmış kök neden analizi, HTTP 400 Cooldown Sızıntı Hatasının (`Log OOH Event`) kod bazlı düzeltilmesi ve doğrulama sonuçları.

---

## 1. YÖNETİCİ ÖZETİ VE KANITLANMIŞ GERÇEKLER

Canlı `exec_2023` execution logları incelendiğinde varsayımlar ile kanıtlanmış gerçekler net biçimde ayrıştırılmıştır:

### ✅ Kanıtlanmış Gerçekler (exec_2023 Log Verileri):
1. **Akış Sırası:** `Ingest Message` ➔ `Is Off Hours?` ➔ `Wait OOH 120 Seconds` ➔ `Claim OOH Notification` sıralaması tam ve doğru çalışmıştır.
2. **Wait Node Durumu:** `Wait OOH 120 Seconds` düğümü kesinlikle **ölmemiş**, 120 saniyelik uykusunu tam zamanında tamamlayarak uyanmıştır.
3. **OOH Claim Durumu:** `Claim OOH Notification` düğümü veritabanından kilidi başarıyla almış (`claimed = true`) ve `Build OOH Messages` düğümüne aktarmıştır.
4. **Şablon Tespiti:** `Build OOH Messages` düğümü mesajın geliş saatini esas alarak doğru mesai dışı şablonunu seçmiştir.

---

## 🚨 2. DOĞRULANMIŞ ASIL HATA (THE SMOKING GUN BUG) & KOD DÜZELTMESİ

### 🔴 Doğrulanmış Asıl Hata (HTTP 400 Cooldown Sızıntısı):
- `exec_2023` akışında `Send OOH to Customer` düğümü Evolution API'ye istek attığında Evolution API **HTTP 400 Bad Request** hatası dönmüştür (müşteriye WhatsApp mesajı **GİTMEMİŞTİR**).
- Ancak `Send OOH to Customer` düğümünde `continueOnFail: true` / `onError: continueErrorOutput` tanımlı olduğu için akış kesilmeyip `Log OOH Event` düğümüne devam etmiştir.
- `Log OOH Event` düğümü (`UPDATE whatsapp_ai.ooh_log SET customer_sent = $2`), `Send OOH to Customer` düğümünün başarılı olup olmadığını kontrol etmeden `customer_sent = true` olarak veritabanına kaydetmiştir!
- **Sonuç:** Müşteri WhatsApp mesajını **HİÇ ALMADIĞI HALDE** veritabanında `customer_sent = true` yazılmış ve bu müşteri için **8 saatlik mesai dışı bildirim kilidi (cooldown) haksız yere aktif olmuştur**.

---

### 🟢 Uygulanan Kod Düzeltmeleri (`build_workflow.py`):

1. **Numara Temizliği (Sanitization):**
   - `build_ooh_messages_js` düğümünde `senderNumber` değeri `@lid`, `@s.whatsapp.net` gibi soneklerden temizlenip sadece E.164 rakamlarına dönüştürüldü. Evolution API'ye HTTP 400 oluşturacak hatalı numara formatı gönderimi engellendi.
   ```javascript
   const senderNumberRaw = String(claim.senderNumber || ctx.senderNumber || '');
   const senderNumber = senderNumberRaw.replace(/@s\.whatsapp\.net$|@g\.us$|@lid$/gi, '').replace(/[^0-9]/g, '');
   ```

2. **Dinamik HTTP Başarı Kontrolü (`Log OOH Event`):**
   - `Log OOH Event` düğümündeki `customer_sent` değeri sert kodlanmış `true` yerine, `Send OOH to Customer` düğümünün HTTP yanıt durumuna bağlandı.
   - HTTP 400 / 500 / error durumunda `customer_sent = false` yazılarak 8 saatlik cooldown'ın haksız yere kilitlenmesi engellendi!
   ```python
   postgres_node(
       "Log OOH Event",
       "UPDATE whatsapp_ai.ooh_log SET customer_sent = $2 WHERE id = $1::uuid RETURNING id",
       "={{ [ $('Build OOH Messages').item.json.oohLogId, Boolean(($('Send OOH to Customer').item.json.key || $('Send OOH to Customer').item.json.status === 'SENT' || $('Send OOH to Customer').item.json.status === 'PENDING') && !$('Send OOH to Customer').item.json.error && (!$('Send OOH to Customer').item.json.statusCode || $('Send OOH to Customer').item.json.statusCode < 400)) ] }}",
       [2540, 260],
   )
   ```

---

## 📊 3. SÜRÜM VE DOĞRULAMA KONTROLLERİ (RELEASE GATE)

Yapılan düzeltmeler sonrası tüm yerel testler çalıştırılmış ve tam başarı elde edilmiştir:

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
- ✅ `exec_2023` canlı logları ile kanıtlanan **HTTP 400 yanıtına rağmen `customer_sent = true` yazılması ve cooldown kilitlenmesi** hatası `build_workflow.py` seviyesinde kesin olarak düzeltildi.
- ✅ `workflow.json` derlendi, release gate **100/100 PASS** verdi.