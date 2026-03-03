from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from jose import JWTError
import logging
import uuid

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.user import User
from app.models.user_invite import UserInvite, InviteStatus
from app.models.oauth_state import OAuthState
from app.auth.security import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from app.auth.schemas import (
    LoginRequest, TokenResponse, RefreshRequest, UserOut, UserSummary,
    UserCreate, UserUpdate, PasswordResetRequest, GoogleOAuthStatus
)
from app.auth.dependencies import get_current_user, get_admin_user
from app.config import settings
from app.utils.time import utcnow
from app.services import api_credentials_service
from app.services import google_oauth_service

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    logger.info("Login attempt for user: %s", req.email)
    user = db.query(User).filter(User.email == req.email, User.is_active == True).first()
    
    # Check user exists and can use password auth
    if not user:
        logger.warning("Failed login attempt for user: %s", req.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if user has password auth enabled
    if not user.hashed_password:
        logger.warning("Password login attempted for Google-only user: %s", req.email)
        raise HTTPException(status_code=401, detail="This account uses Google sign-in. Please use the Google button to log in.")
    
    if not verify_password(req.password, user.hashed_password):
        logger.warning("Failed login attempt for user: %s", req.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.last_login = utcnow()
    db.commit()

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role, "is_restricted": user.is_restricted}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        token_data = {"sub": str(user.id), "email": user.email, "role": user.role, "is_restricted": user.is_restricted}
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/register", response_model=UserOut, status_code=201)
def register(req: UserCreate, db: Session = Depends(get_db)):
    """Public self-registration endpoint. Respects ENFORCE_DOMAIN_RESTRICTION setting."""
    email_lower = req.email.lower().strip()

    active_count = db.query(User).filter(User.is_active == True).count()
    if active_count >= settings.max_users:
        raise HTTPException(status_code=403, detail=f"Maximum user limit ({settings.max_users}) reached.")

    existing = db.query(User).filter(User.email == email_lower).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    TRUSTED_DOMAINS = ("@sarsonfunds.com", "@speranza.local")
    invite = None
    if settings.enforce_domain_restriction:
        if not any(email_lower.endswith(d) for d in TRUSTED_DOMAINS):
            if not req.invite_token:
                raise HTTPException(status_code=403, detail="Registration requires an invitation.")
            invite = (
                db.query(UserInvite)
                .filter(
                    UserInvite.email == email_lower,
                    UserInvite.token == req.invite_token,
                    UserInvite.status == InviteStatus.pending,
                    UserInvite.expires_at > utcnow(),
                )
                .first()
            )
            if not invite:
                raise HTTPException(status_code=403, detail="Registration requires an invitation.")

    user = User(
        id=uuid.uuid4(),
        email=email_lower,
        name=req.name,
        hashed_password=hash_password(req.password),
        role="user",
        auth_provider="local",
        is_restricted=invite is not None,  # Restricted if registered via invite (not domain)
    )
    db.add(user)
    if invite:
        invite.status = InviteStatus.accepted
        invite.accepted_at = utcnow()
    db.commit()
    db.refresh(user)
    return user


# ========== GOOGLE OAUTH ENDPOINTS (Phase 7) ==========

@router.get("/google/status", response_model=GoogleOAuthStatus)
def google_oauth_status(db: Session = Depends(get_db)):
    """Check if Google OAuth is configured and return login URL if enabled."""
    creds = api_credentials_service.get_all_decrypted(db, "google_oauth")
    client_id = creds.get("client_id", "")
    client_secret = creds.get("client_secret", "")
    
    if not client_id or not client_secret:
        return GoogleOAuthStatus(enabled=False)
    
    return GoogleOAuthStatus(
        enabled=True,
        login_url="/api/v1/auth/google/login"
    )


@router.get("/google/login")
def google_login(db: Session = Depends(get_db)):
    """Initiate Google OAuth flow. Redirects to Google consent screen."""
    creds = api_credentials_service.get_all_decrypted(db, "google_oauth")
    client_id = creds.get("client_id", "")
    
    if not client_id:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")
    
    # Generate CSRF state token
    state = google_oauth_service.generate_state()
    
    # Store state in database for validation
    redirect_uri = f"{settings.frontend_url}/api/v1/auth/google/callback"
    oauth_state = OAuthState(
        state=state,
        redirect_uri=redirect_uri,
    )
    db.add(oauth_state)
    db.commit()
    
    # Build authorization URL
    auth_url = google_oauth_service.build_auth_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
    )
    
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth callback.
    Validates state (CSRF), exchanges code for tokens, and logs in or creates user.
    """
    frontend_url = settings.frontend_url.rstrip("/")
    
    # Handle errors from Google
    if error:
        logger.warning(f"Google OAuth error: {error}")
        return RedirectResponse(f"{frontend_url}/login?error=oauth_failed")
    
    if not code or not state:
        return RedirectResponse(f"{frontend_url}/login?error=oauth_failed")
    
    # Validate state with atomic DELETE...RETURNING to prevent replay attacks
    from sqlalchemy import text
    result = db.execute(
        text("DELETE FROM oauth_states WHERE state = :state AND expires_at > NOW() RETURNING state"),
        {"state": state}
    )
    deleted_state = result.fetchone()
    db.commit()
    
    if not deleted_state:
        logger.warning("Invalid or expired OAuth state - possible CSRF or replay attack")
        return RedirectResponse(f"{frontend_url}/login?error=oauth_failed")
    
    # Get OAuth credentials
    creds = api_credentials_service.get_all_decrypted(db, "google_oauth")
    client_id = creds.get("client_id", "")
    client_secret = creds.get("client_secret", "")
    allowed_domains_str = creds.get("allowed_domains", "sarsonfunds.com")
    
    if not client_id or not client_secret:
        return RedirectResponse(f"{frontend_url}/login?error=oauth_failed")
    
    redirect_uri = f"{frontend_url}/api/v1/auth/google/callback"
    
    try:
        # Exchange code for tokens
        tokens = await google_oauth_service.exchange_code_for_tokens(
            code=code,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        
        # Get user info from Google
        user_info = await google_oauth_service.get_user_info(tokens["access_token"])
        
    except Exception as e:
        logger.error(f"Google OAuth token exchange failed: {e}")
        return RedirectResponse(f"{frontend_url}/login?error=oauth_failed")
    
    email = user_info.get("email", "").lower().strip()
    google_id = user_info.get("sub")
    name = user_info.get("name", "")
    avatar_url = user_info.get("picture")
    
    if not email or not google_id:
        return RedirectResponse(f"{frontend_url}/login?error=oauth_failed")
    
    # Parse allowed domains
    allowed_domains = google_oauth_service.parse_domains_string(allowed_domains_str)
    domain_allowed = google_oauth_service.is_domain_allowed(email, allowed_domains)
    
    # Check for invite (bypasses domain restriction)
    invite = (
        db.query(UserInvite)
        .filter(
            UserInvite.email == email,
            UserInvite.status.in_([InviteStatus.pending, InviteStatus.accepted]),
        )
        .first()
    )
    
    # Domain check: must be allowed domain OR have invite
    if not domain_allowed and not invite:
        logger.warning(f"Google OAuth rejected - domain not allowed: {email}")
        return RedirectResponse(f"{frontend_url}/login?error=domain_not_allowed")
    
    # Look for existing user
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        # Existing user - update Google ID and avatar if not set
        if not user.google_id:
            user.google_id = google_id
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
        if user.auth_provider == "local":
            user.auth_provider = "both"
        user.last_login = utcnow()
        db.commit()
    else:
        # Create new user
        # Check max users limit
        active_count = db.query(User).filter(User.is_active == True).count()
        if active_count >= settings.max_users:
            return RedirectResponse(f"{frontend_url}/login?error=max_users_reached")
        
        # Split name into first/last
        name_parts = name.split(" ", 1)
        first_name = name_parts[0] if name_parts else email.split("@")[0]
        
        # Determine if user should be restricted (invited but not from allowed domain)
        is_restricted = not domain_allowed and invite is not None
        
        user = User(
            id=uuid.uuid4(),
            email=email,
            name=name or first_name,
            google_id=google_id,
            avatar_url=avatar_url,
            auth_provider="google",
            role="member",
            is_active=True,
            is_restricted=is_restricted,
            last_login=utcnow(),
        )
        db.add(user)
        
        # Mark invite as accepted if it was pending
        if invite and invite.status == InviteStatus.pending:
            invite.status = InviteStatus.accepted
            invite.accepted_at = utcnow()
        
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user via Google OAuth: {email} (restricted={is_restricted})")
    
    # Create JWT token
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role, "is_restricted": user.is_restricted}
    access_token = create_access_token(token_data)
    
    # Redirect to frontend with token
    return RedirectResponse(f"{frontend_url}/auth/callback?token={access_token}")


# ========== USERS MANAGEMENT ==========

users_router = APIRouter(prefix="/api/v1/users", tags=["users"])


@users_router.get("/", response_model=list[UserSummary])
def list_users(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """List all users. Admin only."""
    return db.query(User).all()


@users_router.post("/", response_model=UserOut)
def create_user(req: UserCreate, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Create a new user. Admin only."""
    email_lower = req.email.lower().strip()

    # Max users check
    active_count = db.query(User).filter(User.is_active == True).count()
    if active_count >= settings.max_users:
        raise HTTPException(
            status_code=403,
            detail=f"Maximum user limit ({settings.max_users}) reached. Contact your administrator.",
        )

    existing = db.query(User).filter(User.email == email_lower).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Invite check: only enforced when ENFORCE_DOMAIN_RESTRICTION=true (production)
    TRUSTED_DOMAINS = ("@sarsonfunds.com", "@speranza.local")
    invite = None
    if settings.enforce_domain_restriction:
        if not any(email_lower.endswith(d) for d in TRUSTED_DOMAINS):
            invite = (
                db.query(UserInvite)
                .filter(
                    UserInvite.email == email_lower,
                    UserInvite.status == InviteStatus.pending,
                    UserInvite.expires_at > utcnow(),
                )
                .first()
            )
            if not invite:
                raise HTTPException(
                    status_code=403,
                    detail="Registration requires an invitation. Contact your administrator.",
                )

    user = User(
        id=uuid.uuid4(),
        email=email_lower,
        name=req.name,
        hashed_password=hash_password(req.password),
        role=req.role,
        auth_provider="local",
        is_restricted=invite is not None,  # Restricted if created via invite
    )
    db.add(user)

    # Mark invite as accepted
    if invite:
        invite.status = InviteStatus.accepted
        invite.accepted_at = utcnow()

    db.commit()
    db.refresh(user)
    return user


