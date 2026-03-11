from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from jose import JWTError
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models.user import User
from app.models.user_invite import UserInvite, InviteStatus
from app.models.password_reset import PasswordResetToken
from app.models.email_verification import EmailVerificationToken
from app.models.token_blacklist import TokenBlacklist
from app.models.mfa import MFASecret
from app.auth.security import (
    verify_password, hash_password, create_access_token, create_refresh_token, 
    decode_token, generate_reset_token, generate_email_verification_token,
    generate_totp_secret, verify_totp, get_totp_qr_code, generate_backup_codes,
    encrypt_data, decrypt_data
)
from app.auth.schemas import (
    LoginRequest, TokenResponse, RefreshRequest, UserOut, UserSummary, UserCreate, 
    UserUpdate, PasswordResetRequest, ForgotPasswordRequest, ResetPasswordRequest,
    VerifyEmailRequest, LogoutRequest, MFASetupResponse, MFAVerifyRequest, MFAEnableRequest, ChangePasswordRequest
)
from app.auth.dependencies import get_current_user, get_admin_user
from app.config import settings
from app.utils.time import utcnow
from app.services.email_service import get_email_service
import uuid
from datetime import timedelta, datetime, timezone

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ==================== AUTHENTICATION ENDPOINTS ====================

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    logger.info("Login attempt for user: %s", req.email)
    user = db.query(User).filter(User.email == req.email.lower(), User.is_active == True).first()
    if not user or not verify_password(req.password, user.hashed_password):
        logger.warning("Failed login attempt for user: %s", req.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

#     # Check if email is verified
#     email_verify = db.query(EmailVerificationToken).filter(
#         EmailVerificationToken.user_id == user.id,
#         EmailVerificationToken.is_verified == False
#     ).first()
#     if email_verify:
#         raise HTTPException(status_code=403, detail="Please verify your email before logging in")

    # Check if MFA is enabled
    mfa = db.query(MFASecret).filter(MFASecret.user_id == user.id, MFASecret.is_enabled == True).first()
    if mfa:
        raise HTTPException(status_code=403, detail="MFA verification required. Use /api/v1/auth/mfa/verify endpoint")

    user.last_login = utcnow()
    db.commit()

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
def refresh(request: Request, req: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Check if token is blacklisted
        token_jti = payload.get("jti")
        blacklisted = db.query(TokenBlacklist).filter(TokenBlacklist.token_jti == token_jti).first()
        if blacklisted:
            raise HTTPException(status_code=401, detail="Token has been revoked")
        
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Get current logged-in user info."""
    return current_user

@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, req: UserCreate, db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
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
    )
    db.add(user)
    db.flush()

    # Create email verification token
    verification_token = EmailVerificationToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=generate_email_verification_token(),
        email=email_lower,
        expires_at=utcnow() + timedelta(hours=settings.email_verification_token_expire_hours)
    )
    db.add(verification_token)

    if invite:
        invite.status = InviteStatus.accepted
        invite.accepted_at = utcnow()

    db.commit()
    db.refresh(user)

    # Send verification email in background
    background_tasks.add_task(send_email_verification_email, user.email, verification_token.token)

    return user

# ==================== PASSWORD RESET ENDPOINTS ====================

@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(request: Request, req: ForgotPasswordRequest, db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
    """Request password reset. Sends reset link to email."""
    email_lower = req.email.lower().strip()
    user = db.query(User).filter(User.email == email_lower).first()
    
    if not user:
        # Don't reveal if user exists
        return {"message": "If email exists, a password reset link has been sent"}
    
    # Invalidate old reset tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used == False
    ).update({"is_used": True})
    
    # Create new reset token
    reset_token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=generate_reset_token(),
        expires_at=utcnow() + timedelta(hours=settings.password_reset_token_expire_hours)
    )
    db.add(reset_token)
    db.commit()
    
    # Send reset email in background
    background_tasks.add_task(send_password_reset_email, user.email, reset_token.token)
    
    return {"message": "If email exists, a password reset link has been sent"}

@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(request: Request, req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using reset token."""
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == req.token,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > utcnow()
    ).first()
    
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hashed_password = hash_password(req.new_password)
    reset_token.is_used = True
    db.commit()
    
    logger.info("Password reset for user: %s", user.email)
    return {"message": "Password reset successfully"}

# ==================== EMAIL VERIFICATION ENDPOINTS ====================

@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email using verification token."""
    email_token = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token == req.token,
        EmailVerificationToken.is_verified == False,
        EmailVerificationToken.expires_at > utcnow()
    ).first()
    
    if not email_token:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    
    user = db.query(User).filter(User.id == email_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    email_token.is_verified = True
    email_token.verified_at = utcnow()
    db.commit()
    
    logger.info("Email verified for user: %s", user.email)
    return {"message": "Email verified successfully"}

# ==================== LOGOUT ENDPOINT ====================

@router.post("/logout")
def logout(request: Request, req: LogoutRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Logout current user by revoking token."""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    try:
        payload = decode_token(token)
        token_jti = payload.get("jti")
        token_exp = payload.get("exp")
        
        if not token_jti:
            raise HTTPException(status_code=400, detail="Invalid token")
        
        # Convert exp timestamp to datetime
        from datetime import datetime as dt
        expires_at = dt.fromtimestamp(token_exp, tz=timezone.utc)
        
        # Create TokenBlacklist entry
        blacklist_entry = TokenBlacklist(
            id=uuid.uuid4(),
            user_id=current_user.id,
            token_jti=token_jti,
            expires_at=expires_at
        )
        db.add(blacklist_entry)
        db.commit()
        
        logger.info("User logged out and token blacklisted: %s (JTI: %s)", current_user.email, token_jti)
        return {"message": "Logged out successfully"}
    except JWTError as e:
        logger.warning("Failed to blacklist token for user %s: %s", current_user.email, str(e))
        raise HTTPException(status_code=400, detail="Invalid token")

# ==================== MFA ENDPOINTS ====================



@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password."""
    # Verify current password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Hash new password
    new_hash = hash_password(payload.new_password)
    
    # Update password
    current_user.password_hash = new_hash
    db.commit()
    
    logger.info("Password changed for user: %s", current_user.email)
    return {"message": "Password changed successfully"}

@router.post("/mfa/setup", response_model=MFASetupResponse)
def setup_mfa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate MFA secret and QR code for user."""
    existing = db.query(MFASecret).filter(MFASecret.user_id == current_user.id).first()
    if existing and existing.is_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")
    
    secret = generate_totp_secret()
    backup_codes = generate_backup_codes()
    encrypted_secret = encrypt_data(secret)
    encrypted_backup_codes = encrypt_data(",".join(backup_codes))
    
    mfa_secret = MFASecret(
        id=uuid.uuid4(),
        user_id=current_user.id,
        secret_key=encrypted_secret,
        backup_codes=encrypted_backup_codes,
        is_enabled=False
    )
    
    db.add(mfa_secret)
    db.commit()
    
    qr_code_url = get_totp_qr_code(secret, current_user.email)
    
    return MFASetupResponse(
        secret=secret,
        qr_code_url=qr_code_url,
        backup_codes=backup_codes
    )

@router.post("/mfa/enable")
def enable_mfa(req: MFAEnableRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Enable MFA after verifying code."""
    if not verify_password(req.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    mfa_secret = db.query(MFASecret).filter(MFASecret.user_id == current_user.id).first()
    if not mfa_secret:
        raise HTTPException(status_code=400, detail="Setup MFA first with /mfa/setup")
    
    if mfa_secret.is_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")
    
    # Decrypt and verify code
    secret = decrypt_data(mfa_secret.secret_key)
    if not verify_totp(secret, req.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    
    mfa_secret.is_enabled = True
    mfa_secret.enabled_at = utcnow()
    db.commit()
    
    logger.info("MFA enabled for user: %s", current_user.email)
    return {"message": "MFA enabled successfully"}

@router.post("/mfa/disable")
def disable_mfa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Disable MFA for user."""
    mfa_secret = db.query(MFASecret).filter(MFASecret.user_id == current_user.id, MFASecret.is_enabled == True).first()
    if not mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not enabled")
    
    mfa_secret.is_enabled = False
    db.commit()
    
    logger.info("MFA disabled for user: %s", current_user.email)
    return {"message": "MFA disabled successfully"}

# ==================== USER MANAGEMENT ENDPOINTS ====================

users_router = APIRouter(prefix="/api/v1/users", tags=["users"])

@users_router.get("/", response_model=list[UserSummary])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List all users."""
    query = db.query(User)
    if current_user.role != "admin":
        query = query.filter(User.is_active == True)
    return query.all()

@users_router.post("/", response_model=UserOut)
def create_user(req: UserCreate, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Create new user (admin only)."""
    email_lower = req.email.lower().strip()

    active_count = db.query(User).filter(User.is_active == True).count()
    if active_count >= settings.max_users:
        raise HTTPException(
            status_code=403,
            detail=f"Maximum user limit ({settings.max_users}) reached. Contact your administrator.",
        )

    existing = db.query(User).filter(User.email == email_lower).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

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
    )
    db.add(user)

    # Create email verification token
    verification_token = EmailVerificationToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=generate_email_verification_token(),
        email=email_lower,
        expires_at=utcnow() + timedelta(hours=settings.email_verification_token_expire_hours)
    )
    db.add(verification_token)

    if invite:
        invite.status = InviteStatus.accepted
        invite.accepted_at = utcnow()

    db.commit()
    db.refresh(user)
    return user

@users_router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Deactivate a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user

@users_router.post("/{user_id}/reset-password")
def admin_reset_password(user_id: uuid.UUID, req: PasswordResetRequest, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Admin reset user password (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"message": "Password reset successfully"}

@users_router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, req: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update user (own account or admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    update_data = req.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
    for k, v in update_data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user

# ==================== EMAIL SENDING HELPERS ====================

def send_password_reset_email(email: str, token: str):
    """Send password reset email via SendGrid."""
    try:
        email_service = get_email_service()
        success = email_service.send_password_reset_email(email, token)
        if success:
            logger.info("Password reset email sent successfully to %s", email)
        else:
            logger.error("Failed to send password reset email to %s", email)
    except Exception as e:
        logger.error("Error sending password reset email to %s: %s", email, str(e))

def send_email_verification_email(email: str, token: str):
    """Send email verification email via SendGrid."""
    try:
        email_service = get_email_service()
        success = email_service.send_email_verification_email(email, token)
        if success:
            logger.info("Email verification email sent successfully to %s", email)
        else:
            logger.error("Failed to send email verification email to %s", email)
    except Exception as e:
        logger.error("Error sending email verification email to %s: %s", email, str(e))
