"""Unit tests for rosu.parsing using real-world sample names."""
from rosu.parsing import parse_pack_name, parse_osz_entry, split_artist_title


def test_standard_pack():
    p = parse_pack_name("S1819 - osu! Beatmap Pack #1819.zip")
    assert p is not None
    assert p.series == "S" and p.number == 1819 and p.code == "S1819"
    assert p.mode == "osu!" and p.category == "Standard"
    assert p.title == "osu! Beatmap Pack #1819"


def test_categories():
    assert parse_pack_name("SM361 - x.zip").category == "Standard"
    assert parse_pack_name("FM38 - Homegrown.zip").category == "Featured"
    assert parse_pack_name("FQ92 - x.zip").category == "Featured"
    assert parse_pack_name("R287 - x.zip").category == "Spotlights"
    assert parse_pack_name("T89 - x.zip").category == "Theme"
    assert parse_pack_name("A5 - x.zip").category == "Artist"
    assert parse_pack_name("L12 - x.zip").category == "Loved"


def test_mania_pack():
    p = parse_pack_name("SM361 - osu!mania Beatmap Pack #361.zip")
    assert p.series == "SM" and p.number == 361 and p.code == "SM361"
    assert p.mode == "osu!mania"


def test_spotlight_osu():
    p = parse_pack_name("R287 - Beatmap Spotlights Winter 2020 (osu!).zip")
    assert p.series == "R" and p.number == 287
    assert p.mode == "osu!" and p.season == "Winter" and p.year == 2020
    assert p.is_spotlight


def test_spotlight_mania_underscore():
    p = parse_pack_name("R298 - Beatmap Spotlights_ Autumn 2020 (osu!mania).zip")
    assert p.mode == "osu!mania" and p.season == "Autumn" and p.year == 2020


def test_spotlight_duplicate_marker_stripped():
    p = parse_pack_name("R338 - Beatmap Spotlights_ Summer 2025 (osu!mania) (1).zip")
    assert p.code == "R338"
    assert p.mode == "osu!mania" and p.season == "Summer" and p.year == 2025
    # the trailing " (1)" is a duplicate-download marker, not part of the title
    assert p.title.endswith("(osu!mania)")
    assert "(1)" not in p.title


def test_featured_packs():
    fm = parse_pack_name("FM38 - Homegrown.zip")
    assert fm.series == "FM" and fm.number == 38 and fm.title == "Homegrown"
    fq = parse_pack_name("FQ92 - A.SAKA Pack.zip")
    assert fq.series == "FQ" and fq.number == 92


def test_bad_pack_name_is_other():
    p = parse_pack_name("some random collection.zip")
    assert p.category == "Other"
    assert p.series is None and p.number is None
    assert p.code == "some random collection"
    assert p.title == "some random collection"


def test_osz_root_entry():
    t = parse_osz_entry("2138180 Luna - Toki to Uta (Short Ver.).osz", 100)
    assert t.beatmapset_id == 2138180
    assert t.artist == "Luna" and t.title == "Toki to Uta (Short Ver.)"
    assert t.subfolder is None and t.size_bytes == 100


def test_osz_nested_entry():
    t = parse_osz_entry("osu!mania/539179 cosMo@BousouP - Oceanus.osz")
    assert t.beatmapset_id == 539179
    assert t.subfolder == "osu!mania"
    assert t.filename == "539179 cosMo@BousouP - Oceanus.osz"


def test_osz_no_numeric_prefix():
    t = parse_osz_entry("SomeArtist - Song.osz")
    assert t.beatmapset_id is None
    assert t.display_name == "SomeArtist - Song"


def test_osz_malformed_no_dash_is_unknown_artist():
    t = parse_osz_entry("1234 justatitle.osz")
    assert t.artist == "Unknown"
    assert t.title == "justatitle"
    assert t.display_name == "justatitle"


def test_directory_entry_ignored():
    assert parse_osz_entry("osu!mania/") is None


def test_osz_drive_letter_rejected():
    # security: a drive-relative / ADS name like "D:evil.osz" has no "/" to split
    # on, so it would survive as the flattened filename and escape the Output
    # folder when joined as ``output_dir / filename`` on Windows. Must be rejected.
    assert parse_osz_entry("D:evil.osz") is None
    assert parse_osz_entry("1234 Artist - Title.osz:bad.osz") is None
    # a normal nested entry with the same id must still parse fine
    assert parse_osz_entry("osu!/1234 Artist - Title.osz") is not None


def test_split_artist_title():
    assert split_artist_title("A - B") == ("A", "B")
    assert split_artist_title("NoDash") == ("", "NoDash")
