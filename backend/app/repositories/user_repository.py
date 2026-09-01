from typing import Optional
from sqlalchemy.orm import Session
from backend.app.db.models.user import UserDB
from backend.app.core.security import get_password_hash

class UserRepository:
    def get_by_id(self, db: Session, user_id: str) -> Optional[UserDB]:
        return db.query(UserDB).filter(UserDB.id == user_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[UserDB]:
        return db.query(UserDB).filter(UserDB.email == email.lower().strip()).first()

    def create(self, db: Session, name: str, email: str, password: str) -> UserDB:
        hashed_password = get_password_hash(password)
        db_user = UserDB(
            name=name.strip(),
            email=email.lower().strip(),
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

user_repository = UserRepository()
