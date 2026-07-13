from tallymind.fuzzy import best_matches, resolve_one


CANDIDATES = ["VRO Technology", "ABC Traders", "XYZ Textiles Pvt Ltd", "Ramesh Patel"]


def test_best_matches_ranks_closest_first() -> None:
    matches = best_matches("VRO", CANDIDATES)
    assert matches[0] == "VRO Technology"


def test_best_matches_respects_limit() -> None:
    matches = best_matches("a", CANDIDATES, limit=2)
    assert len(matches) <= 2


def test_resolve_one_returns_exact_match_even_with_close_fuzzy_alternatives() -> None:
    assert resolve_one("ABC Traders", CANDIDATES) == "ABC Traders"


def test_resolve_one_returns_fuzzy_match_when_no_exact() -> None:
    assert resolve_one("VRO", CANDIDATES) == "VRO Technology"


def test_resolve_one_returns_none_when_nothing_close() -> None:
    assert resolve_one("Completely Unrelated Name Zzz", CANDIDATES) is None
