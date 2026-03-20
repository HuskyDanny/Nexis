from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    mongodb_url: str = "mongodb://mongodb:27017/financial_agent_v2"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = "dev-secret-change-in-production"
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env.base", "env_file_encoding": "utf-8"}


settings = Settings()
