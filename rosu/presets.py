# SPDX-License-Identifier: GPL-3.0-or-later
"""Saved searches (v1.9) — Qt-free.

A saved search is a name plus the exact query text (free text and filters,
``star>5 mode=mania``) and whether creator/tags were searched too. They live in
``config.json`` as plain data, so everything here validates what it is given:
the file is hand-editable and an older build may have written it.
"""
from __future__ import annotations

MAX_SAVED = 50
NAME_MAX = 60
QUERY_MAX = 500


def _clean(entry) -> dict | None:
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    query = entry.get("query")
    if not isinstance(name, str) or not isinstance(query, str):
        return None
    name = " ".join(name.split())[:NAME_MAX]
    query = query.strip()[:QUERY_MAX]
    if not name:
        return None
    return {"name": name, "query": query, "tags": bool(entry.get("tags"))}


def normalize(saved) -> list[dict]:
    """Valid entries only, unique by name (case-insensitive, first wins), capped."""
    out: list[dict] = []
    seen: set[str] = set()
    for e in saved if isinstance(saved, list) else []:
        c = _clean(e)
        if c is None or c["name"].casefold() in seen:
            continue
        seen.add(c["name"].casefold())
        out.append(c)
        if len(out) >= MAX_SAVED:
            break
    return out


def save(saved, name: str, query: str, tags: bool = False) -> list[dict]:
    """``saved`` with ``name`` added — or replaced in place when it exists. When
    the list is full the oldest entry makes room."""
    entry = _clean({"name": name, "query": query, "tags": tags})
    items = normalize(saved)
    if entry is None:
        return items
    key = entry["name"].casefold()
    for i, e in enumerate(items):
        if e["name"].casefold() == key:
            items[i] = entry
            return items
    items.append(entry)
    return items[-MAX_SAVED:]


def remove(saved, name: str) -> list[dict]:
    key = " ".join(str(name).split()).casefold()
    return [e for e in normalize(saved) if e["name"].casefold() != key]


class History:
    """Back/forward through recent searches (v1.9), 16 steps by default.

    Live search runs on every typing pause, so a burst of typing ("ca", "cam",
    "camellia") is one step: a new entry that extends or trims the last one
    within ``burst_s`` seconds replaces it instead of adding a step."""

    def __init__(self, size: int = 16, burst_s: float = 1.5):
        self.size = size
        self.burst_s = burst_s
        self._items: list[tuple] = []
        self._pos = -1
        self._at = 0.0

    def push(self, entry: tuple, now: float) -> None:
        if 0 <= self._pos < len(self._items) and self._items[self._pos] == entry:
            return
        del self._items[self._pos + 1:]          # a new step drops the forward ones
        last = self._items[-1] if self._items else None
        typing = (last is not None and now - self._at < self.burst_s
                  and last[1:] == entry[1:]
                  and (str(entry[0]).startswith(str(last[0]))
                       or str(last[0]).startswith(str(entry[0]))))
        if typing:
            self._items[-1] = entry
        else:
            self._items.append(entry)
            self._items = self._items[-self.size:]
        self._pos = len(self._items) - 1
        self._at = now

    def can_back(self) -> bool:
        return self._pos > 0

    def can_forward(self) -> bool:
        return self._pos < len(self._items) - 1

    def back(self):
        if not self.can_back():
            return None
        self._pos -= 1
        return self._items[self._pos]

    def forward(self):
        if not self.can_forward():
            return None
        self._pos += 1
        return self._items[self._pos]
