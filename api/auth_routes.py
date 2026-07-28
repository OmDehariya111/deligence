import os

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import timedelta
from pydantic import BaseModel, EmailStr

from api.database import get_db
from api.models import User
from api.auth_utils import verify_password, get_password_hash, create_access_token, verify_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["auth"])

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    full_name: str | None = None
    email: EmailStr
    is_admin: bool = False
    tier: str = "FREE"
    credits: int = 5
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: str
    email: EmailStr

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str


@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    normalized_email = str(user.email).lower()
    db_user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=normalized_email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login")
def login(user_credentials: UserLogin, response: Response, db: Session = Depends(get_db)):
    normalized_email = str(user_credentials.email).lower()
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive")
        
    if not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "id": user.id}, expires_delta=access_token_expires
    )
    
    # Remove the legacy path-scoped cookie before setting the app-wide session.
    # Without this, existing users may send two access_token cookies after deploy.
    response.delete_cookie("access_token", path="/api/v1/auth")

    # Set HttpOnly Cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        path="/",
        secure=os.getenv("ENVIRONMENT", "development").lower() == "production",
    )
    
    return {"message": "Successfully logged in", "user": {"id": user.id, "email": user.email, "full_name": user.full_name, "is_admin": user.is_admin, "tier": user.tier.value if user.tier else "FREE", "credits": user.credits}}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("access_token", path="/api/v1/auth")
    return {"message": "Successfully logged out"}

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    try:
        scheme, token_data = token.split()
        if scheme.lower() != "bearer":
            raise Exception("Invalid scheme")
    except:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
        
    payload = verify_access_token(token_data)
    user_email = payload.get("sub")
    if user_email is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    user = db.query(User).filter(func.lower(User.email) == user_email.lower()).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
    return user

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
def update_me(user_update: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if user_update.email != current_user.email:
        # Check if new email is already taken
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
            
    current_user.full_name = user_update.full_name
    current_user.email = user_update.email
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/password")
def update_password(password_update: PasswordUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(password_update.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")
        
    current_user.hashed_password = get_password_hash(password_update.new_password)
    db.commit()
    return {"message": "Password updated successfully"}