@users_router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Deactivate a user. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Prevent self-deactivation
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@users_router.post("/{user_id}/reset-password")
def admin_reset_password(user_id: uuid.UUID, req: PasswordResetRequest, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Reset a user's password. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(req.new_password)
    if user.auth_provider == "google":
        user.auth_provider = "both"
    db.commit()
    return {"message": "Password reset successfully"}


@users_router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get a single user. Users can view their own profile; admins can view any."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Non-admins can only view themselves
    if current_user.role not in ("admin", "owner") and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return user


@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, req: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update a user. Users can update their own profile (except role); admins can update any."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_admin = current_user.role in ("admin", "owner")
    is_self = current_user.id == user_id
    
    # Non-admins can only update themselves
    if not is_admin and not is_self:
        raise HTTPException(status_code=403, detail="Access denied")

    update_data = req.model_dump(exclude_unset=True)
    
    # Non-admins cannot change roles
    if "role" in update_data and not is_admin:
        raise HTTPException(status_code=403, detail="Only admins can change user roles")
    
    # Handle password separately
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
        if user.auth_provider == "google":
            update_data["auth_provider"] = "both"
    
    for k, v in update_data.items():
        setattr(user, k, v)
    
    db.commit()
    db.refresh(user)
    return user


@users_router.patch("/{user_id}/role")
def update_user_role(
    user_id: uuid.UUID,
    role: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Change a user's role. Admin only."""
    if role not in ("user", "admin", "owner"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'user', 'admin', or 'owner'")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.role = role
    db.commit()
    db.refresh(user)
    return {"message": f"Role updated to {role}", "user_id": str(user_id)}
