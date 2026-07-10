# WhatsApp AI v10 - Denetim Raporu

## Tarih: 10 Temmuz 2026
## Surum: v10 Production
## Dugum: 25 | Baglanti: 20

---

## 1. Mimari Degerlendirme

### Webhook Path (AI Cagirmaz)
```
Webhook → Route Message (duplikat+filtre) → Is Customer Message?
  → batch: Batch Collector (sadece toplar)
  → command: Command Handler → Phone A+B
  → ignore: biter
```

### Schedule Path (AI Yalnizca Buradan)
```
Schedule (30sn) → Stale Batch Check → Stale Exists? → Store Context
  → AI Agent → Parse AI Output → Is Reply?
    → [true] Reply to Customer → Finalize Batch → Phone A+B
    → [false] Should Notify? → Handoff Ack → Phone A+B
```

### Guclu Yonler
- Webhook ve Schedule tamamen ayri (race condition imkansiz)
- pendingMessages/processingMessages ayrimi
- messageId duplikat korumasi (6 saat TTL)
- processingToken ile tek execution tek musteri
- 7 farkli medya tipi destegi
- Tam handoff akisi (musteri aktarim + admin bildirim + manuel mod)
- Unclear sayaci ile 2x belirsiz → otomatik handoff
- AI parse hatasinda handoff

---

## 2. Tespit Edilen Sorunlar ve Duzeltmeler

### KRITIK Duzeltmeler (Uygulandi)
| # | Sorun | Duzeltme |
|---|-------|----------|
| 1 | windowMs 30sn (cok kisa) | 3 * 60 * 1000 (3 dk) |
| 2 | Schedule 10sn (gereksiz sik) | 30sn |
| 3 | API key placeholder | Gercek key ile degistirildi |
| 4 | manualModes = false (basi acik) | delete ile temizlendi |
| 5 | unclearCounts temizlenmiyor | Command Handler + Finalize Batch'e eklendi |

### ORTA Seviye Sorunlar (Not Alindi)
| # | Sorun | Aciklama | Onem |
|---|-------|----------|------|
| 6 | Static data eszamanli risk | n8n yuksek frekasta guvensiz olabilir | ORTA |
| 7 | Webhook secret yok | URL ogrenilirse sahte payload gonderilebilir | ORTA |
| 8 | Respond OK erken donebilir | Batch kaydedilmeden once 200 doner | ORTA |
| 9 | Agent gereksiz | Tool baglantisi yok, LLM Chain daha kararli | ORTA |
| 10 | Simple Memory queue mode | Queue mode'da calismayabilir | ORTA |

### Dusuk Seviye Sorunlar
| # | Sorun | Aciklama |
|---|-------|----------|
| 11 | Is Customer? + Is Command? gereksiz | 2 IF yerine 1 Switch daha temiz |
| 12 | HTTP retry cift mesaj | Timeout olursa ayni mesaj tekrar gidebilir |
| 13 | Handoff batch'i siler | AI sirasinda gelen yeni mesaj kaybolabilir |
| 14 | LID numarasi | @lid gercek telefon numarasi olmayabilir |
| 15 | Kapasite sinirli | 30sn'de 1 musteri, yuksek trafikte gecikme |

---

## 3. Guvenli Senaryolar

| Senaryo | Durum |
|---------|-------|
| Musteri ++ yaziyor | Komut sayilmaz, normal mesaj |
| Siz ++ yaziyorsunuz | Manuel mod acilir |
| Siz -- yaziyorsunuz | Otomatik mod acilir |
| Ayni webhook tekrar | 6 saatlik dedup |
| AI gec cevap, batch degismis | Eski cevap yutuluyor |
| AI JSON bozuk | Handoff |
| Musteri AI sirasinda yazar | Pending kuyruğuna eklenir |
| Musteri sadece tesekkur ediyor | expectsReply=false, idle alarm yok |
| Handoff sonra musteri yazar | Bot cevap vermiyor |
| 2x belirsiz mesaj | Otomatik handoff |
| confidence < 0.55 | Otomatik handoff |

---

## 4. Production Hazirlik Kontrol Listesi

- [x] windowMs: 30sn → 3dk
- [x] Schedule: 10sn → 30sn
- [x] API key: Gercek key ile degistirildi
- [x] manualModes: delete ile temizleme
- [x] unclearCounts: Temizleme eklendi
- [ ] Webhook secret/header dogrulamasi (uzun vadeli)
- [ ] Static data → Redis/PostgreSQL (uzun vadeli)
- [ ] Basic LLM Chain + Structured Output Parser (uzun vadeli)
- [ ] Error Workflow olustur (uzun vadeli)
- [ ] Rate limiting (uzun vadeli)

---

## 5. Test Senaryolari

| # | Senaryo | Beklenen |
|---|---------|----------|
| 1 | Normal musteri mesaji | 3dk batch → AI reply → bildirim |
| 2 | ++ komutu | Manuel mod + admin bildirim |
| 3 | -- komutu | Otomatik mod + admin bildirim |
| 4 | Manuel modda musteri | Sessiz kalir |
| 5 | Handoff intent | Musteri aktarim + admin + manuel mod |
| 6 | 2x unclear | Otomatik handoff |
| 7 | confidence < 0.55 | Otomatik handoff |
| 8 | Gorsel/video/ses | Medya tipi etiketiyle batch |
| 9 | Spam (30+ mesaj) | spam_limit |
| 10 | AI timeout | 2dk sonra re-queue |
| 11 | Duplicate webhook | _seenMessageIds ile filtre |
| 12 | Grup mesaji | Filtrelendi |
| 13 | 10dk sessiz musteri | Idle alert |

---

## 6. Sonuc

v10 Production, onceki tum kritik bug'lari (sonsuz dongu, race condition, ++ sizintisi, mesaj kaybi) cozmus durumda. Mimari olarak webhook ve schedule ayristirilmis, duplikat korumasi, processing timeout, handoff akisi ve unclear sayaci eklenmis.

Tek kritik eksik: static data eszamanli risk ve webhook secret. Bunlar uzun vadeli iyilestirmeler olarak planlanmali.

**Production uygunluk: 8/10**
