from src.services.cache import parent_set_hash


def test_parent_set_hash_deterministic():
    """Same IDs in any order produce the same hash."""
    h1 = parent_set_hash(["b", "a", "c"])
    h2 = parent_set_hash(["c", "a", "b"])
    assert h1 == h2


def test_parent_set_hash_different_sets_differ():
    h1 = parent_set_hash(["a", "b"])
    h2 = parent_set_hash(["a", "c"])
    assert h1 != h2


def test_parent_set_hash_empty():
    h = parent_set_hash([])
    assert isinstance(h, str)
    assert len(h) == 16


def test_parent_set_hash_length():
    h = parent_set_hash(["news_001", "news_002", "news_003"])
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)
