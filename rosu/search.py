"""Relevance-ranked music search.

The database only does broad substring recall; ranking happens here so results
feel right. Tiers (high to low): exact field match, field prefix, whole-word
match, word prefix, substring, then weak metadata (creator/tags). Ties break on
a fuzzy similarity score, then shorter name, then copy count.

This fixes the naive "substring + alphabetical" behaviour where searching "hat"
surfaced "What THE CAT" above "Hatsune" / "Forgotten Hate".
"""
from __future__ import annotations

import re

try:
    from rapidfuzz import fuzz

    def _fuzzy(a: str, b: str) -> float:
        return fuzz.WRatio(a, b)
except ImportError:  # graceful fallback if rapidfuzz isn't installed
    from difflib import SequenceMatcher

    def _fuzzy(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio() * 100

_WORD = re.compile(r"\w+", re.UNICODE)

# Tier scores
_EXACT, _PREFIX, _WORD_EQ, _WORD_PREFIX, _SUBSTR, _WEAK = 100, 90, 85, 80, 60, 50


def _norm(s: str | None) -> str:
    return (s or "").casefold().strip()


def _tier(q: str, fields: list[str]) -> int:
    best = 0
    for field in fields:
        fn = _norm(field)
        if not fn:
            continue
        if fn == q:
            return _EXACT
        if fn.startswith(q):
            best = max(best, _PREFIX)
        words = _WORD.findall(fn)
        if any(w == q for w in words):
            best = max(best, _WORD_EQ)
        elif any(w.startswith(q) for w in words):
            best = max(best, _WORD_PREFIX)
        if q in fn:
            best = max(best, _SUBSTR)
    return best


def rank(rows: list[dict], query: str, limit: int = 500) -> list[dict]:
    q = _norm(query)
    raw = query.strip()
    scored = []
    for r in rows:
        tier = _tier(q, [r.get("display_name"), r.get("artist"), r.get("title")])
        if raw.isdigit() and r.get("beatmapset_id") == int(raw):
            tier = _EXACT
        if tier == 0:
            for weak in (r.get("creator"), r.get("tags"), r.get("source")):
                if weak and q in _norm(weak):
                    tier = _WEAK
                    break
        if tier == 0:
            continue
        fz = _fuzzy(q, _norm(r.get("display_name")))
        name_len = len(r.get("display_name") or "")
        scored.append((tier, fz, -name_len, r.get("copy_attempts", 0), r))
    scored.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
    return [s[4] for s in scored[:limit]]


def search(db, query: str, limit: int = 500) -> list[dict]:
    if not query.strip():
        return []
    candidates = db.search_candidates(query)
    ranked = rank(candidates, query, limit)
    db.attach_sources_bulk(ranked)  # only the displayed rows — no N+1
    return ranked
