# WhatsApp AI Runbook

## Guvenlik Kurali

Canli veya test numarasina mesaj gonderen hicbir E2E kontrol, acik kullanici onayi olmadan calistirilmaz. Salt okunur durum kontrolleri ve staging katalog importu mesaj gondermez.

## Zamanlanmis Isler

| Is | Zaman | Davranis |
|---|---|---|
| Queue monitor | Her dakika | 7 dk bekleyen batch, 5 dk processing, dead delivery ve AI manual sayar; 30 dk cooldown ile yonetici outbox alarmi olusturur. |
| Gunluk rapor | Her gun 08:30 Europe/Istanbul | Son 24 saat mesaj, teslimat ve AI manual ozetini yonetici outbox'a yazar. |
| Retention | Her gun 04:10 | 24 saatlik arac baglamini siler, 7 gunluk sent payload'i maskeler, 30 gunluk dead/event kaydini siler. |
| Credential reminder | Her gun 09:00 kontrol | Son rotation 90 gunu astiysa manuel rotation hatirlatir. |
| Drift monitor | Her 10 dakika, host cron | Workflow active/version ve servis erisimi farklarini alarm olarak raporlar; otomatik duzeltmez. |

## Kuyruk Kontrolu

```sql
SELECT status,count(*) FROM whatsapp_ai.batches GROUP BY status;
SELECT status,channel,count(*) FROM whatsapp_ai.deliveries GROUP BY status,channel;
SELECT * FROM whatsapp_ai.batches
WHERE status='processing' AND processing_started_at < clock_timestamp()-interval '5 minutes';
SELECT event_type,details,created_at FROM whatsapp_ai.system_events
ORDER BY created_at DESC LIMIT 50;
```

## Circuit Breaker

```sql
SELECT service,state,consecutive_failures,opened_until,last_error_code
FROM whatsapp_ai.service_circuits;
```

Bes hata iki dakika icinde devreyi 60 saniye acar. Sure sonunda tek half-open probe gecis alir. Basarili probe devreyi kapatir; basarisiz probe yeniden acar.

## Katalog Importu

1. `python tools/import_mann_catalog.py C:\JSON\MANN_FULL_SQL\mann_full_kod.csv`
2. Ciktilardaki checksum, satir, marka ve model sayisini kontrol et.
3. Onaydan sonra ayni dosya ve checksum ile `--activate --checksum <sha256>` calistir.

Importer filtre kodlarini yuklemez. VIN yalniz 24 saatlik musteri arac baglaminda tutulur ve katalog eslestirme anahtari degildir.

## Credential Rotation

OpenAI, Evolution, n8n API ve PostgreSQL credentiallari manuel yenilenir. Tamamlandiginda:

```sql
UPDATE whatsapp_ai.settings
SET value=current_date::text,updated_at=clock_timestamp()
WHERE key='credentials_last_rotated_at';
```

## Geri Alma

Workflow deploy oncesi export saklanir. Hata durumunda once workflow deactivate edilir, son bilinen iyi JSON yuklenir ve tekrar activate edilir. Migration `002` veri kaybetmeden yeni nesneler ekler; katalog aktivasyonu onceki importu `rejected` yapar ancak satirlari silmez.
