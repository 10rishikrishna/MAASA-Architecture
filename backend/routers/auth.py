# backend/routers/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from backend.database import get_db, User
from backend.auth import get_password_hash, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user_id: str
    email: str
    name: str
    token: str
    plan: str

class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    plan: str

@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    new_user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        name=payload.name,
        plan="free"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Token
    token = create_access_token(data={"sub": new_user.id})
    
    return AuthResponse(
        user_id=new_user.id,
        email=new_user.email,
        name=new_user.name,
        token=token,
        plan=new_user.plan
    )

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    token = create_access_token(data={"sub": user.id})
    
    return AuthResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        token=token,
        plan=user.plan
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        user_id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        plan=current_user.plan
    )
