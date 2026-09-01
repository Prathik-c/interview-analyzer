from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.core.security import decode_access_token
from backend.app.repositories.user_repository import user_repository
from backend.app.db.models.user import UserDB

security_scheme = HTTPBearer(auto_error=False)

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[UserDB]:
    """Retrieve current authenticated user if Bearer token present, else None."""
    if not credentials or not credentials.credentials:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    user_id = payload["sub"]
    user = user_repository.get_by_id(db, user_id)
    if user and user.is_active:
        return user
    return None

def get_current_user(
    user: Optional[UserDB] = Depends(get_current_user_optional)
) -> UserDB:
    """Mandatory JWT authentication dependency."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user
