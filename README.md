# osu! Archive Manager

osu! beatmap paketlerini (`.zip`) toplu olarak açan, hafızada takip eden, seri
boşluklarını bulup Excel'de kırmızı gösteren, `.osz` müzikleri tekilleştirilmiş
bir kütüphaneye yedekleyen ve tek tuşla osu!lazer'a aktaran masaüstü uygulaması.

> Arka plan, kod ve loglar İngilizce; kullanıcı arayüzü Türkçe/İngilizce (Ayarlar'dan).

## Ne yapar?

1. **`Packs/`** klasöründeki tüm `.zip` paketleri okur ve sayar.
2. **Arşivleri Çıkar ve İşle** — hepsini **`Output/`** içine düz (flat) çıkarır
   (Spotlight paketlerindeki `osu!/`, `osu!mania/` alt klasörleri de düzleştirir,
   ama kaynağını hafızaya not eder), paketleri hafızaya işler, **Excel** raporunu
   üretir ve işlenen `.zip`'i Geri Dönüşüm Kutusu'na taşır.
   - Daha önce eklenmiş bir paket tekrar gelirse **sorar** (tümü zaten mevcut /
     bazıları eksik).
3. **Library'e Kopyala** — `Output`'taki `.osz`'leri **`Library/`** yedeğine
   tekilleştirerek kopyalar (aynı beatmap tekrar kopyalanmaz; sadece
   "kopya denemesi" sayacı artar).
4. **osu!'ya Aktar** — `Output`'taki `.osz`'leri partiler hâlinde osu!lazer'a
   gönderir; osu! kendi güvenli içe-aktarma hattıyla ekler.
5. **Arşiv Verisini Yenile** — `Library/`'yi tarar; elle eklenenleri hafızaya
   alır, kaybolanları tarih damgasıyla "kayboldu" olarak işaretler.
6. **Müzik Ara** — sanatçı/başlık/ID ile arama ("Hatsune Miku" → tüm eşleşmeler).

## Seri boşluk (kırmızı) mantığı — yalnızca GERÇEK eksikler

- **Standard (S/SM/ST/SC):** osu! bunları boşluksuz numaralar → aradaki eksik numara
  kesinlikle gerçek → **kırmızı** (ör. `S1821`, `SM363`). Ağ gerekmez.
- **Featured / Spotlights / Theme / diğer + resmi olmayan paketler:** offline'da
  **kırmızı gösterilmez**, sadece listelenir (yanlış kırmızı olmaz).
- **Opsiyonel osu! API referansı:** Ayarlar'a osu! `client_id`+`secret` girip
  "Referansı Güncelle" dersen, yayınlanmış gerçek pakete göre TÜM kategorilerde
  (Spotlights dahil) kırmızı %100 doğru olur.

## Zengin metadata

Her `.osz` içindeki `.osu` dosyalarından **BPM, süre, mapper, mod, kaynak, tag,
zorluk sayısı** okunur; Müzik Ara ve Sanatçılar sekmelerinde gösterilir ve bunlara
göre sıralanabilir. Bozuk isimli dosyalar "Unknown" sanatçı olarak sorunsuz eklenir.

## Temalar

Dark (varsayılan), White, Pink, Pink · Açık, Pink · Koyu, Nord, Dracula,
Catppuccin (Mocha/Latte), Solarized (Dark/Light). Ayarlar sekmesinden.

## Klasör yapısı

```
Packs/     gelen .zip paketler (giriş)
Output/    çıkarılan .osz'ler (güncel parti) — osu!'ya aktarım için
Library/   kalıcı, tekilleştirilmiş .osz yedeği
data/      memory.db (SQLite, tek doğruluk kaynağı) + tracking.xlsx
logs/      app-YYYY-MM-DD.log + log_formats.md
config.json ayarlar
```

## Geliştirici olarak çalıştırma

```bash
pip install -r requirements.txt
python run.py
```

## Tek `.exe` olarak paketleme (son kullanıcı için)

Son kullanıcı hiçbir şey kurmaz; sadece `.exe`'yi çalıştırır.

```bash
pip install -r requirements-dev.txt
pyinstaller osu-archiver.spec
# çıktı: dist/osu-archiver.exe  (yayınlarken osu-archiver-<sürüm>.exe olarak adlandırın)
```

## Testler

```bash
python -m pytest tests/ -q
```

## Gelecek planları

- macOS desteği (aynı kod tabanı; PyInstaller macOS runner'da `.app`/`.dmg`).
- Ek diller ve temalar; ek pack serileri (ST/SC/T/L/P/A) otomatik desteklenir.
