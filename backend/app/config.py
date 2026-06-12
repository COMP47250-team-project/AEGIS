from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    database_url_sync: str


    class Config:
        env_file = ".env.example"
        extra = "ignore"

settings = Settings()