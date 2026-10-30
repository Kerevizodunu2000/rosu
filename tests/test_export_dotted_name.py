# SPDX-License-Identifier: GPL-3.0-or-later
"""An export named with a dot (``my.maps``) is written where the dialog said,
not truncated at the last dot."""
from rosu import exporter


def _files(tmp_path, n=3):
    out = []
    for i in range(n):
        p = tmp_path / "src" / f"{i} A - B.osz"
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(b"x" * 100)
        out.append(p)
    return out


def test_single_archive_keeps_dotted_name(tmp_path):
    written = exporter.write_export(_files(tmp_path), tmp_path / "my.maps", fmt="zip")
    assert written == [tmp_path / "my.maps.zip"]
    assert (tmp_path / "my.maps.zip").exists()


def test_volumes_keep_dotted_name(tmp_path):
    written = exporter.write_export(_files(tmp_path), tmp_path / "my.maps", fmt="zip",
                                    split_bytes=150)
    assert len(written) > 1
    assert all(p.name.startswith("my.maps.part") and p.exists() for p in written)
