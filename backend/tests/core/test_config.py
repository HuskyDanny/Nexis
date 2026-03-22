from src.core.config import Settings


class TestPoolConfig:
    def test_default_news_cron_interval(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_cron_interval_hours == 2

    def test_default_news_similarity_threshold(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_similarity_threshold == 0.75

    def test_default_news_lexical_weight(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_lexical_weight == 0.4

    def test_default_news_base_half_life(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_base_half_life_hours == 24

    def test_default_news_stale_threshold(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_stale_threshold == 30

    def test_default_news_max_age_days(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.news_max_age_days == 7

    def test_default_value_stale_threshold(self):
        s = Settings(mongodb_url="mongodb://localhost:27017/test")
        assert s.value_stale_threshold == 20
