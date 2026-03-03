"""
Google OAuth 2.0 integration for Sarson CRM.
Uses authorization code flow for secure authentication.

Domain restriction: Only @sarsonfunds.com emails allowed by default.
Individual invites bypass the domain restriction (checked server-side).
"""
import secrets
import logging
from urllib.parse import urlencode
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Default allowed domains - can be overridden via crm_settings
DEFAULT_ALLOWED_DOMAINS = ["sarsonfunds.com"]


def generate_state() -> str:
    """Generate a cryptographically secure state token for CSRF protection."""
    return secrets.token_urlsafe(32)


def build_auth_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: Optional[list[str]] = None,
) -> str:
    """
    Build the Google OAuth authorization URL.
    
    Args:
        client_id: Google OAuth client ID
        redirect_uri: Callback URL after auth
        state: CSRF protection token
        scopes: OAuth scopes (defaults to openid, email, profile)
    """
    if scopes is None:
        scopes = ["openid", "email", "profile"]
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",  # Always show account picker
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """
    Exchange authorization code for access and refresh tokens.
    
    Returns:
        Dict with access_token, refresh_token (if offline access), expires_in, token_type
    
    Raises:
        httpx.HTTPStatusError: If token exchange fails
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


async def get_user_info(access_token: str) -> dict:
    """
    Fetch user profile from Google using access token.
    
    Returns:
        Dict with: sub (Google ID), email, email_verified, name, picture, given_name, family_name
    
    Raises:
        httpx.HTTPStatusError: If user info fetch fails
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


def is_domain_allowed(email: str, allowed_domains: list[str]) -> bool:
    """
    Check if email domain is in the allowed list.
    
    Args:
        email: User's email address
        allowed_domains: List of allowed domain names (without @)
    
    Returns:
        True if domain is allowed, False otherwise
    """
    if not email or "@" not in email:
        return False
    domain = email.split("@")[-1].lower().strip()
    return domain in [d.lower().strip() for d in allowed_domains]


def parse_domains_string(domains_str: str) -> list[str]:
    """
    Parse comma-separated domains string into a list.
    
    Args:
        domains_str: Comma-separated domain names (e.g., "sarsonfunds.com, example.com")
    
    Returns:
        List of cleaned domain names
    """
    if not domains_str:
        return DEFAULT_ALLOWED_DOMAINS.copy()
    return [d.strip().lower() for d in domains_str.split(",") if d.strip()]
