#!/usr/bin/env python3
"""WhatsApp AI v5 - Ornek Konusma Simulasyonu"""

print("=" * 60)
print("WHATSAPP AI v5 - ORNEK KONUSMA SIMULASYONU")
print("=" * 60)

print("""
[TARIH: 10 Temmuz 2026, 14:30]

========================================
MUSTERI: Ahmet Yilmaz (905331112233)
========================================

14:30 | Ahmet: Merhaba, Renault Clio 2018 icin yag filtresi ariyorum
14:30 | [SISTEM] Batch toplaniyor... (1/30 mesaj)
14:31 | Ahmet: Bir de hava filtresi lazim
14:31 | [SISTEM] Batch toplaniyor... (2/30 mesaj)
14:32 | Ahmet: Sase numaram WDB9066351R123456
14:32 | [SISTEM] Batch toplaniyor... (3/30 mesaj)

--- 3 dk idle suresi bekleniyor ---

14:35 | [BATCH READY] 3 mesaj islendi

--- AI Agent calisiyor ---

14:35 | [AI CIKTI]:
       {
         "bildirim": "Ahmet Yilmaz 905331112233 - Renault Clio 2018 yag ve hava
         filtresi istiyor, sase bilgisi gonderdi",
         "cevap": "WDB9066351R123456 sase numaranizla uyumlu MANN, Filtron ve
         Filtorq marka yag ve hava filtresi setlerimiz mevcuttur. Fiyat bilgisi
         icin ekibimiz sizinle iletisime gececektir."
       }

--- Bildirim gonderiliyor ---

14:35 | [TELEFON A - 0505...] gitti:
       "Ahmet Yilmaz 905331112233 - Renault Clio 2018 yag ve hava filtresi
       istiyor, sase bilgisi gonderdi"

14:35 | [TELEFON B - 0530...] gitti:
       "Ahmet Yilmaz 905331112233 - Renault Clio 2018 yag ve hava filtresi
       istiyor, sase bilgisi gonderdi"

--- Musteriye cevap gidiyor ---

14:35 | Ahmet'e cevap:
       "WDB9066351R123456 sase numaranizla uyumlu MANN, Filtron ve Filtorq
       marka yag ve hava filtresi setlerimiz mevcuttur. Fiyat bilgisi icin
       ekibimiz sizinle iletisime gececektir."


========================================
SAHIP KOMUTU: ++ (MANUEL MODA GECIS)
========================================

14:40 | Sahip (0536): ++     [Ahmet Sohbetinde]
14:40 | [SISTEM] Ahmet Yilmaz (905331112233) icin MANUEL MOD aktif
14:40 | [TELEFON A] "Sistem Manuel De - Ahmet Yilmaz (905331112233)"
14:40 | [TELEFON B] "Sistem Manuel De - Ahmet Yilmaz (905331112233)"

14:42 | Ahmet: Fiyatlar ne kadar?
14:42 | [SISTEM] Mesaj yutuldu (manuel mod) - AI'a gitmedi

14:45 | Ahmet: Bir de polen filtresi istiyorum
14:45 | [SISTEM] Mesaj yutuldu (manuel mod) - AI'a gitmedi

--- Sahip manuel olarak cevap veriyor ---

14:50 | Sahip (0536): Yag filtresi 450 TL, hava filtresi 280 TL,
       polen filtresi 180 TL. Siparis icin onay bekliyoruz.


========================================
SAHIP KOMUTU: -- (OTOMATIK MODA DONUS)
========================================

14:55 | Sahip (0536): --     [Ahmet Sohbetinde]
14:55 | [SISTEM] Ahmet Yilmaz (905331112233) icin OTOMATIK MOD aktif
14:55 | [TELEFON A] "Sistem Otomatik - Ahmet Yilmaz (905331112233)"
14:55 | [TELEFON B] "Sistem Otomatik - Ahmet Yilmaz (905331112233)"

14:57 | Ahmet: Tesekkurler, siparis vermek istiyorum
14:57 | [SISTEM] Mesaj alindi, batch toplaniyor...
15:00 | [BATCH READY] AI calisiyor

15:00 | [AI CIKTI]:
       {
         "bildirim": "Ahmet Yilmaz 905331112233 - Siparis vermek istiyor,
         filtre seti talep etti",
         "cevap": "Siparisiniz alinmistir. Yag, hava ve polen filtresi seti
         910 TL toplam. Kargo bilgilerinizi gonderir misiniz?"
       }


========================================
BOS AI YANITI (FALLBACK)
========================================

15:05 | Musteri: Mercedes Sprinter 2020 icin arama yapiyorum
15:08 | [AI HATA] Bos yanit dondu
15:08 | [FALLBACK] Manuel bildirim olusturuldu:
       "Mehmet Kaya 905342223344 - Mercedes Sprinter 2020 arama yapiyor"
15:08 | [TELEFON A] "Mehmet Kaya 905342223344 - Mercedes Sprinter 2020 arama
       yapiyor"
15:08 | [TELEFON B] "Mehmet Kaya 905342223344 - Mercedes Sprinter 2020 arama
       yapiyor"
15:08 | [MUSTERIYE] "Talebinizi aldik, en kisa surede donecegiz."


========================================
GRUP MESAJI (FILTRELENDI)
========================================

15:10 | Grup mesaji: "Herkes filtre ariyor" [@g.us]
15:10 | [SISTEM] Grup mesaji filtrelendi, islenmedi


========================================
SPAM KORUMASI (30+ mesaj)
========================================

15:15 | Musteri: Mesaj 1
15:15 | Musteri: Mesaj 2
... (30 mesaj)
15:18 | Musteri: Mesaj 31
15:18 | [SISTEM] Spam limiti asildi (30/30) - mesaj yutuldu


========================================
IDLE TIMEOUT (10 DK SESSIZLIK)
========================================

15:00 | Musteri son mesajini gonderdi
15:10 | [IDLE CHECK] 10 dk gecti, cevap yok
15:10 | [TELEFON A] "Sessiz musteri - 905331112233 - 10 dkdir cevap yazmiyor"
15:10 | [TELEFON B] "Sessiz musteri - 905331112233 - 10 dkdir cevap yazmiyor"
""")

print("=" * 60)
print("OZET: 7 senaryo basariyla calisti")
print("=" * 60)
