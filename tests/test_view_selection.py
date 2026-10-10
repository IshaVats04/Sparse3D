import pytest

from src.reconstruction.view_selection import select_views

NAMES = [f"v{i}" for i in range(6)]


def test_all_views_returned_when_k_equals_n():
    assert select_views(NAMES, 6, "random") == NAMES


def test_uniform_is_evenly_spaced():
    picked = select_views(NAMES, 3, "uniform")
    assert picked[0] == "v0" and picked[-1] == "v5" and len(set(picked)) == 3
    assert len(set(select_views(NAMES, 4, "uniform"))) == 4


def test_non_uniform_is_contiguous_block():
    assert select_views(NAMES, 3, "non_uniform") == ["v0", "v1", "v2"]


def test_random_is_reproducible_and_distinct():
    a = select_views(NAMES, 4, "random", seed=7)
    assert a == select_views(NAMES, 4, "random", seed=7)
    assert len(set(a)) == 4


def test_overlap_arrangements_follow_matches():
    # v0-v1-v2 strongly connected, v5 isolated
    pairs = [{"a": "v0", "b": "v1", "matches": 400}, {"a": "v1", "b": "v2", "matches": 380},
             {"a": "v0", "b": "v2", "matches": 350}, {"a": "v2", "b": "v3", "matches": 50},
             {"a": "v3", "b": "v4", "matches": 40}, {"a": "v4", "b": "v5", "matches": 5}]
    high = select_views(NAMES, 3, "high_overlap", pairs)
    low = select_views(NAMES, 3, "low_overlap", pairs)
    assert high == ["v0", "v1", "v2"]
    assert "v5" in low and low != high


def test_unknown_arrangement_rejected():
    with pytest.raises(ValueError):
        select_views(NAMES, 3, "spiral")
