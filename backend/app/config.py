from pydantic_settings import BaseSettings
from functools import lru_cache
import logging
import secrets

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    database_url: str = "postgresql://agentstevesmith@localhost:5432/crm_dev"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = ""
    encryption_key: str = ""  # Fernet key for encrypting sensitive data
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    password_reset_token_expire_hours: int = 24
    email_verification_token_expire_hours: int = 24
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

    # Google Ads OCT
    google_ads_client_id: str = ""
    google_ads_client_secret: str = ""
    google_ads_refresh_token: str = ""
    google_ads_developer_token: str = ""
    google_ads_customer_id: str = ""
    google_ads_manager_customer_id: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    from cryptography.fernet import Fernet
    
    s = Settings()
    if not s.secret_key:
        if s.environment == "production":
            raise RuntimeError("SECRET_KEY must be set in production")
        s.secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY not set — using ephemeral key. All sessions will reset on restart.")
    
    if not s.encryption_key:
        if s.environment == "production":
            raise RuntimeError("ENCRYPTION_KEY must be set in production")
        s.encryption_key = Fernet.generate_key().decode()
        logger.warning("ENCRYPTION_KEY not set — using ephemeral key. Encrypted data will be lost on restart.")
    
    return s


settings = get_settings()
