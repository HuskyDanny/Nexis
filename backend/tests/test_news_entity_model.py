from src.models.news_entity import NewsEntity


def test_news_entity_has_scope_field():
    e = NewsEntity(id="t1", canonical_title="Test", summary="s")
    assert e.scope == 2  # default


def test_news_entity_has_origin_field():
    e = NewsEntity(id="t1", canonical_title="Test", summary="s")
    assert e.origin == "perigon"


def test_news_entity_has_story_cluster_size():
    e = NewsEntity(id="t1", canonical_title="Test", summary="s")
    assert e.story_cluster_size == 1
