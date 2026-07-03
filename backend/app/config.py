from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.example", extra="ignore")
    database_url: str = "postgresql+asyncpg://aegis:aegis_dev_pw@localhost:5432/aegis"
    database_url_sync: str = "postgresql://aegis:aegis_dev_pw@localhost:5432/aegis"
    jwt_secret_key: str = "change_me_to_a_random_64_char_string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    app_env: str = "development"
    # Override this in production with the actual Azure frontend FQDN.
    # Multiple origins: comma-separated string is parsed to list in the validator below.
    backend_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    log_level: str = "DEBUG"
    azure_service_bus_connection_string: str | None = None
    azure_service_bus_queue_name: str = "telemetry-events"
    score_queue_name: str = "score-jobs"
    aegis_events_queue_name: str = "aegis-events"
    scorer_batch_interval_seconds: int = 30
    scorer_max_delivery_attempts: int = 3

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> Any:
        if isinstance(v, str):
            # Handle comma-separated string from environment variable
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
