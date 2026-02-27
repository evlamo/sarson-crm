from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from jose import JWTError
from app.database import get_db
from app.models.user import User
from app.auth.security import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from app.auth.schemas import LoginRequest, TokenResponse, RefreshRequest, UserOut, UserCreate, UserUpdate
from app.auth.dependencies import get_current_user, get_admin_user
import uuid

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email, User.is_active == True).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.last_login = datetime.utcnow()
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

# Users management
users_router = APIRouter(prefix="/api/v1/users", tags=["users"])

@users_router.get("/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(User).filter(User.is_active == True).all()

@users_router.post("/", response_model=UserOut)
def create_user(req: UserCreate, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        id=uuid.uuid4(),
        email=req.email,
        name=req.name,
        hashed_password=hash_password(req.password),
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

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
