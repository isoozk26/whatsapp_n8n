# WhatsApp Yapay Zeka Bildirimi - 3 Dakikalık Toplu Toplama ve Müşteri Yanıtı

Bu plan, n8n WhatsApp iş akışını yeniden yapılandırmak için yapılacak adımları detaylandırmaktadır. 1 saatlik oran limiti engelini kaldırıp yerine 3 dakikalık bir toplu mesaj toplama (batching) mekanizması ekleyeceğiz. Belirli bir müşteriden gelen mesajlar 3 dakika boyunca biriktikten sonra, Yapay Zeka Ajanı (AI Agent) tüm bu mesajları analiz edecek, işletme sahipleri için ortak bir bildirim hazırlayıp (Telefon A ve Telefon B'ye gönderilecek) doğrudan müşteriye de profesyonel bir otomatik cevap gönderecektir.

## Kullanıcı İncelemesi Gereken Konular

> [!IMPORTANT]
> **OpenAI API Anahtarı ve Yetkilendirme:**
> Mevcut düğümleri ve yapılandırmalarını (OpenAI Chat Model ve HTTP Request başlıkları/anahtarları gibi) korumak için orijinal kimliklerini (ID) kullanacağız. Ancak, n8n örneğinizde OpenAI kimlik bilgisi (credential) tanımlı değilse, n8n arayüzünden "OpenAI Chat Model" düğümünü açıp kendi OpenAI kimlik bilginizi seçmeniz gerekecektir.

## Açık Sorular

Şu anda herhangi bir açık soru bulunmamaktadır. Gereksinimler detaylandırılmıştır ve önerilen değişiklikler doğrudan talep edilen toplu toplama mekanizmasını uygulamaktadır.

---

## Önerilen Değişiklikler

### n8n İş Akışı Yapılandırması

#### [MODIFY] [workflow.json](file:///c:/ILAN/WHATSAPP_N8N/workflow.json)
İş akışı JSON'unu güncellenmiş düğüm şeması, yerleşim koordinatları ve JS kodlarıyla yerelde yeniden oluşturacağız. Ardından, bu JSON'u `PUT /api/v1/workflows/MbJkVXLDCOZ5umpp` uç noktasını kullanarak uzak n8n sunucusuna yükleyeceğiz.

**Temel Değişiklikler:**
1. **1 Saatlik Engeli Kaldırma:** `Rate Limit Kontrol1` ve `1 Saat Engeli?1` düğümleri kaldırılacaktır.
2. **3 Dakikalık Batch Collector Ekleme:** Gelen her webhook isteğinde tetiklenen bir JavaScript Code düğümü (`Batch Collector`), mesajı müşterinin `staticData` üzerindeki toplu havuzuna ekleyecektir.
3. **Zaman Aşımı İçin Schedule Trigger Ekleme:** Her 60 saniyede bir çalışan `Schedule Trigger` düğümü, 3 dakikayı aşan ve yeni mesaj gelmeyen toplu havuzları işleyip göndermek üzere bir `Stale Batch Check` Code düğümünü tetikleyecektir.
4. **Yapay Zeka Cevap Çıktısı:** `AI Agent` sistem mesajı, hem `bildirim` (sahipler için özet) hem de `cevap` (müşteriye gönderilecek cevap) alanlarını içeren bir JSON çıktısı üretecek şekilde güncellenecektir.
5. **Müşteriye Cevap Gönderme:** Yapay zeka tarafından oluşturulan cevabı müşterinin WhatsApp numarasına göndermek için yeni bir HTTP Request düğümü (`Reply to Customer`) eklenecektir.

---

## Doğrulama Planı

### Otomatik Doğrulama
- Uzak iş akışının başarıyla güncellendiğini ve doğru bağlantılara/yapılandırmalara sahip 17 düğümü içerdiğini kontrol eden bir Python doğrulama betiği çalıştırılacaktır.

### Manuel Doğrulama
- Bir test numarasından WhatsApp mesajları gönderilerek webhook tetiklenecektir.
- Mesajların 3 dakikalık bir pencerede toplandığı doğrulanacaktır.
- Her iki yönetici telefon numarasına özet bildiriminin ulaştığı ve göndericiye de yapay zeka tarafından üretilen otomatik yanıtın gittiği kontrol edilecektir.
