from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from jose import JWTError
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models.user import User
from app.models.user_invite import UserInvite, InviteStatus
from app.auth.security import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from app.auth.schemas import LoginRequest, TokenResponse, RefreshRequest, UserOut, UserSummary, UserCreate, UserUpdate, PasswordResetRequest
from app.auth.dependencies import get_current_user, get_admin_user
from app.config import settings
from app.utils.time import utcnow
import uuid

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    logger.info("Login attempt for user: %s", req.email)
    user = db.query(User).filter(User.email == req.email, User.is_active == True).first()
    if not user or not verify_password(req.password, user.hashed_password):
        logger.warning("Failed login attempt for user: %s", req.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.last_login = utcnow()
    db.commit()

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
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
        token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
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
    )
    db.add(user)
    if invite:
        invite.status = InviteStatus.accepted
        invite.accepted_at = utcnow()
    db.commit()
    db.refresh(user)
    return user


# Users management
users_router = APIRouter(prefix="/api/v1/users", tags=["users"])

@users_router.get("/", response_model=list[UserSummary])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(User)
    if current_user.role != "admin":
        query = query.filter(User.is_active == True)
    return query.all()

@users_router.post("/", response_model=UserOut)
def create_user(req: UserCreate, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
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
    # In dev/testing, any email can register freely.
    # @sarsonfunds.com and @speranza.local always bypass (speranza.local = internal admin accounts)
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

    # Mark invite as accepted
    if invite:
        invite.status = InviteStatus.accepted
        invite.accepted_at = utcnow()

    db.commit()
    db.refresh(user)
    return user

@users_router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user

@users_router.post("/{user_id}/reset-password")
def admin_reset_password(user_id: uuid.UUID, req: PasswordResetRequest, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"message": "Password reset successfully"}

@users_router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, req: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
