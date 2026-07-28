from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    postgres_host: str
    postgres_port: int = 5432
    postgres_user: str
    postgres_password: str
    postgres_db: str

    redis_url: str

    celery_broker_url: str
    celery_result_backend: str

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    outbound_webhook_url: str | None = None
    outbound_webhook_timeout_seconds: int = 10

    cors_allowed_origins: list[str] = ["*"]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
