# Opus 5.0 Analysis Package

Bu paket, `WHATSAPP_N8N` projesini iki ayrı AI ile inceletmek için hazırlandı.

## Amaç

İncelemeyi iki bağımsız eksene böl:

1. AI-1: workflow akışı, node bağlantıları, OOH Guard, delivery zinciri, fail-open davranışı, test sözleşmesi.
2. AI-2: PostgreSQL migration zinciri, function overload riskleri, index/cooldown tasarımı, güvenlik, deploy tutarlılığı, runtime riskleri.

## Beklenen çıktı formatı

Her AI için aşağıdaki başlıkları iste:

1. Kritik bulgular
2. Orta riskli bulgular
3. Düşük riskli bulgular
4. Net düzeltme önerileri
5. Öncelik sırası

Her bulgu için mümkünse şunları ver:

- Dosya ve satır
- Sorunun nedeni
- Üretim etkisi
- Önerilen düzeltme

## İnceleme soruları

### AI-1

- OOH Guard doğru yerde mi?
- `Check Business Hours` ile `Parse AI Output` arasındaki mesai kuralı tutarlı mı?
- `Send OOH to Customer`, `Notify Managers A/B` ve `Log OOH Event` zinciri fail-open davranıyor mu?
- Node bağlantıları çift gönderim veya dead-end oluşturuyor mu?
- Testler workflow.json ile aynı davranışı doğruluyor mu?

### AI-2

- `ooh_log` şeması doğru mu?
- `sender_number + created_at` composite index gerekli mi?
- 8 saatlik cooldown doğru çalışıyor mu?
- Migration sırası ve final state doğru mu?
- Canlı deploy ile git commit arasında drift var mı?
- Güvenlik ve outbound korumaları yeterli mi?

## Paket içeriği

- `build_workflow.py`
- `workflow.json`
- `db/migrations/*.sql`
- `tools/test_workflow_contract.py`
- `tools/test_workflow_behavior.js`
- `tools/wf_validate.py`
- `tools/wf_security.py`
- `tools/outbound_guard.py`
- `AGENTS.md`
- `.codex/config.toml`
- `.codex/skills/`

## Bilinen durum

- Son bilinen commit: `be2cd03`
- Workflow adı: `WhatsApp AI - v13 PostgreSQL Outbox`
- Live workflow ID: `TjWxSi2Es51mjw5Z`
- Canlı workflow versionId: `2aa796d9-5e1f-442d-aa7c-b62cfd961d93`
- Canlı workflow aktif: `true`
- Workflow node sayısı: `46`
- Migration durumu: `052_ooh_log.sql` ve `053_finalize_ai_retry_and_priority.sql` uygulandı

## Hariç tutulanlar

Gizli veya geçici dosyalar pakete dahil edilmez:

- `.env_token`
- `.session_checkpoint.txt`
- `.checkpoint_status.json`
- `.git/`
- `node_modules/`

## Yerel doğrulama

Paket hazırlanırken şu kontroller çalıştı:

```powershell
python build_workflow.py
python tools/wf_validate.py workflow.json
python tools/test_workflow_contract.py
node tools/test_workflow_behavior.js
python tools/wf_security.py workflow.json
python tools/outbound_guard.py workflow.json
```

## Not

Bu paket analiz içindir. Canlı mesaj gönderme, deploy veya migration tetikleme talimatı içermez.

## Opus çıktı şablonu

Opus’tan cevabı şu formatta iste:

```text
1. Kısa özet
2. Kritik bulgular
3. Orta riskli bulgular
4. Düşük riskli bulgular
5. Önerilen düzeltmeler
6. Öncelik sırası

Her bulgu için:
- Dosya / node / migration
- Sorunun nedeni
- Üretim etkisi
- Önerilen düzeltme
- Gerekirse test önerisi
```

Opus’tan özellikle şu iki soruyu yanıtlamasını iste:

- Müşteri ve yönetici mesajları neden gitmeyebilir?
- Mesai içi / mesai dışı davranış workflow ile canlı DB arasında tutarlı mı?
