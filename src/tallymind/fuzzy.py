from __future__ import annotations

import difflib


def best_matches(query: str, candidates: list[str], limit: int = 5, cutoff: float = 0.35) -> list[str]:
    return difflib.get_close_matches(query, candidates, n=limit, cutoff=cutoff)


def resolve_one(query: str, candidates: list[str]) -> str | None:
    if query in candidates:
        return query
    matches = best_matches(query, candidates, limit=1)
    return matches[0] if matches else None
