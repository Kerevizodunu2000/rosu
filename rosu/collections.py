# SPDX-License-Identifier: GPL-3.0-or-later
"""osu! collection.db parser and writer.

Parses the binary collection.db file format used by osu!(stable).
"""
import struct
from pathlib import Path

# ULEB128 values in this format are always small (string lengths, counts) — 5
# bytes covers the full 32-bit range with room to spare. Without a cap, a
# stream of continuation bytes with no terminator makes the accumulating
# Python int (and the shift) grow unbounded, which is both slow (superlinear
# per extra byte) and a memory-exhaustion vector from a tiny malicious file.
_MAX_ULEB128_BYTES = 5

# osu! collection names and beatmap MD5s are always tiny; this is a generous
# ceiling that still stops a forged length prefix from driving a multi-GB
# f.read(length) off a handful of real bytes on disk.
_MAX_STRING_BYTES = 1 * 1024 * 1024


def _read_uleb128(f) -> int:
    result = 0
    shift = 0
    for _ in range(_MAX_ULEB128_BYTES):
        b = f.read(1)
        if not b:
            raise EOFError()
        byte = b[0]
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return result
        shift += 7
    raise ValueError("ULEB128 value too long")


def _write_uleb128(f, value: int) -> None:
    if value == 0:
        f.write(b'\x00')
        return
    while value > 0:
        byte = value & 0x7F
        value >>= 7
        if value > 0:
            byte |= 0x80
        f.write(bytes([byte]))


def _read_osu_string(f) -> str:
    kind = f.read(1)
    if not kind:
        raise EOFError()
    if kind == b'\x00':
        return ""
    if kind == b'\x0b':
        length = _read_uleb128(f)
        if length == 0:
            return ""
        if length > _MAX_STRING_BYTES:
            raise ValueError(f"string field too long: {length} bytes")
        data = f.read(length)
        return data.decode("utf-8", errors="replace")
    raise ValueError(f"Invalid string flag: {kind}")


def _write_osu_string(f, s: str) -> None:
    if not s:
        f.write(b'\x00')
        return
    f.write(b'\x0b')
    encoded = s.encode("utf-8")
    _write_uleb128(f, len(encoded))
    f.write(encoded)


class OsuCollection:
    def __init__(self, name: str, md5s: list[str]):
        self.name = name
        self.md5s = md5s


def read_collection_db(path: Path | str) -> tuple[int, list[OsuCollection]]:
    """Read a collection.db file and return (version, list[OsuCollection])."""
    p = Path(path)
    if not p.exists():
        return 0, []
    
    with p.open("rb") as f:
        version_data = f.read(4)
        if len(version_data) < 4:
            return 0, []
        version = struct.unpack("<I", version_data)[0]
        
        num_collections_data = f.read(4)
        if len(num_collections_data) < 4:
            return version, []
        num_collections = struct.unpack("<I", num_collections_data)[0]
        
        collections = []
        for _ in range(num_collections):
            name = _read_osu_string(f)
            num_maps = struct.unpack("<I", f.read(4))[0]
            md5s = []
            for _ in range(num_maps):
                md5s.append(_read_osu_string(f))
            collections.append(OsuCollection(name, md5s))
            
        return version, collections


def write_collection_db(path: Path | str, version: int, collections: list[OsuCollection]) -> None:
    """Write collections to a collection.db file."""
    with Path(path).open("wb") as f:
        f.write(struct.pack("<I", version))
        f.write(struct.pack("<I", len(collections)))
        
        for coll in collections:
            _write_osu_string(f, coll.name)
            f.write(struct.pack("<I", len(coll.md5s)))
            for md5 in coll.md5s:
                _write_osu_string(f, md5)
