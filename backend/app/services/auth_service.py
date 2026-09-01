from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.repositories.user_repository import user_repository
from backend.app.core.security import verify_password, create_access_token
from backend.app.schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from fastapi import HTTPException, status

class AuthService:
    def register_user(self, db: Session, req: UserRegisterRequest) -> UserResponse:
        existing = user_repository.get_by_email(db, req.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists."
            )
        user = user_repository.create(db, req.name, req.email, req.password)
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None
        )

    def login_user(self, db: Session, req: UserLoginRequest) -> TokenResponse:
        user = user_repository.get_by_email(db, req.email)
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive."
            )

        token = create_access_token({"sub": user.id, "email": user.email})
        user_resp = UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None
        )
        return TokenResponse(access_token=token, token_type="bearer", user=user_resp)

auth_service = AuthService()
