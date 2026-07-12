#!/usr/bin/env python3
"""WhatsApp AI v5 - Kapsamli Test Sablonlari
Her senaryo icin:
  - Phone A'ya giden bildirim (ozet)
  - Phone B'ya giden bildirim (ozet)
  - Musteriye giden AI cevabi
"""

def banner(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def notification(phone, text):
    print(f"  [{phone}] {text}")

def customer_reply(text):
    print(f"  [MUSTERIYE] {text}")

def separator():
    print(f"  {'-'*50}")


# ═══════════════════════════════════════════════════════════
# SENARYO 1: YAG FILTRESI TALEBI
# ═══════════════════════════════════════════════════════════
banner("SENARYO 1: YAG FILTRESI TALEBI")
print("  Musteri: Ahmet Yilmaz (905331112233)")
separator()
print("  [MUSTERI] Merhaba, Renault Clio 2018 icin yag filtresi ariyorum")
print()
notification("Phone A", "Ahmet Yilmaz 905331112233 - Renault Clio 2018 yag filtresi siparisi istiyor, arac bilgisi soruldu")
notification("Phone B", "Ahmet Yilmaz 905331112233 - Renault Clio 2018 yag filtresi siparisi istiyor, arac bilgisi soruldu")
separator()
customer_reply("Filtre uyumu icin aracinizin marka/model/yil/sase bilgisini paylasir misiniz?")


# ═══════════════════════════════════════════════════════════
# SENARYO 2: COKLU URUN TALEBI
# ═══════════════════════════════════════════════════════════
banner("SENARYO 2: COKLU URUN TALEBI (3 filtre)")
print("  Musteri: Mehmet Kaya (905342223344)")
separator()
print("  [MUSTERI] Mercedes Sprinter 2020 var")
print("  [MUSTERI] Hava filtresi de lazim")
print("  [MUSTERI] Yakit filtresi de olsun")
print()
notification("Phone A", "Mehmet Kaya 905342223344 - Mercedes Sprinter 2020 icin yag, hava ve yakit filtresi istiyor")
notification("Phone B", "Mehmet Kaya 905342223344 - Mercedes Sprinter 2020 icin yag, hava ve yakit filtresi istiyor")
separator()
customer_reply("Mercedes Sprinter 2020 icin MANN-Filter, Filtron ve Filtorq markalarinda uyumlu yag, hava ve yakit filtresi seti mevcuttur. Fiyat ve stok bilgisi icin ekibimiz sizinle iletisime gececektir.")


# ═══════════════════════════════════════════════════════════
# SENARYO 3: SASE NUMARASI ILE UYUMLULUK
# ═══════════════════════════════════════════════════════════
banner("SENARYO 3: SASE NUMARASI ILE UYUMLULUK")
print("  Musteri: Ali Demir (905355556666)")
separator()
print("  [MUSTERI] BMW 320d 2019 aracim var")
print("  [MUSTERI] Sase numaram WBAPL5105KA123456")
print()
notification("Phone A", "Ali Demir 905355556666 - BMW 320d 2019 sase ile uyumlu filtre ariyor")
notification("Phone B", "Ali Demir 905355556666 - BMW 320d 2019 sase ile uyumlu filtre ariyor")
separator()
customer_reply("WBAPL5105KA123456 sase numaranizla uyumlu MANN-Filter yag, hava ve polen filtresi setlerimiz mevcuttur. Siparis icin ekibimiz sizinle iletisime gececektir.")


# ═══════════════════════════════════════════════════════════
# SENARYO 4: FIYAT SORGULAMA
# ═══════════════════════════════════════════════════════════
banner("SENARYO 4: FIYAT SORGULAMA")
print("  Musteri: Fatma Yildiz (905367778888)")
separator()
print("  [MUSTERI] Fiat Egea 2021 icin yag filtresi fiyati ne kadar?")
print()
notification("Phone A", "Fatma Yildiz 905367778888 - Fiat Egea 2021 yag filtresi fiyati soruyor")
notification("Phone B", "Fatma Yildiz 905367778888 - Fiat Egea 2021 yag filtresi fiyati soruyor")
separator()
customer_reply("Fiat Egea 2021 icin uyumlu yag filtrelerimiz mevcuttur. Fiyat bilgisi icin ekibimiz sizinle en kisa surede iletisime gececektir.")


# ═══════════════════════════════════════════════════════════
# SENARYO 5: SIPARIS VERME
# ═══════════════════════════════════════════════════════════
banner("SENARYO 5: SIPARIS VERME")
print("  Musteri: Hasan Coskun (905378889999)")
separator()
print("  [MUSTERI] Toyota Corolla 2020 icin yag filtresi almak istiyorum")
print("  [MUSTERI] Siparis vermek istiyorum")
print()
notification("Phone A", "Hasan Coskun 905378889999 - Toyota Corolla 2020 yag filtresi siparisi vermek istiyor")
notification("Phone B", "Hasan Coskun 905378889999 - Toyota Corolla 2020 yag filtresi siparisi vermek istiyor")
separator()
customer_reply("Toyota Corolla 2020 icin uyumlu yag filtresi siparisiniz alinmistir. Kargo bilgilerinizi gonderir misiniz?")


# ═══════════════════════════════════════════════════════════
# SENARYO 6: ++ KOMUTU (MANUEL MOD)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 6: ++ KOMUTU (MANUEL MODA GECIS)")
print("  Sahip (0536): Ahmet Sohbetinde ++ yazar")
separator()
print("  [SAHIP] ++")
print()
notification("Phone A", "Sistem Manuel De - Ahmet Yilmaz (905331112233)")
notification("Phone B", "Sistem Manuel De - Ahmet Yilmaz (905331112233)")
separator()
print("  [SONRA] Musteri mesaj yazar ama AI'a gitmez, yutulur")


# ═══════════════════════════════════════════════════════════
# SENARYO 7: -- KOMUTU (OTOMATIK MOD)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 7: -- KOMUTU (OTOMATIK MODA DONUS)")
print("  Sahip (0536): Ahmet Sohbetinde -- yazar")
separator()
print("  [SAHIP] --")
print()
notification("Phone A", "Sistem Otomatik - Ahmet Yilmaz (905331112233)")
notification("Phone B", "Sistem Otomatik - Ahmet Yilmaz (905331112233)")
separator()
print("  [SONRA] Sistem tekrar otomatik calismaya baslar")


# ═══════════════════════════════════════════════════════════
# SENARYO 8: GRUP MESAJI (FILTRELEME)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 8: GRUP MESAJI (FILTRELEME)")
print("  WhatsApp grubundan mesaj gelir")
separator()
print("  [GRUP] Herkes filtre ariyor [@g.us]")
print()
print("  [SISTEM] Grup mesaji filtrelendi, islenmedi")


# ═══════════════════════════════════════════════════════════
# SENARYO 9: SPAM KORUMASI (30+ MESAJ)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 9: SPAM KORUMASI (30+ MESAJ)")
print("  Musteri 31 mesaj gonderir")
separator()
for i in range(1, 32):
    print(f"  [MUSTERI] Mesaj {i}")
print()
print("  [SISTEM] 1-30 arasi mesajlar toplandi")
print("  [SISTEM] 31. mesaj: Spam limiti asildi (30/30) - yutuldu")


# ═══════════════════════════════════════════════════════════
# SENARYO 10: IDLE TIMEOUT (10 DK SESSIZLIK)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 10: IDLE TIMEOUT (10 DK SESSIZLIK)")
print("  Musteri 10 dk cevap vermez")
separator()
print("  [MUSTERI] Son mesaj: 15:00'da gonderildi")
print("  [SISTEM] 15:10 - 10 dk gecti, cevap yok")
print()
notification("Phone A", "Sessiz musteri - 905331112233 - 10 dkdir cevap yazmiyor")
notification("Phone B", "Sessiz musteri - 905331112233 - 10 dkdir cevap yazmiyor")


# ═══════════════════════════════════════════════════════════
# SENARYO 11: BOZUK MEYDANA (FALLBACK)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 11: BOS AI YANITI (FALLBACK)")
print("  AI bos veya hatali dondurur")
separator()
print("  [MUSTERI] Opel Astra 2017 icin filtre ariyorum")
print()
print("  [AI HATA] Bos yanit dondu veya JSON parse hatasi")
print()
notification("Phone A", "Mehmet Kaya 905342223344 - Opel Astra 2017 filtre ariyor")
notification("Phone B", "Mehmet Kaya 905342223344 - Opel Astra 2017 filtre ariyor")
separator()
customer_reply("Talebinizi aldik, en kisa surede donecegiz.")


# ═══════════════════════════════════════════════════════════
# SENARYO 12: INGILIZCE MESAJ (FILTRELEME)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 12: INGILIZCE MESAJ")
print("  Musteri Ingilizce yazar")
separator()
print("  [MUSTERI] I need oil filter for VW Golf 2019")
print()
notification("Phone A", "John Smith 905389990000 - VW Golf 2019 icin yag filtresi ariyor, Ingilizce mesaj")
notification("Phone B", "John Smith 905389990000 - VW Golf 2019 icin yag filtresi ariyor, Ingilizce mesaj")
separator()
customer_reply("VW Golf 2019 icin uyumlu yag filtrelerimiz mevcuttur. Arac bilgilerinizi paylasir misiniz?")


# ═══════════════════════════════════════════════════════════
# SENARYO 13: MEDYA MESAJI (FOTOGRAF)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 13: MEDYA MESAJI (FOTOGRAF)")
print("  Musteri fotograf gonderir")
separator()
print("  [MUSTERI] [Fotograf: Elindeki filtre kutusu]")
print()
notification("Phone A", "Zeynep Kara 905391112222 - Filtre fotografı gonderdi, inceleme bekliyor")
notification("Phone B", "Zeynep Kara 905391112222 - Filtre fotografı gonderdi, inceleme bekliyor")
separator()
customer_reply("Fotografinizi inceledik. Uyumlu filtre seceneklerini size en kisa surede iletecegiz.")


# ═══════════════════════════════════════════════════════════
# SENARYO 14: ICICE KOMUT (++ SONRASI MESAJ)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 14: ++ SONRASI MUSTERI MESAJI (YUTULMA)")
print("  Sahip ++ yazar, sonra musteri mesaj gonderir")
separator()
print("  [SAHIP] ++  -> Sistem Manuel De")
print("  [MUSTERI] Fiyatlar ne kadar?")
print("  [SISTEM] Mesaj yutuldu (manuel mod)")
print("  [MUSTERI] Bir de polen filtresi lazim")
print("  [SISTEM] Mesaj yutuldu (manuel mod)")
print()
print("  [SAHIP] --  -> Sistem Otomatik")
print("  [MUSTERI] Siparis vermek istiyorum")
print("  [SISTEM] Mesaj alindi, AI'a gidecek")


# ═══════════════════════════════════════════════════════════
# SENARYO 15: AYNI ANDA 3 MUSTERI
# ═══════════════════════════════════════════════════════════
banner("SENARYO 15: AYNI ANDA 3 MUSTERI")
separator()
print("  [MUSTERI 1] Ahmet - Renault Clio yag filtresi")
print("  [MUSTERI 2] Mehmet - Mercedes Sprinter hava filtresi")
print("  [MUSTERI 3] Ali - BMW 320d polen filtresi")
print()
notification("Phone A", "Ahmet 90533... - Renault Clio yag filtresi istiyor")
notification("Phone A", "Mehmet 90534... - Mercedes Sprinter hava filtresi istiyor")
notification("Phone A", "Ali 90535... - BMW 320d polen filtresi istiyor")
notification("Phone B", "Ahmet 90533... - Renault Clio yag filtresi istiyor")
notification("Phone B", "Mehmet 90534... - Mercedes Sprinter hava filtresi istiyor")
notification("Phone B", "Ali 90535... - BMW 320d polen filtresi istiyor")
separator()
customer_reply("Her 3 musteriye de ayri ayri filtre uyumu cevabi gonderildi")


# ═══════════════════════════════════════════════════════════
# SENARYO 16: HIZLI MESAJ SERIDI (SLIDING WINDOW)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 16: HIZLI MESAJ SERIDI (SLIDING WINDOW)")
print("  Musteri 2 dk icinde 5 mesaj atar")
separator()
print("  [T+0dk] Merhaba")
print("  [T+0dk] Fiat Egea 2021")
print("  [T+1dk] Yag filtresi ariyorum")
print("  [T+1dk] Bir de hava filtresi")
print("  [T+2dk] Fiyat ne kadar?")
print()
print("  [T+3dk] 3 dk idle suresi doldu - batch hazir")
print()
notification("Phone A", "Ahmet Yilmaz 905331112233 - Fiat Egea 2021 icin yag ve hava filtresi ariyor, fiyat soruyor")
notification("Phone B", "Ahmet Yilmaz 905331112233 - Fiat Egea 2021 icin yag ve hava filtresi ariyor, fiyat soruyor")
separator()
customer_reply("Fiat Egea 2021 icin MANN-Filter marka yag ve hava filtresi seti mevcuttur. Fiyat bilgisi icin ekibimiz sizinle iletisime gececektir.")


# ═══════════════════════════════════════════════════════════
# SENARYO 17: PROCESSING FLAG (AI CALISIRKEN GELEN MESAJ)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 17: AI CALISIRKEN GELEN MESAJ")
print("  AI islerken musteri yeni mesaj gonderir")
separator()
print("  [MUSTERI] Renault Clio yag filtresi")
print("  [SISTEM] Batch hazir, AI calisiyor...")
print("  [MUSTERI] Bir de hava filtresi lazim  <- AI calisirken gelen")
print("  [SISTEM] Mesaj kuyruğa alindi (processing)")
print()
notification("Phone A", "Ahmet Yilmaz 905331112233 - Renault Clio yag filtresi istiyor")
notification("Phone B", "Ahmet Yilmaz 905331112233 - Renault Clio yag filtresi istiyor")
separator()
customer_reply("Renault Clio icin uyumlu yag filtresi mevcuttur. Fiyat bilgisi icin ekibimiz sizinle iletisime gececektir.")


# ═══════════════════════════════════════════════════════════
# SENARYO 18: BOZUK MEYDANA (MEDYA + TEXT KARISIK)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 18: MEDYA + TEXT KARISIK")
print("  Musteri hem fotograf hem yazar")
separator()
print("  [MUSTERI] [Fotograf: Filtr kutusu]")
print("  [MUSTERI] Bu filtre uyumlu mu?")
print()
notification("Phone A", "Zeynep Kara 905391112222 - Filtre uyumluluk sorusu, fotograf gonderdi")
notification("Phone B", "Zeynep Kara 905391112222 - Filtre uyumluluk sorusu, fotograf gonderdi")
separator()
customer_reply("Fotografinizi inceledik. Uyumluluk kontrolu icin arac marka/model/yil/sase bilgilerinizi paylasir misiniz?")


# ═══════════════════════════════════════════════════════════
# SENARYO 19: UZUN MESAJ (DETAYLI TALEP)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 19: UZUN MESAJ (DETAYLI TALEP)")
print("  Musteri cok uzun yazar")
separator()
print("  [MUSTERI] Merhaba, 2020 model Volkswagen Passat 1.6 TDI aracim var. Yaklasik 85000 km'de. Yağ degisimi zamani geldi. Yag filtresi, hava filtresi ve yakit filtresi ariyorum. Orijinal MANN-Filter marka olmasini tercih ederim. Sase numaram WVWZZZ3CZWE123456. Fiyat bilgisi verir misiniz?")
print()
notification("Phone A", "Emre Tan 905392223333 - VW Passat 1.6 TDI 2020 icin MANN yag/hava/yakit filtresi seti ariyor, fiyat soruyor, sase: WVWZZZ3CZWE123456")
notification("Phone B", "Emre Tan 905392223333 - VW Passat 1.6 TDI 2020 icin MANN yag/hava/yakit filtresi seti ariyor, fiyat soruyor, sase: WVWZZZ3CZWE123456")
separator()
customer_reply("WVWZZZ3CZWE123456 sase numaranizla uyumlu MANN-Filter yag, hava ve yakit filtresi seti mevcuttur. Fiyat bilgisi icin ekibimiz sizinle iletisime gececektir.")


# ═══════════════════════════════════════════════════════════
# SENARYO 20: KISA MESAJ (SORU)
# ═══════════════════════════════════════════════════════════
banner("SENARYO 20: KISA MESAJ (TEK KELIME)")
print("  Musteri cok kisa yazar")
separator()
print("  [MUSTERI] fiyat?")
print()
notification("Phone A", "Bilinmeyen 905393334444 - Fiyat sorusu, detay bilgi gerekli")
notification("Phone B", "Bilinmeyen 905393334444 - Fiyat sorusu, detay bilgi gerekli")
separator()
customer_reply("Fiyat bilgisi icin arac marka/model/yil bilgilerinizi paylasir misiniz?")


# ═══════════════════════════════════════════════════════════
# OZET
# ═══════════════════════════════════════════════════════════
banner("TEST OZETI")
print("""
  Toplam Senaryo: 20
  ├── Normal Musteri:     5  (1-5)
  ├── Komut Senaryolari:  2  (6-7)
  ├── Filtreleme:         2  (8, 12)
  ├── Koruma Mekanizmasi: 3  (9, 10, 11)
  ├── Karmasik Durumlar:  5  (13-17)
  └── Edge Cases:         3  (18-20)

  Her senaryo icin:
    Phone A: Bildirim ozeti
    Phone B: Bildirim ozeti
    Musteri: AI cevabi
""")
print("=" * 60)
