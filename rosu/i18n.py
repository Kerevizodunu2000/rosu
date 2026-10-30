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
    "disk_no_space": {"en": "Not enough free space on {drive}: {need} needed, {free} free. "
                            "Nothing was written.",
                      "tr": "{drive} sürücüsünde yeterli boş alan yok: {need} gerekli, "
                            "{free} boş. Hiçbir şey yazılmadı."},
    "extract_disk_full": {"en": "Disk full: Unpack stopped. Beatmaps already extracted "
                                "stay in Output and the archive stays in Packs.",
                          "tr": "Disk dolu: arşiv açma durduruldu. Çıkarılan müzikler "
                                "Output'ta, arşiv Packs'te kalıyor."},
    "library_disk_full": {"en": "Disk full: Copy to Library stopped. Sets already copied "
                                "stay in the Library.",
                          "tr": "Disk dolu: Library'e kopyalama durduruldu. Kopyalanan "
                                "setler Library'de kalıyor."},
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
        "en": "Recycle / move the archives fully added to your library "
              "(uses your 'Processed .zip action' setting).",
        "tr": "Tamamen kütüphanende olan arşivleri geri dönüşüme gönder / taşı "
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
    "disposal_kept": {"en": "Kept {n} file(s) instead of removing them; the Logs tab "
                            "says why.",
                      "tr": "{n} dosya kaldırılmak yerine tutuldu; nedeni Loglar "
                            "sekmesinde."},
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
    "lib_status_pruned": {"en": "pruned ✂", "tr": "prune edildi ✂"},
    "lib_status_present": {"en": "present", "tr": "mevcut"},
    "lib_status_memory": {"en": "memory only", "tr": "yalnızca hafıza"},
    "lib_status_disappeared": {"en": "disappeared", "tr": "kayboldu"},
    "lib_status_disappeared_at": {"en": "disappeared @ {when}",
                                  "tr": "kayboldu @ {when}"},
    "pruned_tip": {
        "en": "Pruned in: {where}. Copies of this set anywhere else — including "
              "osu!lazer — were NOT touched.\n\nPrune removed the heavy files "
              "(video, and depending on the mode large unused images). The "
              "beatmap itself, its audio and its background are intact and it "
              "still plays. To get the full set back: Shortcuts → “Restore pruned "
              "maps”, or right-click this row → Repair. List every pruned set "
              "with the search pruned=yes .",
        "tr": "Şurada kırpıldı: {where}. Bu setin başka yerlerdeki kopyalarına — "
              "osu!lazer dahil — DOKUNULMADI.\n\nPrune ağır dosyaları kaldırdı "
              "(video ve moda göre kullanılmayan büyük görseller). Beatmap'in "
              "kendisi, sesi ve arka planı yerinde; harita hâlâ oynanır. Setin "
              "tamamını geri almak için: Kısayollar → “Kırpılmışları geri getir”, "
              "ya da bu satıra sağ tıkla → Onar. Tüm kırpılmış setleri görmek için "
              "pruned=yes ara."},
    "search_truncated": {
        "en": "Showing {n} of {total} matches — narrow the query to see the rest.",
        "tr": "{total} eşleşmenin {n} tanesi listeleniyor — kalanı için aramayı "
              "daralt."},
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
    "set_auto_update": {"en": "Install updates automatically",
                        "tr": "Güncellemeleri otomatik yükle"},
    "tip_auto_update": {
        "en": "When a newer release is found, download it in the background, check its "
              "signature and install it when you restart Rosu. Needs the startup update "
              "check. A new version that fails to start is rolled back.",
        "tr": "Daha yeni bir sürüm bulunduğunda arka planda indirir, imzasını denetler ve "
              "Rosu'yu yeniden başlattığında yükler. Başlangıçta güncelleme denetimi açık "
              "olmalı. Açılamayan yeni bir sürüm geri alınır."},
    "update_downloading": {"en": "Downloading Rosu {tag}… {percent}%",
                           "tr": "Rosu {tag} indiriliyor… %{percent}"},
    "update_ready": {"en": "Rosu {tag} is ready.", "tr": "Rosu {tag} hazır."},
    "update_restart": {"en": "Restart now", "tr": "Şimdi yeniden başlat"},
    "update_restart_later": {
        "en": "A task is still running. The update will be installed the next time "
              "Rosu starts.",
        "tr": "Bir işlem hâlâ sürüyor. Güncelleme, Rosu bir sonraki açılışında "
              "yüklenecek."},
    "set_zip_disposal": {"en": "Processed .zip action", "tr": "İşlenen .zip işlemi"},
    "zip_recycle": {"en": "Move to Recycle Bin", "tr": "Geri Dönüşüm Kutusu'na taşı"},
    "zip_move": {"en": "Move to Processed/", "tr": "Processed/ klasörüne taşı"},
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
    "map_details_pruned": {
        "en": "✂ Pruned — the heavy files (video, and depending on the mode large "
              "unused images) were removed to save space. The beatmap, its audio "
              "and its background are intact and it still plays. Restore "
              "re-downloads the complete set from an osu! mirror.",
        "tr": "✂ Prune edildi — yer kazanmak için ağır dosyalar (video ve moda göre "
              "kullanılmayan büyük görseller) kaldırıldı. Beatmap, sesi ve arka "
              "planı yerinde; harita hâlâ oynanır. “Geri getir”, setin tamamını bir "
              "osu! aynasından yeniden indirir."},
    "map_details_missing": {
        "en": "This set is in Rosu's memory but its file is not in the Library. "
              "Restore re-downloads it from an osu! mirror.",
        "tr": "Bu set Rosu'nun hafızasında var ama dosyası Library'de yok. “Geri "
              "getir” onu bir osu! aynasından yeniden indirir."},
    "btn_restore_map": {"en": "Restore (re-download)", "tr": "Geri getir (yeniden indir)"},
    "tip_restore_map": {
        "en": "Download the complete set again from a third-party osu! mirror and "
              "replace the local file. You are asked to confirm first.",
        "tr": "Setin tamamını üçüncü taraf bir osu! aynasından yeniden indirir ve "
              "yerel dosyanın yerine koyar. Önce onayın istenir."},
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
    "reference_cancelled": {
        "en": "Reference sync cancelled — nothing was saved (a half-fetched "
              "reference would mark real packs as missing).",
        "tr": "Referans eşitlemesi iptal edildi — hiçbir şey kaydedilmedi (yarım "
              "çekilmiş bir referans gerçek paketleri eksik gösterirdi)."},
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
    "err_db_init_title": {"en": "Rosu couldn't start",
                          "tr": "Rosu başlatılamadı"},
    "err_db_init_body": {
        "en": "Rosu couldn't open its database:\n{path}\n\n{error}\n\nYour beatmap "
              "files are untouched. This can happen after a failed update or a "
              "corrupted file — back up the file above, then use \"Report a "
              "problem\" in a previous version or e-mail rosu.app@gmail.com.",
        "tr": "Rosu veritabanını açamadı:\n{path}\n\n{error}\n\nBeatmap "
              "dosyalarınıza dokunulmadı. Bu, başarısız bir güncelleme veya "
              "bozulmuş bir dosya sonrasında olabilir — önce yukarıdaki dosyayı "
              "yedekleyin, sonra önceki bir sürümdeki \"Sorun bildir\" formunu "
              "kullanın veya rosu.app@gmail.com adresine yazın."},
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
    "drive_folder_line": {"en": "Backing up into this Drive folder:",
                          "tr": "Yedekleme şu Drive klasörüne yapılıyor:"},
    "drive_folder_scope_note": {
        "en": "Rosu can only see the files it created itself (the narrow "
              "drive.file permission), so a “Rosu” folder you made by hand — or "
              "one created by a Rosu older than v1.3.3, which used a different "
              "Google client — is invisible to it and a fresh folder is made "
              "instead. Older backups are still in your Drive; open the old "
              "folder yourself to reach them.",
        "tr": "Rosu yalnızca kendi oluşturduğu dosyaları görebilir (dar "
              "drive.file izni). Bu yüzden elle oluşturduğun bir “Rosu” klasörü "
              "— ya da farklı bir Google istemcisi kullanan v1.3.3 öncesi bir "
              "Rosu'nun oluşturduğu klasör — uygulamaya görünmez ve yerine yeni "
              "bir klasör açılır. Eski yedeklerin Drive'ında duruyor; onlara "
              "ulaşmak için eski klasörü kendin aç."},
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
        "en": "Rates each MANIA difficulty on Etterna's 7 skillsets (stream, "
              "jumpstream, handstream, stamina, jackspeed, chordjack, technical) "
              "plus an overall — computed here, offline, no engine or internet. "
              "This is what fills the Skill column in Search, the radar in Map "
              "Details, and a pack's average radar. Sets with no mania difficulty "
              "are visited but produce no rating: the rating is mania-only by "
              "design. Already-scanned sets are skipped, so a second run is "
              "normally a no-op.",
        "tr": "Her MANIA zorluğunu Etterna'nın 7 beceri alanında (stream, "
              "jumpstream, handstream, stamina, jackspeed, chordjack, technical) "
              "ve bir genel puanla derecelendirir — burada, çevrimdışı, motor ya "
              "da internet gerekmeden hesaplanır. Arama'daki Beceri sütununu, "
              "Harita Detayları'ndaki radarı ve bir paketin ortalama radarını "
              "besleyen şey budur. Mania zorluğu olmayan setler taranır ama puan "
              "üretmez: bu derecelendirme tasarım gereği yalnızca mania içindir. "
              "Daha önce taranmış setler atlanır, bu yüzden ikinci çalıştırma "
              "normalde hiçbir şey yapmaz."},
    "msd_no_library": {
        "en": "Your Library is empty — add some beatmaps first.",
        "tr": "Kütüphanen boş — önce birkaç beatmap ekle."},
    "msd_done": {
        "en": "{scanned} set(s) scanned · {rated} had mania difficulties and were "
              "rated · {remaining} left. Sets with no mania difficulty get no "
              "skillset rating — that is by design, not a failure.",
        "tr": "{scanned} set tarandı · {rated} tanesinde mania zorluğu vardı ve "
              "derecelendirildi · {remaining} kaldı. Mania zorluğu olmayan setler "
              "beceri puanı almaz — bu bir hata değil, tasarım gereği."},
    "msd_nothing_new": {
        "en": "Every Library set has already been scanned — nothing new to rate. "
              "(Only mania difficulties get a skillset rating.)",
        "tr": "Kütüphanedeki her set zaten taranmış — derecelendirilecek yeni bir "
              "şey yok. (Beceri puanı yalnızca mania zorlukları için verilir.)"},
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
    "tip_star_dist": {
        "en": "Show the star-rating distribution of your whole Library, counted "
              "per difficulty.",
        "tr": "Tüm kütüphanenin yıldız derecesi dağılımını göster (zorluk başına "
              "sayılır)."},
    "star_dist_title": {"en": "Star distribution", "tr": "Yıldız dağılımı"},
    "star_dist_head": {
        "en": "{n} rated difficulties in {sets} Library sets",
        "tr": "Kütüphanedeki {sets} sette {n} derecelendirilmiş zorluk"},
    "star_dist_bins": {"en": "Ranges:", "tr": "Aralıklar:"},
    "star_dist_bins_tip": {
        "en": "How the bars are split up. “Fit to the data” uses the full width "
              "of your Library; “Whole stars” uses plain 1★ buckets.",
        "tr": "Çubukların nasıl bölüneceği. “Veriye göre” kütüphanenin tüm "
              "genişliğini kullanır; “Tam yıldız” düz 1★'lık kutular kullanır."},
    "star_dist_bins_auto": {"en": "Fit to the data",
                            "tr": "Veriye göre"},
    "star_dist_bins_auto_tip": {
        "en": "Splits the range between your easiest and hardest difficulty into "
              "20 equal bars. It uses the whole chart, but the edges land on odd "
              "numbers like 3.94–4.55 because they follow your actual maps.",
        "tr": "En kolay ve en zor zorluğun arasını 20 eşit çubuğa böler. Grafiğin "
              "tamamını kullanır ama kenarlar senin gerçek haritalarına göre "
              "hesaplandığı için 3.94–4.55 gibi tuhaf sayılara denk gelir."},
    "star_dist_bins_integer": {"en": "Whole stars (0–1, 1–2, …)",
                               "tr": "Tam yıldız (0–1, 1–2, …)"},
    "star_dist_bins_integer_tip": {
        "en": "One bar per whole star: 0–1, 1–2, 2–3 … Easier to read and to act "
              "on (“how many 5★ maps do I have?”). Empty stars are still shown so "
              "the axis reads continuously.",
        "tr": "Her tam yıldız için bir çubuk: 0–1, 1–2, 2–3 … Okuması ve "
              "kullanması daha kolay (“kaç tane 5★ haritam var?”). Boş yıldızlar "
              "da gösterilir, böylece eksen kesintisiz okunur."},
    "star_dist_hint": {
        "en": "Click a bar to select it (drag across bars for a range); "
              "double-click a bar to search that range.",
        "tr": "Bir çubuğa tıklayıp seç (aralık için çubuklar üzerinde sürükle); "
              "bir çubuğa çift tıklayınca o aralık aratılır."},
    "star_dist_selected": {
        "en": "{lo}★–{hi}★ · {count} difficulties ({pct}% of the Library), living "
              "in {sets} set(s). Searching this range will therefore list "
              "{sets} result(s) — one per set, not per difficulty.",
        "tr": "{lo}★–{hi}★ · {count} zorluk (kütüphanenin %{pct}'i), {sets} sette "
              "bulunuyor. Bu aralığı aradığında {sets} sonuç listelenecek — set "
              "başına bir tane, zorluk başına değil."},
    "star_dist_search": {"en": "Search this range", "tr": "Bu aralığı ara"},
    "star_dist_export": {"en": "Export this range", "tr": "Bu aralığı dışa aktar"},
    "star_dist_empty": {
        "en": "No star ratings in your Library yet.",
        "tr": "Kütüphanende henüz yıldız derecesi yok."},
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
        "en": "Re-reads every Library file and compares its SHA-256 to the "
              "checksum recorded when that file was backed up to Drive, so you "
              "can tell whether the bytes on disk have changed since. It only "
              "REPORTS — it never repairs, moves or deletes anything.",
        "tr": "Kütüphanedeki her dosyayı yeniden okur ve SHA-256'sını, o dosya "
              "Drive'a yedeklenirken kaydedilen sağlama toplamıyla karşılaştırır; "
              "böylece diskteki baytların o günden beri değişip değişmediğini "
              "görürsün. Yalnızca RAPORLAR — hiçbir şeyi onarmaz, taşımaz, silmez."},
    "health_verifying": {"en": "Verifying…", "tr": "Doğrulanıyor…"},
    "health_verify_progress": {"en": "Verifying… {done}/{total}",
                               "tr": "Doğrulanıyor… {done}/{total}"},
    "health_verify_done": {
        "en": "Read-only check, nothing was changed. {checked} file(s) compared: "
              "{ok} still match their backup · {mismatch} changed since the backup "
              "(re-imported, refreshed, pruned — or corrupted) · {unhashed} were "
              "never backed up to Drive, so there is nothing to compare them "
              "against · {pruned} are pruned (their bytes changed on purpose) · "
              "{missing} file(s) could not be read.",
        "tr": "Salt-okunur kontrol, hiçbir şey değiştirilmedi. {checked} dosya "
              "karşılaştırıldı: {ok} tanesi yedeğiyle hâlâ aynı · {mismatch} tanesi "
              "yedeklendiğinden beri değişmiş (yeniden içe aktarma, yenileme, prune "
              "— ya da bozulma) · {unhashed} tanesi Drive'a hiç yedeklenmemiş, yani "
              "karşılaştırılacak bir şey yok · {pruned} tanesi prune edilmiş "
              "(baytları bilerek değişti) · {missing} dosya okunamadı."},
    "health_verify_mismatch_list": {
        "en": "Changed since backup ({n}) — right-click one in Search to re-download "
              "it, or back the Library up again to refresh the checksums:",
        "tr": "Yedeklendiğinden beri değişenler ({n}) — Arama'da birine sağ tıklayıp "
              "yeniden indirebilir ya da sağlama toplamlarını tazelemek için "
              "kütüphaneyi tekrar yedekleyebilirsin:"},
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
        "en": "On startup, quietly check Rosu's site (or GitHub) for a newer release.",
        "tr": "Başlangıçta, daha yeni bir sürüm için Rosu'nun sitesini (veya GitHub'ı) "
              "sessizce denetler."},
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
    # -- v1.7.1: what every queued job actually chose ------------------------
    "job_opt_all": {"en": "all sets", "tr": "tüm setler"},
    "job_opt_random": {"en": "{n} at random", "tr": "rastgele {n}"},
    "job_opt_stars": {"en": "★{lo}–{hi}", "tr": "★{lo}–{hi}"},
    "job_opt_stars_min": {"en": "★{lo} and up", "tr": "★{lo} ve üstü"},
    "job_opt_split": {"en": "split every {size}", "tr": "her {size}'ta böl"},
    "job_opt_upload": {"en": "upload to Drive", "tr": "Drive'a yükle"},
    "job_opt_share": {"en": "public link", "tr": "herkese açık link"},
    "job_opt_dest": {"en": "→ {path}", "tr": "→ {path}"},
    "job_opt_link": {"en": "Link: {url}", "tr": "Link: {url}"},
    "job_opt_only_new": {"en": "only sets you don't have",
                         "tr": "yalnızca sende olmayan setler"},
    "job_opt_every_set": {"en": "every set, duplicates included",
                          "tr": "kopyalar dahil her set"},
    "sc_job_repeat_confirm": {
        "en": "You just started this exact job — it is in the queue below. Start "
              "it again anyway?",
        "tr": "Bu işin tam aynısını az önce başlattın — aşağıdaki kuyrukta duruyor. "
              "Yine de tekrar başlatılsın mı?"},
    "sc_export_link": {"en": "Shareable link(s):", "tr": "Paylaşılabilir link(ler):"},
    "sc_export_link_copied": {"en": "Link copied to the clipboard.",
                              "tr": "Link panoya kopyalandı."},
    "btn_copy_link": {"en": "Copy link", "tr": "Linki kopyala"},
    "btn_close": {"en": "Close", "tr": "Kapat"},
    "sc_export_dest_busy": {
        "en": "Another export is still queued or uploading to “{name}”. Pick a "
              "different name — writing there now would overwrite the archive "
              "that export is still using.",
        "tr": "“{name}” hedefine yazan başka bir dışa aktarım hâlâ kuyrukta ya da "
              "yükleniyor. Farklı bir ad seç — şimdi oraya yazmak, o işin hâlâ "
              "kullandığı arşivin üzerine yazar."},
    "sc_export_overwrite_volumes": {
        "en": "{n} archive volume(s) with this name already exist and would be "
              "overwritten ({names}). Continue?",
        "tr": "Bu adla {n} arşiv parçası zaten var ve üzerine yazılacak "
              "({names}). Devam edilsin mi?"},
    "sc_export_upload_failed": {"en": "(Drive upload failed.)",
                                "tr": "(Drive yükleme başarısız.)"},
    "sc_export_shared_no_link": {
        "en": "Some export archive(s) were made public (anyone with the link) but "
              "Rosu couldn't retrieve the link. Open Google Drive to review or "
              "revoke the sharing.",
        "tr": "Bazı dışa-aktarım arşivleri herkese açık (linke sahip herkes) yapıldı "
              "ama Rosu linki alamadı. Paylaşımı gözden geçirmek veya iptal etmek "
              "için Google Drive'ı aç."},

    # -- v1.7.1: undoing a prune -------------------------------------------
    "btn_restore_pruned": {"en": "Restore pruned maps",
                           "tr": "Kırpılmışları geri getir"},
    "tip_restore_pruned": {
        "en": "Re-downloads every pruned set at full size (video and all) from a "
              "third-party osu! mirror. Use this when you want your videos back. "
              "Prune also puts each original in the Recycle Bin as "
              "“<name>.osz.orig” — that is the instant undo, but only until the "
              "bin is emptied, and only for the Library.",
        "tr": "Kırpılmış her seti tam boyutuyla (videosuyla birlikte) üçüncü taraf "
              "bir osu! aynasından yeniden indirir. Videolarını geri istediğinde "
              "bunu kullan. Prune ayrıca her orijinali Geri Dönüşüm Kutusu'na "
              "“<ad>.osz.orig” olarak koyar — anında geri alma yolu odur ama "
              "yalnızca kutu boşaltılana kadar ve yalnızca Kütüphane için."},
    "restore_title": {"en": "Restore pruned maps — from where?",
                      "tr": "Kırpılmışları geri getir — nereden?"},
    "restore_head": {
        "en": "{n} set(s) are pruned. Where should the missing files come back from?",
        "tr": "{n} set kırpılmış. Eksik dosyalar nereden geri gelsin?"},
    "restore_opt_recycle": {"en": "From the Recycle Bin (free, exact, instant)",
                            "tr": "Geri Dönüşüm Kutusu'ndan (bedava, birebir, anında)"},
    "restore_opt_recycle_note": {
        "en": "Prune put every original in the Recycle Bin — Library sets as "
              "“<name>.osz.orig”, and osu!(stable) files under their own names "
              "with their original folder shown. Restoring from there is free and "
              "byte-identical, as long as you have not emptied the bin. Rosu opens "
              "the bin and tells you what to look for; it does not reach into it "
              "for you.",
        "tr": "Prune her orijinali Geri Dönüşüm Kutusu'na koydu — Kütüphane setleri "
              "“<ad>.osz.orig” olarak, osu!(stable) dosyaları ise kendi adlarıyla ve "
              "orijinal klasörleri görünecek şekilde. Kutuyu boşaltmadıysan oradan "
              "geri almak bedava ve birebir aynı. Rosu kutuyu açar ve neye "
              "bakacağını söyler; senin yerine içine uzanmaz."},
    "restore_opt_mirror": {"en": "Download again from an osu! mirror ({url})",
                           "tr": "Bir osu! aynasından yeniden indir ({url})"},
    "restore_opt_mirror_note": {
        "en": "Re-downloads the complete set from {url} — a THIRD-PARTY mirror, "
              "not run by osu!'s developers. Works however long ago the prune "
              "happened, but it costs bandwidth and a set the mirror does not "
              "have will fail.",
        "tr": "Setin tamamını {url} üzerinden yeniden indirir — bu ÜÇÜNCÜ TARAF bir "
              "ayna, osu! geliştiricileri tarafından işletilmiyor. Kırpma ne kadar "
              "önce olursa olsun çalışır ama veri harcar ve aynada olmayan bir set "
              "için başarısız olur."},
    "restore_why_not_official": {
        "en": "Why not the official osu! servers? Downloading beatmaps there needs "
              "a signed-in osu! account, and the public osu! API has no download "
              "endpoint — so Rosu cannot fetch from them on your behalf.",
        "tr": "Neden resmî osu! sunucuları değil? Oradan beatmap indirmek oturum "
              "açmış bir osu! hesabı gerektiriyor ve herkese açık osu! API'sinde "
              "indirme uç noktası yok — bu yüzden Rosu senin adına oradan çekemiyor."},
    "restore_go": {"en": "Continue", "tr": "Devam et"},
    "restore_recycle_how": {
        "en": "The Recycle Bin is open. Sort by “Date deleted” to find the prune "
              "run, then select the files and press Restore — they go straight "
              "back where they came from.\n\nLibrary originals are named "
              "“<set>.osz.orig”: restore them, then remove the “.orig” from the "
              "end of the name so Rosu sees them again. (Sets pruned before this "
              "version may appear as “tmp…….osz.orig”; the Original Location "
              "column still shows they came from your Library.)",
        "tr": "Geri Dönüşüm Kutusu açıldı. Kırpma çalıştırmasını bulmak için "
              "“Silinme tarihi”ne göre sırala, dosyaları seç ve Geri Yükle'ye bas — "
              "geldikleri yere geri dönerler.\n\nKütüphane orijinalleri "
              "“<set>.osz.orig” adıyla duruyor: geri yükledikten sonra adın "
              "sonundaki “.orig” kısmını sil ki Rosu onları yeniden görsün. (Bu "
              "sürümden önce kırpılan setler “tmp…….osz.orig” olarak görünebilir; "
              "Orijinal Konum sütunu yine de Kütüphaneden geldiklerini gösterir.)"},
    "restore_recycle_manual": {
        "en": "Rosu could not open the Recycle Bin on this system — open it "
              "yourself and restore the files from there. Library originals are "
              "named “<set>.osz.orig”; remove the “.orig” after restoring.",
        "tr": "Rosu bu sistemde Geri Dönüşüm Kutusu'nu açamadı — kendin açıp "
              "dosyaları oradan geri yükle. Kütüphane orijinalleri “<set>.osz.orig” "
              "adıyla duruyor; geri yükledikten sonra “.orig” kısmını sil."},
    "sc_restore_none": {
        "en": "No pruned sets — there is nothing to restore.",
        "tr": "Kırpılmış set yok — geri getirilecek bir şey yok."},
    "sc_restore_confirm": {
        "en": "Re-download {n} pruned set(s) at full size from a third-party osu! "
              "mirror (not the official osu! servers)? This replaces the pruned "
              "file in your Library with the complete set, and can take a while "
              "and a lot of bandwidth. You can cancel it from the queue.",
        "tr": "{n} kırpılmış set, üçüncü taraf bir osu! aynasından (resmî osu! "
              "sunucularından değil) tam boyutuyla yeniden indirilsin mi? Bu, "
              "Kütüphanendeki kırpılmış dosyanın yerine setin tamamını koyar; "
              "uzun sürebilir ve çok veri harcayabilir. Kuyruktan iptal edebilirsin."},
    "sc_restore_done": {"en": "Restored {n} set(s) at full size.",
                        "tr": "{n} set tam boyutuyla geri getirildi."},
    "sc_restore_partial": {
        "en": "Restored {n} set(s); {failed} could not be downloaded (the mirror "
              "may not have them).",
        "tr": "{n} set geri getirildi; {failed} tanesi indirilemedi (aynada "
              "bulunmuyor olabilir)."},
    "sc_restore_failed": {
        "en": "Nothing could be restored ({failed} attempted). The mirror may be "
              "down, or those sets may no longer exist on osu!.",
        "tr": "Hiçbir şey geri getirilemedi ({failed} denendi). Ayna kapalı "
              "olabilir ya da bu setler artık osu!'da bulunmuyor olabilir."},

    # -- v1.7.1: guided osu!lazer slim-down ---------------------------------
    "btn_lazer_slim": {"en": "Prune osu!lazer…", "tr": "osu!lazer'ı kırp…"},
    "tip_lazer_slim": {
        "en": "osu!lazer cannot be pruned in place, so this walks you through the "
              "round-trip that does the same job safely: save everything into the "
              "Library, delete the beatmaps inside lazer yourself, prune the "
              "Library, then send it all back. Every step is explained and "
              "confirmed before it runs.",
        "tr": "osu!lazer yerinde kırpılamaz; bu yüzden bu sihirbaz aynı işi güvenle "
              "yapan gidiş-dönüş yolunu adım adım anlatır: her şeyi Kütüphaneye "
              "kaydet, lazer içindeki haritaları kendin sil, Kütüphaneyi kırp, "
              "sonra hepsini geri gönder. Her adım çalışmadan önce açıklanır ve "
              "onaylanır."},
    "lazer_slim_title": {"en": "Prune osu!lazer", "tr": "osu!lazer'ı kırp"},
    "lazer_slim_skip": {"en": "Skip this step", "tr": "Bu adımı atla"},
    "lazer_slim_finish": {"en": "Finish", "tr": "Bitir"},

    "lazer_slim_h_intro": {"en": "How pruning osu!lazer works",
                           "tr": "osu!lazer'ı kırpmak nasıl oluyor"},
    "lazer_slim_b_intro": {
        "en": "osu!lazer stores every file under a content hash and shares ONE "
              "copy between all sets that contain the same asset, so Rosu cannot "
              "simply delete videos out of it — that would break other sets and "
              "leave lazer's database pointing at files that no longer exist.\n\n"
              "So pruning lazer means going the long way round — these steps ARE "
              "the prune:\n\n"
              "1.  Save every beatmap in lazer into your Rosu Library.\n"
              "2.  You delete the beatmaps inside lazer (only lazer's own code may "
              "touch its database — Rosu will tell you exactly where the button is).\n"
              "3.  Rosu checks that lazer's files really went.\n"
              "4.  Prune the Library — strip video and/or images. Optional.\n"
              "5.  Send the slimmed Library back into lazer.\n\n"
              "Nothing happens until you press the button on each step, and your "
              "Library keeps a full copy the whole time.",
        "tr": "osu!lazer her dosyayı içerik özetine göre saklar ve aynı dosyayı "
              "içeren TÜM setler arasında TEK bir kopyayı paylaşır. Bu yüzden Rosu "
              "onun içinden öylece video silemez — bu, başka setleri bozar ve "
              "lazer'in veritabanı artık var olmayan dosyaları göstermeye devam eder."
              "\n\nBu yüzden lazer'ı kırpmak uzun yoldan geçmek demek — bu adımlar "
              "kırpma işleminin TA KENDİSİ:\n\n"
              "1.  lazer'daki her beatmap'i Rosu Kütüphanene kaydet.\n"
              "2.  lazer içindeki haritaları sen sil (veritabanına yalnızca "
              "lazer'in kendi kodu dokunabilir — Rosu tuşun tam olarak nerede "
              "olduğunu söyleyecek).\n"
              "3.  Rosu lazer'in dosyalarının gerçekten gittiğini kontrol eder.\n"
              "4.  Kütüphaneyi kırp — video ve/veya görselleri at. İsteğe bağlı.\n"
              "5.  İncelen Kütüphaneyi lazer'a geri gönder.\n\n"
              "Her adımda tuşa basmadan hiçbir şey olmaz ve Kütüphanen bu süre "
              "boyunca tam kopyayı korur."},
    "lazer_slim_btn_intro": {"en": "Start — save lazer into the Library",
                             "tr": "Başla — lazer'ı Kütüphaneye kaydet"},

    "lazer_slim_h_save": {"en": "Step 1 — saving lazer into your Library",
                          "tr": "Adım 1 — lazer Kütüphaneye kaydediliyor"},
    "lazer_slim_b_save": {
        "en": "Rosu is re-exporting every beatmap set out of lazer and adding the "
              "ones you don't already have to your Library. Nothing in lazer is "
              "modified — its database is only ever read.\n\nOn a big collection "
              "this takes minutes, and it needs temporary disk space roughly the "
              "size of your lazer collection (the sets are rebuilt in your temp "
              "folder first, then moved into the Library). Make sure the drive "
              "holding %TEMP% has room.",
        "tr": "Rosu, lazer'daki her beatmap setini yeniden dışa aktarıp sende "
              "olmayanları Kütüphanene ekliyor. lazer'da hiçbir şey değiştirilmez — "
              "veritabanı yalnızca okunur.\n\nBüyük bir koleksiyonda bu dakikalar "
              "sürer ve kabaca lazer koleksiyonun kadar geçici disk alanı ister "
              "(setler önce geçici klasörde yeniden oluşturulur, sonra Kütüphaneye "
              "taşınır). %TEMP% klasörünün olduğu diskte yer olduğundan emin ol."},
    "lazer_slim_btn_save": {"en": "Retry", "tr": "Tekrar dene"},
    "lazer_slim_saving": {"en": "Reading osu!lazer…", "tr": "osu!lazer okunuyor…"},
    "lazer_slim_saved": {
        "en": "✓ All {total} set(s) from lazer are confirmed in your Library "
              "({new} of them new). lazer's file store is currently {size} — "
              "remember that number for the next step.",
        "tr": "✓ lazer'daki {total} setin tamamının Kütüphanende olduğu doğrulandı "
              "({new} tanesi yeni). lazer'in dosya deposu şu an {size} — sonraki "
              "adım için bu sayıyı aklında tut."},
    "lazer_slim_not_all_saved": {
        "en": "STOP — {n} set(s) from lazer did NOT reach your Library "
              "({names}). Do not delete anything in lazer yet: they would be "
              "lost. Close lazer completely and press Retry.",
        "tr": "DUR — lazer'daki {n} set Kütüphanene ULAŞMADI ({names}). lazer'da "
              "henüz hiçbir şey silme: onlar kaybolur. lazer'ı tamamen kapat ve "
              "Tekrar dene'ye bas."},
    "lazer_slim_nothing_there": {
        "en": "osu!lazer has no beatmaps to save — there is nothing to prune here.",
        "tr": "osu!lazer'da kaydedilecek beatmap yok — burada kırpılacak bir şey yok."},
    "lazer_slim_not_found": {
        "en": "osu!lazer was not found on this computer.",
        "tr": "Bu bilgisayarda osu!lazer bulunamadı."},
    "lazer_slim_disabled": {
        "en": "osu!lazer is turned off in Settings — turn it on first.",
        "tr": "osu!lazer Ayarlar'da kapalı — önce açman gerekiyor."},
    "lazer_slim_save_failed": {
        "en": "Could not read osu!lazer. Close lazer completely and try again — "
              "its database is locked while it is running.",
        "tr": "osu!lazer okunamadı. lazer'ı tamamen kapatıp tekrar dene — çalışırken "
              "veritabanı kilitli oluyor."},
    "lazer_slim_cancelled": {
        "en": "Cancelled. Nothing was changed anywhere.",
        "tr": "İptal edildi. Hiçbir yerde hiçbir şey değişmedi."},
    "lazer_slim_helper_missing": {
        "en": "Rosu's osu!lazer reader (RosuLazerExport.exe) is missing from this "
              "install, so lazer cannot be read at all. Closing lazer will not "
              "help. Re-install Rosu, or run it from a complete copy.",
        "tr": "Rosu'nun osu!lazer okuyucusu (RosuLazerExport.exe) bu kurulumda yok, "
              "bu yüzden lazer hiç okunamıyor. lazer'ı kapatmak işe yaramaz. "
              "Rosu'yu yeniden kur ya da eksiksiz bir kopyadan çalıştır."},

    "lazer_slim_h_delete": {"en": "Step 2 — now delete them inside lazer",
                            "tr": "Adım 2 — şimdi lazer içinden sil"},
    "lazer_slim_b_delete": {
        "en": "Your maps are safe in the Library now. Delete them from lazer "
              "yourself — Rosu deliberately does not touch lazer's database:\n\n"
              "1.  Open osu!lazer.\n"
              "2.  Settings  →  Maintenance.\n"
              "3.  Press “Delete ALL beatmaps” and confirm.\n"
              "4.  Close osu!lazer completely.\n\n"
              "Then come back here and press Check. Rosu will measure lazer's file "
              "store and tell you whether it really emptied.",
        "tr": "Haritaların artık Kütüphanede güvende. lazer'dan silmeyi sen yap — "
              "Rosu, lazer'in veritabanına bilerek dokunmuyor:\n\n"
              "1.  osu!lazer'ı aç.\n"
              "2.  Settings (Ayarlar)  →  Maintenance (Bakım).\n"
              "3.  “Delete ALL beatmaps” tuşuna bas ve onayla.\n"
              "4.  osu!lazer'ı tamamen kapat.\n\n"
              "Sonra buraya dön ve Kontrol et'e bas. Rosu lazer'in dosya deposunu "
              "ölçüp gerçekten boşalıp boşalmadığını söyleyecek."},
    "lazer_slim_btn_delete": {"en": "Check — did they go?",
                              "tr": "Kontrol et — gitti mi?"},
    "lazer_slim_emptied": {
        "en": "✓ lazer's file store went from {before} to {after}. Looks done.",
        "tr": "✓ lazer'in dosya deposu {before} → {after} oldu. Görünüşe göre oldu."},
    "lazer_slim_still_there": {
        "en": "lazer's file store is still {after} (it was {before}). It does not "
              "look like the beatmaps were deleted — or lazer has not finished "
              "cleaning up yet. Close lazer completely and check again.",
        "tr": "lazer'in dosya deposu hâlâ {after} (önce {before} idi). Haritalar "
              "silinmiş görünmüyor — ya da lazer temizliği henüz bitirmedi. "
              "lazer'ı tamamen kapatıp tekrar kontrol et."},
    "lazer_slim_force_continue": {
        "en": "Rosu could not confirm the beatmaps were deleted. Only you can see "
              "lazer's screen — continue anyway?",
        "tr": "Rosu haritaların silindiğini doğrulayamadı. lazer'in ekranını "
              "yalnızca sen görüyorsun — yine de devam edilsin mi?"},

    "lazer_slim_h_prune": {"en": "Step 3 — prune the Library (optional)",
                           "tr": "Adım 3 — Kütüphaneyi kırp (isteğe bağlı)"},
    "lazer_slim_b_prune": {
        "en": "This is the actual space saving. Opening Prune lets you choose what "
              "to strip (video only, images only, or both) and how many sets, with "
              "a preview of exactly what would go. Whatever you strip here is what "
              "lazer gets back in the last step.\n\n"
              "You can skip this and simply put everything back unchanged.",
        "tr": "Asıl yer kazancı burada. Prune'u açtığında neyin çıkarılacağını "
              "(sadece video, sadece görsel ya da ikisi) ve kaç set olacağını, tam "
              "olarak neyin gideceğinin önizlemesiyle seçersin. Burada ne "
              "çıkarırsan son adımda lazer'a o gider.\n\n"
              "Bu adımı atlayıp her şeyi olduğu gibi geri koyabilirsin de."},
    "lazer_slim_btn_prune": {"en": "Open Prune…", "tr": "Prune'u aç…"},
    "lazer_slim_prune_queued": {
        "en": "Prune queued for {n} set(s) — let it finish in the job queue before "
              "sending everything back.",
        "tr": "{n} set için kırpma kuyruğa alındı — her şeyi geri göndermeden önce "
              "iş kuyruğunda bitmesini bekle."},
    "lazer_slim_prune_skipped": {"en": "Prune skipped — nothing was stripped.",
                                 "tr": "Kırpma atlandı — hiçbir şey çıkarılmadı."},

    "lazer_slim_h_send": {"en": "Step 4 — send the Library back to lazer",
                          "tr": "Adım 4 — Kütüphaneyi lazer'a geri gönder"},
    "lazer_slim_b_send": {
        "en": "Rosu will hand every Library set to osu!lazer to import. lazer opens "
              "and does the importing itself, so give it time — and let it finish "
              "before you start playing.\n\n"
              "If you queued a prune in the previous step, wait for it to finish "
              "first, otherwise lazer gets the un-pruned files.",
        "tr": "Rosu, Kütüphanedeki her seti içe aktarması için osu!lazer'a verecek. "
              "İçe aktarmayı lazer kendisi yapar, o yüzden ona zaman tanı — ve "
              "oynamaya başlamadan önce bitmesini bekle.\n\n"
              "Önceki adımda kırpma kuyruğa aldıysan önce onun bitmesini bekle, "
              "yoksa lazer'a kırpılmamış dosyalar gider."},
    "lazer_slim_btn_send": {"en": "Send everything to lazer",
                            "tr": "Her şeyi lazer'a gönder"},
    "lazer_slim_send_confirm": {
        "en": "Hand your whole Library to osu!lazer to import? lazer will open and "
              "import in batches; this can take a long time on a big Library.",
        "tr": "Tüm Kütüphanen içe aktarılmak üzere osu!lazer'a verilsin mi? lazer "
              "açılıp parti parti içe aktaracak; büyük bir Kütüphanede bu uzun sürebilir."},
    "lazer_slim_sending": {"en": "Handing sets to osu!lazer…",
                           "tr": "Setler osu!lazer'a veriliyor…"},
    "lazer_slim_sent": {"en": "✓ {sent} set(s) handed to osu!lazer.",
                        "tr": "✓ {sent} set osu!lazer'a verildi."},

    "lazer_slim_h_done": {"en": "Done", "tr": "Bitti"},
    "lazer_slim_b_done": {
        "en": "osu!lazer is importing the sets you sent. Once it finishes, your "
              "collection is back — minus whatever you chose to strip.\n\n"
              "Changed your mind about the videos? Shortcuts → “Restore pruned "
              "maps” re-downloads every pruned set at full size.",
        "tr": "osu!lazer gönderdiğin setleri içe aktarıyor. Bitince koleksiyonun "
              "geri gelmiş olacak — çıkarmayı seçtiğin şeyler hariç.\n\n"
              "Videolar konusunda fikrin mi değişti? Kısayollar → “Kırpılmışları "
              "geri getir” her kırpılmış seti tam boyutuyla yeniden indirir."},
    "lazer_slim_btn_done": {"en": "Finish", "tr": "Bitir"},

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
    "btn_prune": {"en": "Prune Library (save space)", "tr": "Alan Tasarrufu (Prune)"},
    "tip_prune": {
        "en": "Recycle heavy, non-essential files (video, or video+images) from "
              "Library .osz — the map stays playable. Sends the originals to the "
              "Recycle Bin (recoverable).",
        "tr": "Library'deki .osz'lerden gereksiz ağır dosyaları (video, veya "
              "video+görsel) Geri Dönüşüm'e gönderir — harita çalınabilir kalır. "
              "Orijinaller kurtarılabilir."},
    "sc_prune_none": {"en": "No maps to prune.", "tr": "Kırpılacak harita bulunamadı."},
    "sc_prune_confirm": {
        "en": "{count} map(s) will be pruned (about {freed} freed). This "
              "permanently removes video/background files from the .osz — the "
              "originals go to the Recycle Bin (recoverable). Continue?",
        "tr": "{count} harita kırpılacak (yaklaşık {freed} boşalacak). Bu, .osz "
              "içinden video/arkaplan dosyalarını kalıcı olarak kaldırır — "
              "orijinaller Geri Dönüşüm Kutusu'na gider (kurtarılabilir). Devam "
              "edilsin mi?"},
    "sc_prune_done": {"en": "Pruned {pruned} map(s), freed {freed}.",
                      "tr": "{pruned} harita kırpıldı. {freed} alan açıldı."},
    # Not "Prune Library" any more — the same job also prunes osu!(stable), and
    # the row's detail line names the source.
    "job_prune": {"en": "Space saving (Prune)", "tr": "Alan Tasarrufu (Prune)"},
    "job_restore_pruned": {"en": "Restore pruned maps",
                           "tr": "Kırpılmış haritaları geri getir"},
    "job_step_restore": {"en": "Re-download from an osu! mirror",
                         "tr": "osu! aynasından yeniden indir"},
    "job_step_prune_scan": {"en": "Scan for heavy assets", "tr": "Ağır dosyaları tara"},
    "job_step_prune_remove": {"en": "Trim heavy assets", "tr": "Ağır dosyaları kırp"},

    "set_auto_prune": {"en": "Auto-Prune (strip heavy assets from new maps)",
                       "tr": "Otomatik Kırp (yeni haritaları otomatik kırp)"},
    "tip_auto_prune": {
        "en": "When a new map is added to the Library, automatically prune it "
              "(see Prune Mode below).",
        "tr": "Yeni bir harita Kütüphane'ye eklendiğinde otomatik olarak kırpar "
              "(aşağıdaki Prune Modu'na göre)."},
    "set_export_prune": {"en": "Export Prune (prune on the fly when exporting)",
                         "tr": "Dışa Aktarımda Kırp (osu!'ya aktarırken anlık kırp)"},
    "tip_export_prune": {
        "en": "Library files stay untouched — only the copy sent to osu! or "
              "exported to a folder/archive is pruned.",
        "tr": "Kütüphanedeki dosyalar bozulmaz — yalnızca osu!'ya veya bir "
              "klasöre/arşive aktarılan kopya kırpılır."},
    "lbl_prune_mode": {"en": "Prune mode:", "tr": "Prune Modu:"},

    # -- v1.7.1: the Prune dialog (source · mode · order · limit · preview) ---
    "prune_title": {"en": "Space saving (Prune)", "tr": "Alan Tasarrufu (Prune)"},
    "prune_intro": {
        "en": "Removes the heavy extras from beatmap sets — the beatmaps "
              "themselves (.osu) are never touched, so every map still plays. "
              "Pick what to strip, preview exactly what would go, then confirm.",
        "tr": "Beatmap setlerindeki ağır ekleri kaldırır — beatmap dosyalarının "
              "(.osu) kendisine asla dokunulmaz, yani her harita oynanmaya devam "
              "eder. Neyin çıkacağını seç, tam olarak ne gideceğini önizle, sonra "
              "onayla."},
    "prune_source": {"en": "Where:", "tr": "Nerede:"},
    "prune_source_library": {"en": "Rosu Library", "tr": "Rosu Kütüphanesi"},
    "prune_source_stable": {"en": "osu!(stable)", "tr": "osu!(stable)"},
    "prune_source_lazer": {"en": "osu!lazer", "tr": "osu!lazer"},
    "prune_n_sets": {"en": "{n} set(s)", "tr": "{n} set"},
    "prune_frees": {"en": "frees {size}", "tr": "{size} kazandırır"},
    "prune_why_no_stable": {
        "en": "osu!(stable) was not found (or is turned off in Settings), so there "
              "is nothing here to prune.",
        "tr": "osu!(stable) bulunamadı (ya da Ayarlar'da kapalı), bu yüzden burada "
              "kırpılacak bir şey yok."},
    "prune_why_lazer_realm": {
        "en": "osu!lazer cannot be pruned from here, and that is not a setting: it "
              "stores every file by content hash and SHARES one copy between all "
              "sets containing the same asset, so removing one set's video would "
              "break other sets and leave lazer's database pointing at a file "
              "that no longer exists.\n\nIt CAN still be pruned — just the long "
              "way round: save it into the Library, delete the beatmaps inside "
              "lazer, prune the Library, send it back. Those steps are right "
              "here.",
        "tr": "osu!lazer buradan kırpılamaz ve bu bir tercih değil: her dosyayı "
              "içerik özetine göre saklar ve aynı dosyayı içeren TÜM setler "
              "arasında tek bir kopyayı PAYLAŞIR. Yani bir setin videosunu silmek "
              "başka setleri bozar ve lazer'in veritabanı artık var olmayan bir "
              "dosyayı göstermeye devam eder.\n\nYine de kırpılabilir — sadece uzun "
              "yoldan: Kütüphaneye kaydet, lazer içindeki haritaları sil, "
              "Kütüphaneyi kırp, geri gönder. O adımlar tam burada."},
    "prune_open_lazer_steps": {
        "en": "Open the osu!lazer prune steps…",
        "tr": "osu!lazer kırpma adımlarını aç…"},
    "prune_mode": {"en": "Remove:", "tr": "Kaldırılacak:"},
    "prune_mode_video_only": {"en": "Video only (safe)", "tr": "Sadece video (güvenli)"},
    "prune_mode_video_only_tip": {
        "en": "Removes only video files. Backgrounds, audio and hitsounds stay — "
              "this is the safest option and usually frees the most.",
        "tr": "Yalnızca video dosyalarını kaldırır. Arka planlar, ses ve hitsound'lar "
              "kalır — en güvenli seçenek ve genelde en çok yeri o açar."},
    "prune_mode_images_only": {"en": "Images only", "tr": "Sadece görseller"},
    "prune_mode_images_only_tip": {
        "en": "Removes image files — INCLUDING each map's background. Pick this "
              "only if you play with backgrounds off. Audio and video are kept.",
        "tr": "Görsel dosyaları kaldırır — haritaların ARKA PLANI DAHİL. Bunu "
              "yalnızca arka planları kapalı oynuyorsan seç. Ses ve video kalır."},
    "prune_mode_video_and_images": {"en": "Video + images",
                                    "tr": "Video + görseller"},
    "prune_mode_video_and_images_tip": {
        "en": "Removes both video and image files (backgrounds included). Audio "
              "and the beatmaps themselves are kept.",
        "tr": "Hem video hem görsel dosyalarını kaldırır (arka planlar dahil). Ses "
              "ve beatmap'lerin kendisi kalır."},
    "prune_mode_heavy_assets": {"en": "Smart clean-up",
                                "tr": "Akıllı temizlik"},
    "prune_mode_heavy_assets_tip": {
        "en": "Keeps whatever a beatmap actually references (its audio and its "
              "background) plus small images and hitsounds, and drops the rest — "
              "video, storyboard scripts (.osb) and unused images over 500 KB.",
        "tr": "Bir beatmap'in gerçekten kullandığı şeyleri (sesi ve arka planı) "
              "artı küçük görselleri ve hitsound'ları tutar, gerisini atar — video, "
              "storyboard betikleri (.osb) ve 500 KB üstü kullanılmayan görseller."},
    "prune_order": {"en": "Order:", "tr": "Sıralama:"},
    "prune_sort_largest": {"en": "Biggest saving first",
                           "tr": "En çok yer açan önce"},
    "prune_sort_smallest": {"en": "Smallest saving first",
                            "tr": "En az yer açan önce"},
    "prune_sort_name": {"en": "By name", "tr": "İsme göre"},
    "prune_limit": {"en": "How many:", "tr": "Kaç tane:"},
    "prune_limit_all": {"en": "All of them", "tr": "Hepsi"},
    "prune_limit_tip": {
        "en": "Prune only this many sets, taken from the top of the order above. "
              "0 means all of them.",
        "tr": "Yukarıdaki sıralamanın başından yalnızca bu kadar seti kırp. 0 = hepsi."},
    "prune_scan": {"en": "Rescan", "tr": "Yeniden tara"},
    "prune_scanning": {"en": "Checking what could be removed…",
                       "tr": "Neyin kaldırılabileceği kontrol ediliyor…"},
    "prune_scanning_n": {"en": "Checking… {done}/{total}",
                         "tr": "Kontrol ediliyor… {done}/{total}"},
    "prune_scanned": {
        "en": "Checked {scanned} set(s), {n} have something to remove. "
              "{size} in total on disk.",
        "tr": "{scanned} set kontrol edildi, {n} tanesinde kaldırılacak bir şey var. "
              "Diskte toplam {size}."},
    "prune_no_source": {
        "en": "Nothing here can be pruned right now.",
        "tr": "Şu anda burada kırpılabilecek bir şey yok."},
    "prune_col_freed": {"en": "Would free", "tr": "Kazanılacak"},
    "prune_show_list": {"en": "Show the list of sets",
                        "tr": "Set listesini göster"},
    "prune_show_list_tip": {
        "en": "Lists every set that would change, with its size and how much it "
              "would free. Hidden by default — the totals above are what you "
              "decide from; the list is here for when you want to check.",
        "tr": "Değişecek her seti, boyutunu ve kazandıracağı yeri listeler. "
              "Varsayılan olarak gizli — kararı yukarıdaki toplamlara göre "
              "veriyorsun; liste kontrol etmek istediğinde burada."},
    "prune_total": {"en": "{n} set(s) selected · {size} would be freed",
                    "tr": "{n} set seçildi · {size} kazanılacak"},
    "prune_run": {"en": "Prune", "tr": "Kırp"},
    "prune_run_n": {"en": "Prune {n} set(s)", "tr": "{n} seti kırp"},
    "prune_confirm_body": {
        "en": "About to prune {n} set(s) in {source} using “{mode}”, freeing about "
              "{size}.\n\nThis changes files. {recovery}\n\nMake sure osu! is "
              "closed first.",
        "tr": "{source} içinde {n} set “{mode}” ile kırpılacak, yaklaşık {size} "
              "kazanılacak.\n\nBu işlem dosyaları değiştirir. {recovery}\n\nÖnce "
              "osu!'nun kapalı olduğundan emin ol."},
    "prune_recovery_osz": {
        "en": "Each original .osz goes to the Recycle Bin first, and any pruned set "
              "can be re-downloaded later from Search (right-click → Repair).",
        "tr": "Her orijinal .osz önce Geri Dönüşüm Kutusu'na gider ve kırpılan her "
              "set daha sonra Arama'dan yeniden indirilebilir (sağ tık → Onar)."},
    "prune_recovery_folder": {
        "en": "The removed files go to the Recycle Bin, so you can put them back "
              "from there. The .osu beatmap files are never removed.",
        "tr": "Kaldırılan dosyalar Geri Dönüşüm Kutusu'na gider, oradan geri "
              "alabilirsin. .osu beatmap dosyaları asla kaldırılmaz."},

    "btn_sync_coll": {"en": "Sync Collections", "tr": "Koleksiyonları Eşitle"},
    "tip_sync_coll": {
        "en": "Reads osu!(stable)'s collection.db and tags matching Library maps "
              "with their collection name.",
        "tr": "osu!(stable) collection.db dosyasını okuyup eşleşen Kütüphane "
              "haritalarını koleksiyon adıyla etiketler."},
    "sync_coll_no_stable": {
        "en": "collection.db not found. Make sure osu!(stable) is installed and "
              "its path is set in Settings.",
        "tr": "collection.db bulunamadı. osu!(stable)'ın kurulu olduğundan ve "
              "yolunun Ayarlar'da tanımlı olduğundan emin ol."},
    "sync_coll_done": {
        "en": "Tagged {tagged} map(s) from {collections} collection(s).",
        "tr": "{collections} koleksiyondan toplam {tagged} harita etiketlendi."},

    "repair_confirm_title": {"en": "Repair confirmation", "tr": "Onarım Onayı"},
    "repair_confirm_body": {
        "en": "{filename} will be re-downloaded from a third-party osu! mirror, "
              "not the official osu! servers. As with any beatmap archive, this "
              "may contain third-party copyrighted audio and artwork — you are "
              "responsible for what you download. Continue?",
        "tr": "{filename} resmi olmayan bir üçüncü taraf osu! mirror'ından yeniden "
              "indirilecek (resmi osu! sunucuları değil). Diğer beatmap "
              "arşivlerinde olduğu gibi bu da üçüncü taraf telifli ses/görsel "
              "içerebilir — indirdiğin içerikten sen sorumlusun. Devam edilsin mi?"},
    "repair_done": {"en": "{repaired} map(s) repaired.",
                    "tr": "{repaired} harita onarıldı."},
    "repair_partial": {"en": "{repaired} map(s) repaired, {failed} could not be downloaded.",
                       "tr": "{repaired} harita onarıldı, {failed} harita indirilemedi."},
    "repair_none": {"en": "Could not download any of the selected map(s).",
                    "tr": "Seçilen haritaların hiçbiri indirilemedi."},

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
    "menu_repair": {"en": "Download original (mirror repair)",
                   "tr": "Orijinalini indir (mirror onarımı)"},

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
        "en": "Sent to the Rosu team: your text, your contact e-mail if you "
              "provide one, the app version, your OS and UI language, and any "
              "screenshot you attach (plus, on the server, a hashed form of your "
              "IP address to limit spam). Nothing is sent until you press Send.",
        "tr": "Rosu ekibine gönderilir: yazdıkların, verirsen iletişim e-postan, "
              "uygulama sürümü, işletim sistemin ve arayüz dilin, ve eklediğin "
              "ekran görüntüsü (ayrıca sunucuda, spam'i sınırlamak için IP "
              "adresinin hash'lenmiş bir hâli). Gönder'e basana kadar hiçbir şey "
              "gönderilmez."},
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
    # -- v1.8: remove from a client (HANDOFF 4.1) ------------------------------
    "btn_remove_from_client": {"en": "Remove from osu!…", "tr": "osu!'dan Kaldır…"},
    "tip_remove_from_client": {
        "en": "Take beatmap sets out of osu!(stable) or osu!lazer — saving them to the "
              "Library first if you want. Shows exactly what goes before anything is touched.",
        "tr": "osu!(stable) veya osu!lazer'dan beatmap setlerini kaldırır — istersen önce "
              "Library'e kaydeder. Hiçbir şeye dokunmadan önce tam olarak neyin gideceğini gösterir."},
    "tip_history_back": {"en": "Previous search (Alt+←)", "tr": "Önceki arama (Alt+←)"},
    "tip_history_forward": {"en": "Next search (Alt+→)", "tr": "Sonraki arama (Alt+→)"},

    # -- v1.9: Library → Output staging --------------------------------------------
    "menu_stage_output": {"en": "Copy to Output (for Import to osu!)",
                          "tr": "Output'a kopyala (osu!'ya aktarmak için)"},
    "stage_output_done": {
        "en": "Copied {n} sets to Output ({already} already there, {skipped} skipped). Use "
              "Import to osu! on the Dashboard to send them.",
        "tr": "{n} set Output'a kopyalandı ({already} tanesi zaten oradaydı, {skipped} "
              "atlandı). Göndermek için Gösterge Paneli'nde osu!'ya Aktar'ı kullan."},

    # -- v1.10: same song, different sets ---------------------------------------------
    "btn_same_song": {"en": "Same song, different sets…", "tr": "Aynı şarkı, farklı setler…"},
    "tip_same_song": {
        "en": "Find Library sets that use the same song — re-encodes, re-uploads, TV-size "
              "cuts — by listening to the audio itself, and recycle the ones you pick.",
        "tr": "Aynı şarkıyı kullanan Library setlerini — yeniden kodlamalar, yeniden "
              "yüklemeler, TV-boyu kesimler — sesin kendisine bakarak bul ve seçtiklerini geri "
              "dönüşüme gönder."},
    "ss_title": {"en": "Same song, different sets", "tr": "Aynı şarkı, farklı setler"},
    "ss_intro": {
        "en": "Rosu fingerprints each Library set's audio (the first two minutes) and groups "
              "the sets whose songs match. Different sets of one song are often different "
              "maps worth keeping: nothing is selected for you, and one set of every song "
              "always stays.",
        "tr": "Rosu her Library setinin sesinin parmak izini çıkarır (ilk iki dakika) ve "
              "şarkısı eşleşen setleri gruplar. Bir şarkının farklı setleri çoğu zaman "
              "saklamaya değer farklı haritalardır: senin yerine hiçbir şey seçilmez ve her "
              "şarkıdan bir set daima kalır."},
    "ss_scan": {"en": "Scan again", "tr": "Yeniden tara"},
    "ss_scanning": {"en": "Listening to the Library…", "tr": "Library dinleniyor…"},
    "ss_scanning_n": {"en": "Fingerprinting {done} of {total} new sets…",
                      "tr": "{total} yeni setin {done} tanesinin parmak izi çıkarılıyor…"},
    "ss_no_fpcalc": {
        "en": "This build has no fpcalc (the audio fingerprint tool). Running from source: "
              "python tools/fetch_fpcalc.py",
        "tr": "Bu sürümde fpcalc (ses parmak izi aracı) yok. Kaynaktan çalıştırıyorsan: "
              "python tools/fetch_fpcalc.py"},
    "ss_summary": {
        "en": "{groups} songs appear in more than one set ({sets} sets); {checked} sets "
              "checked.",
        "tr": "{groups} şarkı birden fazla sette var ({sets} set); {checked} set kontrol "
              "edildi."},
    "ss_unreadable": {"en": "{n} sets have audio that could not be read.",
                      "tr": "{n} setin sesi okunamadı."},
    "ss_retry": {"en": "{n} sets could not be checked this time (they are tried again next scan).",
                 "tr": "{n} set bu sefer kontrol edilemedi (bir sonraki taramada yeniden denenir)."},
    "ss_fpcalc_broken": {
        "en": "The audio fingerprint tool (fpcalc) does not start. An antivirus may have blocked "
              "or quarantined it — allow it, or reinstall Rosu, then scan again.",
        "tr": "Ses parmak izi aracı (fpcalc) başlamıyor. Bir antivirüs onu engellemiş ya da "
              "karantinaya almış olabilir — izin ver ya da Rosu'yu yeniden kur, sonra yeniden tara."},
    "ss_group": {"en": "{name} — {n} sets", "tr": "{name} — {n} set"},
    "ss_col_diffs": {"en": "Difficulties", "tr": "Zorluklar"},
    "ss_select_extras": {"en": "Select extras", "tr": "Fazlalıkları seç"},
    "tip_ss_select_extras": {
        "en": "In every group, select all sets but the one with the most difficulties.",
        "tr": "Her grupta, en çok zorluğu olan set dışındaki tüm setleri seç."},
    "ss_recycle": {"en": "Recycle", "tr": "Geri dönüşüme gönder"},
    "ss_recycle_n": {"en": "Recycle {n} sets", "tr": "{n} seti geri dönüşüme gönder"},
    "ss_keep_one": {
        "en": "Every set of one song is selected — leave at least one per song.",
        "tr": "Bir şarkının tüm setleri seçili — her şarkıdan en az birini bırak."},
    "ss_confirm": {
        "en": "Send {n} Library sets ({size}) to the Recycle Bin?\n\nThey can be restored "
              "from there. The other sets of each song stay.",
        "tr": "{n} Library seti ({size}) Geri Dönüşüm Kutusu'na gönderilsin mi?\n\nOradan "
              "geri yüklenebilirler. Her şarkının diğer setleri kalır."},
    "job_same_song_recycle": {"en": "Recycle same-song sets", "tr": "Aynı şarkı setlerini geri dönüştür"},

    # -- v1.9: watch folder ------------------------------------------------------------
    "set_watch": {"en": "Watch a folder", "tr": "Bir klasörü izle"},
    "set_watch_folder": {"en": "Folder for new .osz downloads (e.g. Downloads)",
                         "tr": "Yeni .osz indirmelerinin klasörü (ör. İndirilenler)"},
    "tip_watch": {
        "en": "New .osz files that appear in this folder are added to the Library (ones "
              "that arrive while Rosu is closed, the next time it starts). Files already "
              "there when you turn this on are left alone, and your files are never moved "
              "or deleted.",
        "tr": "Bu klasöre gelen yeni .osz dosyaları Library'e eklenir (Rosu kapalıyken "
              "gelenler, bir sonraki açılışta). Bu ayarı açtığınızda klasörde olan "
              "dosyalara dokunulmaz; dosyalarınız asla taşınmaz ya da silinmez."},
    "job_watch_import": {"en": "Add new downloads", "tr": "Yeni indirmeleri ekle"},
    "job_step_watch_import": {"en": "Import into the Library", "tr": "Library'e aktar"},
    "watch_n_files": {"en": "{n} new files", "tr": "{n} yeni dosya"},
    "watch_done": {"en": "Watched folder: {new} new sets added ({files} files).",
                   "tr": "İzlenen klasör: {new} yeni set eklendi ({files} dosya)."},

    # -- v1.9: move the Library -----------------------------------------------------
    "btn_move_library": {"en": "Move Library…", "tr": "Library'yi Taşı…"},
    "tip_move_library": {
        "en": "Move the Library to another folder or drive. Every file is copied and "
              "checked before Rosu switches to the new folder.",
        "tr": "Library'yi başka bir klasöre ya da sürücüye taşı. Rosu yeni klasöre "
              "geçmeden önce her dosya kopyalanır ve kontrol edilir."},
    "mv_title": {"en": "Move the Library", "tr": "Library'yi Taşı"},
    "mv_intro": {
        "en": "Every file is copied to the new folder and checked byte for byte; only "
              "then does Rosu switch to it. If anything goes wrong, nothing changes.",
        "tr": "Her dosya yeni klasöre kopyalanır ve bayt bayt kontrol edilir; Rosu ancak "
              "ondan sonra oraya geçer. Bir şey ters giderse hiçbir şey değişmez."},
    "mv_current": {"en": "Current Library: {path}", "tr": "Şu anki Library: {path}"},
    "mv_dest_placeholder": {"en": "New Library folder…", "tr": "Yeni Library klasörü…"},
    "mv_checking": {"en": "Checking the destination…", "tr": "Hedef kontrol ediliyor…"},
    "mv_plan": {"en": "{n} files ({size}) will be copied. Free space there: {free}.",
                "tr": "{n} dosya ({size}) kopyalanacak. Oradaki boş alan: {free}."},
    "mv_plan_same": {"en": "{n} of them are already there (identical) and are kept.",
                     "tr": "Bunların {n} tanesi zaten orada (birebir aynı) ve korunur."},
    "mv_plan_subfolders": {
        "en": "Folders inside the Library stay where they are: {names}",
        "tr": "Library içindeki klasörler olduğu yerde kalır: {names}"},
    "mv_remove_old": {"en": "Afterwards, send the old copies to the Recycle Bin",
                      "tr": "Sonra eski kopyaları Geri Dönüşüm Kutusu'na gönder"},
    "mv_remove_old_short": {"en": "old copies → Recycle Bin",
                            "tr": "eski kopyalar → Geri Dönüşüm Kutusu"},
    "tip_mv_remove_old": {
        "en": "Only after every file is verified in the new folder. On a drive without a "
              "Recycle Bin the old copies are left alone.",
        "tr": "Yalnızca her dosya yeni klasörde doğrulandıktan sonra. Geri Dönüşüm Kutusu "
              "olmayan bir sürücüde eski kopyalara dokunulmaz."},
    "mv_run": {"en": "Move", "tr": "Taşı"},
    "mv_confirm": {
        "en": "Move {n} files ({size}) to:\n{dest}\n\nRosu copies and checks every file, "
              "then switches to the new folder.",
        "tr": "{n} dosya ({size}) şuraya taşınsın mı:\n{dest}\n\nRosu her dosyayı "
              "kopyalayıp kontrol eder, sonra yeni klasöre geçer."},
    "mv_confirm_old_recycle": {
        "en": "Then the old copies go to the Recycle Bin.",
        "tr": "Sonra eski kopyalar Geri Dönüşüm Kutusu'na gider."},
    "mv_confirm_old_kept": {
        "en": "The old copies stay where they are (delete them yourself when you are sure).",
        "tr": "Eski kopyalar olduğu yerde kalır (emin olunca kendin silebilirsin)."},
    "mv_err_same": {"en": "That is the current Library folder.",
                    "tr": "Bu zaten şu anki Library klasörü."},
    "mv_err_inside": {
        "en": "The new folder cannot be inside the Library, or contain it.",
        "tr": "Yeni klasör Library'nin içinde olamaz ya da onu içeremez."},
    "mv_err_not_writable": {"en": "Rosu cannot write to that folder.",
                            "tr": "Rosu o klasöre yazamıyor."},
    "mv_err_reserved": {
        "en": "That folder is (or holds) Rosu's Output, Packs, data or logs folder — Unpack "
              "empties Output, for one. Pick a folder of its own.",
        "tr": "O klasör Rosu'nun Output, Packs, data ya da logs klasörü (veya onları "
              "içeriyor) — örneğin Paketi Aç, Output'u boşaltır. Kendine ait bir klasör seç."},
    "mv_err_config_save": {
        "en": "The files were copied, but the new location could not be saved, so the "
              "Library stays where it was.",
        "tr": "Dosyalar kopyalandı ama yeni konum kaydedilemedi, bu yüzden Library olduğu "
              "yerde kalıyor."},
    "mv_plan_links": {"en": "{n} linked entries in the Library are skipped.",
                      "tr": "Library'deki {n} bağlantı (link) atlanır."},
    "mv_done_late": {"en": "{n} files that arrived during the move were copied too.",
                     "tr": "Taşıma sırasında gelen {n} dosya da kopyalandı."},
    "mv_done_left_behind": {
        "en": "{n} files stayed in the old folder (a file with the same name was already "
              "in the new one): {names}",
        "tr": "{n} dosya eski klasörde kaldı (yenisinde aynı adlı bir dosya vardı): {names}"},
    "mv_done_old_failed": {
        "en": "{n} old copies were left in place: they changed after being copied, or could "
              "not be recycled.",
        "tr": "{n} eski kopya yerinde bırakıldı: kopyalandıktan sonra değişmişler ya da geri "
              "dönüşüme gönderilemediler."},
    "mv_err_no_library": {"en": "The current Library folder does not exist.",
                          "tr": "Şu anki Library klasörü yok."},
    "mv_err_conflicts": {
        "en": "{n} files with the same name but different contents are already there "
              "(e.g. {names}). Move or rename them first.",
        "tr": "Orada aynı adlı ama içeriği farklı {n} dosya zaten var (ör. {names}). Önce "
              "onları taşı ya da yeniden adlandır."},
    "mv_err_no_space": {"en": "There is not enough free space there.",
                        "tr": "Orada yeterli boş alan yok."},
    "mv_err_copy_failed": {"en": "A file could not be copied or did not match its original.",
                           "tr": "Bir dosya kopyalanamadı ya da aslıyla eşleşmedi."},
    "mv_cancelled": {"en": "The move was cancelled.", "tr": "Taşıma iptal edildi."},
    "mv_nothing_changed": {
        "en": "Nothing changed: the Library is still where it was.",
        "tr": "Hiçbir şey değişmedi: Library hâlâ olduğu yerde."},
    "mv_done": {"en": "The Library ({n} files) is now in {dest}.",
                "tr": "Library ({n} dosya) artık şurada: {dest}."},
    "mv_done_recycled": {"en": "{n} old copies went to the Recycle Bin.",
                         "tr": "{n} eski kopya Geri Dönüşüm Kutusu'na gitti."},
    "mv_done_old_kept_no_bin": {
        "en": "The old copies were left in place: that drive has no Recycle Bin.",
        "tr": "Eski kopyalar yerinde bırakıldı: o sürücüde Geri Dönüşüm Kutusu yok."},
    "job_library_move": {"en": "Move the Library", "tr": "Library'yi taşı"},
    "job_step_library_move": {"en": "Copy, verify, switch", "tr": "Kopyala, doğrula, geç"},
    "job_library_move_desc": {"en": "to {dest}", "tr": "hedef: {dest}"},

    # -- v1.9: Logs table ----------------------------------------------------------
    "log_col_time": {"en": "Time", "tr": "Zaman"},
    "log_col_level": {"en": "Level", "tr": "Seviye"},
    "log_col_action": {"en": "Action", "tr": "İşlem"},
    "log_col_fields": {"en": "Details", "tr": "Ayrıntılar"},
    "log_col_message": {"en": "Message", "tr": "Mesaj"},
    "log_errors_only": {"en": "Errors only", "tr": "Yalnızca hatalar"},
    "log_filter": {"en": "Filter the log…", "tr": "Logu filtrele…"},
    "log_count": {"en": "{shown} of {total} lines", "tr": "{total} satırın {shown} tanesi"},
    # -- v1.9: Search columns, saved searches, export ---------------------------
    "tip_column_menu": {"en": "Right-click to choose which columns to show.",
                        "tr": "Hangi sütunların görüneceğini seçmek için sağ tıkla."},
    "columns_show_all": {"en": "Show all columns", "tr": "Tüm sütunları göster"},
    "saved_searches": {"en": "★ Saved", "tr": "★ Kayıtlı"},
    "tip_saved_searches": {
        "en": "Save the current search (text and filters) under a name, and run it again "
              "with one click.",
        "tr": "Geçerli aramayı (metin ve filtreler) bir adla kaydet ve tek tıkla tekrar "
              "çalıştır."},
    "saved_search_save": {"en": "Save this search…", "tr": "Bu aramayı kaydet…"},
    "saved_search_delete": {"en": "Delete", "tr": "Sil"},
    "saved_search_none": {"en": "No saved searches yet", "tr": "Henüz kayıtlı arama yok"},
    "saved_search_name": {"en": "Name:", "tr": "Ad:"},
    "saved_search_saved": {"en": "Saved as \"{name}\".", "tr": "\"{name}\" olarak kaydedildi."},
    "btn_gallery": {"en": "▦ Gallery", "tr": "▦ Galeri"},
    "tip_gallery": {
        "en": "Show the results as cover art (the first {n}). Double-click a cover for "
              "its details.",
        "tr": "Sonuçları kapak görselleriyle göster (ilk {n} tanesi). Ayrıntılar için bir "
              "kapağa çift tıkla."},
    "btn_export_results": {"en": "Export…", "tr": "Dışa aktar…"},
    "tip_export_results": {
        "en": "Save the listed sets as a CSV (spreadsheet) or JSON file.",
        "tr": "Listelenen setleri CSV (tablo) ya da JSON dosyası olarak kaydet."},
    "export_results_none": {"en": "Nothing to export — the list is empty.",
                            "tr": "Dışa aktarılacak bir şey yok — liste boş."},
    "export_results_done": {"en": "Exported {n} sets.", "tr": "{n} set dışa aktarıldı."},
    "export_results_done_shown": {
        "en": "Exported the {n} sets shown (the search matched more; narrow it to export "
              "the rest).",
        "tr": "Gösterilen {n} set dışa aktarıldı (arama daha fazlasını buldu; kalanı için "
              "aramayı daralt)."},
    "export_results_failed": {"en": "Could not write the file: {error}",
                              "tr": "Dosya yazılamadı: {error}"},
    "rm_title": {"en": "Remove from osu!", "tr": "osu!'dan Kaldır"},
    "rm_intro": {
        "en": "Pick a client and which sets to take out of it. Nothing changes until you "
              "confirm, and nothing is removed without a way back: the Recycle Bin or an "
              "identical copy in the Library.",
        "tr": "Bir client seç ve içinden hangi setlerin çıkacağını belirle. Sen onaylayana "
              "kadar hiçbir şey değişmez ve hiçbir şey geri dönüş yolu olmadan kaldırılmaz: "
              "Geri Dönüşüm Kutusu ya da Library'deki birebir aynı kopya."},
    "rm_checking": {"en": "Checking which osu! clients are available…",
                    "tr": "Hangi osu! client'larının kullanılabildiği kontrol ediliyor…"},
    "rm_source": {"en": "Remove from:", "tr": "Şuradan kaldır:"},
    "rm_why_disabled": {"en": "This client is turned off in Settings.",
                        "tr": "Bu client Ayarlar'da kapalı."},
    "rm_why_no_stable": {"en": "osu!(stable)'s Songs folder was not found.",
                         "tr": "osu!(stable)'ın Songs klasörü bulunamadı."},
    "rm_why_no_lazer": {"en": "osu!lazer's data folder was not found.",
                        "tr": "osu!lazer'ın veri klasörü bulunamadı."},
    "rm_why_lazer_helper": {
        "en": "Not available yet: removing from osu!lazer needs the updated lazer helper "
              "(it edits lazer's database the way lazer itself does). It ships once it has "
              "been verified on a real lazer install.",
        "tr": "Henüz kullanılamıyor: osu!lazer'dan kaldırmak için güncellenmiş lazer "
              "yardımcısı gerekir (lazer'ın veritabanını lazer'ın kendisi gibi düzenler). "
              "Gerçek bir lazer kurulumunda doğrulandıktan sonra gelecek."},
    "rm_how_stable": {
        "en": "Each set's folder in Songs/ goes to the Recycle Bin. In osu!, press F5 in "
              "song select afterwards so it notices.",
        "tr": "Her setin Songs/ içindeki klasörü Geri Dönüşüm Kutusu'na gider. Sonrasında "
              "osu!'da şarkı seçiminde F5'e bas ki fark etsin."},
    "rm_how_lazer": {
        "en": "Experimental. The sets are saved to the Library first, then marked deleted "
              "in lazer's database exactly like lazer's own delete; lazer removes them for "
              "good on its next start. To get one back later, import it from the Library.",
        "tr": "Deneysel. Setler önce Library'e kaydedilir, sonra lazer'ın veritabanında "
              "lazer'ın kendi silme işlemiyle aynı şekilde silinmiş olarak işaretlenir; "
              "lazer onları bir sonraki açılışında kalıcı olarak kaldırır. Birini sonradan "
              "geri istersen Library'den içe aktar."},
    "rm_mode_save": {"en": "Save to Library, then remove", "tr": "Library'e kaydet, sonra kaldır"},
    "rm_mode_save_tip": {
        "en": "Copies each set into the Library first and removes only the sets whose "
              "Library copy holds every difficulty byte for byte. A Library file is never "
              "overwritten; a set that differs from it stays in osu!.",
        "tr": "Her seti önce Library'e kopyalar ve yalnızca Library kopyası her zorluğu "
              "bayt bayt içeren setleri kaldırır. Library'deki bir dosyanın üzerine asla "
              "yazılmaz; ondan farklı olan set osu!'da kalır."},
    "rm_mode_only": {"en": "Remove only", "tr": "Sadece kaldır"},
    "rm_mode_only_tip": {
        "en": "Removes the sets without saving them anywhere first (they go to the "
              "Recycle Bin).",
        "tr": "Setleri önce bir yere kaydetmeden kaldırır (Geri Dönüşüm Kutusu'na "
              "giderler)."},
    "rm_mode_only_lazer": {
        "en": "Not for osu!lazer: lazer deletes removed sets for good on its next start, "
              "so they are always saved to the Library first.",
        "tr": "osu!lazer için yok: lazer kaldırılan setleri bir sonraki açılışında kalıcı "
              "olarak siler, bu yüzden her zaman önce Library'e kaydedilirler."},
    "rm_which": {"en": "Which:", "tr": "Hangileri:"},
    "rm_which_all": {"en": "All sets", "tr": "Tüm setler"},
    "rm_which_backed_up": {"en": "Only sets already in the Library",
                           "tr": "Yalnızca Library'de olan setler"},
    "rm_which_not_backed_up": {"en": "Only sets not in the Library",
                               "tr": "Yalnızca Library'de olmayan setler"},
    "rm_sort_largest": {"en": "Largest first", "tr": "Önce en büyük"},
    "rm_sort_smallest": {"en": "Smallest first", "tr": "Önce en küçük"},
    "rm_sort_name": {"en": "By name", "tr": "İsme göre"},
    "rm_col_in_library": {"en": "In Library", "tr": "Library'de"},
    "rm_run": {"en": "Remove", "tr": "Kaldır"},
    "rm_run_n": {"en": "Remove {n} sets", "tr": "{n} seti kaldır"},
    "rm_no_source": {"en": "No osu! client is available to remove from.",
                     "tr": "Kaldırılabilecek bir osu! client'ı yok."},
    "rm_scanned": {"en": "{n} sets found ({size}); {backed} of them are already in the Library.",
                   "tr": "{n} set bulundu ({size}); bunların {backed} tanesi zaten Library'de."},
    "rm_total": {"en": "{n} sets selected · {size}", "tr": "{n} set seçili · {size}"},
    "rm_warn_save": {
        "en": "{n} of these are not in the Library yet — they will be copied there first.",
        "tr": "Bunların {n} tanesi henüz Library'de değil — önce oraya kopyalanacaklar."},
    "rm_warn_only": {
        "en": "Careful: {n} of these have no copy in the Library. After removing them Rosu "
              "has no copy of its own; the Recycle Bin is the only way back.",
        "tr": "Dikkat: bunların {n} tanesinin Library'de kopyası yok. Kaldırdıktan sonra "
              "Rosu'nun kendi kopyası olmaz; tek geri dönüş yolu Geri Dönüşüm Kutusu."},
    "rm_confirm_body": {
        "en": "Remove {n} sets from {source}?\nMode: {mode}.\n\n{recovery}\n\nClose {source} "
              "first.",
        "tr": "{source} içinden {n} set kaldırılsın mı?\nYöntem: {mode}.\n\n{recovery}\n\n"
              "Önce {source}'ı kapat."},
    "rm_recovery_stable": {
        "en": "Undo: the folders are in the Recycle Bin — restore them from there.",
        "tr": "Geri alma: klasörler Geri Dönüşüm Kutusu'nda — oradan geri yükle."},
    "rm_recovery_lazer": {
        "en": "Undo: until osu!lazer is started again, putting back the copy of "
              "client.realm saved next to it (with lazer closed) restores the sets. After "
              "that, the Library copy is the way back.",
        "tr": "Geri alma: osu!lazer yeniden açılana kadar, yanına kaydedilen client.realm "
              "kopyasını (lazer kapalıyken) geri koymak setleri geri getirir. Ondan sonra "
              "geri dönüş yolu Library'deki kopyadır."},
    "rm_listing_lazer": {"en": "Reading osu!lazer's set list…",
                         "tr": "osu!lazer'ın set listesi okunuyor…"},
    "rm_deleting_lazer": {"en": "Marking the sets deleted in osu!lazer…",
                          "tr": "Setler osu!lazer'da silinmiş olarak işaretleniyor…"},
    "rm_err_no_stable": {"en": "osu!(stable) was not found.", "tr": "osu!(stable) bulunamadı."},
    "rm_err_no_lazer": {"en": "osu!lazer was not found.", "tr": "osu!lazer bulunamadı."},
    "rm_err_helper_failed": {
        "en": "The osu!lazer helper failed — see the Logs tab. Nothing was removed.",
        "tr": "osu!lazer yardımcısı başarısız oldu — Loglar sekmesine bak. Hiçbir şey "
              "kaldırılmadı."},
    "rm_err_bad_source": {"en": "Unknown source.", "tr": "Bilinmeyen kaynak."},
    "rm_err_unavailable": {"en": "That client is not available (turned off in Settings?).",
                           "tr": "Bu client kullanılamıyor (Ayarlar'da kapalı mı?)."},
    "rm_err_client_check_failed": {
        "en": "Could not check whether osu! is running. Close osu! and try again — nothing "
              "was removed.",
        "tr": "osu!'nun açık olup olmadığı kontrol edilemedi. osu!'yu kapatıp tekrar dene — "
              "hiçbir şey kaldırılmadı."},
    "rm_err_no_recycle_bin": {
        "en": "Removing needs a drive with a Recycle Bin, and the Songs folder is on a "
              "removable or network drive without one, so removed folders could not be "
              "brought back — nothing was removed.",
        "tr": "Kaldırmak için Geri Dönüşüm Kutusu olan bir sürücü gerekir; Songs klasörü "
              "ise Geri Dönüşüm Kutusu olmayan çıkarılabilir ya da ağ sürücüsünde, bu "
              "yüzden kaldırılan klasörler geri getirilemez — hiçbir şey kaldırılmadı."},
    "rm_err_client_running": {
        "en": "osu! is running. Close it and try again — nothing was removed.",
        "tr": "osu! açık. Kapatıp tekrar dene — hiçbir şey kaldırılmadı."},
    "rm_err_lazer_helper": {
        "en": "The bundled osu!lazer helper cannot remove sets yet. Nothing was removed.",
        "tr": "Paketteki osu!lazer yardımcısı henüz set kaldıramıyor. Hiçbir şey "
              "kaldırılmadı."},
    "rm_done": {"en": "Removed {n} sets from {source}.", "tr": "{source} içinden {n} set kaldırıldı."},
    "rm_done_saved": {"en": "{n} sets were copied into the Library first.",
                      "tr": "{n} set önce Library'e kopyalandı."},
    "rm_done_kept": {
        "en": "{n} sets were kept because the Library does not hold an identical copy "
              "(see the Logs tab).",
        "tr": "{n} set, Library'de birebir aynı kopyası olmadığı için bırakıldı (Loglar "
              "sekmesine bak)."},
    "rm_done_failed": {"en": "{n} sets could not be removed — see the Logs tab.",
                       "tr": "{n} set kaldırılamadı — Loglar sekmesine bak."},
    "rm_done_lazer_restart": {
        "en": "Start osu!lazer once: it finishes the removal and frees the space then.",
        "tr": "osu!lazer'ı bir kez aç: kaldırmayı o zaman tamamlar ve alanı boşaltır."},
    "rm_done_backup": {"en": "Database backup: {path}", "tr": "Veritabanı yedeği: {path}"},
    "rm_done_stable_refresh": {
        "en": "In osu!(stable), press F5 in song select to refresh the list.",
        "tr": "osu!(stable)'da listeyi yenilemek için şarkı seçiminde F5'e bas."},
    "job_remove": {"en": "Remove from osu!", "tr": "osu!'dan Kaldır"},
    "job_step_remove_save": {"en": "Save to Library, then remove",
                             "tr": "Library'e kaydet, sonra kaldır"},
    "job_step_remove_only": {"en": "Remove", "tr": "Kaldır"},

    # -- v1.8: Drive backup browser (HANDOFF 4.2) -------------------------------
    "btn_drive_browse": {"en": "Browse Drive backup…", "tr": "Drive Yedeğine Göz At…"},
    "tip_drive_browse": {
        "en": "See every set in your Google Drive backup (from this PC and any other) and "
              "bring chosen ones back into the Library.",
        "tr": "Google Drive yedeğindeki tüm setleri (bu PC'den ve diğerlerinden) gör ve "
              "seçtiklerini Library'e geri al."},
    "drv_title": {"en": "Drive backup", "tr": "Drive Yedeği"},
    "drv_intro": {
        "en": "Everything your Drive backup holds, from every PC that backs up into it. "
              "Select sets and restore them into the Library; each file is checked "
              "against the fingerprint recorded when it was backed up.",
        "tr": "Drive yedeğinin içerdiği her şey — oraya yedek alan tüm PC'lerden. Setleri "
              "seç ve Library'e geri yükle; her dosya yedeklendiği anda kaydedilen parmak "
              "iziyle karşılaştırılır."},
    "drv_filter": {"en": "Filter by artist, title or file name…",
                   "tr": "Sanatçı, başlık veya dosya adına göre süz…"},
    "drv_hide_in_library": {"en": "Hide sets already in the Library",
                            "tr": "Library'de olan setleri gizle"},
    "drv_reload": {"en": "Reload from Drive", "tr": "Drive'dan yeniden yükle"},
    "drv_col_from": {"en": "Backed up from", "tr": "Yedekleyen"},
    "drv_col_state": {"en": "State", "tr": "Durum"},
    "drv_from_here": {"en": "This PC", "tr": "Bu PC"},
    "drv_from_other": {"en": "Another PC", "tr": "Başka bir PC"},
    "drv_state_missing": {"en": "archive missing on Drive", "tr": "arşiv Drive'da yok"},
    "drv_state_in_library": {"en": "in Library", "tr": "Library'de"},
    "drv_state_restorable": {"en": "restorable", "tr": "geri alınabilir"},
    "drv_select_all": {"en": "Select all shown", "tr": "Gösterilenlerin hepsini seç"},
    "drv_restore": {"en": "Restore to Library", "tr": "Library'e Geri Al"},
    "drv_restore_n": {"en": "Restore {n} sets", "tr": "{n} seti geri al"},
    "drv_loading": {"en": "Reading the backup from Drive…", "tr": "Yedek Drive'dan okunuyor…"},
    "drv_err_not_connected": {"en": "Google Drive is not connected (Settings → Drive).",
                              "tr": "Google Drive bağlı değil (Ayarlar → Drive)."},
    "drv_err": {"en": "Drive error: {detail}", "tr": "Drive hatası: {detail}"},
    "drv_summary": {
        "en": "{n} sets in the backup, from {devices} PC(s); {in_lib} already in the Library.",
        "tr": "Yedekte {n} set var, {devices} PC'den; {in_lib} tanesi zaten Library'de."},
    "drv_missing": {
        "en": "{n} point to an archive that is no longer on Drive.",
        "tr": "{n} tanesi artık Drive'da olmayan bir arşivi gösteriyor."},
    "drv_orphans": {
        "en": "{n} backup file(s) on Drive are not listed in any manifest.",
        "tr": "Drive'daki {n} yedek dosyası hiçbir manifestte listelenmiyor."},
    "drv_confirm": {
        "en": "Restore {n} sets ({size}) into the Library?\n\nRosu downloads the {archives} "
              "backup archive(s) that hold them — a whole archive even for one set, so this "
              "can take a while — and checks every file before importing it.",
        "tr": "{n} set ({size}) Library'e geri alınsın mı?\n\nRosu onları içeren {archives} "
              "yedek arşivini indirir — tek set için bile arşivin tamamını, bu yüzden biraz "
              "sürebilir — ve her dosyayı içe aktarmadan önce kontrol eder."},
    "drv_downloading": {"en": "Downloading {name}…", "tr": "{name} indiriliyor…"},
    "drv_done": {"en": "Restored {n} sets into the Library ({already} were already there).",
                 "tr": "{n} set Library'e geri alındı ({already} tanesi zaten oradaydı)."},
    "drv_done_failed": {"en": "{n} could not be restored: {names}",
                        "tr": "{n} tanesi geri alınamadı: {names}"},
    "drv_fail_bad_name": {"en": "unsafe name", "tr": "güvensiz ad"},
    "drv_fail_not_on_drive": {"en": "archive not on Drive", "tr": "arşiv Drive'da yok"},
    "drv_fail_download": {"en": "download failed", "tr": "indirme başarısız"},
    "drv_fail_not_in_archive": {"en": "not in its archive", "tr": "arşivinde yok"},
    "drv_fail_size_mismatch": {"en": "size mismatch", "tr": "boyut uyuşmuyor"},
    "drv_fail_corrupt": {"en": "unreadable", "tr": "okunamıyor"},
    "drv_fail_hash_mismatch": {"en": "fingerprint mismatch", "tr": "parmak izi uyuşmuyor"},
    "drv_fail_disk_full": {"en": "not enough disk space", "tr": "yeterli disk alanı yok"},
    "drv_fail_library_conflict": {
        "en": "a different file with this name is in the Library (left as it is)",
        "tr": "Library'de bu adla farklı bir dosya var (olduğu gibi bırakıldı)"},
    "job_drive_restore": {"en": "Restore from Drive", "tr": "Drive'dan Geri Al"},
    "job_step_drive_fetch": {"en": "Download + verify", "tr": "İndir + doğrula"},
    "job_step_drive_import": {"en": "Import into the Library", "tr": "Library'e aktar"},

    # -- v1.8: update check, report tracking, crash reports ----------------------
    "update_whats_new": {"en": "What's new", "tr": "Yenilikler"},
    "report_sent_track": {
        "en": "Follow its status here (the link is also on your clipboard — keep it "
              "private):<br>{link}",
        "tr": "Durumunu buradan takip edebilirsin (bağlantı panoya da kopyalandı — gizli "
              "tut):<br>{link}"},
    "set_crash_reports": {"en": "Send anonymous crash reports",
                          "tr": "Anonim çökme raporları gönder"},
    "tip_crash_reports": {
        "en": "Off by default. When on, an unexpected error sends its type, a short message "
              "with file paths and e-mail addresses removed, and the names of the code "
              "locations involved, plus the Rosu version and your OS. No files, no library "
              "contents, no usernames. Details: rosu-web.vercel.app/privacy",
        "tr": "Varsayılan olarak kapalı. Açıkken beklenmedik bir hata; türünü, dosya yolları "
              "ve e-posta adresleri temizlenmiş kısa bir mesajı ve ilgili kod konumlarının "
              "adlarını, Rosu sürümü ve işletim sisteminle birlikte gönderir. Dosya, "
              "kütüphane içeriği veya kullanıcı adı gönderilmez. Ayrıntı: "
              "rosu-web.vercel.app/privacy"},
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
