# SPDX-License-Identifier: GPL-3.0-or-later
"""Small shared helpers from the v1.9/v1.10 reviews: bounded zip reads,
never-replace placement, the writable-folder probe, and the cover format check."""
import io
import os
import zipfile

import pytest

from rosu import config
from rosu.fsutil import dir_writable, place_new
from rosu.zipread import TooBig, copy_capped, read_capped


def _zip(members: dict) -> zipfile.ZipFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return zipfile.ZipFile(io.BytesIO(buf.getvalue()))


def test_read_capped_takes_up_to_the_cap_and_refuses_more():
    zf = _zip({"a": b"x" * 100, "b": b"y" * 101})
    assert read_capped(zf, zf.getinfo("a"), 100) == b"x" * 100
    with pytest.raises(TooBig):
        read_capped(zf, zf.getinfo("b"), 100)
    out = io.BytesIO()
    assert copy_capped(zf, zf.getinfo("a"), out, 100) == 100
    assert out.getvalue() == b"x" * 100
    with pytest.raises(TooBig):
        copy_capped(zf, zf.getinfo("b"), io.BytesIO(), 100)


def test_read_capped_stops_even_when_the_header_understates_the_size():
    zf = _zip({"big": b"z" * 5000})
    info = zf.getinfo("big")
    info.file_size = 10          # a header that lies about the size
    with pytest.raises((TooBig, zipfile.BadZipFile)):
        read_capped(zf, info, 100)


def test_place_new_never_replaces_a_file(tmp_path):
    tmp = tmp_path / "tmp.part"
    tmp.write_bytes(b"new")
    dest = tmp_path / "set.osz"
    place_new(tmp, dest)
    assert dest.read_bytes() == b"new" and not tmp.exists()
    tmp.write_bytes(b"newer")
    with pytest.raises(FileExistsError):
        place_new(tmp, dest)
    assert dest.read_bytes() == b"new"


def test_dir_writable_is_false_when_a_file_cannot_be_created(tmp_path, monkeypatch):
    import tempfile

    def refuse(**_k):
        raise PermissionError("access denied")
    monkeypatch.setattr(tempfile, "TemporaryFile", refuse)
    assert not dir_writable(tmp_path)


# chmod cannot take write access away from a folder on Windows (it only sets the
# read-only attribute, which folders ignore), and root ignores it on POSIX.
@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                    reason="needs POSIX permissions enforced for this user")
def test_dir_writable_answers_for_read_only_folders(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    assert dir_writable(ro)
    ro.chmod(0o500)
    try:
        assert not dir_writable(ro)
    finally:
        ro.chmod(0o700)


def test_dir_writable_is_false_for_a_missing_folder(tmp_path):
    assert dir_writable(tmp_path) and not dir_writable(tmp_path / "nope")


def test_ensure_dirs_survives_an_offline_library_drive(tmp_path, monkeypatch):
    blocker = tmp_path / "file-not-folder"
    blocker.write_text("x")
    cfg = config._fill_defaults(config.Config(root=str(tmp_path / "app"),
                                              library_dir=str(blocker / "Library")))
    cfg.ensure_dirs()                      # the Library cannot be made: no crash
    assert cfg.data_path.is_dir() and cfg.logs_path.is_dir()


def test_cover_images_are_sniffed_by_their_magic_bytes():
    from rosu.ui.cover_gallery import image_format
    assert image_format(b"\xff\xd8\xff\xe0rest") == "JPG"
    assert image_format(b"\x89PNG\r\n\x1a\nrest") == "PNG"
    assert image_format(b"BMxxxx") == "BMP"
    assert image_format(b"<svg></svg>") is None and image_format(b"") is None
