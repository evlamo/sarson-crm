from pydantic_settings import BaseSettings
from functools import lru_cache
import secrets

class Settings(BaseSettings):
    database_url: str = "postgresql://agentstevesmith@localhost:5432/crm_dev"
    redis_url: str = "redis://localhost:6379/0"
    # In production, set SECRET_KEY env var to a strong random 64-char string.
    # Dev fallback generates a random key each restart (tokens invalidated on restart — acceptable for dev).
    secret_key: str = secrets.token_hex(32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    sendgrid_api_key: str = ""
    from_email: str = "noreply@speranza.local"
    from_name: str = "Speranza CRM"
    environment: str = "development"
    frontend_url: str = "http://localhost:3000"
    mailchimp_api_key: str = ""
    mailchimp_server_prefix: str = "us1"
    mailchimp_audience_id: str = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
