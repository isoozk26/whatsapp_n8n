# Changelog

## 2026-07-18 - PostgreSQL Outbox ve Güvenilirlik

### Takip Düzeltmeleri

- Mesaj havuzu ilk mesajdan itibaren 120 saniye bekleyecek şekilde güncellendi.
- Doğrudan filtre kodu içeren talepler stok ve net fiyat kontrolü akışına alındı.
- Araç bazlı aramada marka, model, üretim yılı, CC ve kW/HP alanları tamamlanır
  hale getirildi; eksik alanlar müşteriye açıkça soruluyor.
- Düşük güvenli fakat deterministik araç taleplerinin manuel moda geçmesi engellendi.
- Atanan kişi adındaki Türkçe karakter kodlama sorunu düzeltildi.
- Araç modeli ve motor gücü ifadelerinin filtre kodu sanılması engellendi; araç
  bağlamı ürün kodu sınıflandırmasından önce değerlendiriliyor.

### Mimari

- Batch, mesaj dedupe, manuel mod, bildirim cooldown ve kanal teslimatları
  `whatsapp_ai` PostgreSQL schema'sına taşındı.
- Token-aware batch claim/finalize ve `FOR UPDATE SKIP LOCKED` tabanlı outbox
  dispatcher eklendi.
- Müşteri ve iki yönetici teslimatı bağımsız `pending/sending/sent/failed/dead`
  durumlarıyla izlenir hale getirildi.
- AI ve Evolution çağrıları için sınırlı retry, hata kodları ve dead-letter
  davranışı eklendi.

### Workflow

- Evolution payload'ları normalize edildi; webhook token doğrulaması ve duplicate
  mesaj koruması eklendi.
- Batch penceresi son mesajdan sonra 10 saniye sessizlik ve ilk mesajdan sonra en
  fazla 30 saniye olacak şekilde düzenlendi.
- Yönetici bildirimi araç, ürün/kod, istenen işlemler, atanan kişi, müşteri
  mesajları ve AI cevabını içeren bölümlü formata geçirildi.
- Fiat Egea gibi tanınabilir araç taleplerinde eksik motor, güç veya şasi bilgisi
  güvenli ve deterministik olarak sorulur hale getirildi.
- Geçersiz AI JSON'u artık tanınabilir talepleri yanlışlıkla manuel moda almıyor;
  güvenli fallback uygulanıyor. Sınıflandırılamayan parse hataları retry hattına
  yönlendiriliyor.

### Güvenlik ve Operasyon

- Evolution API anahtarları n8n credential kullanımına taşındı; webhook tokenı
  rotate edildi ve yalnız `MESSAGES_UPSERT` olayı açık bırakıldı.
- PostgreSQL migration, credential çözümleme ve canlı workflow deploy araçları
  eklendi.
- Outbound testler varsayılan olarak engellendi; gerçek numaralara gönderim açık
  onay ve koruma değişkenleri gerektiriyor.
- Başarılı execution verileri kısa tutulurken hata execution'larının saklanması
  sağlandı.

### Doğrulama

- JavaScript syntax, workflow contract, davranış, güvenlik ve outbound guard test
  kapıları eklendi.
- Hasan Durgun senaryosunda iki mesaj tek batch olarak işlendi; müşteri ve iki
  yönetici kanalı birer kez başarıyla teslim edildi ve yanlış manuel mod kaldırıldı.
# 2026-07-18 - Catalog, resilience and operations

- Added a staged MANN vehicle catalog with 24-hour customer vehicle context. Brand, model series and engine are required; year, engine code, kW/BHP, ccm and VIN are requested only when needed. Filter codes are never returned from this catalog.
- Added OpenAI and Evolution circuit breakers, exact AI retry timing, token-aware outbox processing and structured operational events.
- Added a separate operations workflow (`AezKZ5gGKEnxImGd`) for minute queue monitoring, 08:30 daily reports, 04:10 retention and 90-day credential reminders.
- Added manual checksum-gated catalog import, PostgreSQL integration tests on main pushes, a read-only drift probe and a real-schema runbook.
- Deployed migration `002` and main workflow version `a95d9ac4-2efb-445e-8c73-5e5b033677f5`. No outbound test message was sent. MANN checksum `fbec4b1252a5832afb9c9117e186c4d7845305f17d3443da6b8bb336657110c9` is staged with 18,474 unique vehicle rows, 47 brands and 2,187 brand-models; it remains inactive until explicitly approved.
