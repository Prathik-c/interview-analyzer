from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.db.session import engine

router = APIRouter()

@router.get("/health")
async def health_check():
    db_status = "connected"
    try:
        with engine.connect() as conn:
            pass
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "online",
        "app_title": settings.PROJECT_NAME,
        "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL,
        "database_status": db_status
    }
