"""
Central place for all configuration. Everything comes from environment
variables (loaded from a .env file in local dev) so we never hardcode
secrets like the mock API key.
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Mock Instagram API
    mock_api_base_url: str = "https://pseudogram-api.onrender.com"
    mock_api_key: str = ""

    # Database
    database_url: str = "postgresql+psycopg2://linkplease:linkplease@localhost:5432/linkplease"

    @field_validator("database_url")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    # Redis (unused by design - see README)
    redis_url: str = ""

    # Rate limiting: the mock API allows DM_RATE_LIMIT_MAX sends per
    # DM_RATE_LIMIT_WINDOW_SECONDS, on a rolling basis.
    dm_rate_limit_max: int = 10
    dm_rate_limit_window_seconds: int = 60

    # Retry policy
    dm_max_attempts: int = 6
    dm_retry_base_seconds: int = 5
    dm_retry_max_seconds: int = 300

    # Worker loop tuning
    worker_poll_interval_seconds: float = 1.0
    reconcile_poll_interval_seconds: float = 5.0


settings = Settings()
