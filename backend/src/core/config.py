from pydantic import BaseModel
from pydantic_settings import BaseSettings


class SessionConfig(BaseModel):
    cache_ttl_seconds: int = 3600
    key_prefix: str = "session"


class Settings(BaseSettings):
    environment: str = "development"
    mongodb_url: str = "mongodb://mongodb:27017/financial_agent_v2"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = "dev-secret-change-in-production"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    siliconflow_api_key: str = ""
    perigon_api_key: str = ""
    session: SessionConfig = SessionConfig()

    # Pool pipeline config
    news_cron_interval_hours: int = 2
    news_similarity_threshold: float = 0.75
    news_lexical_weight: float = 0.4
    news_base_half_life_hours: int = 24
    news_stale_threshold: int = 30
    news_max_age_days: int = 7
    value_stale_threshold: int = 20

    # Macro news pipeline config
    news_macro_quota_ratio: float = 0.4
    newsapi_api_key: str = ""
    newsapi_daily_limit: int = 100
    newsapi_agent_daily_cap: int = 50
    perigon_agent_daily_cap: int = 2

    model_config = {"env_file": [".env.base", ".env"], "env_file_encoding": "utf-8"}


settings = Settings()
