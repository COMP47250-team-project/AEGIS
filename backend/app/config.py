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
    acs_connection_string: str | None = None
    acs_sender_address: str | None = None
    frontend_base_url: str = "http://localhost:5173"

    # ---------------------------------------------------------------------------
    # AI features (1A integrity brief, 1B grading, 1C collusion)
    # Priority: Azure OpenAI -> Ollama -> dev stub
    # Unset all azure_openai_* vars to fall back to Ollama or the dev stub.
    # ---------------------------------------------------------------------------
    ai_features_enabled: bool = True

    # Azure OpenAI (production)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2025-01-01-preview"
    # Deploy gpt-4.1 for chat; text-embedding-3-small for embeddings
    azure_openai_chat_deployment: str = "gpt-4.1"
    azure_openai_embed_deployment: str = "text-embedding-3-small"

    # Ollama (local twin — OpenAI-compatible /v1 API)
    # e.g. http://ollama:11434/v1  (docker compose)  or  http://localhost:11434/v1
    ollama_base_url: str | None = None
    ollama_chat_model: str = "qwen3:8b"
    ollama_embed_model: str = "nomic-embed-text"

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> Any:
        if isinstance(v, str):
            # Handle comma-separated string from environment variable
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
