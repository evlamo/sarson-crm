from pydantic_settings import BaseSettings
from functools import lru_cache
import logging
import secrets

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    database_url: str = "postgresql://agentstevesmith@localhost:5432/crm_dev"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    sendgrid_api_key: str = ""
    sendgrid_webhook_verification_key: str = ""
    from_email: str = "noreply@speranza.local"
    from_name: str = "Speranza CRM"
    environment: str = "development"
    frontend_url: str = "http://localhost:3000"
    mailchimp_api_key: str = ""
    mailchimp_server_prefix: str = "us1"
    mailchimp_audience_id: str = ""
    mailchimp_webhook_secret: str = ""
    mailchimp_from_email: str = "info@sarsonfunds.com"
    max_users: int = 15
    enforce_domain_restriction: bool = False  # Set to true in production to require @sarsonfunds.com or invite

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    s = Settings()
    if not s.secret_key:
        if s.environment == "production":
            raise RuntimeError("SECRET_KEY must be set in production")
        s.secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY not set — using ephemeral key. All sessions will reset on restart.")
    return s


settings = get_settings()
