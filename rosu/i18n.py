"""Minimal dictionary-based i18n for the user-facing UI (English default, Turkish).

Only strings the user sees are translated; logs, code and the Excel report stay
English by design. Add languages by extending each entry.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "app_title": {"en": "Rosu", "tr": "Rosu"},

    # Tabs
    "tab_dashboard": {"en": "Dashboard", "tr": "Panel"},
    "tab_search": {"en": "Search", "tr": "Müzik Ara"},
    "tab_packs": {"en": "Packs", "tr": "Arşivler"},
    "tab_logs": {"en": "Logs", "tr": "Loglar"},
    "tab_settings": {"en": "Settings", "tr": "Ayarlar"},

    # Dashboard
    "loaded_count": {"en": "Loaded archives: {n}", "tr": "Yüklü arşiv sayısı: {n}"},
    "btn_extract": {"en": "Unpack Archives", "tr": "Arşivleri Aç"},
    "btn_copy_library": {"en": "Copy to Library", "tr": "Library'e Kopyala"},
    "btn_import_osu": {"en": "Import to osu!", "tr": "osu!'ya Aktar"},
    "btn_refresh": {"en": "Refresh Library Data", "tr": "Arşiv Verisini Yenile"},
    "btn_rescan": {"en": "Rescan Packs", "tr": "Arşivleri Tara"},
    "col_code": {"en": "Code", "tr": "Kod"},
    "col_series": {"en": "Series", "tr": "Seri"},
    "col_title": {"en": "Title", "tr": "Başlık"},
    "col_size": {"en": "Size", "tr": "Boyut"},
    "col_state": {"en": "State", "tr": "Durum"},
    "state_new": {"en": "new", "tr": "yeni"},
    "state_known": {"en": "already added", "tr": "zaten eklenmiş"},
    "missing_banner": {"en": "Possibly missing: {items}", "tr": "Eksik olabilir: {items}"},
    "missing_show_link": {"en": "show these →", "tr": "bunları göster →"},
    "only_missing": {"en": "Only missing", "tr": "Sadece eksik"},
    "only_extra": {"en": "With extra files", "tr": "Ek dosyalı"},
    "extra_marker": {"en": "  ⚠ +{n} extra files", "tr": "  ⚠ +{n} ek dosya"},
    "no_missing": {"en": "No gaps detected.", "tr": "Boşluk bulunamadı."},
    "ready": {"en": "Ready.", "tr": "Hazır."},
    "working": {"en": "Working…", "tr": "Çalışıyor…"},
    "done": {"en": "Done.", "tr": "Tamamlandı."},

    # Toasts / results
    "extract_done": {"en": "Extracted {packs} packs, {tracks} tracks.",
                     "tr": "{packs} arşiv, {tracks} müzik çıkarıldı."},
    "library_done": {"en": "{new} added, {dup} duplicates — names saved to memory.",
                     "tr": "{new} eklendi, {dup} kopya ile karşılandı — isimler hafızaya eklendi."},
    "import_done": {"en": "Sent {files} beatmaps to osu! in {batches} batches.",
                    "tr": "{files} müzik {batches} partide osu!'ya gönderildi."},
    "refresh_done": {
        "en": "{added} added, {enriched} enriched, {disappeared} disappeared, {present} present.",
        "tr": "{added} eklendi, {enriched} zenginleştirildi, {disappeared} kayboldu, {present} mevcut."},
    "osu_not_found": {"en": "osu! executable not found. Set it in Settings.",
                      "tr": "osu! çalıştırılabilir dosyası bulunamadı. Ayarlar'dan belirtin."},
    "nothing_in_output": {"en": "Output is empty — unpack some archives first.",
                          "tr": "Output boş — önce arşiv açın."},

    # Empty Packs / external import (item 4)
    "packs_empty": {
        "en": "The Packs folder is empty. Add archives there and try again, or pick "
              "archive files to import now.",
        "tr": "Packs klasörü boş. Oraya arşiv ekleyip tekrar deneyin, ya da şimdi "
              "içe aktarmak için arşiv dosyaları seçin."},
    "btn_browse_archives": {"en": "Choose archives…", "tr": "Arşiv seç…"},
    "select_archives": {"en": "Select archives to import", "tr": "İçe aktarılacak arşivleri seç"},
    "imported_to_packs": {"en": "Copied {n} archive(s) into Packs.",
                          "tr": "{n} arşiv Packs klasörüne kopyalandı."},
    "file_missing": {
        "en": "File not found:\n{path}\n\nIt may not have been generated yet.",
        "tr": "Dosya bulunamadı:\n{path}\n\nHenüz oluşturulmamış olabilir."},

    # Re-add dialog
    "readd_title": {"en": "Archive already added", "tr": "Arşiv zaten eklenmiş"},
    "readd_all_present": {
        "en": "The archive '{code}' was already added and all of its beatmaps are "
              "already in your library. Extract it anyway?",
        "tr": "'{code}' arşivi daha önce eklenmişti ve tüm müzikleri zaten "
              "kütüphanede mevcut. Yine de çıkarmak ister misiniz?"},
    "readd_some_missing": {
        "en": "The archive '{code}' was added before, but {n} beatmap(s) are new or "
              "missing. Extract it anyway?",
        "tr": "'{code}' arşivi daha önce eklenmişti ama {n} müzik yeni/eksik. "
              "Yine de çıkarmak ister misiniz?"},
    "readd_apply_all": {"en": "Apply to all remaining", "tr": "Kalanların tümüne uygula"},
    "btn_extract_anyway": {"en": "Extract anyway", "tr": "Yine de çıkar"},
    "btn_skip": {"en": "Skip", "tr": "Atla"},

    # Search
    "search_placeholder": {"en": "Search artist, title or id…",
                           "tr": "Sanatçı, başlık veya id ara…"},
    "search_have": {"en": "You have this music ({n} match).",
                    "tr": "Bu müzik sizde yüklü ({n} eşleşme)."},
    "search_none": {"en": "Not found in your memory.", "tr": "Hafızanızda bulunamadı."},
    "browse_all": {"en": "Showing all {n} tracks in your library.",
                   "tr": "Kütüphanendeki {n} müzik listeleniyor."},
    "copy_names_action": {"en": "Copy names", "tr": "İsimleri kopyala"},
    "copy_table_action": {"en": "Copy as table (Ctrl+C)", "tr": "Tablo olarak kopyala (Ctrl+C)"},
    "col_name": {"en": "Name", "tr": "İsim"},
    "col_id": {"en": "ID", "tr": "ID"},
    "col_sources": {"en": "Sources", "tr": "Kaynaklar"},
    "col_first_seen": {"en": "First seen", "tr": "İlk görülme"},
    "col_attempts": {"en": "Copy attempts", "tr": "Kopya denemesi"},
    "col_lib_status": {"en": "Library", "tr": "Kütüphane"},

    # Settings
    "set_language": {"en": "Language", "tr": "Dil"},
    "set_theme": {"en": "Theme", "tr": "Tema"},
    "theme_dark": {"en": "Dark", "tr": "Koyu"},
    "theme_white": {"en": "White", "tr": "Beyaz"},
    "theme_pink": {"en": "Pink", "tr": "Pembe"},
    "set_paths": {"en": "Folders", "tr": "Klasörler"},
    "set_packs_dir": {"en": "Packs folder", "tr": "Packs klasörü"},
    "set_output_dir": {"en": "Output folder", "tr": "Output klasörü"},
    "set_library_dir": {"en": "Library folder", "tr": "Library klasörü"},
    "set_osu_exe": {"en": "osu! executable", "tr": "osu! çalıştırılabilir"},
    "set_physical_copy": {"en": "Keep physical .osz copies in Library",
                          "tr": "Library'de fiziksel .osz kopyası tut"},
    "set_clear_output_before": {"en": "Clear Output before each extraction",
                                "tr": "Her çıkarmadan önce Output'u temizle"},
    "set_clear_output_after": {"en": "Clear Output after importing to osu!",
                               "tr": "osu!'ya aktardıktan sonra Output'u temizle"},
    "set_zip_disposal": {"en": "Processed .zip action", "tr": "İşlenen .zip işlemi"},
    "zip_recycle": {"en": "Move to Recycle Bin", "tr": "Geri Dönüşüm Kutusu'na taşı"},
    "zip_move": {"en": "Move to Processed/", "tr": "Processed/ klasörüne taşı"},
    "zip_delete": {"en": "Delete permanently", "tr": "Kalıcı sil"},
    "btn_browse": {"en": "Browse…", "tr": "Gözat…"},
    "btn_save": {"en": "Save", "tr": "Kaydet"},
    "saved": {"en": "Settings saved.", "tr": "Ayarlar kaydedildi."},
    "open_formats": {"en": "Open log_formats.md", "tr": "log_formats.md dosyasını aç"},
    "open_excel": {"en": "Open Excel report", "tr": "Excel raporunu aç"},

    # Tabs (added)
    "tab_artists": {"en": "Artists", "tr": "Sanatçılar"},

    # Progress panel
    "extracting": {"en": "Unpacking archives…", "tr": "Arşivler açılıyor…"},
    "progress_of": {"en": "{done} / {total}", "tr": "{done} / {total}"},

    # Extra search / track columns
    "col_artist": {"en": "Artist", "tr": "Sanatçı"},
    "col_bpm": {"en": "BPM", "tr": "BPM"},
    "col_length": {"en": "Length", "tr": "Süre"},
    "col_mapper": {"en": "Mapper", "tr": "Mapper"},
    "col_mode": {"en": "Mode", "tr": "Mod"},
    "col_songs": {"en": "Songs", "tr": "Şarkı"},

    # Packs / artists
    "packs_search_placeholder": {"en": "Filter by code, title or category…",
                                 "tr": "Kod, başlık veya kategoriye göre süz…"},
    "sort_by": {"en": "Sort", "tr": "Sırala"},
    "sort_most": {"en": "Most songs", "tr": "En çok şarkı"},
    "sort_least": {"en": "Fewest songs", "tr": "En az şarkı"},
    "sort_len_long": {"en": "Longest average length", "tr": "En uzun ortalama süre"},
    "sort_len_short": {"en": "Shortest average length", "tr": "En kısa ortalama süre"},
    "sort_bpm_high": {"en": "Highest average BPM", "tr": "En yüksek ortalama BPM"},
    "sort_bpm_low": {"en": "Lowest average BPM", "tr": "En düşük ortalama BPM"},
    "col_avg_length": {"en": "Avg length", "tr": "Ort. süre"},
    "col_avg_bpm": {"en": "Avg BPM", "tr": "Ort. BPM"},
    "artist_songs": {"en": "{artist} — {n} songs", "tr": "{artist} — {n} şarkı"},
    "copy_hint": {"en": "Tip: click a cell to copy its name; Ctrl+C copies full rows.",
                  "tr": "İpucu: bir hücreye tıkla → ismi kopyalanır; Ctrl+C tüm satırları kopyalar."},

    # Import confirmation
    "import_confirm_title": {"en": "Import to osu!", "tr": "osu!'ya Aktar"},
    "import_confirm_body": {
        "en": "Send {files} beatmaps to osu! in {batches} batches?\n\nosu! imports "
              "them one by one in the background, so this can take a while "
              "(~{eta}). You can cancel dispatch at any time.",
        "tr": "{files} müzik {batches} partide osu!'ya gönderilsin mi?\n\nosu! bunları "
              "arka planda tek tek içe aktarır, bu yüzden biraz sürebilir "
              "(~{eta}). Gönderimi istediğin an iptal edebilirsin."},
    "btn_cancel": {"en": "Cancel", "tr": "İptal"},
    "import_cancelled": {"en": "Import cancelled ({sent}/{total} beatmaps sent).",
                         "tr": "Aktarım iptal edildi ({sent}/{total} müzik gönderildi)."},
    "import_dispatching": {"en": "Dispatching batch {batch}/{total}…",
                           "tr": "Parti gönderiliyor {batch}/{total}…"},
    "osu_keep_open": {
        "en": "Sent to osu!. osu! now imports the beatmaps in the background — "
              "please DON'T close osu! until it finishes. You can close this window.",
        "tr": "osu!'ya gönderildi. osu! müzikleri arka planda içe aktarıyor — işlem "
              "bitene kadar lütfen osu!'yu KAPATMAYIN. Bu pencereyi kapatabilirsiniz."},

    # Physical-copy delete confirmation (item 17)
    "physical_off_title": {"en": "Delete physical copies?",
                           "tr": "Fiziksel kopyalar silinsin mi?"},
    "physical_off_body": {
        "en": "You're turning off keeping physical .osz copies in Library. The .osz "
              "files currently in your Library will be moved to the Recycle Bin — "
              "their info stays in your memory. Are you sure?",
        "tr": "Library'de fiziksel .osz kopyası tutmayı kapatıyorsunuz. Library'deki "
              "mevcut .osz dosyaları Geri Dönüşüm Kutusu'na taşınacak — bilgileri "
              "hafızanızda kalır. Emin misiniz?"},
    "physical_off_confirm": {"en": "Delete files", "tr": "Dosyaları sil"},
    "physical_off_done": {"en": "Moved {n} .osz from Library to Recycle Bin (info kept).",
                          "tr": "{n} .osz Library'den Geri Dönüşüm Kutusu'na taşındı (bilgiler korundu)."},

    # Auto-import from installed osu! clients (item 15)
    "set_import": {"en": "Import installed songs", "tr": "Yüklü şarkıları içe aktar"},
    "set_import_help": {
        "en": "Pull the beatmaps already installed in your osu! client straight into "
              "your library (dedup is automatic). osu!lazer export bundles a helper — "
              "close osu!lazer first for best results.",
        "tr": "osu! istemcinde zaten yüklü beatmap'leri doğrudan kütüphanene çeker "
              "(tekilleştirme otomatik). osu!lazer için en iyi sonuç için önce "
              "osu!lazer'ı kapat."},
    "btn_import_stable": {"en": "From osu!(stable)", "tr": "osu!(stable)'dan"},
    "btn_import_lazer": {"en": "From osu!lazer", "tr": "osu!lazer'dan"},
    "import_client_result": {"en": "{client}: {new} added, {dup} already had.",
                             "tr": "{client}: {new} eklendi, {dup} zaten vardı."},
    "import_client_none": {"en": "{client} not found on this PC.",
                           "tr": "{client} bu bilgisayarda bulunamadı."},
    "import_lazer_error": {
        "en": "Couldn't read osu!lazer. Close osu!lazer and try again.",
        "tr": "osu!lazer okunamadı. osu!lazer'ı kapatıp tekrar deneyin."},

    # Settings additions
    "set_auto_backup": {"en": "Auto-copy to Library after unpacking",
                        "tr": "Açtıktan sonra otomatik Library'e kopyala"},
    "set_osu_api": {"en": "osu! API (optional, for accurate missing detection)",
                    "tr": "osu! API (opsiyonel, doğru eksik tespiti için)"},
    "set_client_id": {"en": "Client ID", "tr": "Client ID"},
    "set_client_secret": {"en": "Client Secret", "tr": "Client Secret"},
    "btn_update_reference": {"en": "Update reference from osu!",
                             "tr": "osu!'dan referansı güncelle"},
    "reference_status": {"en": "Reference: {n} packs ({when})",
                         "tr": "Referans: {n} paket ({when})"},
    "reference_none": {"en": "Reference: not synced (only Standard gaps shown)",
                       "tr": "Referans: yok (yalnız Standard boşlukları gösterilir)"},
    "reference_done": {"en": "Reference updated: {n} packs.",
                       "tr": "Referans güncellendi: {n} paket."},
    "reference_help": {
        "en": "Register an OAuth app at osu.ppy.sh/home/account/edit → paste the "
              "Client ID + Secret, then update. Lets us flag genuinely missing "
              "Featured/Spotlight/etc. packs.",
        "tr": "osu.ppy.sh/home/account/edit → OAuth uygulaması aç, Client ID + Secret'i "
              "buraya yapıştır ve güncelle. Featured/Spotlight vb. gerçekten eksik "
              "paketleri işaretlememizi sağlar."},

    # Folder self-heal (item 20)
    "path_heal_title": {"en": "Folder location changed",
                        "tr": "Klasör konumu değişti"},
    "path_heal_body": {
        "en": "The folders saved in your settings were not found at their old "
              "location. The app is now running from:\n\n{base}\n\nThe folders "
              "below were found here. Set these as the new locations?\n\n{changes}",
        "tr": "Ayarlarda kayıtlı klasörler eski konumlarında bulunamadı. Uygulama "
              "şu an şuradan çalışıyor:\n\n{base}\n\nAşağıdaki klasörler burada "
              "bulundu. Bunları yeni konum olarak ayarlayayım mı?\n\n{changes}"},
    "path_heal_apply": {"en": "Use these locations", "tr": "Bu konumları kullan"},
    "path_heal_keep": {"en": "Keep old settings", "tr": "Eski ayarları koru"},
    "path_heal_applied": {"en": "Folder locations updated to this folder.",
                          "tr": "Klasör konumları bu klasöre göre güncellendi."},

    # Theme display names
    "theme_pink-white": {"en": "Pink · Light", "tr": "Pembe · Açık"},
    "theme_pink-dark": {"en": "Pink · Dark", "tr": "Pembe · Koyu"},
    "theme_pink-darker": {"en": "Pink · Darker", "tr": "Pembe · Daha Koyu"},
    "theme_nord": {"en": "Nord", "tr": "Nord"},
    "theme_dracula": {"en": "Dracula", "tr": "Dracula"},
    "theme_catppuccin-mocha": {"en": "Catppuccin Mocha", "tr": "Catppuccin Mocha"},
    "theme_catppuccin-latte": {"en": "Catppuccin Latte", "tr": "Catppuccin Latte"},
    "theme_solarized-dark": {"en": "Solarized Dark", "tr": "Solarized Koyu"},
    "theme_solarized-light": {"en": "Solarized Light", "tr": "Solarized Açık"},
}


def human_duration(seconds: int | None) -> str:
    if not seconds or seconds < 0:
        return ""
    m, s = divmod(int(seconds), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}h {m}m"
    return f"{m}:{s:02d}"


class I18N:
    def __init__(self, lang: str = "en"):
        self.lang = lang if lang in ("en", "tr") else "en"

    def set_language(self, lang: str) -> None:
        self.lang = lang if lang in ("en", "tr") else "en"

    def t(self, key: str, **kwargs) -> str:
        entry = STRINGS.get(key, {})
        text = entry.get(self.lang) or entry.get("en") or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text
