# SPDX-License-Identifier: GPL-3.0-or-later
"""Relevance-ranked music search.

The database does broad **token-AND** recall; ranking happens here so results
feel right. A query is split into tokens and **every** token must hit a *strong*
field (name / artist / title) for a row to qualify — so "Hatsune Miku" no longer
surfaces maps merely *tagged* miku by another artist. Each token is scored by how
well it matches a field (exact field, field prefix, whole word, word prefix,
substring); a row's tier is its **weakest** token, so "all words as prefixes"
beats "all words as substrings". A whole-query field match (e.g. an exact
"artist - title") is also checked and can only promote a row. Ties break on total
match strength, a fuzzy similarity score, then shorter name, then copy count.

Tag/creator matching is **opt-in** (``search_tags``) and can only ever qualify a
row at the lowest tier, so tag noise never outranks a real name/artist/title hit.
The old ``source`` fallback is gone — it flooded results with unrelated maps.
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

# How well ONE token matches ONE field-set (high to low).
_S_EXACT, _S_PREFIX, _S_WORD_EQ, _S_WORD_PREFIX, _S_SUBSTR, _S_NONE = 5, 4, 3, 2, 1, 0

# Row tiers (high to low). Strong = name/artist/title; weak = creator/tags (opt-in).
_EXACT, _PREFIX, _WORD_EQ, _WORD_PREFIX, _SUBSTR, _WEAK = 100, 90, 85, 80, 60, 40
_STRENGTH_TIER = {_S_EXACT: _EXACT, _S_PREFIX: _PREFIX, _S_WORD_EQ: _WORD_EQ,
                  _S_WORD_PREFIX: _WORD_PREFIX, _S_SUBSTR: _SUBSTR, _S_NONE: 0}


def _norm(s: str | None) -> str:
    return (s or "").casefold().strip()


def tokenize(query: str) -> list[str]:
    """Split a query into lowercase word tokens (the recall + rank unit)."""
    return _WORD.findall((query or "").casefold())


def _token_strength(token: str, fields: list[str],
                    words_by_field: list[list[str]]) -> int:
    """Best match strength of one token across the given normalized fields."""
    best = _S_NONE
    for fn, words in zip(fields, words_by_field, strict=True):
        if not fn:
            continue
        if fn == token:
            return _S_EXACT
        if fn.startswith(token):
            best = max(best, _S_PREFIX)
        if any(w == token for w in words):
            best = max(best, _S_WORD_EQ)
        elif any(w.startswith(token) for w in words):
            best = max(best, _S_WORD_PREFIX)
        if token in fn:
            best = max(best, _S_SUBSTR)
    return best


def _strong_score(q: str, tokens: list[str],
                  raw_fields: list[str | None]) -> tuple[int, int]:
    """(tier, total_strength) for a row's strong fields. tier 0 = doesn't qualify.

    Every token must hit a field (AND); the tier is the weakest token. A
    whole-query field match (exact / prefix / substring) can only promote it.
    """
    fields = [_norm(f) for f in raw_fields]
    words_by_field = [_WORD.findall(fn) for fn in fields]

    strengths = [_token_strength(t, fields, words_by_field) for t in tokens]
    if not strengths or min(strengths) == _S_NONE:
        token_tier = 0
        total = 0
    else:
        token_tier = _STRENGTH_TIER[min(strengths)]
        total = sum(strengths)

    whole = _S_NONE
    for fn in fields:
        if not fn:
            continue
        if fn == q:
            whole = _S_EXACT
            break
        if fn.startswith(q):
            whole = max(whole, _S_PREFIX)
        elif q in fn:
            whole = max(whole, _S_SUBSTR)

    tier = max(token_tier, _STRENGTH_TIER[whole])
    return tier, total + whole


def rank(rows: list[dict], query: str, limit: int = 500,
         search_tags: bool = False) -> list[dict]:
    q = _norm(query)
    raw = query.strip()
    tokens = tokenize(query)
    scored = []
    for r in rows:
        tier, total = _strong_score(
            q, tokens, [r.get("display_name"), r.get("artist"), r.get("title")])
        if raw.isdigit() and r.get("beatmapset_id") == int(raw):
            tier = _EXACT
        if tier == 0 and search_tags and tokens:
            # Opt-in weak match: creator + tags, every token must appear. Capped
            # at _WEAK so a tag hit can never outrank a real name/artist/title one.
            weak = " ".join(_norm(r.get(k)) for k in ("creator", "tags"))
            if weak and all(tok in weak for tok in tokens):
                tier = _WEAK
                total = _S_SUBSTR * len(tokens)
        if tier == 0:
            continue
        fz = _fuzzy(q, _norm(r.get("display_name")))
        name_len = len(r.get("display_name") or "")
        scored.append((tier, total, fz, -name_len, r.get("copy_attempts", 0), r))
    scored.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]), reverse=True)
    return [s[5] for s in scored[:limit]]


def search(db, query: str, limit: int = 500,
           search_tags: bool = False) -> list[dict]:
    """Structured filters (``star>5 mode=mania``) + free-text relevance search.

    The query is split into filters and free text (:mod:`rosu.query`). Filters are
    hard constraints applied as SQL; free text is ranked. A filters-only query has
    nothing to rank (``rank`` on zero tokens drops every row), so it returns the
    filter-recalled rows name-sorted instead.
    """
    from .query import parse
    parsed = parse(query)
    free = parsed.free_text.strip()
    if not free and not parsed.filters:
        return []
    if not free:   # filters only — no ranking, return name-sorted matches
        rows = db.filtered_tracks(parsed.filters, limit)
        db.attach_sources_bulk(rows)
        db.attach_difficulties_bulk(rows)
        return rows
    candidates = db.search_candidates(free, search_tags=search_tags,
                                      filters=parsed.filters)
    ranked = rank(candidates, free, limit, search_tags=search_tags)
    db.attach_sources_bulk(ranked)  # only the displayed rows — no N+1
    db.attach_difficulties_bulk(ranked)
    return ranked
