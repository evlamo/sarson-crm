"""Admin invite management endpoints."""
import uuid
import secrets
from datetime import datetime, timedelta
from app.utils.time import utcnow
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.user_invite import UserInvite, InviteStatus
from app.auth.dependencies import get_admin_user, get_current_user
from app.config import settings

router = APIRouter(prefix="/invites", tags=["invites"])


# ── Schemas ────────────────────────────────────────────────────────────────
class InviteCreate(BaseModel):
    email: EmailStr


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    token: str
    invite_url: str
    status: str
    invited_by: uuid.UUID
    invited_by_name: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InviteListItem(BaseModel):
    id: uuid.UUID
    email: str
    status: str
    invited_by: uuid.UUID
    invited_by_name: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InviteValidation(BaseModel):
    email: str
    valid: bool
    expired: bool


# ── Helpers ────────────────────────────────────────────────────────────────
def _build_invite_url(token: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/register?token={token}"


def _serialize_invite(invite: UserInvite, include_token: bool = False, include_url: bool = False) -> dict:
    data = {
        "id": invite.id,
        "email": invite.email,
        "status": invite.status.value if isinstance(invite.status, InviteStatus) else invite.status,
        "invited_by": invite.invited_by,
        "invited_by_name": invite.inviter.name if invite.inviter else None,
        "created_at": invite.created_at,
        "expires_at": invite.expires_at,
        "accepted_at": invite.accepted_at,
    }
    if include_token:
        data["token"] = invite.token
    if include_url:
        data["invite_url"] = _build_invite_url(invite.token)
    return data


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/", response_model=InviteOut)
def create_invite(
    body: InviteCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    email_lower = body.email.lower().strip()

    # Check max users won't be exceeded
    active_users = db.query(User).filter(User.is_active == True).count()
    pending_invites = db.query(UserInvite).filter(
        UserInvite.status == InviteStatus.pending,
        UserInvite.expires_at > utcnow(),
    ).count()
    if active_users + pending_invites >= settings.max_users:
        raise HTTPException(
            status_code=403,
            detail=f"Maximum user limit ({settings.max_users}) reached. Cannot create more invites.",
        )

    # Check no existing user with this email
    existing_user = db.query(User).filter(User.email == email_lower).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    # Check no pending invite for this email
    existing_invite = (
        db.query(UserInvite)
        .filter(
            UserInvite.email == email_lower,
            UserInvite.status == InviteStatus.pending,
            UserInvite.expires_at > utcnow(),
        )
        .first()
    )
    if existing_invite:
        raise HTTPException(status_code=400, detail="A pending invite for this email already exists.")

    invite = UserInvite(
        id=uuid.uuid4(),
        email=email_lower,
        invited_by=admin.id,
        token=secrets.token_hex(32),
        status=InviteStatus.pending,
        created_at=utcnow(),
        expires_at=utcnow() + timedelta(hours=72),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    result = _serialize_invite(invite, include_token=True, include_url=True)
    return result


@router.get("/", response_model=list[InviteListItem])
def list_invites(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    invites = db.query(UserInvite).order_by(UserInvite.created_at.desc()).all()
    # Never include token or URL in list responses
    return [_serialize_invite(inv, include_token=False, include_url=False) for inv in invites]


@router.delete("/{invite_id}")
def revoke_invite(
    invite_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    invite = db.query(UserInvite).filter(UserInvite.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != InviteStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending invites can be revoked")
    invite.status = InviteStatus.revoked
    db.commit()
    return {"message": "Invite revoked"}


@router.get("/validate/{token}", response_model=InviteValidation)
def validate_invite(token: str, db: Session = Depends(get_db)):
    invite = db.query(UserInvite).filter(UserInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite token")

    now = utcnow()
    expired = invite.expires_at < now
    valid = invite.status == InviteStatus.pending and not expired

    return InviteValidation(email=invite.email, valid=valid, expired=expired)
