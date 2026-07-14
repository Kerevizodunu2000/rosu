# SPDX-License-Identifier: GPL-3.0-or-later
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
    "set_osu_lazer_exe": {"en": "osu!lazer executable", "tr": "osu!lazer çalıştırılabilir"},
    "set_osu_stable_exe": {"en": "osu!(stable) executable", "tr": "osu!(stable) çalıştırılabilir"},
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

    # Google Drive backup (item 11, v0.8)
    "col_location": {"en": "Where", "tr": "Konum"},
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
    "drive_connect_first": {"en": "Connect Google Drive in Settings first.",
                            "tr": "Önce Ayarlar'dan Google Drive'a bağlan."},
    "drive_backing_up": {"en": "Backing up to Google Drive…",
                         "tr": "Google Drive'a yedekleniyor…"},
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
    "tip_clear_before": {"en": "Empty the Output folder before each new extraction.",
                        "tr": "Her yeni çıkarmadan önce Output klasörünü boşaltır."},
    "tip_update_reference": {
        "en": "Fetch the current official pack list from the osu! API to detect "
              "genuinely missing packs.",
        "tr": "Gerçekten eksik paketleri tespit etmek için osu! API'sinden güncel "
              "resmi paket listesini çeker."},
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

    "tip_open_formats": {
        "en": "Open log_formats.md, which explains the log entry formats.",
        "tr": "Log girdisi biçimlerini açıklayan log_formats.md dosyasını açar."},
    "tip_open_excel": {"en": "Open the Excel report of your library.",
                      "tr": "Kütüphanenizin Excel raporunu açar."},
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
