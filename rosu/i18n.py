# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal dictionary-based i18n for the user-facing UI (English default, Turkish).

Only strings the user sees are translated; logs, code and the Excel report stay
English by design. Add languages by extending each entry.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "app_title": {"en": "Rosu", "tr": "Rosu"},
    "op_running_quit": {
        "en": "An operation is still running (import / Drive upload). Cancel it "
              "and quit Rosu?",
        "tr": "Bir işlem hâlâ sürüyor (içe aktarma / Drive yükleme). İptal edip "
              "Rosu'dan çıkılsın mı?"},

    # Tabs
    "tab_dashboard": {"en": "Dashboard", "tr": "Panel"},
    "tab_search": {"en": "Search", "tr": "Müzik Ara"},
    "tab_packs": {"en": "Packs", "tr": "Arşivler"},
    "tab_logs": {"en": "Logs", "tr": "Loglar"},
    "tab_settings": {"en": "Settings", "tr": "Ayarlar"},

    # Dashboard
    "loaded_count": {"en": "Loaded archives: {n}", "tr": "Yüklü arşiv sayısı: {n}"},
    "output_count": {"en": "Unpacked beatmaps in Output: {n}",
                     "tr": "Output'taki çıkarılmış müzik: {n}"},
    "btn_extract": {"en": "Unpack Archives", "tr": "Arşivleri Aç"},
    "btn_copy_library": {"en": "Copy to Library", "tr": "Library'e Kopyala"},
    "btn_import_osu": {"en": "Import to osu!", "tr": "osu!'ya Aktar"},
    "btn_import_to_lazer": {"en": "Import → osu!lazer", "tr": "osu!lazer'a Aktar"},
    "btn_import_to_stable": {"en": "Import → osu!(stable)", "tr": "osu!(stable)'a Aktar"},
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
    "missing_banner_sure": {"en": "Missing: {items}", "tr": "Eksik: {items}"},
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
    "loose_done": {"en": "Moved {n} loose beatmap(s) straight to Output (Direct).",
                   "tr": "{n} arşivsiz müzik doğrudan Output'a taşındı (Direct)."},
    "library_done": {"en": "{new} added, {dup} duplicates — names saved to memory.",
                     "tr": "{new} eklendi, {dup} kopya ile karşılandı — isimler hafızaya eklendi."},
    "library_all_present": {
        "en": "All {n} beatmaps are already in your Library — nothing to copy.",
        "tr": "{n} müziğin tamamı zaten kütüphanende — kopyalanacak bir şey yok."},
    "import_done": {"en": "Sent {files} beatmaps to osu! in {batches} batches.",
                    "tr": "{files} müzik {batches} partide osu!'ya gönderildi."},
    "refresh_done": {
        "en": "{added} added, {enriched} enriched, {disappeared} disappeared, {present} present.",
        "tr": "{added} eklendi, {enriched} zenginleştirildi, {disappeared} kayboldu, {present} mevcut."},
    "osu_not_found": {"en": "osu! executable not found. Set it in Settings.",
                      "tr": "osu! çalıştırılabilir dosyası bulunamadı. Ayarlar'dan belirtin."},
    "import_no_lazer_exe": {
        "en": "osu!lazer executable not found. Set its path in Settings.",
        "tr": "osu!lazer çalıştırılabilir dosyası bulunamadı. Yolunu Ayarlar'dan belirtin."},
    "import_no_stable_exe": {
        "en": "osu!(stable) executable not found. Set its path in Settings.",
        "tr": "osu!(stable) çalıştırılabilir dosyası bulunamadı. Yolunu Ayarlar'dan belirtin."},
    "nothing_in_output": {"en": "Output is empty — unpack some archives first.",
                          "tr": "Output boş — önce arşiv açın."},

    # Archive security — rejected (zip-bomb / path-traversal) packs
    "archive_rejected": {
        "en": "⚠ {n} unsafe archive(s) rejected and moved to Quarantine.",
        "tr": "⚠ {n} güvensiz arşiv reddedildi ve Karantina'ya taşındı."},
    "archive_rejected_title": {"en": "Unsafe archive rejected",
                               "tr": "Güvensiz arşiv reddedildi"},
    "archive_rejected_body": {
        "en": "These archives were refused as potentially malicious and moved to "
              "the Quarantine folder (not deleted):\n\n{items}",
        "tr": "Bu arşivler kötü amaçlı olabileceği için reddedildi ve Karantina "
              "klasörüne taşındı (silinmedi):\n\n{items}"},
    "archive_reason_total": {"en": "too large", "tr": "çok büyük"},
    "archive_reason_entries": {"en": "too many files", "tr": "çok fazla dosya"},
    "archive_reason_ratio": {"en": "suspicious compression", "tr": "şüpheli sıkıştırma"},
    "archive_reason_path": {"en": "unsafe file path", "tr": "güvensiz dosya yolu"},
    "archive_reason_unsafe": {"en": "unsafe", "tr": "güvensiz"},
    "archive_not_moved": {"en": "(could not move — left in place)",
                          "tr": "(taşınamadı — yerinde bırakıldı)"},

    # Empty Packs / external import (item 4)
    "packs_empty": {
        "en": "The Packs folder is empty. Add archives there and try again, or pick "
              "archive files to import now.",
        "tr": "Packs klasörü boş. Oraya arşiv ekleyip tekrar deneyin, ya da şimdi "
              "içe aktarmak için arşiv dosyaları seçin."},
    "btn_browse_archives": {"en": "Choose archives…", "tr": "Arşiv seç…"},
    "btn_purge_known": {"en": "Remove already-added", "tr": "Eklenmişleri kaldır"},
    "tip_purge_known": {
        "en": "Recycle / move / delete the archives already in your library "
              "(uses your 'Processed .zip action' setting).",
        "tr": "Zaten kütüphanende olan arşivleri geri dönüşüme taşı / sil "
              "('İşlenen .zip işlemi' ayarını kullanır)."},
    "purge_known_confirm": {
        "en": "Remove {n} already-added archive(s) from Packs? Uses your "
              "'Processed .zip action' setting (Recycle Bin by default).",
        "tr": "{n} çoktan eklenmiş arşiv Packs'ten kaldırılsın mı? 'İşlenen .zip "
              "işlemi' ayarını kullanır (varsayılan: Geri Dönüşüm Kutusu)."},
    "purge_known_done": {"en": "Removed {n} already-added archive(s).",
                         "tr": "{n} çoktan eklenmiş arşiv kaldırıldı."},
    "btn_clear_output": {"en": "Clear Output", "tr": "Output'u Temizle"},
    "tip_clear_output": {
        "en": "Send the .osz still in Output to the Recycle Bin — they're already "
              "in your Library and imported into osu!.",
        "tr": "Output'ta kalan .osz dosyalarını Geri Dönüşüm Kutusu'na gönder — "
              "zaten Library'nde ve osu!'ya aktarılmış durumdalar."},
    "clear_output_confirm": {
        "en": "Move {n} file(s) from Output to the Recycle Bin? They're already "
              "backed up in your Library and imported into osu!.",
        "tr": "{n} dosya Output'tan Geri Dönüşüm Kutusu'na taşınsın mı? Zaten "
              "Library'nde yedekli ve osu!'ya aktarılmış durumdalar."},
    "clear_output_done": {"en": "Cleared {n} file(s) from Output.",
                          "tr": "Output'tan {n} dosya temizlendi."},
    "nothing_to_unpack": {
        "en": "Nothing new to unpack — everything in Packs is already added. "
              "Choose archives to import, or use 'Remove already-added'.",
        "tr": "Açılacak yeni bir şey yok — Packs'teki her şey zaten eklenmiş. "
              "İçe aktarmak için arşiv seç, ya da 'Eklenmişleri kaldır'ı kullan."},
    "select_archives": {"en": "Select archives to import", "tr": "İçe aktarılacak arşivleri seç"},
    "imported_to_packs": {"en": "Moved {n} archive(s) into Packs.",
                          "tr": "{n} arşiv Packs klasörüne taşındı."},
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
    "search_tags_toggle": {"en": "Also search tags / mapper",
                           "tr": "Etiketlerde / haritacıda da ara"},
    # -- v1.6: visual filters panel ------------------------------------------
    "filters_panel": {"en": "Filters", "tr": "Filtreler"},
    "filters_clear": {"en": "Clear filters", "tr": "Filtreleri temizle"},
    "filters_mode": {"en": "Mode", "tr": "Mod"},
    "filters_star": {"en": "Star", "tr": "Yıldız"},
    "filters_keys": {"en": "Keys (mania)", "tr": "Tuş (mania)"},
    "filters_bpm": {"en": "BPM", "tr": "BPM"},
    "filters_length": {"en": "Length", "tr": "Süre"},
    "filters_arod": {"en": "AR / OD", "tr": "AR / OD"},
    "filters_min": {"en": "min", "tr": "en az"},
    "filters_max": {"en": "max", "tr": "en çok"},
    "filters_mode_have": {"en": "{mode} — {n} set(s) in your Library",
                          "tr": "{mode} — kütüphanende {n} set"},
    "filters_mode_none": {"en": "No {mode} maps in your Library",
                          "tr": "Kütüphanende hiç {mode} haritası yok"},
    "artist_filter_placeholder": {"en": "Filter artists…",
                                  "tr": "Sanatçı süz…"},
    "btn_reload": {"en": "Refresh", "tr": "Yenile"},
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
    "set_osu_lazer_exe": {"en": "osu!lazer executable", "tr": "osu!lazer çalıştırılabilir"},
    "set_osu_stable_exe": {"en": "osu!(stable) executable", "tr": "osu!(stable) çalıştırılabilir"},
    "set_physical_copy": {"en": "Keep physical .osz copies in Library",
                          "tr": "Library'de fiziksel .osz kopyası tut"},
    "set_clear_output_before": {"en": "Clear Output before each extraction",
                                "tr": "Her çıkarmadan önce Output'u temizle"},
    "set_clear_output_after": {"en": "Clear Output after importing to osu!",
                               "tr": "osu!'ya aktardıktan sonra Output'u temizle"},
    "set_check_updates": {"en": "Check for updates on startup",
                          "tr": "Başlangıçta güncellemeleri denetle"},
    "update_available": {"en": "Rosu {tag} is available.",
                         "tr": "Rosu {tag} yayınlandı."},
    "update_open": {"en": "Download", "tr": "İndir"},
    "set_zip_disposal": {"en": "Processed .zip action", "tr": "İşlenen .zip işlemi"},
    "zip_recycle": {"en": "Move to Recycle Bin", "tr": "Geri Dönüşüm Kutusu'na taşı"},
    "zip_move": {"en": "Move to Processed/", "tr": "Processed/ klasörüne taşı"},
    "zip_delete": {"en": "Delete permanently", "tr": "Kalıcı sil"},
    "zip_drive": {"en": "Upload to Drive & remove locally",
                  "tr": "Drive'a yükle & lokalden kaldır"},
    "btn_browse": {"en": "Browse…", "tr": "Gözat…"},
    "btn_save": {"en": "Save", "tr": "Kaydet"},
    "saved": {"en": "Settings saved.", "tr": "Ayarlar kaydedildi."},

    # Unsaved-changes guard (items 11 & 18)
    "unsaved_title": {"en": "Unsaved changes", "tr": "Kaydedilmemiş değişiklikler"},
    "unsaved_body": {
        "en": "You changed some settings but didn't save them. Save your changes "
              "before leaving? (Tip: Ctrl+S saves.)",
        "tr": "Bazı ayarları değiştirdiniz ama kaydetmediniz. Ayrılmadan önce "
              "kaydedilsin mi? (İpucu: Ctrl+S kaydeder.)"},
    "btn_save_now": {"en": "Save", "tr": "Kaydet"},
    "btn_discard": {"en": "Discard", "tr": "Vazgeç"},
    "settings_save_failed": {"en": "Couldn't save settings: {err}",
                             "tr": "Ayarlar kaydedilemedi: {err}"},
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
    "col_star": {"en": "Star", "tr": "Yıldız"},
    "col_keys": {"en": "Keys", "tr": "Tuş"},
    "col_avg_star": {"en": "Avg ★", "tr": "Ort. ★"},
    "col_version": {"en": "Difficulty", "tr": "Zorluk"},
    "col_cs": {"en": "CS", "tr": "CS"},
    "col_ar": {"en": "AR", "tr": "AR"},
    "col_od": {"en": "OD", "tr": "OD"},
    "col_hp": {"en": "HP", "tr": "HP"},
    "col_skill": {"en": "Skill", "tr": "Beceri"},
    "map_details_title": {"en": "Map details", "tr": "Map detayları"},
    "map_details_skillset": {"en": "Rosu Skillset Rating (mania)",
                             "tr": "Rosu Beceri Puanı (mania)"},
    "map_details_skill_of": {
        "en": "{version} — overall {overall}",
        "tr": "{version} — genel {overall}"},
    "tip_col_skill": {
        "en": "Rosu Skillset Rating — our in-house mania skillset estimate "
              "(overall). Double-click / select a mania difficulty to see its "
              "stream / jack / chordjack / tech breakdown on the radar.",
        "tr": "Rosu Beceri Puanı — mania için kendi beceri tahminimiz (genel). "
              "Radarda stream / jack / chordjack / tech dağılımını görmek için bir "
              "mania zorluğunu seçin."},
    "map_details_mapper": {"en": "Mapper: {mapper}", "tr": "Mapper: {mapper}"},
    "map_details_status": {"en": "Status: {status}", "tr": "Durum: {status}"},
    "map_details_plays": {"en": "{n} plays", "tr": "{n} oynanma"},
    "map_details_favs": {"en": "{n} favourites", "tr": "{n} favori"},
    "map_details_ranked_on": {"en": "ranked {d}", "tr": "ranked {d}"},
    "map_details_no_enrich": {
        "en": "Ranked status, dates & play counts appear here once you run "
              "“Enrich from osu! API” in Settings.",
        "tr": "Ranked durumu, tarihler ve oynanma sayıları, Ayarlar’dan "
              "“osu! API’den Zenginleştir”i çalıştırınca burada görünür."},
    "tip_col_version": {"en": "Difficulty name.", "tr": "Zorluk adı."},
    "tip_col_mode": {"en": "Game mode (osu! / taiko / catch / mania).",
                     "tr": "Oyun modu (osu! / taiko / catch / mania)."},
    "tip_col_keys": {"en": "Key count — number of columns in a mania chart.",
                     "tr": "Tuş sayısı — bir mania haritasındaki kolon sayısı."},
    "tip_col_star": {"en": "Star rating — the difficulty's overall hardness.",
                     "tr": "Yıldız derecesi — zorluğun genel zorluk seviyesi."},
    "tip_col_cs": {
        "en": "CS — Circle Size: smaller circles in osu!, and the key count in mania.",
        "tr": "CS — Circle Size: osu!'da daire boyutu, mania'da tuş sayısı."},
    "tip_col_ar": {
        "en": "AR — Approach Rate: how fast the approach circles/notes appear.",
        "tr": "AR — Approach Rate: yaklaşma çemberlerinin/notaların ne kadar hızlı geldiği."},
    "tip_col_od": {
        "en": "OD — Overall Difficulty: how strict the hit timing / accuracy is.",
        "tr": "OD — Overall Difficulty: vuruş zamanlaması / isabet ne kadar sıkı."},
    "tip_col_hp": {
        "en": "HP — HP Drain: how fast health drains and how punishing misses are.",
        "tr": "HP — HP Drain: canın ne kadar hızlı azaldığı ve ıskaların cezası."},
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
    "sort_star_high": {"en": "Highest average star", "tr": "En yüksek ortalama yıldız"},
    "sort_star_low": {"en": "Lowest average star", "tr": "En düşük ortalama yıldız"},
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
    "set_library_section": {"en": "Library", "tr": "Kütüphane"},
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
    "btn_scan_lost": {"en": "Scan for lost maps", "tr": "Kayıp haritaları tara"},
    "lost_maps_needs_api": {
        "en": "Enter your osu! API credentials above first, then scan.",
        "tr": "Önce yukarıdan osu! API bilgilerinizi girin, sonra tarayın."},
    "lost_maps_result": {
        "en": "Checked {checked}, {gone} no longer on osu!.",
        "tr": "{checked} kontrol edildi, {gone} tanesi artık osu!'da yok."},
    "lost_maps_result_more": {
        "en": "Checked {checked} sets this run — {gone} no longer on osu!. "
              "{remaining} sets not checked yet: run the scan again to continue "
              "(it works in batches of 500 to respect osu!'s API limits).",
        "tr": "Bu turda {checked} set kontrol edildi — {gone} tanesi artık "
              "osu!'da yok. {remaining} set henüz kontrol edilmedi: devam etmek "
              "için taramayı tekrar çalıştır (osu! API limitlerine uymak için "
              "500'erlik gruplar hâlinde çalışır)."},
    "lost_maps_result_all": {
        "en": "All {total} sets in the Library have been checked — {gone} in "
              "this run no longer on osu!.",
        "tr": "Kütüphanedeki {total} setin tümü kontrol edildi — bu turda "
              "{gone} tanesi artık osu!'da yok."},
    "lost_maps_count": {"en": "{n} beatmap(s) no longer on osu!.",
                        "tr": "{n} müzik artık osu!'da yok."},
    "reference_help": {
        "en": "Optional — for accurate gap detection. Open "
              "<a href='https://osu.ppy.sh/home/account/edit#oauth'>"
              "osu.ppy.sh/home/account/edit</a> → <b>New OAuth Application</b> → "
              "Application Name: anything (e.g. Rosu), Callback URL: "
              "<b>http://localhost</b> → Register. Copy the shown Client ID + Client "
              "Secret into the two boxes below, then Update. (These are YOUR keys; "
              "Rosu can't fill them in for you.)",
        "tr": "İsteğe bağlı — daha doğru boşluk tespiti için. "
              "<a href='https://osu.ppy.sh/home/account/edit#oauth'>"
              "osu.ppy.sh/home/account/edit</a> → <b>New OAuth Application</b> → "
              "Uygulama Adı: herhangi bir şey (ör. Rosu), Geri Çağırma URL'si: "
              "<b>http://localhost</b> → Kaydet. Görünen Client ID + Client Secret'i "
              "aşağıdaki iki kutuya yapıştır ve Güncelle. (Bunlar SENİN anahtarların; "
              "Rosu senin yerine dolduramaz.)"},

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

    # Google Drive backup (item 11, v0.8)
    "col_location": {"en": "Where", "tr": "Konum"},
    "where_legend": {
        "en": "🎮 osu!lazer   🕹️ osu!(stable)   💾 Library   ☁️ Drive backup",
        "tr": "🎮 osu!lazer   🕹️ osu!(stable)   💾 Library   ☁️ Drive yedeği"},
    "btn_about": {"en": "About / Licenses", "tr": "Hakkında / Lisanslar"},
    "tip_about": {"en": "App version, license, and third-party notices.",
                  "tr": "Uygulama sürümü, lisansı ve üçüncü taraf bildirimleri."},
    "about_title": {"en": "About Rosu", "tr": "Rosu Hakkında"},
    "about_license": {
        "en": "Rosu is free software, licensed under the "
              "<a href='https://www.gnu.org/licenses/gpl-3.0.html'>GNU GPL v3.0 or "
              "later</a>. It comes with ABSOLUTELY NO WARRANTY.<br>"
              "© 2026 Halil Şafak Şimşek — an unofficial, fan-made tool, not "
              "affiliated with or endorsed by ppy Pty Ltd or osu!.",
        "tr": "Rosu özgür bir yazılımdır; "
              "<a href='https://www.gnu.org/licenses/gpl-3.0.html'>GNU GPL v3.0 veya "
              "sonrası</a> ile lisanslanmıştır. HİÇBİR GARANTİSİ YOKTUR.<br>"
              "© 2026 Halil Şafak Şimşek — gayriresmî, hayran yapımı bir araçtır; "
              "ppy Pty Ltd veya osu! ile bağlantılı ya da onaylı değildir."},
    "about_legal": {
        "en": "<a href='https://rosu-web.vercel.app/privacy'>Privacy Policy</a> · "
              "<a href='https://rosu-web.vercel.app/terms'>Terms</a>",
        "tr": "<a href='https://rosu-web.vercel.app/privacy'>Gizlilik Politikası</a> · "
              "<a href='https://rosu-web.vercel.app/terms'>Şartlar</a>"},
    "about_contact": {
        "en": "Prefer e-mail? Reach us at rosu.app@gmail.com (select and copy it).",
        "tr": "E-postayı mı tercih edersin? rosu.app@gmail.com adresinden "
              "ulaşabilirsin (seçip kopyalayabilirsin)."},
    "about_social": {
        "en": "Follow Rosu: "
              "<a href='https://www.instagram.com/rosu.app/'>Instagram</a> · "
              "<a href='https://www.youtube.com/@RosuApp'>YouTube</a> · "
              "<a href='https://www.reddit.com/user/RosuApp/'>Reddit</a> · "
              "<a href='https://x.com/RosuApp'>X</a>",
        "tr": "Rosu'yu takip et: "
              "<a href='https://www.instagram.com/rosu.app/'>Instagram</a> · "
              "<a href='https://www.youtube.com/@RosuApp'>YouTube</a> · "
              "<a href='https://www.reddit.com/user/RosuApp/'>Reddit</a> · "
              "<a href='https://x.com/RosuApp'>X</a>"},
    "about_website": {
        "en": "Website: <a href='https://rosu-web.vercel.app'>rosu-web</a>",
        "tr": "Web sitesi: <a href='https://rosu-web.vercel.app'>rosu-web</a>"},
    "about_third_party": {"en": "Bundled third-party components:",
                          "tr": "Paketlenmiş üçüncü taraf bileşenleri:"},
    "about_third_party_missing": {
        "en": "Third-party license notices file was not found.",
        "tr": "Üçüncü taraf lisans bildirimleri dosyası bulunamadı."},
    "set_drive": {"en": "Google Drive backup", "tr": "Google Drive yedeği"},
    "set_drive_help": {
        "en": "Log in once to back up your Library to Google Drive as bundled "
              "archives, and restore it on another PC. Rosu can only see the files "
              "it creates (drive.file scope) — never the rest of your Drive.",
        "tr": "Kütüphaneni paketlenmiş arşivler halinde Google Drive'a yedeklemek ve "
              "başka bir bilgisayarda geri yüklemek için bir kez giriş yap. Rosu "
              "yalnızca kendi oluşturduğu dosyaları görebilir (drive.file) — "
              "Drive'ının geri kalanını asla."},
    "btn_drive_connect": {"en": "Connect Google Drive", "tr": "Google Drive'a Bağlan"},
    "btn_drive_disconnect": {"en": "Disconnect", "tr": "Bağlantıyı Kes"},
    "drive_connected": {"en": "Connected.", "tr": "Bağlı."},
    "drive_disconnected": {"en": "Not connected.", "tr": "Bağlı değil."},
    "drive_disconnected_done": {"en": "✓ Disconnected from Google Drive.",
                                "tr": "✓ Google Drive bağlantısı kesildi."},
    "drive_connecting": {"en": "Opening browser for Google sign-in…",
                         "tr": "Google girişi için tarayıcı açılıyor…"},
    "drive_not_configured": {
        "en": "Google Drive is not available in this build (no OAuth client).",
        "tr": "Bu sürümde Google Drive kullanılamıyor (OAuth istemcisi yok)."},
    "drive_no_keyring": {
        "en": "Needs the 'keyring' package to store your login "
              "(pip install -r requirements.txt).",
        "tr": "Girişini saklamak için 'keyring' paketi gerekli "
              "(pip install -r requirements.txt)."},
    "drive_login_failed": {"en": "Google sign-in failed or was cancelled.",
                           "tr": "Google girişi başarısız oldu veya iptal edildi."},
    "btn_backup_drive": {"en": "Back up to Drive", "tr": "Drive'a Yedekle"},

    # Library Health (v1.1)
    "btn_library_health": {"en": "Library Health", "tr": "Kütüphane Sağlığı"},
    # -- v1.6: Mania skillset (Rosu Skillset Rating) --------------------------
    "btn_compute_msd": {"en": "Compute Skillset Ratings (mania)",
                        "tr": "Beceri Puanlarını Hesapla (mania)"},
    "tip_compute_msd": {
        "en": "Estimate each mania difficulty's Rosu Skillset Rating (stream, jack, "
              "chordjack, stamina, tech…) locally for the whole Library. Pure, "
              "offline — no engine or internet needed.",
        "tr": "Kütüphanedeki her mania zorluğu için Rosu Beceri Puanını (stream, jack, "
              "chordjack, stamina, tech…) yerel olarak tahmin et. Tamamen çevrimdışı — "
              "motor veya internet gerekmez."},
    "msd_no_library": {
        "en": "Your Library is empty — add some beatmaps first.",
        "tr": "Kütüphanen boş — önce birkaç beatmap ekle."},
    "msd_done": {
        "en": "Skillset ratings: {rated} mania sets rated, {scanned} scanned, "
              "{remaining} remaining.",
        "tr": "Beceri puanları: {rated} mania set derecelendirildi, {scanned} tarandı, "
              "{remaining} kaldı."},
    # -- v1.5: star ratings (rosu-pp) + osu! API metadata enrichment ----------
    "btn_compute_ratings": {"en": "Compute Star Ratings",
                            "tr": "Yıldız Derecelerini Hesapla"},
    "tip_compute_ratings": {
        "en": "Compute star ratings for every Library difficulty locally (rosu-pp).",
        "tr": "Kütüphanedeki her zorluk için yıldız derecelerini yerel olarak hesapla (rosu-pp)."},
    "btn_enrich_api": {"en": "Enrich from osu! API", "tr": "osu! API’den Zenginleştir"},
    "tip_enrich_api": {
        "en": "Fetch ranked status, dates, play/favourite counts, genre & language "
              "from the osu! API.",
        "tr": "osu! API’den ranked durumu, tarihler, oynanma/favori sayıları, tür "
              "ve dil bilgisini çek."},
    "tip_enrich_disabled": {
        "en": "Enable “Fetch metadata from the osu! API” in Settings first.",
        "tr": "Önce Ayarlar’dan “osu! API’den meta veri çek”i etkinleştir."},
    "ratings_no_engine": {"en": "rosu-pp not available — no local star ratings.",
                          "tr": "rosu-pp yok — yerel yıldız derecesi hesaplanamadı."},
    "ratings_no_engine_msg": {
        "en": "The rosu-pp difficulty engine isn't installed, so star ratings can't "
              "be computed locally. Difficulty data (key count, mode, CS/AR/OD/HP) is "
              "still recorded, and the osu! API can fill in star ratings via "
              "“Enrich from osu! API”.",
        "tr": "rosu-pp zorluk motoru kurulu değil, bu yüzden yıldız dereceleri yerel "
              "olarak hesaplanamıyor. Zorluk verileri (tuş sayısı, mod, CS/AR/OD/HP) "
              "yine de kaydedilir; yıldız dereceleri “osu! API’den Zenginleştir” ile "
              "doldurulabilir."},
    "ratings_done": {"en": "Star ratings: {scanned} sets scanned, {rated} rated.",
                     "tr": "Yıldız dereceleri: {scanned} set tarandı, {rated} derecelendirildi."},
    "ratings_title": {"en": "Star Ratings", "tr": "Yıldız Dereceleri"},
    "ratings_summary": {
        "en": "Scanned {scanned} sets · {rated} rated · {remaining} remaining.",
        "tr": "{scanned} set tarandı · {rated} derecelendirildi · {remaining} kaldı."},
    "ratings_cancelled": {
        "en": "Cancelled — run again to continue where it left off.",
        "tr": "İptal edildi — kaldığı yerden devam etmek için tekrar çalıştır."},
    "ratings_distribution": {"en": "Library star distribution",
                             "tr": "Kütüphane yıldız dağılımı"},
    "enrich_progress": {"en": "Enriching from osu! API… {done}/{total}",
                        "tr": "osu! API’den zenginleştiriliyor… {done}/{total}"},
    "enrich_disabled": {"en": "osu! API enrichment is off",
                        "tr": "osu! API zenginleştirmesi kapalı"},
    "enrich_disabled_msg": {
        "en": "Enable “Fetch metadata from the osu! API” in Settings to use this.",
        "tr": "Bunu kullanmak için Ayarlar’dan “osu! API’den meta veri çek”i etkinleştir."},
    "enrich_no_api": {"en": "osu! API credentials needed",
                      "tr": "osu! API kimlik bilgileri gerekli"},
    "enrich_no_api_msg": {
        "en": "Add your osu! API client id and secret in Settings to enrich metadata.",
        "tr": "Meta veriyi zenginleştirmek için Ayarlar’a osu! API istemci kimliğini "
              "ve gizli anahtarını ekle."},
    "enrich_done": {
        "en": "Enriched {updated} of {checked} sets · {remaining} remaining.",
        "tr": "{checked} setten {updated} tanesi zenginleştirildi · {remaining} kaldı."},
    "set_enrich_api": {
        "en": "Fetch metadata from the osu! API (ranked status, dates, play counts)",
        "tr": "osu! API’den meta veri çek (ranked durumu, tarihler, oynanma sayıları)"},
    "btn_star_dist": {"en": "★ Distribution", "tr": "★ Dağılımı"},
    "tip_star_dist": {"en": "Show the star-rating distribution of the current results.",
                      "tr": "Mevcut sonuçların yıldız derecesi dağılımını göster."},
    "star_dist_title": {"en": "Star distribution", "tr": "Yıldız dağılımı"},
    "star_dist_head": {"en": "{n} rated sets in the current results",
                       "tr": "Mevcut sonuçlarda {n} derecelendirilmiş set"},
    "star_dist_hint": {
        "en": "Click a bar to select it (drag across bars for a range); "
              "double-click a bar to search that range.",
        "tr": "Bir çubuğa tıklayıp seç (aralık için çubuklar üzerinde sürükle); "
              "bir çubuğa çift tıklayınca o aralık aratılır."},
    "star_dist_selected": {
        "en": "{lo}★–{hi}★ · {count} sets ({pct}% of these results)",
        "tr": "{lo}★–{hi}★ · {count} set (bu sonuçların %{pct}'i)"},
    "star_dist_search": {"en": "Search this range", "tr": "Bu aralığı ara"},
    "star_dist_export": {"en": "Export this range", "tr": "Bu aralığı dışa aktar"},
    "star_dist_empty": {
        "en": "No star ratings in the current results yet.",
        "tr": "Mevcut sonuçlarda henüz yıldız derecesi yok."},
    "star_dist_no_library": {
        "en": "Your Library is empty — add some music first, then star ratings can "
              "be computed.",
        "tr": "Kütüphanen boş — önce müzik ekle, sonra yıldız dereceleri hesaplanabilir."},
    "star_dist_scan_prompt": {
        "en": "{n} set(s) don't have a star rating yet. Scan them now to determine "
              "their star values?",
        "tr": "{n} setin henüz yıldız derecesi yok. Yıldız değerlerini belirlemek "
              "için şimdi taransın mı?"},
    "ratings_scanning": {"en": "Scanning maps to determine star values…",
                         "tr": "Yıldız değerleri belirlenmek üzere müzikler taranıyor…"},
    "cancelling": {"en": "Cancelling…", "tr": "İptal ediliyor…"},
    "ratings_progress": {"en": "Computing star ratings… {done}/{total}",
                         "tr": "Yıldız dereceleri hesaplanıyor… {done}/{total}"},
    "health_done": {"en": "Library health checked ({files} files).",
                    "tr": "Kütüphane sağlığı denetlendi ({files} dosya)."},
    "health_title": {"en": "Library Health", "tr": "Kütüphane Sağlığı"},
    "health_usage": {"en": "Library: {files} files · {size} on disk.",
                     "tr": "Kütüphane: {files} dosya · diskte {size}."},
    "health_scrub": {
        "en": "{present} healthy · {orphans} orphan file(s) (on disk, no record) · "
              "{dead} dead link(s) (record, file missing) · {memory} memory-only.",
        "tr": "{present} sağlam · {orphans} yetim dosya (diskte var, kayıt yok) · "
              "{dead} ölü bağlantı (kayıt var, dosya yok) · {memory} yalnızca-hafıza."},
    "health_biggest": {"en": "Biggest beatmap sets (where the space goes):",
                       "tr": "En büyük beatmap setleri (yer nereye gidiyor):"},
    "btn_verify": {"en": "Verify (SHA-256)", "tr": "Doğrula (SHA-256)"},
    "tip_verify": {
        "en": "Re-hash each backed-up set and compare to the checksum stored when "
              "it was backed up, flagging corruption or drift. Read-only.",
        "tr": "Her yedeklenmiş seti yeniden özetler ve yedekleme sırasında saklanan "
              "sağlama toplamıyla karşılaştırır; bozulma/kaymayı işaretler. Salt okunur."},
    "health_verifying": {"en": "Verifying…", "tr": "Doğrulanıyor…"},
    "health_verify_progress": {"en": "Verifying… {done}/{total}",
                               "tr": "Doğrulanıyor… {done}/{total}"},
    "health_verify_done": {
        "en": "Verified {checked}: {ok} OK, {mismatch} mismatch, {unhashed} "
              "un-backed-up, {missing} missing.",
        "tr": "{checked} doğrulandı: {ok} sağlam, {mismatch} uyuşmazlık, {unhashed} "
              "yedeksiz, {missing} eksik."},
    "health_verify_cancelled": {"en": "Verify cancelled after {checked}.",
                                "tr": "Doğrulama {checked} sonra iptal edildi."},

    "drive_connect_first": {"en": "Connect Google Drive in Settings first.",
                            "tr": "Önce Ayarlar'dan Google Drive'a bağlan."},
    "drive_backing_up": {"en": "Backing up to Google Drive…",
                         "tr": "Google Drive'a yedekleniyor…"},
    "drive_nothing_new": {
        "en": "Everything in your Library is already backed up to Drive.",
        "tr": "Library'ndeki her şey zaten Drive'a yedeklenmiş."},
    "backup_opts_title": {"en": "Back up to Google Drive", "tr": "Google Drive'a yedekle"},
    "backup_opts_summary": {
        "en": "{n} new/changed set(s) to upload ({size}). Bundled into chunk "
              "archives and uploaded incrementally.",
        "tr": "Yüklenecek {n} yeni/değişmiş set ({size}). Chunk arşivlerine "
              "paketlenip aşamalı yüklenir."},
    "backup_opts_count": {"en": "Upload this run", "tr": "Bu turda yükle"},
    "backup_opts_chunk": {"en": "Chunk size", "tr": "Chunk boyutu"},
    "backup_opts_individual": {"en": "Individual (one file per set — slower)",
                               "tr": "Tek tek (set başına bir dosya — daha yavaş)"},
    "backup_opts_start": {"en": "Start backup", "tr": "Yedeklemeyi başlat"},
    "drive_backup_done": {
        "en": "Backed up {uploaded} tracks in {chunks} archive(s) to Drive.",
        "tr": "{uploaded} müzik {chunks} arşiv halinde Drive'a yedeklendi."},
    "drive_backup_cancelled": {
        "en": "Backup cancelled — {uploaded} tracks in {chunks} archive(s) uploaded.",
        "tr": "Yedek iptal edildi — {uploaded} müzik {chunks} arşiv yüklendi."},
    "drive_backup_failed": {"en": "Drive backup failed.", "tr": "Drive yedeği başarısız."},

    # Tooltips (item 14)
    "tip_extract": {"en": "Unpack the archives in your Packs folder into Output.",
                    "tr": "Packs klasöründeki arşivleri Output'a çıkarır."},
    "tip_copy_library": {"en": "Copy the unpacked beatmaps from Output into your Library.",
                         "tr": "Output'taki çıkarılmış müzikleri Library'e kopyalar."},
    "tip_import_osu": {"en": "Send the beatmaps in Output to osu!.",
                       "tr": "Output'taki müzikleri osu!'ya gönderir."},
    "tip_import_to_lazer": {
        "en": "Send the unpacked beatmaps in Output to osu!lazer.",
        "tr": "Output'taki çıkarılmış müzikleri osu!lazer'a gönderir."},
    "tip_import_to_stable": {
        "en": "Send the unpacked beatmaps in Output to osu!(stable).",
        "tr": "Output'taki çıkarılmış müzikleri osu!(stable)'a gönderir."},
    "tip_refresh": {
        "en": "Rescan your osu! library and update its records (added, enriched, "
              "disappeared, present).",
        "tr": "osu! kütüphanenizi yeniden tarayıp kayıtlarını günceller (eklenen, "
              "zenginleştirilen, kaybolan, mevcut)."},
    "tip_backup_drive": {"en": "Back up your Library to Google Drive.",
                        "tr": "Library'nizi Google Drive'a yedekler."},
    "tip_library_health": {
        "en": "Check your Library's integrity and disk usage: biggest sets, "
              "orphan/missing files, and an optional SHA-256 verify. Read-only.",
        "tr": "Kütüphanenizin bütünlüğünü ve disk kullanımını denetler: en büyük "
              "setler, yetim/eksik dosyalar ve isteğe bağlı SHA-256 doğrulama. "
              "Salt okunur."},
    "tip_rescan": {"en": "Rescan the Packs folder for new or updated archives.",
                  "tr": "Packs klasörünü yeni veya güncellenmiş arşivler için yeniden tarar."},
    "tip_cancel": {"en": "Cancel the operation currently in progress.",
                  "tr": "Devam eden işlemi iptal eder."},

    "tip_language": {"en": "Choose the app's display language.",
                     "tr": "Uygulamanın görüntü dilini seçer."},
    "tip_theme": {"en": "Choose the app's color theme.",
                  "tr": "Uygulamanın renk temasını seçer."},
    "tip_packs_dir": {"en": "Folder Rosu scans for archive packs to unpack.",
                      "tr": "Rosu'nun açılacak arşiv paketlerini taradığı klasör."},
    "tip_output_dir": {
        "en": "Folder where unpacked beatmaps land before being copied to Library "
              "or imported to osu!.",
        "tr": "Çıkarılan müziklerin Library'e kopyalanmadan veya osu!'ya "
              "aktarılmadan önce konduğu klasör."},
    "tip_library_dir": {"en": "Folder where your permanent beatmap library is kept.",
                        "tr": "Kalıcı müzik kütüphanenizin tutulduğu klasör."},
    "tip_osu_exe": {"en": "Path to the osu! executable used to import beatmaps.",
                    "tr": "Müzik aktarımında kullanılan osu! çalıştırılabilir dosyasının yolu."},
    "tip_osu_lazer_exe": {
        "en": "Path to the osu!lazer executable used to import beatmaps.",
        "tr": "Müzik aktarımında kullanılan osu!lazer çalıştırılabilir dosyasının yolu."},
    "tip_osu_stable_exe": {
        "en": "Path to the osu!(stable) executable used to import beatmaps.",
        "tr": "Müzik aktarımında kullanılan osu!(stable) çalıştırılabilir dosyasının yolu."},
    "tip_physical_copy": {
        "en": "Keep an actual .osz file copy in Library instead of tracking it in "
              "memory only.",
        "tr": "Library'de yalnızca hafızada değil, gerçek bir .osz dosya kopyası da tutar."},
    "tip_auto_backup": {
        "en": "Automatically copy newly unpacked beatmaps to Library right after "
              "extraction.",
        "tr": "Çıkarma işleminden hemen sonra yeni müzikleri otomatik olarak "
              "Library'e kopyalar."},
    "tip_check_updates": {
        "en": "On startup, quietly check GitHub for a newer Rosu release.",
        "tr": "Başlangıçta, daha yeni bir Rosu sürümü için GitHub'ı sessizce denetler."},
    "tip_clear_before": {"en": "Empty the Output folder before each new extraction.",
                        "tr": "Her yeni çıkarmadan önce Output klasörünü boşaltır."},
    "tip_update_reference": {
        "en": "Fetch the current official pack list from the osu! API to detect "
              "genuinely missing packs.",
        "tr": "Gerçekten eksik paketleri tespit etmek için osu! API'sinden güncel "
              "resmi paket listesini çeker."},
    "tip_scan_lost": {
        "en": "Asks the osu! API about each beatmapset in your Library: still "
              "there = fine, 404 = deleted/taken down (lost). Works in batches "
              "of 500 per run (API rate limits) — never-checked sets first, so "
              "run it again to keep going. Needs osu! API credentials.",
        "tr": "Kütüphanendeki her beatmapset'i osu! API'sine sorar: duruyorsa "
              "sorun yok, 404 ise silinmiş/kaldırılmış (kayıp). API limitleri "
              "nedeniyle her çalıştırmada 500'erlik gruplar hâlinde ilerler — "
              "önce hiç kontrol edilmemişler; devam etmek için tekrar çalıştır. "
              "osu! API bilgileri gerekir."},
    "tip_import_stable": {"en": "Import beatmaps already installed in your osu!(stable) client.",
                         "tr": "osu!(stable) istemcinizde zaten yüklü olan müzikleri içe aktarır."},
    "tip_import_lazer": {"en": "Import beatmaps already installed in your osu!lazer client.",
                        "tr": "osu!lazer istemcinizde zaten yüklü olan müzikleri içe aktarır."},
    "tip_drive": {"en": "Connect or disconnect your Google Drive account for backups.",
                 "tr": "Yedekleme için Google Drive hesabınızı bağlar veya bağlantısını keser."},
    "tip_save": {"en": "Save your folder, path and API settings.",
                "tr": "Klasör, yol ve API ayarlarınızı kaydeder."},

    "tip_search_box": {"en": "Type to search your library by artist, title or beatmap id.",
                      "tr": "Kütüphanenizde sanatçı, başlık veya beatmap id'sine göre "
                            "arama yapmak için yazın."},
    "tip_search_btn": {"en": "Run the search now.", "tr": "Aramayı şimdi çalıştırır."},
    "tip_search_tags": {
        "en": "Off by default: also match a map's tags and mapper. Leave off for "
              "artist/title searches — tag matching used to flood results.",
        "tr": "Varsayılan kapalı: haritanın etiketleri ve haritacıyı da eşleştirir. "
              "Sanatçı/başlık aramaları için kapalı bırakın — etiket eşleşmesi "
              "sonuçları eskiden dolduruyordu."},
    "tip_reload": {"en": "Reload the list from your library (reflect new imports).",
                   "tr": "Listeyi kütüphanenden yeniden yükler (yeni içe aktarımları gösterir)."},

    "tip_packs_search": {"en": "Filter packs by code, title or category.",
                        "tr": "Arşivleri koda, başlığa veya kategoriye göre süzer."},
    "tip_only_missing": {"en": "Show only packs that are missing from your collection.",
                        "tr": "Yalnızca koleksiyonunuzda eksik olan arşivleri gösterir."},
    "tip_only_extra": {
        "en": "Show only packs that contain extra files beyond the expected tracks.",
        "tr": "Yalnızca beklenenden fazla dosya içeren arşivleri gösterir."},
    "tip_packs_filter": {"en": "Filter packs by category.",
                        "tr": "Arşivleri kategoriye göre süzer."},

    "tip_artists_sort": {"en": "Choose how the artist list is sorted.",
                        "tr": "Sanatçı listesinin nasıl sıralanacağını seçer."},
    "tip_artist_filter": {"en": "Filter the artist list by name (instant, no reload).",
                          "tr": "Sanatçı listesini ada göre süzer (anında, yeniden "
                                "yükleme yok)."},

    "tip_open_formats": {
        "en": "Open log_formats.md, which explains the log entry formats.",
        "tr": "Log girdisi biçimlerini açıklayan log_formats.md dosyasını açar."},
    "tip_open_excel": {"en": "Open the Excel report of your library.",
                      "tr": "Kütüphanenizin Excel raporunu açar."},

    # Shortcuts (Kısayollar) tab (v1.2)
    "tab_shortcuts": {"en": "Shortcuts", "tr": "Kısayollar"},
    "sc_summary_title": {"en": "Installed music", "tr": "Yüklü müzik"},
    "sc_lazer": {"en": "osu!lazer", "tr": "osu!lazer"},
    "sc_stable": {"en": "osu!(stable)", "tr": "osu!(stable)"},
    "sc_library": {"en": "Library", "tr": "Kütüphane"},
    "sc_drive": {"en": "Drive backup", "tr": "Drive yedeği"},
    "sc_count_fmt": {"en": "{n} sets", "tr": "{n} set"},
    "sc_count_recorded": {"en": "{n} recorded", "tr": "{n} kayıtlı"},
    "sc_installed": {"en": "installed", "tr": "kurulu"},
    "sc_not_installed": {"en": "not installed", "tr": "yüklü değil"},
    "sc_lazer_from_library": {
        "en": "osu!lazer's library can't be read directly, so this shows how many "
              "sets Rosu has recorded from osu!lazer (imported or transferred) — "
              "your actual osu!lazer library is usually larger.",
        "tr": "osu!lazer'in kütüphanesi doğrudan okunamadığından bu, Rosu'nun "
              "osu!lazer'dan kaydettiği (içe aktarılan/aktarılan) set sayısını "
              "gösterir — gerçek osu!lazer kütüphanen genellikle daha büyüktür."},

    "sc_transfer_title": {"en": "Transfer between clients",
                          "tr": "İstemciler arası aktarım"},
    "btn_transfer_l2s": {"en": "osu!lazer → osu!(stable)",
                         "tr": "osu!lazer → osu!(stable)"},
    "btn_transfer_s2l": {"en": "osu!(stable) → osu!lazer",
                         "tr": "osu!(stable) → osu!lazer"},
    "sc_transfer_done": {
        "en": "Transfer: {transferred} sent, {skipped} already in target "
              "({found} candidates).",
        "tr": "Aktarım: {transferred} gönderildi, {skipped} zaten hedefte "
              "({found} aday)."},
    "sc_no_target_exe": {
        "en": "The target osu! client isn't set up. Set its path in Settings.",
        "tr": "Hedef osu! istemcisi ayarlı değil. Yolunu Ayarlar'dan belirtin."},

    "sc_save_title": {"en": "Save installed music to Library",
                      "tr": "Yüklü müziği Library'ye kaydet"},
    "btn_save_lib_lazer": {"en": "osu!lazer → Library", "tr": "osu!lazer → Library"},
    "btn_save_lib_stable": {"en": "osu!(stable) → Library",
                            "tr": "osu!(stable) → Library"},
    "sc_save_done": {"en": "{new} new set(s) added to your Library.",
                     "tr": "Kütüphanene {new} yeni set eklendi."},

    "sc_unpack_title": {"en": "Unpack Packs → import to osu!",
                        "tr": "Packs'i aç → osu!'ya aktar"},
    "btn_unpack_lazer": {"en": "→ osu!lazer", "tr": "→ osu!lazer"},
    "btn_unpack_stable": {"en": "→ osu!(stable)", "tr": "→ osu!(stable)"},
    "btn_unpack_both": {"en": "→ both", "tr": "→ ikisi"},
    "sc_unpack_done": {"en": "Unpacked and dispatched {tracks} beatmap(s).",
                       "tr": "{tracks} müzik açıldı ve gönderildi."},

    "sc_export_title": {"en": "Export", "tr": "Dışa aktar"},
    "sc_source_library": {"en": "Library", "tr": "Kütüphane"},
    "sc_source_drive": {"en": "Drive-backed sets", "tr": "Drive'a yedekli setler"},
    "sc_source_lazer": {"en": "osu!lazer", "tr": "osu!lazer"},
    "sc_source_stable": {"en": "osu!(stable)", "tr": "osu!(stable)"},
    "sc_source_merged": {"en": "All merged", "tr": "Hepsi birleşik"},
    "sc_split_none": {"en": "Single file", "tr": "Tek dosya"},
    "sc_split_1g": {"en": "Split 1 GB", "tr": "1 GB'a böl"},
    "sc_split_500m": {"en": "Split 500 MB", "tr": "500 MB'a böl"},
    "sc_export_drive": {"en": "Upload to Drive", "tr": "Drive'a yükle"},
    "sc_export_share": {"en": "Public link (anyone)", "tr": "Herkese açık link"},
    "sc_share_public_warn": {
        "en": "This makes the exported archive(s) accessible to ANYONE with the "
              "link — a public Google Drive share. Beatmap archives contain "
              "third-party copyrighted audio and artwork, so you are responsible "
              "for what you share. Continue?",
        "tr": "Bu, dışa aktarılan arşiv(ler)i linke sahip HERKESE açık hale getirir "
              "— herkese açık bir Google Drive paylaşımı. Beatmap arşivleri üçüncü "
              "taraf telifli ses ve görsel içerir; paylaştığından sen sorumlusun. "
              "Devam edilsin mi?"},
    "btn_export": {"en": "Export…", "tr": "Dışa aktar…"},
    "sc_export_choose": {"en": "Save export as", "tr": "Dışa aktarımı kaydet"},
    "sc_export_done": {
        "en": "Exported {count} set(s) into {archives} archive(s).",
        "tr": "{count} set {archives} arşive aktarıldı."},
    "sc_export_empty": {"en": "Nothing to export from that source.",
                        "tr": "Bu kaynakta dışa aktarılacak bir şey yok."},
    "sc_export_link": {"en": "Shareable link(s):", "tr": "Paylaşılabilir link(ler):"},
    "sc_export_upload_failed": {"en": "(Drive upload failed.)",
                                "tr": "(Drive yükleme başarısız.)"},
    "sc_export_shared_no_link": {
        "en": "Some export archive(s) were made public (anyone with the link) but "
              "Rosu couldn't retrieve the link. Open Google Drive to review or "
              "revoke the sharing.",
        "tr": "Bazı dışa-aktarım arşivleri herkese açık (linke sahip herkes) yapıldı "
              "ama Rosu linki alamadı. Paylaşımı gözden geçirmek veya iptal etmek "
              "için Google Drive'ı aç."},

    "btn_dedup": {"en": "Dedupe Library", "tr": "Kütüphaneyi tekilleştir"},
    "tip_dedup": {
        "en": "Recycle redundant duplicate .osz in your Library (the same set "
              "under different names), keeping one.",
        "tr": "Library'deki gereksiz kopya .osz'leri (aynı set, farklı ad) Geri "
              "Dönüşüm'e gönderir, birini bırakır."},
    "sc_dedup_done": {"en": "Removed {removed} duplicate file(s), freed {freed}.",
                      "tr": "{removed} kopya dosya kaldırıldı, {freed} boşaldı."},
    "sc_dedup_none": {"en": "No duplicate files found.",
                      "tr": "Kopya dosya bulunamadı."},
    "sc_cancelled": {"en": "Cancelled.", "tr": "İptal edildi."},
    "sc_exporting_lazer": {"en": "Reading osu!lazer… (can take a while — Cancel is OK)",
                           "tr": "osu!lazer okunuyor… (uzun sürebilir — İptal edebilirsin)"},
    "sc_uploading_drive": {"en": "Uploading to Google Drive…",
                           "tr": "Google Drive'a yükleniyor…"},
    "sc_export_saved_to": {"en": "Exported to: {path}",
                           "tr": "Şuraya aktarıldı: {path}"},
    "sc_dedup_confirm": {
        "en": "Found {count} extra file(s) that are duplicate copies of sets you "
              "already have (matched by beatmapset id — Rosu keeps one canonical "
              "copy per set, these are the extras). They go to the Recycle Bin "
              "(recoverable), freeing {freed}. Continue?",
        "tr": "Zaten sahip olduğun setlerin fazladan kopyası olan {count} dosya "
              "bulundu (beatmapset id ile eşleşti — Rosu her set için tek kanonik "
              "kopya tutar, bunlar fazlalıklar). Geri Dönüşüm Kutusu'na gidecekler "
              "(kurtarılabilir), {freed} boşalacak. Devam edilsin mi?"},
    "drive_disconnect_busy_title": {"en": "Operation in progress",
                                    "tr": "İşlem sürüyor"},
    "drive_disconnect_busy_body": {
        "en": "A Drive operation is still running. Disconnecting now will interrupt "
              "it. Disconnect anyway?",
        "tr": "Bir Drive işlemi hâlâ sürüyor. Şimdi bağlantıyı kesersen yarıda "
              "kalır. Yine de kesilsin mi?"},
    "sc_unpack_dupe_prompt": {
        "en": "Unpack the new packs and send them to osu!. Skip sets already in the "
              "target client, or send everything anyway?",
        "tr": "Yeni arşivleri aç ve osu!'ya gönder. Hedef istemcide zaten olan "
              "setleri atla, yoksa hepsini yine de gönder?"},
    "sc_unpack_only_new": {"en": "Only new (skip duplicates)",
                           "tr": "Sadece yeni (kopyaları atla)"},
    "sc_unpack_all": {"en": "Send all anyway", "tr": "Yine de hepsini gönder"},
    "sc_unpack_done2": {
        "en": "Unpacked {tracks} beatmap(s); skipped {skipped} already in the client.",
        "tr": "{tracks} müzik açıldı; istemcide zaten olan {skipped} atlandı."},
    "sc_share_needs_upload": {
        "en": "Tick 'Upload to Drive' first — a share link needs the file uploaded.",
        "tr": "Önce 'Drive'a yükle'yi işaretle — paylaşım linki için dosyanın "
              "yüklenmesi gerekir."},

    # -- İş Kuyruğu / Job queue (v1.3) ---------------------------------------
    "sc_refresh": {"en": "Refresh counts", "tr": "Sayıları yenile"},
    "sc_client_hidden": {
        "en": "{clients} is turned off in Settings, so its shortcuts are hidden "
              "here. Re-enable it in Settings to bring them back.",
        "tr": "{clients} Ayarlar'da kapalı olduğu için buradaki kısayolları "
              "gizlendi. Geri getirmek için Ayarlar'dan tekrar aç."},
    "refreshing": {"en": "Refreshing…", "tr": "Yenileniyor…"},
    "settings_dirty": {"en": "Unsaved changes — press Save.",
                       "tr": "Kaydedilmemiş değişiklikler — Kaydet'e bas."},
    "packs_download_hint": {
        "en": "Missing a pack? Every official beatmap pack can be downloaded "
              "from <a href='https://osu.ppy.sh/beatmaps/packs'>"
              "osu.ppy.sh/beatmaps/packs</a> — drop the downloads into Packs/ "
              "and unpack. <b>Double-click a red (missing) row to open that "
              "pack's page; a single click copies its link (Ctrl-select "
              "several to collect all their links). Double-click a present pack "
              "to see its mania skillset radar. Right-click any pack for "
              "its osu! page.</b>",
        "tr": "Eksik paket mi var? Tüm resmî beatmap paketleri "
              "<a href='https://osu.ppy.sh/beatmaps/packs'>"
              "osu.ppy.sh/beatmaps/packs</a> adresinden indirilebilir — "
              "indirdiklerini Packs/ klasörüne at ve aç. <b>Kırmızı (eksik) "
              "satıra çift tıklayınca o paketin sayfası açılır; tek tık "
              "linkini kopyalar (Ctrl ile çoklu seçersen tüm linkler "
              "toplanır). Mevcut bir pakete çift tıklayınca mania beceri "
              "radarı açılır. Herhangi bir pakete sağ tıklayıp osu! sayfasını "
              "açabilirsin.</b>"},
    "menu_open_osu_page": {"en": "Open osu! page", "tr": "osu! sayfasını aç"},
    # -- v1.6: pack skillset summary (double-click a present pack) ------------
    "pack_skill_title": {"en": "Skillset — {code}", "tr": "Beceri — {code}"},
    "pack_skill_sub": {
        "en": "Average of {n} mania set(s) · overall {overall} · hardest {peak}",
        "tr": "{n} mania setinin ortalaması · genel {overall} · en zor {peak}"},
    "pack_skill_none": {
        "en": "This pack has no rated mania charts yet. Run “Compute Skillset "
              "Ratings (mania)” in Settings, or it may simply contain no mania maps.",
        "tr": "Bu pakette henüz derecelendirilmiş mania haritası yok. Ayarlar’dan "
              "“Beceri Puanlarını Hesapla (mania)”yı çalıştır ya da pakette hiç "
              "mania haritası olmayabilir."},
    "sc_jobqueue_title": {"en": "Job queue", "tr": "İş kuyruğu"},
    "job_added": {"en": "Added to the queue.", "tr": "Kuyruğa eklendi."},
    "sc_export_star_prefilled": {
        "en": "Star range set from the histogram — pick a format and Export.",
        "tr": "Yıldız aralığı histogramdan alındı — bir biçim seçip Dışa aktar’a bas."},
    "tip_export_star": {
        "en": "Only export Library sets whose hardest difficulty's star is in this "
              "range. ★≥ — / ★≤ 12 means no limit.",
        "tr": "Yalnızca en zor zorluğunun yıldızı bu aralıkta olan Kütüphane setlerini "
              "dışa aktar. ★≥ — / ★≤ 12 = sınır yok."},
    "job_cancelled_rest": {"en": "Cancelled — the rest keep going.",
                           "tr": "İptal edildi — diğerleri devam ediyor."},
    "job_clear_finished": {"en": "Clear finished", "tr": "Bitenleri temizle"},
    "queue_empty": {
        "en": "Queue is empty. Start an action above to add a job.",
        "tr": "Kuyruk boş. Bir iş eklemek için yukarıdan bir işlem başlat."},
    "job_state_pending": {"en": "Queued", "tr": "Sırada"},
    "job_state_running": {"en": "Running", "tr": "Çalışıyor"},
    "job_state_done": {"en": "Done", "tr": "Bitti"},
    "job_state_failed": {"en": "Failed", "tr": "Hata"},
    "job_state_cancelled": {"en": "Cancelled", "tr": "İptal"},
    # job titles
    "job_unpack_lazer": {"en": "Unpack → osu!lazer", "tr": "Aç → osu!lazer"},
    "job_unpack_stable": {"en": "Unpack → osu!(stable)", "tr": "Aç → osu!(stable)"},
    "job_unpack_both": {"en": "Unpack → both clients", "tr": "Aç → iki istemci"},
    "job_transfer": {"en": "Transfer {source} → {target}",
                     "tr": "Aktar {source} → {target}"},
    "job_save": {"en": "Save {sources} → Library",
                 "tr": "{sources} → Library'ye kaydet"},
    "job_export": {"en": "Export {source} → {name}",
                   "tr": "Dışa aktar {source} → {name}"},
    "job_dedup": {"en": "Dedupe Library", "tr": "Kütüphaneyi tekilleştir"},
    "job_cancel_tip": {"en": "Cancel this job", "tr": "Bu işi iptal et"},
    "job_step_skip": {"en": "Remove this step", "tr": "Bu adımı çıkar"},
    # step labels
    "job_step_prescan": {"en": "Pre-scan packs", "tr": "Paketleri ön tara"},
    "job_step_extract": {"en": "Extract", "tr": "Çıkart"},
    "job_step_send_lazer": {"en": "Send to osu!lazer", "tr": "osu!lazer'e gönder"},
    "job_step_send_stable": {"en": "Send to osu!(stable)",
                             "tr": "osu!(stable)'a gönder"},
    "job_step_enumerate": {"en": "Check target", "tr": "Hedefi tara"},
    "job_step_export_client": {"en": "Export from client",
                               "tr": "İstemciden dışa aktar"},
    "job_step_send": {"en": "Send to target", "tr": "Hedefe gönder"},
    "job_step_save_lazer": {"en": "osu!lazer → Library", "tr": "osu!lazer → Library"},
    "job_step_save_stable": {"en": "osu!(stable) → Library",
                             "tr": "osu!(stable) → Library"},
    "job_step_gather": {"en": "Gather sets from {source}",
                        "tr": "{source} kaynağından setleri topla"},
    "job_step_archive": {"en": "Write {name}", "tr": "{name} yaz"},
    "job_step_upload": {"en": "Upload to Drive", "tr": "Drive'a yükle"},
    "job_step_scan": {"en": "Scan for duplicates", "tr": "Kopyaları tara"},
    "job_step_remove": {"en": "Recycle duplicates",
                        "tr": "Kopyaları geri dönüşüme gönder"},

    # -- quick UX (v1.3) -----------------------------------------------------
    "set_auto_refresh": {"en": "Auto-refresh a tab when I open it",
                         "tr": "Sekmeye geçince verileri otomatik yenile"},
    "tip_auto_refresh": {
        "en": "When you switch to a tab, refresh its data automatically "
              "(Dashboard scan, Shortcuts counts, Search, Packs…).",
        "tr": "Bir sekmeye geçtiğinde verilerini otomatik yeniler (Panel taraması, "
              "Kısayol sayıları, Arama, Packs…)."},
    "sc_export_random": {"en": "Random N:", "tr": "Rastgele N:"},
    "tip_export_random": {
        "en": "Export a random sample of this many sets instead of all of them.",
        "tr": "Hepsi yerine bu kadar seti rastgele seçip dışa aktarır."},
    "menu_open_location": {"en": "Open file location", "tr": "Dosya konumunu aç"},

    # -- Settings overhaul (v1.4) --------------------------------------------
    "set_lazer_enabled": {"en": "Enable osu!lazer", "tr": "osu!lazer'i etkinleştir"},
    "tip_lazer_enabled": {
        "en": "Show osu!lazer import/transfer/export controls. Turn off if you "
              "don't use osu!lazer — its buttons are then hidden everywhere.",
        "tr": "osu!lazer içe aktar/aktar/dışa aktar denetimlerini gösterir. "
              "Kullanmıyorsan kapat — düğmeleri her yerde gizlenir."},
    "set_stable_enabled": {"en": "Enable osu!(stable)", "tr": "osu!(stable)'ı etkinleştir"},
    "tip_stable_enabled": {
        "en": "Show osu!(stable) import/transfer/export controls. Off by default; "
              "turn it on if you use osu!(stable).",
        "tr": "osu!(stable) içe aktar/aktar/dışa aktar denetimlerini gösterir. "
              "Varsayılan kapalı; osu!(stable) kullanıyorsan aç."},
    "set_autosave": {"en": "Auto-save settings (apply immediately)",
                     "tr": "Ayarları otomatik kaydet (anında uygula)"},
    "tip_autosave": {
        "en": "On: every setting (including folders and API keys) is saved the "
              "moment you change it — the Save button is hidden. Off: paths and "
              "API keys wait for the Save button.",
        "tr": "Açık: her ayar (klasörler ve API anahtarları dahil) değiştirdiğin "
              "an kaydedilir — Kaydet düğmesi gizlenir. Kapalı: yollar ve API "
              "anahtarları Kaydet düğmesini bekler."},
    "sc_client_disabled": {
        "en": "That osu! client is turned off in Settings. Enable it there first.",
        "tr": "Bu osu! istemcisi Ayarlar'dan kapalı. Önce oradan etkinleştir."},

    # -- bug-report / contact form (v1.4) ------------------------------------
    "btn_report": {"en": "Report a problem", "tr": "Sorun bildir"},
    "tip_report": {
        "en": "Send a bug report or feedback (with an optional screenshot) to the "
              "Rosu team.",
        "tr": "Rosu ekibine hata bildirimi veya geri bildirim gönder (isteğe bağlı "
              "ekran görüntüsüyle)."},
    "report_title": {"en": "Report a problem / Send feedback",
                     "tr": "Sorun bildir / Geri bildirim gönder"},
    "report_field_title": {"en": "Title", "tr": "Başlık"},
    "report_field_desc": {
        "en": "Description — what happened, and the steps to reproduce it",
        "tr": "Açıklama — ne oldu ve nasıl tekrarlanır"},
    "report_contact": {"en": "Your e-mail (optional, so we can reply)",
                       "tr": "E-postan (isteğe bağlı, yanıt verebilmemiz için)"},
    "report_attach": {"en": "Attach screenshot (max 3 MB)…",
                      "tr": "Ekran görüntüsü ekle (en fazla 3 MB)…"},
    "report_bad_email": {
        "en": "That e-mail address doesn't look valid (e.g. you@example.com). "
              "Fix it or leave the field empty.",
        "tr": "Bu e-posta adresi geçerli görünmüyor (ör. sen@ornek.com). "
              "Düzelt ya da alanı boş bırak."},
    "report_web_alt": {
        "en": "You can also send this report from the website: "
              "<a href='https://rosu-web.vercel.app/report'>"
              "rosu-web.vercel.app/report</a>.",
        "tr": "Bu bildirimi web sitesinden de gönderebilirsin: "
              "<a href='https://rosu-web.vercel.app/report'>"
              "rosu-web.vercel.app/report</a>."},
    "report_disclosure": {
        "en": "Sent to the Rosu team: your text, the app version, your OS and UI "
              "language, and any screenshot you attach (plus, on the server, a "
              "hashed form of your IP address to limit spam). Nothing is sent "
              "until you press Send.",
        "tr": "Rosu ekibine gönderilir: yazdıkların, uygulama sürümü, işletim "
              "sistemin ve arayüz dilin, ve eklediğin ekran görüntüsü (ayrıca "
              "sunucuda, spam'i sınırlamak için IP adresinin hash'lenmiş bir "
              "hâli). Gönder'e basana kadar hiçbir şey gönderilmez."},
    "report_agree": {
        "en": "By sending, you agree to our "
              "<a href='https://rosu-web.vercel.app/privacy'>Privacy Policy</a> and "
              "<a href='https://rosu-web.vercel.app/terms'>Terms</a>.",
        "tr": "Göndererek "
              "<a href='https://rosu-web.vercel.app/privacy'>Gizlilik Politikası</a> ve "
              "<a href='https://rosu-web.vercel.app/terms'>Şartlar</a>'ı kabul etmiş olursun."},
    "report_submit": {"en": "Send", "tr": "Gönder"},
    "report_sending": {"en": "Sending…", "tr": "Gönderiliyor…"},
    "report_sent": {"en": "Thanks! Your report was sent.",
                    "tr": "Teşekkürler! Bildirimin gönderildi."},
    "report_need_fields": {"en": "Please fill in both the title and the description.",
                           "tr": "Lütfen hem başlığı hem açıklamayı doldur."},
    "report_image_too_big": {
        "en": "That image is too large (max 3 MB). Please attach a smaller one.",
        "tr": "Bu görsel çok büyük (en fazla 3 MB). Lütfen daha küçük bir tane ekle."},
    "report_image_bad": {"en": "That file isn't a supported image.",
                         "tr": "Bu dosya desteklenen bir görsel değil."},
    "report_failed_fallback": {
        "en": "Couldn't send right now. Click <a href='copy-mail'>"
              "rosu.app@gmail.com</a> to copy the address, or "
              "<a href='https://rosu-web.vercel.app/report'>use the web form</a>.",
        "tr": "Şu an gönderilemedi. Adresi kopyalamak için <a href='copy-mail'>"
              "rosu.app@gmail.com</a>'a tıkla veya "
              "<a href='https://rosu-web.vercel.app/report'>web formunu kullan</a>."},
    "report_email_copied": {
        "en": "rosu.app@gmail.com copied to the clipboard. Or "
              "<a href='https://rosu-web.vercel.app/report'>use the web form</a>.",
        "tr": "rosu.app@gmail.com panoya kopyalandı. İstersen "
              "<a href='https://rosu-web.vercel.app/report'>web formunu kullan</a>."},
    "report_rate_limited": {
        "en": "You've sent a few reports in a short time. Please wait a bit and "
              "try again.",
        "tr": "Kısa sürede birkaç rapor gönderdin. Lütfen biraz bekleyip tekrar "
              "dene."},
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
