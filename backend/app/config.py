from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str = "postgresql://agentstevesmith@localhost:5432/crm_dev"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "speranza-crm-dev-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    sendgrid_api_key: str = ""
    from_email: str = "noreply@speranza.local"
    from_name: str = "Speranza CRM"
    environment: str = "development"
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
