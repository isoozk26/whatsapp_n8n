# WhatsApp n8n PostgreSQL Outbox Workflow

`build_workflow.py` tek kaynak, `workflow.json` ise üretilen n8n artifact'idir.
Batch, dedupe, manuel mod ve kanal teslimatları n8n'in mevcut PostgreSQL
veritabanındaki izole `whatsapp_ai` schema'sında tutulur.

## Son değişiklikler

- PostgreSQL tabanlı atomik batch, dedupe ve kanal bazlı outbox mimarisi eklendi.
- Webhook token doğrulaması, AI/Evolution retry ve outbound test koruması getirildi.
- Yönetici kartları bölümlü formata geçirildi; araç talepleri için güvenli bilgi
  tamamlama akışı eklendi.
- AI parse hatasının tanınabilir talepleri yanlışlıkla manuel moda alması düzeltildi.
- Mesajlar 120 saniyelik havuzda birleştirilir; ürün kodu ve eksik araç bilgisi
  talepleri ayrı cevap politikalarıyla işlenir.
- Araç modeli, üretim yılı ve HP/kW ifadeleri ürün kodu olarak sınıflandırılmaz.

Ayrıntılı sürüm notları için [CHANGELOG.md](CHANGELOG.md) dosyasına bakın.

## Yerel doğrulama

```powershell
python build_workflow.py
python tools/wf_validate.py workflow.json
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/test_outbound_guard.py
```

Build bütün JavaScript Code node'larını sözdizimi açısından kontrol eder. Contract
ve davranış testleri webhook auth, payload normalizasyonu, token-aware batch claim,
AI hata sınırı ve kanal bazlı outbox sözleşmelerini doğrular.

## PostgreSQL migration

n8n'in mevcut PostgreSQL bağlantısını `WHATSAPP_POSTGRES_URL` olarak tanımlayın:

```powershell
python tools/wf_migrate.py
```

Migration yalnız `whatsapp_ai` schema'sını değiştirir. `public` schema ve n8n
tablolarına dokunmaz.

## Credential ve deploy

Workflow şu n8n credential adlarını bekler:

- `OpenAi account`
- `WhatsApp State PostgreSQL`
- `Evolution API`

Coolify'da `N8N_WEBHOOK_SECRET`, `ADMIN_PHONE_A`, `ADMIN_PHONE_B` ve
`OWNER_PHONE_NUMBERS` değişkenleri tanımlanmalıdır. Deploy scripti credential
kimliklerini adlarından çözer ve varsayılan olarak canlı workflow
`pW8YzDP44WpeJ6CJ` üzerinde çalışır.

```powershell
python upload_to_n8n.py
```

Deploy öncesinde PostgreSQL backup ve migration doğrulanmalıdır. Rollback için
önceki n8n workflow sürümü korunur; migration geriye dönük uyumludur.
