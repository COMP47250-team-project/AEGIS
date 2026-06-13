from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
<<<<<<< HEAD
    model_config = SettingsConfigDict(env_file=".env.example", extra="ignore")

    database_url: str = "postgresql+asyncpg://aegis:aegis_dev_pw@localhost:5432/aegis"
    database_url_sync: str = "postgresql://aegis:aegis_dev_pw@localhost:5432/aegis"

    jwt_secret_key: str = "change_me_to_a_random_64_char_string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    app_env: str = "development"
    backend_cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    log_level: str = "DEBUG"

    # Azure Service Bus — optional; scoring dispatch is skipped when not set
    azure_service_bus_connection_string: str | None = None
    azure_service_bus_queue_name: str = "telemetry-events"
    score_queue_name: str = "score-jobs"
=======



settings = Settings()
