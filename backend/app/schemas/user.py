from pydantic import BaseModel, EmailStr
from typing import Optional

class UserSchema(BaseModel):
    id: str
    name: str
    email: EmailStr
    is_active: bool = True
    created_at: Optional[str] = None
