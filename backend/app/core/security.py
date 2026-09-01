import hashlib
import hmac
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from passlib.context import CryptContext
from backend.app.core.config import settings

# Passlib CryptContext for secure password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against stored password hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Fallback PBKDF2 verification if legacy/simple hash
        if ":" in hashed_password:
            salt, stored_hash = hashed_password.split(":", 1)
            computed = hashlib.pbkdf2_hmac(
                "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000
            ).hex()
            return hmac.compare_digest(computed, stored_hash)
        return False

def get_password_hash(password: str) -> str:
    """Generate secure bcrypt password hash."""
    try:
        return pwd_context.hash(password)
    except Exception:
        import secrets
        salt = secrets.token_hex(16)
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
        ).hex()
        return f"{salt}:{computed}"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encode JWT access token with expiration payload."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
